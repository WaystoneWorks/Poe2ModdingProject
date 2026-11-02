//! `cargo xtask game-test <scenario>`: one unattended in-game test with no human (PLAN T1).
//!
//! In order: take `runtime/client.lock`, check that `GameFiles/` is a current private
//! standalone deploy (deploys when the built DLLs differ), make sure Steam runs, build the
//! server and start it with the dev config (plus the scenario's overrides), sign the test
//! account in with a Remember Me token, launch the client, press Play, run the scenario's steps,
//! close the client and the server, and print a short pass/fail summary. Everything else goes
//! to `runtime/game-test/<scenario>-<time>/` (server log, client launcher output, hook log,
//! the new part of `Client.txt`, `summary.txt`).
//!
//! Scenario files are TOML in `scripts/game-test/` (format: docs/guides/setup.md, "Game tests").
//! The display is behind `--display`: `desktop` (the normal desktop, the only tested one) or
//! `gamescope` (nested headless gamescope, PLAN T0, untested until gamescope is installed).

use std::{
    fs,
    io::Write as _,
    os::unix::process::CommandExt as _,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result, bail};
use poe_config::Config;
use regex::Regex;
use serde::Deserialize;

/// Where scenario names are looked up.
const SCENARIO_DIR: &str = "scripts/game-test";
const LOCK: &str = "runtime/client.lock";
/// The client's settings file in the test prefix (input mode lives there).
const PREFIX_INI: &str =
    "pfx/drive_c/users/steamuser/Documents/My Games/Path of Exile 2/poe2_production_Config.ini";

#[derive(Clone, Copy, PartialEq, Eq, clap::ValueEnum)]
pub enum Display {
    /// The user's normal desktop (the window titled "PoE2 Test Client").
    Desktop,
    /// Nested gamescope with `GAME_TEST_GAMESCOPE_ARGS` (default `--backend headless -W 2560 -H 1440`).
    Gamescope,
}

#[derive(clap::Args)]
pub struct Args {
    /// Scenario name (`scripts/game-test/<name>.toml`) or a path to a scenario file.
    scenario: String,
    /// Where the client window goes.
    #[arg(long, value_enum, default_value = "desktop")]
    display: Display,
    /// Do not build the client DLLs and the server first (still deploys when GameFiles differs
    /// from the last build).
    #[arg(long)]
    no_build: bool,
    /// Seconds to wait for the login (the client takes about 2 minutes to start).
    #[arg(long, default_value_t = 240)]
    login_timeout: u64,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Scenario {
    #[serde(default)]
    description: String,
    #[serde(default = "default_account")]
    account: String,
    /// Class and area of the character made on the account's first use.
    #[serde(default = "default_class")]
    class: String,
    #[serde(default = "default_area")]
    area: String,
    /// `wasd` or `mouse_and_keyboard`: written to the test prefix while the client is closed and
    /// restored afterwards. Unset: left as it is.
    input_mode: Option<String>,
    /// Extra client environment (`POE_HOOK_*`).
    #[serde(default)]
    client_env: toml::Table,
    /// Overrides on the dev config, `"section.key" = value` (`"dev.drift_check" = true`).
    #[serde(default)]
    server: toml::Table,
    #[serde(default, rename = "step")]
    steps: Vec<Step>,
}

fn default_account() -> String {
    "testrun".into()
}
fn default_class() -> String {
    "DexFourDefault".into()
}
fn default_area() -> String {
    "G1_town".into()
}

/// One scenario step; exactly one action field is set.
#[derive(Deserialize, Default)]
#[serde(deny_unknown_fields)]
struct Step {
    /// Label in the summary.
    name: Option<String>,
    /// `poe-hook.keys` entries (one per line or whitespace-separated; docs/guides/setup.md).
    keys: Option<String>,
    /// A server command over the debug link (`cmd:` entry).
    cmd: Option<String>,
    /// Pause.
    wait_ms: Option<u64>,
    /// Pass when this regex appears in `log` after the step starts (`since = "start"`: since the
    /// scenario started) within `timeout_s`.
    expect_log: Option<String>,
    /// Fail when this regex appears in `log` since the scenario started.
    reject_log: Option<String>,
    /// `server` (default), `hook` (GameFiles/poe-hook.log) or `client` (Client.txt).
    log: Option<String>,
    since: Option<String>,
    timeout_s: Option<u64>,
}

/// The run: files, children and what to undo; `Drop` cleans up whatever is left.
struct Run {
    root: PathBuf,
    dir: PathBuf,
    game: PathBuf,
    prefix: PathBuf,
    server: Option<Child>,
    client: Option<Child>,
    ini_backup: Option<String>,
    client_txt_start: u64,
    lock_taken: bool,
}

pub fn run(root: &Path, config_path: &Path, prefix: &Path, args: Args) -> Result<()> {
    let scenario_path = scenario_path(root, &args.scenario)?;
    let scenario: Scenario = toml::from_str(
        &fs::read_to_string(&scenario_path)
            .with_context(|| format!("reading {}", scenario_path.display()))?,
    )
    .with_context(|| format!("parsing {}", scenario_path.display()))?;
    let name = scenario_path.file_stem().unwrap().to_string_lossy().into_owned();
    let dir = root.join("runtime/game-test").join(format!("{name}-{}", stamp()));
    fs::create_dir_all(&dir)?;
    let base = Config::load(config_path)?;
    let game = base.game.game_dir.clone();
    let mut run = Run {
        root: root.to_owned(),
        dir: dir.clone(),
        game,
        prefix: prefix.to_owned(),
        server: None,
        client: None,
        ini_backup: None,
        client_txt_start: 0,
        lock_taken: false,
    };
    println!("game-test {name}: {}", scenario.description);
    println!("logs: {}", dir.display());
    let mut results: Vec<(String, bool, String)> = Vec::new();
    let outcome = run.execute(&args, &scenario, &mut results);
    run.shutdown();
    if let Err(e) = &outcome {
        results.push(("setup".into(), false, format!("{e:#}")));
    }
    run.collect();
    for (label, re) in [("server panic", "panicked at"), ("hook panic", "PANIC:")] {
        let log = if label.starts_with("server") { "server" } else { "hook" };
        if let Some(line) = run.find(log, re, 0)? {
            results.push((label.into(), false, line));
        }
    }
    let pass = !results.is_empty() && results.iter().all(|r| r.1);
    let mut summary = format!("game-test {name}: {}\n", if pass { "PASS" } else { "FAIL" });
    for (label, ok, detail) in &results {
        summary += &format!("  {} {label}: {detail}\n", if *ok { "ok  " } else { "FAIL" });
    }
    summary += &format!("logs: {}\n", dir.display());
    fs::write(dir.join("summary.txt"), &summary)?;
    print!("{summary}");
    drop(run);
    if !pass {
        std::process::exit(1);
    }
    Ok(())
}

fn scenario_path(root: &Path, s: &str) -> Result<PathBuf> {
    let p = PathBuf::from(s);
    if p.is_file() {
        return Ok(p);
    }
    let named = root.join(SCENARIO_DIR).join(format!("{s}.toml"));
    if named.is_file() {
        return Ok(named);
    }
    bail!("no scenario {s} ({} or a file path)", named.display())
}

fn stamp() -> String {
    Command::new("date")
        .arg("+%Y%m%d-%H%M%S")
        .output()
        .ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs().to_string())
}

impl Run {
    fn execute(
        &mut self,
        args: &Args,
        sc: &Scenario,
        results: &mut Vec<(String, bool, String)>,
    ) -> Result<()> {
        self.take_lock()?;
        self.check_deploy(args.no_build)?;
        ensure_steam()?;
        let cfg = self.server_config(sc)?;
        let bin = self.start_server(&cfg, args.no_build)?;
        let token = self.sign_in(&bin, &cfg, sc)?;
        crate::login_token(&self.prefix, &sc.account, &token)?;
        drop(token);
        if let Some(mode) = &sc.input_mode {
            self.set_input_mode(mode)?;
        }
        self.launch_client(args.display, sc)?;
        // Login: the client presses Login by itself (auto_keys at 20 s); then Play.
        let t = Duration::from_secs(args.login_timeout);
        let login = format!("authenticated account={}", regex::escape(&sc.account));
        self.wait_log("server", &login, 0, t)
            .context("no login (client start, Steam or the token)")?;
        std::thread::sleep(Duration::from_secs(3));
        self.send_keys("0x0d")?;
        let entered = self
            .wait_log("server", "player entered the world", 0, Duration::from_secs(120))
            .context("did not enter the world after Play")?;
        results.push(("login".into(), true, short(&entered)));
        for (i, step) in sc.steps.iter().enumerate() {
            let label = step.name.clone().unwrap_or_else(|| format!("step {}", i + 1));
            let r = self.step(step);
            let failed = r.is_err();
            results.push(match r {
                Ok(detail) => (label, true, detail),
                Err(e) => (label, false, format!("{e:#}")),
            });
            if failed {
                break;
            }
        }
        Ok(())
    }

    fn take_lock(&mut self) -> Result<()> {
        let lock = self.root.join(LOCK);
        if let Ok(text) = fs::read_to_string(&lock) {
            let pid = text
                .split_whitespace()
                .skip_while(|w| *w != "pid")
                .nth(1)
                .and_then(|p| p.parse::<u32>().ok());
            match pid {
                Some(p) if !Path::new(&format!("/proc/{p}")).exists() => {
                    println!("stale {LOCK} ({}); taking it", text.trim());
                }
                _ => bail!("{LOCK} is held: {}", text.trim()),
            }
        }
        let others = client_pids(&self.game);
        if !others.is_empty() {
            bail!("a GameFiles client is already running (pids {others:?})");
        }
        if pgrep_x("poe-server") {
            bail!("a poe-server is already running; stop it first (the test starts its own)");
        }
        fs::write(
            &lock,
            format!("game-test {} pid {} since {}\n", self.dir.display(), std::process::id(), stamp()),
        )?;
        self.lock_taken = true;
        Ok(())
    }

    /// A private standalone deploy whose DLLs equal the last build; deploys if they differ.
    fn check_deploy(&self, no_build: bool) -> Result<()> {
        let cfg = fs::read_to_string(self.game.join("poe-hook.toml")).unwrap_or_default();
        let key = |k: &str| {
            cfg.lines()
                .find_map(|l| l.trim().strip_prefix(k)?.trim().strip_prefix('=').map(|v| v.trim().trim_matches('"').to_owned()))
        };
        if key("mode").as_deref() == Some("official") {
            bail!("GameFiles is deployed in official mode (a capture may be pending): run `cargo xtask deploy-client` yourself");
        }
        let built = if no_build {
            crate::dll_out_dir(&self.root, true)
        } else {
            crate::build_dll(&self.root, true)?
        };
        let same = ["version.dll", "poe_hook_core.dll"].iter().all(|f| {
            let a = fs::read(built.join(f));
            let b = fs::read(self.game.join(f));
            matches!((a, b), (Ok(a), Ok(b)) if a == b)
        });
        if same && key("mode").as_deref() == Some("private") && key("login_mode").as_deref() == Some("standalone") {
            println!("deploy: current");
            return Ok(());
        }
        println!("deploy: GameFiles differs from the build; cargo xtask deploy-client --no-build");
        let status = Command::new(std::env::current_exe()?)
            .args(["deploy-client", "--no-build", "--login-mode", "standalone"])
            .current_dir(&self.root)
            .stdout(log_file(&self.dir.join("deploy.log"))?)
            .stderr(log_file(&self.dir.join("deploy.log"))?)
            .status()?;
        if !status.success() {
            bail!("deploy-client failed (deploy.log)");
        }
        Ok(())
    }

    /// The dev config (scripts/dev-config.py) with the scenario's overrides, in the run folder.
    fn server_config(&self, sc: &Scenario) -> Result<PathBuf> {
        let out = self.dir.join("server.toml");
        let status = Command::new("python3")
            .arg(self.root.join("scripts/dev-config.py"))
            .arg("--out")
            .arg(&out)
            .stdout(Stdio::null())
            .status()?;
        if !status.success() {
            bail!("scripts/dev-config.py failed");
        }
        if sc.server.is_empty() {
            return Ok(out);
        }
        let mut doc: toml::Table = toml::from_str(&fs::read_to_string(&out)?)?;
        for (path, value) in &sc.server {
            let mut keys: Vec<&str> = path.split('.').collect();
            let last = keys.pop().context("empty server key")?;
            let mut table = &mut doc;
            for k in keys {
                table = table
                    .entry(k)
                    .or_insert_with(|| toml::Value::Table(Default::default()))
                    .as_table_mut()
                    .with_context(|| format!("server override {path}: {k} is not a table"))?;
            }
            table.insert(last.to_owned(), value.clone());
        }
        fs::write(&out, toml::to_string(&doc)?)?;
        Config::load(&out).context("the scenario's server overrides make an invalid config")?;
        Ok(out)
    }

    fn start_server(&mut self, cfg: &Path, no_build: bool) -> Result<PathBuf> {
        let server = self.root.join(crate::server::SERVER_DIR);
        let bin = if no_build {
            crate::server::binary(&server, false)
        } else {
            let mut c = Command::new("cargo");
            c.args(["build", "-p", "poe-server"])
                .current_dir(&server)
                .stdout(log_file(&self.dir.join("build.log"))?)
                .stderr(log_file(&self.dir.join("build.log"))?);
            crate::run(&mut c).context("server build failed (build.log)")?;
            crate::server::binary(&server, false)
        };
        let child = Command::new(&bin)
            .current_dir(&self.root)
            .env(poe_config::ENV_PATH, cfg)
            .env("NO_COLOR", "1")
            .stdout(log_file(&self.dir.join("server.log"))?)
            .stderr(log_file(&self.dir.join("server.log"))?)
            .process_group(0)
            .spawn()
            .with_context(|| bin.display().to_string())?;
        self.server = Some(child);
        self.wait_log("server", "instance server listening", 0, Duration::from_secs(60))
            .context("server did not start (server.log)")?;
        println!("server: up");
        Ok(bin)
    }

    /// Test account (scripts/lib/test-accounts.sh), its character, and a Remember Me token.
    fn sign_in(&self, bin: &Path, cfg: &Path, sc: &Scenario) -> Result<String> {
        let script = r#"
set -e
srv() { POE_CONFIG="$CFG" "$BIN" "$@"; }
. scripts/lib/test-accounts.sh
ta_ensure "$ACCT" admin
srv character list "$ACCT" 2>/dev/null | grep -qP "^$ACCT\t" \
    || srv character create "$ACCT" "${ACCT}Ranger" "$CLASS" "$AREA" >/dev/null
ta_token "$ACCT" "$(ta_web_port "$CFG")"
"#;
        let out = Command::new("bash")
            .args(["-c", script])
            .current_dir(&self.root)
            .env("CFG", cfg)
            .env("BIN", bin)
            .env("ACCT", &sc.account)
            .env("CLASS", &sc.class)
            .env("AREA", &sc.area)
            .stderr(log_file(&self.dir.join("account.log"))?)
            .output()?;
        let token = String::from_utf8_lossy(&out.stdout).trim().to_owned();
        if !out.status.success() || token.len() != 64 {
            bail!("no game token for {} (account.log; is the web API on?)", sc.account);
        }
        Ok(token)
    }

    fn set_input_mode(&mut self, mode: &str) -> Result<()> {
        let path = self.prefix.join(PREFIX_INI);
        let text = fs::read_to_string(&path).with_context(|| path.display().to_string())?;
        let changed: Vec<String> = text
            .lines()
            .map(|l| {
                if l.starts_with("user_input_mode=") || l.starts_with("last_selected_KBM_input_mode=") {
                    format!("{}={mode}", l.split('=').next().unwrap())
                } else {
                    l.to_owned()
                }
            })
            .collect();
        fs::write(&path, changed.join("\r\n") + if text.ends_with('\n') { "\r\n" } else { "" })?;
        self.ini_backup = Some(text);
        Ok(())
    }

    fn launch_client(&mut self, display: Display, sc: &Scenario) -> Result<()> {
        let _ = fs::remove_file(self.game.join("poe-hook.keys"));
        let _ = fs::remove_file(self.game.join("poe-hook.log"));
        self.client_txt_start = fs::metadata(self.game.join("logs/Client.txt")).map(|m| m.len()).unwrap_or(0);
        poe_hook_deploy::launch::quarantine_crash_dumps(&self.prefix, &self.root.join("runtime/crash-dumps"))?;
        let launch = poe_hook_deploy::launch::ProtonLaunch {
            steam_root: poe_hook_deploy::launch::default_steam_root()?,
            proton: "Proton - Experimental".into(),
            prefix_dir: self.prefix.clone(),
            game_dir: self.game.clone(),
            crash_dump_dir: None,
        };
        let inner = launch.command()?;
        let mut cmd = match display {
            Display::Desktop => Command::new(inner.get_program()),
            Display::Gamescope => {
                if !Path::new("/usr/bin/gamescope").exists() && !which("gamescope") {
                    bail!("--display gamescope: gamescope is not installed (PLAN T0)");
                }
                let mut c = Command::new("gamescope");
                let extra = std::env::var("GAME_TEST_GAMESCOPE_ARGS")
                    .unwrap_or_else(|_| "--backend headless -W 2560 -H 1440".into());
                c.args(extra.split_whitespace()).arg("--").arg(inner.get_program());
                c
            }
        };
        cmd.args(inner.get_args());
        if let Some(dir) = inner.get_current_dir() {
            cmd.current_dir(dir);
        }
        for (k, v) in inner.get_envs() {
            match v {
                Some(v) => cmd.env(k, v),
                None => cmd.env_remove(k),
            };
        }
        cmd.env("POE_HOOK_AUTO_KEYS", "20000:13")
            .env("POE_HOOK_FAKE_FOCUS", "1")
            .env("POE_HOOK_MOVEMENT_LOG", "1")
            .env("POE_HOOK_WINDOW_TITLE", "PoE2 Test Client");
        for (k, v) in &sc.client_env {
            let v = match v {
                toml::Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            cmd.env(k, v);
        }
        cmd.stdout(log_file(&self.dir.join("client-run.log"))?)
            .stderr(log_file(&self.dir.join("client-run.log"))?)
            .process_group(0);
        self.client = Some(cmd.spawn().context("launching the client")?);
        println!("client: started");
        Ok(())
    }

    fn step(&mut self, s: &Step) -> Result<String> {
        if let Some(k) = &s.keys {
            self.send_keys(k)?;
            return Ok(format!("sent {}", k.split_whitespace().count()));
        }
        if let Some(c) = &s.cmd {
            self.send_keys(&format!("cmd:{c}"))?;
            return Ok(format!("cmd {c}"));
        }
        if let Some(ms) = s.wait_ms {
            std::thread::sleep(Duration::from_millis(ms));
            return Ok(format!("{ms} ms"));
        }
        let log = s.log.as_deref().unwrap_or("server");
        if let Some(re) = &s.expect_log {
            let from = if s.since.as_deref() == Some("start") { 0 } else { self.log_len(log) };
            let t = Duration::from_secs(s.timeout_s.unwrap_or(30));
            return self.wait_log(log, re, from, t).map(|l| short(&l));
        }
        if let Some(re) = &s.reject_log {
            return match self.find(log, re, 0)? {
                Some(line) => bail!("found: {}", short(&line)),
                None => Ok(format!("no /{re}/")),
            };
        }
        bail!("step with no action")
    }

    /// Writes entries for the DLL once its previous file was consumed; waits until it is read
    /// and for the `wait:` and hold times inside.
    fn send_keys(&mut self, entries: &str) -> Result<()> {
        let file = self.game.join("poe-hook.keys");
        self.wait_until(Duration::from_secs(15), || !file.exists())
            .context("the DLL did not read poe-hook.keys")?;
        let tmp = self.game.join("poe-hook.keys.tmp");
        fs::write(&tmp, format!("{entries}\n"))?;
        fs::rename(&tmp, &file)?;
        self.wait_until(Duration::from_secs(15), || !file.exists())
            .context("the DLL did not read poe-hook.keys")?;
        let busy: u64 = entries
            .split_whitespace()
            .filter_map(|e| {
                if let Some(ms) = e.strip_prefix("wait:") {
                    return ms.parse::<u64>().ok();
                }
                if e.starts_with("text:") || e.starts_with("cmd:") || e.matches(':').count() != 1 {
                    return None;
                }
                e.rsplit_once(':').and_then(|(_, ms)| ms.parse().ok())
            })
            .sum();
        std::thread::sleep(Duration::from_millis(busy + 300));
        Ok(())
    }

    fn wait_until(&mut self, t: Duration, mut f: impl FnMut() -> bool) -> Result<()> {
        let end = Instant::now() + t;
        while !f() {
            self.check_alive()?;
            if Instant::now() > end {
                bail!("timeout");
            }
            std::thread::sleep(Duration::from_millis(200));
        }
        Ok(())
    }

    fn check_alive(&mut self) -> Result<()> {
        if let Some(s) = self.server.as_mut()
            && let Some(st) = s.try_wait()?
        {
            bail!("the server exited ({st})");
        }
        if let Some(c) = self.client.as_mut()
            && let Some(st) = c.try_wait()?
            && client_pids(&self.game).is_empty()
        {
            bail!("the client exited ({st})");
        }
        Ok(())
    }

    fn log_path(&self, log: &str) -> PathBuf {
        match log {
            "hook" => self.game.join("poe-hook.log"),
            "client" => self.game.join("logs/Client.txt"),
            _ => self.dir.join("server.log"),
        }
    }

    fn log_len(&self, log: &str) -> u64 {
        fs::metadata(self.log_path(log)).map(|m| m.len()).unwrap_or(0)
    }

    /// First line matching `re` at or after byte `from` (Client.txt: after the run's start).
    fn find(&self, log: &str, re: &str, from: u64) -> Result<Option<String>> {
        let re = Regex::new(re).with_context(|| format!("bad regex {re}"))?;
        let from = if log == "client" { from.max(self.client_txt_start) } else { from };
        let Ok(bytes) = fs::read(self.log_path(log)) else {
            return Ok(None);
        };
        let start = (from as usize).min(bytes.len());
        let text = String::from_utf8_lossy(&bytes[start..]);
        Ok(text.lines().find(|l| re.is_match(&strip_ansi(l))).map(strip_ansi))
    }

    fn wait_log(&mut self, log: &str, re: &str, from: u64, t: Duration) -> Result<String> {
        let end = Instant::now() + t;
        loop {
            if let Some(line) = self.find(log, re, from)? {
                return Ok(line);
            }
            self.check_alive()?;
            if Instant::now() > end {
                bail!("/{re}/ not in the {log} log after {} s", t.as_secs());
            }
            std::thread::sleep(Duration::from_millis(500));
        }
    }

    /// Closes the client (WM_CLOSE, then signals) and the server (SIGINT, then SIGKILL).
    fn shutdown(&mut self) {
        if self.client.is_some() {
            let file = self.game.join("poe-hook.keys");
            let _ = fs::remove_file(&file);
            let _ = fs::write(&file, "close\n");
            let end = Instant::now() + Duration::from_secs(30);
            while Instant::now() < end && !client_pids(&self.game).is_empty() {
                std::thread::sleep(Duration::from_millis(500));
            }
            for sig in ["-TERM", "-KILL"] {
                let pids = client_pids(&self.game);
                if pids.is_empty() {
                    break;
                }
                for p in &pids {
                    let _ = Command::new("kill").args([sig, &p.to_string()]).status();
                }
                std::thread::sleep(Duration::from_secs(5));
            }
            if let Some(mut c) = self.client.take() {
                let _ = Command::new("kill").args(["-KILL", &format!("-{}", c.id())]).stderr(Stdio::null()).status();
                let _ = c.wait();
            }
            let _ = fs::remove_file(&file);
            println!("client: closed");
        }
        if let Some(mut s) = self.server.take() {
            let _ = Command::new("kill").args(["-INT", &s.id().to_string()]).status();
            let end = Instant::now() + Duration::from_secs(15);
            while Instant::now() < end && matches!(s.try_wait(), Ok(None)) {
                std::thread::sleep(Duration::from_millis(200));
            }
            let _ = s.kill();
            let _ = s.wait();
            println!("server: stopped");
        }
        if let Some(text) = self.ini_backup.take() {
            let _ = fs::write(self.prefix.join(PREFIX_INI), text);
        }
    }

    /// Copies the hook log and the run's part of Client.txt into the run folder.
    fn collect(&self) {
        let _ = fs::copy(self.game.join("poe-hook.log"), self.dir.join("poe-hook.log"));
        if let Ok(bytes) = fs::read(self.game.join("logs/Client.txt")) {
            let start = (self.client_txt_start as usize).min(bytes.len());
            let _ = fs::write(self.dir.join("Client.txt"), &bytes[start..]);
        }
        // The DLL's per-process session folder (packets, snapshots): the newest one.
        let sessions = self.game.join("logs/poe-hook");
        if let Some(newest) = fs::read_dir(&sessions).ok().and_then(|d| {
            d.flatten().max_by_key(|e| e.metadata().and_then(|m| m.modified()).ok())
        }) {
            let _ = fs::write(self.dir.join("hook-session.txt"), format!("{}\n", newest.path().display()));
        }
    }
}

impl Drop for Run {
    fn drop(&mut self) {
        self.shutdown();
        if self.lock_taken {
            let _ = fs::remove_file(self.root.join(LOCK));
        }
    }
}

fn log_file(path: &Path) -> Result<fs::File> {
    let mut f = fs::OpenOptions::new().create(true).append(true).open(path)?;
    f.flush()?;
    Ok(f)
}

fn strip_ansi(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars();
    while let Some(c) = chars.next() {
        if c == '\x1b' {
            for c in chars.by_ref() {
                if c.is_ascii_alphabetic() {
                    break;
                }
            }
        } else {
            out.push(c);
        }
    }
    out
}

fn short(line: &str) -> String {
    let l = line.trim();
    // Drop the timestamp and level of a tracing line.
    let l = l.splitn(3, ' ').nth(2).filter(|_| l.starts_with("20")).unwrap_or(l);
    l.chars().take(140).collect()
}

fn pgrep_x(name: &str) -> bool {
    Command::new("pgrep").args(["-x", name]).stdout(Stdio::null()).status().is_ok_and(|s| s.success())
}

fn which(name: &str) -> bool {
    Command::new("which").arg(name).stdout(Stdio::null()).stderr(Stdio::null()).status().is_ok_and(|s| s.success())
}

fn ensure_steam() -> Result<()> {
    if pgrep_x("steam") {
        return Ok(());
    }
    println!("steam: starting (-silent)");
    Command::new("steam")
        .arg("-silent")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .process_group(0)
        .spawn()
        .context("starting Steam")?;
    let end = Instant::now() + Duration::from_secs(90);
    while !pgrep_x("steam") {
        if Instant::now() > end {
            bail!("Steam did not start");
        }
        std::thread::sleep(Duration::from_secs(1));
    }
    // The client exits with "Unable to init Steam API" while Steam is still starting.
    std::thread::sleep(Duration::from_secs(30));
    Ok(())
}

/// Processes Proton made for the GameFiles client (same rules as scripts/re/terrain_batch.py).
fn client_pids(game: &Path) -> Vec<u32> {
    let me = std::process::id();
    let game = game.canonicalize().unwrap_or_else(|_| game.to_owned());
    let mut pids = Vec::new();
    let Ok(dir) = fs::read_dir("/proc") else {
        return pids;
    };
    for e in dir.flatten() {
        let Some(pid) = e.file_name().to_str().and_then(|s| s.parse::<u32>().ok()) else {
            continue;
        };
        if pid == me {
            continue;
        }
        let Ok(raw) = fs::read(e.path().join("cmdline")) else {
            continue;
        };
        let argv: Vec<String> = raw
            .split(|b| *b == 0)
            .map(|a| String::from_utf8_lossy(a).into_owned())
            .collect();
        let a0 = argv[0].to_lowercase();
        let helper = a0.ends_with("pathofexilesteam.exe")
            && fs::read_link(e.path().join("cwd")).is_ok_and(|c| c == game);
        // Never the Steam install's client: only an exe under GameFiles.
        let wine_exe = a0.starts_with("z:") && a0.contains("gamefiles") && a0.ends_with("pathofexilesteam.exe");
        let steam_exe = a0.ends_with("steam.exe") && argv.get(1).is_some_and(|a| a.contains("GameFiles"));
        let proton = argv.len() > 3
            && a0.contains("python")
            && argv[1].ends_with("/proton")
            && argv[3].contains("GameFiles");
        if helper || wine_exe || steam_exe || proton {
            pids.push(pid);
        }
    }
    pids
}

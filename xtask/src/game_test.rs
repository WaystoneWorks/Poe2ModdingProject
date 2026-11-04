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
//! The display is behind `--display`: `gamescope` (default: headless gamescope, no window on the
//! user's desktop) or `desktop` (the normal desktop).

use std::{
    fs,
    io::Write as _,
    os::unix::process::CommandExt as _,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use std::f64::consts::FRAC_1_SQRT_2;

use anyhow::{Context, Result, bail};
use poe_config::Config;
use regex::Regex;
use serde::Deserialize;

/// Where scenario names are looked up.
const SCENARIO_DIR: &str = "scripts/game-test";
const LOCK: &str = "runtime/client.lock";
/// The DLL's live state file in the game folder (poe-hook-core `state_export.rs`).
const STATE_FILE: &str = "poe-hook-state.json";
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
    #[arg(long, value_enum, default_value = "gamescope")]
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
    /// Shell commands run from the hub root once the server is up and the account signed in,
    /// before the client starts; `srv` runs `poe-server` against the run's config, `$WEB` is the
    /// web API port and `$ACCT` the account. A failing command ends the run (`setup-<n>.txt`).
    #[serde(default)]
    setup: Vec<String>,
    /// Steps at the character select screen, after the login and before Play.
    #[serde(default, rename = "select")]
    select_steps: Vec<Step>,
    /// Press Play after the `select` steps (default). `false`: the `select` steps enter the
    /// world themselves (a character creation plays the new character).
    #[serde(default = "yes")]
    play: bool,
    #[serde(default, rename = "step")]
    steps: Vec<Step>,
    /// Checks run from the hub root after the client and server are closed, one shell command
    /// each, `{session}` replaced by the DLL's session folder (packets, hook log) and `{dir}` by
    /// the run folder (its `server.toml`); a check passes
    /// on exit code 0. Output goes to `after-<n>.txt`, its last line to the summary.
    #[serde(default)]
    after: Vec<String>,
}

fn yes() -> bool {
    true
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
    /// Pass when every check holds at once in the DLL's live state file within `timeout_s`
    /// (default 10): `area`, `near = [x, y, r]`, `panel`, `no_panel`, or a dotted path with a
    /// value or a comparison (`"player.life.current" = ">= 1"`); see `game_state.rs`.
    expect_state: Option<toml::Table>,
    /// `walk_to = [x, y, r]`: steers with W/A/S/D (scenario `input_mode = "wasd"`) until the
    /// player's grid cell is within r cells of (x, y), within `timeout_s` (default 30). With
    /// `blocked = true` it holds the one key combination that points at (x, y) from the start
    /// and passes when the player stops short (a wall), fails when it gets there.
    walk_to: Option<Vec<f64>>,
    blocked: Option<bool>,
    /// `roll = "W"` (keys `W`, `A`, `S`, `D`, up to two, e.g. `"WD"`; `""` rolls standing,
    /// towards the cursor): holds the keys, presses Space as a real hold, releases the keys
    /// after `hold_ms` (default 1000).
    roll: Option<String>,
    hold_ms: Option<u64>,
    /// `max_drift = 5`: fails when a server `drift` line (scenario `"dev.drift_check" = true`)
    /// since the last action step started (keys, cmd, walk_to, roll; `since = "start"`: since
    /// the scenario started) shows
    /// more than this many cells between the server's and the client's position.
    max_drift: Option<f64>,
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
    /// Player cell at the start of the previous and the current step (live state file).
    grids: (Option<(f64, f64)>, Option<(f64, f64)>),
    /// Server log length when the last action step (keys, cmd, walk_to, roll) started
    /// (`max_drift`).
    action_log_at: u64,
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
        grids: (None, None),
        action_log_at: 0,
    };
    println!("game-test {name}: {}", scenario.description);
    println!("logs: {}", dir.display());
    let mut results: Vec<(String, bool, String)> = Vec::new();
    let outcome = run.execute(&args, &scenario, &mut results);
    run.shutdown();
    if let Err(e) = &outcome {
        results.push(("setup".into(), false, format!("{e:#}")));
    }
    let session = run.collect();
    for (n, cmd) in scenario.after.iter().enumerate() {
        let label = format!("after {}", n + 1);
        let Some(session) = &session else {
            results.push((label, false, "no DLL session folder".into()));
            continue;
        };
        let cmd = cmd.replace("{session}", &session.display().to_string()).replace("{dir}", &dir.display().to_string());
        match Command::new("sh").arg("-c").arg(&cmd).current_dir(&run.root).output() {
            Ok(out) => {
                let text = format!("$ {cmd}\n{}{}", String::from_utf8_lossy(&out.stdout), String::from_utf8_lossy(&out.stderr));
                let _ = fs::write(dir.join(format!("after-{}.txt", n + 1)), &text);
                let last = text.lines().rev().find(|l| !l.trim().is_empty()).unwrap_or("").to_string();
                results.push((label, out.status.success(), last));
            }
            Err(e) => results.push((label, false, format!("{cmd}: {e}"))),
        }
    }
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
        self.setup(&bin, &cfg, sc)?;
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
        for (i, step) in sc.select_steps.iter().enumerate() {
            let label = format!("select: {}", step.name.clone().unwrap_or_else(|| format!("step {}", i + 1)));
            match self.step(step) {
                Ok(detail) => results.push((label, true, detail)),
                Err(e) => {
                    results.push((label, false, format!("{e:#}")));
                    return Ok(());
                }
            }
        }
        if sc.play {
            self.send_keys("0x0d")?;
        }
        let entered = self
            .wait_log("server", "player entered the world", 0, Duration::from_secs(120))
            .context("did not enter the world after Play")?;
        results.push(("login".into(), true, short(&entered)));
        // The loading screen can outlast "entered the world" by a minute; steps start once the
        // state file shows the player.
        let state_file = self.game.join(STATE_FILE);
        self.player_cell(0).or_else(|_| {
            self.wait_until(Duration::from_secs(120), || {
                fs::read_to_string(&state_file)
                    .ok()
                    .and_then(|t| crate::game_state::parse(&t).ok())
                    .and_then(|v| crate::game_state::grid(&v))
                    .is_some()
            })
            .context("no player in the state file after entering the world")?;
            self.player_cell(0)
        })?;
        for (i, step) in sc.steps.iter().enumerate() {
            let label = step.name.clone().unwrap_or_else(|| format!("step {}", i + 1));
            let r = self.step(step).map(|d| match (&step.keys, &step.roll, &step.cmd) {
                (None, None, None) => d,
                _ => match SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map_err(anyhow::Error::from)
                    .and_then(|t| self.player_cell(t.as_millis() as u64))
                {
                    Ok((x, y)) => format!("{d}, at ({x},{y})"),
                    Err(_) => d,
                },
            });
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
ta_league
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

    fn setup(&self, bin: &Path, cfg: &Path, sc: &Scenario) -> Result<()> {
        for (n, cmd) in sc.setup.iter().enumerate() {
            let script = format!(
                "set -e\nsrv() {{ POE_CONFIG=\"$CFG\" \"$BIN\" \"$@\"; }}\n. scripts/lib/test-accounts.sh\nWEB=$(ta_web_port \"$CFG\")\n{cmd}\n"
            );
            let out = Command::new("bash")
                .args(["-c", &script])
                .current_dir(&self.root)
                .env("CFG", cfg)
                .env("BIN", bin)
                .env("ACCT", &sc.account)
                .output()?;
            let text = format!("$ {cmd}\n{}{}", String::from_utf8_lossy(&out.stdout), String::from_utf8_lossy(&out.stderr));
            fs::write(self.dir.join(format!("setup-{}.txt", n + 1)), &text)?;
            if !out.status.success() {
                bail!("setup command {} failed: {}", n + 1, text.trim_end());
            }
        }
        Ok(())
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
        let _ = fs::remove_file(self.game.join(STATE_FILE));
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
                    bail!("--display gamescope: gamescope is not installed (`sudo pacman -S gamescope`, or pass --display desktop)");
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
            .env("POE_HOOK_STATE", "250")
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
        // The player's cell at the start of this step and of the previous one (`moved`).
        let now = fs::read_to_string(self.game.join(STATE_FILE))
            .ok()
            .and_then(|t| crate::game_state::parse(&t).ok())
            .and_then(|v| crate::game_state::grid(&v));
        self.grids = (self.grids.1, now);
        if s.keys.is_some() || s.cmd.is_some() || s.walk_to.is_some() || s.roll.is_some() {
            self.action_log_at = self.log_len("server");
        }
        if let Some(max) = s.max_drift {
            // One more sample after the action (`[dev] drift_interval_ms`, 1000 by default).
            std::thread::sleep(Duration::from_millis(1500));
            let from = if s.since.as_deref() == Some("start") { 0 } else { self.action_log_at };
            return self.check_drift(max, from);
        }
        if let Some(k) = &s.keys {
            self.send_keys(k)?;
            return Ok(format!("sent {}", k.split_whitespace().count()));
        }
        if let Some(c) = &s.cmd {
            // The DLL logs `server command "<c>" sent: false` while its debug link is not up
            // yet (just after loading): retry for up to 20 s.
            let sent = Regex::new(&format!(r#"server command {} sent: (\w+)"#, regex::escape(&format!("{c:?}"))))?;
            for _ in 0..20 {
                let from = self.log_len("hook");
                self.send_keys(&format!("cmd:{c}"))?;
                let line = self.wait_log("hook", sent.as_str(), from, Duration::from_secs(5))?;
                if sent.captures(&line).is_some_and(|m| &m[1] == "true") {
                    return Ok(format!("cmd {c}"));
                }
                std::thread::sleep(Duration::from_secs(1));
            }
            bail!("the DLL could not send {c:?} (debug link down)");
        }
        if let Some(ms) = s.wait_ms {
            std::thread::sleep(Duration::from_millis(ms));
            return Ok(format!("{ms} ms"));
        }
        if let Some(w) = &s.walk_to {
            let [x, y, r] = w[..] else { bail!("walk_to: want [x, y, r]") };
            let t = Duration::from_secs(s.timeout_s.unwrap_or(30));
            return self.walk_to((x, y), r, s.blocked.unwrap_or(false), t);
        }
        if let Some(keys) = &s.roll {
            let vks = keys.chars().map(key_vk).collect::<Result<Vec<_>>>()?;
            let down: String = vks.iter().map(|k| format!("indown:{k:#x} ")).collect();
            let up: String = vks.iter().map(|k| format!(" inup:{k:#x}")).collect();
            let hold = s.hold_ms.unwrap_or(1000);
            self.send_keys(&format!("{down}indown:0x20 0x20 wait:250 inup:0x20 wait:{hold}{up}"))?;
            return Ok(format!("rolled {keys:?}"));
        }
        if let Some(checks) = &s.expect_state {
            let t = Duration::from_secs(s.timeout_s.unwrap_or(10));
            return self.wait_state(checks, t);
        }
        let log = s.log.as_deref().unwrap_or("server");
        if let Some(re) = &s.expect_log {
            let from = match s.since.as_deref() {
                Some("start") => 0,
                // A command's reply can land before the next step begins (server log only).
                Some("action") if log == "server" => self.action_log_at,
                _ => self.log_len(log),
            };
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
                // The DLL sleeps 100 ms after each raw input entry.
                let pause = if e.starts_with("in") { 100 } else { 0 };
                if e.starts_with("text:") || e.starts_with("cmd:") || e.matches(':').count() != 1 {
                    return Some(pause);
                }
                Some(pause + e.rsplit_once(':').and_then(|(_, ms)| ms.parse().ok()).unwrap_or(0))
            })
            .sum();
        std::thread::sleep(Duration::from_millis(busy + 300));
        Ok(())
    }

    /// `max_drift`: the largest `cells` of the server's `drift` lines from byte `from` on.
    fn check_drift(&self, max: f64, from: u64) -> Result<String> {
        let re = Regex::new(r#": drift .*\bcells=Some\("([0-9.]+)"\)"#)?;
        let bytes = fs::read(self.log_path("server")).unwrap_or_default();
        let text = String::from_utf8_lossy(&bytes[(from as usize).min(bytes.len())..]);
        let (mut worst, mut n, mut line) = (0.0f64, 0, String::new());
        for l in text.lines().map(strip_ansi) {
            if let Some(d) = re.captures(&l).and_then(|m| m[1].parse::<f64>().ok()) {
                n += 1;
                if d > worst {
                    (worst, line) = (d, l);
                }
            }
        }
        if n == 0 {
            bail!("no drift lines (scenario [server] \"dev.drift_check\" = true?)");
        }
        if worst > max {
            bail!("drift {worst:.2} cells > {max}: {}", short(&line));
        }
        Ok(format!("max {worst:.2} cells over {n} samples"))
    }

    /// The player's cell in a fresh state file, at least `after` (unix ms) new.
    fn player_cell(&mut self, after: u64) -> Result<(f64, f64)> {
        let file = self.game.join(STATE_FILE);
        let end = Instant::now() + Duration::from_secs(5);
        loop {
            let v = fs::read_to_string(&file).ok().and_then(|t| crate::game_state::parse(&t).ok());
            if let Some(v) = v
                && v.get("t").and_then(serde_json::Value::as_u64).unwrap_or(0) >= after
                && let Some(g) = crate::game_state::grid(&v)
            {
                return Ok(g);
            }
            self.check_alive()?;
            if Instant::now() > end {
                bail!("no fresh player cell in the state file");
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    }

    /// `walk_to`: holds the W/A/S/D combination that points closest to the target for a time
    /// sized from the distance and the speed seen so far, reads the new cell, and repeats.
    /// Two holds in a row that move less than a fifth of what they should (and under 2 cells)
    /// count as stopped.
    fn walk_to(&mut self, to: (f64, f64), r: f64, blocked: bool, t: Duration) -> Result<String> {
        let end = Instant::now() + t;
        let start = self.player_cell(0)?;
        let mut pos = start;
        let mut speed = 37.0; // cells per second (WASD walk), refined from long holds
        let fixed = blocked.then(|| best_keys((to.0 - pos.0, to.1 - pos.1)));
        let mut stalls = 0;
        let mut holds = 0;
        let (mut best, mut since_best) = (f64::MAX, 0);
        loop {
            let d = ((to.0 - pos.0).powi(2) + (to.1 - pos.1).powi(2)).sqrt();
            if d < best - 0.5 {
                (best, since_best) = (d, 0);
            } else {
                since_best += 1;
            }
            if !blocked && since_best >= 8 {
                bail!("no closer than {best:.1} cells in 8 holds, at ({},{}) (radius too small?)", pos.0, pos.1);
            }
            if d <= r {
                if blocked {
                    bail!("reached ({},{}) from ({},{}): not blocked", pos.0, pos.1, start.0, start.1);
                }
                return Ok(format!("({},{})->({},{}) in {holds} holds, {d:.1} off", start.0, start.1, pos.0, pos.1));
            }
            if stalls >= 2 {
                if blocked {
                    return Ok(format!("stopped at ({},{}) from ({},{}), {d:.1} short", pos.0, pos.1, start.0, start.1));
                }
                bail!("stuck at ({},{}) {d:.1} cells from ({},{})", pos.0, pos.1, to.0, to.1);
            }
            if Instant::now() > end {
                bail!("timeout at ({},{}), {d:.1} cells from ({},{})", pos.0, pos.1, to.0, to.1);
            }
            let keys = fixed.unwrap_or_else(|| best_keys((to.0 - pos.0, to.1 - pos.1)));
            let (ux, uy) = keys_dir(keys);
            let along = (to.0 - pos.0) * ux + (to.1 - pos.1) * uy;
            let hold = if blocked { 1000 } else { ((along / speed * 1000.0 - KEY_PAUSE_MS) * 0.8).clamp(0.0, 1500.0) as u64 };
            let down: String = keys.chars().map(|c| format!("indown:{:#x} ", key_vk(c).unwrap_or(0))).collect();
            let up: String = keys.chars().map(|c| format!(" inup:{:#x}", key_vk(c).unwrap_or(0))).collect();
            self.send_keys(&format!("{down}wait:{hold}{up}"))?;
            let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis() as u64;
            let new = self.player_cell(now)?;
            let moved = ((new.0 - pos.0).powi(2) + (new.1 - pos.1).powi(2)).sqrt();
            // The keys are down for the hold plus the DLL's pause after each entry.
            let held_s = (hold as f64 + KEY_PAUSE_MS) / 1000.0;
            let expected = speed * held_s;
            if moved < 2.0 && moved < expected / 5.0 {
                stalls += 1;
            } else {
                stalls = 0;
                if hold >= 300 {
                    speed = (speed + moved / held_s) / 2.0;
                }
            }
            holds += 1;
            // One line per hold in walk.tsv of the run folder.
            if let Ok(mut f) = fs::OpenOptions::new().create(true).append(true).open(self.dir.join("walk.tsv")) {
                let _ = writeln!(f, "{}\t{}\t{}\t{}\t{keys}\t{hold}\t{}\t{}\t{moved:.1}\t{speed:.1}", to.0, to.1, pos.0, pos.1, new.0, new.1);
            }
            pos = new;
        }
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

    /// Polls the live state file until `checks` hold; the error names the last mismatch.
    fn wait_state(&mut self, checks: &toml::Table, t: Duration) -> Result<String> {
        let file = self.game.join(STATE_FILE);
        let aliases: toml::Table = match fs::read_to_string(self.root.join(SCENARIO_DIR).join("panels.toml")) {
            Ok(text) => toml::from_str(&text).context("scripts/game-test/panels.toml")?,
            Err(_) => toml::Table::new(),
        };
        let ctx = crate::game_state::Ctx { aliases, before: self.grids.0 };
        let end = Instant::now() + t;
        let mut seen = String::new();
        loop {
            let last = match fs::read_to_string(&file) {
                Err(e) => format!("{}: {e}", file.display()),
                Ok(text) => match crate::game_state::parse({
                    seen.clone_from(&text);
                    &text
                }) {
                    Err(e) => format!("{e:#}"),
                    Ok(v) => match crate::game_state::check(&v, checks, &ctx) {
                        Ok(seen) => {
                            let _ = fs::write(self.dir.join("state-last-check.json"), &text);
                            return Ok(seen);
                        }
                        Err(why) => why,
                    },
                },
            };
            self.check_alive()?;
            if Instant::now() > end {
                let _ = fs::write(self.dir.join("state-last-check.json"), &seen);
                bail!("state after {} s: {last}", t.as_secs());
            }
            std::thread::sleep(Duration::from_millis(250));
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

    /// Copies the hook log and the run's part of Client.txt into the run folder; returns the
    /// DLL's session folder.
    fn collect(&self) -> Option<PathBuf> {
        let _ = fs::copy(self.game.join("poe-hook.log"), self.dir.join("poe-hook.log"));
        let _ = fs::copy(self.game.join(STATE_FILE), self.dir.join("state-final.json"));
        if let Ok(bytes) = fs::read(self.game.join("logs/Client.txt")) {
            let start = (self.client_txt_start as usize).min(bytes.len());
            let _ = fs::write(self.dir.join("Client.txt"), &bytes[start..]);
        }
        // The DLL's per-process session folder (packets, snapshots): the newest one.
        let sessions = self.game.join("logs/poe-hook");
        if let Some(newest) = fs::read_dir(&sessions).ok().and_then(|d| {
            d.flatten()
                .filter(|e| e.file_type().is_ok_and(|t| t.is_dir()))
                .max_by_key(|e| e.metadata().and_then(|m| m.modified()).ok())
        }) {
            let _ = fs::write(self.dir.join("hook-session.txt"), format!("{}\n", newest.path().display()));
            return Some(newest.path());
        }
        None
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

/// The DLL sleeps this long after each raw input entry (`indown:` ...), so keys stay down that
/// much longer than the `wait:` between them.
const KEY_PAUSE_MS: f64 = 100.0;

/// Virtual key of a movement key letter.
fn key_vk(c: char) -> Result<u32> {
    Ok(match c.to_ascii_uppercase() {
        'W' => 0x57,
        'A' => 0x41,
        'S' => 0x53,
        'D' => 0x44,
        _ => bail!("movement key {c:?}: want W, A, S or D"),
    })
}

/// Grid direction each movement key walks (unit vector; `0x63` MoveDirection vectors,
/// docs/protocol/movement.md: W is (127, 127)).
const KEY_DIRS: [(char, (f64, f64)); 4] = [
    ('W', (FRAC_1_SQRT_2, FRAC_1_SQRT_2)),
    ('S', (-FRAC_1_SQRT_2, -FRAC_1_SQRT_2)),
    ('D', (FRAC_1_SQRT_2, -FRAC_1_SQRT_2)),
    ('A', (-FRAC_1_SQRT_2, FRAC_1_SQRT_2)),
];

/// Unit grid direction of a key combination ("W", "WD").
fn keys_dir(keys: &str) -> (f64, f64) {
    let (x, y) = keys.chars().fold((0.0, 0.0), |(x, y), c| {
        let (dx, dy) = KEY_DIRS.iter().find(|(k, _)| *k == c).map(|(_, d)| *d).unwrap_or((0.0, 0.0));
        (x + dx, y + dy)
    });
    let n = (x * x + y * y).sqrt().max(1e-9);
    (x / n, y / n)
}

/// The one- or two-key combination whose direction is closest to `(dx, dy)`.
fn best_keys((dx, dy): (f64, f64)) -> &'static str {
    const COMBOS: [&str; 8] = ["W", "WD", "D", "SD", "S", "AS", "A", "WA"];
    *COMBOS
        .iter()
        .max_by(|a, b| {
            let (ax, ay) = keys_dir(a);
            let (bx, by) = keys_dir(b);
            (ax * dx + ay * dy).total_cmp(&(bx * dx + by * dy))
        })
        .unwrap_or(&"W")
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn key_combinations() {
        assert_eq!(best_keys((1.0, 1.0)), "W");
        assert_eq!(best_keys((1.0, 0.1)), "WD");
        assert_eq!(best_keys((-1.0, -0.9)), "S");
        assert_eq!(best_keys((-1.0, 1.0)), "A");
        let (x, y) = keys_dir("WD");
        assert!((x - 1.0).abs() < 1e-9 && y.abs() < 1e-9);
    }
}

#[cfg(test)]
mod drift_tests {
    #[test]
    fn drift_line() {
        let re = regex::Regex::new(r#": drift .*\bcells=Some\("([0-9.]+)"\)"#).unwrap();
        let l = r#"2026-11-02T16:00:00Z  INFO instance{peer=127.0.0.1:1}: instance_server: drift server=1.00,2.00 client=Some("1.00,2.00") cells=Some("0.42") max_cells=Some("3.10") samples=3 state=walk"#;
        assert_eq!(&re.captures(l).unwrap()[1], "0.42");
    }
}

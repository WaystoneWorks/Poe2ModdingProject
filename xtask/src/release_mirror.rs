//! `cargo xtask release-mirror <dir>`: builds the release files of the server, the client hook
//! (and optionally the launcher) from the local checkouts, the same packages the release
//! workflows make, and writes a **static release source** the launcher and the server read
//! (`kind = "static"` in the launcher's Settings > Advanced > Release source):
//!
//! ```text
//! <dir>/Poe2Server/releases.json  + poe-server-v...tar.gz/.sha256  + hosting.md
//! <dir>/Poe2ClientHook/releases.json + poe-hook-v...zip/.sha256
//! <dir>/Poe2Launcher/releases.json + latest.json + AppImage/.sig     (--launcher)
//! <dir>/Poe2Mods/index.json  <dir>/Poe2ServerList/servers.json  <dir>/Poe2ModdingProject/news.json
//! ```
//!
//! `releases.json` is a list in the shape of GitHub's release API (tag_name, name, body, assets
//! with browser_download_url, size, digest), so the launcher's own parsers read it. Serve the
//! folder with `python3 -m http.server`, or use `file:///<dir>` (everything but the launcher's
//! self-update works from a folder). Spec: docs/guides/launcher.md.

use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result, bail};
use clap::Args;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

use crate::{build_dll, run, server};

const SERVER_REPO: &str = "Poe2Server";
const HOOK_REPO: &str = "Poe2ClientHook";
const LAUNCHER_REPO: &str = "Poe2Launcher";

#[derive(Args)]
pub struct MirrorArgs {
    /// The mirror folder (created; an existing one is updated in place, a release with the same
    /// tag is replaced).
    pub dir: PathBuf,
    /// Address the folder will be served at, written into `browser_download_url`.
    /// Default: `file://` + the absolute folder.
    #[arg(long)]
    pub base_url: Option<String>,
    /// Use the existing builds (server release binary, web admin dist, hook DLLs) as they are.
    #[arg(long)]
    pub no_build: bool,
    /// Leave the server out.
    #[arg(long)]
    pub skip_server: bool,
    /// Leave the client hook out.
    #[arg(long)]
    pub skip_hook: bool,
    /// Also build the server for Windows (cargo-xwin) and package it as a zip.
    #[arg(long)]
    pub windows_server: bool,
    /// Also build the launcher (Linux AppImage) and write `latest.json`. Needs the updater
    /// signing key: `TAURI_SIGNING_PRIVATE_KEY` (the key or its path) and
    /// `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` in the environment.
    #[arg(long)]
    pub launcher: bool,
}

pub fn run_mirror(root: &Path, a: MirrorArgs) -> Result<()> {
    fs::create_dir_all(&a.dir)?;
    let dir = fs::canonicalize(&a.dir)?;
    let base = a
        .base_url
        .clone()
        .unwrap_or_else(|| format!("file://{}", dir.display()))
        .trim_end_matches('/')
        .to_owned();
    println!("mirror folder {}\nserved at     {base}", dir.display());

    if !a.skip_server {
        mirror_server(root, &dir, &base, &a)?;
    }
    if !a.skip_hook {
        mirror_hook(root, &dir, &base, &a)?;
    }
    if a.launcher {
        mirror_launcher(root, &dir, &base, &a)?;
    }
    copy_lists(root, &dir)?;
    println!(
        "\nDone. Launcher: Settings > Advanced > Release source > Static mirror > {base}\n\
         Server/other tools: the same layout; `python3 -m http.server -d {} 8000` serves it \
         (then rerun with --base-url http://127.0.0.1:8000).",
        dir.display()
    );
    Ok(())
}

// --- the products --------------------------------------------------------------------------

fn mirror_server(root: &Path, dir: &Path, base: &str, a: &MirrorArgs) -> Result<()> {
    let srv = root.join(server::SERVER_DIR);
    if !srv.join("Cargo.toml").exists() {
        bail!("{} is empty: git submodule update --init --recursive", srv.display());
    }
    let version = workspace_version(&srv.join("Cargo.toml"))?;
    let schema = root.join("third_party/dat-schema/schema-poe2.min.json");
    if !schema.exists() {
        bail!("{} is missing (third_party/fetch-tools.sh or docs/guides/setup.md)", schema.display());
    }
    let repo_dir = dir.join(SERVER_REPO);
    let staging = tempdir(dir, "server")?;

    if !a.no_build {
        server::build_web_admin(root).context("web admin build")?;
    }
    let dist = root.join(server::WEB_ADMIN_DIR).join("dist");
    let mut assets: Vec<PathBuf> = Vec::new();

    let linux_bin = if a.no_build {
        server::binary(&srv, true)
    } else {
        server::build(&srv, true)?
    };
    package_server(&srv, "linux", &version, &linux_bin, &dist, &schema, &staging)?;
    if a.windows_server {
        let xwin = root.join("third_party/cargo-xwin/bin/cargo-xwin");
        let target = "x86_64-pc-windows-msvc";
        if !a.no_build {
            let mut c = Command::new(&xwin);
            c.args(["xwin", "build", "--release", "-p", "poe-server", "--target", target])
                .current_dir(&srv)
                .env("XWIN_CACHE_DIR", root.join("third_party/xwin-cache"));
            run(&mut c)?;
        }
        let exe = srv.join("target").join(target).join("release/poe-server.exe");
        package_server(&srv, "windows", &version, &exe, &dist, &schema, &staging)?;
    }
    for e in fs::read_dir(&staging)? {
        assets.push(e?.path());
    }
    let guide = srv.join("docs/hosting.md");
    if guide.exists() {
        fs::create_dir_all(&repo_dir)?;
        fs::copy(&guide, repo_dir.join("hosting.md"))?;
    }
    let game = game_version_of(&srv)?;
    add_release(
        &repo_dir,
        base,
        SERVER_REPO,
        &format!("server-v{version}"),
        &format!("Server {version} (game {game})"),
        &commit_note(&srv, "Poe2Server"),
        &assets,
    )?;
    fs::remove_dir_all(&staging).ok();
    Ok(())
}

fn package_server(
    srv: &Path,
    platform: &str,
    version: &str,
    bin: &Path,
    dist: &Path,
    schema: &Path,
    out: &Path,
) -> Result<()> {
    if !bin.exists() {
        bail!("{} not found (build it, or drop --no-build)", bin.display());
    }
    let mut c = Command::new("bash");
    c.arg(srv.join(".github/scripts/package-server.sh"))
        .args([platform, version])
        .arg(bin)
        .arg(dist)
        .arg(schema)
        .arg(out);
    run(&mut c).with_context(|| format!("packaging the {platform} server"))
}

fn mirror_hook(root: &Path, dir: &Path, base: &str, a: &MirrorArgs) -> Result<()> {
    let hook = root.join("modules/client-hook");
    if !hook.join("Cargo.toml").exists() {
        bail!("{} is empty: git submodule update --init --recursive", hook.display());
    }
    let version = workspace_version(&hook.join("Cargo.toml"))?;
    let dlls = if a.no_build {
        hook.join("target/x86_64-pc-windows-msvc/release")
    } else {
        build_dll(root, true)?
    };
    let repo_dir = dir.join(HOOK_REPO);
    let staging = tempdir(dir, "hook")?;
    let mut c = Command::new("python3");
    c.arg(hook.join(".github/scripts/package-hook.py"))
        .arg(&version)
        .arg(&dlls)
        .arg(&staging);
    run(&mut c).context("packaging the client hook")?;
    let assets: Vec<PathBuf> = fs::read_dir(&staging)?.map(|e| e.map(|e| e.path())).collect::<Result<_, _>>()?;
    add_release(
        &repo_dir,
        base,
        HOOK_REPO,
        &format!("hook-v{version}"),
        &format!("Client hook {version}"),
        &commit_note(&hook, "Poe2ClientHook"),
        &assets,
    )?;
    fs::remove_dir_all(&staging).ok();
    Ok(())
}

fn mirror_launcher(root: &Path, dir: &Path, base: &str, a: &MirrorArgs) -> Result<()> {
    let l = root.join("modules/launcher");
    if std::env::var_os("TAURI_SIGNING_PRIVATE_KEY").is_none() {
        bail!("--launcher needs TAURI_SIGNING_PRIVATE_KEY (and _PASSWORD) in the environment to sign the update");
    }
    let conf: Value = serde_json::from_str(&fs::read_to_string(l.join("src-tauri/tauri.conf.json"))?)?;
    let version = conf["version"].as_str().context("tauri.conf.json has no version")?.to_owned();
    if !a.no_build {
        let mut c = Command::new("npm");
        c.args(["run", "tauri", "--", "build", "--bundles", "appimage"]).current_dir(&l);
        run(&mut c).context("launcher build (npm run tauri build)")?;
    }
    let bundle = l.join("src-tauri/target/release/bundle/appimage");
    let image = fs::read_dir(&bundle)
        .with_context(|| format!("{} (no AppImage built)", bundle.display()))?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .find(|p| p.extension().is_some_and(|x| x == "AppImage"))
        .context("no .AppImage in the bundle folder")?;
    let sig_path = PathBuf::from(format!("{}.sig", image.display()));
    let signature = fs::read_to_string(&sig_path)
        .with_context(|| format!("{} (is createUpdaterArtifacts on and the key set?)", sig_path.display()))?;
    let repo_dir = dir.join(LAUNCHER_REPO);
    fs::create_dir_all(&repo_dir)?;
    let name = format!("Poe2Launcher_{version}_amd64.AppImage");
    fs::copy(&image, repo_dir.join(&name))?;
    // latest.json: keep the platforms of an earlier run (a Windows entry made elsewhere).
    let latest_path = repo_dir.join("latest.json");
    let mut latest: Value = fs::read_to_string(&latest_path)
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_else(|| json!({"platforms": {}}));
    if latest["version"].as_str() != Some(&version) {
        latest["platforms"] = json!({});
    }
    latest["version"] = json!(version);
    latest["notes"] = json!(commit_note(&l, "Poe2Launcher"));
    latest["pub_date"] = json!(rfc3339_now());
    latest["platforms"]["linux-x86_64"] = json!({
        "signature": signature.trim(),
        "url": format!("{base}/{LAUNCHER_REPO}/{name}"),
    });
    fs::write(&latest_path, serde_json::to_string_pretty(&latest)? + "\n")?;
    add_release(
        &repo_dir,
        base,
        LAUNCHER_REPO,
        &format!("v{version}"),
        &format!("Launcher {version}"),
        &commit_note(&l, "Poe2Launcher"),
        &[repo_dir.join(&name), sig_path],
    )?;
    Ok(())
}

/// The hub's lists, so a mirror is a complete release source.
fn copy_lists(root: &Path, dir: &Path) -> Result<()> {
    for (from, repo, file) in [
        ("modules/mod-index/index.json", "Poe2Mods", "index.json"),
        ("modules/server-list/servers.json", "Poe2ServerList", "servers.json"),
        ("news.json", "Poe2ModdingProject", "news.json"),
    ] {
        let src = root.join(from);
        if src.exists() {
            fs::create_dir_all(dir.join(repo))?;
            fs::copy(&src, dir.join(repo).join(file))?;
            println!("copied {from} -> {repo}/{file}");
        } else {
            println!("skipped {from} (not there)");
        }
    }
    Ok(())
}

// --- release list --------------------------------------------------------------------------

/// Copies `assets` into `repo_dir` (when they are elsewhere), then adds (or replaces) the
/// release `tag` in `<repo_dir>/releases.json`, newest first.
fn add_release(
    repo_dir: &Path,
    base: &str,
    repo: &str,
    tag: &str,
    title: &str,
    body: &str,
    assets: &[PathBuf],
) -> Result<()> {
    fs::create_dir_all(repo_dir)?;
    let mut listed = Vec::new();
    for src in assets {
        let name = src.file_name().context("asset without a name")?.to_string_lossy().into_owned();
        let dest = repo_dir.join(&name);
        if fs::canonicalize(src).ok() != fs::canonicalize(&dest).ok() {
            fs::copy(src, &dest).with_context(|| format!("copying {}", src.display()))?;
        }
        let bytes = fs::read(&dest)?;
        let sha = hex::encode(Sha256::digest(&bytes));
        listed.push(json!({
            "name": name,
            "size": bytes.len(),
            "digest": format!("sha256:{sha}"),
            "browser_download_url": format!("{base}/{repo}/{name}"),
        }));
    }
    let path = repo_dir.join("releases.json");
    let mut all: Vec<Value> = fs::read_to_string(&path)
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_default();
    all.retain(|r| r["tag_name"].as_str() != Some(tag));
    all.push(json!({
        "tag_name": tag,
        "name": title,
        "body": body,
        "draft": false,
        "prerelease": tag.contains('-'),
        "published_at": rfc3339_now(),
        "html_url": format!("{base}/{repo}"),
        "assets": listed,
    }));
    all.sort_by(|a, b| b["published_at"].as_str().cmp(&a["published_at"].as_str()));
    fs::write(&path, serde_json::to_string_pretty(&all)? + "\n")?;
    println!("{repo}: {tag} ({} files) -> {}", assets.len(), path.display());
    Ok(())
}

// --- helpers -------------------------------------------------------------------------------

fn tempdir(dir: &Path, what: &str) -> Result<PathBuf> {
    let p = dir.join(format!(".staging-{what}"));
    if p.exists() {
        fs::remove_dir_all(&p)?;
    }
    fs::create_dir_all(&p)?;
    Ok(p)
}

/// `[workspace.package] version` of a Cargo.toml.
fn workspace_version(cargo_toml: &Path) -> Result<String> {
    let text = fs::read_to_string(cargo_toml)?;
    let doc: toml::Value = toml::from_str(&text).with_context(|| format!("parsing {}", cargo_toml.display()))?;
    doc.get("workspace")
        .and_then(|w| w.get("package"))
        .and_then(|p| p.get("version"))
        .and_then(|v| v.as_str())
        .map(str::to_owned)
        .with_context(|| format!("no [workspace.package] version in {}", cargo_toml.display()))
}

/// `[game] version` of the server's example config (what the package script reads too).
fn game_version_of(srv: &Path) -> Result<String> {
    let text = fs::read_to_string(srv.join("config/server.example.toml"))?;
    let doc: toml::Value = toml::from_str(&text)?;
    doc.get("game")
        .and_then(|g| g.get("version"))
        .and_then(|v| v.as_str())
        .map(str::to_owned)
        .context("no [game] version in config/server.example.toml")
}

fn commit_note(repo: &Path, name: &str) -> String {
    let out = Command::new("git").args(["rev-parse", "--short", "HEAD"]).current_dir(repo).output();
    let commit = out
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned())
        .unwrap_or_else(|| "unknown".into());
    format!("Local build of {name} at commit {commit} (cargo xtask release-mirror).")
}

/// `2026-11-04T12:00:00Z` for now (UTC), without a date crate.
fn rfc3339_now() -> String {
    let secs = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0) as i64;
    let (days, rem) = (secs.div_euclid(86_400), secs.rem_euclid(86_400));
    // Civil date from days since 1970-01-01 (Howard Hinnant's algorithm).
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z",
        rem / 3600,
        rem % 3600 / 60,
        rem % 60
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_release_list_replaces_a_tag_and_lists_files() {
        let tmp = std::env::temp_dir().join(format!("mirror-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&tmp);
        fs::create_dir_all(&tmp).unwrap();
        let file = tmp.join("a.zip");
        fs::write(&file, b"abc").unwrap();
        let repo = tmp.join("Repo");
        for _ in 0..2 {
            add_release(&repo, "http://h", "Repo", "v1.0.0", "One", "b", std::slice::from_ref(&file)).unwrap();
        }
        let list: Vec<Value> = serde_json::from_str(&fs::read_to_string(repo.join("releases.json")).unwrap()).unwrap();
        assert_eq!(list.len(), 1);
        let a = &list[0]["assets"][0];
        assert_eq!(a["browser_download_url"], "http://h/Repo/a.zip");
        assert_eq!(a["size"], 3);
        assert_eq!(
            a["digest"],
            "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        fs::remove_dir_all(&tmp).unwrap();
    }

    #[test]
    fn the_time_stamp_is_rfc3339() {
        let t = rfc3339_now();
        assert_eq!(t.len(), 20);
        assert!(t.starts_with("20") && t.ends_with('Z'));
    }
}

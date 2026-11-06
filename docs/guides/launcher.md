# Launcher

The player launcher: a small desktop program (Tauri 2 with a Svelte 5 UI) that does what `cargo xtask deploy-client` and `run-client` do for the developer ([setup.md](setup.md)), without this repository. Repo [Poe2Launcher](https://github.com/WaystoneWorks/Poe2Launcher) (public), submodule `modules/launcher`. Its README covers development; this page covers using it and how it fits the server.

The launcher has **no login of its own and creates no accounts**: accounts belong to each server, and players sign in on the game's login screen. It supports several servers, including several hosted on the same computer.

The window is a sidebar (brand, **game version** picker, five pages) and the page.
- **Game version picker:** the private-server versions this launcher supports and *Official (read-only)*, each *installed* / *not installed*. It drives the install folder and depots, verification, hook deploy, Play, the server-release filter of *Create a server* and server compatibility ([below](#game-versions-and-the-official-mode)).
- **Play** (`#/home`): the selected server, the **Play** button with one line of state, the *Get ready to play* checklist while something is missing, and the newest news item ([below](#play-and-news)).
- **News:** one feed, newest first, filter chips; the selected server's message of the day is pinned on top.
- **Servers:** *My servers* (rows with **Start** for hosted ones, *Check*, **Web admin**, details with the server's **active leagues and banners**, **Create account** when registration is open, *Edit*/*Manage*, *Remove*; a hosted server is **deleted**), *Browse public* ([below](#server-browser); **Show leagues** on an online server), *Host* ([below](#host-a-server)).
- **Library:** *Game* (status, **Verify files**, **Client hook** card, *Download or repair from Steam* with your own Steam login, pause/resume, speed, disk-space check), *Mods* ([below](#mods)), *Logs* ([below](#logs-and-crash-dumps)).
- **Settings:** every change saves on its own: *General*, *Game & Proton* (per-version install folder, Steam root, Proton), *Steam* (remember login, Guard code, **Log out of Steam**), *Mods* (**Mod sync**, cache), *Updates & About*, *Advanced* (hook DLL folder, desktop entry on a Linux AppImage).
- **Play** deploys the hook ([../architecture/client-dll.md](../architecture/client-dll.md)) pointed at the selected server and starts the game (Proton on Linux, native on Windows) at its own login screen.

## Download, install and update

Releases are on the [GitHub releases page of Poe2Launcher](https://github.com/WaystoneWorks/Poe2Launcher/releases): Linux AppImage, Windows installer, their `.sig` files and `latest.json`.

- **Linux:** download `Poe2.Launcher_<version>_amd64.AppImage`, `chmod +x` it and run it. Keep it where it is: the launcher updates this file in place. (AppImages need FUSE 2, or start it with `--appimage-extract-and-run`.)
- **Windows:** run `Poe2.Launcher_<version>_x64-setup.exe` (per-user NSIS installer, no administrator rights). SmartScreen may warn because the installer is not code-signed (the update signature below is not a Windows code-signing certificate).
- **Updates:** the launcher checks for a newer release at start and on Settings, *Updates*, *Check for updates*. A badge "Update <version> available" appears in the top bar and Settings shows the release notes. *Download and install* downloads the AppImage or installer, verifies its signature against the public key built into the launcher (`plugins.updater.pubkey` in `tauri.conf.json`), installs it (Windows: passive-mode installer) and restarts. A failed check shows "No update info available" quietly; a failed download or signature check shows the error and changes nothing. Updating works only from an installed AppImage or NSIS install, not from a `tauri dev` or plain `cargo build` binary.
- The endpoint comes from the [release source](#release-source) (`https://github.com/<owner>/Poe2Launcher/releases/latest/download/latest.json` for GitHub; `releases/latest` ignores drafts and pre-releases, tags with a `-`). The check and the install are backend commands (`src-tauri/src/updater.rs`: `update_check`, `update_install`), because the JS plugin cannot set endpoints; `tauri.conf.json` keeps the public key and a placeholder endpoint. Release builds refuse a non-https endpoint; a `file://` mirror cannot update the launcher.

## Release source

One setting decides where the launcher reads releases and lists: **Settings > Advanced > Release source** (`release_source` in `settings.json`, code `src-tauri/src/source.rs`, "Reset to default" in the page):

| `kind` | Reads |
|---|---|
| `github` (default, `owner` + `api`) | `{api}/repos/{owner}/{repo}/releases`, `raw.githubusercontent.com/{owner}/Poe2Mods/main/index.json` (and `Poe2ServerList/.../servers.json`, `Poe2ModdingProject/.../news.json`), `github.com/{owner}/Poe2Launcher/releases/latest/download/latest.json`, the hosting guide link |
| `static` (`base` = `https://...`, `http://...` or `file:///dir`) | `{base}/{repo}/releases.json` (a list in GitHub's release JSON shape: `tag_name`, `body`, `draft`, `prerelease`, `assets[]` with `name`, `size`, `browser_download_url`), `{base}/Poe2Mods/index.json`, `{base}/Poe2ServerList/servers.json`, `{base}/Poe2ModdingProject/news.json`, `{base}/Poe2Launcher/latest.json`, `{base}/Poe2Server/hosting.md`; asset URLs may be `file://` too |

Server releases (`Poe2Server`, fallback `Poe2ModdingProject`), hook releases (`Poe2ClientHook`), news, the mod index and the server list all go through it, so the final GitHub owner is one setting (compiled-in default: `default_owner!` in `source.rs`, rewritten with the links by `scripts/set-owner.sh`) and local testing needs no GitHub. **`cargo xtask release-mirror <dir>`** builds the server (Linux; `--windows-server` adds the Windows zip), the client hook (`build-dll`) and the hub's `index.json`, `servers.json`, `news.json` into such a folder (`--base-url http://127.0.0.1:8000` when served with `python3 -m http.server -d <dir> 8000`, default `file://<dir>`; `--no-build` reuses builds; `--launcher` builds the AppImage and writes a signed `latest.json`, needs `TAURI_SIGNING_PRIVATE_KEY` and its password). A tag already in `releases.json` is replaced. The Poe2Server itself reads no releases, so it has no release-source setting. Test: `POE2_TEST_MIRROR=<dir> cargo test --test mirror_flow -- --ignored` (installs hook and server from a real mirror, over `file://` and, with `POE2_TEST_MIRROR_URL`, http); the updater's signed install from a mirror needs the signing key and is not tested.

## Building and running

Commands (`npm ci`, `npm run tauri dev`): [setup.md](setup.md#launcher-build-and-test).

Linux needs the WebKitGTK stack (Arch: `webkit2gtk-4.1 gtk3 libsoup3 librsvg`; Debian: `libwebkit2gtk-4.1-dev libgtk-3-dev libsoup-3.0-dev libdbus-1-dev librsvg2-dev`), Node 22 and Rust. The result is `src-tauri/target/{debug,release}/poe2-launcher` plus deb, rpm and AppImage bundles. CI (`.github/workflows/ci.yml`): Ubuntu runs `npm run check/test/build`, `cargo fmt --check`, `clippy -D warnings` and `cargo test`; Windows runs `cargo check`. The submodules are public and fetched by `actions/checkout`. Releases: [Releasing](#releasing).

## One-time set-up

1. **Hook DLLs.** Nothing to set: the launcher downloads the **client hook** itself ([below](#client-hook)). A developer can set Settings, *Hook DLL directory* to a folder holding `poe_hook.dll` and `poe_hook_core.dll`, normally `modules/client-hook/target/x86_64-pc-windows-msvc/release` (`build-dll`, [setup.md](setup.md#build-and-test)); it wins over the download.
2. **Linux:** Steam must be running when you press Play, and the Proton set in Settings (default `Proton - Experimental`) must exist under `<Steam>/steamapps/common`. The launcher only reads Proton from there.
3. **Server:** one with the web API on (`[web] enabled`, reachable from the player; TLS outside a trusted network) and an account (`open_registration = true`, or `account create`).

## The flow

A fresh launcher shows a **Get ready to play** checklist at the top of the Play page (gone once all steps are done; official mode has two steps, no server): **1. Install the game** (Library), **2. Get the client hook** (a *Download* button right there), **3. Pick a server** (one *Set up a server* button; its chooser offers *Host on this computer*, *Browse public servers* and *Add by address*). The Play button says what is still missing and links to where to fix it.

1. **Servers:** *Add a server*, e.g. `127.0.0.1:8080` (`http://` is added, a pasted `/api/v1` dropped), or *Add to my servers* in Browse. *Check* shows realm, ping, client version, players, whether registration is open and the game address.
2. **Play.** Pick the server and press Play: the game starts at its own login screen, already pointed at that server, and you sign in there with an account of that server (its *Remember Me* keeps you signed in). New accounts are made on the server's register page (its web admin's `#/register`, when registration is open): *Create account* in the server's row opens it, and so does the game's own *Create account* button (the launcher writes the page into the hook config at Play).
3. **Library, Game:** your Steam account name and password, optionally *Remember the Steam login*. A Steam Guard code is typed into the launcher when Steam asks. The download is about 150 GB.

## Play and news

**Play** is the first page (official mode has it too): the selected server (name, status light, players, **ping** = the time of the launcher's own `GET /api/v1/server` request; checked on open, on pick, every 30 s and on *Check*; an unconfirmed plain `http://` server is not contacted); the **Play** button with one line under it (*Ready to play*, *Game running*, or what blocks Play with a link to the fix, and *Switch to <version>* when the server wants another client); the checklist ([The flow](#the-flow)); a *Server update available* notice for hosted servers ([below](#updating-the-server)); and the newest news item.

**News** is cached (`<data>/poe2-launcher/cache/news.json`, fresh 30 minutes, manual refresh at most once a minute) from sources read without login: the release notes of the newest stable releases (3 each) of `WaystoneWorks/Poe2Launcher` (`v*`), `WaystoneWorks/Poe2Server` (`server-v*` only) and `WaystoneWorks/Poe2ClientHook` (`hook-v*`); and `news.json` in the hub root (`https://raw.githubusercontent.com/WaystoneWorks/Poe2ModdingProject/main/news.json`), schema `{"version": 1, "items": [{"id", "date": "YYYY-MM-DD", "title" (required, 120), "body" (optional markdown, 4000), "link" (optional, https only)}]}`; `id` is unique (`a-z A-Z 0-9 . _ -`, up to 64); a broken item is skipped, the file is limited to 256 KB; to post news add an item at the top and push to `main`. Offline or rate-limited is quiet: the saved copy shows. The selected server's `motd` (`GET /api/v1/server`, [../architecture/web-api.md](../architecture/web-api.md#message-of-the-day); at most 2000 characters) is pinned first. Bodies and the motd are a markdown subset rendered as plain text nodes (no HTML runs; only `https://` links, opened in the system browser).

## Server browser

*Servers, Browse* shows the **public list of servers**, kept in `WaystoneWorks/Poe2ServerList` (initial content, README and validator: [../server-list-template/](../server-list-template/README.md)). The launcher reads `https://raw.githubusercontent.com/WaystoneWorks/Poe2ServerList/main/servers.json`.

- **The file** (`{"schema": 1, "servers": [...]}`): each entry has `id`, `name`, `address` (the web API address), `game_version` and optionally `description`, `region`, `tags`, `contact` and `mods` (required client mods: `id`, optional `version` and `url`); full table in the template's README and `servers.schema.json`. The launcher re-checks every entry: a broken one is skipped and counted ("1 list entry was ignored"), an address that is this computer or a local network is refused, a newer `schema` number is reported, the file is limited to 1 MB and 500 entries. The list is cached (`<data>/poe2-launcher/cache/serverlist.json`, fresh for 10 minutes; *Refresh* asks again); an unreachable list shows the saved copy with a note.
- **Add to my servers** creates a normal profile and checks it. A plain `http://` listing is marked *plain http* ([below](#plain-http-warning)); servers already in your list show *in your servers*. Required mods in the list are shown on the card; mod sync works from what the server advertises ([Mods](#mods)).

## Client hook

The hook is the pair of DLLs (`poe_hook.dll`, installed as the game's `version.dll`, and `poe_hook_core.dll`) that connect the game to a private server and, read-only, observe the official one. The **Client hook** card in Library (Game tab), and step 2 of the checklist, gets it from the releases of [Poe2ClientHook](https://github.com/WaystoneWorks/Poe2ClientHook) (tag `hook-v<version>`, made by that repository's CI: [releasing-hook.md](releasing-hook.md)):

- **Which release.** The newest stable release (a pre-release only when nothing stable fits) whose package supports the selected game version (*Official (read-only)* uses the newest private version's hook; the same DLLs run in official mode). Package name: `poe-hook-v<version>-game-<game versions>-windows-x86_64.zip`.
- **Checks.** The zip against the release's `.sha256` (and size), safe unpacking (no paths outside the folder, no links, bounded size), `release.json` (schema, `windows`/`x86_64`, both DLLs listed, only safe paths), then **every file against the size and SHA-256 in `release.json`, with no unlisted file allowed**, and the game version against the selected one. A failure deletes everything; nothing is installed. The same files are hashed again right before each Play (a changed DLL stops Play with "download it again").
- **Where.** `<data>/hook/packages/<hook version>/`; Play deploys from there. A newer release replaces the older one of the same game versions; a hook kept for another game version stays. Downloads go to `<data>/hook/downloads/` and are removed.
- **The card** shows the installed version, the game versions it serves, the mod ABI, whether an update is available (looked up at start and on *Check for updates*) and a *Download client hook* / *Update* button with speed and time left. Offline or rate-limited GitHub is a card message, never a stop for an installed hook.

Without a hook Play is blocked with "Get the client hook first (Library)".

## Game versions and the official mode

The version picker lists every target the launcher can work with, from the embedded `modules/protocol/versions/<version>.toml` files (copies of Poe2Protocol's, [new-game-version.md](new-game-version.md#the-launcher-and-the-version-dropdown)), so a second supported build appears as a second entry without UI change. The choice is saved in the launcher's `settings.json` (`game_version`; empty or an unknown version means the newest). It cannot change while the game is downloading, starting or running, or while the hosted server runs.

| Part | Private version `<v>` | Official (read-only) |
|---|---|---|
| Install folder | `<data>/game/<v>` or the folder set for that version in Settings | `<data>/game/official`, separate from every private version |
| Download | the depots with the pinned manifests of `modules/protocol/versions/<v>.toml` | the same depots **without manifests**: the current official build |
| Verify | file counts, key file sizes and the exe checksum of that version file | the main files exist and the size floors (the build is not pinned) |
| Play | the selected server profile, `mode = "private"` | no server, `mode = "official"` ([below](#official-read-only)) |
| Servers, Host a server, Mods | available; a server reporting another client version is marked *incompatible* | hidden |
| Host a server | downloads the `poe-server` package whose name carries this game version | not possible |
| Client hook | the newest hook release whose package supports `<v>` | the newest private version's hook, run in official mode |

**Server compatibility.** *Check* (and a quiet check at start) reads `GET /server`. A server whose client version equals the selection is *compatible*. One reporting another version this launcher supports shows *needs client X* with a one-click *Switch to X*, and Play is blocked for it. One reporting an unknown version is marked *incompatible* with a warning; Play is not blocked (the check can be wrong).

### Official (read-only)

For observing a session on the official servers, exactly what `cargo xtask deploy-client --official` does ([official-mode.md](official-mode.md); read its risk section first). Selecting it and pressing Play:

1. asks once for the warning to be accepted (the risk text and an "I understand" box; saved as `official_ack`; the backend refuses to start without it);
2. deploys the hook with `mode = "official"`, `login_mode = "steam"`, an **empty** `trusted_servers`, the original `gateway_list.txt` restored from `gateway_list.txt.orig`, no position sync port and no output folder. The launcher never writes a trusted server or a private gateway for this mode and never touches the read-only latch;
3. starts the game without the standalone-login argument, with its own Steam login (Linux: through Proton in a **separate** prefix `<data>/proton-prefix-official`; Steam must be running). The launcher sends nothing to any server and logs in nowhere.

If the game was updated and the hook's signature table does not match, the hook switches its features off (`NOT verified` in the log); the game runs without the observer. Unit tests cover the deploy files (official versus private) with a temporary game folder; it has not been played against the official servers from the launcher.

The Steam download for the official build is the Library (Game) page; *Download again* updates to whatever Steam serves, *Repair* re-checks files.

### Install in detail

The version file is `modules/protocol/versions/<version>.toml` of Poe2Protocol (the launcher embeds a byte-identical copy kept by `cargo xtask versions`). For 0.5.5f: app 2694490, depot 2694491 manifest 4712263798014036045 (content), depot 2694492 manifest 4973272861086296374 (Windows exe), in that order into one directory (exe over content).

- **DepotDownloader 3.4.0**, the self-contained release (no .NET), is fetched from its GitHub release into the launcher's data directory, pinned by version and SHA-256 (`versions/depotdownloader.toml`); a mismatch deletes the download.
- It runs **once for both depots** (`-app 2694490 -depot 2694491 -manifest ... -depot 2694492 -manifest ... -username U -dir DIR`), so the Steam login and Guard code are asked once. `-no-mobile` is added by default so a typed code is requested instead of the mobile-app confirmation (Settings). `-remember-password` is added only if you tick the box (DepotDownloader then keeps its own login token; the launcher never stores the password).
- **The Steam password** is typed in the launcher, written once to the downloader's standard input when it asks, then wiped from memory. Not on a command line, not logged, not saved. Steam Guard prompts are detected in the output (they have no line end) and shown as a code box.
- **Never the Steam install.** The launcher does not read or write `~/.local/share/Steam/steamapps/common/Path of Exile 2` or `compatdata/2694490`; an install directory inside any Steam library is refused. The default is `<data>/poe2-launcher/game/<version>` (`~/.local/share/poe2-launcher/...`).
- **Pause and resume.** *Pause* kills DepotDownloader (written files stay); *Resume* reruns the same command with `-validate`, fetching what is missing, then verifies. The password is never kept (Resume asks again unless the Steam login is remembered). Pause survives leaving the page, not closing the launcher.
- **Disk space.** Before every install or repair the launcher compares the install disk's free space with what is missing (the version file's `[verify] min_bytes` plus 16 %, about 174 GB for 0.5.5f); not enough disables the buttons and says how much to free.
- **Verification** afterwards (and on *Verify files*): file count and total size floors, key files with exact sizes, SHA-256 of `PathOfExileSteam.exe`. **The reference values were measured on the `GameFiles/` copy in this repository, not on a launcher download**, so the executable checksum is a warning (not a failure) until `exe_sha256_enforce = true` is set after a real install matched. *Repair* re-runs the download with `-validate`.

## Host a server

Servers > **Host** runs private servers on the machine you play on, **several at once**: each has an id (`s1`, `s2`, ...), its own folder `<data>/poe2-launcher/servers/<id>/` (database `data/server.sqlite`, its config `server.toml`, `mods/`, `config-backups/`, `backups/`, `server.log`) and its own settings `<config>/poe2-launcher/servers/<id>.json` (+ `<id>.backup.json`; no secrets). Downloaded server programs live in `<data>/poe2-launcher/server/packages/` and are **shared**: a release another server already has is used without a download, and a package is deleted only when no server uses it. **Create a server** asks for a name and gives the new server the next free ports: the defaults 20481 / 6112 / 8080 moved by 10 per server (20491 / 6122 / 8090, ...), skipping ports another server or program uses; two servers with the same ports are refused at *Apply* and at *Start*. Hosting works on Linux and Windows; the package comes from the server release CI ([releasing-server.md](../../modules/server/docs/releasing.md)).

**Manage** opens a server's panel with four tabs (a new server opens on *Program*, then *Settings*):

1. **Overview.** **Start** / **Stop**, **Open web admin**, **Usage** while it runs (CPU and memory with small charts, from `/proc` on Linux; tick time, network and uptime from the server's `GET /api/v1/local/metrics`, which answers only a direct request from the same computer, [../architecture/web-api.md](../architecture/web-api.md)), and the live **server log** (also `server.log`, replaced at each start).
2. **Settings.** Folding sections: *General* (name, **Start with the launcher**), *Network* (**public host** with *Use my LAN address* and *Look up my public IP* (asks `api.ipify.org` only on the click); the three ports: login TCP, game TCP and UDP, web TCP), *Access* (**open registration**; whether the **web API is reachable from other computers**: binds `0.0.0.0`, plain http, [hosting.md](../../modules/server/docs/hosting.md#tls-reverse-proxy-for-the-web-api)), *Advanced* (**cluster id**, the folder) and *Danger zone*. *Apply* needs the server stopped and writes `server.toml` from the package's `config/server.example.toml` (only these keys change: `game_dir`, `[network]` and binds, `[cluster] id`, `[gateway] display_name`, `[web]` enabled, bind, `static_dir = "web-admin"` and `config_backup_dir`, `[accounts] open_registration`, `[database] path`, `[mods] dir`, `[server] restart_mode = "exit"`; comments, other keys and your own edits stay). **No account is made**: a new server's **first admin is created in its web admin** (first-run page, only from this computer while it has no account; [../architecture/web-api.md](../architecture/web-api.md)).
3. **Program.** *Download the latest release* takes the newest stable `server-v*` release of `WaystoneWorks/Poe2Server` whose package is named `poe-server-v<ver>-game-<your game version>-<linux|windows>-x86_64.tar.gz` (Linux) or `.zip` (Windows), falling back to `WaystoneWorks/Poe2ModdingProject` (the two earliest releases); the `.sha256` must match or nothing is installed. *Use a package file/folder...* takes one you have. `release.json` must name your OS and game version and the needed files must be there (`poe-server`, `config/server.example.toml`, `third_party/dat-schema/schema-poe2.min.json`, the version file). Unpacking checks paths, links and sizes; a package in use by another server is never replaced.
4. **Backups.** *Back up now* copies the database to `backups/server-<UTC date>-<time>-<kind>.sqlite` with SQLite's online backup API (consistent while running; `PRAGMA quick_check`). Kinds: *manual*, *before start*, *before restore*, *before update*. **Restore** needs the server stopped, checks the backup (`PRAGMA integrity_check`) and **backs up the current database first**. *Back up each time the server starts from the launcher* keeps the last N (1 to 100, default 5; other kinds are never deleted automatically).

**Run.** A stop is SIGTERM on Linux, which the server answers with a graceful stop (players disconnected, sessions saved, about 5 seconds); the launcher waits **15 seconds** before it kills the process (Windows: `taskkill`). Servers run while the launcher is open; closing it stops them all. **Restart from the web admin**: the config has `[server] restart_mode = "exit"` ([server-admin.md](server-admin.md#stop-and-restart-the-server)), so the server exits with code 75 and the launcher starts it again by itself (at most a few times a minute).

**Delete** (Settings > Danger zone, the Host list, or *Remove* on its My servers row) asks you to **type the server's name**, then stops the server and removes its entry, folder (database, config, backups, log), settings and unused packages. It cannot be undone.

### Updating the server

The launcher looks for a newer server release for each hosted server **at start, when the Play page or a Manage panel opens (at most every 10 minutes per server and game version) and on *Check for updates***. It compares the installed package's server version with the newest release for your game version in `WaystoneWorks/Poe2Server` (with `WaystoneWorks/Poe2ModdingProject` as the fallback above); a prerelease counts only when no stable release exists. The check is one quiet request: nothing changes, a failure (offline, rate limit) is a line in the hosting panel and never a popup, and with no server installed GitHub is not asked. A newer release shows **Server update available (v0.3.0)** in *Program* with the release notes (markdown subset, rendered as text) and an **Update to 0.3.0** button, and a notice on the Play page.

**Update** (code: `host_update.rs`): downloads the new package and checks its SHA-256 against the release's `.sha256` **while the old server keeps running** (a bad download changes nothing); stops the server gracefully (confirmation first); backs up the database (kind *before update*; the update ends if that fails); unpacks the new package **next to** the old one; writes `server.toml` from the **new** `config/server.example.toml` plus every setting you changed in the old one (including web admin config-editor edits, new sections) and your hosting-panel answers, so untouched settings take the new defaults; starts the server if it ran before and waits up to 90 seconds for its web API (a server that stopped by itself counts as failed); only then deletes the old package folder.

**On any failure after the stop, everything is put back**: the launcher points at the old package, the new folder is removed, the database is restored from the backup (a *before restore* backup of the new server's database is kept) and the old server is started again if it was running. The page says what happened. The database and backups live outside the package. A server stopped before *Update* stays stopped, and the page is busy during the update.

Players outside your network add your server as `<public host>:<web port>` (https if you put a TLS proxy in front), install the game with their own launcher and play ([hosting.md](../../modules/server/docs/hosting.md#what-a-remote-player-needs)).

**What Play does.** `GET /server` gives `login_host`, `login_port`, `instance_port` and `gateway_region` (loopback advertised but reached elsewhere: the address used is taken). The register page `<address>/#/register` goes into `poe-hook.toml` as `register_url`. `deploy` writes `gateway_list.txt` (one entry), installs `version.dll` and `poe_hook_core.dll`, sets `poe-hook.toml` (`mode = "private"`, `login_mode = "standalone"`, `trusted_servers` = the server's login and instance `host:port`) and writes `steam_appid.txt`. Linux runs `proton run PathOfExileSteam.exe --success-event 0` in the launcher's own prefix (`<data>/proton-prefix`, created with `proton run wineboot -u`; crash dumps set aside as in `run-client`); Windows runs the exe directly; output goes to `<data>/logs/game-<time>.log`. The window is frameless (Settings can switch to the system frame); on a Linux AppImage, Settings > Desktop entry installs the `.desktop` file Wayland needs for the icon.

## Logs and crash dumps

*Library, Logs* lists, newest first, the **game logs** written at Play (`<data>/poe2-launcher/logs/game-<time>.log`), the **hosted server's log** (`server/server.log`) and the **crash dumps** the launcher sets aside before the game starts so the client's helper never uploads them (`crash-dumps/`). Pick a file to read the last 3000 lines (at most the last 2 MB; ANSI colours removed). *Search this log* highlights matches; *Only matching lines* and *Warnings and errors only* filter; lines with `error`, `fatal`, `panic`, `failed` or `crash` are red, `warn` lines yellow. A crash dump is binary: listed with its size, not readable here. The folder buttons open the log folder in the file manager. Files are read by an id the launcher listed, never by a path.

## Open web admin

**Web admin** in a server's row opens its web admin in your system browser; it asks for its own login (an account with the `admin` role of that server). For a server hosted on this computer, **Open web admin** in *Manage* opens it too, and on a new server it shows the page that creates the first admin, then (the hash `#/leagues` is kept) the Leagues page, where its first league is created: a new server has none. Leagues and banners come from the server's `GET /api/v1/leagues`; the launcher fetches each base league's PNG banner from the server's own `/api/v1/art/` path (at most 8, 600 KB each) and shows it as a data URL.

## Plain http warning

The launcher sends no password or token to a server (it reads `GET /server` and opens pages in your browser), so it asks no confirmation for a plain `http://` address. A bare `host:port` you type gets `http://` when it is this computer or a local network address (192.168.x.x, 10.x.x.x, 172.16-31.x.x, `*.local`, single-label names) and `https://` otherwise. Passwords typed into a server's web admin over plain http to another computer can be read on the way: a server hosted from the launcher uses plain http on loopback; if you open its web API to other computers, put TLS in front ([hosting.md](../../modules/server/docs/hosting.md#tls-reverse-proxy-for-the-web-api)).

## Releasing

A release is a pushed tag; `.github/workflows/release.yml` of Poe2Launcher does the rest.

1. Set the same new version in `src-tauri/tauri.conf.json` (`version`), `src-tauri/Cargo.toml` and `package.json` (`src-tauri/Cargo.lock` follows from a build), commit and push to `main`. The workflow refuses a tag that does not match all three.
2. Tag and push: `git tag v0.1.1 && git push origin v0.1.1` (in the Poe2Launcher repository). A tag with a `-` (`v0.2.0-rc1`) makes a pre-release, which the update endpoint ignores.
3. The workflow checks the secrets and version, creates a **draft** release with notes from the commits since the previous release, builds on `ubuntu-22.04` (`tauri build --bundles appimage`) and `windows-latest` (`--bundles nsis`) with `tauri-action` (signs the updater artifacts, attaches the AppImage, the `.exe` installer, their `.sig` files and a merged `latest.json` with `linux-x86_64`, `linux-x86_64-appimage`, `windows-x86_64`, `windows-x86_64-nsis`), and publishes only when `latest.json` lists both `linux-x86_64` and `windows-x86_64`. A run takes about 7 minutes. A failed job leaves a draft: delete the draft and the tag, or re-run the failed jobs.
4. Nothing is released from a developer machine. Local check: `TAURI_SIGNING_PRIVATE_KEY="$(cat ~/.tauri/poe2-launcher.key)" TAURI_SIGNING_PRIVATE_KEY_PASSWORD="$(cat ~/.tauri/poe2-launcher.key.password)" npx tauri build --bundles appimage` in `modules/launcher` (do not commit the outputs). The NSIS installer is CI-only; `cargo xwin build --target x86_64-pc-windows-msvc` (`third_party/cargo-xwin`, `XWIN_CACHE_DIR=third_party/xwin-cache`) compiles the Windows binary as a check. Lint workflows with `third_party/actionlint/actionlint`.

**Secrets** (repository secrets of Poe2Launcher; the workflow fails at once if one is missing):

| Secret | What | How it is made |
|---|---|---|
| `TAURI_SIGNING_PRIVATE_KEY` | the updater's private signing key (minisign format, the file's content) | `npx tauri signer generate -w ~/.tauri/poe2-launcher.key -p "$(cat ~/.tauri/poe2-launcher.key.password)"` once, in `modules/launcher`; store the content of `~/.tauri/poe2-launcher.key` as the secret |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | the key's password | a random string kept in `~/.tauri/poe2-launcher.key.password`; the same file's content is the secret |

Set them with `gh secret set TAURI_SIGNING_PRIVATE_KEY < ~/.tauri/poe2-launcher.key` and `gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD < ~/.tauri/poe2-launcher.key.password` (the project owner does this; the tooling does not create secrets). Nothing else is needed: the submodules (client-hook, protocol) are public and checked out with `actions/checkout`.

**Key care.** The key pair lives in `~/.tauri/` (`poe2-launcher.key`, `.key.pub`, `.key.password`, mode 600, outside every repository); only the public key is in the repository (`plugins.updater.pubkey`). Back all three up privately: if the private key is lost, installed launchers can never update again (players must reinstall). If it leaks, generate a new pair, put the new public key in `tauri.conf.json`, release once more signed with the **old** key, then switch the secrets. Never put the key or password in a repository file, an issue or a log.

## Mods

Library, *Mods*: the mods a player runs, **per server**. Format: [../../modules/client-hook/docs/mod-manifest.md](../../modules/client-hook/docs/mod-manifest.md) (manifest v1 and v2, parsed by the shared `poe-hook-mods` crate); building one: [modding.md](modding.md). The hook's loader loads what the launcher puts into `<install>/poe-hook-mods/` and lists in `state.toml`, never in official (read-only) mode, where the Mods tab is hidden.

**Sides.** Every mod has a badge: `client` (runs in the game), `server` (runs on a server) or `both` (one package, two halves). The launcher is for the client half: a **server-only** mod is refused ("it does not belong in the launcher's mod store", with the `poe-server mod install` hint), and from a `both` package only the client half is unpacked: the `server/` files never reach the player's disk. A mod with a DLL carries a *code* badge: it runs inside the game process with your user's rights (trust note: [modding.md](modding.md#client)).

**Cache and versions.** Everything you add or download goes to `<data>/poe2-launcher/mods/cache/<id>/<version>/` after `verify_package` accepted it (SHA-256 against the `.sha256` or pinned hash, `<id>-<version>.zip` name, paths, links, size limits, CRCs, manifest; a failed check leaves nothing). Several versions of one mod live side by side. *Add package (.zip)* takes a package (a `.sha256` next to it is used; without one a warning says the identity is not pinned); *Add folder* a developer's mod folder (identity: a hash over its client files).

**Per-server sets.** The *Mods for* picker selects a server (or *All servers*). A server's **required** mods are always on for it, in the version the server pins. Your own mods are **off on a server unless enabled for it** (the checkbox), or for all servers. Dependencies are pulled from the cache; an own mod that conflicts with a required one, is incompatible or lacks a dependency is left out with a note. **Play** copies the selected server's set from the cache into the game's `poe-hook-mods/` and writes `state.toml` (load order: dependencies, `load.after/before`, then your arrangement: the row arrows move a mod within the selected server's own list, mods on for all servers are ordered under *All servers*, and the *load order N* chip is the position Play uses); mods a previous server needed are removed. Folders in `poe-hook-mods/` that the launcher did not create (a developer's `deploy-mod`) are never touched and not enabled. A game-version mismatch can be overridden per mod; a mod ABI mismatch cannot (the loader would refuse it).

**Mod sync** (Settings, *Mods*: **Off / Ask / Auto**, default Ask). A server that requires mods says so in `GET /api/v1/server` (the optional field `mods`, [../architecture/web-api.md](../architecture/web-api.md#mods)): per mod `id`, `version`, `side`, `sha256`, `size`, `required`, `hook_api`, `game_versions`, `sources` and a display `name`, `authors`, `description`. The launcher compares that with its cache when you select the server and again before Play:

- **Off:** shows what is missing (Mods tab, the reason under Play) and **blocks Play**; nothing is downloaded.
- **Ask:** pressing Play opens a dialog listing the missing required mods (name, version, side, size, *contains code*) with **Download**; Cancel stops Play. A failed download keeps the dialog open with the reason.
- **Auto:** downloads, verifies and switches silently and shows a toast. It includes code mods, also from a server you added a minute ago, without another question (use Ask if you do not want that).

Downloads come from the server itself (`/api/v1/mods/{id}/{version}.zip`) and then any extra `https://` addresses in `sources`; the package is kept only if its SHA-256 equals the advertised one and `verify_package` accepts it (size capped at the advertised size). A mismatch installs nothing. Plain `http://` to another machine needs the confirmation of the Servers page first (otherwise the server's own download path is not used). A required mod incompatible with your game version or hook ABI (or without a usable address) blocks Play in every mode with the reason; optional (`required = false`) mods are listed but never block. Servers without a `mods` field work as before. The check is advisory: the server may verify the client's mods at login ([mod-host.md](../architecture/mod-host.md#the-login-check-of-the-clients-mods)), a modified client can still lie.

## Testing

UI preview without the backend: `npm run dev`, then `/?mock` (switches such as `?offline`, `?hostpkg`, `?mods&modsync` in `src/lib/mock.ts`; routes like `#/library?tab=mods&view=browse`); screenshots only headless (`chrome-headless-shell --headless --screenshot`, minimum window 860x600), never a visible window. Unit tests use a mock keyring-free profile store, a mock web API, a mock GitHub API and a fake Proton; ignored tests (`hook_flow real_release`, `host_flow real_package`, `fetch_tool`) hit the real network or a real server package. Commands and the scratch-server setup: [setup.md](setup.md#launcher-build-and-test), [setup.md](setup.md#web-api). The Linux end-to-end path (depot install, hook download, Host a server with an update, Play, web admin, restart) has passed.

## Not done

- Windows: the launch path, installer, update, Host a server and restart are untested (no Windows machine); `cargo check` runs in CI.
- Mod sync has not run against a real server with mods; nothing was played with a mod from the launcher.
- Unverified on a real desktop: window drag and resize, the icon, minimize on Play, Official play.
- Mod signatures and packaging beyond a zip. Windows code signing (SmartScreen warning). macOS builds.

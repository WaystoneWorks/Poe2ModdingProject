# Setup

The only place in `docs/` for commands, log locations and unattended tests. Rules (what may be touched, official servers read-only): [../../CLAUDE.md](../../CLAUDE.md).

## Requirements
- Linux with rustup. `rust-toolchain.toml` pins `nightly-2026-08-10` (`poe_data_tools` needs nightly). Targets: `x86_64-unknown-linux-gnu` and `x86_64-pc-windows-msvc`.
- clang and lld (`clang-cl`, `lld-link`), used by cargo-xwin to link the Windows DLL.
- `gh` and `git`, for the tool downloads.
- Steam with Proton Experimental, to run the client.
- `GameFiles/`: a copy of the 0.5.5e Hotfix 1 client install (not in git). The Steam install itself is never used or modified.

## Tools
`third_party/fetch-tools.sh` downloads every external tool into `third_party/` (listed in [third_party/README.md](../../third_party/README.md)): poe_data_tools CLI, dat-schema, LibGGPK3, cargo-xwin, the Python venv `pyenv` for `scripts/re` ([../re/README.md](../re/README.md)), reference repos and the pinned toolchain.

Game files (what they are: [../re/datamining.md](../re/datamining.md)), from the repo root:
```sh
T=third_party/poe_data_tools/poe_data_tools
$T -p 2 --steam GameFiles list 'data/balance/*.datc64'
$T -p 2 --steam GameFiles extract out/ 'metadata/characters/str/*'   # output folder first
$T -p 2 --steam GameFiles dump-tables ...      # tables -> CSV/JSON using the schema
```

## Clone
This repository is the hub ([overview](../overview.md)); submodules live under `modules/`: `server` (Poe2Server, nesting `protocol`, `client-hook`, `web-admin`), `protocol`, `client-hook` (nesting `protocol`), `web-admin`, `launcher` (nesting `client-hook` and `protocol`), `mod-sdk`, `mod-index`, `server-list`. `gh` is only needed for tool downloads; repositories are cloned over plain https:
```sh
git clone --recursive https://github.com/WaystoneWorks/Poe2ModdingProject.git
# or, after a plain clone / after pulling a changed submodule pointer:
git submodule update --init --recursive
```
Submodule changes: commit inside the submodule (`modules/...`) first, then the new pointer here.

## Build and test
```sh
cargo build                 # the hub's workspace: xtask only
cargo xtask server build    # the server (modules/server, its own workspace; --release)
cargo xtask server test     # the server's tests (cargo test in modules/server; poe-data tests read GameFiles if present; movement replay tests need the game's curves from the hub's `GameFiles/`, `POE_GAME_DIR` points elsewhere, and panic without them)
cargo xtask build-dll       # modules/client-hook -> version.dll (loader) + poe_hook_core.dll (x86_64-pc-windows-msvc);
                            # output modules/client-hook/target/x86_64-pc-windows-msvc/release/
python3 scripts/check-links.py   # relative links and #anchors in the docs, README.md, CLAUDE.md, dumps/README.md
```
Port tests: `cargo test --release -p poe-game` (lib, `tests/replay.rs` 27 + 2 ignored, `tests/rules.rs` 7, `tests/clientpath.rs`), `cargo test --release -p instance-server` (86; the replay tests run the port through the actor and Codec), `cargo test --release --workspace`: all pass. Local replay check: `runtime/replay/check.sh [--free] [--show N] [--trace LO HI]`. Game file lookup: `cargo run --release -p poe-game --example gamefile -- find WORD..` or `-- cat PATH [GREP]`; stat names: example `statnames`. End-to-end inputs include cursor aims: `scripts/re/movement_own_inputs.py` adds `0x62` mode 2 aims (key episodes still drop them) and `movement_session_replay.py` emits `aim` ops from trace `in-AimTarget Aim {..}` rows. Session replay of a private test: `scripts/re/movement_session_replay.py TRACE PORT POE_HOOK_LOG OUT_DIR` ([movement.md](../protocol/movement.md#movement-trace)).
`build-dll` runs `third_party/cargo-xwin/bin/cargo-xwin xwin build -p poe-hook -p poe-hook-core --target x86_64-pc-windows-msvc --release` in `modules/client-hook/` and keeps the MSVC SDK cache in `third_party/xwin-cache`.

## Run
The server is Poe2Server (`modules/server`, own Cargo workspace and `target/`). `cargo xtask server run` builds it and runs it **with the hub root as working directory**, because every path in its config (`GameFiles/`, `dumps/`, `runtime/`, `modules/protocol/...`, `modules/web-admin/dist`) is relative to it. Running `modules/server/target/debug/poe-server` by hand works the same from the hub root with `POE_CONFIG` set. In a standalone Poe2Server checkout the working directory is that repository's root.

```sh
cargo xtask server run     # login (20481) + instance (6112) servers + web API (127.0.0.1:8080), config modules/server/config/server.toml (add --release for play; --config <file> or POE_CONFIG=<file> for another, e.g. runtime/server.dev.toml, see below); rebuilds the web admin first when its sources are newer than dist/build.json (--no-web-build skips that, see Web admin (build))
cargo xtask deploy-client   # builds the DLLs and installs them into GameFiles/ (--official: read-only observation of official sessions, see below and official-mode.md; --no-build; --sample-mod: also install the sample mod, enabled)
cargo xtask deploy-mod      # install a client mod (default: the sample mod) into GameFiles/poe-hook-mods/<id>/ and enable it; [dir] [--dll f] [--disable] [--no-build]
cargo xtask deploy-core     # rebuilds and installs only the debug core; a running client reloads it within about a second (--no-build)
cargo xtask dll-data        # rewrites only GameFiles/poe-hook-data/ (stats, action types, areas)
cargo xtask run-client      # launches the client through Proton (Steam must be running)
cargo xtask revert-client   # restores GameFiles/ to the original state
cargo xtask release-mirror <dir>  # server and hook release files as a static release source folder for the launcher; flags: launcher.md#release-source
scripts/set-owner.sh OWNER [--apply]  # rewrites the GitHub owner in all links and defaults (dry run without --apply)
cargo xtask openapi         # writes modules/server/docs/openapi.json from the web API code (runs `cargo xtask openapi` of Poe2Server; --check: fail if stale)
cargo xtask terrain-matrix  # writes docs/status/terrain-matrix.tsv (area x topology x orientation) from the game data and dumps/<version>/terrain/vectors/ (--dumps, --out)
cargo xtask check-build <exe> # what a game build breaks: signatures, offsets, opcode drift, strings, game data, identity (report dumps/<version>/check-build.md; --bundles, --version, --report; exit 0/1/2): new-game-version.md
cargo xtask versions        # copies modules/protocol/versions/<version>.toml into the launcher (modules/launcher/versions/); --check only compares
cargo xtask login-token <account> <64 hex digits>   # remember-me token for the standalone client, see below
cargo xtask select-gateway  # only points the remembered gateway of the prefix at our server
```

`deploy-client` (logic in `poe-hook-deploy` in `modules/client-hook`; xtask passes the paths):
- Backs up `GameFiles/gateway_list.txt` to `gateway_list.txt.orig` (once).
- Writes a single UTF-16LE gateway entry from `[gateway]`, `[network] public_host` and `[network.login] bind` (its port) in `modules/server/config/server.toml`.
- Copies the loader to `GameFiles/version.dll` and the debug core next to it.
- Writes `dump_dir` (`<repo>/dumps/<version>` as a `Z:\` path) into `GameFiles/poe-hook.toml`; the DLL writes terrain grids and layouts, area exports and client tables there ([../../dumps/README.md](../../dumps/README.md)).
- Writes the DLL's name tables to `GameFiles/poe-hook-data/` (`stats.tsv`, `action_types.tsv`, `areas.tsv` for the area picker).
- Copies `modules/client-hook/poe-hook/poe-hook.toml`, unless a copy exists (local edits survive).
- Sets `login_mode` (`standalone` by default; `--login-mode steam` is for observing official servers: our server refuses the Steam login) and `trusted_servers` (`[network] public_host` with the login and instance ports) at the top of that file. `--official` writes `login_mode = "steam"` and `trusted_servers = []`.
- Sets `position_sync_port` in `[features]` to `[network.instance] public_port`, so the side channel (position reports, debug link, terrain upload) goes to the instance server.
- Resets `auto_keys` to `[]`, and the client's remembered gateway (`gateway_id` in the test prefix's `poe2_production_Config.ini`) to ours for private deploys (after an official session it stays on an official realm and never contacts our server).
- Writes `steam_appid.txt`.
- With `--sample-mod` (not with `--official`), or `cargo xtask deploy-mod [dir]`: installs a client mod into `GameFiles/poe-hook-mods/<id>/` (`mod.toml`, data, entry DLL) and appends its id to `GameFiles/poe-hook-mods/state.toml`; the loader loads it at the next client start ([../architecture/client-dll.md](../architecture/client-dll.md#mod-loader), spec `modules/client-hook/docs/mod-manifest.md`). `revert-client` removes mods installed this way (not the launcher's). `deploy-mod` refuses when GameFiles is deployed in official mode.

`cargo xtask --prefix <dir> <command>` (global option) runs `run-client`, `login-token`, `select-gateway` and the gateway selection of `deploy-client` against another Proton prefix, for a second client (`third_party/proton-prefix-2`, a copy of the first; [hosting.md](../../modules/server/docs/hosting.md#local-two-client-test)). `select-gateway` only writes the remembered gateway (`gateway_id`) of the chosen prefix to ours. `run-client` uses its own prefix (`third_party/proton-prefix`) with `WINEDLLOVERRIDES=version=n,b`, clears `GameFiles/poe-hook.log` per launch, and moves pending crash dumps away ([Crash reports](#crash-reports)). `build-dll` and `deploy-client` are thin wrappers over `poe-hook-deploy` ([../architecture/client-dll.md](../architecture/client-dll.md)).

### Developer config

`modules/server/config/server.toml` is committed with **safe values**: login and instance servers listen on loopback only, there is no password-less login, and the developer tools (`[dev] position_sync`, `debug_link`, `movement_trace`, `known_seeds`) are off. A checkout cannot be reached from the network by accident and needs a real account (`account create`, [below](#accounts-and-characters-offline)) to log in.

Development needs the opposite: every interface for remote and two-client tests, the debug link and position sync for the overlay and drift checks, the movement trace and known terrain seeds. Those overrides live in a **git-ignored copy**:

```sh
python3 scripts/dev-config.py                      # writes runtime/server.dev.toml from modules/server/config/server.toml (all comments kept)
cargo xtask server run --config runtime/server.dev.toml     # or POE_CONFIG=runtime/server.dev.toml cargo xtask server run
POE_CONFIG=runtime/server.dev.toml cargo xtask deploy-client      # deploy-client reads public_host and the ports from the same file
```

`scripts/dev-config.py --if-missing` only writes a missing file; without the flag it overwrites (keep personal changes in a copy under another name). `scripts/test-mp.sh setup` makes its own `runtime/server-mp.toml` from the same script. The unattended tests ([below](#unattended-client-tests)) use the dev config; they log in with a test account. Never use the dev config on a server others can reach ([hosting.md](../../modules/server/docs/hosting.md#security-notes)).

### Web API

`poe-server` serves the web API on `[web] bind` (default `127.0.0.1:8080`; `[web] enabled = false` turns it off). Try `curl localhost:8080/api/v1/server`. For the admin endpoints make an admin offline ([Accounts and characters](#accounts-and-characters-offline)), `POST /api/v1/login` and send the token as `Authorization: Bearer <token>`. To serve the built web admin set `[web] static_dir` to its `dist`; for Vite development put its origin in `[web] cors_origins`. Details: [../architecture/web-api.md](../architecture/web-api.md). A second server on shifted ports (smoke test): copy `modules/server/config/server.toml`, change `[network.login] bind`, `[network.instance] bind`/`public_port`, `[web] bind`, `[database] path` and the audit log path, start with `POE_CONFIG=<copy>`.

### Accounts and characters (offline)

These run against the database (also while the server is up), print a result and exit. They make the first admin; every other account command also works in chat and the overlay ([server-admin.md](server-admin.md#accounts)).

```sh
cargo xtask server run -- account create alice --password-stdin   # type the password, Enter; also: role <name> <player|admin>, disable|enable <name>, passwd <name> --password-stdin, list
cargo xtask server run -- account role alice admin
cargo xtask server run -- character create <account> <name> <start_state> [area] [league]
cargo xtask server run -- character list [account]
```

`poe-server league list|create|end|delete` manages leagues offline ([server-admin.md](server-admin.md#leagues)). `character create` works like the character creation screen (slot limit and name rules apply). `start_state` is a `CharacterStartStates` id (e.g. `DexFourDefault`), `area` a `WorldAreas` id, `league` defaults to the default league (none: create one first). A character created with an explicit town or hideout area counts as having played the intro. `POE_CONFIG=<file>` selects another config (and database).

### Web admin (build)

The web admin is the Svelte app in `modules/web-admin` (Node 22 and npm; `git submodule update --init modules/web-admin` if empty). What it shows and how it talks to the API: [../architecture/web-api.md](../architecture/web-api.md#the-web-admin-spa).

```sh
cd modules/web-admin && npm ci && npm run build      # npm run dev: Vite on port 5173, proxies /api to [web] bind
cargo xtask server web-admin [--check] [--force]     # the same check `server run` does: rebuild only when the sources are newer than dist/build.json
```

**Which web admin the dev server serves:** `[web] static_dir = "modules/web-admin/dist"` (the committed default) is resolved from the hub root, so a server started from the hub serves the hub's `modules/web-admin`, the single source of truth in development. The copy at `modules/server/modules/web-admin` (nested submodule of Poe2Server) only feeds the server's releases and CI. `cargo xtask server run` runs `npm ci` (when `node_modules` is missing) and `npm run build` when a file in `src/`, `public/`, `index.html` or the package and build config is newer than `dist/build.json`. The build writes `dist/build.json` (name, version, build time, commit); the server logs it at start (`serving the web admin ... version=... built_at=... commit=...`) and warns when the sources are newer or `build.json` is missing. Open <http://127.0.0.1:8080>; only `admin` accounts get in; the session lasts 12 hours.

### Launcher (build and test)

The launcher is the Tauri 2 app in `modules/launcher` (Node 22, Rust, on Linux the WebKitGTK stack; system packages: [launcher.md](launcher.md)).

```sh
git submodule update --init --recursive
cd modules/launcher && npm ci && npm run tauri dev       # or: npm run tauri build -- --debug
cd src-tauri && cargo test                               # mock keyring, mock web API, fake Proton
```

Against a real local server (a scratch config with shifted ports as under [Web API](#web-api), `open_registration = true` and an account made offline):

```sh
cd modules/launcher/src-tauri
POE_LAUNCHER_TEST_URL=http://127.0.0.1:18080 POE_LAUNCHER_TEST_USER=alice POE_LAUNCHER_TEST_PASS="a long password" \
  cargo test --test core_flow real_server -- --nocapture
cargo test --test fetch_tool -- --ignored                # downloads and starts the pinned DepotDownloader (never logs in)
```

### Two-client test (LAN)

`scripts/test-mp.sh` runs two real game clients against one server on one machine (Steam must be running); checks and results: [hosting.md](../../modules/server/docs/hosting.md#local-two-client-test). Environment: `LAN_IP`, `MP_RES`, `MP_BORDERLESS`, `MP_AREA`, `MP_CLASS` (documented in the script's header).

```sh
scripts/test-mp.sh setup      # build, runtime/server-mp.toml (LAN IP, own database), accounts + one Ranger each in G1_town, prefix 2, deploy
scripts/test-mp.sh server     # poe-server, log runtime/server-mp.log
scripts/test-mp.sh clients    # token login + Play for both (client <n> [acct] for one; acct = duplicate-login test)
scripts/test-mp.sh keys 1 inmove:640,200 indown:0x57 wait:2000 inup:0x57   # poe-hook.1.keys: input for client 1
scripts/test-mp.sh shot 2     # F8 screenshot of client 2 (prints the file)
scripts/test-mp.sh status     # processes, memory, session lines of the server log
scripts/test-mp.sh stop       # kill the clients; then stop the server in its own call; puts prefix 1's window size back and redeploys the private standalone-login state (`restore` does just that)
```

The second client uses `third_party/proton-prefix-2` (a copy of the first with its own credentials, screenshots and gateway) through `cargo xtask --prefix third_party/proton-prefix-2 ...`. `POE_HOOK_KEYS_FILE=poe-hook.<n>.keys` gives each DLL its own input file ([entries](#poe-hookkeys-entries)).

### Remember-me token (auto-login)

With `login_mode = "standalone"` the client's Remember Me stores a 32-byte token issued by the login server (`AuthenticationResult.session_token`). To sign an account in without typing the password:

```
cargo xtask login-token <account> <64 hex digits>
```

It writes the token to `third_party/proton-prefix/pfx/drive_c/users/steamuser/Documents/My Games/Path of Exile 2/poe2_production_login.credentials` (32 raw bytes, owner-only) and sets `[LOGIN] username=<account>` and `save_login=true` in `poe2_production_Config.ini` there. Start the client with `run-client` and press **Login** with the password box empty. The client reads both files itself; the DLL has no part in it (`poe_hook_deploy::LoginTokenFiles` makes the file names a parameter). A rejected token (stale, revoked or unknown: the server answers `0x0f` with a notice) makes the client delete the file. Library API: `poe_hook_deploy::write_login_token(prefix_or_documents_dir, account, token)`.

### `login_mode` and `trusted_servers`

`deploy-client` writes `login_mode = "standalone"` into `GameFiles/poe-hook.toml` by default (also the DLL's default): the client shows the account/password screen and sends `0x0003`. Existing configs get the keys on the next deploy; to go back set `login_mode = "steam"` and `trusted_servers = []` (or `--login-mode steam`). `deploy-core` does not touch the config. `scripts/test-run.sh` and `scripts/test-mp.sh` need `standalone` (they sign in with a Remember Me token, [Unattended client tests](#unattended-client-tests)); the Steam mode only suits observing official servers (`--official`).

## Config

`modules/server/config/server.toml` is the committed config with safe values (developer switches: [Developer config](#developer-config)); `modules/server/config/server.example.toml` is a fully commented copy with every key and its default, the template for a hosted server (a `poe-config` test parses both and checks the committed one is safe). `POE_CONFIG=<path>` selects another file. Sections: `[game]`, `[network]` (+ `.login`, `.instance`), `[instance]`, `[movement]` (only `sprint_buff_rows`), `[accounts]`, `[database]`, `[dev]`, `[terrain]`, `[spawn]` (+ `.start_tiles.<area>`, `.upload`), `[cluster]`, `[web]`, `[commands]`, `[chat]`, `[player]`, `[inventories]`, `[gateway]`, `[logging]`. Leagues are in the database (a leftover `[[leagues]]` block only logs a warning). Env overrides: `POE_CONFIG`, `POE_SWEEP` (overrides `[dev] sweep`), `RUST_LOG` (overrides `[logging] filter`).

### Config key changes

The server reads only the current layout (a config with `[login]`/`[instances]` fails to parse because `[network]` is missing). Removed keys in a config file are ignored (unknown keys do not fail the load). Where keys live:

Moved or removed: `[login]`/`[instance]` hosts and binds are now `[network]`, `[network.login]`, `[network.instance]` (`public_host` is one value); `[instances] idle_minutes` is `[instance] idle_minutes`; `known_seeds`, `position_sync`, `movement_trace`, `debug_link`, `sweep`, `sweep_results` live in `[dev]` (`drift_check`, `drift_interval_ms` run the drift checker); movement workaround keys are gone (`[movement]` holds `sprint_buff_rows` and the five `sprint_*` coasting keys); there is no `[admin]` list (admin is the account role) and `[accounts] dev_machine_hash_login` is ignored with a warning.

Other keys:

| Key | Meaning |
|---|---|
| `[security]` | password attempt limits and `trust_forwarded_for` ([accounts.md](../architecture/accounts.md#password-attempt-limits)) |
| `[security] allow_unknown_client` | default `false`: a client whose exe hash (`client_hash`) is not a known value of the version is refused with "you need to update"; `true` accepts it (logged). Nothing is refused while the version file's `[client] hashes_confirmed` is `false` ([new-game-version.md](new-game-version.md#what-the-server-does-with-the-clients-version)) |
| `[cluster] id` | cluster identity; login tokens from another id are invalid (default `"local"`) |
| `[accounts] open_registration` | whether `POST /api/v1/register` may create accounts (default `false`) |
| `[accounts] remember_days` | lifetime of a Remember Me login (default `30`) |
| `[web]` | `enabled` (`true`), `bind` (`127.0.0.1:8080`), `static_dir`, `cors_origins`, `log_buffer` (`2000`): [../architecture/web-api.md](../architecture/web-api.md) |
| `[network.login] public_port` | port written into the gateway entry and trusted list when it differs from the bind port (default: the bind port) |
| `[instance] first_entity_id` | first entity id of an instance's counter (default `12000`, the official value for players) |
| `[game] version`, optional `[game] protocol_dir` | `version` selects `modules/protocol/versions/<version>.toml`, the single definition of a build ([new-game-version.md](new-game-version.md)); `protocol_dir` defaults to its `[protocol] opcodes`; `{version}` in `[dev] known_seeds`, `[dev] sweep_results` and `[spawn] layout_dir` is replaced by `[game] version`; an unknown version stops start-up |
| `[network.login]` `pre_auth_read_timeout_secs`, `pre_auth_login_timeout_secs`, `pre_auth_max_buffer`, `max_pre_auth_connections`, `max_pre_auth_per_ip`; `[network.instance]` `pre_auth_read_timeout_secs`, `pre_auth_max_buffer`, `max_pre_auth_connections`, `max_pre_auth_per_ip` | limits before a client has logged in or shown its ticket: a message must arrive complete within 15 s, login must finish within 60 s (login server), at most 64 KiB buffered for an incomplete message, at most 256 such connections in total and 16 per client IP (IPv6 per /64); connections over a limit are closed (a log line, at most one per second). `0` turns a limit off. [hosting.md](../../modules/server/docs/hosting.md#security-notes) |
| `[spawn.upload]` | terrain upload from client DLLs (default off): `enabled`, `max_bytes`, `max_layout_bytes`, `max_grid_bytes`, `wait_ms`, `wait_upload_secs` ([hosting.md](../../modules/server/docs/hosting.md#terrain-spawn-spawnupload)) |
| `[spawn] player_spacing` | smallest distance in grid cells between a joining player's spawn cell and players already in the instance (default `8`; `0` = spawn where requested); a closer spawn moves to the nearest free walkable cell ([../protocol/entities.md](../protocol/entities.md#implementation-notes)) |
| `[dev] remote_blob_omit`, `remote_animated_path` | bisect switches for the remote player's look: parts of the generated remote blob to leave out (`"stat_sets"`, `"derived_stats"`, `"life_state"`, `"player_flags"`) and whether to add the class's `.ao` path (defaults: everything sent, no path; [../protocol/entities.md](../protocol/entities.md#remote-player-look)) |
| `[player] animation_sets` | the three animation set names of a remote player's blob (official, weapon dependent; the example config omits it) |

## Playing from Steam (non-Steam game shortcut)
Steps: [steam-shortcut.md](../re/steam-shortcut.md).

## Official servers (read-only observation)
**Read this first**; the full guide is [official-mode.md](official-mode.md). This mode lets you observe and log your own official sessions. The DLL sends, alters and injects nothing, but it still **patches game code in memory** to observe (inline detours, a Vulkan hook, the `version.dll` proxy), and the anti-cheat may detect any injected DLL as a violation. Do not use it on an account you care about. The launcher never does this (apart from its explicit Official (read-only) entry).

1. `cargo xtask deploy-client --official`: the original gateway list goes back into `GameFiles/`, and `poe-hook.toml` gets `mode = "official"`, `login_mode = "steam"` (the client is not patched; the Steam login screen shows) and `trusted_servers = []`. The GameFiles copy must be the live game's build; after a patch, update GameFiles first.
2. Start Steam, then `cargo xtask run-client` (the copy in its own Proton prefix).
3. Play. The overlay shows `OFFICIAL: read-only`; packets, logs and snapshots go to the session folder ([Logs](#logs)). What the DLL does and does not do: [../architecture/client-dll.md](../architecture/client-dll.md#modes-and-the-read-only-latch).
4. `cargo xtask deploy-client` switches back to our server.

Comparing a session with one from our server: [../re/captures.md](../re/captures.md).

## Unattended client tests
With Steam running (else the client logs `Unable to init Steam API` and exits with code 1) and the server, started with the [dev config](#developer-config), writing to `runtime/server-run.log` (`POE_CONFIG=runtime/server.dev.toml modules/server/target/debug/poe-server > runtime/server-run.log 2>&1`):
- `scripts/test-run.sh <name> [seconds]` signs the test account in, launches the client and enters the game by itself (`auto_keys`). GameFiles must be deployed with `cargo xtask deploy-client --no-build --login-mode standalone` (the script checks). The script makes the account `testrun` (admin, one character; `TEST_ACCOUNT`, `TEST_CLASS`, `TEST_AREA` change it) offline with a random password in `runtime/test-accounts/<name>.pw` (git-ignored, mode 600, never printed), gets a Remember Me token for it from the web API (`POST /login`, then `POST /game-token`) and writes it with `cargo xtask login-token` ([above](#remember-me-token-auto-login)); the Enter at 20 s then logs in with the empty password box. Helper functions are in `scripts/lib/test-accounts.sh`; `scripts/test-mp.sh` uses them for `mp1` and `mp2`. The web API must be on (`[web] enabled`, the default). It first deletes `dumps/<version>/terrain/layouts/*` and `grids/*` so the run shows whether the DLL exports them again (the server waits for the layout by tile hash). It sets these environment variables for the client:
  - `POE_HOOK_AUTO_KEYS=20000:13` (Enter at 20 s, press Login; `[[ms, vk], ...]` in `auto_keys` form);
  - `POE_HOOK_MOVEMENT_LOG=1` (per-frame movement log, `movement_log` in the config);
  - `POE_HOOK_PATH_LOG=1` (the client's pathfinder plans as `PATHPLAN` lines, `path_log` in the config);
  - `POE_HOOK_PHASE_LOG=1` (message-phase and roll rows in `poe-hook.log`, read by `runtime/replay/phasetab.py`; [movement-sprint.md](../re/movement-sprint.md)). Rows: `TOL frame stat|2pi ra 142 id ty` (hooks `0x14197e1c6` / `0x14197e1e3`: the facing tolerance of a started action); `FACE frame comp phase new old ra ra2` (hook at the store `0x141ddc91a` of Positioned_SetFacing; a hook at its entry `0x141ddc820` hangs the client at startup before the login scene: ruled out); `player actions` slots print `/142=..`/`id=..` and the state `2b4=` `2b8new=`; LINE rows end with `o=` (Positioned `+0x1e3`). Facing findings: [movement-roll.md](../re/movement-roll.md#facing-event-first-heading-checked-by-replay);
  - `POE_HOOK_FAKE_FOCUS=1` (the hooked `GetForegroundWindow` returns the game's own window, `*[0x1445d8350]`, so a client on another desktop still sends cursor reports; never while read-only);
  - `POE_HOOK_WINDOW_TITLE="PoE2 Test Client"` (hooks on `CreateWindowExW`/`SetWindowTextW` give the game's main window (class `POEWindowClass`; message boxes and other windows keep their titles) that title, so a desktop rule can match it).
- `scripts/re/send_dev.py <command>` sends a server command over the debug link (like the overlay). The link is authenticated per session, so the script queues a `cmd:<command>` entry in `GameFiles/poe-hook.keys` and the running client DLL sends it.
- `scripts/shot.sh <name>` takes a screenshot of the game monitor (Spectacle) into `runtime/shots/`; F8 takes one inside the game.
- `echo <entry> > GameFiles/poe-hook.keys` presses keys and moves the mouse in the client; `0x2d` is Insert (the overlay), `0x0d` Enter.

### Game tests (`cargo xtask game-test`)
`cargo xtask game-test <scenario>` runs one test with no human and no server of your own: it takes `runtime/client.lock` (refuses while a live process holds it, or a GameFiles client or any `poe-server` runs), builds the DLLs and the server (`--no-build` skips), deploys with `deploy-client --no-build --login-mode standalone` when GameFiles differs from the build (refuses an official deploy), starts Steam, starts the server with a fresh dev config plus the scenario's overrides, signs the test account in as `scripts/test-run.sh` does, launches the client, presses Play, runs the steps, closes the client and the server (SIGINT), and prints pass/fail per step. Server panics and hook `PANIC:` lines fail it. All output goes to `runtime/game-test/<scenario>-<time>/`: `summary.txt`, `server.log`, `server.toml`, `client-run.log`, `poe-hook.log`, the run's part of `Client.txt`, `hook-session.txt` (the DLL's session folder), `build.log`, `account.log`, `deploy.log`.

With the movement port ([instance-world.md](../architecture/instance-world.md#the-movement-seam-movementrs)) `smoke`, `state`, `walk`, `sprint-w`, `cliffs` and `dungeon` pass. No scenario covers the `speed` command. Every close logs `ERROR [exit_trace] TerminateProcess`. `--display gamescope` (default) wraps the client in gamescope with the headless backend (`GAME_TEST_GAMESCOPE_ARGS`, default `--backend headless -W 2560 -H 1440`; gamescope runs its own Xwayland). `--display desktop` shows the window on the desktop. `--login-timeout <s>` (240).

Scenarios are TOML files in `scripts/game-test/` (name without `.toml`, or a path). Top-level keys: `description`; `account`, `class`, `area` (the test account and the character made on first use; defaults `testrun`, `DexFourDefault`, `G1_town`); `input_mode` (`wasd` or `mouse_and_keyboard`, set in the test prefix, restored after); `[client_env]` (extra `POE_HOOK_*` variables); `[server]` (dev config overrides, `"dev.drift_check" = true`); `after` (shell commands run from the hub root once the client and server are closed, `{session}` replaced by the DLL's session folder; each passes on exit code 0, output in `after-<n>.txt`, its last line in the summary; `{dir}` is the run folder); `setup` (shell commands, run after sign-in and before the client starts, with `srv` = the server binary on the run config, `$WEB` the web port, `$ACCT`, `$CFG`; a failure ends the run); `play = false` (no Play press: the `[[select]]` steps enter the world); `[[select]]` steps (same actions as `[[step]]`, run at character select). Each `[[step]]` has an optional `name` and one action:
- `keys = "<entries>"`: [`poe-hook.keys` entries](#poe-hookkeys-entries); the runner waits for the DLL to read the file, then for the `wait:` and hold times inside.
- `cmd = "<server command>"`: a `cmd:` entry (debug link); resent for up to 20 s while the DLL logs `sent: false` (its link is not up yet right after loading). `transfer <area> <seed>` and `teleport <x> <y>` ([server-admin.md](server-admin.md)) put the player on a known layout and cell.
- `wait_ms = <ms>`.
- `expect_log = "<regex>"`: passes when a line matches in `log` (`server` default, `hook`, `client`) after the step starts, or since the scenario started with `since = "start"`, within `timeout_s` (default 30).
- `reject_log = "<regex>"`: fails when a line matches in `log` since the scenario started.
- `expect_state = { ... }` (inline table): passes when all checks hold in one fresh [state](#live-state-file) (`t` at most 3 s old) within `timeout_s` (default 10). Checks: `area = "<regex>"` (whole id, e.g. `"G1_town"`, `"G\\w+"`); `near = [x, y, r]` (player grid within r cells); `moved = N` (at least N cells from the player's cell at the start of the previous step); `panel = "<text>"` / `no_panel = "<text>"` (a visible panel path contains / none contains the text, after naming `@<vtable>` segments with `scripts/game-test/panels.toml`, now `"@1430a3a28" = "inventory"`); `moved_max = N` (at most N cells); any other key is a dotted path into the JSON (`"player.life.current" = ">= 1"`, `"player.grid.0" = 100`): a string starting with `>=`, `<=`, `>`, `<`, `==`, `!=` compares numbers, anything else is equality.
- `walk_to = [x, y, r]` (needs `input_mode = "wasd"`): holds the W/A/S/D combination pointing closest to (x, y) for a time sized from the distance and the speed seen so far (about 37 cells/s; each `indown:` adds the DLL's 100 ms), reads the new cell from the state file and repeats until the player is within r cells (r 3 works: a short hold still walks about 4 cells). Fails after `timeout_s` (default 30), when two holds in a row barely move (stuck), or after 8 holds without getting closer. Keys walk these grid directions: W (+1, +1), S (-1, -1), D (+1, -1), A (-1, +1) (measured; the `0x63` vectors). One line per hold goes to `walk.tsv` in the run folder (target, cell, keys, hold ms, new cell, cells moved, speed).
- `walk_to = [x, y, r]` with `blocked = true`: holds the one combination that points at (x, y) from the start, 1 s at a time, and passes when the player stops short (a wall); fails when it gets within r.
- `roll = "<keys>"` (`"W"`, `"WD"`; `""` rolls standing, towards the cursor): holds the keys, presses Space as a real hold (`indown:0x20 0x20 wait:250 inup:0x20`), releases the keys after `hold_ms` (default 1000). The client plans a roll around a wall rather than stopping dead at it.
- `max_drift = <cells>`: waits 1.5 s, then fails when a server `drift` line since the last action step (keys, cmd, walk_to, roll; `since = "start"`: the whole scenario) is above the limit. Needs `"dev.drift_check" = true` in `[server]`.

After "player entered the world" the runner waits (up to 120 s) until the state file shows the player, since the loading can last a minute longer. Key, cmd, walk and roll steps add the player's cell after the step to their summary line.

Wall, open-ground and narrow-passage cells for a layout come from the server's generated grid: `modules/server/target/release/examples/wall_probe <area> <seed> [--count N]` (build: `cargo build --release -p poe-world --example wall_probe` in `modules/server`; run from the hub root; output format in the file's header). The natural layout it uses is the one `transfer <area> <seed>` gets. `--layout FILE` writes the layout TSV; `--runs` adds, after each `open` spot, the free cells (up to 80) along each key direction (room for a sprint). Its `wall` spots are often small obstacles the WASD walk slides along, so use `blocked` only for walls shown to stop the walk (`G1_1` 750 828 WD, 684 825 S); otherwise hold the key 1.2 s and check `max_drift`.

Grid check against the client: `modules/server/target/release/examples/grid_diff <area> <seed> <client grid .bin> [--layer L] [--at X Y [R]]` (build `cargo build --release -p poe-world --example grid_diff` in `modules/server`; run from the hub root; `POE_FORCE` as wall_probe) compares the server's generated grid with the client's `dumps/0.5.5e.hotfix1/terrain/grids/terrain_grid_<tile>.bin` per layer and prints both around a cell. `G1_8` seed 1 (tile 1819364532) is identical in all 4 layers.

Clicking a transition is not a step yet (needs R4 entities and a world-to-screen mapping).

`terrain-mismatch` ([instance.md](../protocol/instance.md#terrain-check); fake hash, kicks to the town, the previous instance, character select; popup screenshot; about 6 minutes) covers the terrain check. Scenarios `leagues` (creates Dawn through the web API, makes a character in it, ends Dawn into Standard) and `leagues-none` (no league: empty list, Create, Play) cover leagues; `ta_league` in `scripts/lib/test-accounts.sh` makes the Standard family when none exists. The first failing step ends the scenario. `scripts/game-test/overlay-settings.toml` (seed `GameFiles/logs/poe-hook/overlay.toml` with `last_page = "Settings"` and `show_slow_hook_popups = false` first; remove it after) shows the overlay, takes a snapshot screenshot (`runtime/game-test/overlay-settings.png`) and checks the file is kept (about 1.5 min). `overlay-pages.toml` (`POE_HOOK_OVERLAY_TOUR`: every overlay page with a screenshot in `runtime/game-test/overlay-pages/`; about 3 minutes) covers the layout. `scripts/game-test/smoke.toml` checks the runner itself; `scripts/game-test/state.toml` checks the state file (area and life, a 1.5 s walk with `moved`, I opens and closes the inventory, Esc the escape menu, no server errors). `scripts/game-test/walk.toml` checks the actions on the generated grid (`G1_town` seed 1: teleport, one short hold per key, two `walk_to`, a walk into a wall that stops at x 406 as the grid says, a roll at the wall, `max_drift = 5` after each). `cliffs.toml` (`G1_1` seed 1: cliffs, key holds and tap rolls into walls, the 6-cell passage at 708 1512) and `dungeon.toml` (`G1_8` seed 1: 4 key holds and 3 rolls into walls) pass the same way; `sprint-turn.toml` (`G1_1` then `G1_8` seed 1: sprints with key turns, rolls during the SprintEnd coast, a sprint into a wall; `POE_HOOK_MOVEMENT_LOG` on and `dev.movement_trace` to `runtime/game-test/sprint-turn-trace.tsv`; check it with `scripts/re/movement_gridcmp.py` ([movement.md](../protocol/movement.md#movement-trace))); `sprint-w.toml` (`G1_1` seed 1 at 621 1146: W pressed and released, also during a sprint; `max_drift = 5` after each, then `after` runs `scripts/re/sprint_check.py` on the session's packets; about 2.5 minutes; results in [movement.md](../protocol/movement.md#test-tooling)) passes too. The scenarios keep `"dev.drift_check" = true`; the generated grid is the default. The runner sets `POE_HOOK_STATE=250`, deletes the state file before launch and copies the last one to `state-final.json` in the run folder; every `expect_state` writes the state it last read to `state-last-check.json`. Code: `xtask/src/game_state.rs`, `game_test.rs`.

### Live state file
The DLL ([client-dll.md](../architecture/client-dll.md#live-state-export-state_exportrs)) writes `GameFiles/poe-hook-state.json` every 250 ms (temp file, then rename, so never half a file; deleted at DLL start). Enable with `[features] state_export` / `state_export_ms` or `POE_HOOK_STATE=1` / `=<ms>`. Fields:
- `version` (1), `seq`, `t` (unix ms), `read_only`, `frame` (player simulation frame counter).
- `area`: `{id, name, hash16, kind, tile_hash}` (`name` from `poe-hook-data/areas.tsv`) or null.
- `player`: `{id, grid [x,y], world [x,y], facing, action, action2 (ActionTypes names, "" when none), wasd [x,y], life/mana/es {current, max, reserved}}` or null. Pool offsets and the unverified parts: [addresses.md](../re/addresses.md#ui-elements-and-the-life-pools).
- `panels`: sorted paths of every UI element that is visible with all its parents, as `root/.../name`; a nameless element is `@<vtable Ghidra address>` (`root/escape_menu/escape_menu_inner`; the inventory is `root/@143167d20/@1430a3a28/...`). Only elements whose visibility went through SetVisible are known.
- `packets`: the last 40 as `{seq, t, dir, chan, op, name, len}`.

The checks on it are the `expect_state` step ([above](#game-tests-cargo-xtask-game-test)).

### `poe-hook.keys` entries
Each entry is one line; the DLL reads the file and posts the input to the game window only (nothing goes to other windows; `SendInput` is not used, because it types into whatever window has focus). Never while read-only.
- A plain virtual-key number (`0x0d`, `0x57:800` with a hold time in ms) is a posted key message. **`down:<vk>` / `up:<vk>`** post the key-down and the key-up separately (other entries run in between): the roll key's held state (`0x2e6 held=1`) follows the posted messages, so a sprint during which other keys change needs `indown:0x20 down:0x20 ... up:0x20 inup:0x20` (with a plain `0x20` the client sends `0x2e6 held=0` two frames later and only rolls). Plain keys (`0x20`, Space = dodge roll) reach the input bindings that are read from window messages. A plain `0x20` is down and up in one go, so the client's key state never reads "held" and a roll started that way is not steered (no `0x1a8`); for roll and sprint tests use `indown:0x20`, `0x20`, `wait:250`, `inup:0x20` ([movement spec](../protocol/movement.md#test-tooling)).
- **`in:<vk>[:ms]`** posts `WM_INPUT` with a marker handle. The game reads WASD through Raw Input, so posted key messages do not move the player; the DLL hooks `GetRawInputData` (user32) to return a synthetic keyboard record for that handle, and `GetKeyState` reports the key as held meanwhile.
- **`indown:<vk>` / `inup:<vk>` / `wait:<ms>`** hold and release a key while other input arrives.
- **`inmove:x,y` / `inclick:x,y`** make the hooked `GetCursorPos` return that client position, then post the mouse messages.
- **`inpress:x,y` / `inrelease:x,y`** hold and release the left button at a client position (held click-to-move); the hooked `GetKeyState` reports `VK_LBUTTON` held meanwhile.
- **`text:<chars>`** posts one `WM_CHAR` per character, for text boxes such as the character name.
- **`POE_HOOK_KEYS_FILE=<name or absolute path>`** (environment variable of the client process) makes that DLL read its input entries from another file than `GameFiles/poe-hook.keys`, so two clients on one GameFiles get one file each (`poe-hook.1.keys`, `poe-hook.2.keys` in `scripts/test-mp.sh`). The DLL logs `input file: ...` at start.
- **`0x77` (F8)** takes a game screenshot into the test prefix's `My Games/Path of Exile 2/Screenshots`, which shows the game even when its window is not visible.
- **`close`** posts `WM_CLOSE` to the game window (like its X button).
- Before each batch the DLL posts `WM_ACTIVATEAPP(1)`: the game ignores input while it thinks it is in the background, and this changes only its own flag, not the real focus.
- Click-to-move needs `user_input_mode=mouse_and_keyboard` in the test prefix's `poe2_production_Config.ini` (edit it only while the client is closed: the client rewrites it on exit). W/A/S/D move the player only with `user_input_mode=wasd` (plus `last_selected_KBM_input_mode=wasd`); `use_wasd_to_move` is a different setting and does not switch the mode. Neither mode needs the game window to be active for injected keys.

## Terrain batch generation
The DLL can run the client's terrain generator for thousands of `area seed topology orientation` jobs without a login (`[gen_batch]`), driven by `scripts/re/terrain_batch.py` (what it does: [../re/terrain/batch.md](../re/terrain/batch.md)). Private mode only; Steam must be running, no server needed; it refuses a GameFiles deployed in official mode.
```sh
python3 scripts/re/terrain_batch.py plan act1 --act 1 --seeds 50       # jobs.txt from docs/status/terrain-matrix.tsv x 50 random seeds (--area, --kind, --master-seed, --vectors, --limit)
python3 scripts/re/terrain_batch.py run act1                           # deploy-client, start the client, watch, restart after a crash, resume (--threads N --max-rss-gb 16 --restart-every N --no-deploy)
python3 scripts/re/terrain_batch.py status act1 --watch 30             # done / remaining / rate / ETA
python3 scripts/re/terrain_batch.py verify vectors                     # after `plan vectors --vectors` and `run vectors`
python3 scripts/re/terrain_batch.py stop
```
A run is `dumps/<version>/terrain/batch/<run>/` with `jobs.txt`, `batch-results.tsv` (`area seed topology orientation status tile_hash doodad_hash width height ms detail`; status ok / error / crash-skip), optional `export.txt`, `crashes.tsv`, `state.json`, `rss.tsv`. Above `--max-rss-gb` the client is restarted and the run resumes; a job that crashes the client twice is `crash-skip`. The DLL reads `POE_HOOK_GEN_BATCH=<run dir>` and `POE_HOOK_GEN_BATCH_THREADS=<n>` (or `[gen_batch]`); the script sets both.

## Logs
- Client: `GameFiles/logs/Client.txt`.
- DLL: `GameFiles/poe-hook.log`, plus a per-process session folder `GameFiles/logs/poe-hook/<date_time>_<pid>/` (logs, `packets.jsonl`, `packets.txt`, snapshots) and the in-game overlay (Insert). What the DLL logs: [../architecture/client-dll.md](../architecture/client-dll.md).
- Generated data (terrain grids and layouts, area exports, client tables) goes to `dumps/<version>/`; `scripts/dumps/migrate.sh` sorts older files there and copies packet sessions to `dumps/<version>/captures/{official,local}/`.
- Server: stdout, filtered by `RUST_LOG` or `[logging] filter`. Admin commands are also appended to `[commands] audit_log`. Unattended runs: `runtime/server-run.log`; the movement trace is `runtime/movement-trace.tsv`.
- Real play on official servers: the user's `Client.txt` in the Steam install (read only, [../../CLAUDE.md](../../CLAUDE.md)); analysis in [../re/captures.md](../re/captures.md).

## Crash reports
After a crash the client writes `PoE-<time>-<pid>.dmp` (plus `.txt`, `.log.txt` and `.poecap` side files) under `My Games/Path of Exile 2/poe2_production` in the prefix. A helper process uploads them, right after the crash and on the next launch. With `block_external` installed from `DllMain`, the upload connections are refused. `cargo xtask run-client` also moves pending dumps to `runtime/crash-dumps/` (git-ignored) before launching, so nothing is left to upload and the dumps stay available for debugging.

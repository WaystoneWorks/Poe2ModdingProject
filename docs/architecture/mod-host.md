# Server mod host

The server half of the mod system: `modules/server/crates/poe-mod-host` loads native server mods and data mods, delivers events to them, advertises the client half of mods to launchers, serves the packages and checks at login that a client runs the mods the server requires. Operator and author guide: [../guides/modding.md](../guides/modding.md). The mod ABI and SDK live in [Poe2ModSDK](https://github.com/WaystoneWorks/Poe2ModSDK); manifest, `state.toml`, plan logic and package verification are `modules/client-hook/poe-hook-mods`, shared with the client hook and the launcher.

```
poe-server ── ModHost::load ──► mods/ (state.toml, <id>/, packages/)      modules/server/crates/poe-mod-host
   │                               │ plan (poe-hook-mods) → libloading → poe_server_mod_init(ServerApi)
   │                               ▼
   ├─ instance-server ── actors ── dispatch(Event + read-only snapshot) ──► mod callbacks
   │      │  └─ applies the submitted commands on the actor task (teleport) or through ModSink (chat, kick)
   │      └─ login: compare the hook's mod report with ModHost::required()   → check_client
   └─ poe-web-api ── ModDirectory (poe-cluster trait) ──► GET /server `mods`, GET /mods/{id}/{version}.zip, GET /admin/mods
```

## The mods folder

`[mods] dir` (default `mods`, relative to the working directory):

```
mods/
  state.toml              enabled = ["hello-both", "motd"]    the enabled mods in load order
  hello-both/mod.toml …   the installed mod (what the server loads and hashes)
  packages/
    hello-both-0.1.0.zip       what clients download; verified at every start
    hello-both-0.1.0.zip.sha256
```

- **`state.toml` turns the mod system on.** Without it nothing is loaded and the login check is off. `poe-server mod enable <id>` creates it.
- A mod is a folder `mods/<id>/` with a valid `mod.toml` (folder name = id). A zip in `mods/` or `mods/packages/` is verified (`verify_package_bytes`: name `<id>-<version>.zip`, hash against the `.sha256` sidecar if present, paths, limits) and counts as that mod's package. `poe-server mod install <zip>` verifies, unpacks into `mods/<id>/` (replacing an installed version) and copies the zip to `packages/`; it does not enable.
- A mod with a client half needs a package to offer. If none matches the folder (same id, version and `mod.toml` hash), the host **packs the folder** deterministically (sorted entries, fixed timestamp and permissions) into `packages/` and logs it; a stale package is replaced the same way, since the folder is what the server runs and the login check hashes.
- Every change (state, install, new folder) needs a restart; mods are never unloaded or reloaded. `GET /api/v1/admin/mods` compares the folder with what was loaded and reports `restart_required`.

## Load plan

For each id in `state.toml`, in order (`ModHost::plan`):

1. The folder must exist with a valid manifest. A mod failing any step is skipped with one log line (`mods: skipped <id>: <why>`) and a `skipped` row in the admin list; the server keeps starting.
2. **Server side** (`side` server or both): `game.versions`, when stated, must contain `[game] version` (a refusal on the server; the client loader only warns); `check_server_api` against `SERVER_API_VERSION` (newer: "update the server", older: "rebuild the mod", a library without `server_api`: refused); dependencies and conflicts via `LoadSet` (a `both` mod may depend on a client-only mod, a server-only mod may not).
3. **Client half** (`side` client or both): the entry DLL and the package must be available; the mod joins `required()`.
4. **Native library**: the platform file from `[server.library]` (`.so` on Linux, `.dll` on Windows); missing for this platform: skipped. `libloading` maps it, `poe_server_mod_abi_version` must equal `SERVER_API_VERSION` (checked before anything else is called), then `poe_server_mod_init(&ServerApi, &mut ModInfo)` runs. A non-zero return unmaps the library and skips the mod. A started mod is never unloaded.
5. **Data tier**: `[[commands]]` are registered next to native ones; `[server] tables` directories go to `GameFiles::push_override` in load order (done by `poe-server` before the game data is shared); `config_defaults` and server `opcodes` are parsed but not applied (logged).

Command names are unique: the server's own commands win (`commands::reserved_names`: the first path word of every built-in command and every alias, e.g. `instance`, `tp`, `transfer`), then the earlier mod; a clash makes a native `register_command` return `ERR_EXISTS` (`hello-both` and `hello-server` both register `!hello` and cannot be enabled together) and drops a data-tier duplicate with a log line.

## ServerApi and callbacks

`ServerApi` is the table of C functions of `poe-mod-api` (version 1): `log` (target `mod`, field `mod_id`), `config_get` (a key of `[mods.config.<id>]` as text; strings as they are, other values as TOML), `register_command` (only during init), `submit` (only inside a callback, with that callback's `scope`). All input from a mod is untrusted: null pointers, non-UTF-8 or over-long text, a `size` shorter than the struct (copied by the mod's own size), unknown command kinds, NaN coordinates, a scope that is not the calling thread's running callback, more than 64 queued commands per callback or 32 registered commands per mod all give an error code, never a panic.

Events (`EVENT_*`, delivered to mods whose `event_mask` has the bit; `EVENT_COMMAND` always to the command's owner):

| Event | Where it is raised | Snapshot |
|---|---|---|
| `SERVER_START` / `SERVER_STOP` | `poe-server`: before serving / when a stop or restart begins (players still online) | none |
| `PLAYER_JOIN` / `PLAYER_LEAVE` | the instance actor, when a session joins or leaves | the instance after the join / without the leaver |
| `COMMAND` | the actor of the caller's instance, on `Cmd::ModCommand` | the instance, caller as `player` |
| `INSTANCE_CREATED` / `INSTANCE_CLOSED` | the actor starts / ends (starts with the first player, ends when the instance is closed or idle) | none |
| `TICK` | the actor, after each simulation frame, only when some mod subscribed | the instance |

Callbacks run on the thread that raised the event, so callbacks of one instance never overlap and different instances run concurrently (`COMMAND` callbacks run on the actor too, stricter than the ABI requires). A snapshot (`InstanceSnap`) is plain data copied for the call; a mod never sees the `World`.

**Commands a mod submits** go back to the code that raised the event (`ModHost::dispatch` returns `Vec<Submitted>`), which applies them after the callback returned: `Teleport` on the actor task (`World::teleport`, carried out by the next frame like the admin's `teleport`), `SendChat`/`Broadcast`/`Kick` through the `ModSink` trait (`LiveSink`: the live session registry; a kick first shows its reason). A command for a player who is gone is dropped with a debug line. Player ids are session ids (`PlayerInfo::id`).

**Failure handling.** A Rust panic inside a mod aborts the process unless the SDK contains it (it does, and logs); the host cannot catch an abort. A callback that returns anything but `EVENT_CONTINUE`/`EVENT_CONSUMED`, or runs longer than `[mods] callback_budget_ms`, counts as a failure (logged); `[mods] max_failures` failures in a row disable the mod until the next start (`failed` in the admin list); a success resets the count. Disabled mods get no more events. `shutdown` callbacks run once at server stop, after the drain.

## Commands in the registry

`instance-server/src/commands.rs` keeps the compile-time list of server commands and, after `install_mod_commands` (once at startup, before anything serves), a list of mod commands (`Extra`: a leaked `Spec`, the mod id and a `CommandAction`). `find`, `parse`, `all` and the overlay's registry lines use both, so a mod command appears in chat, `!help`, the overlay (category Mods, Debug > Help) and the role check (`admin` for `role = "admin"`) like a built-in. A mod command has one argument, the rest of the line (`args`).

- `Reply(text)`: sends the text back (`{player}`, `{args}` filled in).
- `Alias(line)`: runs another command line as the caller, parsed and role-checked like a typed command; aliases nest at most 4 deep.
- `Native`: sent to the actor as `Cmd::ModCommand`; the mod answers with `submit(SendChat)`, so the command's own outcome is empty and the session sends no chat line.

Mod commands need a game session (not offered through `AdminControl` or the web API's command endpoint).

## Advertisement and downloads

`ModHost` implements `poe_cluster::ModDirectory`, used by `poe-web-api` (`WebState::mods`):

- `GET /api/v1/server` gets an optional `mods` array: every enabled mod with side `client` or `both` that loaded (server-only mods are not listed), with `id`, `name`, `version`, `side`, `sha256` and `size` of the package, `required` (always `true`), `hook_api`, `game_versions`, `code` (the client half has a DLL), `authors`, `description` and `sources`: first `{"type":"server","path":"/api/v1/mods/{id}/{version}.zip"}`, then one `{"type":"url","url":…}` per `[mods] extra_urls` (`{id}` and `{version}` replaced). Absent when there is nothing to offer. A router test (`tests_mods.rs`) pins the shape because the launcher parses it.
- `GET /api/v1/mods/{id}/{version}.zip` serves the package whose hash was verified at startup; it compares the hash again before sending, so a file replaced on disk is not served (`404`, logged). Public, `Content-Type: application/zip`, `ETag` = the SHA-256 (`If-None-Match` answers `304`), `Cache-Control: public, max-age=3600`. Server-only mods and unknown versions are `404`.
- `GET /api/v1/admin/mods` (admin): every mod with `state` (`loaded`, `skipped`, `failed`, `installed`), the reason, its commands, `restart_required` and the two check options. Shown on the web admin's Mods page.

## The login check of the client's mods

| Part | Where |
|---|---|
| The report: id, version, SHA-256 of `mod.toml` and of the entry DLL of every loaded client mod | `poe_hook_shared::modreport` (client-hook), built by the hook loader (`poe-hook/src/mods.rs`), handed to the core through `HostApi::mod_report` (core ABI 3) |
| The transport: side-channel frame `Kind::ModReport` (6), TCP on the instance port with the `PSUP` framing, sealed with the session keys, answered with `PSUR` status 0 | `poe-hook-core/src/side.rs`, `modules/server/servers/instance-server/src/{terrain_store,sync}.rs`; [../protocol/side-channel.md](../protocol/side-channel.md#mod-report) |
| The comparison | `poe_mod_host::check_client(required, allow_extra, report)` (pure, unit-tested) |
| Where it is acted on | `InstanceServer::handle`: the server waits up to `[mods] report_wait_secs` for the report (it arrives while the terrain is generated), joins the instance, enters the world, sends the refusal as server chat lines, waits 8 seconds so the client can show them, and ends the session before the player is registered as online |

**Rules.** The check is active when `[mods] require_client_mods = true` and `<mods dir>/state.toml` exists. The required set is the loaded mods with a client half. A required mod that is missing, has another version, or the right version with a different `mod.toml` or DLL hash refuses the login; so does a reported mod that is not required unless `allow_extra_client_mods = true`. A client that sends no report (an old hook) is refused when the server requires mods and allowed when it requires none (with `allow_extra_client_mods = false` and an empty required set the server waits for a report and refuses extras only if one arrives). The message lists what is wrong and what the server needs; the refusal is logged (`login refused: the client's mods do not match this server's`).

The installed `mod.toml` hash equals the package's only if the installer copies the file unchanged; the launcher's installer (it unpacks the zip) and `poe-server mod install` do.

## Pin consistency

- `poe-hook-mods` (manifest v2, plan logic, package verification): a **path dependency through the client-hook submodule** (`modules/client-hook/poe-hook-mods`), so server, launcher and hook share one parser at the commit the submodule pins. The SDK pins the same crate by git commit; the e2e test `modules/server/crates/poe-mod-host/tests/sdk_hello.rs` loads a library built with the SDK's pin and fails on a manifest disagreement.
- `poe-mod-api` (the server ABI): a **git dependency pinned to the SDK's `v0.1.0` tag** (workspace `Cargo.toml`), so there is one definition of the ABI, reviewed in the SDK, and moving to another version is a visible one-line change. Since a tag could be moved, `ffi.rs` repeats the pinned struct sizes in a test (`the_abi_layout_matches_what_this_host_was_written_for`), and the host refuses a library whose `poe_server_mod_abi_version` differs from `SERVER_API_VERSION` before calling anything else. When the SDK bumps `SERVER_API_VERSION`, change the tag and the host's code together.

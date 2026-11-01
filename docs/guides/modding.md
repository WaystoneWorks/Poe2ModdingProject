# Modding

One mod system for client and server: a mod is **one package** with a `mod.toml` that says where it runs (`side = "client" | "server" | "both"`), built and packed with the public SDK. Native Rust server mods (a `cdylib` with a versioned C ABI) plus data-only mods; never hot-reloaded, no install guard, exact version and SHA-256 pinning.

## What exists

| | State |
|---|---|
| Client mods (DLL loaded by the hook), launcher cache/enable/order per server | Exists (manifest v1 and v2) |
| Manifest v2: `side`, `[client]`, `[server]`, `[[commands]]`, fail-closed for old readers, shared parser | Exists (`modules/client-hook/poe-hook-mods`) |
| Package `<id>-<version>.zip` + `.sha256`, reproducible packer, verification | Exists (`poe-mod pack/verify`, `poe_hook_mods::verify_package`) |
| Server mod ABI (`poe-mod-api`), wrappers (`poe-mod-sdk`), templates, examples, `poe-mod` tool | Exists (SDK repository) |
| Client loader refusing a server-only mod and ignoring the server half of a `both` mod | Exists |
| Server loader for native and data mods (`mods/`, `state.toml`, events, commands, `[mods]` config, `poe-server mod` CLI) | Exists (`modules/server/crates/poe-mod-host`, [mod-host.md](../architecture/mod-host.md)) |
| Server advertising its client mods (`GET /api/v1/server` field `mods`, `GET /api/v1/mods/{id}/{version}.zip`) and checking client mods at login | Exists |
| Launcher mod sync (per-server sets, Off / Ask / Auto, versioned cache, SHA-256 and `verify_package` checks), side badges, mod browser (`Poe2Mods` index, [template](../mod-index-template/README.md)) | Exists |
| Server `[data]` table overlays (`push_override`) and `[[commands]]` from mods | Exists; `config_defaults` and server `opcodes` are parsed but **not applied** (logged) |
| Client `[data]` overlays, ed25519 signatures | Later |

## Sides

| `side` | Contains | Loaded by |
|---|---|---|
| `client` | a DLL for the game process and/or client data (v1 manifests are always this) | the client hook (`poe-hook-mods/<id>/`) |
| `server` | a native library per platform (`.so` / `.dll`), game-data overlays, config defaults and/or `[[commands]]` | the server (`mods/<id>/`) |
| `both` | one package with both halves | both; the hook ignores the server half |

`manifest_version = 2` is required for `server` and `both` (and for `[client]`/`[server]`/`[[commands]]`); a v1-only reader refuses such a manifest ("fail closed"), so a server-only mod is never mistaken for a client mod. Client-only mods can stay v1. Spec: [../../modules/client-hook/docs/mod-manifest.md](../../modules/client-hook/docs/mod-manifest.md).

## Packaging

`<id>-<version>.zip` with `mod.toml` at the root plus the files it names (conventionally `client/`, `server/`, `data/`), and `<id>-<version>.zip.sha256`; the zip's SHA-256 is the package identity. `poe-mod pack` writes it reproducibly (sorted entries, fixed timestamp and permissions); `poe-mod verify` and `poe_hook_mods::verify_package` check hash, name, manifest, named files, path hygiene, symlinks, encryption, duplicates, size limits and CRCs. Details: the SDK's [docs/packaging.md](https://github.com/WaystoneWorks/Poe2ModSDK/blob/main/docs/packaging.md).

## The SDK repository

[github.com/WaystoneWorks/Poe2ModSDK](https://github.com/WaystoneWorks/Poe2ModSDK) (public, MIT; local clone `third_party/Poe2ModSDK`, git-ignored):

- `poe-mod-api`: the server mod C ABI, `SERVER_API_VERSION = 1`. `ServerApi` (log, config, command registration, submit), `ModInfo`, events with read-only snapshots (server start/stop, player join/leave, command, instance created/closed, tick) and commands the mod returns (send chat, broadcast, teleport, kick), applied on the owning actor task. Rules: [abi-stability.md](https://github.com/WaystoneWorks/Poe2ModSDK/blob/main/docs/abi-stability.md).
- `poe-mod-sdk`: `ServerMod` + `declare_server_mod!`; `declare_client_mod!` with the hook's `HookApi` re-exported.
- `poe-mod-cli` (`poe-mod`): `new client|server|both`, `check`, `pack`, `verify`.
- `examples/`: `hello-client`, `hello-server` (`!hello`), `hello-both`.

The SDK takes the client ABI crate and manifest parser from `Poe2ClientHook` as git dependencies pinned to a commit. The server loader (`modules/server/crates/poe-mod-host`) uses the same `poe-hook-mods` crate through the client-hook submodule and the SDK's `poe-mod-api` as a git dependency pinned to `v0.1.0` ([why](../architecture/mod-host.md#pin-consistency)). Guides: [writing-server-mods.md](https://github.com/WaystoneWorks/Poe2ModSDK/blob/main/docs/writing-server-mods.md), [writing-client-mods.md](https://github.com/WaystoneWorks/Poe2ModSDK/blob/main/docs/writing-client-mods.md).

## Server

- **Data-driven content:** server logic reads game tables by column name, so modified tables flow through without code changes.
- **Data mods (no code):** a server mod with only `[[commands]]` (a `reply` text or an `alias` of another command, `role` player or admin) and/or `[server] tables = [...]` folders. Table folders are pushed with `poe_data::GameFiles::push_override` in load order (`<folder>/<virtual path>` replaces the bundled file, later mods win) before the server shares its game data; a table the client also reads makes the mod `both` (the client half of an overlay is not applied).
- **Native server mods:** every mod in `mods/` enabled in `state.toml` is loaded; the owner is responsible. The server API version and game version are still checked; a refused mod is a log line and the server keeps starting. Changes need a restart. Authors: the SDK guides. Design: [mod-host.md](../architecture/mod-host.md).
- **Server commands:** one registry (`modules/server/servers/instance-server/src/commands.rs`, run by `exec.rs`) of built-ins plus mod-registered commands; a command works in chat (`!name`) and in the overlay's Commands page ([server-admin.md](server-admin.md)) and takes the rest of the line as its argument.

### Running server mods

```sh
poe-server mod install hello-both-0.1.0.zip --enable   # verify, unpack into mods/hello-both/, enable
poe-server mod list                                    # id, version, side, enabled
poe-server mod disable hello-both                      # edits mods/state.toml
poe-server mod verify                                  # packages, manifests, libraries; exit code 1 on errors
```

- **Layout** (`[mods] dir`, default `mods`): `state.toml` (`enabled = [...]`, the load order; **its existence turns the mod system and the login check on**), `<id>/` folders, `packages/<id>-<version>.zip` (+ `.sha256`) for mods with a client half. A zip dropped into `mods/` or `packages/` is verified and used as that mod's package. A mod with a client half but no package is packed from its folder at start. A mod's installed `mod.toml` must be the one in its package (install does this).
- **At start** each enabled mod is checked and loaded in order; the log shows `mods: loaded <id> <version> ...` or `mods: skipped <id>: <reason>` (wrong `server_api`, another game version, no library for this OS, missing or conflicting dependency, `poe_server_mod_init` error, taken command name). A server library is mapped only after its manifest passed.
- **Config** `[mods]` in `modules/server/config/server.toml` (all keys in `server.example.toml`): `dir`; `require_client_mods` (default `true`: check the client's mods at login); `allow_extra_client_mods` (default `false`: a client mod the server does not list refuses the login); `extra_urls` (more download addresses for every offered mod, `{id}` and `{version}` replaced); `report_wait_secs` (15), `max_failures` (5), `callback_budget_ms` (50); per-mod settings under `[mods.config.<id>]`, read by the mod as text with `config_get`.
- **What clients see.** `GET /api/v1/server` lists the enabled client and `both` mods that loaded (id, version, SHA-256 and size of the package, `required`, `hook_api`, `game_versions`, `code`, `sources`); `GET /api/v1/mods/{id}/{version}.zip` serves the exact package ([web-api.md](../architecture/web-api.md#mods)). The launcher compares, downloads and verifies them per its *Mod sync* setting.
- **The login check.** When a player enters the world, the server compares the client mods the hook reports with the required set. On missing mods, other versions, a changed `mod.toml` or DLL, or (without `allow_extra_client_mods`) unlisted mods, the player gets server chat lines naming the problem and is disconnected a few seconds later; the log has `login refused: the client's mods do not match this server's`. An old hook that sends no report is refused when the server requires mods and allowed when it requires none. This is a consistency check, not anti-cheat. The hook sends the report only to your own (trusted) server, never in official mode. To forbid all client mods, create an empty `mods/state.toml` and keep `allow_extra_client_mods = false`; a development server whose players run their own client mods needs `allow_extra_client_mods = true` (or no `state.toml`).
- **Web admin:** the Mods page lists every mod with its state and says when a restart is needed ([server-admin.md](server-admin.md#mods)).
- **Trust.** A native server mod runs inside the server process with its rights and can read the database and all account data: install only mods you trust. A mod crash takes the server down (the SDK contains panics, not aborts or segfaults).

## Client

- **Debug core:** `modules/client-hook/poe-hook-core` is hot-reloadable (a running client reloads a redeployed core, see [setup.md](setup.md)); its features are toggled in `poe-hook.toml` ([../architecture/client-dll.md](../architecture/client-dll.md)). The loader (`modules/client-hook/poe-hook`) keeps the permanent hooks.
- **Mod loader:** a client mod is a folder `poe-hook-mods/<id>/` next to `PathOfExileSteam.exe` with a `mod.toml`; `poe-hook-mods/state.toml` lists the enabled ids in load order. The launcher keeps a cache of verified packages, switches them per server (required mods are downloaded per the *Mod sync* setting) and writes the set into `poe-hook-mods/` at Play ([launcher.md](launcher.md#mods)). The loader in `version.dll` maps the enabled entry DLLs in order and calls `poe_mod_init(&HookApi)` (a logging callback, the game build, the read-only latch, the resolved signature table). A mod with another ABI version, a missing dependency or a failing init is logged and skipped; a server-only mod is skipped with "server-only mod"; the server half of a `both` mod is ignored; **in official mode no mod loads**. Format, ABI, log lines: [mod-manifest.md](../../modules/client-hook/docs/mod-manifest.md); sample mod `modules/client-hook/examples/sample-mod/` (manifest v1).
- **Launcher:** Library, Mods shows each mod's side, refuses a server-only mod and installs only the client half of a `both` package; each server has its own mod set; the mod browser reads the public index (submit by pull request: [../mod-index-template/README.md](../mod-index-template/README.md)). Details: [launcher.md](launcher.md#mods).
- **Install from the repository:** `cargo xtask deploy-mod [dir]` (default: the sample mod; `--dll`, `--disable`, `--no-build`) or `cargo xtask deploy-client --sample-mod` put a mod into `GameFiles/poe-hook-mods/<id>/` and enable it through `poe-hook-deploy` (a server-only mod is refused; of a `both` mod only the client half is installed); `revert-client` removes what these installed. Never copy into GameFiles by hand.
- **Trust.** A client mod is native code running in the game process with your user's rights. Install only mods from sources you trust. The launcher checks a mod's manifest and paths, not what its code does; a package hash proves which file it is, not that it is safe.
- **Planned:** applying a mod's `[data]` overlays (game tables, opcodes, config defaults), a loose-file override hook for replacement assets, packet hooks for custom messages.

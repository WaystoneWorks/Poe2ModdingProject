# Client and install guide

How a player gets the game client onto a private server of this project: through the launcher, or by hand with `cargo xtask` on Linux (Proton) or Windows. Running a server for others: [hosting.md](../../modules/server/docs/hosting.md). Developer commands: [setup.md](setup.md).

**Unofficial.** This project is not affiliated with or endorsed by Grinding Gear Games. No game files are distributed: you need your own legal copy of Path of Exile 2 on the supported build (**0.5.5e Hotfix 1**; build and executable checksum in `modules/protocol/versions/0.5.5e.hotfix1.toml`). The client hook is a DLL loaded into the game; the anti-cheat may detect it. Use it only for the private server and never on an account you care about; to observe an official session read [official-mode.md](official-mode.md) first ([overview](#going-back-to-the-official-game)). See the [disclaimer](../../README.md#disclaimer).

## What gets installed

| Piece | What it is | Where |
|---|---|---|
| The game (0.5.5e Hotfix 1) | Your own copy of the client files | a folder you choose, never Steam's own install folder |
| `version.dll` | The hook loader (our `poe_hook.dll`), plus `poe_hook_core.dll` (features and overlay) | next to `PathOfExileSteam.exe` |
| `poe-hook.toml` | Hook config: mode, login mode, trusted servers | next to the exe |
| `gateway_list.txt` | Realm list, replaced by one entry pointing at your server (original kept as `gateway_list.txt.orig`) | next to the exe |
| `steam_appid.txt` | Makes the Steam API start as Path of Exile 2 | next to the exe |
| a login token (optional) | Your saved login (Remember Me) | the Documents folder of the game's prefix/profile |

Everything the deploy changes is inside the game copy; `cargo xtask revert-client` and the launcher's uninstall put it back.

## Option 1: through the launcher (recommended)

The launcher downloads client 0.5.5e Hotfix 1 from Steam with your own Steam login into its own folder, installs the hook, writes the config for the server you pick and starts the game at its login screen. Launcher install, update, one-time set-up (Linux keyring, Proton) and the flow: [launcher.md](launcher.md).

1. Get the launcher: Linux AppImage or Windows installer from the Poe2Launcher releases ([launcher.md](launcher.md#download-install-and-update)).
2. **Servers**: add your server's web API address (from the server owner, for example `https://play.example.org`) and select it.
3. **Install**: enter your Steam account (about 150 GB; Steam Guard asks for a code), wait for verification.
4. **Play**, then sign in on the game's own login screen. On Linux, Steam must be running and a Proton installed (default "Proton - Experimental").

The launcher never touches your real Steam install of Path of Exile 2 and never plays on official servers.

## Option 2: by hand (`cargo xtask`)

For developers. You need a hub checkout with submodules ([setup.md](setup.md#clone)), the tools ([setup.md](setup.md#tools)) and a copy of the game files.

### The game files

Copy a complete 0.5.5e Hotfix 1 install into `GameFiles/` (the folder with `PathOfExileSteam.exe` and `Bundles2`). Copy it, never point the tooling at Steam's folder: the deploy replaces `gateway_list.txt` and adds DLLs, which would change your real install. The copy must match the server's `[game] version`. Git ignores `GameFiles/`.

### Linux (Proton)

Requirements: Steam running (else the client exits with `Unable to init Steam API`), Proton Experimental installed through Steam, `rustup` (the pinned toolchain installs on first build), clang and lld for the Windows cross build.

```sh
third_party/fetch-tools.sh                  # once: tools, cargo-xwin, the pinned toolchain
cargo xtask build-dll                       # the hook DLLs for the Windows target
cargo xtask deploy-client --no-build        # gateway entry, version.dll, poe-hook.toml; reads [network] public_host and the ports from modules/server/config/server.toml
cargo xtask run-client                      # starts the game through Proton in its own prefix (third_party/proton-prefix)
```

`deploy-client` reads the server address and ports from the config it is given: for someone else's server, copy their `modules/server/config/server.example.toml` values into a config of your own (only `[network]` and `[gateway]` matter) and pass `--config <file>` (or `POE_CONFIG=<file>`), as [hosting.md](../../modules/server/docs/hosting.md#what-a-remote-player-needs) says. The default login is the account name and password screen (`--login-mode standalone`); a development server using the Steam machine-hash login deploys with `--login-mode steam` ([setup.md](setup.md#developer-config)). `cargo xtask revert-client` restores the original files.

To start from Steam instead (overlay, controller), add `GameFiles/PathOfExileSteam.exe` as a non-Steam game with the launch options from [setup.md](setup.md#playing-from-steam-non-steam-game-shortcut).

### Windows

The launcher is the supported way. A manual install **has not been tested on Windows yet**:

1. Build the DLLs with the pinned toolchain (`rustup`, MSVC build tools): in `modules/client-hook`, `cargo build --release -p poe-hook -p poe-hook-core --target x86_64-pc-windows-msvc`. Output: `target/x86_64-pc-windows-msvc/release/poe_hook.dll` and `poe_hook_core.dll`.
2. Copy your game folder somewhere (not the Steam library). Copy `poe_hook.dll` as `version.dll` and `poe_hook_core.dll` next to `PathOfExileSteam.exe`, and `modules/client-hook/poe-hook/poe-hook.toml` as `poe-hook.toml`.
3. In `poe-hook.toml` set `mode = "private"`, `login_mode = "standalone"` and `trusted_servers = ["<server host>:<login port>", "<server host>:<instance port>"]` (IPv4 literals). In `gateway_list.txt` (UTF-16 little endian) keep one line for your server in the original's format; keep the original as `gateway_list.txt.orig`.
4. Create `steam_appid.txt` containing `2694490`, make sure Steam is running, start `PathOfExileSteam.exe`.

`poe-hook-deploy` (behind `cargo xtask deploy-client`) writes exactly these files and also builds on Windows; running it there is the likely shortcut, untried.

## First start

1. The login screen shows your realm (the server's `[gateway] display_name`, e.g. "Local Server"). With the default `standalone` login you see the account name and password screen. Sign in with the account the server owner made for you; **Remember Me** works.
2. Create a character and play. The server offers the classes, areas and leagues from its game tables; characters and items are not shared with official servers.
3. Controls follow the game's options: WASD input mode for WASD, mouse input mode for click to move.
4. **Insert** shows and hides the hook's overlay. Admin server commands start with `!` in chat ([server-admin.md](server-admin.md)). **F8** saves a screenshot into the profile's `Screenshots` folder.

## Updating

- **The game.** The private server works only with the build it supports. Do not update Steam's copy; wait for a server release and a launcher that name the new build ([new-game-version.md](new-game-version.md)). The launcher installs the build the server needs.
- **The hook.** After rebuilding or updating the DLLs run `cargo xtask deploy-client` again (the launcher does it on every Play). Edits in `poe-hook.toml` survive deploys.

## Going back to the official game

A client deployed for a private server refuses connections to anything but loopback and your server (`block_external`), so it cannot reach official services by accident, and cannot play the official game. For that use Steam's own untouched install. To remove the hook from a copy: `cargo xtask revert-client` (by hand: delete `version.dll`, `poe_hook_core.dll`, `poe-hook.toml`, `steam_appid.txt` and rename `gateway_list.txt.orig` back; the launcher's uninstall does it).

The `--official` mode lets the hook *observe* an official session (it sends and changes nothing but patches game code in memory, which the anti-cheat may detect): [official-mode.md](official-mode.md).

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| The client exits at once, log says `Unable to init Steam API` | Steam is not running | Start Steam first |
| Login screen shows the official realms, or the client never contacts the server | `gateway_list.txt` not replaced, or an earlier realm remembered | Deploy again; `cargo xtask select-gateway` resets the remembered gateway (Proton prefix); check `gateway_list.txt` |
| "There has been a patch that you need to update to" | The server does not know your executable (another build) | Use the build the server names; the owner can allow unknown builds ([hosting.md](../../modules/server/docs/hosting.md#troubleshooting)) |
| Steam login instead of account and password | `login_mode = "steam"` in `poe-hook.toml` | Set `login_mode = "standalone"` or deploy without `--login-mode steam` |
| Account does not exist / wrong password | No account yet, or a typo | Ask the server owner; too many failures lock the account for a few minutes |
| Stuck on the loading screen, or a freeze right after entering | Port 6112 (TCP) unreachable, or the server lacks the area's layout | Tell the server owner; [hosting.md](../../modules/server/docs/hosting.md#troubleshooting) |
| The game crashes | Many | Logs: `GameFiles/poe-hook.log`, `GameFiles/logs/poe-hook/<session>/`, `logs/Client.txt`; `run-client` moves crash dumps to `runtime/crash-dumps/` ([setup.md](setup.md#logs), [crash reports](setup.md#crash-reports)). Never attach captures or logs with passwords to a public issue |

For anything else open an issue with your OS, client build, server release and the logs, after removing account names, tokens and passwords.

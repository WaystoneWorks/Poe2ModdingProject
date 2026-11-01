# Server commands, admins and instances

## Commands

One registry (`modules/server/servers/instance-server/src/commands.rs`) defines every server command: name, group, whether it needs an admin, typed arguments and help. The same commands work in two places:

- **Chat**: `!name args` (prefix `[commands] prefix`; `/` stays with the client's own commands). Replies come back as chat lines from `<Server>`.
- **Overlay**: the DLL's Commands page builds a form per command from the registry, which the server sends over the authenticated debug link (`cmds` lines in debug frames; the overlay asks with a `registry` command frame, [../protocol/side-channel.md](../protocol/side-channel.md)). Results arrive as `ack` lines. New registry commands show up by themselves.

Execution is in `exec.rs` (`InstanceServer::run_command`). Admin commands need the **admin role** (checked when the command runs; see Accounts below) and are appended to `[commands] audit_log` (`unix ms, account, command, result`; passwords written as `***`).

| Command | Admin | What it does |
|---|---|---|
| `help [command]` | | the command list, or one command's usage |
| `where` | | your instance, area, seed and cell |
| `who` | yes | online players and their instances |
| `kick <player>` | yes | disconnects a player |
| `mute <player> [minutes]` / `unmute <player>` | yes | stops / restores a player's chat |
| `announce <message>` | yes | a `<Server>` chat line to everyone |
| `instances` | yes | every instance (id, area, seed, layout, players) |
| `instance_new <area> [seed] [topology] [orientation]` | yes | creates an instance without entering it |
| `transfer <area> [seed] [topology] [orientation]` | yes | creates an instance and moves you into it |
| `join <instance>` | yes | moves you into an existing instance |
| `close <instance>` | yes | closes an instance; its players are disconnected |
| `teleport <x> <y>` | yes | moves you to a grid cell |
| `account <action> [name] [value]` | yes | accounts, see below |
| `terrain` | yes | generates this instance's terrain on the server and logs the comparison |
| `area_info <area> <seed>` | yes | research: a second AreaInfo on the connection (the client may crash) |

`seed` takes `random` (the server picks); `topology` and `orientation` take `natural` (the client's own choice; with `[terrain] force_layout`, the default, the server computes that choice and sends it). Any area in `WorldAreas` works. Topology numbers are 1-based in the area's topology list; orientations are checked against that topology's allowed ones.

## Terrain switches (`[terrain]`)

- `force_layout` (default `true`): every new instance's AreaInfo forces the layout (`map_force_topology`, `map_force_orientation`). What the instance does not force itself is the server generator's natural choice (`poe_world::area::choose_layout`), which is the client's own (ported from the client's world-map pin directions; 4,173 of 4,173 unforced client generations match: [../re/terrain/shared-passes.md](../re/terrain/shared-passes.md)). Forcing makes client and server agree by construction; the log line `forcing the layout (AreaInfo stats)` shows the values. `false`: only what the instance forces is sent and the client chooses the rest alone.
- `generate` (default `true`): the server also generates each new instance's terrain (in the background, a few hundred ms per area in a release build) and logs `server terrain matches the client` or the warning `server terrain differs from the client` (the `terrain` command does it for one instance). Coverage: [../status/terrain.md](../status/terrain.md#results).
- `generated_grid` (default `false`): the collision grid (walkability for movement and spawns) comes from the server's generator instead of the grid the client uploaded or the layout cache holds. Applies only when the server's tile hash equals the client's; otherwise the log says `generated collision grid unavailable` and the uploaded grid is used, so leaving it on is safe. When used the log has `using the generated collision grid` with the generation time. Grid construction and accuracy: [../re/terrain/doodads.md](../re/terrain/doodads.md); where it plugs in: [../architecture/instance-world.md](../architecture/instance-world.md#terrain-grid-sources).

## Mods

Server mods are managed offline with `poe-server mod` (the server need not run; changes apply at the next start):

```
poe-server mod list                      the mods folder ([mods] dir) and what is enabled
poe-server mod install <zip> [--enable]  verify a package (hash, names, paths) and install it
poe-server mod enable <id> | disable <id>
poe-server mod verify                    check packages, manifests and libraries without starting
```

The web admin's **Mods** page (`GET /api/v1/admin/mods`) shows every mod with its state (`loaded`, `skipped` with the reason, `failed`, `installed`), the chat commands it added, and a **Restart required** notice when the folder changed after start. Mod commands show up in `!help` and the overlay like built-ins. The `[mods]` options are in [modding.md](modding.md#running-server-mods). A player whose client mods do not match is refused with a list of what is missing; the log has `login refused: the client's mods do not match`.

## Web API

The same commands are available over HTTP for the web admin: `kick`, `mute`/`unmute`, `announce`, instance create/close, player transfer and the `account` actions are `poe-web-api` endpoints that run the registry command as the logged-in web admin (role checked at the time, audit lines tagged `<admin> (web)`, passwords redacted). Endpoints, authentication, live log: [../architecture/web-api.md](../architecture/web-api.md). In short: make an admin offline ([setup.md](setup.md#accounts-and-characters-offline)), start `poe-server`, `POST /api/v1/login` on `[web] bind` (default `127.0.0.1:8080`), send the token as `Authorization: Bearer`. `[accounts] open_registration = true` lets `POST /api/v1/register` create player accounts (the web admin's public page `#/register`, also opened by the launcher and the game's *Create account* button); admins create accounts in the web admin (*Accounts*, *New account*) and the server commands always can. A server without any account lets the computer it runs on create the first admin in the web admin (*Welcome* page, `POST /api/v1/setup`); the launcher's hosted servers use that instead of asking for a password.

## Web admin

A browser UI for the same commands in the launcher's look (shared "Ash & Blood" design tokens, dark or light parchment theme, grouped sidebar, bottom tab bar on narrow screens). The sidebar has the server's name and status light, then **Dashboard**; **People**: players (online list with kick, mute, transfer and ban, and the ban list), accounts, characters; **World**: instances, scheduled tasks; **Advanced** (folded; stays open if you leave it so, and opens on its pages): live logs, the config editor, mods. At its foot: **Announce...**, your account, the theme switch and Sign out. The dashboard shows players online, instances and client version, *Online now* and *Busiest instances*, then the server control, message of the day, server details and live charts. It is the Svelte app in `modules/web-admin` (Poe2WebAdmin); build details: [../architecture/web-api.md](../architecture/web-api.md#the-web-admin-spa).

Build it, point `[web] static_dir` at `modules/web-admin/dist`, restart `poe-server` and open <http://127.0.0.1:8080> (the `[web] bind` address): [setup.md](setup.md#web-admin-build). Only `admin` accounts get in ([setup.md](setup.md#accounts-and-characters-offline)); the session lasts 12 hours. The moon/sun button switches the theme (saved in the browser; the system preference decides until you choose).

### Dashboard, message of the day, players and bans

The **Activity** card plots 15 minutes to 24 hours of players, instances, simulation frame time (mean and longest), memory and CPU (memory and CPU need Linux); the server samples every 5 s and keeps 24 h in memory (`[metrics] enabled`, `interval_secs`, `retention_hours`; [../architecture/web-api.md](../architecture/web-api.md#metrics)). A frame time that grows with the players, or a longest frame above half of `[instance] tick_ms` (the server logs "slow simulation frame"), means the instance is overloaded. The **Message of the day** card edits `[server] motd` (plain text up to 280 characters): it applies at once, shows on the launcher's Home page and is written to the config file with a backup (if the file cannot be written, it holds until restart). The **Players** page lists who is in game (character, class id and level, account, area, instance, time connected, **IP address**, muted) with **Mute**, **Unmute**, **Transfer**, **Kick** and **Ban**, each confirmed.

A **ban** has a reason (shown to the player), a length (1 hour to 30 days, your own such as `90m` or `2w`, or Permanent) and, for an account, an option to also ban the address it plays from. The player is disconnected at once, saved logins (game Remember Me, web) stop working, and logging in again is refused with "This account is banned until 2026-10-29 04:00 UTC. Reason: ..." until the time is up. A banned **address** is refused at the game login and the web login, register and sign-in link, and covers everyone behind it (IPv6 matched exactly). You cannot ban yourself, another admin (remove the role first) or the address you use. The **Bans** tab lists bans (tick "Show ended and lifted bans too" for history), **Lift** ends one early, **New ban** bans an address or an account by name. Bans live in the `bans` table and are audited.

### Config editor

The **Config** page edits the file the server was started with (`POE_CONFIG`, else `modules/server/config/server.toml`); `[web] config_editor = false` makes it read-only. A **Form** shows common keys by section with help and bounds and whether a change is **live** (only the message of the day) or **needs a restart**; **Raw TOML** edits everything else with a live syntax check; comments and layout are kept. **Review changes** shows a diff and the server's verdict: an invalid config cannot be saved, risky settings (non-loopback web bind, open registration) are allowed but listed. **Save** writes the file; **Save and restart** also restarts with a countdown. The previous file goes to `[web] config_backup_dir` (`runtime/config-backups`, newest 20); **Backups** restores one. A file changed on disk since you opened the page refuses the save. The config has no secrets and must stay that way (token-like strings are hidden and kept on save). The committed `server.toml` keeps the safe defaults: run a server others use from your own copy (`POE_CONFIG=runtime/server.toml`); the page warns when it edits the committed file in a checkout.

### Scheduled tasks

The **Schedule** page runs **Restart the server** (countdown 0 to 3600 s and a message; the creator must still be an admin) on a schedule: **every day** or **days of the week** at a time, **every N hours** (`6h`, `90m`, `1d`: 1 minute to 30 days) or a **cron** expression (`minute hour day-of-month month day-of-week`, e.g. `0 4 * * mon-fri`). Times use the **server's local time zone** (the machine's, or `TZ`); the form previews the next five runs. **History** lists runs (`ran`, `failed`, `skipped` because a stop or restart was pending, `missed`). A run missed while the server was down is recorded `missed`, not made up; `[scheduler] enabled = false` turns it off and `missed_grace_secs` (120) is how late a run may still start. Tasks live in the database; changes and scheduled restarts are audited.

### Stop and restart the server

The dashboard's **Server** card has **Restart** and **Stop** buttons (admins only). Each opens a dialog with an optional message for the players and a countdown in seconds (0 to 3600; quick choices Now, 30 s, 1 min, 5 min, 10 min). Players in game get a `<Server>` chat line when the countdown starts and again at 10 min, 5 min, 2 min, 1 min, 30 s, 10 s and 5 s before the end, and a last one at the end, each with your message; then they are disconnected (characters saved) and the server stops or restarts. A banner on every page shows the countdown with a **Cancel** button (the players are told) until the last announcement. After a restart the page notices the server is back and keeps you signed in (the session is in the database). A stop leaves the server off: the page shows "The server has stopped" and reconnects by itself if somebody starts it again. The same endpoints work with `curl` (`POST /api/v1/admin/server/stop` and `/restart`, body `{"delay_secs": 60, "message": "new build"}`, [../architecture/web-api.md](../architecture/web-api.md#stop-and-restart)); every request, cancellation and announcement is in the audit file as `<admin> (web)`.

Ctrl+C and SIGTERM (systemd stop, the launcher's Stop) shut the server down the same way, at once and without announcements: players disconnected, sessions saved, exit code 0.

**How a restart brings the server back** (`[server] restart_mode` in `modules/server/config/server.toml`):

| `restart_mode` | After the shutdown | Use it |
|---|---|---|
| `"exec"` (default) | the process starts itself again with the same binary, arguments, environment and working directory (Unix: `exec`, the pid stays; Windows: a new process is started and the old one exits) | `cargo run`, a terminal, tmux, a plain systemd unit on Linux |
| `"exit"` | the process exits with **code 75** and something else starts it again | systemd (`RestartForceExitStatus=75`, [hosting.md](../../modules/server/docs/hosting.md#running-it-permanently)), the launcher's Host a server page, any supervisor that restarts on an exit code |

A stop exits with 0, so a supervisor that restarts only on failure leaves a stopped server stopped. A supervisor that restarts on every exit (`Restart=always`) also restarts a stop; use `on-failure` as in the hosting guide. Without a supervisor and with `"exit"` a restart request simply ends the process.

**Hosted through the launcher:** the launcher starts `poe-server` as a child process. On Linux and macOS the default `exec` mode works unchanged. On Windows `exec` mode makes the launcher see an exit; the intended fix is `restart_mode = "exit"` in the generated config plus a launcher restart on code 75, not done yet: a restart from the web admin ends the server and the host page's Start brings it back.

The log page shows what `[logging] filter` lets through (enable `debug` events there). For development the Vite dev server proxies `/api` to `[web] bind` ([setup.md](setup.md#web-admin-build)).

## Accounts

Admins are accounts with the `admin` role; there is no config admin list. Model, hashing, tokens: [../architecture/accounts.md](../architecture/accounts.md).

| Command | What it does |
|---|---|
| `account create <name> <password>` (CLI: `account create <name> --password-stdin`) | new player account. Hashed like the client does (SHA-256 of the UTF-16LE text), then argon2id. Password at least 8 characters, username 3-64 of `A-Za-z0-9_.@+-` |
| `account role <name> <player\|admin>` | sets the role; takes effect on the next command |
| `account disable <name>` / `account enable <name>` | a disabled account cannot log in; disabling revokes its saved logins and ends its sessions |
| `account passwd <name> <password>` (CLI: `account passwd <name> --password-stdin`) | new password; revokes the account's saved logins (Remember Me, launcher, web) |
| `account list` | every account: id, role, state, last login (`no password (dev)` marks old accounts without a password; nobody can log in to one until `account passwd`) |

An admin cannot demote or disable themselves.

**Passwords on the command line.** On the CLI give the password of `create` and `passwd` with `--password-stdin`: `poe-server account create alice --password-stdin` reads one line from standard input (e.g. `read -rs pw; printf '%s\n' "$pw" | poe-server account create alice --password-stdin`, or a pipe from a password manager). Only the trailing newline is removed, an empty line is refused, and the value is never echoed or logged. The flag works anywhere among the words, only with these two subcommands, and not together with a password argument. The form `account create <name> <password>` still works but is discouraged: every program on the machine can read a command line in the process list, and shell history keeps it.

Passwords typed in chat travel over the game connection and appear on screen: use the offline form for real passwords. `poe-server account ...` runs against the database, also while the server is up, and works for the first admin; it and the offline `poe-server character create|list` (test setups, `scripts/test-mp.sh`) are in [setup.md](setup.md#accounts-and-characters-offline).

Password attempts are rate limited (`[security]`: 5 failures per account name and 20 per IP in 5 minutes lock the key for 5 minutes, in game and on the web; saved-token logins are unaffected; a restart clears locks; [../architecture/accounts.md](../architecture/accounts.md#password-attempt-limits)). Set a limit to 0 to switch it off, e.g. for a test script that fails logins on purpose.

A client whose exe is not a known build of `[game] version` (its `client_hash` is not in the version file's `[client] hashes`) is refused at login with the client's own "There has been a patch that you need to update to" popup. `[security] allow_unknown_client = true` lets any build in (logged); a test config made without a version file checks nothing. Nothing is refused while the version file's `hashes_confirmed` is `false` ([new-game-version.md](new-game-version.md#what-the-server-does-with-the-clients-version)).

A second login of an account ends the first one (login connection and game).

## Instances

`poe_cluster::InstanceDirectory` (in-process `MemoryInstances`) holds every instance: area, seed, forced topology and orientation, its players and since when it is empty.

- Entering from character selection: towns and hideouts share one kept instance; other areas join the area's newest open instance, else get a new one.
- The first player decides an instance's seed (spec seed, else saved location, known seeds, random); later players get the same one.
- Empty instances close after `[instance] idle_minutes` (towns and hideouts stay in the directory; their simulation, the instance actor, also ends after that time and restarts with the next player).
- A closed instance disconnects its players.
- All players in an instance share one simulation and see each other ([instance-world.md](../architecture/instance-world.md#the-instance-actor)). The escape menu pauses the world only for a lone player.
- `instances` shows each instance's player count and names (written by its actor).

## Transfers

Verified with `G1_1` to `G1_2`, forced topology 3, orientation 0 (the client's tile hash 1655364279 equals the server's forced generation):

1. The instance server issues a ticket for the target instance and hands it to the account's login connection (`LoginSessions::transfer`), which keeps it as pending.
2. It ends the client's instance session. The client goes back to character selection on its still-open login connection and asks for the character list.
3. The login server answers with the list and the pending `InstanceDetails`; the client connects to the new instance and loads its area.

What does not work: `InstanceDetails` while the client is in an instance (received, ignored), and a second AreaInfo on one connection (crash). The login connection must stay open, so the server does not send login `0x0017` after the hand-off (`[network.login] close_after_handoff = false`; [../protocol/login.md](../protocol/login.md#hand-off-to-the-instance-server)). How official servers reconnect for later transfers is still to be captured.

Forced layouts: an instance with a topology or orientation sends them in AreaInfo's first stat record (flags0 bit 7; `map_force_topology` = 1-based topology, `map_force_orientation` = orientation + 1). Verified: the client generates that layout.

## Chat

C→S `0x0016` ChatSend (`u8`, wstring text, `u8`) carries the line as typed. Lines starting with the command prefix run as commands (replies as `<Server>` chat lines); others are routed by prefix: `#` global and `$` trade to everyone on the same channel number (from the client's join requests, `/global N`), none = local (same instance), `@name text` whispers. Party (`%`) and guild (`&`) answer "not supported yet". Muted players get "You are muted."

## Overlay pages (our server only, SERVER group)

Hidden while the read-only latch is on (official servers), like the Sync state and Desync pages.

- **Commands**: every registry command as a form, grouped; results below.
- **Instances**: the server's instances (id, area, seed, layout, players, time until an empty one closes) with Join and Close, and a new-instance form: area picker (search, kind and act filters, recent picks; every area from `poe-hook-data/areas.tsv`, written by `cargo xtask dll-data` or `deploy-client`), seed (random or server-picked), topology and orientation (natural or forced), with "Transfer there" and "Create without transferring".

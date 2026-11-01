# Web API

The server's HTTP and WebSocket API, for the web admin site ([Poe2WebAdmin](#the-web-admin-spa)) and the launcher ([../guides/launcher.md](../guides/launcher.md)). It is the crate `modules/server/crates/poe-web-api` (axum 0.8), started by `poe-server` next to the login and instance servers. The OpenAPI description is [openapi.json](../../modules/server/docs/openapi.json), generated from the code (`cargo xtask openapi`; `--check` fails when stale, and a unit test does too) and served live at `GET /api/v1/openapi.json`. The SPA and the launcher generate their types from it.

Related: accounts, tokens, hashing in [accounts.md](accounts.md); the commands the admin endpoints run in [../guides/server-admin.md](../guides/server-admin.md).

## Running it

`poe-server` starts the API when `[web] enabled` is true (default). Config (`modules/server/config/server.toml`, every key in `server.example.toml`):

| Key | Default | |
|---|---|---|
| `[web] enabled` | `true` | start the API with poe-server |
| `[web] bind` | `127.0.0.1:8080` | listen address. Loopback by default: passwords travel in request bodies, so put a TLS reverse proxy in front before exposing it |
| `[web] static_dir` | empty | directory with the built web admin (from the working directory); served at `/` with an `index.html` fallback for client-side routes. A set but missing directory logs a warning and serves nothing |
| `[web] cors_origins` | `[]` | browser origins allowed to call the API (e.g. `["http://localhost:5173"]` for the Vite dev server). Empty: no CORS headers |
| `[web] log_buffer` | `2000` | recent log events kept for the live log viewer |
| `[web] web_token_ttl_secs` | `60` | lifetime of the single-use web sign-in token ([below](#opening-the-web-admin-from-the-launcher)) |
| `[web] config_editor` | `true` | the config editor may save the config file ([below](#config-editor)); `false`: read-only |
| `[web] config_backup_dir`, `config_backup_keep` | `runtime/config-backups`, `20` | where the editor keeps the previous file on every save, and how many |
| `[server] motd` | empty | message of the day, `GET /server` field `motd` ([below](#message-of-the-day)) |
| `[metrics] enabled`, `interval_secs`, `retention_hours` | `true`, `5`, `24` | the sampler behind the dashboard charts ([below](#metrics)) |
| `[scheduler] enabled`, `history_keep`, `missed_grace_secs` | `true`, `100`, `120` | scheduled tasks ([below](#scheduled-tasks)) |
| `[mods] dir`, `require_client_mods`, `allow_extra_client_mods`, `extra_urls`, `report_wait_secs`, `max_failures`, `callback_budget_ms` | `mods`, `true`, `false`, `[]`, `15`, `5`, `50` | server mods and the client mod check ([below](#mods), [mod-host.md](mod-host.md)) |
| `[accounts] open_registration` | `false` | whether `POST /register` works |

Start the server and make an admin as in [../guides/setup.md](../guides/setup.md#web-api) (`curl localhost:8080/api/v1/server`, `POST /api/v1/login` with `{"username", "password"}`, then `Authorization: Bearer <token>` on `/api/v1/admin/...`).

## Authentication

- **Passwords are plain text in the request body** (`register`, `login`, `password`). The server turns them into the client's digest itself (`poe_accounts::password_digest`) and calls `AccountStore` as the game login does (argon2id over the digest), so an account made on the web logs in in game with the same password and the other way round. Minimum 8 characters, maximum 256.
- **Tokens** come from `AccountStore::issue_token`: 32 random bytes as 64 hex characters, only their SHA-256 stored, bound to `[cluster] id`, expiring, revocable. `POST /login` returns one of two kinds:
  - `web` (default): 12 hours. For the browser; the only kind the admin endpoints accept.
  - `launcher` (`"kind":"launcher"`): `[accounts] remember_days`. Never valid for `/admin/*`, so a leaked one cannot administer the server. The game's token login accepts it too, but a caller that wants to auto-login the game uses `POST /game-token` instead (the game would revoke the launcher token).
- Send `Authorization: Bearer <token>`. A browser cannot set the header on the log WebSocket, so it takes a **single-use ticket**: `POST /admin/logs/ws-ticket` (admin web token) returns `{ticket, expires_in_secs}` (valid `[web] web_token_ttl_secs`), and `GET /admin/logs/ws?ticket=<ticket>` redeems it once. The session token is never accepted in a URL (proxy logs record URLs). Non-browser clients can use the header on the WebSocket request.
- A token stops working when revoked (`POST /logout`, password change or `account passwd`, disabling the account), expired, from another cluster, or its account is disabled: `401` with the reason. The role is read at every call, so a demoted admin loses access at once.
- Wrong username and wrong password give the same `401`; a disabled account with the right password gets `403`.
- **Rate limiting:** `POST /login` and the old-password check of `POST /password` count failures per account name and per client IP (`[security]`, shared with the game login, [accounts.md](accounts.md#password-attempt-limits)). A locked name or IP gets `429` with `Retry-After` (seconds) before the password is checked, also for the right password. The client IP is the socket address; with `[security] trust_forwarded_for = true` (behind your own TLS proxy) the **last** `X-Forwarded-For` entry, the one the proxy appended.

### Opening the web admin from the launcher

The launcher's "Open web admin" button opens the browser already signed in. Three endpoints:

1. `GET /me` with the launcher token: the account and its `role`; the button shows only for `admin`. (`POST /login` returns the same `account` object; `/me` serves a launcher that restarts with only a stored token and reflects role changes at once.)
2. `POST /web-token` with the launcher token: returns `{token, expires_in_secs, login_path}`. The token is 32 random bytes as 64 hex characters, valid for `[web] web_token_ttl_secs` (60) and usable **once**. `login_path` is `/#/token-login?t=<token>`; the launcher opens `<server web address>` + `login_path` in the system browser.
3. The web admin's `#/token-login` page reads the token, removes it from the address bar and history (`history.replaceState`), then calls `POST /web-token/redeem` `{token}`, which returns the same response as `POST /login` with `kind: "web"` (a 12 hour session), kept in `sessionStorage`. A link that is expired, used, malformed or for a non-admin leads to the login page with a notice.

Security: the token is **single use and short-lived** (redeeming removes it whatever the outcome; a new request replaces the account's older one; at most 1024 unused tokens, `503` beyond), **bound to the account** it was minted for (only a launcher token of an admin may mint one; a disabled account's token gets `403`), kept only as a SHA-256 in memory (a restart drops pending tokens) and never logged (the log says `web sign-in token issued` / `redeemed` with the account name), travels in the URL *fragment* (never sent to the server, a proxy or a `Referer`; responses carry `Cache-Control: no-store`), and failed redemptions count per client IP in the shared `[security]` limiter (`429` with `Retry-After`). Redeeming issues a new `web` token and leaves the launcher token untouched.

Errors are JSON, `{"error": "..."}`: `400` bad input, `401` no or bad token, `403` not an admin (or registration closed), `404` unknown player, instance, account or character, `409` name taken, `429` too many failed password attempts (with `Retry-After`).

## Endpoints

All under `/api/v1`. Full schemas: [openapi.json](../../modules/server/docs/openapi.json).

Public (no token):
- `GET /server`: name, version, cluster id, players online, `open_registration`, `login_host`/`login_port` (where the game client connects), `instance_port`, `gateway_region`, uptime, `motd` (up to 280 characters; absent when none) and `mods` (client mods players need; absent when none; [below](#mods)).
- `POST /register` `{username, password}`: new player account; `403` unless `open_registration`, `409` when taken.
- `GET /setup`: `{needed, local, open_registration, name}`; `needed` is true only for a direct request from the server's own computer (loopback peer, no `X-Forwarded-For` / `Forwarded` header) while no account exists. `POST /setup` `{username, password}` (same restriction) creates the first account with the admin role and signs it in (`kind: "web"`); `403` once any account exists or from elsewhere. The launcher's "Open web admin" leads here on a new server.
- `POST /login` `{username, password, kind?}` returns `{token, kind, expires_at, account}`. `POST /web-token/redeem` `{token}` returns the same (`kind: "web"`); `401` unknown, used or expired (all alike), `403` disabled account, `429` too many failures from this IP.
- `GET /openapi.json`.
- `GET /mods/{id}/{version}.zip`: package of an offered client mod ([Mods](#mods)).
- `GET /local/metrics`: only for a direct request from the server's own computer (the `/setup` check); `{enabled, uptime_secs, latest}`, the newest sample, for the launcher that hosts the server.

Any token: `POST /logout` (revokes the token, `204`); `POST /password` `{old_password, new_password}` (revokes every token of the account, game Remember Me included, and returns a fresh token of the same kind); `GET /me` (`username`, `role`, state).

Launcher token: `POST /game-token` returns a fresh `game_remember` token (as `/login`) for the client's credentials file (web tokens get `403`; a launcher token must never be handed to the game, whose token login retires the token it uses). `POST /web-token` (admin launcher token only) returns `{token, expires_in_secs, login_path}` ([above](#opening-the-web-admin-from-the-launcher)); `403` for web or non-admin tokens, `503` when too many unused tokens wait.

Admin (web token with the `admin` role):
- Players and instances: `GET /admin/sessions` (character, account, level and class id, instance, area, `connected_at`, `ip` (admin API only), `muted`); `GET /admin/instances`; `POST /admin/instances` `{area, seed?, topology?, orientation?}` (`201 {id}`); `POST /admin/instances/{id}/close`; `POST /admin/players/{name}/kick`; `.../mute` `{minutes?}` and `.../unmute`; `.../transfer` `{instance}` or `{area, seed?, topology?, orientation?}`; `POST /admin/announce` `{message}`.
- Bans ([Bans](#bans)): `GET /admin/bans[?active=true]`; `POST /admin/bans` `{account` or `ip, reason?, duration_secs?` or `expires_at?}` (`201`; `400` for yourself, an admin, your own address, a bad address, reason or length; `404` unknown account; `409` already banned); `POST /admin/bans/{id}/lift` (`404` unknown, `409` already over).
- Accounts and characters: `GET /admin/accounts` (never the password hash); `POST /admin/accounts` `{username, password, role?}` (`409` when taken); `POST /admin/accounts/{name}/disable|enable` (disabling revokes tokens and ends sessions); `.../role` `{role}` (not on yourself); `GET /admin/characters[?account=name]` (with `online`); `GET /admin/characters/{id}`.
- `GET /admin/metrics[?since=<ms>&range_secs=&max_points=]` ([Metrics](#metrics)); `GET /admin/mods` ([Mods](#mods)); `POST /admin/motd` `{motd}` ([Message of the day](#message-of-the-day)).
- Config ([Config editor](#config-editor)): `GET /admin/config`; `POST /admin/config/validate` `{content}` (`{valid, error{message,line,column}, warnings}`); `POST /admin/config/fields` `{content, set{path: value}}`; `POST /admin/config/save` `{content, base_revision, restart?}` (`400` with line and column, `403` editor off, `409` stale revision); `GET /admin/config/backups`, `/{name}`.
- Schedule ([Scheduled tasks](#scheduled-tasks)): `GET /admin/schedule`; `POST /admin/schedule/tasks`, `/{id}`, `/{id}/enable|disable|delete` (`TaskBody`: `{name, enabled?, task{kind: "restart", delay_secs?, message?}, schedule{type: ...}}`); `GET /admin/schedule/tasks/{id}/runs`; `POST /admin/schedule/preview` `{schedule}` (next 5 runs, or `400`).
- Server control ([Stop and restart](#stop-and-restart)): `POST /admin/server/stop` and `/restart` `{delay_secs?, message?}` (`202`; `400` for a delay above 3600 s or a message above 200 characters; `409` when one is pending; the body is optional); `POST /admin/server/cancel` (`404` nothing pending, `409` too late); `GET /admin/server/shutdown` (`{pending: null}` or `{pending: {action, remaining_secs, delay_secs, message, requested_by, cancellable}}`).
- Logs: `POST /admin/logs/ws-ticket`; `GET /admin/logs/ws` (`?ticket=` or the `Authorization` header).

Character and account names in paths must not contain whitespace (they go into registry command lines).

### How the admin endpoints run

They reimplement nothing. `poe_cluster::AdminControl` (`modules/server/crates/poe-cluster/src/admin.rs`) is the surface the API needs from the instance server, which implements it (`modules/server/servers/instance-server/src/admin.rs`):

- `online()`: the live sessions (`Live::online`); rows carry the account id, session start, the client's address (the instance connection's peer) and the muted flag.
- `run_command(actor, line)`: parses `line` with the command registry (`commands.rs`), checks the actor's admin role now, and runs the session-free commands (`who`, `kick`, `mute`, `unmute`, `announce`, `instances`, `instance_new`, `close`, `account ...`) through the same code as chat (`exec.rs`: `run_global`/`execute_global`). Commands needing the caller's own game session (`where`, `join`, `teleport`, `terrain`, `area_info`) are refused. The call is logged and appended to the audit file as `<admin> (web)`, passwords redacted.
- `create_instance(actor, ...)` and `transfer_player(actor, character, target)`: `instance_new`, and `transfer` applied to another player: the account's login connection gets a ticket for the instance, the player's instance session ends, and the client falls back to character selection and receives the pending `InstanceDetails` ([../guides/server-admin.md](../guides/server-admin.md#transfers)).
- `record(actor, action, result)`: logs an admin action that is not a registry command (server stop, restart or cancel, ban, config save, schedule change) to the audit file as `<admin> (web)`.
- `end_sessions(account_id)`: ends an account's login connections and game sessions (`LoginSessions::supersede`), after a ban.

Instance listing reads `InstanceDirectory`; characters come from `poe-store` (`Store::all_characters`, `character_by_id`); accounts from `AccountStore`. The crate depends on those traits only, so tests run against an in-memory database and a mock `AdminControl`.

### Live log: `GET /admin/logs/ws`

`poe-server` adds `poe_web_api::LogLayer` to its tracing subscriber. The layer stores each event (`seq`, `ts_ms`, `level`, `target`, `message`, `fields`) in a ring buffer of `[web] log_buffer` events and broadcasts it. The buffer holds what the server's own filter lets through (`[logging] filter`, `RUST_LOG`).

Protocol (JSON text frames), after the upgrade:

1. Server: `{"type":"hello","buffer":2000}`.
2. Client: a filter, `{"min_level":"info","target":"instance_server","text":"kick","history":200}`. Every field is optional (`min_level` defaults to `info`, `history` to 200; `target` is a prefix; `text` matches message and fields case-insensitively). If nothing arrives within 500 ms, defaults apply.
3. Server: the newest `history` matching buffered events, oldest first, then new matching events: `{"type":"event","event":{...}}`.
4. The client may send a new filter at any time; the server answers `{"type":"reset"}` and replays the history under it.
5. `{"type":"lagged","missed":n}` when the client reads too slowly; `{"type":"error","message":...}` for a bad filter.

### Stop and restart

`modules/server/crates/poe-web-api/src/lifecycle.rs` owns the request, `modules/server/servers/poe-server/src/lifecycle.rs` the end of the process. `POST /admin/server/stop|restart` validates the body (`delay_secs` 0 to 3600, `message` up to 200 characters), refuses a second request with `409`, audits it and answers `202`; a countdown task announces through the `announce` command at the start, at 10 min, 5 min, 2 min, 1 min, 30 s, 10 s and 5 s below the delay, and `Server restarting now` at the end (cancellable until then via `POST /admin/server/cancel`). 1.5 s later it hands the request over a channel (`Lifecycle::new` returns the receiver) to `poe-server`, which stops the login and instance servers, kicks every session and waits up to 5 s for them to save and end, then ends per `[server] restart_mode`:

| Request | `restart_mode` | The process |
|---|---|---|
| stop (also SIGTERM and Ctrl+C, which skip the countdown) | any | exits with code 0 |
| restart | `exec` (default) | starts itself again: Unix `exec` of the same binary, arguments, environment and working directory (same pid, so a waiting parent such as the launcher's Host page or a systemd unit keeps seeing it); Windows has no `exec`: it spawns the new process (waits 2 s for the ports, `POE_SERVER_RESTART_WAIT_MS`) and exits 0, so a parent sees an exit |
| restart | `exit` | exits with code **75** (`poe_config::RESTART_EXIT_CODE`, `EX_TEMPFAIL`) and leaves the start to a supervisor |

A binary replaced while running is found again at its path (Linux reports `<path> (deleted)`). If the restart itself fails the process logs it and exits 75. Web sessions are database rows and survive a restart. Under a supervisor use `restart_mode = "exit"` ([hosting.md](../../modules/server/docs/hosting.md#running-it-permanently)).

### Bans

`POST /admin/bans` bans an **account** or an **IP address** for a length (`duration_secs`, 60 s to 10 years), until a date (`expires_at`) or for good. Rows live in the `bans` table (migration 0007) and stay as history when expired or lifted (`POST /admin/bans/{id}/lift`).

- **Account ban.** `AccountStore::authenticate` and `authenticate_token` (`modules/server/crates/poe-accounts`) refuse a banned account with `AccountError::Banned { reason, until }` *after* the password check (a wrong password never learns the ban state). That covers the game login (the client shows "This account is banned until 2026-10-29 04:00 UTC. Reason: ..."), the web login (`403`, same text), launcher and game tokens and the sign-in link. Creating the ban revokes the account's tokens and ends its sessions (`AdminControl::end_sessions`).
- **IP ban.** One address (IPv4, or IPv6 with IPv4-mapped addresses folded), no ranges, checked before the password and rate limiter by the game login (`modules/server/servers/login-server/src/auth.rs`) and the web API's `login`, `register` and sign-in-link redemption, using the login limiter's client address.
- **Safety.** An admin cannot be banned (take the role away first), nobody can ban themselves or the address they call from. A second active ban of the same target is `409`. The reason is plain text up to 200 characters, shown to the player. `ban account|ip` and `unban account|ip` with target and reason go to the audit file as `<admin> (web)`.

### Metrics

`poe_cluster::metrics` (`modules/server/crates/poe-cluster/src/metrics.rs`). Instance actors record each frame's time in `Actors::ticks` (`TickStats`); a sampler (`spawn_sampler`, started by `poe-server`) takes a `Sample` every `[metrics] interval_secs` into a ring buffer for `[metrics] retention_hours` (24 h at 5 s = 17 280 samples; lost on restart). A sample holds time (ms), `players`, `instances`, `occupied`, the interval's frames (`tick_count`) with mean and longest time in microseconds, `rss_bytes` and `cpu_pct` (from `/proc/self` on Linux, `0`/absent elsewhere), and `net_in_bps` / `net_out_bps` (TCP payload of every `poe_net::Connection`, `poe_net::stats`; the UDP side channel is not counted).

`GET /admin/metrics` answers `{enabled, interval_secs, retention_secs, now, samples}`; `since` (ms) returns only newer samples, `range_secs` the last N seconds, `max_points` (2 to 5000, default 600) merges longer ranges into buckets keeping peaks, frame-weighted mean frame time and mean CPU and network rates. The dashboard polls (every 5 s to 1 min by range).

### Config editor

`modules/server/crates/poe-web-api/src/configfile.rs`. The editor reads and writes **the file the server was started with** (`Config::source_path`: `POE_CONFIG`, else `modules/server/config/server.toml`; `409` when the server has no file). `[web] config_editor = false` makes it read-only (`403` on save).

- **Form and raw editor.** `GET /admin/config` returns the text, its `revision` (SHA-256 prefix), the form's field schema (`poe_config::schema::common_fields`: section, key, label, help, type, bounds, default, restart needed; a test checks them against the typed config) and the values the file sets. `POST /admin/config/fields` writes form values into the text with `toml_edit` (comments and layout kept). `POST /admin/config/validate` is the live syntax check.
- **Validation.** Like at start: TOML syntax, typed sections, then the `[game] version` file (`Config::check_text`). Invalid text is refused with **line and column** (`400`). Dangerous settings (`Config::security_warnings`: non-loopback web bind, open registration on a reachable API, the removed Steam login key) are saved and returned as warnings.
- **Save.** A line diff is shown first. A save copies the previous file to `[web] config_backup_dir` as `<name>.<UTC timestamp>` (`-001`, `-002`; mode 0600; the oldest beyond `config_backup_keep` are deleted), then writes a temp file and renames it over the original (permissions kept). `GET /admin/config/backups` lists them. A stale `base_revision` (hand edit) gets `409`. `restart: {delay_secs?, message?}` requests the [Stop and restart](#stop-and-restart) restart afterwards (a pending shutdown makes it `restart_error`; the file stays saved). Most keys are read only at start; the message of the day applies live.
- **Secrets.** The config holds none and must not. Strings under token-like keys (`token`, `secret`, `password`, `passwd`, `api_key`, `private_key`, `credential`) show as `<hidden>` (`poe_config::edit::redact`) and are restored on save; a placeholder with nothing to restore is refused. Contents are never logged or audited (the audit line: `config save`, changed line count, backup name).
- **Safe defaults.** The committed `server.toml` has the safe values (loopback binds, no registration, no developer tools; tests keep it valid and warning-free). The editor never loosens anything and warns when it edits that committed file in a checkout: use your own copy (`POE_CONFIG=runtime/server.toml`). New keys come with safe defaults in `server.toml` and `server.example.toml`.

### Message of the day

`[server] motd`: plain text, at most 280 characters, line breaks allowed, no other control characters (`poe_config::check_motd`; the config refuses a longer one at load). `GET /server` returns it as `motd` when not empty (the launcher's Home page shows it). `POST /admin/motd {motd}` applies it at once (`WebState::motd`, a live copy) and writes the same text into the config file through the editor's save path (backup, validation, atomic write); when the file cannot be written (editor off, no file, read-only) the response says `persisted: false` with the reason and the message holds until a restart. Saving the config in the editor refreshes the live message.

### Mods

`WebState::mods` is a `poe_cluster::ModDirectory` (implemented by `poe_mod_host::ModHost`; `NoMods` in tests). Three endpoints, `modules/server/crates/poe-web-api/src/mods.rs`:

- **`mods` in `GET /server`**, a plain array (the launcher's contract, pinned by `tests_mods.rs`): one entry per enabled mod with side `client` or `both` that loaded (server-only mods are never listed):

```json
"mods": [{
  "id": "hello-both", "name": "Hello both", "version": "0.1.0", "side": "both",
  "sha256": "<64 lower-case hex of the zip>", "size": 288813,
  "required": true, "hook_api": 1, "game_versions": ["0.5.5e.hotfix1"], "code": true,
  "authors": ["..."], "description": "...",
  "sources": [
    {"type": "server", "path": "/api/v1/mods/hello-both/0.1.0.zip"},
    {"type": "url", "url": "https://example.invalid/hello-both-0.1.0.zip"}
  ]
}]
```

  `hook_api` is absent for a data-only client half; `sources` has the server's own path first, then one `url` per `[mods] extra_urls` (`{id}`/`{version}` replaced). The field is absent for a server without client mods.
- **`GET /mods/{id}/{version}.zip`**: public, the verified package bytes, `ETag` = the quoted SHA-256, `If-None-Match` gives `304`, `Cache-Control: public, max-age=3600`, `Content-Disposition` with `<id>-<version>.zip`; `404` for unknown or server-only mods and malformed ids and versions (letters, digits, `. - _ +` only). The host re-hashes the file before sending. No rate limit of its own; put the usual reverse-proxy limits in front of a public server.
- **`GET /admin/mods`** (admin): `{active, mods: [{id, name, version, side, enabled, state, detail, commands}], restart_required, require_client_mods, allow_extra_client_mods}` for the Mods page. `state` is `loaded`, `skipped` (reason in `detail`), `failed` (disabled at run time) or `installed` (not enabled). Mods are changed on the server (`poe-server mod ...`, [../guides/modding.md](../guides/modding.md#running-server-mods)) and apply at the next start; no endpoint changes them.

### Scheduled tasks

`modules/server/crates/poe-web-api/src/scheduler/`. Tasks live in the database (`scheduled_tasks`, `scheduled_task_runs`, migration 0008): name, `kind` and `params`, `schedule` (JSON), enabled flag, creator, last run and result, next run. `poe-store` keeps these as opaque JSON; the scheduler owns their meaning.

- **Schedules** (`schedule.rs`), in the server's **local time zone** (`TZ`, else the system zone; shown by `GET /admin/schedule`): `daily` (`HH:MM`), `weekly` (`days` mon..sun, `time`), `interval` (`every_secs`, 60 s to 30 days, from the last run or server start) and `cron` (five fields; `*`, numbers, ranges, lists, steps `*/n` `a-b/n` `a/n`, names `jan` `mon-fri`; `0` and `7` are Sunday; if both day fields are restricted either may match, as in Vixie cron). A local time skipped when clocks go forward runs right after the gap; one that happens twice runs the first time only.
- **Kinds** (`kind.rs`, enum `TaskKind` with a `kind` tag): only `restart` (`delay_secs`, `message`, like `POST /admin/server/restart`). To add one: a variant, `tag`, `validate`, `describe` and `execute` arms, the web admin's task form and `cargo xtask openapi`. A task runs as the admin that made it (announcements audited as that admin) and fails clearly if that account is no longer an admin.
- **Running** (`mod.rs`): `Scheduler::run` polls once a second. A task's next time is stored before it runs, so a restart cannot repeat it. **Missed runs are skipped, not replayed**: a run found later than `[scheduler] missed_grace_secs` (120) after its time, or due while the server was down, is recorded `missed`; at start next runs are worked out from the current time. A restart finding another shutdown pending is `skipped`. Results: `ok`, `failed`, `skipped`, `missed`; `history_keep` runs kept per task. `[scheduler] enabled = false` lists tasks but runs nothing.
- Every create, update, enable, disable and delete is audited, and so is each scheduled restart.

## Serving the web admin

Every response (API and static files) carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` and a `Content-Security-Policy` allowing only the app's own scripts, styles, images and connections (`default-src 'self'`, `connect-src 'self'`, `frame-ancestors 'none'`); a reverse proxy that sets the same headers wins. The server has no TLS of its own: put a TLS proxy in front ([hosting.md](../../modules/server/docs/hosting.md#tls-reverse-proxy-for-the-web-api)).

With `[web] static_dir` set to the SPA build (`modules/web-admin/dist`), the same port serves it: files as they are, any unknown non-API path as `index.html`. At start the server logs which build it serves, read from `dist/build.json` that the web admin's build writes (`name`, `version`, `built_at`, `commit`, `dirty`), and warns when the sources next to `dist` are newer than the build or `build.json` is missing (`modules/server/crates/poe-web-api/src/webadmin.rs`). A release package has no sources, so it never warns; from the hub, `cargo xtask server run` rebuilds a stale web admin first ([setup.md](../guides/setup.md#web-admin-build)). Unknown `/api/v1/...` paths stay JSON `404`s. During SPA development run Vite on its own port; its dev server proxies `/api` (and the log WebSocket) to `[web] bind`, so `cors_origins` is only needed when the page calls the API cross-origin.

## The web admin SPA

Repo [Poe2WebAdmin](https://github.com/WaystoneWorks/Poe2WebAdmin) (private), submodule `modules/web-admin`. Svelte 5 + Vite + TypeScript, plain CSS in the launcher's design language (same tokens, sidebar, cards, chips, dialogs, toasts; dark by default, a light theme, the system preference until toggled; animations stop under `prefers-reduced-motion`; icon rail on narrow windows, bottom tab bar on phones). Build and run: [../guides/setup.md](../guides/setup.md#web-admin-build); usage: [../guides/server-admin.md](../guides/server-admin.md#web-admin); development: the repo's README.

Pages (hash routes) and the endpoints they use: login (`POST /login` with `kind: "web"`; non-admins are refused and their token revoked); `#/token-login?t=` (redeems the launcher's one-time link with `POST /web-token/redeem`, same admin check); `#/register` (public: `GET /server`, `POST /register`; opened by the game's *Create account* button through the hook's `register_url`); first run (`GET /setup`: when `needed` the login page becomes *Welcome*, whose form posts to `POST /setup`); `#/dashboard` (`GET /server`, `/admin/instances`, `/admin/sessions` every 5 s; server control with confirmation dialogs for `POST /admin/server/restart|stop` and a countdown with Cancel; the Activity charts from `GET /admin/metrics`, hand-rolled SVG, ranges 15 min to 24 h; the message-of-the-day card `POST /admin/motd`); a banner on every page from `GET /server` and `GET /admin/server/shutdown` (every 5 s, 1.5 s while pending or unreachable); `#/logs` (ws-ticket, then the log WebSocket per connection attempt; filters sent after 300 ms; pause, autoscroll, at most 3000 lines, reconnect with backoff 0.5 s doubling to 15 s); `#/players` (Online tab from `GET /admin/sessions` every 5 s with kick, mute, unmute, transfer, Ban; Bans tab `#/players?tab=bans`); `#/schedule` (tasks, preview, history); `#/config` (Form and Raw TOML, Review changes, Save, Backups); `#/instances`; `#/accounts` (search, filters, **New account**, drawer with role, state, Disable/Enable, Ban); `#/characters[/{id}]`; the sidebar Announce dialog; `#/inventory` and `#/passives` are stubs behind `VITE_FEATURE_INVENTORY` / `VITE_FEATURE_PASSIVES`.

Close, kick, unmute, ban (permanent ones twice), lift, disable, delete and role changes ask for confirmation. The bearer token is kept in `sessionStorage` (never `localStorage`); a `401` from any call other than login clears it and shows the login page. The TypeScript types (`src/lib/api/schema.d.ts`) are generated from [openapi.json](../../modules/server/docs/openapi.json) with `npm run gen:api` in the SPA repo: after `cargo xtask openapi` changes the spec, regenerate, run `npm run check`, commit in Poe2WebAdmin, then bump the submodule here. Its CI runs `npm ci`, `npm run check`, `npm test` and `npm run build`.

## Code map

In `modules/server/crates/poe-web-api/src/`: `lib.rs` (`WebState` with the shared `LoginLimiter` and `Lifecycle`, `router`, `serve`), `lifecycle.rs`, `auth.rs` (`Auth`, `AdminAuth`, `WsAdminAuth`), `webtoken.rs` (`WebTokens`), `public.rs` and `admin.rs` (handlers with `utoipa` descriptions), `dto.rs`, `error.rs`, `logs.rs` (`LogBuffer`, `LogLayer`, `LogFilter`), `bans.rs`, `metrics.rs`, `motd.rs`, `mods.rs`, `configfile.rs`, `scheduler/` (`schedule.rs`, `kind.rs`, `mod.rs`, `api.rs`), `openapi.rs`, and router tests with tower `oneshot` in `tests.rs`, `tests_features.rs` and `tests_mods.rs` (which pins the mod advertisement JSON and package download).

## Not done

- TLS in the server itself (use a reverse proxy).
- Inventory and passive-tree endpoints.
- A registry listing endpoint (`GET /admin/commands`) for generic command forms.
- Class names in the players list (it shows the class id), address ranges for IP bans, `ban`/`unban` as chat commands or `poe-server account` subcommands, a push stream for the metrics (the page polls).

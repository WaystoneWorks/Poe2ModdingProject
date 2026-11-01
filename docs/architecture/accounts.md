# Accounts and identity

How a player logs in, how accounts and tokens are stored, how admins are chosen. Remote players: [hosting.md](../../modules/server/docs/hosting.md). Wire format: [../protocol/login.md](../protocol/login.md). Client side: [../re/standalone-login.md](../re/standalone-login.md).

The code is the `poe-accounts` crate (`AccountStore` trait, `SqliteAccounts` over the `poe-store` database, migration `0006_accounts_auth.sql`). The login server decides in `modules/server/servers/login-server/src/auth.rs`. The launcher has no login of its own and creates no accounts: players sign in on the game's login screen, and new accounts are made on the server's web page or by commands.

## Model

| | |
|---|---|
| Account | `accounts` table: `id`, `name` (username; unique case-insensitively), `password_hash`, `role`, `created_at`, `last_login`, `disabled`. Characters belong to the account id. |
| Role | `player` or `admin`, checked when a command runs; no config list. |
| Disabled | Cannot log in (result `0x47`); its tokens are revoked and running sessions ended. |
| Token | `account_tokens` table: `kind` (`game_remember`, `launcher`, `web`), `token_hash`, `cluster_id`, `created_at`, `expires_at`, `revoked`, `last_used`. |
| Cluster | `[cluster] id` in `modules/server/config/server.toml`; every token records the issuing cluster's id. |

Usernames are 3-64 characters from `A-Za-z0-9_.@+-` (an email address works). Server commands require passwords of at least 8 characters.

## Passwords: what is hashed

The client never sends the plain password. Its login screen sends `SHA-256(UTF-16LE(password))` (32 bytes, no salt; [login.md](../protocol/login.md#cs-0x0003-credentials-standalone-platform)). The stored secret is **argon2id over that digest** (PHC string, random salt per hash; default cost 19 MiB, 2 passes).

Everything that sets or checks a password must produce the same digest first:

```
digest = SHA-256(password encoded as UTF-16LE, no BOM, no terminator)
stored = argon2id(digest)            // poe_accounts::AccountStore takes the digest, never the text
```

`poe_accounts::password_digest(&str)` does the first step. The server commands (`account create`, `account passwd`) and the web API (registration, login, password change; `modules/server/crates/poe-web-api`) go through it, or a web-made account would not accept the same password in game. The web API receives the plain password in the request body (use TLS outside the local machine) and never needs the stored hash. The digest is a password equivalent for this server but is stored only inside an argon2id hash.

## Tokens

- 32 random bytes (never all zero). The server keeps only `SHA-256(token)`; the raw bytes exist once, in the `0x0004` reply (`session_token`) or the web response.
- `game_remember`: issued when a password login has `save_login = 1`. The client saves it in its credentials file and sends it back as `password_hash` with `token_login = 1`. **Rolling:** each token login revokes the token it used and returns a fresh one. Lifetime `[accounts] remember_days` (30).
- A token is valid when its hash is known, its `cluster_id` equals `[cluster] id`, it is not revoked or expired, of an accepted kind, and the account is not disabled. On a token login the client's saved user name must also match the token's account.
- A new password (`account passwd`) and disabling an account revoke all the account's tokens.
- **Cluster id:** changing `[cluster] id` invalidates every saved login; a database copied between clusters keeps its accounts and passwords, but no token from the other cluster works.
- Other kinds share the table and trait (`TokenKind::Launcher`, `TokenKind::Web`), issued by `POST /api/v1/login` ([web-api.md](web-api.md)): web 12 hours, launcher `remember_days`. The game's token login accepts `game_remember` and `launcher`; `POST /api/v1/game-token` issues a separate one-off `game_remember` token because the game's rolling login would revoke the caller's token. The admin API accepts `web` only. `POST /api/v1/web-token` exchanges a launcher token for a single-use, 60-second sign-in token that the browser redeems for a `web` token ([web-api.md](web-api.md#opening-the-web-admin-from-the-launcher)); these hand-off tokens live in memory only.

Failure result codes: [login.md](../protocol/login.md#authentication-results). A saved login that cannot be used (expired, revoked, unknown, another cluster, another user name) gets `0x0f`: the client deletes its credentials file and asks for the password at the next start.

## Login paths

| Path | Packet | When |
|---|---|---|
| Username and password | `0x0003`, `token_login = 0` | the standalone login screen (`login_mode = "standalone"`, [client-dll.md](client-dll.md#login-mode-and-trusted-servers)) |
| Saved token | `0x0003`, `token_login = 1` | Remember Me |

There is no password-less login. A Steam `0x0005` login always gets result `9` ("Access to the game is not currently enabled") with the notice "This server needs a username and password login." (an unknown client build gets its update popup first). The key `[accounts] dev_machine_hash_login` is ignored with a startup warning. Unattended in-game tests sign in with a Remember Me token ([setup.md](../guides/setup.md#unattended-client-tests)).

Accounts from before migration `0006` (made by the old machine-hash login) have a null password: nobody can log in until `account passwd <name> <password>` sets one. The migration made an existing `Exile1` an admin; on a fresh database nobody is promoted.

## Admins and account commands

Admin is the `admin` role. Commands (chat `!account ...`, the overlay's Commands page, or offline `cargo xtask server run -- account ...`): `create`, `role`, `disable`, `enable`, `passwd`, `list`; see [../guides/server-admin.md](../guides/server-admin.md). The first admin is made offline: `account create <name> <password>`, then `account role <name> admin`. Passwords typed in chat are replaced by `***` in the log and audit file. An admin cannot demote or disable themselves.

`[accounts] open_registration` (default false) lets `POST /api/v1/register` create player accounts ([web-api.md](web-api.md)); server commands always work.

## Password attempt limits

`[security]` (`modules/server/config/server.toml`) limits failed password attempts. One `poe_accounts::LoginLimiter` is shared by the login server (`0x0003` password logins) and the web API (`POST /login`, and the old-password check of `POST /password`). Failures are counted per account name (case-insensitive; unknown names count too, so the limit does not reveal which accounts exist) and per client IP (IPv6 per /64) in a sliding window; at the limit the key is locked and attempts are refused before the password is checked (no argon2 cost).

| Key | Default | Meaning |
|---|---|---|
| `login_max_failures_per_account` | 5 | failures per account name in the window before it is locked; 0 = off |
| `login_max_failures_per_ip` | 20 | the same per client IP; 0 = off |
| `login_failure_window_secs` | 300 | failures older than this are forgotten |
| `login_lockout_secs` | 300 | how long a locked key stays locked (from the failure that locked it; refused attempts do not extend it) |
| `trust_forwarded_for` | false | web API behind a reverse proxy: take the client IP from the **last** `X-Forwarded-For` entry, the one your proxy appended (a client can prepend its own, so the first proves nothing). Only with a proxy that appends the real peer address (nginx `$proxy_add_x_forwarded_for`, Caddy's default); otherwise a client chooses its own IP |

The game answers a locked attempt with result `0x49` (`LoginRateLimited`) and a notice naming the wait; the web API answers `429` with `Retry-After`. A right password clears the account's count but not the IP's. Saved-token logins are neither counted nor refused. The state is in memory: a restart clears all locks; there is no unlock command. Trade-off: someone who knows a name can lock that account for the lockout time (the owner can still use a saved token). Behind a proxy without `trust_forwarded_for` every web client shares the proxy's IP and one attacker locks the web login for everyone; the game login sees real addresses.

**Timing.** A password login for an unknown account name, or for an account with no password, verifies the digest against a throw-away decoy argon2 hash first, so a wrong login takes about as long whether or not the name exists (`SqliteAccounts::spend_verify_time`). Game reply codes still differ (5 no such account, 6 wrong password); the web API answers one text for both.

## Limits before the login

Idle or slow sockets must not pin memory and tasks before authentication. Both game ports have limits until the client has logged in (login server) or shown a valid ticket (instance server); `0` turns one off:

| Key | Default | Meaning |
|---|---|---|
| `[network.login] pre_auth_read_timeout_secs` | 15 | longest time one message (key exchange included) may take to arrive; then the connection closes |
| `[network.login] pre_auth_login_timeout_secs` | 60 | longest time from connecting to a successful login (keep-alives do not extend it) |
| `[network.login] pre_auth_max_buffer` | 65536 | bytes held for an incomplete message (`Connection::set_max_buffer` in `poe-net`); after login the limit is 16 times that |
| `[network.login] max_pre_auth_connections`, `max_pre_auth_per_ip` | 256, 16 | connections not yet logged in, total and per client IP (IPv6 per /64); `poe_accounts::ConnectionLimiter`; a place is freed at login |
| `[network.instance] pre_auth_read_timeout_secs`, `pre_auth_max_buffer`, `max_pre_auth_connections`, `max_pre_auth_per_ip` | 15, 65536, 256, 16 | the same for the instance server's first message (`Hello`); a place is freed when the ticket is redeemed and the buffer limit lifted |

A refused connection is closed at once and logged (at most one line per second). Instance tickets are random 32-bit numbers, valid 60 seconds, single use (the wire format has a 32-bit field).

## One session per account

A new login ends the old one: `LoginSessions::supersede(account)` (`poe-cluster`) closes the account's login connections and signals its instance sessions to disconnect. It runs after a successful login, before the new connection subscribes. The same call ends the sessions of a disabled account. A resumed session (`0x0008`, "Exit to character selection") does not supersede.

## Other state

- **Storage:** accounts, characters and per-account character lists are in SQLite (`poe-store`). Character names are unique across accounts (case-insensitive). The slot limit comes from config.
- **Tickets and sessions** (`poe-cluster`): tickets with random keys per hand-off; single-use resume tickets; login sessions per account (logout, supersede, transfers).
- **Account settings:** `[accounts] flags` (default `[0x23, 0x03]`, [login.md](../protocol/login.md#authenticationresult-flags-and-the-suspicious-activity-popup)), `full_access`, `stash_tabs` are global for every account.
- **Steam path:** `0x0005` carries the Steam encrypted app ticket, encrypted with GGG's key, so the server cannot verify it.

## Not done yet

- Per-account settings.
- An admin command to unlock an account or IP early.
- Whether `0x0f` (stale token) and `0x49` (rate limit) show what the client code says (untried in game; password and Remember Me logins work): [../re/standalone-login.md](../re/standalone-login.md) section 5.

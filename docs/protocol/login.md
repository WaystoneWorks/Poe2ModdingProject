# Login protocol (0.5.5e Hotfix 1)

Connection: client to the login host from `gateway_list.txt` (ours: `[network] public_host` and `[network.login]` port, written by `cargo xtask deploy-client`).

## Observed sequence
1. **C→S `0x0002` ephemeral public key** (the first message, unencrypted):
   ```
   00 02            opcode
   00 80            u16 key length = 128
   <128 bytes>      client DH public value (1024-bit)
   00 00            u16 signature length = 0 (the client does not sign)
   ```
   Identical to PoE1 3.x `LOGIN_EPHEMERAL_PUBKEY`.
2. **S→C `0x0002`** with the same layout: the server's public value and a DSA signature. Ours sends 128 random bytes and an empty signature; the DLL's `crypto_bypass` derives the keys. **From here on both directions are Salsa20-encrypted** ([../re/crypto.md](../re/crypto.md)).
3. **C→S authentication.** On the Steam platform (the exe file name contains `Steam`): `0x0005` (229 bytes in the first capture, a protobuf-like blob from +0x45 = the Steam encrypted app ticket). On the standalone platform: `0x0003` with account name and password hash, see [below](#cs-0x0003-credentials-standalone-platform). The platform getter decides; a DLL patch can force it: [../re/standalone-login.md](../re/standalone-login.md).
4. **C→S `0x0001`** every ~10 s: keep-alive (opcode only).

## Message layouts

Encodings: integers big-endian. `wstring` uses the compact per-character encoding ([framing.md](framing.md)). `astring` = u16 length + bytes. Rust types: `modules/protocol/poe-proto/src/login.rs`. Opcodes: `modules/protocol/opcodes/0.5.5e.hotfix1/login.toml`.

### C→S `0x0005` Authenticate (client serializer `0x1420e3670`, built in `0x1420e7f80`)
| Field | Type | Notes |
|---|---|---|
| ticket_len | u16 | |
| flags_lo | u8 | UI language id (global `DAT_143a0c068`, 0 = English) `\| 0x40` |
| client_hash | 32 bytes | `LoginClientHash_Get32` `0x1420e7700`: a hash (SHA-256 family, `0x1421bbf40`) of **the file named by argv[0], the client executable**, computed once on a worker thread at start (`0x1420eb5f0`; the getter waits). The 0.5.5e value is the exe's SHA-256 `7157984534da1b146e9b0be342aa9fd24272915b6f478aadef9830fc7873f89f`. The login server judges it against `[client] hashes` of `modules/protocol/versions/<version>.toml` and refuses an unknown build with code 8 (`InvalidProtocolVersion`) once `hashes_confirmed` is set (true for 0.5.5e; [../guides/new-game-version.md](../guides/new-game-version.md#what-the-server-does-with-the-clients-version)); while unconfirmed it logs the value of a hash not in the list. The refusal shows the popup "There has been a patch that you need to update to. Please restart Path of Exile." and our notice in the log pane |
| machine_hash | 32 bytes | `0x1421c1580`: cached 32-byte machine id built by `0x1421c0f60` (fallback `0x1421c0e60` when all zero); stable per machine; our server ignores it |
| flags_hi | u8 | optional login-state byte (`LoginState +0x529`, valid when `+0x52a`), 0 when unset |
| ticket | bytes[ticket_len] | Steam encrypted app ticket (from `GetEncryptedAppTicket`), encrypted for GGG, unreadable to us |

### C→S `0x0003` Credentials (standalone platform)
Sent instead of `0x0005` when the client platform is 0 (email/password screen). Serializer `0x1420e3ce0`, builder `0x1420e7c70`; analysis and the patch that forces this path on the Steam exe: [../re/standalone-login.md](../re/standalone-login.md). Opcode in `login.toml` (`Credentials`), Rust type `poe_proto::login::Credentials`; handled by `modules/server/servers/login-server/src/auth.rs`.
| Field | Type | Notes |
|---|---|---|
| mode | u32 | constant `2` (object +0x30 of the packet class), the only value the client stores; meaning unknown (auth type or protocol revision). Keep `2`, ignore it |
| account_name | u16 length + UTF-8 bytes | not a wstring |
| client_hash | 32 bytes | as in `0x0005` |
| password_hash | 32 bytes | SHA-256 of the UTF-16LE password; with `token_login = 1` the saved 32-byte token that an earlier `0x0004` `session_token` handed out |
| machine_hash | 32 bytes | as in `0x0005` |
| save_login | u8 | the Remember Me checkbox (1 on the token path) |
| token_login | u8 | 1 = `password_hash` is a saved login token |
| flags_lo | u8 | UI language id `\| 0x40` (same as `0x0005`) |
| flags_hi | u8 | optional login-state byte, 0 when unset |

Answered with `0x0004`. With `save_login = 1` (or a token login) a successful answer carries a fresh 32-byte `session_token`, which the client saves for Remember Me; otherwise the token is all zeros. `password_hash` is checked against the argon2id hash of the digest ([../architecture/accounts.md](../architecture/accounts.md)). Failures: [Authentication results](#authentication-results).

### Authentication results
**The client has one code table: `Data/Balance/BackendErrors.dat`** (715 rows, `Id` and `Text`; the text of code *n* is row *n - 1*, so row 0 is code 1). `BackendError_GetText` (`0x1425cb9c0`) looks it up; the language picks a translated copy under `data/balance/<language>/`. Every result code on the login connection goes through it: `0x0004` `result`, `0x0013` CharacterCreated `result`, `0x000d` DeleteCharacterResult `result`. An unknown row prints `bad-error-code`. Read the table with `poe_data_tools ... extract <dir> 'data/balance/backenderrors.datc64'` (`docs/guides/setup.md`). The 16-entry table at `0x1421ee750` belongs to the standalone patcher only (caller `StandalonePatcher_Run`), not to login.

Codes the login server uses (`modules/server/servers/login-server/src/auth.rs`, `auth::code`, numbers from `poe_proto::backend_error`: one named list of table rows with their `Id`; the server checks them against the real table at start and warns on a mismatch, `login-server/src/codes.rs`). `*` = special handling in `LoginState_HandleAuthenticationError` `0x140ef63a0`:

| Code | `Id` | Text (English table) | Client effect |
|---|---|---|---|
| `0` | | accepted | continues (see [flags](#authenticationresult-flags-and-the-suspicious-activity-popup)) |
| `5` | AccountDoesNotExist | The specified account does not exist. | error popup |
| `6` | InvalidPassword | The password is not correct for this account. | error popup |
| `8` * | InvalidProtocolVersion | There has been a patch that you need to update to. Please restart Path of Exile. | Steam only: marks the content corrupt |
| `9` | NotAllowedGameLogin | Access to the game is not currently enabled on this account. | error popup |
| `0x0f` * | UnexpectedDisconnect | An unexpected disconnection occurred. | **deletes the saved credentials file** (not on Steam); our notice shows only as a line in the status log at the lower left, no modal popup |
| `0x13` | DatabaseError | An unexpected database error occurred. Try again. | error popup |
| `0x47` (71) | AccountBanned | Your account has been banned by an administrator. | error popup |
| `0x49` (73) | LoginRateLimited | You have attempted to log in too often within a short time period. Try again later. | error popup with the table text; our notice (the wait) shows only in the status log |
| `0x4a` (74) | AccountLocked | Your account has been locked. Please contact support. | error popup |
| `0x4c` (76) | TemporaryLockout | Your account has been temporarily locked while an administrator works with it. | error popup |
| `0x54` (84) * | LeagueUnavailableToNonBeta | This league is only available to Beta players. | popup path of its own |
| `0x60` (96) | SavedCredentialsNewLocation | You are logging in from a new location. Please re-enter your password. | error popup only |
| `0x61` (97) | SavedCredentialsBad | Your saved credentials are out of date. Please re-enter your password. | error popup only (file kept) |
| `0x62` (98) * | LoginRequiresUnlockCode | Your account has been locked until you can provide an unlock code from your email. | **opens the Unlock window** ("...An unlock code has been sent to your email address...", code box, Unlock / Resend Email). Our `notice` is not shown |
| `0x1cf` (463) * | LoginRequiresUnlockCodeStrict | ... (strict) | the same Unlock window with the red "We have detected suspicious activity on your account. You will be required to enter login unlock codes more often until you change your password." in front |
| `0x208` (520) | EmailLoginDisabled | This login method has been disabled for this account. | error popup |
| `0x230` (560) | AccountNotVerified | Account is not verified. | error popup |
| other | | table text, or `bad-error-code` | error popup |

If `notice` is non-empty it replaces the table text in the popup (language-tagged, see the `notice` row of the `0x0004` table); it does not change what the code does.

**Close the connection after a refusal.** The client starts a new attempt (Log In button, Enter) only once the old login connection is gone. The server closes it right after a refused `0x0003` (`login-server/src/session.rs`); the client then also logs "An unexpected disconnection occurred." in the status log.

**What our server sends.** `5` no such account, `6` wrong password, `9` for every Steam `0x0005` login, `0x13` store error, `0x47` disabled account, **`0x49` too many password attempts** ([rate limits](#password-attempt-limits)), **`0x0f` for every saved login that cannot be used** (expired, revoked, unknown, of another cluster, or for another user name): the client deletes its credentials file and shows our notice ("Your saved credentials are out of date. Please re-enter your password."), so the next start shows the password screen. Never `0x62` (it opens the email Unlock window) and never `0x61` (it keeps the file, so the dead token would be retried at every start). The notice is our own wording for `0x0f`, `0x47`, `0x13`, `0x49` (it carries the wait) and the table's words for `5`/`6`; with an empty notice the client prints the table text. Only `0` has been seen at runtime for the rest; `0x0f` and `0x49` notices were checked in game as above.

### Password attempt limits
`[security]` in `modules/server/config/server.toml` (`modules/server/crates/poe-accounts/src/ratelimit.rs`, one `LoginLimiter` shared by the login server and the web API). Failed password attempts (wrong password, or an unknown name) are counted per account name (case-insensitive, existing or not) and per client IP (IPv6 per /64) in a sliding window `login_failure_window_secs`. At `login_max_failures_per_account` (5) or `login_max_failures_per_ip` (20) the key is locked for `login_lockout_secs`; attempts while locked are answered `0x49` before the password is checked and do not extend the lock. A right password clears the account's count (not the IP's). Token logins are not counted or refused. `0` turns a limit off. The `0x49` reply carries the wait in the notice ("... Try again in 10 minutes."), because the table text has none. The Steam dev path has no password and is not limited. The web API answers the same condition with HTTP 429 ([web-api.md](../architecture/web-api.md)).

### S→C `0x0004` AuthenticationResult (deserializer `0x14214dbe0`, handler `0x1420e841d`)
| Field | Type | Notes |
|---|---|---|
| account_id | u32 | stored in the logged-in account record (account entry +0x20, 0x78 bytes each, vector at login session +0xef0) |
| result | u16 | 0 = success; non-zero goes to the error path ([codes](#authentication-results)) |
| notice | wstring (+0x38) | **on success** (result 0, no flag below set): a non-empty notice is shown in a popup after login (so it must not carry the account name). **On an error** it replaces the table text. Language-tagged: the first part (up to the first NUL) is the default text; each later part is `NUL, <language id as one wchar>, text`. With language 0 (English) the first part is used; for another language the part whose id matches (`0x140ef5140`, `0x140ef63a0`). Official: empty (2 bytes) |
| session_token | 32 bytes | kept with the account; on the standalone path it is the Remember Me token the client saves (all zero = nothing to save) |
| account_flags | 2 bytes | split into booleans in the account entry, see [flags](#authenticationresult-flags-and-the-suspicious-activity-popup). **Not captured**: the official `0x0004` is redacted in every capture (63 bytes = 2 opcode + 4 account id + 2 result + 2 empty notice + 32 token + 2 flags + 2 name length + 17 name) |
| account_name | astring (+0x68) | the account name kept by the login session (official: 17 bytes, the `Name#1234` form). The short `0x0004` that answers a resume is 46 bytes: the name is empty |

### AuthenticationResult flags and the suspicious-activity popup
`0x1420e8511`..`0x1420e85a7` (case 4 of `ClientLoginSession_ProcessPacket`) splits the two flag bytes into ten booleans of the account entry. `LoginState_AuthenticationResultHandler` (`0x140ef5140`) and the screens read them:

| Wire bit | Entry field | Meaning (client code) | Ours |
|---|---|---|---|
| byte 0 bit 0 | +0x30 | no reader found | 1 |
| byte 0 bit 1 | +0x31 | "early league access": a league whose start time has not come is shown as started (`0x1406c19a0` picks the start time by this flag and by league flag +0xe0 bit 5); also shows a widget on the login screen (`0x140effac0`) | 1 |
| byte 0 bit 2 | +0x32 | **terms of use**: opens the ToU window after login and holds the login | 0 |
| byte 0 bit 3 | +0x33 | **cheating warning** popup (`LoginStateWarnAboutHacks`) | 0 |
| byte 0 bit 4 | +0x34 | **RMT warning** popup (`LoginStateWarnAboutRMT`) | 0 |
| byte 0 bit 5 | +0x37 | strict-unlock banner: only built when this is set on every account entry (`0x140f0f6c6` ff.); a later update hides it again while it is set (`0x140f0f690`) | 1 |
| byte 0 bit 6 | +0x38 | **strict unlocks enabled**: the character-select screen shows the red "suspicious activity" banner | 0 |
| byte 0 bit 7 | +0x35 | **update required** popup (`LoginErrorGameUpdateRequired`, title "Warning"); checked after the ToU, cheating and RMT flags | 0 |
| byte 1 bit 0 | +0x36 | per-row hook in the select screen (`0x140f060de`, calls a list widget method for characters of the account); effect not seen | 1 |
| byte 1 bit 1 | +0x39 | hides a select-screen widget (+0x6e0 of the select screen object, `0x1406c0b64`): visible only while this bit is clear. Probably an upsell button | 1 |

Order of the success path with no error and `+0x468 == 0` (the "unlock window is open" flag): save the login, then ToU (bit 2), else cheating (bit 3), else RMT (bit 4), else update required (bit 7), else the notice if non-empty, else continue to the character list (`0x140ef62c0`). If the Unlock window was open (`+0x468`) a success shows "Account Unlocked / Account successfully unlocked. You can now attempt to log in again." instead.

**The suspicious-activity popup.** ClientStrings row `StrictUnlocksEnabledMessage` (row 4307) is the red text "We have detected suspicious activity on your account. You will be required to enter login unlock codes more often until you change your password." It is put on the character-select screen by `SelectScreen_UpdateStrictUnlockBanner` (`0x140f0f600`, widget names `strict_unlock_warning_frame` / `strict_unlock_warning_label`) and made visible by `SelectScreen_ShowWidgets` (`0x140f05b20`) when:
1. the platform is **not Steam** (`ClientPlatform_IsSteam()` false; it appears only with the standalone patch), and
2. at least one account entry has **+0x38** set (account_flags byte 0 **bit 6**, mask `0x40`), and
3. the select screen's flag `+0x4b0` is clear (set once the user has unlocked the account in this session), and
4. for the frame to exist at all, no entry has +0x37 clear (byte 0 bit 5, mask `0x20`).

The default `[accounts] flags = [0x23, 0x03]` (`poe-config` default and both config files) leaves bit 6 clear, which removes the banner. Bit 5 stays set; clear it too (`0x03` as byte 0) if the banner still shows. This chain is read from code and string and has not been run.

The error code `0x1cf` (`LoginRequiresUnlockCodeStrict`) opens the Unlock window with the same red text in front. The server never sends it.

**"Get Full Access" is not an account flag.** The escape-menu button comes from the in-game InitialState flag at `+0x3edc` (`0x1420edd56`, `[accounts] full_access`), not from `0x0004`.

## Incoming packet factory
The client's login factory is `0x14214fbe0` (opcode to class, then vtable slot 2 = deserialize). Classes by opcode (vtable):

| Opcode(s) | Vtable | Size |
|---|---|---|
| 0x01 | `0x143506450` | 0x10 |
| 0x02 | `0x1435061d0` | 0x50 |
| 0x04 | `0x143509ed8` | 0x90 |
| 0x0b, 0x0d, 0x0f, 0x44 | `0x143509f18` (u32 + u16) | 0x18 |
| 0x11 | `0x14350a038` | 0x60 |
| 0x13 | `0x143509e98` | 0x18 |
| 0x14 | `0x143509f78` | 0x88 |
| 0x15 | `0x143509f98` | 0x78 |
| 0x16 | `0x143509e58` | 0x18 |
| 0x17, 0x1e | `0x14350a018` (u16) | 0x18 |
| 0x1a | `0x143509f38` | 0x30 |
| 0x1b | `0x143509fd8` | 0x38 |
| 0x1f, 0x20 | `0x143506270` (u32) | 0x18 |
| 0x24, 0x25, 0x26, 0x28, 0x29 | `0x143509e78` (string) | 0x30 |
| 0x3c | `0x143509f58` | 0x20 |
| 0x3e | `0x143509fb8` | 0x18 |
| 0x41 | `0x143509ff8` | 0x30 |
| 0x43 | `0x143509ef8` | 0x38 |
| 0x47 | `0x143509eb8` | 0x30 |

Vtable slots: 0 = destructor, 1 = serialize, 2 = deserialize, 3 = ?. The dispatcher is the switch at `0x1420e8313`, inside a function starting at `0x1420e82b0`.

## Login flow after authentication
| Step | Direction | Message | Notes |
|---|---|---|---|
| 1 | C→S | `0x0018` RequestCharacterList | `u32 account_id` |
| 2 | S→C | `0x0015` CharacterList | must carry the same `account_id` (the client drops it otherwise) |
| 3 | S→C | `0x001b` LeagueList | sent by our server right after the character list |
| 4 | C→S | `0x0010` RequestCharacterDetails | `u32 account_id, u8 index`; sent automatically for the selected character |
| 5 | S→C | `0x0011` CharacterDetails | same tail layout as the list; empty blob/pairs are accepted |
| - | C→S | `0x0012` CreateCharacter | `astring name, astring league, u32 account_id, u32 0, u32 0, wstring start_state, 32 bytes` (`start_state` is `<class>Default`-style text such as the metadata name plus `Default`; sender not decoded) |
| - | S→C | `0x0013` CharacterCreated | `u16 result (0 = ok), u8 notify, u32 account_id` (deserializer `0x14214ebf0`); then a fresh CharacterList. Result codes: [Create and delete result codes](#create-and-delete-result-codes). On 0 the create screen (callback `CreateCharacterState_OnCharacterCreated` `0x140ed2ab0`) plays the creation scene, finds the new character **by name** in the list (`0x140ec8b20`) and sends PlayCharacter (`0x140ecee50`, "character_creation_done"), so a new character goes straight into the game. Do not send `0x0016` instead (different message, handler `0x1420e8f26`, signal +0x288): a second character would leave the create screen stuck after Continue |

New characters are stored with their start area (`[player] start_area`).

### CharacterList entry fields
Wire order of one entry (reader `CharacterEntries_Read` `0x142716700`, 0x58-byte client struct): `wstring name (+0x00), wstring league (+0x20), u8 +0x4d, u8 +0x51, u8 +0x4c, u32 +0x40, u8 +0x4e, u16 +0x44, u16 +0x46, u16 +0x48, u16 +0x4a, u8 +0x4f, u8 +0x50`. `SelectScreen_SetEntry` (`0x1406b9b90`) fills one select-screen row from it.

| Field | Meaning | Official values seen |
|---|---|---|
| +0x4e (u8) | **bits 0-4: class** (`Characters.IntegerId`; drives the 3D preview and the icon `Art/2DArt/UIImages/Common/Icon<class>`); **bits 5-7: ascendancy index** (0 = none, up to 6; adds a suffix to the icon name, `0x1425ff350`) | `2` (no ascendancy) |
| +0x4a (u16) | current area: `WorldAreas.HASH16`. Looked up first (`0x1406b8e90`); if not found the row falls back to +0x48 | **0 for a brand-new character and after logging out in a town**; the zone's hash after logging out in a field zone (the intro zone, 3860) |
| +0x48 (u16) | fallback area: `WorldAreas.HASH16`; if the row is not a town the client shows its parent town (`WorldAreas` +0x70) | the intro zone (3860) for a new character; the town's hash after logging out in a town |
| +0x4c (u8) | level | 1, 2 |
| +0x4d (u8) | league banner: `LeagueFlag` row + 1 | `0x9b` |
| +0x40 (u32) | experience (same values as the Player component delta's mask `0x0001` field) | |
| +0x51 (u8) | flags: bit 3 goes to the select-screen entry (`0x1406b9b90` to `0x1406b8890`) | `0x40` (`0x00` while brand new) |
| +0x44 (u16) | **MTX portrait frame id**: 0 = `DefaultIconFrame`; non-zero = `Art/2DArt/UIImages/Common/MTX/SupporterIconFrame<id>` (`SelectScreen_SetEntryPortraitFrame` `0x1406b8460`) | 0 |
| +0x46 (u16) | **portrait variation row**: 0 = the class icon; non-zero = `Art/2DArt/UIImages/Common/PortraitVariations/<name of the row>` (`0x1425ff350`) | 0 |
| +0x50 (u8) | **`MiniQuestStates.dat` row** of the quest state, used for the "Act N" label of a row whose two area hashes find no area (`SelectScreen_SetEntryLocation` `0x1406b9010`). If both hashes are 0 the row shows a fixed text (string id 205) | 0 |
| +0x4f (u8) | stored, no reader found | 0 |

Official lists of characters that have played also carry a blob (`blob_30`, 91 to 131 bytes) and (stat id, value) pairs (`pairs_48`); a fresh character has neither.

### CharacterList trailer (and the CharacterDetails tail)
`0x0015` handler: case at `0x1420e86b4`; `0x0011` CharacterDetails has the same tail. It describes **one character, the one the select screen previews**; the handler builds an event with it (`0x1420e87e0`..`0x1420e89d2`) that reaches `SelectScreen_OnCharacterDetails` (`0x140f0c090`), which caches it per character index.

| Field | Meaning | Official |
|---|---|---|
| +0x28 (u8) | **index of the character the tail belongs to**. The handler builds the preview event only when the list has more entries than this value (`0x1420e87d5`), with `0xffffffff` otherwise. Inferred from the handler, not run | 0 |
| +0x29 (u8) | character slot limit. The select screen refuses creation when the count reaches it (`0x140f0d475`; popup `CreateCharacterButtonMaxCharactersReachedPopup`) | `0x18` (24) |
| +0x74, +0x76 (u16, u16) | passed on to the cached preview (`0x140f0c090` reads them at event +0xf88 / +0xf8a); meaning unknown | 0, 0 |
| +0x30 blob (u16 length + bytes) | the **31 visible equipment slots** (a decoded array of 31 items of 128 bytes each, `0x1420e5c10`) | 91 to 131 bytes |
| +0x48 pairs (varuint count, `u16 key, varint value`) | stat (id, value) pairs, copied into the preview event as 8-byte entries | about 33 pairs |
| +0x68 (u32) | kept in the preview event (+0xfb0); meaning unknown | 0 |
| +0x6c (u32) | **`ShapeshiftForms.dat` row** (the form the preview shows, Druid); looked up by `FUN_1423e57f0` against that table (`0x140495730`) | 0 |

### LeagueEntry (0xe8 bytes, reader `0x142716e10`)
Wire order: five wstrings (+0x10, +0x40, +0x60, +0x80, +0xa0), three u64 (+0xd0, +0xd8, +0xc8), 3 flag bytes (+0xe0), u8 +0xc0, u8 +0xc1, u8 +0xc2. After the list: a flags byte (bit 0 to +0x30, bit 1 to +0x31). Source: the official LeagueList (`dumps/0.5.5e.hotfix1/captures/official/2026-11-03_13-16-29_336`, 12 entries) plus Ghidra.

**Strings.** +0x10 id; +0x40 display name (official sends keys such as `#LeagueStandardExpedition2`; we send the display name); +0x60 = SSF-of (SSF -> its base, HC SSF -> HC); +0x80 = HC-of (HC -> base, HC SSF -> SSF); +0xa0 = third pairing slot (Ruthless in the shared code), empty officially. `0x140e7ca80` builds the 8 creation slots from these.

**Times** (unix seconds): +0xd0 start; +0xd8 early-access start, used when +0xe0 bit 5 (`0x1406c19a0` compares it with `_time64` plus the server offset `DAT_1445d8080`); +0xc8 end, checked when +0xe0 bit 4 (the banner and the Join entry drop after it).

| Bit | Meaning |
|---|---|
| +0xe0 bit 1 | hardcore (red text and banner) |
| +0xe0 bit 2 | timed event (Events panel `0x1408b3dd0`; bits 3/4/5 gate on the start/end times) |
| +0xe0 bit 4 / 5 | the end time +0xc8 / the early-access start +0xd8 is checked |
| +0xe0 bit 7 | gets a banner at character creation (**not** "permanent"; challenge leagues have it too) and is not offered in the "Join" list |
| +0xe1 bit 0 | unknown; set on Forbidden Rites |
| +0xe1 bit 1 | **variant** of the league at +0x80: no banner of its own, not in the "Join" list (`0x1406bee00`); copied to characters (+0x3ab) |
| +0xe1 bit 4 | entry faded (0.5 alpha) |
| +0xe1 bits 5, 6 | extra confirmation warnings at character creation (`0x140ece3e0`) |
| +0xe2 bits 2, 3 | SSF (`0c`); bit 2 also "green" variant / creation warning |

Official flag bytes (+0xe0..+0xe2): base `a8 00 00`, HC `2a 02 00`, SSF `28 02 0c`, HC SSF `2a 02 0c`. We send the same, plus bit 4 when the league has an end time.

- +0xc1 = league category (`LeagueCategoryToDisplayName.Id`: Standard 1, Runes of Aldur 54, Forbidden Rites 56). 1 preselects the banner at creation; we send 1 for the default base league.
- +0xc2 = `LeagueFlag` row + 1 of the creation banner (`0x140e77810` reads BannerArt/LogoArt of row c2-1). Official: 2, 3, 0x23, 0x24 = StandardFlag, HardcoreFlag, StandardSSF, HardcoreSSF; 0x97.. = Expedition2*. LeagueFlag sets are `<Set>Standard/Hardcore/StandardSSF/HardcoreSSF` (`LeagueFlagRow::variant_of`).
- Mechanics list: `CoreLeagues.Id` (13 rows: Shrines, Strongboxes, Breach, Delirium, Ritual, Expedition, Essences, RogueExiles, Spirits, StoneCircles, Abyss, Incursion, Expedition2); stored only. Raw dumps in `runtime/p3/`.
- The character-select **"Join" list** (lower right) comes from a second list (screen +0x738), not from these entries.
- **Character creation** (second and later characters; the first goes straight to the class step) starts with a league step: "Choose a league by clicking on a banner below, then click OK". `0x140e7ca80` builds one banner per entry with +0xe0 bit 7 and without +0xe1 bit 1; the HC and SSF checkboxes pick the variant through the +0x60 / +0x80 ids. Creation needs a selected league (`0x140ece3e0`, screen +0x320 / +0x318). With +0xe1 bit 1 set on every league there would be no banners and the class step could not be reached.
- **No league:** the server sends an empty list (chosen over sending none: a stale list would stay on a connected client); game test `leagues-none`.
- **Server side:** login-server `session.rs` `league_entries` sends the active leagues, the default first; hidden and ended ones are not sent. Creation refusals: 26 unknown, 55 ended, 56 closed, 139 not started.
- The **league label** under a character is grey (`0xff676767`) for every non-hardcore league and dark red for hardcore (`0x1406b95f0`). Grey is normal.
- The **league banner** comes from CharacterEntry **+0x4d = `LeagueFlag.dat` row + 1** (`0x140c7e460`). 0 or 1 give the grey event banner. The row's IsHC/IsSSF pick red or blue and the green variant. The server stores the row id per league.

## League migrations
The **League Migrations** window (`LeaguesWithProgressWindow`, button `>>` above the character list, built in `SelectCharacterState::GetLeaguesWithProgressWindow` `0x140f0def0`). Read in Ghidra and run in game (`leagues`); no official capture exists.

| Direction | Opcode | Message | Layout |
|---|---|---|---|
| C→S | `0x0019` | RequestLeaguesWithProgress (sender `0x140f0a2d0`, class `0x143506270`) | `u32 account_id`; captured `00 19 00 00 00 05` |
| S→C | `0x001a` | LeaguesWithProgress (reader `0x14214ea40`, class `0x143509f38`, session signal +0x908, handler `0x140f0b660`) | `u16 result, u32 count, LeagueEntry[count]` (no flags byte, unlike `0x001b`) |
| C→S | `0x003f` | MigrateCharacter (`0x1420eac10`, class `0x1435061f0`, serializer `0x1420e5800`) | `astring name, u32 account_id` |
| C→S | `0x0040` | MigrateLeague, the Migrate All (`0x1420ead40`, same class) | `astring league, u32 account_id`; `league` = the id of the pair's first entry |
| S→C | `0x0044` | MigrationResult (class `0x143509f18`, signal +0x788, handler `0x140f0b3e0`) | `u16 result, u32 account_id`, as DeleteCharacterResult |

**Opening.** The button (`0x140745170`; `0x1406d2510` on the other layout) calls `0x140f0a2d0`: with no cached list (screen +0x398) or Ctrl held it sends `0x0019`, at most once per 3 s (screen +0x3a0); the reply fills the cache at screen +0x380 and calls it again. An empty list prints `LeaguesWithProgressNoneAvailableMessage` in the status lines at the lower left and shows no window (when the window is open, as after the last migration, the client also closes it). `result` non-zero closes the window and opens an error dialog titled `LeaguesWithProgressErrorTitle`.

**What is listed comes from the server.** The entries are **pairs**, `[from, to, from, to, ...]` (`0x140e6f130` steps by 2; entry widget `0x140e6ddf0`): "League: {from id}", "Parent League: {to id}". The client does not check the pair against the SSF-of or HC-of fields or any flag, so **hardcore to softcore shows like SSF to trade** (seen in game). It fills each row's dropdown (`All` plus names) with the characters whose league string (+0x20) equals the from id (`0x140f0a2d0`).

**Clicking.** The row's Migrate raises window signal +0x2f0 for `All` (dialog `0x140f0e330`) or +0x2f1 for a name (`0x140f0e8c0`, with `LastCharacterMigrationWarning` when it is the league's last character); the From and To texts are the pair's ids (`0x140e6c340`). Confirming sends `0x0040` (`0x140f1acc0`) or `0x003f` (`0x140f1ab50`) and clears the cache. **Neither message names a target:** two pairs with one from league could not be told apart, so a league has one move.

**The reply.** `0x0044` non-zero shows `MigrationFailedTitle` with the code's text (`0x140f13a60`; not yet seen in game, the normal flow has no stale row to click). Zero does nothing: the client does not refresh by itself. So on success the server sends `0x0044`, the new `0x0015`, then an unasked new `0x001a` (the handler rebuilds an open window; order matters, the rows read the character list). `MigrateCharacterUnavailableError` is client text only (`0x1406c39d0`, `0x1406cc0e0`, `0x141b4bc00`).

**Server** (`login-server/src/migration.rs`): lists each league of the account's characters that has a `League::player_leave` into a league that has not ended. SSF goes first: `HC SSF Dawn` to `HC Dawn`, then `HC Dawn` to `Dawn`. Refusals: a character in game `384` AccountIsOnline (any character in the league for Migrate All; nothing moves), no move or no such character there `526` LeagueDisallowsManualMigration, unknown league `26`, another account's name `17`, no such name `16`, store error `19`. Rules: [server-admin.md](../guides/server-admin.md#leagues).

## Deleting a character
1. **C→S `0x000c` DeleteCharacter**, sent after the confirmation dialog (builder `0x140ed8149`): `astring name` (`u16` byte length + bytes), `u8 slot`, `u32 account_id`. Officially the byte is 0 and the `u32` is the account id. The byte is the low byte of a `u32` at screen +0x214 that the select screen stores when the delete screen opens (`0xffffffff` when unset; probably the list index or the local player); our server identifies the character by name and may ignore it.
2. **S→C `0x000d` DeleteCharacterResult**: `u16 result, u32 account_id` (class `0x143509f18`, shared with 0x0b/0x0f/0x44; official: `00 00` + the account id). The handler signals event +0xb88. The delete screen's callback (`0x140ed8710`) closes on result 0; any other code is looked up in `BackendErrors.dat` and shown as an error text. Until the reply arrives the dialog shows "Waiting for response...".
3. **S→C `0x0015` CharacterList**: the client keeps its old list after a delete and does not ask for a new one, so the server sends it.

## Create and delete result codes
Both results go through `BackendError_GetText` (`0x1425cb9c0`) as under [result codes](#authentication-results): the client shows the table text of the code in the create screen (`0x140ec96b0`, a message line) or the delete screen. **The packets carry no text**; the server picks the code. Official captures only contain result 0 for both; the failure codes are read from the table and the callbacks.

| Situation | Code | `Id` | Text |
|---|---|---|---|
| name already used (global) | 21 (`0x15`) | CharacterNameAlreadyExists | A character with this name already exists. |
| bad characters in the name | 22 | CharacterNameInvalid | The character name contains invalid characters. Valid names only contain letters and underscores. |
| name too short | 23 | CharacterNameTooShort | The character name is too short. |
| name too long | 24 | CharacterNameTooLong | The character name is too long. |
| unknown class / start state | 25 | CharacterInvalidClass | Invalid character class. |
| unknown league | 26 | LeagueDoesNotExist | This league does not exist. |
| bad flags (hardcore, SSF, ...) | 27 | InvalidCharacterFlags | Invalid character flags. |
| no free slot | 49 (`0x31`) | TooManyCharacters | You have no character slots left. |
| league over | 55 / 140 | LeagueHasEnded / LeagueAlreadyEnded | The league has ended. You cannot create characters in it anymore. / This league has already ended. |
| league closed | 56 | LeagueClosedForEntry | Entry to this league has closed. |
| league not started | 139 | LeagueNotYetStarted | The league has not yet started and so you cannot move. ... |
| league password | 79 | LeaguePasswordInvalid | The password is not correct for this league. |
| delete: no such character | 16 (`0x10`) | CharacterDoesNotExist | The specified character does not exist. |
| delete: not the owner | 17 | NotCharacterOwner | An attempt was made to retreive a character that this account is not the owner of. |
| delete: cosmetics still on items | 94 | CantDeleteWithMicrotransactions | Please remove all cosmetic effects from items on this character first. ... |
| any: database failure | 19 | DatabaseError | An unexpected database error occurred. Try again. |

What the server sends (`login-server/src/session.rs`): a name under 3 characters `23`, over 23 `24`, other characters than letters, digits and `_` `22` (the server accepts digits, but the client's name box already drops digits, spaces and other characters), unknown league `26`, no free slot (`[accounts] max_characters`) `49`, unknown start state `25`, name taken `21` (seen in game), store error `19`. `22`, `23` and `24` cannot be reached from the stock client (it filters characters, keeps Continue disabled under 3 characters and caps the box at 23), so only server tests cover them; `27` is named but cannot occur (the create packet has no flag field). Delete: no such character `16`, a character of another account `17`, store error `19`; the reply carries the account id in its `u32`. Never use row 1 (`AccountNameAlreadyExists`): wrong text. The `notify` byte of CharacterCreated must stay 0: when non-zero the client builds a request to `https://<web host>/api/tracking-conversions/` (`0x1420e8b41`..`0x1420e8c40`), a marketing call to the official website.

## Keep-alive and resuming
- The client keeps its login connection open while in game (unless the server sends `0x0017`, below) and sends **`0x0001` KeepAlive** (no body) every 10 seconds. The server answers with an empty `0x0001` (the factory maps it to the empty class `0x143506450`).
- **C→S `0x0008` ResumeSession**: `u32 account id, u64 token` (raw). Sent on a new login connection right after the key exchange, after the instance server's `0x174` ExitSession ("Exit to character selection"; [instance.md](instance.md#leaving-the-game)). The server redeems the ticket (`TicketRegistry::redeem_resume`, single use) and answers like a login (AuthenticationResult). The client then requests the character list.

## Hand-off to the instance server
| Message | Layout |
|---|---|
| C→S `0x0e` PlayCharacter | `u8 flags, varuint count, (u32 character_index, u32 account_id)[count]` (one entry per local split-screen player) |
| S→C `0x14` InstanceDetails | `astring host, u16 port (+0x38), u32 (+0x30), u16 area HASH16 (+0x3a, must exist in WorldAreas), u32 (+0x34), 64-byte key material (+0x3c), 8 bytes (+0x7c), u8 (+0x84)` |

- **S→C `0x0017`** (`u16` reason): the client closes its login connection (handler case in `0x1420e82b0`, `ClientLoginSession_ProcessPacket` to `0x1420e72c0` to `0x1420e7350`: `shutdown()`). Official servers send `0x0017 0x0014` right after InstanceDetails; we do not (in-game transfers use the open connection, [server-admin.md](../guides/server-admin.md#transfers)).
- InstanceDetails while the client is in an instance is received and ignored; at character selection it is followed even unasked.

Deserializer `0x14214ee60`; handler `0x1420e9078`; the instance connect (`0x14211dd30`) logs host = the string and port = struct +0x80 (packet +0x38). It uses only the host, port `+0x38`, area `+0x3a` and the key material; the byte **`+0x84`** is compared with 7 and the result kept in the instance session (`+0x2184`, meaning unknown).

## Still unknown (login protocol)
| Item | What would settle it |
|---|---|
| `0x0003` `mode` (always 2); harmless | official standalone `0x0003` capture |
| `0x0004` byte-0 bit 0 (`+0x30`), byte-1 bit 0 (`+0x36`) effect | a client run with the bit toggled (static search found no or only a vague reader) |
| `0x0004` official flag values (the DLL redacts the auth packets) | an unredacted `0x0004` capture |
| `CharacterList` +0x74, +0x76, +0x68, entry +0x4f (always 0 officially) | a capture of a Druid in a shapeshift form or with MTX portrait settings; the consumer `FUN_140ec6670` |
| `CharacterList` +0x28 as "preview index" | a capture of a list with two characters (official lists seen have one) |
| `InstanceDetails` `+0x30`, `+0x34`, `+0x7c`, `+0x84` (official `0x0014` is redacted) | unredacted capture, or the readers of session `+0x2184` |
| `CreateCharacter` the two zero `u32` and the trailing 32 bytes | decode the sender (not found by the opcode searches); official values are in `dumps/0.5.5e.hotfix1/captures/official/*/packets.jsonl` |
| Create/delete failure codes at runtime | **gate G-LOGIN**: a read-only official capture of a failed create (taken or invalid name) and a delete of a missing character; expected codes `21`, `22`, `16`. Not needed to implement; ask the user |

## Implementation notes
Login server code: `modules/server/servers/login-server`, `poe-proto`, `poe-config`. `session_token` is all zero unless Remember Me; the resume answer carries the account name. `CharacterEntry` fields are named `portrait_frame` (+0x44), `portrait_variation` (+0x46), `quest_state` (+0x50). Error codes are named once in `poe_proto::backend_error` (each with its `Id`; code = row + 1) and verified against the table at start (`codes::verify`, also a test that runs when `GameFiles/` exists). Create and delete failures print the table text (no notice exists there); login refusals keep short own notices. A test checks the `CharacterCreated` bytes (`notify` 0).

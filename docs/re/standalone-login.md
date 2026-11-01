# Standalone (email/password) login on the Steam exe (0.5.5e Hotfix 1)

How `PathOfExileSteam.exe` chooses between the Steam login (encrypted app ticket, `0x0005`) and the email/password login, what the latter sends, and how our DLL forces it. Addresses are Ghidra addresses; names are in [addresses.md](addresses.md#client-platform-and-standalone-login).

## Summary
1. **The platform is decided once, from the exe file name and the command line**, by `ClientPlatform_Detect` (`0x142197010`). A name containing `Steam` (case-sensitive) or the argument `--steam` gives platform 1. No marker gives platform **0 = standalone**. The result is cached in `DAT_144717148`; consumers read it through tiny getters. No config key, no flag, no Steam probing.
2. **The standalone path sends `0x0003`** (class vtable `0x143506250`, serializer `0x1420e3ce0`, builder `0x1420e7c70`): `u32 mode = 2`, account name (UTF-8), `client_hash[32]`, `password_hash[32]`, `machine_hash[32]`, four flag bytes. `password_hash` is plain **SHA-256 of the UTF-16LE password**, or for "Remember Me" the **32-byte `session_token` the server returned in the previous `0x0004`** (flag byte 1 = 1). No salt, no wide strings on the wire.
3. **Platform 0 also starts the standalone patcher** (window, GGG patch servers) unless the client gets `--success-event <int>` ([below](#platform-0-starts-the-standalone-patcher)). The launcher passes `--success-event 0`; the DLL patches the patcher's entry as a safety net.
4. **Patch: `ClientPlatform_Detect` returns 0** (`40 55 53` at `0x142197010` becomes `31 C0 C3`, `xor eax,eax; ret`). It is a pure getter with a cached result. With platform 0 the client shows `LoginScreen.ui`, never initialises the Steam API and does not need Steam running.
5. The platform-0 patch works in game (password and remember-me token). The residual risk is the other platform-0 consumers (about 90 getter callers, mostly UI and shop code), not read one by one.

## 1. Platform detection
`ClientPlatform_Detect` (`0x142197010`, body to `0x14219746f`), simplified:

```
exe  = basename(argv[0])                     // 0x142195bd0 (strips up to the last \ or /)
if VersionInfo ProductName == "Path Of Exile Hotcool Game Client":
    return (exe contains "Steam" or arg == "--steam") ? 3 : 2
if exe contains "Steam"  or any arg == "--steam": return 1
if exe contains "KG"     or any arg == "--kakao": return 4
if exe contains "EGS"    or any arg == "--epic":  return 5
return 0
```

| Value | Platform | Login screen | Credentials flow |
|---|---|---|---|
| 0 | standalone | `LoginScreen.ui` | `0x0003` password / saved token |
| 1 | Steam | `SteamLoginScreen.ui` | `0x0005` encrypted app ticket |
| 2 | Hotcool (Taiwan) | `HotCoolLoginScreen.ui` | `0x0003`, same path as 0 |
| 3 | Hotcool + Steam | `HotCoolSteamLoginScreen.ui` | `0x0005` |
| 4 | Kakao | `KakaoLoginScreen.ui` | `0x140ef4050` |
| 5 | Epic | `EpicLoginScreen.ui` | `0x140ef3a10` |
| 7, 8 | (never returned) | none | `0x0032` / `0x0033` token logins (`0x1420e77a0`, `0x1420e7980`), dead code on PC |

The `Steam` match is `FUN_140152460(exe, len, 0, L"Steam", 5)` (`wstring::find`, `-1` = not found); the `--steam` loop compares 7 wide characters. Strings: `L"--steam"` `0x14350cc50`, `L"Steam"` `0x14350cc60`, `"KG"` `0x14350cc6c`, `"EGS"` `0x14350cc48`.

The cache: each getter is the MSVC thread-safe-static pattern `if (guard > TLS epoch) { DAT_144717148 = ClientPlatform_Detect(); }`, guard `DAT_144717144`. Getters: `ClientPlatform_IsSteam` (`0x140109b20`, 1 or 3), `ClientPlatform_IsHotcool` (`0x140109be0`, 2 or 3), `ClientPlatform_IsTokenLogin7or8` (`0x1401af120`), `ClientPlatform_Equals` (`0x142197480`, compares with `*param`). `ClientPlatform_Detect` is called only by these and a few inlined copies of the same init (each a `[WRITE]` xref to `DAT_144717148`).

## 2. Which screen and which flow
| Decision | Function | Rule |
|---|---|---|
| Login screen | `LoginState_BuildUi_SelectLoginScreen` (`0x140ee8cb0`, branches `0x140ee9228`..`0x140ee9357`) | platform 2 -> Hotcool; Steam (1/3) -> Steam/HotCoolSteam; 5 -> Epic; 4 -> Kakao; else `LoginScreen.ui` |
| Auth start | `LoginState_StartAuthentication` (`0x140ef4c90`), after the key exchange (session state 2) | 7/8 -> `0x140ef3530`; Steam -> encrypted app ticket, callback `LoginState_OnSteamEncryptedAppTicket` (`0x140ef9ec0`) -> `0x0005`; 5 -> `0x140ef3a10`; 4 -> `0x140ef4050`; **else `LoginState_StandaloneLogin` (`0x140ef4410`)** |
| Steam API init | `FUN_140110960` ("Unable to init Steam API") | `if (!ClientPlatform_IsSteam()) return 1;` before `SteamAPI_RestartAppIfNecessary` / `SteamAPI_Init` |

`LoginScreen.ui` (`Metadata/UI/PreGameState/LoginScreen.ui`) has `username_textbox`, `password_textbox` (`mode = password`), `remember_login_checkbox`, `gateway_combobox`, `language_combobox`, `login_button`, `new_account_button`, `lost_password_button`. The Steam screen has the gateway combobox and a login button but no account fields, so `gateway_list.txt` works on both.

## 3. The credentials packet: C->S `0x0003`
Built in `ClientLoginSession_SendCredentials_0003` (`0x1420e7c70`), serialised by `Packet0003_Credentials_Serialize` (`0x1420e3ce0`). Integers big-endian, as everywhere on the login connection; sent after the key exchange, like `0x0005`.

| Field | Type | Source / notes |
|---|---|---|
| opcode | u16 | `3` |
| mode | u32 | constant `2` (object +0x30); meaning unknown, keep `2` |
| name_len, name | u16 + bytes | the account name from `username_textbox`, wide -> UTF-8 (`WideCharToMultiByte(65001)`, `0x141021120`). **Not** a wstring, no terminator |
| client_hash | 32 bytes | `LoginClientHash_Get32` (`0x1420e7700`, global `DAT_1445d5f90`); same as in `0x0005` |
| password_hash | 32 bytes | password path: `Sha256_Bytes32` (`0x1421bbec0`) over the UTF-16LE password (`size * 2` bytes), SHA-256 IV at `0x143a0c198`. Saved-login path: the 32 bytes of the credentials file (section 4) |
| machine_hash | 32 bytes | `0x1421c1580`; same as in `0x0005` |
| flag0 | u8 | password path: the "Remember Me" checkbox (`save_login`); saved-token path: 1 |
| flag1 | u8 | 0 = `password_hash` is a password hash; **1 = saved login token** |
| flag2 | u8 | `DAT_143a0c068 \| 0x40`: UI language id (0 = English, 6 / 9 other, see `0x1424a9310`) with bit 6 set; same as `flags_lo` in `0x0005` |
| flag3 | u8 | optional byte of the login state (`+0x529`, valid when `+0x52a`), 0 when unset; same as `flags_hi` in `0x0005` |

Total: 2 + 4 + 2 + len(name) + 96 + 4 bytes. `0x0005` is `u16 ticket_len, flags_lo, client_hash[32], machine_hash[32], flags_hi, ticket[...]`: the same identity block with a Steam ticket instead of name and password hash. The `0x0003` builder passes `0x15180` (86400) as the second argument of the post-send call `FUN_142198110`; the `0x0005` builder passes 0 (probably a response timeout in seconds).

Server reply: the same `0x0004 AuthenticationResult`; failures go through `FUN_140ef63a0` (section 5).

## 4. "Remember Me" is a server-issued token
- On a successful `0x0004`, `LoginState_AuthenticationResultHandler` (`0x140ef5140`) calls `LoginState_SaveLoginAfterAuth` (`0x140ef07d0`) with the **32-byte `session_token` of the packet**. If `save_login` is set in `poe2_production_Config.ini` (`[LOGIN]`) and the token is not all zero, `LoginCredentials_Save32` (`0x1423d06d0`) writes the 32 raw bytes to the credentials file and the account name goes into the ini. With `save_login` clear the file is deleted (`FUN_1423d0070`).
- On the next start `LoginState_StandaloneLogin` takes the **saved-token branch** when the password box is empty, `[LOGIN] save_login` is true, the credentials file exists (`PathFileExistsW`) and `LoginCredentials_Load32` (`0x1423d05e0`) reads exactly 32 bytes. It sends `0x0003` with that token as `password_hash` and `flag0 = flag1 = 1`.
- The file: `<Documents>\My Games\Path of Exile 2\` + `<name>`, built by `FUN_141018210` from the configuration display name (default `poe2_production`) and the suffix `_login.credentials` (string `0x14316ab08`): `poe2_production_login.credentials`. `config.json` in the working directory can override it with `GGG_CREDENTIAL_FILE_NAME` (loader `FUN_141018370`). Under our Proton prefix: `third_party/proton-prefix/pfx/drive_c/users/steamuser/Documents/My Games/Path of Exile 2/`, which also holds `poe2_production_Config.ini`.
- ini keys (`[LOGIN]`): `username` (last account name), `save_login`, `gateway_id`, `gateway_auto_select`, `hide_email`. The `account_name=` line in our prefix is written by the Steam path.
- Server rule: on password login issue a random 32-byte token, return it in `AuthenticationResult.session_token`, store a hash of it (revocable, expiry, per cluster); on `flag1 = 1` treat `password_hash` as that token. Never send an all-zero token if the client should not remember anything. Code `0x0f` makes the client delete the credentials file (`LoginState_HandleAuthenticationError` `0x140ef63a0`, not on Steam), so an expired, revoked or unknown token gets `0x0f` with a notice. Codes `0x62` (98) and `0x1cf` (463) do **not** mean "re-enter your password": they set `LoginState +0x468` and open the **Unlock window** (`UnlockWindowMessage`, id `0x5eb`; `0x1cf` puts the red `StrictUnlocksEnabledMessage` in front). `0x61` (97, `SavedCredentialsBad`) and `0x60` (96, `SavedCredentialsNewLocation`) only show their error text. The strings at `0x14351cfa0` / `0x14351d140` are the patcher's own copies. Full table: [../protocol/login.md](../protocol/login.md#authentication-results).

Launcher auto-login without any packet change: the launcher writes the 32-byte token to the credentials file, sets `[LOGIN] username=<name>` and `save_login=true`, and the DLL (or the user) presses Login with the password box empty. The DLL could hook `LoginCredentials_Load32` to return a token from `poe-hook.toml`, but `PathFileExistsW` runs first, so a file must exist anyway.

## 5. Results and errors
Non-zero results go to `FUN_140ef63a0` (`0x140ef63a0`):
- **The `notice` of the `0x0004` packet is shown as the error message when present**; otherwise the client looks the message up by code (`FUN_1425cb9c0(language, code)`). The login server can send any code with its own text.
- Special codes: `0x62`, `0x1cf` (flag +0x468, Unlock window), `0x0f` (delete the credentials file), `0x08` (Steam only: marks the Steam content corrupt, forces a patch recheck), `0x54` (popup), `0x05` (platform 7/8 only).
- **Texts come from `Data/Balance/BackendErrors.dat`** through `BackendError_GetText` (`0x1425cb9c0`, row = code - 1, language-specific copy under `data/balance/<language>/`; 715 rows). Codes `5` AccountDoesNotExist, `6` InvalidPassword, `9` NotAllowedGameLogin, `0x0c` Timeout, `0x13` DatabaseError, `0x47` AccountBanned, `0x49` LoginRateLimited, `0x4a` AccountLocked, `0x4c` TemporaryLockout, `0x60` SavedCredentialsNewLocation, `0x61` SavedCredentialsBad, `0x62` LoginRequiresUnlockCode, `0x1cf` LoginRequiresUnlockCodeStrict, `0x208` EmailLoginDisabled, `0x230` AccountNotVerified. Create/delete codes: [../protocol/login.md](../protocol/login.md#authentication-results). The 16-entry table at `0x1421ee750` (`StandalonePatcher_GetErrorText`) belongs to the patcher only (single caller `StandalonePatcher_Run`); it is not the login table.
- The success path contains a client-side report `"System or game DLLs are tampered!"` (`0x143158ae8`, sent by `0x1420e9bc0` when `LoginState +0x549 != 0 && +0x548 == 0`). `+0x549` is initialised to 0 (`0x140ee7d69`) and the only writes found are 16-bit stores of `(byte)x` to `+0x548` at `0x140ef5597` / `0x140efa855`, which leave `+0x549` at 0, so the report looks inactive; the Steam login works with `version.dll` in place.

## 6. The patch
**Patch `ClientPlatform_Detect` to return 0.**

| | |
|---|---|
| Address / RVA | `0x142197010` / `0x2196ec0` (function entry) |
| Original bytes | `40 55 53 56 57 41 56 48 8d ac 24 70 fe ff ff 48` (`push rbp; push rbx; push rsi; push rdi; push r14; lea rbp,[rsp-0x190]`...) |
| New bytes | `31 C0 C3` (`xor eax,eax; ret`) |
| Safety | Pure function of process state (argv, module file name, version resource); all call sites are the cached getters, so one patch covers every consumer |
| When | At `version.dll` load, before the first getter call (WinMain, after CRT init). `VirtualProtect` RWX, write 3 bytes, restore. Verify the original 3 bytes first and refuse (log) otherwise, like `crypto_bypass`. If the guard `*(i32*)0x144717144 != 0` (the Steam value is already cached), also store 0 into `*(i32*)0x144717148` |
| Config | `login_mode = "standalone"` in `poe-hook.toml` (default `"standalone"`; official mode forces `"steam"`); deploy writes it. Done in `poe-hook` (permanent hooks): it must be in place before the login state is built |

A getter patch, not data or a branch: the value is lazily initialised under the thread-safe-static guard (writing early is overwritten, late races), and the screen choice, flow choice and Steam init all key on the getters. A mismatch (standalone screen but Steam flow) would send a `0x0005` without an account.

**A/B test without the DLL patch:** start a copy of the exe under a file name without `Steam` (e.g. `PathOfExile.exe`), through `xtask` only. `--steam` only forces Steam, never standalone.

### Does the standalone path still need Steam?
- **Steam API init:** no. `FUN_140110960` returns 1 at once, so `SteamAPI_RestartAppIfNecessary`, `SteamAPI_Init`, the overlay hooks and the Steam Deck settings are skipped. `steam_api64.dll` stays next to the exe (mentioned at `0x142eabc00`) but is not initialised; `steam_appid.txt` is unnecessary.
- **Lost features:** Steam achievements/stats, Steam microtransaction purchase (`BuyPackSteamAsync`), Steam shop/account linking. None matter for a private server.
- **Entitlement:** no local check on the standalone path; the only gate is the server's `0x0004` result.

### Pitfalls
- No integrity check on the code was found along these paths; the DLL already patches the exe in memory (`crypto_bypass`).
- The patch only changes which login packet is built; the read-only latch and the connection guard still apply. A standalone-mode client must never be pointed at an official server.
- `gateway_list.txt`, `Bundles2/gateway_list.txt` are loaded by `FUN_140ee79c0` for the gateway combobox, not platform-specific.
- The saved-token branch needs an empty password box and an existing credentials file. With a stale file and a wrong token the server must answer `0x0f` (not `0x62`, which opens the Unlock window) or the user loops on failures.
- Tests should echo `mode = 2` and `flags`; the server must not assume other values.

### Ruled out: launcher token in the Steam packet
`0x0005` carries `u16 ticket_len` and an opaque ticket. `LoginState_OnSteamEncryptedAppTicket` (`0x140ef9ec0`) gets it with `ISteamUser` vtable slot `+0xa8` into a **1024-byte stack buffer** (`local_428[1024]`, capped at `0x400`), copies it into a vector at `LoginState +0x298` and sends it via `0x1420e7f80`; the wire allows 65535 bytes. The client does not validate the ticket locally (only Steam success codes: `Steam: Unable to get encrypted app ticket`, `Not connected to steam`, rate limit `0x19`, duplicate `0x1d`). A token could replace the ticket bytes or ride in `flags_hi`, but Steam must run and be logged in, the login screen has no account field and there is no password path. The platform-0 patch gives a real account screen, needs no Steam, and the saved 32-byte token is a ready launcher channel.

## Platform 0 starts the standalone patcher
With platform 0 the exe first acts as the **standalone patcher launcher** (window "Language", news pane, progress bar, LAUNCH button; `Client.txt`: `Started patching (N free bytes available)`) and contacts GGG's patch servers. This must never happen with our client.

**What decides it.** `Client_Startup` (`0x14011b820`) calls `StandalonePatcher_Run` (`0x1401162d0`, call at `0x14011bf76`; returns `bool`, 0 = quit) and then `CmdLine_ReadSuccessEvent` (`0x140117c40`). `StandalonePatcher_Run`:
1. `ClientPlatform_IsSteam()` true: return 1 (why the Steam build never shows the patcher). Platform 5 (Epic): return 1.
2. Otherwise loads the patch server list from the config singleton (`FUN_14010ac40`, built by `FUN_14010aca0`: `us.patch.pathofexile2.com` `0x142f76fd0`, `patch/patch2/patch3.pathofexile2.tw`, `kr-patch.pathofexile2.com`; platform 2 and `--kakao` pick other lists) and applies `--patching-server`.
3. **Skip test:** if `--disable-client-switching` is absent **and** `--success-event` is present, it returns 1 without opening anything (`0x140116a43`..`0x140116be9`, `bVar3`).
4. Else it opens the patcher window (`MainWindowClass`, `FUN_1428ca830`/`FUN_1428cbc70`, `RegisterClassW`, "Could not create the User Interface for the patcher") and runs `Patcher_RunPatching` (`0x142737860`: "Started patching (...)" `0x14358d0e0`; patch server, `/launcher/patch/start|success|fail`, `/client/record-patching-metrics` in `FUN_142737300`). With `--require-launch` the user must press LAUNCH.

The skip test is the real protocol: the patcher starts the client with `--success-event <inherited event handle>` and waits on the event. `CmdLine_ReadSuccessEvent` parses the number (`FUN_1423cd360`, `wistringstream >> int`, so it must be an integer) into `DAT_144431668` (initially -1). At the end of `Client_Startup` (`0x14011c916`) a handle `!= -1` gets `SetEvent` and `CloseHandle` and is reset to -1. With `0` both calls fail (`ERROR_INVALID_HANDLE`, nothing is closed). **Do not use a small positive number**: it could be a real handle of the process.

**Command line (`CmdLine_BuildOptionTable` `0x140110d60`, parser `CmdLine_ParseArgs` `0x1423cc3e0`).** Options (type 1 = flag, 3 = takes a value): `--no-agility-sdk`, `--no-nv`, `--no-lmdb`, `--login-port <n>`, `--patching-server <host>`, `--patching-auth <x>`, `--prev-proc-id <pid>` (waits for that process to exit, 15 s, then "Timed out waiting for patching process to exit."), `--require-launch`, `--fail`, `--nosound`, `--softwareaudio`/`-swa`, `--success-event <handle>`, `--24h2-mt`, `--test-*` (job queues, descriptors, frame graph, ...), `--force-safe-frame-graph`, `--device-resource-manager`, `--disable-static-entities`, `--descriptors-keep-alive`, `--descriptors-validate`, `--flush-descriptors`, `--flush-resources`, `--no-device-recovery`, `--enable-dx12-pso-cache`, `--disable-dx12-pso-cache`, `--nologo` (skips intro video), `--kakao`, `--disable-assert-box`, `-AUTH_PASSWORD` and `-epiclocale` (platform 5 only), `--language`/`-lang` (not Hotcool), `--use-defaults`, `--disable-client-switching`/`--dcs`. Values: `--opt value` or `--opt=value`. **There is no `--nopatch`**; unknown options only log `[CMD][Unrecognized] <arg>`.

**Other network behaviour.** All patch access is reachable only through `StandalonePatcher_Run`: `Patcher_RunPatching` has that single caller; the metrics sender `FUN_142737300` is called only from `FUN_142733d30`, whose only caller is `Patcher_RunPatching`; `/launcher/patch/*` (`FUN_1428ccb70`) belongs to the patcher UI. `FUN_14011a370` (reads the config singleton, called early from `Client_Startup`) has no network callee (strings, `LoadStringA`, file name helpers). Skipping `StandalonePatcher_Run` removes every patch-server access found; URLs opened by the remaining platform-0 getter callers are browser/shop links.

**Fix, layered:**
1. **Launcher flag (primary).** `poe_hook_deploy::launch::client_args` adds `--success-event 0` to the Proton command line when the installed `poe-hook.toml` has `login_mode = "standalone"` and `mode != "official"`. Manual start: `PathOfExileSteam.exe --success-event 0`.
2. **DLL safety net.** In `login_mode = standalone` the loader checks `GetCommandLineW`: if the client's own test would still run the patcher (`--success-event` missing, or `--disable-client-switching` present) it replaces the first three bytes of `StandalonePatcher_Run` (`48 8B C4`, `mov rax,rsp`) with `B0 01 C3` (`mov al,1; ret`), after verifying them. Failure is logged as an error (`standalone patcher NOT skipped, it would contact GGG patch servers`); success logs `standalone patcher skipped by the client itself`. Not applied in Steam or official mode.
3. Ruled out: returning platform 1 to the patcher only (two answers from one getter needs a caller check and breaks the cache); patching `FUN_14010ac40` data (the window would still appear).

Official mode keeps `login_mode = steam`, so none of this runs there.

**Window title (debug core).** `POE_HOOK_WINDOW_TITLE` renames only windows of class `POEWindowClass` (the game window, `Window_CreateMain_POEWindowClass` `0x141050c30`; the patcher uses `MainWindowClass`, message boxes `#32770`): the `CreateWindowExW` hook compares the class name argument, the `SetWindowTextW` hook calls `GetClassNameW`.

## Checks
Confirmed in game: the `0x0003` login with a password and with a remember-me token, `poe2_production_login.credentials` in the prefix, no patcher (`Client.txt` has no `Started patching`, `[CMD] --success-event` is logged, no `patch.pathofexile2.com` lookup: check with `ss -tnp` or the guard log). Not checked:
- **Tamper report:** break on `0x1420e9bc0` (sender) and `0x140ef5541` (`cmp [rdi+0x549],0`); expect it never to fire with `version.dll` loaded. If it does, find the writer of `LoginState +0x548`.
- **Flag bytes:** what sets `LoginState +0x529/+0x52a` (`flag3` / `flags_hi`); break on `0x140ef4afa` / `0x140ef48a9`; expected 0.
- **Result codes:** `5` and `6` should give "account does not exist" / "password is not correct" when the notice is empty; `0x62` opens the Unlock window.

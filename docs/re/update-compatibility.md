# Update compatibility: what breaks when GGG ships a new client build

What breaks when a game build changes. The signature table, `cargo xtask check-build` and the version files are in [client-dll.md](../architecture/client-dll.md) and [new-game-version.md](../guides/new-game-version.md).

## Still open
- `gen_batch.rs` `WORLD_SIZE`, the `ClientWorld` allocation size, is a literal; a build that grows the world overflows the heap in batch runs (0.5.5f: `0x17e8` to `0x1810`, crashes in `0x1416859c0`). Read it at `0x141014047` on every build.
- Struct offsets listed as literal in client-dll.md (terrain cell grids, tile record internals, generator-trace object layouts, diagnostic reads, component indices 0 and 9).
- Runtime sanity checks after resolution (position inside the terrain; the side-channel key against the server's first report); a failed tile-hash check flagging the export (row 15).
- `symbols.tsv` per build (row 20); the opcode/layout drift report beyond the server-to-client deserializer fingerprints.
- `cargo xtask sig-gen` (the generator stays `scripts/re/sig_gen.py`).
- Renumbered opcodes and client-to-server layouts are not derived from the exe; the factory is not found by the `Unable to deserialise packet` string (its address and switch numbers come from Ghidra and `find_switches.py`).
- Row 11's ids instead of rows in config and code; row 14's format-version checks (`.tgr` and others); a pinned schema download; the DLL selecting its opcode tables by the resolved build (it uses `poe_proto::opcodes::latest()`); a side-channel hello carrying the DLL's resolved build (only the login channel is protected).
- The `client_hash` is the exe's sha256 (confirmed with a real standalone login on 0.5.5e Hotfix 1; `hashes_confirmed = true`). The refusal (code 8 popup) and `allow_unknown_client` were checked in game too.

## The first real update: 0.5.5e Hotfix 1
GGG's first build after the signature tooling was **0.5.5e Hotfix 1** ("Fixed a bug where minimap landscape geometry could fail to render correctly", client only). What the tools found:
- **Identity:** exe 78,336,856 bytes, sha256 `d46f4c27...a455d`, PE timestamp `0x6ae12470` (image size unchanged `0x4ca0000`), build revision `326410`. Steam manifests: content `4712263798014036045`, exe `4973272861086296374`. The previous 0.5.5e exe: sha256 `7157984534da1b146e9b0be342aa9fd24272915b6f478aadef9830fc7873f89f`, 78,335,832 bytes, PE timestamp `0x6ac302e0`, revision `323943` (string at file offset `0x350b509`; a May session printed `304532`), manifests content `7366357142270402355` (`2694491`), exe `246779027001700092` (`2694492`).
- **`check-build` with the 0.5.5e table:** all 115 signatures and 64 struct offsets resolved uniquely (106 at moved addresses), all 16 features on, every server-to-client deserializer fingerprint unchanged, all game-data checks passed. Only identity and key-file sizes differed, and the revision pattern no longer matched (the `" 326410"` string now follows `%S.poecap` instead of preceding it).
- **Code:** `scripts/re/addr_map.py` aligned 154,521 of 154,537 functions by size; code moved in runs by +0x0 to +0x2d0. 16 functions changed (10 changed bodies, 6 merged away), all undocumented: around `0x141010ea0`, `0x141211730`, `0x14121a400`, `0x14134b380`-`0x14134ccb7`, `0x14219ddce`-`0x14219deb0`, `0x1421cd290`-`0x1421cd850` (0.5.5e addresses). Nothing in the terrain generator (`0x141f…`) changed.
- **Data** (`scripts/re/bundlediff`): 36 files added, 28 removed, 173,868 changed, almost all texture `.header` files (173,857), plus 8 `.fmt` models, `metadata/exe_hash_*.txt`, one monster `.ot`; added: a telescope object in the act 5 town (`metadata/terrain/gallows/act5/5_town/objects/towntelescope.ot`, its `.ao`, model) and renamed portal effects. No `.datc64`, `.tgr`, `.dgr`, `.tdt`, `.tmd` or `.arm`: the server's tables and terrain inputs are byte-identical, so the terrain vectors stay valid.
- **Work needed:** a new signature table (the old spec with every address moved by the map: patterns identical, `sig_gen.py` output differs only in `[build]` and addresses), a new version file sharing the 0.5.5e opcode folder, the server's `[game] version`, and test fixtures that named the newest version. The name is `0.5.5e.hotfix1` (not `0.5.5e-hotfix1`): release file names allow only letters, digits, dots. Procedure: [../guides/new-game-version.md](../guides/new-game-version.md).
- **In-game check:** `scripts/test-run.sh` on the hotfix copy: the DLL logged `table 0.5.5e.hotfix1: timestamp ok, size ok, revision 326410` and every feature `ok`; standalone login screen, token login, hand-off, G1_1 (client tile hash 1866332366) and click-to-move worked. The login server logged no `client_hash cannot be checked yet` line, so `hashes_confirmed = true`, `status = "supported"`. Not repeated for this build: the refusal of another build and an official read-only session (the user's).
- **Ghidra:** the hotfix exe is `/0.5.5e.hotfix1/PathOfExileSteam.exe` with the old program's names, signatures, comments and data types ported by the address map (`scripts/re/ghidra/PortFromAddrMap.java`; Version Tracking failed, [README.md](README.md#a-new-build-in-the-ghidra-project)).

## The second update: 0.5.5f
GGG's next build, revision `328049`, is not the supporter-pack-only patch it looked like. What the tools found:
- **Identity:** exe 78,440,792 bytes, sha256 `7e0d3665...7c834e`. Steam manifests: content `5662192306551403401`, exe `3411296386151915616`.
- **Protocol:** instance opcodes from `0x2ef` up moved +3, from `0x35d` up +4; the client-to-server ones were derived the same way and confirmed by the game tests. `InstanceDetails` has a new string ([login.md](../protocol/login.md)); the class of `SocialEntry` grew with an unchanged deserializer; unnamed classes `0x29`, `0x238`, `0x1f1` changed. Old tables stay in Poe2Protocol `capture-opcodes/0.5.5e.hotfix1/` to replay old captures.
- **Client:** the image moved, `instance_ciphers` was inlined (now a site with `session.key_material`, `+0x58`), and `World` grew (`+0x98..0x665` +8, `0x666` +0x2a, `0x668..0x680` +0x2c, `0x690` up +0x28).
- **Data** (`dumps/0.5.5f/bundlediff.tsv`): 699 `.datc64` changed (171 English tables), 2 `.ot`, 2 `.arm` (`past_town_01`, `kalguur_dock_town`), 64,272 files added; 1,040,488 shader cache files are `unread` (their bundle is not on one side). `WorldAreas` went from 442 to 448 rows (four hideouts with layouts, `PlayerAtlasHideout` and `PlayerAtlasHideoutInert` without).
- **Terrain:** the port needed no change ([terrain.md](../status/terrain.md#results)). The batch crashed in `gen_batch` until its literal `WORLD_SIZE` was raised.
- **Ghidra:** `/0.5.5f/PathOfExileSteam.exe` has the names, signatures and data types (`PortFromAddrMap.java`: 795 data types, 917 of 1,104 named functions right, 2 created; the rest are loader and CRT names under other addresses). Four game functions the address map missed were placed by masked bytes: `Player_SimulationHandler`, `Mt19937_Next`, `PartyInvitePopup_Accept`, `PartyInvitePopup_Decline`.
- **Addresses not carried over:** these in the docs predate Hotfix 1 or sit in code the address map cannot place, so they are not 0.5.5f addresses; read them again before use: `0x14019ad14`, `0x14020ad50`, `0x14020ad94`, `0x14025613c`, `0x1416d5080` (movement-click.md), `0x140286850`, `0x140c75310`, `0x1420e9a64` (addresses.md), `0x141cc9a30` (washed-up.md), `0x1420e8c40`, `0x143509e78` (login.md), `0x142125446` (world-travel.md), `0x142f08770` (tgr.md), `0x1431c9e10` (movement-sprint.md).

## How to read the table
Patch kinds:
- **D** = data-only patch. `Bundles2` changes, the exe is byte-identical.
- **H** = hotfix with a rebuilt exe. Functions move and stack frames change; most bodies stay the same. The common case.
- **M** = major patch (new league, 0.6). Messages, components and generator passes change.

Ratings L/M/H (low/medium/high), written D/H/M. Detection: **easy** = fails at start-up with a log line or crash; **hard** = runs, something is wrong later; **silent** = nothing logged.

## Ranked table (highest risk first)
| # | Item | Break D/H/M | Failure mode (detection) | Mitigation / status |
|---|---|---|---|---|
| 1 | DLL hooks at fixed addresses: `dump_types`, `terrain_tools`, `packets`, `protocol`, `side` (about 45 sites) | L/H/H | Crash on a wrong target, also in official mode, or a hook that never fires (easy at start-up, hard at area load) | Done: all hooks come from the signature table, verified, per-feature disable; features fail closed |
| 2 | Mid-function sites: `FLUSH_PLAINTEXT` `0x1421a8007`, `ROOM_CANDIDATES` `0x141f9d4e5`, `DOODAD_HASH_SITE` `0x142001df3` | L/H/H | Hook inside an instruction (crash) or registers with other values (silent bad data) | Done: `site` signatures with anchor + offset + expected bytes and an instruction-boundary check |
| 3 | Login patch: `ClientPlatform_Detect` `0x1421a6e90`, `StandalonePatcher_Run` `0x140118c10`, platform cache `0x14472f634`/`0x14472f638` | L/H/H | Wrong function patched (3-byte check), Steam screen stays, or a 4-byte write to a wrong global (easy if the screen is wrong; hard if corrupted) | Done: unique function patterns + exact `expect` bytes; cache globals are `ref` entries |
| 4 | Side-channel key hook `0x14212ac10` (`side.rs:29`), argument order `(out, material, &is_client)` | L/H/M | Wrong target crashes; wrong argument register gives wrong keys, so the server drops every report (silent) | Target is a signature. Not done: checking the 64 bytes against the server's session key at the first report |
| 5 | Crypto bypass: prologue pattern (`crypto_bypass.rs:23`), key buffer `+0x60` (`:28`) | L/H/M | Pattern fails: logged, login refused. `+0x60` wrong: handshake garbage (easy) | Done: stack immediates wildcarded; `+0x60` is the `crypto.key_buffer` field (found in the DH-agree routine) |
| 6 | Opcode tables `modules/protocol/opcodes/0.5.5e.hotfix1/*.toml` (login 22 named, instance 75 named, `client_body_sizes`) | L/M/H | A message id means another message: wrong parse, or "Unable to deserialise packet" (the client drops the link); redaction by name stops working (hard) | Partly: `check-build` fingerprints the server-to-client deserializers (renumbering is not derived); per-version opcode dir and `poe_proto::opcodes::EMBEDDED` |
| 7 | Message layouts in `poe-proto` (`login.rs`, `instance.rs`, `skill.rs`, `remote.rs`) | L/M/H | Fields shift: garbage values or disconnect; the client does not check a message is fully consumed (hard) | Replay tests against official captures per build; reader fingerprints |
| 8 | `InitialState` / `AddObject` blob layouts and component order (`entity.rs`, `player_blob.rs`, `docs/protocol/entities.md`) | M/M/H | Components misread; wrong stats, client crash; component order comes from the `.ot` data (hard) | Reader-span self-test with the DLL's `entity_trace`; order from `.ot` instead of code |
| 9 | Struct offsets read by the DLL (Positioned, Actor, Entity, stream, world, terrain; section 2) | L/H/M | `position_sync` reports garbage (silent); exports wrong | Done for the offsets the table lists (client-dll.md). Not done: runtime sanity check (position near terrain) |
| 10 | Hard-coded component indices: Positioned = 0, Actor = 9 (`position_sync.rs:87-90`, `actions.rs:50`, `dump_types.rs:508`) | M/L/M | Reads another component's memory (silent) | Look up by name with `entities::component_names` once per entity |
| 11 | Data row indices as keys: `sprint_buff_rows` `[2758, 2737, 2853]` (`modules/server/config/server.toml:48`, `poe-config/src/lib.rs:444-459`), `Stats` row + 1 (`views.rs:175-179`), `Inventories` row = slot (`views.rs:136-154`), `ActionTypes` 2nd column (`views.rs:182-189`), `Move` `0x20002909` (`poe-game/src/world.rs:258`) | H/M/M | Wrong buff, stat or slot ids: wrong sprint effects, broken inventories (silent) | Partly: `check-build` verifies the row anchors (`Stats`, `ActionTypes` `Move`, `Inventories`, the sprint buffs) and the config's rows; ids are not yet stored instead of rows |
| 12 | dat schema `third_party/dat-schema` (rolling `latest`, `fetch-tools.sh:15-17`) and table columns | H/M/M | Column names or widths drift; a wider schema only warns (`dat.rs:97-103`); positional access reads wrong data (hard) | Partly: `check-build` checks every used table and column (`poe_data::used`), row width and the schema's sha256 pin; `fetch-tools.sh` warns on a different schema but cannot fetch a given release |
| 13 | Version plumbing: `game.version` is a label; `v0_5_5e` module (`poe-proto/src/opcodes.rs:11`); `0.5.5e` in login-server tests, `xtask`, config defaults | M/M/M | Mixed tables from two builds; dumps in the wrong folder (silent) | Done: `modules/protocol/versions/<ver>.toml` is the single source for xtask, the server (`[game] version`, `{version}` in paths, `protocol_dir` default) and the launcher (byte-identical copy, `cargo xtask versions`); the server refuses an unknown client hash |
| 14 | Terrain generator port (`poe-world`, 14,800 lines, 500 address refs) and data formats (`.tgr` version 25, `.dgr`, `.tdt`, `.ot`) | M/M/H | Layouts differ from the client's: walls and spawn wrong; data patches change tile sets even with an unchanged exe (hard; the client logs `Tile hash` / `Doodad hash` as an oracle) | Re-run vectors per build; `check-build` reports stale `terrain-vectors.tsv` by its `build` column |
| 15 | Terrain export hooks and offsets (`area_export`: world `+0x98/+0x1b4/+0x114/+0x118`, terrain `+0x18/+0x20/+0x28`, tile record `0x38`, grid `+0xd0/+0xe8/+0x100/+0x118`) | L/H/M | Wrong layouts exported to the dump dir (easy: the export re-checks the client's tile hash, `terrain_tools.rs:1050`) | Keep the hash check; make a failed check flag the export |
| 16 | HNC table: `key_xor` and `swaps` (`opcodes/0.5.5e.hotfix1/hnc.toml`, exe `0x142f23aa0`, `0x1421d5170`); Salsa20 key/IV split (`poe-net/src/cipher.rs:40`) | L/L/M | Our side of the HNC channel cannot decode (the client disconnects after `0x1c`; easy) | Done for `key_xor`: `check-build` re-extracts the 64 bytes and compares. The `swaps` are not re-derived |
| 17 | Packet capture stream offsets (`packets.rs:333-440`, `protocol.rs:102-123`) and caller ranges `LOGIN_READER`/`INSTANCE_READER` (`packets.rs:41-42`) | L/H/M | Wrong messages or channel in captures; no crash (guarded reads) (hard) | Done: offsets are fields; the channel is the `.pdata` range of the two session loops |
| 18 | Packet redaction by opcode name (`packets.rs:198-211`) | L/L/H | After a renumber, secrets reach `packets.jsonl` (silent) | Done: `Credentials` added and every login message is redacted on an unverified build (`redact.rs`) |
| 19 | Launcher `modules/protocol/versions/*.toml`: depots, manifests, sha, key sizes | L/H/H | Steam may remove an old manifest (download fails); `verify` only warns (easy) | Done: the launcher reads the shared file (`[exe]` section) and embeds every file of `modules/protocol/versions/` (`build.rs`); `status` is parsed by the server only. Play still does not compare the exe with the DLL's table |
| 20 | `symbols.tsv` (585 names) and `addresses.md` | L/H/M | Misleading names in crash logs and the Protocol page (hard) | Embed the table by build id with a build header; `export_symbols.py` takes a version |
| 21 | `Client.txt` parsing: `Generating level ... with seed`, `Tile hash:`, `Doodad hash:`, `Build Revision:` (`scripts/re/clientlog_terrain.py:13-16`, `clientlog_entries.py:13-19`, DLL `gamelog.rs`) | L/L/M | Scripts give 0 vectors; the Game log page empties (easy: count printed) | Use `Build Revision` as the version key |
| 22 | Command-line options `--success-event`, `--disable-client-switching` (`login.rs:38-41`, `login_patch.rs:64`), `config.json` / credentials file name | L/L/M | The patcher window appears and talks to GGG patch servers (the guard blocks external connects in private mode; easy) | Done: `StandalonePatcher_Run` signature is the safety net; `check-build` checks the option strings (`[client] strings`) |
| 23 | Data pointer `0x1445f0768` (game window handle) in `auto_keys.rs:473`; `trace_calls` / `POE_HOOK_TRACE` addresses | L/H/L | Test injection only: wrong focus for the aim check | Resolve by pattern or drop |
| 24 | Scripts with fixed addresses: `dump_factory.py` arguments (`d 35f 217305c 142173040`), `export_symbols.py` file names | L/H/L | The tool dumps wrong tables (easy) | Partly: `dump_factory.py` takes an index table (`--bytes`), `find_switches.py` prints its arguments; the factory is still found by hand (could use the string `Unable to deserialise packet`) |
| 25 | Win32 and Vulkan hooks (ws2_32 `connect`, `GetRawInputData`, Vulkan loader), `version.dll` proxy exports | L/L/L | None expected | None |
| 26 | `poe-hook-deploy` constants: `PathOfExileSteam.exe`, `gateway_list.txt`, app id `2694490` (`lib.rs:39-51`) | L/L/L | Deploy fails or copies to the wrong file (easy) | Take from `modules/protocol/versions/<ver>.toml` |

## 1. Fixed Ghidra addresses

### 1.1 Where they live
| Group | Files | Addresses |
|---|---|---|
| Login patch | `poe-hook-shared/src/login.rs:13-35`, `poe-hook/src/login_patch.rs:85,121,141-142` | `ClientPlatform_Detect` `0x1421a6e90`, cache guard/value `0x14472f634`/`0x14472f638`, `StandalonePatcher_Run` `0x140118c10` |
| Crypto bypass | `poe-hook-core/src/crypto_bypass.rs:23` | pattern only; same function as `0x1421aefe0` |
| Side channel | `side.rs:29,45-50` | `0x14212ac10` |
| Packet capture | `packets.rs:37-42`, `protocol.rs:31-32` | `0x1421d5a10`, `0x1421a8007` (mid-function), `0x14212eb20`, `0x1421a7d00`, `0x1421a7e30`, caller ranges `0x1420f5c10..0x1420f6186`, `0x14212fe10..0x142130855` |
| Entity and world research | `dump_types.rs:27-62` (installs `:67-95`, calls `:668-696`), `entities.rs:19` | `0x14169bf40`, `0x141e7f190`, `0x141e7f100`, `0x14010c9b0`, `0x141683940`, `0x14213e730`, `0x14339a108` (vtable), `0x141de5b50`, `0x14213f8f0`, `0x141e8b960`, `0x141de99d0`, `0x141687120`, `0x1401558b0`, `0x1416b2160`, `0x141df2770`, `0x141d19fd0` |
| Terrain export and trace | `terrain_tools.rs:40-121` (installs `:171-200`) | 32 more, including `0x14200d1f0`, `0x142005f20`, `0x142001df3` (mid-function), and the whole generator trace set |
| Window handle | `auto_keys.rs:473` | data `0x1445f0768` |
| Trace | `trace_calls.rs:29`, `POE_HOOK_TRACE` | any address typed by the user |
| Symbols | `symbols.rs:24` (`assets/symbols.tsv`, 585 lines) | names for Ghidra addresses |
| Docs | `docs/re/addresses.md`, `docs/re/terrain/*.md`, `docs/protocol/*.md` | the knowledge itself |
| Server crates | 500 address mentions in `modules/server/crates/poe-world`, 139 in `modules/protocol` | comments only (where the algorithm came from); no runtime dependency; starting points for re-deriving a changed algorithm |

### 1.2 What a wrong address does
- `hooks::install` copies the first 16 bytes and calls `ilhook` (`hooks.rs:45-58`), which disassembles the target; a non-instruction boundary relocates garbage. `report()` (`lib.rs:120-130`) logs an error when `install` returns `Err`, but `install` returns `Ok` for almost any readable address. The signature table with expected bytes is the fix.
- The login patch checks only **3 bytes**; 1,167 functions begin with `40 55 53` and 6,590 with `48 8b c4`, so it proves a function start, not this function.
- `login_patch.rs:141-148` reads the cache guard at `0x14472f634` and, when non-zero, writes 0 to `0x14472f638`; if only data moved, this is a stray 4-byte write.
- `crypto_bypass` uses a 40-byte prologue pattern, requires exactly one match, and fails with a log line: the model for the others.

### 1.3 Uniqueness test (offline, no Ghidra)
Each address was disassembled with capstone, `rel32`/`disp32` of calls, jumps and RIP-relative operands and image-address-like `imm` values wildcarded, and the pattern grown one instruction at a time until unique in `.text`; a second run also wildcarded `sub rsp, imm` and `lea reg, [rsp+disp]`. Result: 44 of 47 unique both ways; 3 not unique within 40 instructions, template-like clones: `0x14169bf40` (object-type lookup, unique after 86 instructions, 310 bytes), `0x1401558b0` (Render component by name, unique after 50 instructions), `0x141d19fd0` (terrain height; two copies). They need an anchor: a unique caller, a string, or a constant (the `0x30` entry size for the lookup).

Unique patterns for load-bearing addresses (0.5.5e bytes; `??` is a wildcard):

| Name | Ghidra | Length | Pattern |
|---|---|---|---|
| `ClientPlatform_Detect` | `0x1421a6e90` | 27 | `40 55 53 56 57 41 56 48 8d ac 24 ?? ?? ?? ?? 48 81 ec ?? ?? ?? ?? 48 8d 4c 24 ??` |
| `StandalonePatcher_Run` | `0x140118c10` | 33 | `48 8b c4 48 89 58 10 4c 89 40 18 48 89 48 08 55 56 57 41 54 41 55 41 56 41 57 48 8d a8 18 fa ff ff` |
| side-channel builder | `0x14212ac10` | 41 | `48 89 5c 24 10 48 89 6c 24 18 48 89 74 24 20 48 89 4c 24 08 57 48 83 ec ?? 49 8b f0 48 8b ea 48 8b d9 33 ff b9 10 00 00 00` |
| verify-and-derive | `0x1421aefe0` | 29 | `40 55 53 56 57 41 54 41 56 41 57 48 8d ac 24 ?? ?? ?? ?? 48 81 ec ?? ?? ?? ?? 4d 8b f0` |
| message reader | `0x1421d5a10` | 29 | `48 8b c4 48 89 50 10 48 89 48 08 53 56 57 41 54 41 55 41 56 41 57 48 81 ec 90 01 00 00` |
| session send | `0x14212eb20` | 33 | `48 89 5c 24 10 48 89 6c 24 18 48 89 74 24 20 57 48 83 ec 30 48 8b f2 48 8b e9 48 8b b9 f8 20 00 00` |
| stream read | `0x1421a7d00` | 29 | `48 89 5c 24 08 48 89 6c 24 10 48 89 74 24 18 57 48 83 ec 60 49 8b f8 48 8b ea 48 8b d9` |
| stream write | `0x1421a7e30` | 27 | `48 89 5c 24 08 48 89 6c 24 10 48 89 74 24 18 57 48 83 ec 40 48 8d b9 80 02 00 00` |

Cautions:
- **Neighbours with the same prologue.** `0x14212ac80` (the HNC builder) starts with the same `mov [rsp+0x10], rbx` as `0x14212ac10`; only later instructions (`b9 10 00 00 00`, the `call`) separate them. Always check uniqueness and report the match count.
- **Short patterns are lucky.** `SET_ORIENTATION` is unique at 12 bytes (`40 53 48 81 ec 60 01 00 00 0f 28 c1`) and `FRAME_DRAIN` at 11 bytes; they hold only while the stack frame stays the same. Require at least 24 bytes or include body instructions.
- **Mid-function sites** (`0x1421a8007`, `0x141f9d4e5`, `0x142001df3`) are unique at 11 to 21 bytes only because the pattern started at the site. Anchor to the enclosing function's signature plus an offset and check the expected bytes (flush site: `48 8b 93 60 02 00 00 48 8b bb 58 02 00 00`).
- **String anchors survive a rebuild better than prologues:** `"General Rhoa Failure #3"` (verify-and-derive), `"HNC Protocol Violated"`, `"Generating level"`, `"Tile hash"`, `"Doodad hash"`, `"Unable to deserialise packet"` (message reader and factory), `"Connecting to instance server at {}:{} "`. A `string_xref` signature kind (find the string in `.rdata`, the `lea` that references it, the function start from `.pdata`) is the fallback when a prologue is ambiguous.

## 2. Struct offsets
| Struct and field | Offset | Used in | Production or research | Derivable from an instruction? |
|---|---|---|---|---|
| Entity: component vector | `+0x10`/`+0x18` | `entities.rs:75,167`, `position_sync.rs:87`, `actions.rs:50`, `inspect.rs:29` | `position_sync` is production | Yes: `GetComponent` by name `0x1401558b0` and the entity update loop |
| Entity: id, type, world | `+0x88`, `+8`, `+0x78` | `entities.rs:118,143`, `dump_types.rs:212,637` | research | Yes: `Entity_ReadInitialState`, `Entity_Destroy` use `+0x88` |
| Entity: type's component lookup | `+8` -> `+0x28`, array `+0x28..+0x30` of 16-byte `{char*, i32}` | `entities.rs:143-168` | research | Yes: `0x1401558b0` |
| Positioned: grid | `+0x444`, `+0x448` | `entities.rs:133`, `inspect.rs:41`, `dump_types.rs:487` | production | Yes: `lea rbx,[rsi+0x444]` at `0x141de5c52` |
| Positioned: world | `+0x490`, `+0x494` | `position_sync.rs:94-95`, `entities.rs:134` | **production** | Yes: `mov [rsi+0x490], ecx` at `0x141de5f49` |
| Positioned: facing, lock | `+0x44c`, `+0x1e5` bit 1 | `entities.rs:135`, `inspect.rs:43-44` | research | **Yes, best example:** `SetOrientation` has `f6 81 <D1:4> 02` then `c7 81 <D2:4> 00 00 00 00`; unique as a 37-byte pattern |
| Actor: WASD direction | `+0x400`, `+0x404` | `inspect.rs:48-49`, `dump_types.rs:520` | research | Probably: stores in the `0x64` case of `0x142158b60` |
| Actor: action slots, action type | `+0x238`, `+0x240`; action `+0x120` | `position_sync.rs:99`, `actions.rs:50-58` | **production** | Probably: `0x14211e950` / `0x141e5da30` |
| Actor: sprint key bit | `+0x2a2` bit 5 | `position_sync.rs:103` | **production** | Probably: the `0x2e7` handler |
| Player pending-skill slots | `+0x214` (and `+0x22c`) | docs only | none at run time | n/a |
| Stats component, set containers | `+0x1c8`, `+0x1e8/+0x1f0`, container `+0xd8/+0xf8/+0x100` | `inspect.rs:95-119` | research | Yes: `Stats` handler `0x142191f20` |
| World: frame mode, pause, frame queue | `+0x661`, `+0x868/+0x869/+0x86a`, `+0x6a8` | `dump_types.rs:169-199,651-661`, `timing.rs` | research | Yes: frame drain `0x14213f8f0` |
| World / area: area row, kind, tile hash, doodad hash | `+0x98` -> `+0x1b4`, `+0x114`, `+0x118` | `dump_types.rs:345-349`, `terrain_tools.rs:262` | **production** (`area_export`) | Yes: `ClientWorld_LoadArea` / `TerrainGen_Run` |
| Generator object | `+0x28`, `+0x30` (seed at `+4`), `+0x38` | `terrain_tools.rs:255-256` | production | Yes: `TerrainGen_Run` |
| Terrain: size, tile array, tile record | `+0x18`, `+0x20`, `+0x28`, record `0x38` | `dump_types.rs:353-385`, `minimap.rs:24-25` | production | Yes |
| Terrain: cell grids | `+0xd0`, `+0xe8`, `+0x100`, `+0x118` | `dump_types.rs:435` | production | Yes, from the tile reader |
| Network stream | `+0x252`, `+0x258`, `+0x260`, `+0x268`, `+0x278`, `+0x280`, `+0x298`, `+0x2a0`, session `+0x20f8` | `packets.rs:333-440`, `protocol.rs:102-123` | production (capture) | Yes: stream read/write use them (the session-send signature contains `+0x20f8` as `f8 20 00 00`) |
| Crypto session: key buffer pointer | `+0x60` | `crypto_bypass.rs:28` | **production** | Partly: found at the SHA-512 output copy; verify with a test (the server's key must agree) |
| Render component: disabled flag | `+0x39a` | `dump_types.rs:670` | research (probe) | Yes |

Deriving an operand safely:
1. The signature has a named capture over the displacement bytes, e.g. `c7 81 <facing:4> 00 00 00 00`.
2. The capture must be in `0x100..0x2000` and 4-byte aligned.
3. Where the same field appears twice (grid in the reader and the setter), both captures must agree; disagreement disables the feature.
4. A runtime sanity check where possible: for Positioned, after the first player frame the world position divided by the cell size must be near the grid position (`position_sync.rs:92`: `CELL = 250/23`); if not, stop reporting.

**Component indices** (Positioned 0, Actor 9) are not struct offsets. They come from the object template (`.ot`), so they change with data patches even with the same exe. `entities::component_names` reads the names from the type's lookup table; use the names once per entity and cache the index.

## 3. Opcodes and message layouts

### 3.1 Opcodes
- Files: `modules/protocol/opcodes/0.5.5e.hotfix1/login.toml` (35 lines), `instance.toml` (143 lines, 75 named opcodes), `hnc.toml`, `inventories.tsv`. Loaded by the servers from `[game] protocol_dir` (`modules/server/config/server.toml:11`) and compiled into the DLL by `poe-proto/src/opcodes.rs:11-19` (`v0_5_5e`, hard-coded module name and `include_str!` paths).
- The client's factories hold about 316 server-to-client instance opcodes and 90 more in the second factory (`dumps/0.5.5e.hotfix1/ghidra/instance_factory_s2c.json`, `instance_factory2_s2c.json`). We name 75.
- A wrong opcode table is a hard failure only for opcodes the client reads with a different class. An unknown opcode is fatal on the client ([../protocol/framing.md](../protocol/framing.md)).
- Opcode numbers likely move on a major patch (messages inserted mid-switch), unlikely on a hotfix.

**Drift detection.** `scripts/re/dump_factory.py` maps each opcode to its class vtable and deserializer address. Planned: a function fingerprint (the deserializer's bytes with `rel32`/`disp32` wildcarded, hashed) stored as `opcode, name, fingerprint` per version; on a new build, match by fingerprint: same opcode and fingerprint (fine), fingerprint under another opcode (renumbered), fingerprint missing (layout changed, needs RE). The factory itself should be found from the string `Unable to deserialise packet` instead of hand-typed arguments (`d 35f 217305c 142173040`, `dump_factory.py:5`).

### 3.2 Layouts
- Rust types: `poe-proto/src/login.rs` (934 lines), `instance.rs` (1,669), `entity.rs`, `player_blob.rs`, `remote.rs`, `skill.rs`; doc comments carry the reader addresses.
- The client does not check that a message or blob was fully consumed: a layout error reads garbage later instead of failing loudly.
- **Oracle:** the movement fixtures (`modules/server/crates/poe-game/tests/fixtures/`, official 0.5.5e captures; the port's tests will compare against them); a new build needs new captures (the user's).
- **Cheaper oracle for blobs:** the DLL's reader-span trace (`entity_trace`) measures bytes consumed per component reader. Keep the spans as a table (`docs/protocol/entities.md`); on a new build run one session and diff.
- `InitialState` and the character-state flags reader (`0x1420fcb70`) are the most delicate: they feed a lot of client state with few checks.
- `client_body_sizes` (`instance.toml:129-143`) are sizes of messages we do not decode; same drift class as opcodes.

### 3.3 Crypto and framing
- The Salsa20 split of the 64-byte key material (`cipher.rs:40`: key `[0..32]`, IVs `[32..40]` and `[48..56]`) is verified by the live handshake; a change shows at once as a login failure.
- HNC: `key_xor` and the six `swaps` are data (`hnc.toml`). The 64 `key_xor` bytes occur in the 0.5.5e exe (file offset `0x2f0f560`, Ghidra `0x142f23aa0`); they can be found by value, falling back to the rip-relative operand in `0x1421d5170`.
- `wstring`/`astring`/varint codecs (`poe-net/src/codec.rs`) change rarely; a test on a captured message detects a change.

## 4. Game data: dat-schema, tables, row indices
- `poe-data` addresses columns by name (`lib.rs:5-6`). The schema comes from `third_party/dat-schema/schema-poe2.min.json`, downloaded from the rolling release `latest` (`third_party/fetch-tools.sh:15-17`); it is not pinned, so two clones a week apart can differ. `poe_data_tools` is pinned (`Cargo.toml:26`, `4.0.1`), but the bundle format can change without notice.
- Width mismatches are only `tracing::warn!` (schema wider than the file, `dat.rs:97-103`) or `debug!` (narrower): the server starts and some columns read wrong bytes. A mismatch in a table the server uses should be an error at start.
- Tables and columns in use: `WorldAreas` (`Id`, `Name`, `Act`, `AreaLevel`, `IsTown`, `IsHideout`, `HASH16`), `Characters`, `CharacterStartStates`, `Inventories`, `LeagueFlag`, `Stats`, `ActionTypes`, `GrantedEffects`, `GrantedEffectsPerLevel`, `GrantedEffectStatSets`, `GrantedEffectStatSetsPerLevel`, `ActiveSkills` and others (`poe-data/src/views.rs`), the `.ot` templates (`template.rs`), `.tgr`/`.dgr`/`.tdt` (`poe-world`).
- Positional access (fragile): `get_index(1)` for the `ActionTypes` key (`views.rs:189`, `:287`).
- **Row index as a key** (each breaks if a row is inserted before it):
  - network key of a stat = `Stats` row + 1 (`views.rs:175-179`; DLL `stats.tsv` from `xtask/src/main.rs:353-364`);
  - inventory slot = `Inventories` row (`views.rs:136-154`; 121 rows in 0.5.5e Hotfix 1; `opcodes/0.5.5e.hotfix1/inventories.tsv` has 123 lines; `modules/server/config/server.toml:151-158`);
  - `sprint_buff_rows = [2758, 2737, 2853]` (`modules/server/config/server.toml:48`);
  - the `Move` skill id `0x20002909` is `0x20000000 | ActionTypes key (10505)`; also written in `poe-game/src/world.rs` (test config). Production code takes it from data (`views.rs:182-189`), the tests do not.
- `InstanceDetails` carries an area `HASH16` that must exist in `WorldAreas` ([../protocol/login.md](../protocol/login.md)); a data patch removing an area breaks any character saved there.
- Config values copied from captures, which may change with the client: `first_entity_id = 12000`, `animation_sets` (`modules/server/config/server.toml:42,215`), the two account flag bytes `[0x23, 0x03]`.
- Bundle paths: `Bundles2/_.index.bin`, `data/balance/<table>.datc64` (`lib.rs:29,70`). `gateway_list.txt` at the game root is written by deploy (`poe-hook-deploy/src/gateway.rs`); the client also looks at `Bundles2/gateway_list.txt`.

**Planned fixes:**
- Store ids in config and code and resolve rows at start (`sprint_buffs = ["<BuffDefinitions id>", ...]`).
- Pin the schema: record the release tag or file sha256 in `modules/protocol/versions/<ver>.toml`, and have `fetch-tools.sh` download that.
- `check-build` anchors: `Stats` has `actor_scale_+%`, `ActionTypes` has `Move` with key 10505, `Inventories` has 121 rows and `MainInventory` at the expected index, the three sprint buffs exist by id.

## 5. Version strings and where the version lives
| Place | What |
|---|---|
| `modules/server/config/server.toml`, `server.example.toml` | `version`, `protocol_dir` contain `0.5.5e` |
| `modules/server/crates/poe-config/src/lib.rs` | `[game] version` is a plain `String` |
| `xtask/src/main.rs` | `dump_dir = dumps/<config.game.version>` (`:274`) |
| `xtask/src/terrain_matrix.rs` | `VECTORS_DIR = "dumps/0.5.5e.hotfix1/terrain/vectors"` (`:30`) |
| `modules/protocol/poe-proto/src/opcodes.rs` | module `v0_5_5e`, `include_str!` paths (`:11-19`, tests `:236-260`); DLL `packets.rs:164,168` uses `v0_5_5e` |
| `modules/server/servers/login-server/src/auth.rs` | test path `opcodes/0.5.5e.hotfix1` (`:134`) |
| `modules/launcher/versions/0.5.5e.toml`, `src-tauri/src/version.rs:7` | `EMBEDDED` list; `settings.rs:157`, `paths.rs:160-178` use `0.5.5e` in test paths |
| `modules/launcher/src-tauri/src/mods.rs` | mod `versions = ["0.5.5e.hotfix1"]` compatibility check (`compat`, `:930-1019`) |
| Web API | `GET /public` shows `game.version` (`poe-web-api/src/public.rs:74`) |
| Python tools | `dumps/0.5.5e.hotfix1/...`, `docs/re/addresses.md` (`export_symbols.py:6-39`, `movement_sequences.py:41`) |

Other identifiers: the 0.5.5e sizes were `Bundles2/_.index.bin` 115,154,591; `steam_api64.dll` 262,944; `fmod.dll` 1,913,344; `bink2w64.dll` 466,560. DepotDownloader can fetch an old manifest only while Steam keeps it. `exe_sha256_enforce = false` and Play does not run `verify` (`install_verify` is a separate command, `commands.rs:125`), so nothing stops the DLL from being deployed onto another build.

## 6. Terrain generator constants and data formats
- The port reproduces the client's generator: MSVC `mt19937` and `uniform_int` (stable), MurmurHash2 string and tile hashes (`hash.rs`, `terrain_tools.rs:1016-1050`), and long algorithms (rooms, routing, smoothing). Constants (`0x38` records, 23-cell tiles, `250/23` cell size, `0x2000` steps in `smoothing.rs`) are stable per release; algorithms change with game updates that touch levels. Tile sets and `.tgr`/`.dgr` come from the bundles, so a **data** patch changes layouts with no exe change.
- `.tgr` is version 25 (`poe-world/src/graph.rs:1,111`); the parser branches on `> 22` / `> 23` (`graph.rs:133-134`) with no upper bound, so a version 26 file would be parsed as 25. It should fail on an unknown version.
- **Oracle.** The client logs `Generating level L area "A" with seed S`, `Tile hash` and `Doodad hash` for every area, and the DLL recomputes the hashes on export. `terrain-vectors.tsv` has a `build` column (from `Build Revision`); a vector whose `build` differs from the current one is stale.
- On a new build: re-export a few areas from a play session, run `cargo xtask terrain-matrix` and `check_exports`; a hash mismatch is the signal. It needs the client running, so `check-build` only reports "vectors from build X, current Y". Expect failing seeds to grow for new area types first ([../status/terrain.md](../status/terrain.md)).

## 7. `Client.txt` parsing in scripts and the DLL
- `scripts/re/clientlog_terrain.py:13-16`: four regexes including `Build Revision`.
- `scripts/re/clientlog_entries.py:13-19`: a line regex (`^\S+ \S+ (\d+) \S+ \[(\w+) Client \d+\] (.*)$`) and the `Generating level` regex.
- `scripts/test-run.sh`, `scripts/test-mp.sh` read the **server** log (`authenticated`, `listening`), not `Client.txt`.
- DLL `gamelog.rs` and the Log page read `logs/Client.txt` lines of this launch.
- Risk is low (stable format, tools print counts). Add the build revision to every output header; at count 0 say "no lines matched; the log format may have changed".

## 8. Other items checked
- `poe-hook` and the core use `ws2_32`, `user32` raw input, Vulkan loader (`vkGetInstanceProcAddr` found by export, `vulkan.rs:4`) and `version.dll` forwarding: OS APIs that do not move.
- `trace_calls.rs:29` takes arbitrary user addresses, so a new build needs new addresses; print the build revision next to each hit.
- `auto_keys.rs:473` reads the pointer at `0x1445f0768` (game window); test input only, never in official mode.
- `login_patch.rs` logs on mismatch; the patcher skip logs "would contact GGG patch servers" (`:64-80`); in private mode the guard still refuses external connects.
- `poe-hook-deploy/src/lib.rs:39-51`: `version.dll`, `steam_appid.txt` (`2694490`), `gateway_list.txt`, `PathOfExileSteam.exe`.
- `config.json` keys (`GGG_*`, `STEAM_APP_ID`, ...) from `0x141020b20` are used by `docs/guides/setup.md` for the credentials file name (`login_token.rs:14`).

## Surprises
- Packet capture redaction depends on the opcode table, so check a capture after a game update; `poe-hook-shared/src/redact.rs` redacts `Credentials` and every outgoing login-channel body when the opcode table is not the known one. Captures in `dumps/` are never committed.
- The build revision is a plain ASCII string in `.rdata`: the easiest version fingerprint, and what `Client.txt` prints.
- Research hooks run by default on official sessions; a signature failure there is a crash risk, not just a lost feature.
- `Play` never verifies the exe (`exe_sha256_enforce = false`; `verify` is a separate button).
- `dump_factory.py` and `export_symbols.py` are tied to 0.5.5e by name; the symbols file is a source of misleading names after a patch.

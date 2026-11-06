# RE findings: PathOfExileSteam.exe 0.5.5f

The DLL finds hook addresses, patch sites and struct offsets by byte signature from `modules/client-hook/signatures/0.5.5f.toml` (85 signatures, 51 fields; each with its Ghidra address in a `ghidra` key). The table is the source for what the DLL does; this page is the knowledge base and the starting point for a new build. Check the table against the exe with `cargo run --release -p poe-hook-sig --example resolve -- GameFiles/PathOfExileSteam.exe`. See [../architecture/client-dll.md](../architecture/client-dll.md#signature-table-signaturesversiontoml) and [update-compatibility.md](update-compatibility.md).

Ghidra project: `GhidraProject/Poe2ModdingProject`, program `/PathOfExileSteam.exe`, image base `0x140000000`, 115,673 functions. Addresses are Ghidra addresses (`Module::from_ghidra` converts them).

## Login, gateway and crypto
| Address | What |
|---|---|
| `0x140ef0470` | gateway list loader (`"gateway_list.txt"` 0x14316c898, `"Bundles2/gateway_list.txt"` 0x14316c860) |
| `0x14212cde0` | instance server connect (`"Connecting to instance server at {}:{} "` 0x14351d610) |
| `0x1435288d8` | string `"HNC Protocol Violated"` (no direct code references) |
| `0x1420f71e3` | login packet dispatcher switch (`ClientLoginSession`?), opcodes 0x02-0x47; opcode 2 case `0x1420f7210`; jump table `0x1420e9a64`, index `0x1420f8a10` |
| `0x1421aefe0` | crypto: verify server signature + derive keys ("General Rhoa Failure #3"), hooked by `crypto_bypass` |
| `0x1421aee10` | crypto: DH2 agree + SHA-512 -> 64-byte key material ("#1") |
| `0x1421adc10` | crypto session constructor (DH groups, DSA key, "#2") |
| `0x1421af380` | builds the two-direction Salsa20 cipher from the key material |
| `0x1421a8500` | installs a cipher on a Tcpstream |
| `0x14212ac10` | instance packet-cipher builder `(out, InstanceDetails + 0x38, &is_client)`, only caller `0x142131323` in `0x142131210`; hooked by `side` ([crypto.md](crypto.md#side-channel-keys)) |
| `0x142b15570` | Crypto++ Salsa20 key setup |
| `0x142111ca0` | loader for server-delivered encrypted code modules ([crypto.md](crypto.md)) |
| `0x1421d5170` | HNC bit queue: key material XOR table `0x142f23aa0` + swaps, Salsa20 pair |
| `0x1421d5420` | HNC incoming byte parser ("HNC Protocol Violated") |

Imports: `VERSION.dll` (`GetFileVersionInfoW`, `GetFileVersionInfoSizeW`, `VerQueryValueW`) is proxied by poe-hook. `WS2_32.dll` sockets; `bcrypt.dll` and `CRYPT32.dll` are present. The crypto strings (CALG_*, TLS_*, RSA) belong to bundled curl/OpenSSL; the game cipher has no string anchors.

## Entities and rendering
| Address | What |
|---|---|
| `0x14213f4f0` | game world update in frame mode (`world, ctx, f32 real dt`): plays queued frames in real time with speed factor +0x670 (1.01/1.5/2/5 by frames left, back to 1.0 only when drained), bank +0x66c capped at one frame: [movement.md](../protocol/movement.md#timing) |
| `0x14213f8f0` | world frame drain (`world, f32 frame_dt`): pops one frame length (deque world +0x688), applies that frame's packets, updates entities with frame_dt (0 when paused, +0x868). Reached through vfunc +0x3c0 `0x14213dd50` |
| `0x14213fe30` | world vfunc +0x3c8: visual update job (`dt`, played simulation time) |
| `0x140b2afa0` | world vfunc +0x178: `world +0x124 = frame_ms` (InitialState, `0x2f8`) |
| `0x14213ee40` | world start (InitialState vfunc +0x1f0): applies all queued packets |
| `0x14213f410` | flush packets scheduled at the current (entity, component, sequence) position |
| `0x141e808f0` | object registry insert ("Replacing awake/asleep/deleted object") |
| `0x142146490` | frame-mode entity update loop (component vfunc +0x50, then `0x141e8b960`) |
| `0x1421433d0` | simulation packet queue (param = world +0x260): `0x2f7` pushes a separator and world +0x124 into the frame-length deque (only once started, +0x86a), `0x2f8` -> world vfunc +0x178 |
| `0x1401558b0` | entity -> Render component by name: entity `+8` → type, `+0x28` → component lookup, sorted `{char* name, i32 index}` (16 bytes) from `+0x28` to `+0x30`; the index selects `entity+0x10[index]` |
| `0x1416b2160` | Render: apply visibility to the AO scene node (+0x39a disabled flag) |
| `0x14192f6a0` | GEAL `EnableRendering` lambda body |
| `0x141d50ab0` | animation controller: play animation (index, ...) |
| `0x141e078c0` | StateMachine reader (shared-state count check) |
| `0x1427045e0` | GEAL script interpreter loop |
| `0x140286850` | `Data/Balance/Hideouts.dat` table getter |
| `0x14102ecb0` | Vulkan loader (`LoadLibrary("vulkan-1.dll")`, `GetProcAddress("vkGetInstanceProcAddr")`) |
| `0x142191f20` | Stats component message handler: `0x1d3` StatsUpdate (set 0 -> container at component `+0x1c8`, other sets in list `+0x1e8..+0x1f0`, container `+0xd8` = set id); `0x1d4` removes a set |
| `0x1426bec20` | stat container set `(container, key, value)`: sorted `(i32 key, i32 value)` array at `+0xf8..+0x100` |

### UI elements and the Life pools
| Address | What |
|---|---|
| `0x1427c12b0` | UI element SetVisible `(element, bool)` (signature `ui_set_visible`, feature `ui_panels`): flags u32 `+0x168` bit 11 (`0x800`) = visible; parent `+0xb8`; name `std::wstring` at `+0x98` (size `+0xa8`, capacity `+0xb0`, inline < 8); UI context `+0x90`; children vector `+0x10..+0x18` |
| `0x1402cbff0` | escape menu constructor: names itself `escape_menu` (child `escape_menu_inner`, loads `Metadata/UI/InGameState/EscapeMenu.ui`) |
| `0x1430b7a18` | inventory panel class vtable (constructors `0x1408ea1f0`, `0x1408ecfa0`), found by toggling I in game |
| `0x141d99350` | Life component reader. Pools: life `+0x1a8`, mana `+0x200`, `+0x240` (read as energy shield by the state export, unverified) |
| `0x141d95f60` | pool reader: wire u32 to `+0x38`, then `0x141d98af0` (u32 to `+0x18`, i16 to `+0x1c`), then u32 to `+0x30`; long pools (`0x141d98fb0`) add u32 to `+0x48`. After login (life 28, mana 34, full): `+0x34` = 28/34 (not on the wire: the client's maximum), `+0x38` = 28/34 (first wire field), `+0x30` = 0 for life, 34 for mana. The state export reads current = `+0x38`, max = `+0x34`, reserved = `+0x30` (assumed) |

## Session, chat, pause
| Address | What |
|---|---|
| `0x14212e7e0` | logout routine ("FourLogOut"): 0 / 2 = exit to login / game, 1 = exit to character selection (sends `0x173`) |
| `0x14216d550` / `0x14216d620` | S->C `0x174` ExitSession constructor / reader |
| `0x1421942a0` | S->C `0x1fe` SetPause reader; applied via world vfunc +0x200 `0x141693250` |
| `0x14216c160` / `0x14216c240` / `0x142133fbe` | S->C `0x14d` ChatJoined constructor / reader / handler |
| `0x1401b8eb0` | chat join timeout message ("Timeout while joining {0} chat") |
| `0x1402cbff0` | escape menu construction ("Get Full Access" button when +0x3edc is clear) |
| `0x1402ced20` | escape menu buttons: +0x2f0 exit to log in screen (logout 0), +0x2f8 exit game (`0x140eb53d0`, logout 2 + WM_CLOSE), +0x300 exit to character selection (logout 1) |
| `0x1420fcb70` | InitialState CharacterState flags -> local player (+0x3eca..+0x3ede) |
| `0x140ee11b0` | delete-character screen result callback |
| `0x142130484` | `0x1c` frame report sender; `0x141f56da0` its serializer |
| `0x141f57310` / `0x142131422` | S->C `0x1d` ping reply reader / handler |
| `0x14212ed70` | sends `0x358` ExitReport (once per session); `0x141f55e30` serializer `u8, u16 len, bytes` |
| `0x14211de90` | chat sender (`0x16`, wstring; "@whisper") |
| `0x142160090` / `0x142160020` | S->C `0x18` ChatMessage read / write: `u8`, then the chat struct (`0x1421b73a0` read, `0x1421b71a0` write): 3 wstrings (`0x141d07d60`), flags, class, item links |

## Movement and skills
| Address | What |
|---|---|
| `0x14212eb20` | game-session send (`packet->vtable[1](packet, stream)`); senders build the packet on the stack (opcode at +8) |
| `0x142158b60` | Actor component simulation handler: `0x64` WASD, `0x65`, `0x1c8` start action, `0x1c9`..`0x1ce`, `0x1d8`/`0x1d9` skill stats, `0x1f9`..`0x1fc`, `0x2e7`, `0x30e` action update, `0x316`..`0x324`. `0x64` (`0x142158cce`): non-zero and cell != grid +0x444: snap `0x141de88a0` (predictive mode only: <46 cells, `0x844`, bends instead) |
| `0x141f79880` | S->C `0x64` MoveDirectionUpdate reader |
| `0x141f77e50` | S->C `0x1c8` StartAction reader |
| `0x141e4fa60` (`0x141e4fb20`) | StartAction apply: same 46-cell snap threshold |
| `0x141de88a0` | SetLocationForcedNoCallbacks (stops a running move, `0x141df31b0`) |
| `0x141e972a0` | create an action from an actor skill |
| `0x140172a80` | C->S `0x2e6` sender (`u8 player, u8`) |
| `0x14016fd30` | `AimReport_Tick`: per frame, AimTarget mode 2/3 via `0x14016fb10` (33 ms) only while mode 1 was sent (+0x418, WASD), `GetForegroundWindow() == *[0x1445f0768]`, Player component (`local player +0x188`) combat stance (+0x20d) and UI checks pass |
| `0x141ddc630` / `0x141dddd40` | `PlayerComponent_Read` (full, vtable `0x1433b82c0` +0x98; first `u32` after the class is experience `0x141dde510`, `flags` bit 2 = combat stance +0x20c) / delta reader (+0xb0, `u16` raw mask; see `PlayerDelta`) |
| `0x141de1b10` | Player vfunc +0x138: set combat stance (+0x20d); +0x20c is the networked byte |
| `0x142124030` / `0x142123ec0` | `0xfe` sender (+0x7a90 blocks skills until `0xff`) / next set; `0x1d5` -> `0x141e099b0` (Stats +0x168) |
| `0x14200d1f0` / `0x141ffe1d0` | `TerrainGen_Run` / `TerrainGen_Construct`; phases, RNG and hashes in [terrain/README.md](terrain/README.md) |
| `0x141683940` / `0x14213e730` | `ClientWorld_LoadArea` (in-game world) / `HeadlessWorld_LoadArea` (server-side world class in the client) |
| `0x141faa7c0` / `0x140a65f30` / `0x141f1ba50` | terrain RNG seed (TLS +0x20190) / `std::mt19937` next / MSVC `uniform_int` draw |
| `0x141d20d80` / `0x142003d00` / `0x142001ac0` | tile hash / doodad pass (doodad hash -> world +0x120) / per-tile doodads and entities |
| `0x1408746f0` | stream varuint reader (the `0x2fc` ComponentDelta length) |
| `0x14219a850` | Actor skill container reader; `0x14219afb0` skill list; `0x142198bd0` one skill |
| `0x142695a70` / `0x142695790` | skill effect reference reader (GrantedEffectsPerLevel row) / stat-set reference (GrantedEffectStatSetsPerLevel row) |
| `0x1419a25a0` / `0x141e33c80` | varuint / varint readers used in stat lists |
| `0x141dda290` | Pathfinding component constructor (+0x550 base speed, +0x55c multiplier) |
| `0x14213dd60` | world constructor (+0x661 frame mode; in-game world created with 2 by `0x141014066`; vfunc +0x1d8 returns 2 for lockstep); vtable `0x14351d938`, vfunc `+0x1e0` is `HeadlessWorld_LoadArea` |
| `0x141944fc0` | `[NETWORKING] networking_type` option reader |
| `0x14212fe10` | game session update / instance session receive loop: frame reports, auto network-mode switch, world update |

### Roll, sprint and steering
| Address | What |
|---|---|
| `0x141b84fb0` | end of a dodge roll: decides whether it becomes a sprint (official servers decide server-side: `is_sprinting` is set 15 frames into a held roll) |
| `0x141e6b500` | Actor "is sprinting": Actor +0x915 or the stat `is_sprinting` |
| `0x141e5be90` | movement reset / stat listener: stops Move when Actor +0x2a1 bit 2 is set |
| `0x141b855b0` | sprint end: ends Move, stops the entity (`0x141df2040`), plays `SprintEnd` (`0x36a`, Bonk `0x36b`) unless Actor +0x2a3 bit 0 (`0x141e5fbd0` mode 1) or a slot-0 action; `m_ExtraAnimations` of row `0x368` (+2 with stat `0x4862`) |
| `0x141db47b0` | Animated animation-event handler (type 0x12 MoveEventType -> `0x141f6daf0`) |
| `0x141f6daf0` / `0x141f6f170` / `0x141f6dca0` | animation root-motion move (event, displacement, start; rate: xmm0 at `0x141f6e084`) |
| `0x141d53e40` / `0x141e69fe0` | AnimationController +0x178 rate setter / action speed |
| `0x141e65a70` / `0x141e649d0` / `0x141e5b9f0` | play animation / movement-speed rate / speed |
| `0x141b84fb0` | sprint end check ([rules](../protocol/movement.md#coasting-after-a-sprint)) |
| `0x141f6f650` / `0x141df3290` | its target cell: grid + displacement rotated by facing +0x44c, Positioned scales +0x46c/+0x470/+0x474 |
| `0x141db4eb0` | animation change: stops it |
| `0x141ab6230` | `dodge_roll_travel_distance` getter |
| Actor +0x238 / +0x240 | current action (roll) / Move action slot (WASD walk); action type at action +0x120 |
| Actor +0x2a2 bit 5 | sprint key held (set by S->C `0x2e7`) |

### Facing
| Address | What |
|---|---|
| `0x141de99d0` | Positioned::SetOrientation(angle): writes +0x44c (radians, `atan2(dy, dx) + π/2`) unless locked (+0x1e5 bit 1) |
| `0x141de7970` | Positioned simulation handler: `0x1dd`/`0x1de` position, **`0x1df` SetOrientation (f32, u8 locked)**, `0x1e0` knockback-like move, `0x1e7` +0x440/+0x48c, `0x2ef` flags |
| `0x141f796a0` | `0x1df` reader |
| `0x141df0400` | `Positioned_MoveToWaypoint`: movement step, turns toward the path (orientation mode +0x1e3 or the request's; 2 = backwards); `"Tried to issue a MoveTo with infinite speed"` |
| `0x141de5b50` | Positioned initial data (facing +0x44c, flags0 bit 7 -> lock) |
| `0x141e61520` | Actor RecalculateStance ("Aiming", "AimingUpwards", "Ranged", "Mounted", "Unarmed") |
| `0x14215980a` | Actor `0x1cc` (u16 action id, u8) -> Actor vfunc +0x130 (end action?) |
| `0x142159920` | Actor `0x1fc` (f32, u16) -> Actor vfunc +0x100 |

## Character creation
| Address | What |
|---|---|
| `0x14215f000` | login incoming-packet factory (opcode -> class); `0x13` CharacterCreated class `0x14351f4a0`, deserializer `0x14215df90` |
| `0x1420f71f5` | login dispatch switch (opcode - 2; byte table `0x1420f8a10`, targets `0x1420e9a64`); `0x13` case `0x1420f79ae` signals connection +0xb08 |
| `0x140ed0d80` | create screen: connects to the login connection's signals (+0xb08 -> `0x140edb550`, +0x188 -> league list `0x140edd450`) |
| `0x140ed6e80` | create screen Continue/Create button (needs a selected league: +0x320, +0x318) |
| `0x140ed72b0` | sends CreateCharacter (`0x1420f8c20`); do not hook its entry, the trace hook crashes |
| `0x140edb550` | `CreateCharacterState_OnCharacterCreated` (u16 result): 0 -> +0x392, creation scene (`0x140ed7760`, sets +0x390); else `BackendError_GetText` into the message line `0x140ed2150` |
| `0x140ed8070` | create screen per-frame update: scene done with +0x390 and +0x392 -> `0x140ed78f0` |
| `0x140ed78f0` | "character_creation_done": finds the new character by name (`0x140ed15c0`), sends PlayCharacter (`0x1420f8f30`) |
| `0x140edd8f0` | create screen key handler (Space skips the creation scene) |
| `0x140e855a0` | league banners at character creation (entries with +0xe0 bit 7, not variants; variants matched by +0x80) |

## Streams and packet capture
| Address | What |
|---|---|
| `0x1421d5a10` | message reader `(registry, stream)`: reads the opcode, lets the registered handlers deserialize, advances the receive ring (+0x268) by the message size; low byte of the result 1 = a whole message was read |
| `0x1420f5c10` | login session receive loop (caller of the message reader on the login connection) |
| `0x1421a7d00` | stream read `(stream, dst, len)`: copies from the receive ring at +0x268 + +0x278 (bytes read in this message); sets +0x252 on underflow |
| `0x1421a7e30` | stream write `(stream, src, len)`: appends to the send buffer (+0x280, length +0x258); flushes when full |
| `0x1421a7f90` | stream flush `(stream, err, force)`: plaintext tap (+0x190), cipher (+0x1b8 slot 1, in place), then `send` on the socket (+0) |
| `0x1421a8007` | inside the flush, after the lock, before the cipher: pending plaintext `[+0x280] + [+0x260 .. +0x258]`, rbx = stream |

## Login hand-off, AreaInfo, terrain passes
| Address | What |
|---|---|
| `0x1420f7180` | `ClientLoginSession_ProcessPacket`: login message switch (opcode - 2); case `0x14` InstanceDetails (+0xa8 kept, +0x40 string), case `0x17` -> `0x1420f6190` |
| `0x1420f6190` / `0x1420f6220` | login disconnect with reason; `0x1420f6220` calls `shutdown()` on the login socket: login `0x0017 <u16>` makes the client close its login connection |
| `0x14212c3f0` | AreaInfo reader: optional blocks by flags0/flags1 bits; flags0 bit 7: stat records `0x1423cab90` (varuint count, `u16` key, varint value via `0x141d08b90`) |
| `0x1420b0f90` | dungeon exit wiggle (after the fill): sorted position set at tile pass +0xb0, filled by pass A (`0x1420a7b38`) and the fill listener `0x1420a92e0`; hashed exits `0x1421a69b0` |
| `0x1420ae070` | dungeon border tile placement; fallbacks: middle exits `0x1420aea30`, height flattening `0x1420aeb20`, neighbour repair `0x1420adc90` |
| `0x1420ac1a0` | dungeon door groups: door sizes per edge set `0x141d162b0` (sets built by `0x141d16660`) |
| `0x1420061c0` / `0x141ffeda0` | per-graph outer fill + buffer / subgraph generation (subgraphs run the whole pipeline in a window `0x141fac8d0` of the main map) |
| `0x141fe47a0` / `0x141fe5970` | outer fill with height repair / one levelling round ([terrain/dungeon.md](terrain/dungeon.md)) |

## Skill acknowledgements, buffs, sprint
Layouts and sequences: [../protocol/movement.md](../protocol/movement.md). Structs: `modules/protocol/poe-proto/src/skill.rs`.

| Address | Ghidra name | What |
|---|---|---|
| `0x142196800` | `UseSkillAck_1ae_Read` | S->C `0x1ae` reader: sim header (`SimMsg_ReadHeader`, `0x141f59d30`) then the skill block |
| `0x141edbfb0` / `0x141edbeb0` | `SkillUseParams_Read` / `_Write` | shared block: `u32 skill, u16 flags, u8, u8 target flags, [u32 entity if flags & 8], i32 x, i32 y` (C->S `0x1a5` writes it after `u8 player`) |
| `0x141f7bcc0` | `SkillTargetAck_1af_Read` | S->C `0x1af`: header, `i32 x, i32 y, u32 skill` |
| `0x1421968e0` | | S->C `0x1b0`: header, `u32 entity, i32 x, i32 y, u32 skill` |
| `0x141f59d30` | `SimMsg_ReadHeader` | `0x1b1` (and `0x1c6`, `0x1c7`, `0x1ca`) have no body past the header; vtable `0x1435216d8` |
| class vtable `0x143521898` | | S->C `0x1b2`: header, `u32 skill, u8` (ctor `0x142197ec5`) |
| `0x14211e950` | `Session_SendUseSkill_1a5` | C->S `0x1a5` UseSkill sender (vtable `0x1434fb368`, body `0x141edbeb0`; `0x1a7`..`0x1ad` senders follow). Cursor relative to the player (`x -= Positioned +0x444`, `y -= +0x448`; absolute with a target entity). Outside lockstep it ORs `0x04` into the local copy and calls Player vfunc +0x108 |
| `0x14211ebe0` | | skill target update sender: `0x1a8` (lockstep, relative), `0x1a9` (absolute), `0x1aa` (entity) |
| `0x14211ed90` | `Session_SendSkillInputEnd_1ac` | C->S `0x1ac` (`u8 local player`); in lockstep (world +0x669 == 2) the client only waits for `0x1b1`, otherwise it calls Player vfunc +0x118 itself |
| `0x14211ee10` | `Session_SendSkillReleased_1ad` | C->S `0x1ad` (`u8, u32 skill, u8`); the local fallback is Player vfunc +0x120 |
| `0x142143530` (`0x142143edf`, `0x142144e92`) | | frame processor: `0x64`/`0x65` go straight to the Actor handler `0x142158b60`; the opcode switch at `0x142144e92` (base `0x1af`) sends `0x1ae`..`0x1b2`, `0x26f`, `0x270` to `Entity_GetPlayerComponent` + vfunc +0xc0 |
| `0x1416fc930` | `Player_SimulationHandler` | Player sim handler (vtable `0x1433b82c0` +0xc0); jump table over opcode - `0x1ae`: `0x1ae` -> `0x1416fcecb`, `0x1af` -> `0x1416fcf03`, `0x1b0` -> `0x1416fcf42`, `0x1b1` -> `0x1416fcf7b`, `0x1b2` -> `0x1416fcfa8`, `0x26f`/`0x270` -> `0x1416fc990`/`0x1416fca6f`. `0x1ae`..`0x1b2` are skipped when `[Player +0x430] != 0` and world vfunc +0x1d8 returns 1 (predictive); never in lockstep |
| `0x141de15a0` | `Player_ApplyServerSkillUse` | Player vfunc +0x108 (`0x1ae`): copies the block (24 bytes) into the pending-skill slot (+0x214, or +0x22c when the skill is Move `0x20002909`), marks it valid. Target flags bit `0x04` -> stop. Else if the player may act (vfunc +0x128) and bit `0x01` is clear, starts the skill locally (`0x141edba90`); bit `0x02` with a running action of the same skill cancels it |
| `0x141de1700` | `Player_ApplyServerSkillTarget` | Player vfunc +0x110 (`0x1af`, `0x1b0`): stores position (+0x21c / +0x234) and entity (+0x218 / +0x230) of the matching pending slot, then Actor vfunc +0x128 `(pos, skill, entity)` re-targets that skill's running action |
| `0x141de1850` | `Player_ClearHeldSkill` | Player vfunc +0x118 (`0x1b1`): clears both pending slots (+0x214, +0x22c), then ends the held action unless Player flag +0x226 bit 2 |
| `0x141de1940` | `Player_ApplyServerSkillRelease` | Player vfunc +0x120 (`0x1b2`, `u32 skill, u8`): clears the slot of that skill (Move -> +0x22c) and runs +0x118 for the main slot; a running Actor action (+0x248) of that skill is ended (except a Move with the `u8` clear); with the `u8` set and the Move slot (+0x240) matching, the walk is finished (`0x141e53c90`) |
| `0x140154a20` / `0x140153470` | `Entity_GetPlayerComponent` / `Entity_GetActorComponent` | component lookup by name (static string pointer; Player at `0x1434e8d54`) |
| `0x141f7a390` | `BuffAdded_1eb_Read` | S->C `0x1eb`: header, `u16 index, u16 buff row, u32, u16, u16 flags`, fields by flag in order `0x01` (varuint,u32,u8,u16), `0x02` f32, `0x80` f32, `0x04` u16, `0x08` (u16,u32,u8), `0x10` u16 BuffVisuals row (replaces the row's `BuffVisual`), `0x20` u8; then `u16` if BuffDefinitions row byte `0xfe` (column 43, unnamed: 99 rows, e.g. `chilled`) and one `u32` per `GrantedStats` entry if row byte `0x7c` (`IsRecovery`, misnamed: 142 rows, e.g. `poison`); then `u32 n` + `n` x `u32`. Port: `BuffAdded::decode_with` |
| `0x141f7a940` | `BuffRemoved_1ec_Read` | S->C `0x1ec`: header, `u16 index`; Actor-side opcodes `0x1eb`..`0x1ed` share the handler at `0x142144ef1` |
| `0x14215965e` | | Actor case `0x1ca` (header only): decrements `Actor +0x348`; in predictive mode also restarts the action; seen with every roll start and sprint end by an attack |

## Walk speed factor, roll heading, sprint end
Evidence: [../protocol/movement.md](../protocol/movement.md#coasting-after-a-sprint).

| Address | Ghidra name | What |
|---|---|---|
| `0x141dda090` | `Pathfinding_GetSpeed` | `base_speed` (+0x550) x (1 + stat `0xec` / 10000) x (1 + stat `0xc39` / 100) x multiplier (+0x55c), capped by stat `0x44a`; +0x554 < 0 means "computed" (movement_velocity_+permyriad, virtual_action_speed_+%) |
| `0x141dda220` | `Pathfinding_SetSpeedMultiplier` | writes the multiplier +0x55c (clamped at 0) and re-issues the running step (`0x141dd9200`) |
| `0x141e4fe40` | `Actor_ApplyActionSpeedFactor` | from the running action: vfunc +0xe8 = 0 sets the factor at once (non-Move actions: Actor +0x440 = vfunc +0xe0), else Actor +0x444 = rate and +0x448 = target (vfunc +0xe0 clamped 0..1); the Actor tick (`0x141e508f0`, multiplier written at `0x141e52193`) moves +0x440 to the target at that rate per second and multiplies it by +0x438 into Pathfinding +0x55c |
| `0x141989da0` | (action vfunc +0xe0, the factor) | `1 + A/100 x (1 + B/100)`, A = stat `0x4738` (`movement_speed_+%_final_while_performing_action`), B = stat `0x559d` (`virtual_movement_speed_penalty_%_while_performing_action`); 1.0 when vfunc +0x58 is false. 1217 vtables use it, 4 use `0x1419904d0` |
| `0x141e4ffa0` | `Actor_ActionSpeedFactorBackTo1` | as `0x141e4fe40` with target 1.0: at once when the action's vfunc +0xe8 is 0, else a ramp at that rate; also at action end (`0x141e534ae`) |
| `0x141e500c0` | `Actor_SetActionSpeedFactorNow` | Actor +0x440 = factor, min with +0x3fc while the timer +0x3f8 runs (set only for skill `0x9ce8`, `0x141e69230`), times +0x438 into Pathfinding +0x55c; stops the ramp (+0x444 = 0); callers `0x141e50a54`, `0x141e51d3b`, `0x141a48e01` |
| `0x141a48970` | `Action_OnAnimationEvent` (~800 vtables) | **contact** event (`0x9b8d`): vfunc +0x7b8, then with stat `0x473f` (`can_perform_skill_while_moving`), without `0x54ce` (`..._is_not_slowed_on_contact`) and Actor +0x448 != 0: `0x141e500c0(actor, +0x448)`, the factor jumps to the target (also `0x141a48400`) |
| `0x141e51e41` | (inside the Actor tick `0x141e508f0`) | while an action with a factor other than 1 runs: with stat `0x4e28` (`movement_speed_while_performing_action_locked_duration_%`) not 0, calls `0x141e4ffa0` once the action's elapsed time (`0x141985cb0` +0x24) reaches that % of its duration (+0x3c); else when the action's vfuncs +0x290, +0x2a0 and +0x288 say so. The ramp itself is at `0x141e5209b` (step = `copysign(rate, target - current) x dt`, snaps at the target) |
| `0x141989e70` | `Action_GetSpeedAccelerationPerSecond` | action vfunc +0xe8: stat `0x4777` (`movement_speed_acceleration_+%_per_second_while_performing_action`) / 100 when the action is a performing one (vfunc +0x58); `0x1419bc960`, `0x1419c2bb0` are variants |
| `0x141e5da30` | `Actor_StartWasdWalk` | creates the Move action (skill `0x20002909`); not when axes Actor +0x400/+0x404 are 0, Actor +0x2a1 bits 1/2 or +0x2a0 bit 6 are set, **the animation (Actor +0x380) is (`0x36a`, `0x36b`, `0x371`, `0x372`)**, or a push (Positioned +0x480, PushTo `0x141def770`) is at least as fast. Called per frame by the Actor tick (`0x141e508f0`+0x860) |
| `0x141dd9020` / `0x141dd9790` / `0x141dd9200` | `Pathfinding_FollowPath` / (path request) / `Pathfinding_StepAlongPath` | the path request clamps the first leg to 126 cells (`0x42fc0000`); step issues the waypoint move with the speed getter |
| `0x141ab54e0` | `DodgeRoll_OnStart` | roll action start: stats `0x5121`, `0x478c`, travel distance (`0x141ab6230`), builds the movement helper and calls `0x141b99fb0` |
| `0x141b99fb0` | `DodgeRoll_InitHeading` | roll heading (action +0x40, radians, `atan2 + π/2` wrapped to 0..2pi): the held input vector when Actor +0x400/+0x404 are not both 0 and the action's flag +0x5e is set; else the direction from the entity's position (Positioned +0x444/+0x448) to the action's target (+0x150/+0x154); the facing (+0x44c) when target = position; action +0x3f = 1 when the heading differs from the facing by >= 90 degrees (Actor +0x8fa) |
| `0x141e5ba50`, `0x1416ea950` | | sprint animation transition: `sprint_blend_time_override_ms` (`0x5735`) / 1000 as the blend time (-1 = default), `virtual_sprint_timeline_variation` (`0x6996`) |
| client log `action start/end slot N: <Action>` (`poe-hook.log`, `poe_hook_core::actions`) | | slot 0 = the performing action, slot 1 = Move |

## Client platform and standalone login
Details and the patch: [standalone-login.md](standalone-login.md).

| Address | Name | What |
|---|---|---|
| `0x1421a6e90` | `ClientPlatform_Detect` | platform enum from exe name and command line: 0 standalone, 1 Steam (`Steam` in the name or `--steam`), 2 Hotcool, 3 Hotcool+Steam, 4 Kakao (`KG` / `--kakao`), 5 Epic (`EGS` / `--epic`). Patch `40 55 53` -> `31 C0 C3` forces 0 |
| `0x14472f638` / `0x14472f634` | | cached platform value / its thread-safe-static guard |
| `0x14010c450` / `0x14010c510` / `0x1401b1690` / `0x1421a7300` | `ClientPlatform_IsSteam` / `_IsHotcool` / `_IsTokenLogin7or8` / `_Equals` | cached-value getters (about 90 callers) |
| `0x140ef1760` | `LoginState_BuildUi_SelectLoginScreen` | picks `LoginScreen.ui` / `SteamLoginScreen.ui` / Hotcool / Epic / Kakao by platform (branches `0x140ef1cd8`..`0x140ef1e07`) |
| `0x140efd650` | `LoginState_StartAuthentication` | after the key exchange: Steam -> ticket request, 5 -> `0x140efc3d0`, 4 -> `0x140efca10`, else `0x140efcdd0` |
| `0x140efcdd0` | `LoginState_StandaloneLogin` | email/password or saved-token login; sends `0x0003` |
| `0x140f02880` | `LoginState_OnSteamEncryptedAppTicket` | Steam callback: ticket (<=1024 bytes) -> `0x0005` |
| `0x140efbef0` | `LoginState_TokenLogin7or8` | platform 7/8 only: `0x0032` / `0x0033` (`0x1420f6670`, `0x1420f6850`), dead on PC |
| `0x1420f6b40` | `ClientLoginSession_SendCredentials_0003` | builds and sends `0x0003` (class vtable `0x14351b9d8`, serializer `0x1420f2bb0` `Packet0003_Credentials_Serialize`) |
| `0x1420f6e50` | `ClientLoginSession_SendSteamTicket_0005` | builds and sends `0x0005` (serializer `0x1420f2540`) |
| `0x1421cbd40` | `Sha256_Bytes32` | SHA-256 (IV at `0x143a23198`) for the password hash: UTF-16LE bytes, no salt |
| `0x1420f65d0` | `LoginClientHash_Get32` | the 32-byte client hash (global `0x1445ee3a0`), a hash of the file at argv[0] computed on a worker thread by `0x1420fa530` (`0x14102eb80` returns argv[0], `0x1421cbdc0` hashes the file) |
| `0x140ef9190` | `LoginState_SaveLoginAfterAuth` | after success: ini `[LOGIN]`, writes or deletes the credentials file with the `0x0004` `session_token` |
| `0x1423e0430` / `0x1423e05c0` / `0x1423e06b0` | `LoginCredentials_GetFilePath` / `_Load32` / `_Save32` | `Documents\My Games\Path of Exile 2\<name>_login.credentials`, exactly 32 raw bytes |
| `0x140efed60` | `LoginState_HandleAuthenticationError` | non-zero `0x0004` result handler: notice text if present, else the `BackendErrors.dat` text; special codes `0x62` / `0x1cf` (Unlock window), `0x0f` (delete saved credentials), `0x08`, `0x54` |
| `0x141020b20` | | `config.json` loader (`GGG_*`, `STEAM_APP_ID`, `GGG_CREDENTIAL_FILE_NAME`, `GGG_LOGIN_SERVER_PORT`, ...); defaults at `0x1447147a0` |
| `0x1401132a0` | | Steam API init, returns 1 without touching Steam when the platform is not Steam |
| `0x1421fe5d0` | `StandalonePatcher_GetErrorText` | the **patcher's** own 16-entry error table (only caller `StandalonePatcher_Run`); login, create and delete texts come from `BackendErrors.dat` via `0x1425dc920` |
| `0x14011e160` | `Client_Startup` | WinMain-level: single-instance check, config, `StandalonePatcher_Run` (call `0x14011e8b6`), `CmdLine_ReadSuccessEvent`, then engine/state init; `SetEvent`+`CloseHandle` of `DAT_144448668` at `0x14011f256` |
| `0x140118c10` | `StandalonePatcher_Run` | returns bool; Steam/Epic return 1 at once; returns 1 when `--success-event` is given and `--disable-client-switching` is not; else opens the patcher window. First bytes `48 8B C4`; the DLL safety net writes `B0 01 C3` |
| `0x1427499e0` | `Patcher_RunPatching` | "Started patching ({} free bytes available)" `0x1435a2cd0`, "No patching required" `0x1435a3430`; only caller `StandalonePatcher_Run` |
| `0x142749480` / `0x142745eb0` | | `/client/record-patching-metrics` sender / its only caller (inside the patcher) |
| `0x1428dcab0` / `0x1428ddef0` / `0x1428dedf0` | | patcher window: create (`MainWindowClass` `0x1435c27e0`), class registration, `/launcher/patch/start` |
| `0x14011a580` | `CmdLine_ReadSuccessEvent` | parses `--success-event <int>` into `DAT_144448668` (-1 initially) unless `--disable-client-switching` |
| `0x1401136a0` | `CmdLine_BuildOptionTable` | registers every command-line option (`--patching-server`, `--require-launch`, `--success-event`, `--nologo`, `--language`, ...); no `--nopatch` |
| `0x1423dc3c0` | `CmdLine_ParseArgs` | `--opt value` / `--opt=value`; unknown args only log `[CMD][Unrecognized]` (`0x143537f00`) |
| `0x1423dd340` | | reads an integer option value (`wistringstream`), throws "value is not an integer" |
| `0x14010d570` / `0x14010d5d0` | | config singleton / its default builder (patch servers `us.patch.pathofexile2.com` `0x142f8a650`, `patch.pathofexile2.tw`, `patch2/3.pathofexile2.tw`, `kr-patch.pathofexile2.com`) |
| `0x141059430` | `Window_CreateMain_POEWindowClass` | registers and creates the game window (class `POEWindowClass`, string `0x142f8ce38`); `FUN_14011d570` uses the same class for the single-instance check |

## Remote players, entity lifetime, party and trade
Layouts: [../protocol/entities.md](../protocol/entities.md#other-players-add-actions-remove-party-and-trade). Structs: `modules/protocol/poe-proto/src/player_blob.rs`, `remote.rs`.

| Address | Ghidra name | What |
|---|---|---|
| `0x141e7f190` | `Entity_ReadInitialState` | AddObject blob reader: `u8 flags`, link records, components in template order, `u8 m` keyed entries (`0x141e8bd50`) |
| `0x141e7f490` | `Entity_ReadLinkRecords` | `u8 n`, each `u32 key, u8 tag`, values by `0x141e8cb40`; stored in the entity's property map (`entity +0x28`: `0x142201370` / `0x142200d10`) |
| `0x141e8cb40` | `LinkRecord_ReadValues` | `u8 count`, then (count != 0) `u8 kind` and `count` values: kind 1 = `u32` entity ids (resolved by `0x141e800a0`, unresolved queued by `0x141e81280`), others via the reader table at `0x1434e97c0` (kind `0x0a` `0x141e8ef30`, `0x0b` = `u32` `0x141e8f020`, `0x0c`-`0x0e` `0x141e8f120`/`0x141e8f240`/`0x141e8f350`) |
| `0x141e7f690` | `Entity_Destroy` | `(entity, bool destroy parent chain)`: sets `+0x8c |= 1`, recurses into children (`+0xd0..+0xd8`), appends the entity to the world's delete list (`world +0xc0`), calls vfunc `+0xa8` when id < `0x40000000`; logs "...CannotBeDeleted" for flag `+0x8c & 0x10`. Called by `0x1c5` (flag 0) and `0x2fd` (1) |
| `0x142144e94` (case), `0x142144ea3`, `0x142144ebe`, `0x142145392` | | frame processor cases (`0x142143530`): `0x1c5` -> `Entity_Destroy(e, 0)`; `0x1c6` -> `+0x8d |= 4`, `ObjectInWakeZone` (`0x141e81c60`); `0x1c7` -> `+0x8d &= ~4`, `Entity_LeaveWakeZone` (`0x141e81f90`); `0x2fd` -> skipped when `+0x8c & 1`, deferred when `+0x8c & 4`, `+0x8d & 4` and the type flag `+0x29` is clear, else `Entity_Destroy(e, 1)` |
| `0x141dc2170` | `BuffsComponent_Read` | `u16 n`, each `u16, u8`, body `Buff_ReadBody`, then `0x141dc2bb0` (add the buff to the component) |
| `0x141d7fb10` | `Buff_ReadBody` | `u16 row, u16 buff-definition index (Buffs table stride 0x137), u32 +0x28, u32 +0x2c, u16 +0x38, u32 +0x34, u16 +0x3a, u16 +0x48, u32 +0x44, u32 +0x4c, varuint +0x3c, u8 +0xb8`, `[u16 +0x64 if definition +0xfe]`, `[u32 × k if definition +0x7c]`, `i32 n`, `n × u32` |
| `0x142190fe0` | `StatsComponent_Read` | stat list (`0x1419a25a0`/`0x141e33c80`, applied by `0x1426bec20`); player types (type +0x158 -> +0x20): `u8 +0x168`, `u8` shapeshift form (row + 1 of `FUN_1423f57d0`'s table), `u8 x 3` weapon-set forms (`+0x180..+0x1b0`), `u8 k` + k × (`u8 set id` via `0x142191ca0`, stat list), then `u32 +0x1b0, u8 +0x1b4, u8 +0x1b5` |
| `0x141d8fcb0` | `InventoriesComponent_Read` | `u8 n` x (`u8 slot`, `EquipmentVisual_Read`), `u8 k` x `u32` (applied by `0x141d91aa0` per slot) |
| `0x1426d6280` | `EquipmentVisual_Read` | `u8 id`; `0` = empty, else `0x1426d5e60` and `0x1426d6030` (`u16` row, `u32` row of `Data/Balance/MTXTypeGameSpecific.dat`, `u8`) twice, `u8` (row of a 0x11-byte table), `u16` row, `u8 x 3` |
| `0x14211c660` | `Chat_ProcessCommand` | `/command` dispatcher (from the chat sender `0x14211de90`); case `0x16` sends `0x00b6` through `Social_SendPartyInvite`, case `0x1a` sends `0x00b7`, `0x28`/`0x29` join a chat channel by name (`0x142138280`, global/trade) |
| `0x14211f860` | `Social_SendPartyInvite` | sends `PartyInvite` `0x00b6` (class `0x1434fa4b8`, `u8 local player` from session `+0x181`, wstring name) and raises the UI event `FourSocialPartySend` (string `0x14351c730`) |
| class vtable `0x1434fa4b8` | | generic `u8 + wstring` packet class (ctor `0x140858540`, serializer `0x141f46220`): `0xb6`, `0xb7`, `0xc7` and others (the chat sender also builds `0xba` from it); the opcode is stored at `+8` by the sender |
| `0x141f44240` | `SocialEntryPacket_Read` | S->C `0x00c6` (flags byte: bit 2 character data, bits 0/1 extra `u16` pairs); handler `0x1421332ea` keeps `0x210`-byte entries in the session at `+0x27d8` (add/update by account) |
| `0x1420fda15` | | account-session case for `0x00c4`: logs "InstanceClientSetSelfPartyInvitationSecurityCode = " (`0x14351c2f0`), stores the `u32` at session `+0x3ec0` |
| `0x141f53510` | | deserializer of `0x0271` (`u8 × 4`); handler not found |
| `0x142165930` | | `0x00c8` PartyUpdate reader (`0x1421656c0` ctor); `0x142166ac0` `0x00d9` TradeState reader; `0x141f52300` `0x00c9`; `0x141f471f0` `0x00da`; `0x141f47150` serializer of `0x00d2`/`0x00c9`; `0x141f4b1c0` `0x00e0`; `0x142160360` `0x0019` |

### Party invitation and trade request, receiving side
Layouts and the flow: [../protocol/entities.md](../protocol/entities.md#party-and-trade-flows).

| Address | Ghidra name | What |
|---|---|---|
| `0x142115ad0` | `Session_HandleAccountMessage` | account-session handler; case `0xc8` PartyUpdate (member roles: 2 leader, 1 member, 0 invited; own state from `members[+0x76]`), `0xc9` PartyEnded (current party id at session `+0x2278`, else the invitation record is erased), `0xd9` TradeState, `0xda` TradeAck, `0xdd`/`0xe0` inventory events |
| `0x142115490` | | member role byte to state: 0 -> 1 (invited), 1 -> 2 (member), 2 -> 0 (leader), else 3 |
| `0x14211a6e0` | `Social_AddPartyInvitation` | adds an invitation record (`0xa0` bytes + flag `+0x2b0`, keyed by party id, vector at session `+0x7620`); raises the event list at `+0x5850` when the leader's social entry was found (flag set by `0x14211a7f0`) |
| `0x140ff40e0` | `PartyInvite_OnReceived_ShowPopup` | listener of that list: builds the popup (`0x140c75310`) and raises `FourSocialPartyReceive`; registered in `0x140fe0390` |
| `0x140ff4300` | | listener of the list at `+0x58d0` (member joined): raises `FourSocialPartyAccept` |
| `0x140c7a4d0` | `PartyInvitePopup_Accept` | accept button: sends C->S `0x00b8` (`u8 local` from session `+0x181`, `u32` the popup's party id) with the generic `u8 + u32` class `0x1430b4930` |
| `0x140c7a440` | `PartyInvitePopup_Decline` | decline button: raises `FourSocialPartyDecline`, calls `Social_SendPartyDecline` |
| `0x14211fb00` | `Social_SendPartyDecline` | sends C->S `0x00b9` (same class) unless the id is the party already joined with 2+ members |
| `0x1402cb5a0` | `TradeInvite_ShowPopup` | popup with the string `TradeInviteFrom;` (`0x142fb95c8`) and the trade record; result callback `0x1402cb210` (writes a bool into a promise) |
| `0x1402cb290` | `TradeInvite_OnTradeState` | listener of the `0xd9` event: popup only if trade id != 0, record flags `+0x30` bit 1 set and bit 0 clear, and the character is in the social list (`0x1421388a0`, lookup by character name, case-insensitive) |

## Login results, flags, create and delete
Decoded fields: [../protocol/login.md](../protocol/login.md).

| Address | Name | What |
|---|---|---|
| `0x1420f73e1`..`0x1420f7477` | | case 4 of the login dispatcher: splits the two `0x0004` flag bytes into the ten booleans of the account entry (`+0x30`..`+0x39`, entry size `0x78`, vector at login session `+0xef0`) |
| `0x140efdb00` | `LoginState_AuthenticationResultHandler` | success path: ToU (entry `+0x32`), cheating (`+0x33`), RMT (`+0x34`), update required (`+0x35`), notice popup, or continue (`0x140efec80`) |
| `0x1425dc920` | `BackendError_GetText` | result code to text: `Data/Balance/BackendErrors.dat` row `code - 1` (language `0xb` read directly, others through a language path); `bad-error-code` for an unknown row |
| `0x140f17fe0` | `SelectScreen_UpdateStrictUnlockBanner` | builds/updates `strict_unlock_warning_frame` / `_label` (text `StrictUnlocksEnabledMessage`, id `0x10d4`); needs entry `+0x38` (flag byte 0 bit 6) |
| `0x140f0e500` | `SelectScreen_ShowWidgets` | select-screen enter: on a non-Steam platform shows the strict-unlock banner when an entry has `+0x38` and screen `+0x4b0` is clear |
| `0x140ed01a0` | | (create-screen range) after a successful unlock: deletes the credentials file, sets screen `+0x4b0 = 1` when an entry has `+0x38` |
| `0x140f084a0` | | login-screen widget shown when an entry has `+0x31` |
| `0x1406c4500` | | league start time choice, uses entry `+0x31` and league `+0xe0` bit 5 |
| `0x1406c3410` / `0x1406ca640` | | select-screen refresh: hides widget `+0x6e0` when entry `+0x39` is set |
| `0x142728880` | `CharacterEntries_Read` | reads the character entries of `0x0015` (`0x58`-byte struct, order in login.md) |
| `0x1406bc6f0` | `SelectScreen_SetEntry` | fills one select-screen row from an entry; calls the next three |
| `0x1406bb010` | `SelectScreen_SetEntryPortraitFrame` | entry `+0x44`: `DefaultIconFrame` or `MTX/SupporterIconFrame<id>` |
| `0x1426102a0` | `CharacterPortrait_GetIconPath` | entry `+0x4e` bits 0-4 class, bits 5-7 ascendancy; entry `+0x46` portrait variation |
| `0x1406bbbc0` / `0x1406bba40` | `SelectScreen_SetEntryLocation` / | entry `+0x50` (MiniQuestStates row), areas `+0x48` / `+0x4a` (WorldAreas lookup) |
| `0x140f14a70` | `SelectScreen_OnCharacterDetails` | caches the preview event (31 gear slots, two `u16`, pairs, shapeshift form) per character index |
| `0x1420f7584`..`0x1420f7986` | | `0x0015` handler: stores the list in the account entry (`+0x40` vector, `+0x58`/`+0x59` bytes), builds the preview event; signal at login session `+0xd08` |
| `0x14215df90` / `0x1420f79ae` | | `0x0013` CharacterCreated reader / handler (signal `+0xb08` with account id and result; the `notify` byte makes `0x1420f7a11` build an `/api/tracking-conversions/` request) |
| `0x140ee0be9` | | `0x000c` DeleteCharacter builder (name, `u8` from screen `+0x214`, `u32` account id from `+0x210`) |

## Pathfinder
Algorithm and evidence: [pathfinding.md](pathfinding.md). Signature `path_plan` (feature `path_log`) in `modules/client-hook/signatures/0.5.5f.toml`.

| Address | Name | What |
|---|---|---|
| `0x141ede540` | `Pathfinder_Plan` | the grid search (bounded jump point search, ellipse window of 272 x 272 cells, MSVC heap, line-of-sight thinning); `(goal*, entity, params*, ..., out path*, out count*, out flag*)`, hooked by `path_log` |
| `0x141edc200` | | A*-style fallback when the main search is skipped (monsters/pets, or its window test fails) |
| `0x141ee0a50` / `0x141ee0360` | | window setup: marks cells with dynamic obstacles (other entities) as walls |
| `0x141ee0e20` | | classifies a window cell: 0 free, 1 wall (`level >= value`), 2 outside the terrain or the ellipse |
| `0x141ee10d0` / `0x141ee1540` | | straight / diagonal jump with the jump limit `min(cap, 3 + 5 * alignment + 0.2 * excess)` |
| `0x141ee0fe0` | | whether the neighbour in a direction is a wall (forced-neighbour test) |
| `0x141edc0a0` | | `h` of a cell: distance adjusted by min/max/radius plus `0.001 * |cross|` |
| `0x141eeaa40` | | line-of-sight test of the thinning passes (Bresenham over the grid); called at `0x141edf8b0` / `0x141edfa0c` |
| `0x141eea7b0` | | line-of-sight variant while the entity moves along a line (`0x141edf878` / `0x141edf9d4`): `(cell, q, point p, d, ctx)`, steps from the cell to `q` one cell per axis, then walks the line `p -> d` along its major axis (minor `floor(p_minor + slope * k + 0.49 or 0.5)`, 0.49 for a positive slope) |
| `0x141ed8820` | | inputs of that variant: `p` = the line point (`0x141ed6400`), `q` = `round(p + v * dot(v, cell - p) / |v|^2)`, `v = d - p` |
| `0x141ed6400` | | the point on the entity's line (Positioned `+0x208`): `start (+0x214..) + (end cell (+0x23c..) - start) * clamp(progress)` (progress `+0x284/+0x278`, or `+0x288/+0x274` when `+0x268`), axes swapped back by `+0x22e` (0 and 2) and `+0x22d` (0 and 1); position after the frame's step, cell-centred |
| `0x141b95790` | | whether the variant applies: the line runs (`+0x269` 0, `+0x274` not 0) and its current cell (`+0x248..+0x250`, same swaps) is the grid cell `+0x444/+0x448`; the flag is `[rbp+0x5f8]` of `0x141ede540` |
| `0x141ee1910` | | whether a cell is walkable and not marked a wall in the window |
| `0x141d1a980` | | reads a cell's 4-bit value of layer `n` (value 5 reads as 255) |
| `0x141dd4df0` | | the entity's pathing level from Positioned `+0x1e8` (sizes `+0x1f8/+0x1f9`, extra bytes `+0x1fc..+0x200`) |
| `0x141b85320` / `0x141b855b0` | | sprint/roll action start sets / end clears the larger pathing size (level 4 for characters) |
| `0x1421a30f0` | | world vector to cells: `floor(v * 0.092)` (cell = 250/23 = 10.87 world units) |
| `0x141ed66d0` / `0x141ed6ce0` / `0x141ed6310` | | the client's own digital line from cell to cell that trails the position by up to half a cell; steps it by the frame's distance |
| `0x1419d1930` / `0x1419d17c0` / `0x1419d1a20` | | open-list push / pop (MSVC `push_heap`/`pop_heap` on `f`) and the node array `0x1445f0d80` (16-byte nodes, 0x110 x 0x110) |

## In-client batch generation
Details: [terrain/batch.md](terrain/batch.md). Signature entries (feature `gen_batch`) in `modules/client-hook/signatures/0.5.5f.toml`.

| Address | Name | What |
|---|---|---|
| `0x1416859c0` | `world_construct_client` | `ClientWorld` constructor `(this, u8 frame mode, u8 flag)`, object size `0x17e8`; vtable `0x1433b15d8` |
| `0x14213dd60` | | base world constructor (called by the ClientWorld one only) |
| `0x141ffe1d0` / `0x141ffe5f0` | `terrain_gen_construct` / `terrain_gen_destroy` | base generator constructor `(generator, world)` / destructor; generator `+0xe` (u8, 1 after construction) enables the tile map validation pass, which `ClientWorld_LoadArea` clears |
| `0x142007a30` | `terrain_topology_pick` | generator vtable `+0`: reads stats `0xb92` (forced topology, 1-based, `<= row +0x60`) and `0xb93` (forced orientation + 1), world `+0xc0` (league mode); `0x1420078a0` picks the graph |
| `0x14200c360` / `0x141fac6a0` / `0x141fac160` | | validation pass (only when generator `+0xe`) / driver / "Invalid TileMap: ..." checks |
| `0x1423ca520` / `0x1423ca3c0` / `0x1423ca470` | `flat_map_set` / get / contains | sorted `(i32 key, i32 value)` map at `container +8 .. +0x10`; the world stats at world `+0x130` |
| `0x140225df0` | `world_areas_table` | `Data/Balance/WorldAreas.dat` table getter `(out)` -> counted reference; table `+0x28` -> `(begin, end)`, 442 rows of `0x2e0`, row `+0` id string pointer, `+0x2a` hash16, `+0x60` / `+0x68` topologies, `+0x1b4` kind |
| `0x1421e6ef0` | `resource_wait_loaded` | blocks until resource state `+0x40` is 2 |
| `0x142bcc880` / `0x142bcc760` | `game_alloc` / `game_free` | the game's allocator (per-thread heaps, free from any thread) |
| `0x142c26748` | `vcrt_getptd` | the statically linked C++ runtime's per-thread data; `+0x58` chain of catch-block frame infos (`_IsExceptionObjectToBeDestroyed` `0x142c25ec0`) |
| `0x141f0d4f0` | | Incursion temple room object constructor: reads the `WorldAreas` table from world `+0xa8` |
| world `+0xa0` / `+0xa0` / `+0xb8` | `world.area` / `world.area_table` / `world.league_mode` | area row / counted table reference / league mode |
| world `+0x4b8` / `+0x4b4` / `+0x663` / `+0x8d0` | `world.gen_state` / `world.gen_seed` / `world.gen_flag` / terrain | generation state (u32 first LoadArea argument; seed) / headless flag / the embedded terrain object |

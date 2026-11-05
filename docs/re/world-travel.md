# World travel: transitions, waypoints, checkpoints, world map

Client facts for P9 ([plan](../plans/r4-world.md)), from the capture `2026-11-02_18-31-34_336` and static RE. Marked **inferred** or **untested** where no capture or game test proves it. Longer notes while P9 runs: `runtime/r4/world-panel-re.md`.

## Objects
Official servers stream these by range with `AddObject`, not all at entry. Keys are `murmur2(path)`; `Metadata/MiscellaneousObjects/AreaTransition_Animate` is the fog gate (key `0x41012847`, from the capture; the hash of that path was not computed yet), `Waypoint` `0x20e8d38a`, `Checkpoint` as listed in `dumps/<version>/client-tables/object_types.txt`.

Blob (flags, `n`=0, then Positioned): `i32 x, i32 y, f32 angle, u16 team, u8 flags[3]` with optional parts, then Animated `0x41`, `u32 len + UTF-16 .ao path`, `u8`, then the type's tail:
| Type | Positioned flags (captured) | Tail after the Animated `u8` |
|---|---|---|
| Fog gate | zero, or `04 00 00` + `i32 height`, `u16`, `f32` for the `_vert` art | `02, u16 LE target HASH16, u8 index, 7 zero bytes, 01 08 00000000 01 000000` |
| Waypoint | zero, or `04 00 00 ...` | `01 00` |
| Checkpoint | `05 00 00` / `04 00 00`, then `00000000 000000c0 40` | `02 00 00 00 00 00 00` |

The tail fields are copied bytes, not decoded (`InteractionAction` reader `0x141d81480`; the fog gate's own reader was not found).

## Which area a transition leads to
`WorldAreas.Connections[N-1]` for a transition in a room whose graph node has tag `entranceN` (`G1_2`: `town_N` `entrance1` -> `G1_town`, `mud_entrance` `entrance2` -> `G1_3`, `exit_woods` `entrance3` -> `G1_4`, all as the capture shows). The blob's `index` is the place among equal targets: `G1_town` Connections `[G1_1, G1_2, G1_2, G1_2, G1_16]` has three gates with target `G1_2` and index 0, 1, 2. Rule proved on these two areas only; the survey (`area_objects --survey`) must confirm it for the campaign.

The generator already places these objects: `G1_town` seed 1 gives gates at (324,189), (453,284), (383,398), identical to the official cells. `Doodad::exists(Side::Server)` keeps them; `TileMap::tagged_rooms` gives the room's tags. `AreaTransition_Auto` markers (`marker3.ao`) stand next to the gates and were not seen in the capture.

## Clicking an object
Client: `UseSkill` (`0x1a5`) skill `0x2000c266`, target flag 8, entity, the object's cell. Official reply: `StartAction` (flags `0x90`, target entity), `ActionEvent`, `UseSkillAck`, `SkillInputEndAck`, then:
- **Out of range:** nothing further; the capture's clicks from afar did not walk the player in the slice read (t 81.5-83 s). How far the official server walks is **open**.
- **Fog gate in range:** the client sends `ExitReport` (`0x355`) and goes to the area. Ctrl-click (`flags 0x0404`): `0xce` (instance list), client `0xcf` (`01 ff` new, **inferred**), then the transfer.
- **Waypoint in range:** `0x5a` then `0x98` (below); the client answers `0x5b`, then `0x2f1` and the transfer.

Touching a waypoint or checkpoint: `0x6b` (`u8 local, u32be entity`; sets `checkpoint_state` old 1, new 2; `session+0x2274`), `0x196`, `0x2ff`, and for a checkpoint `0x2f9` `04 02 0001 000000` on the object. `006b 01 00000000` clears it.

## Messages
| Op | Wire | Effect |
|---|---|---|
| S `0x5a` | `u8, u32be entity, mask[22]` | Waypoint mask, session `+0x2318`, handler `0x142123878`. On every entry with entity 0, and with the waypoint entity right before `0x98` |
| S `0x98` | `u8 local, u8 sub, u32be a, b, c, d` | Handler `0x1421111c0`. Sub 0 opens the World panel (a = entity, b = mode; `0x140bac280`). Sub `0x2a` opens the large area map (`0x140ff5860`; **static only**) |
| C `0x5b` | `u8 local, u16be HASH16, u32be entity, u8 flags` (bit 7 ctrl) | Waypoint choice (`0x141f396f0`) |
| S `0x2f1` | `u8, u16be HASH16, u8` | Starts the load (`0x14211fc50`); last byte 02 after `0x5b`, 00 walked, meaning **open** |
| S `0xce` | `u8, u16be hash, u8, u8 n, n x (u64, u32be, u8, u8 m, names)` | Instance list |
| C `0xcf` | `u8 local, u8 choice` | Instance choice |
| S `0x352` | `u8 (not read), u8 n, n x (u8 bit 7 boss, bits 0-6 index; u16be x, u16be y)` | Checkpoint warp list, session `+0x2330`, case `0x142125446`; sent at entry |
| C `0x353` | `u8 local, u8 index` | Warp request (`0x140cfd2a0`). **Never captured**, server reply unknown; use the teleport the server already has |

Waypoint mask bits (`0x141f68b30`, list `0x141f68930`): position among WorldAreas rows, in table order, with `HasWaypoint` and `+0x1b4` (schema `_45`) in {1, 2, 31}. Bit 0 `G1_town`, bit 1 `G1_2`, bit 2 `G1_4`, bit 3 `G1_5`; 103 bits (`runtime/r4/waypoint_bits.tsv`).

## Checkpoint warp: the client has the UI
Answer to the spec's open question: **the client offers it, the overlay does not need to pick a destination.** The area map (`AreaMapScreen`, UI `+0x970`, ctor `0x140cfb370`) shows one button per `0x352` entry ("Travel to Checkpoint", "Travel to Boss Checkpoint", index 0 = "WarpWaypointButtonHover"), rebuilt on every `0x352` (`0x140cfce10`), visible only while that screen is open. The capture shows `03 010b 049e` and `00 0137 0471` for `G1_2` after re-entry: index 0 is the waypoint at its cell, others are touched checkpoints. Clicking one sends `0x353`. The capture has no checkpoint click and no `0x353`. The client has no special code for clicking a Checkpoint, so a click should get `0098 <local> 2a 0 0 0 0` (**inferred**, test it).

## World panel unlock state
Node `+0x2d0` is a `MapPins` row, flags `0x140b747e0`:
- `+0x31e` waypoint active = mask bit of `MapPins.WorldArea`.
- `+0x319` visited = mask bit and every `WorldAreas.RequiredFlags` set (`0x141dd3060`), or any `QuestFlags2` set.
- `+0x318` shown = any `QuestFlags1` set.

Flags are the first `AddObject` Player list (Player `+0x248`, `u16 n + (u8 chunk, 8 bytes)[n]`; chunk = flag >> 6, byte = (flag & 63) >> 3, bit = flag & 7). `WorldAreas.FlagOnEntered` gives the `Visited-*` flag (2889 `Visited-G1_1`, 2890 `G1_town`, 2891 `G1_2`; 2934 `MillerDefeated`). `G1_town` and `G1_2` require 2934.

Minimal bytes, **untested**: `005a 00 00000000 03 00*21`; Player list `0100 2d 000e000000004000`.

Warp from the panel needs panel `+0x340` != 0 (`0x140bb4a70`): a panel opened with M alone cannot warp, only one opened by `0x98` with a waypoint entity. What makes an act's tab selectable is **unproven**; test it with the flags above. Which message changes a flag after spawn is unknown (writers `0x141dd222e`, `0x141e9483b`, `0x141eb4701`), so an unlock may need a re-entry.

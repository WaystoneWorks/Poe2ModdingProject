# World travel: transitions, waypoints, checkpoints, world map

Client facts for P9 ([plan](../plans/r4-world.md)), from the capture `2026-11-02_18-31-34_336` and static RE. Marked **inferred** or **untested** where no capture or game test proves it. Longer notes while P9 runs: `runtime/r4/world-panel-re.md`.

## Objects
Official servers stream these by range with `AddObject`, not all at entry. Keys are `murmur2(path)`; `Metadata/MiscellaneousObjects/AreaTransition_Animate` is the fog gate (key `0x41012847`, from the capture; the hash of that path was not computed yet), `Waypoint` `0x20e8d38a`, `Checkpoint` as listed in `dumps/<version>/client-tables/object_types.txt`.

Blob (flags, `n`=0, then Positioned): `i32 x, i32 y, f32 angle, u16 team, u8 flags[3]` with optional parts, then Animated `0x41`, `u32 len + UTF-16 .ao path`, `u8`, then the type's tail:
| Type | Positioned flags (captured) | Tail after the Animated `u8` |
|---|---|---|
| Fog gate | raw head after the angle: `0000 000000` (cylinder), `0000 040000 eeffffff 0000 1143` (`_vert`, `G1_2`), `0000 050000 fdffffff 0000 f041` (`_vert`, `G1_3`) | `02, u16 LE target HASH16, u8 index`, zeros, `01 08 00000000 01 000000`. Zeros: 6 bytes in `G1_town`, 5 in `G1_2` and `G1_3`, unexplained |
| Waypoint | raw head: `0000 000000` or `0000 040000 00000000 0000 0000` | `01 00` |
| Checkpoint | raw head: `0000 040000` or `0000 050000`, then `00000000 0000c040` | `02 00 00 00 00 00 00` |

These are captured bytes, not decoded (`InteractionAction` reader `0x141d81480`; the fog gate's own reader was not found: `0x141e01980`, slot `+0x98` of the vtable tried, reads a different layout, so that vtable is probably not the right one).

## Which area a transition leads to
A room's gates in placement order take `entranceN` (`WorldAreas.Connections[N-1]`), then `teleportN` (the room tagged `telepadN`, inside the instance; tags only, **inferred**). A gate left over takes the next connection no tag names: `G1_town` has one room tagged `entrance1`, connections `[G1_1, G1_2, G1_2, G1_2, G2_1]` and gates `AreaTransition` (115,376), then (324,189), (453,284), (383,398), which the capture shows leading to `G1_2` with index 0, 1, 2 (proven for this area). `G1_2`'s `entranceN` gates fit the capture too; the gate to `G1_4` was not seen. Gates with nothing left repeat the room's last target, or pair up as teleports (**no evidence**). Code and coverage: `poe_world::objects`, `area_objects --survey`.

Arrival: on a waypoint, its own cell (4 of 4). By a gate, 15 to 39 cells away across the gate's facing, on the open side: gate (449,474) angle 3.142 arrival (452,506); (976,1162) 3.142 (975,1123); (249,1207) 1.577 (279,1210); (383,398) 0 (380,383). `travel::gate_arrival` approximates it; the exact cell rule is unknown.

The generator already places these objects: `G1_town` seed 1 gives gates at (324,189), (453,284), (383,398), identical to the official cells. `G1_2` with the official seed `750761653` gives other cells than the capture (gate (1001,474) against (449,474)): `area::generate` did not reproduce the official layout there; the server forces its own layout, so its objects still follow from what it generates. `Doodad::exists(Side::Server)` keeps them; `TileMap::tagged_rooms` gives the room's tags. `AreaTransition_Auto` markers (`marker3.ao`) stand next to the gates and were not seen in the capture.

## Clicking an object
Client: `UseSkill` (`0x1a5`) skill `0x2000c266`, target flag 8, entity, the object's cell. Official reply: `StartAction` (flags `0x90`, target entity), `ActionEvent`, `UseSkillAck`, `SkillInputEndAck`, then:
- **Far click:** official `StartAction` and ack at the click, no `0x64`, `ActionEvent` on arrival. A click from 41.4 cells acted 0.4 s later at (292,276), 26.0 cells from the waypoint. Clicks from up to 25.5 cells act at once. So the reach is about 26 cells.
- **Ruled out:** range as the reason for the clicks at t 81.6 and 82.9 that did not transfer: t 90.5 transferred from the same cell. Their reason is unknown.
- **Fog gate in range:** the client sends `ExitReport` (`0x355`) and goes to the area. Ctrl-click (`flags 0x0404`): `0xce` (instance list), client `0xcf` (`01 ff` new, **inferred**), then the transfer.
- **Waypoint in range:** `0x5a` then `0x98` (below); the client answers `0x5b`, then `0x2f1` and the transfer.

Types: a gate has the `AreaTransition` component, a waypoint interaction `action_name=waypoint`, a checkpoint `ControlZone` (`.ot`). Only the fog gate, `Waypoint` and `Checkpoint` component sets have captured blobs; other sets are sent as those types with their own art (**untested**). No capture holds a healing well: its blob is a guess. `HealingWell*` are static, the others are not.

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

Warp from the panel needs panel `+0x340` != 0 (`0x140bb4a70`): a panel opened with M alone cannot warp, only one opened by `0x98` with a waypoint entity. What makes an act's tab selectable is **unproven**; test it with the flags above. Which message changes a flag after spawn is unproven: the server sends the Player delta `0x0002` flag words (reader `0x141dd0b90`, near writer `0x141dd222e`; **untested**); otherwise an unlock needs a re-entry.

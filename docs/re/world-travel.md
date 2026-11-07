# World travel: transitions, waypoints, checkpoints, world map

Client facts for P9 (done), from the capture `2026-11-02_18-31-34_336` and static RE. Marked **inferred** or **untested** where no capture or game test proves it. Game tests of 2026-11-05 (`r4-objects`, `r4-click`, `r4-travel`, `r4-unlock`, `r4-areas`, `r4-ctrl`, `r4-gates`, [setup.md](../guides/setup.md#game-tests-cargo-xtask-game-test)) pass on a private server. Longer notes: `runtime/r4/world-panel-re.md`, `runtime/r4/areatransition-re.md`.

## Objects
Official servers stream these by range with `AddObject`, not all at entry. Keys are `murmur2(path)`; `Metadata/MiscellaneousObjects/AreaTransition_Animate` is the fog gate (key `0x41012847`, murmur2 of that path, test in poe-data `hash.rs`), `Waypoint` `0x20e8d38a`, `Checkpoint` as listed in `dumps/<version>/client-tables/object_types.txt`.

Blob (flags, `n`=0, then Positioned): `i32 x, i32 y, f32 angle, u16 team, u8 flags[3]` with optional parts, then Animated `0x41`, `u32 len + UTF-16 .ao path`, `u8`, then the type's tail:
| Type | Positioned flags (captured) | Tail after the Animated `u8` |
|---|---|---|
| Fog gate | raw head after the angle: `0000 000000` (cylinder), `0000 040000 eeffffff 0000 1143` (`_vert`, `G1_2`), `0000 050000 fdffffff 0000 f041` (`_vert`, `G1_3`) | AreaTransition (`0x141db7af0`): the `u8` 0 above, destination `02` + `u16 LE HASH16` (`0x141da8d90`; tags 0 and 1 take a `u32`, meaning unknown), then a varuint index (`0x1419a25a0`) **only** when the area is a town (`WorldAreas` row `+0x14`) and that `u8` is 0; then `00*6 01 08 00000000 01 000000` (Stats count 0 first; same in every capture). An index byte outside a town shifts the rest: `BufferUnderflow`, the load never ends (`G1_8`) |
| Waypoint | raw head: `0000 000000` or `0000 040000 00000000 0000 0000` | `01 00` |
| Checkpoint | raw head: `0000 040000` or `0000 050000`, then `00000000 0000c040` | `02 00 00 00 00 00 00` |

Waypoint and checkpoint tails are captured bytes, not decoded (`InteractionAction` reader `0x141d8e560`). The AreaTransition component vtable is `0x1434e5d38` (slot `+0x98` reads), found by the string "Cannot enable AreaTransition. No destination has been set." (`0x1434e1ca0`); ruled out: `0x141e0eda0` (vtable `0x1434edc40`) and the factory vtable `0x1434e4060` (three slots). Notes: `runtime/r4/areatransition-re.md`.

## Which area a transition leads to
A room's gates in placement order take `entranceN` (`WorldAreas.Connections[N-1]`), then `teleportN` (the room tagged `telepadN`, inside the instance; tags only, **inferred**). A gate left over takes the next connection no tag names: `G1_town` has one room tagged `entrance1`, connections `[G1_1, G1_2, G1_2, G1_2, G2_1]` and gates `AreaTransition` (115,376), then (324,189), (453,284), (383,398), which the capture shows leading to `G1_2` with index 0, 1, 2 (proven for this area). `G1_2`'s `entranceN` gates fit the capture too; the gate to `G1_4` was not seen. Gates with nothing left repeat the room's last target, or pair up as teleports (**no evidence**). Code and coverage: `poe_world::objects`, `area_objects --survey`.

Arrival: on a waypoint, its own cell (4 of 4). By a gate, 15 to 39 cells away across the gate's facing, on the open side: gate (449,474) angle 3.142 arrival (452,506); (976,1162) 3.142 (975,1123); (249,1207) 1.577 (279,1210); (383,398) 0 (380,383). `travel::gate_arrival` approximates it; the exact cell rule is unknown.

The generator already places these objects: `G1_town` seed 1 gives gates at (324,189), (453,284), (383,398), identical to the official cells. `G1_2` with the official seed `750761653` gives other cells than the capture (gate (1001,474) against (449,474)): `area::generate` did not reproduce the official layout there; the server forces its own layout, so its objects still follow from what it generates. `Doodad::exists(Side::Server)` keeps them; `TileMap::tagged_rooms` gives the room's tags. `AreaTransition_Auto` markers (`marker3.ao`) stand next to the gates and were not seen in the capture.

## Clicking an object
Client: `UseSkill` (`0x1a5`) skill `0x2000c266`, target flag 8, entity, the object's cell. Official reply: `StartAction` (flags `0x90`, target entity), `ActionEvent`, `UseSkillAck`, `SkillInputEndAck`, then:
- **Far click:** official `StartAction` and ack at the click, no `0x64`, `ActionEvent` on arrival; `0x5a`, `0x98` about 100 ms (3 frames) after it, when slot 0's `Interaction` ends (official 58.859, 537.112; the hook's slot 0 end is 3 frames after its start). A click from 41.4 cells acted 0.4 s later at (292,276), 26.0 cells from the waypoint. Clicks from up to 25.5 cells act at once.
- **Reach (static, fits the capture and the game test):** skill `0x2000c266` is the `Interaction` action (type `0xc266` = fold16 of the name, create `0x14146ecb0`, vtable `0x1432dbcc0`). It goes through the Move slot (`vf48` `0x14198e920` false), so the client walks until `Pathfinding_IsArrived` (entity branch `0x141dd8d10`) holds, at once if it holds already, and a click in reach during a walk stops the line. **Where it stops:** `Pathfinding_Plan` passes the request `pf+0x520` to the search (`max_dist = r1`, `radius = targeting`), so the path ends on the first ring cell; the line ends there, `Pathfinding_OnLineDone` arrives and `0x141df1e90` finds no line to run on (hook, 10 of 10 distances: `+0x28c` = 0), so there is no stop step. Ruled out: the `Interaction` start stopping the line. Ring: `d <= r1 + targeting`, with `r1 = reach + max(player object_size, secondary_object_size) - 1` (`vf220` `0x14198ee90`, `Action_GetPathRequest` `0x141985f10`) and `targeting` = `Positioned +0x1fa`: `object_targeting_size`, else the larger object size (`0x141de5180`). `reach` (`0x14198db20`): `object_size + 13` (a `WorldItem` 20), or for Player `+999` modes 2 and 3 `object_size + 30`; a non-zero `interaction_distance_override` (modes 2, 3: `console_...`) replaces it when `interaction_distance_override_ignores_minimum` is set, else takes the larger. One cell beyond the ring also counts when the step in is blocked. The player's sizes are 0 and 4: **waypoint 26** (size 5, override 10), **checkpoint 20** (size 2, override 10), `AreaTransition_Animate` 22 (size 3). `requires_line_of_sight` (`+0x1d9`) is off on these three, so no line test (`vf240` `0x14198f5e0` gives 2). `Player +999` comes from our Player blob; the server ports modes other than 2 and 3 only.
- **During the coast after a sprint:** `Actor_StartQueuedAction` drops an action while `SprintEnd` plays only when its vf `+0x70` is true. A plain Move's is 1; `Interaction`'s is `0x140108d20` = 0, so the click ends the clip: the client stands from the frame of the `StartAction` when in reach (hook, position constant from that frame), and otherwise walks to the ring at once. Game test `b4-sprint-click`.
- **Ruled out:** porting the aim echo's turn before a coast. When the client drains the sprint-off and the next `0x1dc` in one frame, it turns first and coasts along the new facing, away from the server, until the next message with a cell corrects it. The official server echoes one frame after the sprint-off too (seven sessions with sprints, first echoes within a frame), so this race is the game's own.
- **Ruled out:** range as the reason for the clicks at t 81.6 and 82.9 that did not transfer: t 90.5 transferred from the same cell. Their reason is unknown.
- **Fog gate in range:** the client sends `ExitReport` (`0x358`) and goes to the area. Ctrl-click (`flags 0x0404`): the client shows its Instance Manager from `0xce`; NEW sends `0xcf` choice 255 (`0xff`) and the server transfers (game test `r4-ctrl`). Our rows show "Closed" and 1970 dates: the row's `u64` shows as the creation time (we send the instance id) and the `u32` as time left; row fields not decoded. Game: a gate click in `G1_town` transfers to `G1_2`.
- **Waypoint in range:** `0x5a` then `0x98` (below); the client answers `0x5b`, then `0x2f4` and the transfer.

Types: a gate has the `AreaTransition` component, a waypoint interaction `action_name=waypoint`, a checkpoint `ControlZone` (`.ot`). Only the fog gate, `Waypoint` and `Checkpoint` component sets have captured blobs; other sets are sent as those types with their own art (**untested**). No capture holds a healing well: both guessed blobs (the checkpoint tail; InteractionAction flags before Animated and an empty StateMachine) hang the area load, so wells are not spawned (`[travel] skip_objects = ["HealingWell"]`). `HealingWell*` are static, the others are not.

Touching a waypoint or checkpoint: `0x6b` (`u8 local, u32be entity`; sets `checkpoint_state` old 1, new 2; `session+0x2274`), `0x196`, `0x2ff`, and for a checkpoint `0x2fc` `04 02 0001 000000` on the object. `006b 01 00000000` clears it.

## Messages
| Op | Wire | Effect |
|---|---|---|
| S `0x5a` | `u8, u32be entity, mask[22]` | Waypoint mask, session `+0x2318`, handler `0x142132ab9`. On every entry with entity 0, and with the waypoint entity right before `0x98` |
| S `0x98` | `u8 local, u8 sub, u32be a, b, c, d` | Handler `0x142120090`. Sub 0 opens the World panel (a = entity, b = mode; `0x140bb1140`). Sub `0x2a` opens the large area map (`0x140ffdf80`; **static only**) |
| C `0x5b` | `u8 local, u16be HASH16, u32be entity, u8 flags` (bit 7 ctrl) | Waypoint choice (`0x141f479e0`) |
| S `0x2f4` | `u8, u16be HASH16, u8` | Starts the load (`0x14212ed70`); last byte 02 after `0x5b`, 00 walked, meaning **open** |
| S `0xce` | `u8, u16be hash, u8, u8 n, n x (u64, u32be, u8, u8 m, names)` | Instance list |
| C `0xcf` | `u8 local, u8 choice` | Instance choice |
| S `0x355` | `u8 (not read), u8 n, n x (u8 bit 7 boss, bits 0-6 index; u16be x, u16be y)` | Checkpoint warp list, session `+0x2330`, case `0x142125446`; sent at entry |
| C `0x356` | `u8 local, u8 index` | Warp request (`0x140d05410`). Seen from the client in game: index 2 after a checkpoint click; the server answers with a teleport only (to (328,1014), drift 0.71 cells) |

Waypoint mask bits (`0x141f77180`, list `0x141f76f80`): position among WorldAreas rows, in table order, with `HasWaypoint` and `+0x1b4` (schema `_45`) in {1, 2, 31}. Bit 0 `G1_town`, bit 1 `G1_2`, bit 2 `G1_4`, bit 3 `G1_5`; 103 bits (`runtime/r4/waypoint_bits.tsv`).

## Checkpoint warp: the client has the UI
Answer to the spec's open question: **the client offers it, the overlay does not need to pick a destination.** The area map (`AreaMapScreen`, UI `+0x970`, ctor `0x140d034e0`) shows one button per `0x355` entry ("Travel to Checkpoint", "Travel to Boss Checkpoint", index 0 = "WarpWaypointButtonHover"), rebuilt on every `0x355` (`0x140d04f80`), visible only while that screen is open. The capture shows `03 010b 049e` and `00 0137 0471` for `G1_2` after re-entry: index 0 is the waypoint at its cell, others are touched checkpoints. Clicking one sends `0x356` (`u8 local, u8 index`; handler `0x140d05410` sends it when screen `+0x318` is set; `0x140d04360` sets it and builds the buttons from session `+0x2330` via `0x140d04f80`; node ctor `0x140d03000`). The button for the player's current spot reads "You are here" (the player marker `AreaNodePlayer` covers nodes close to the player at that map scale). The capture has no checkpoint click; in game a click is answered `0352`, `0098 01 2a 00..` and opens the map titled "Checkpoints" (sub `0x2a` confirmed).

## World panel unlock state
Node `+0x2d0` is a `MapPins` row, flags `0x140b78790`:
- `+0x31e` waypoint active = mask bit of `MapPins.WorldArea`.
- `+0x319` visited = mask bit and every `WorldAreas.RequiredFlags` set (`0x141de0210`), or any `QuestFlags2` set.
- `+0x318` shown = any `QuestFlags1` set.

Flags are the first `AddObject` Player list (Player `+0x248`, `u16 n + (u8 chunk, 8 bytes)[n]`; chunk = flag >> 6, byte = (flag & 63) >> 3, bit = flag & 7). `WorldAreas.FlagOnEntered` gives the `Visited-*` flag (2889 `Visited-G1_1`, 2890 `G1_town`, 2891 `G1_2`; 2934 `MillerDefeated`). `G1_town` and `G1_2` require 2934.

Minimal bytes (work in game: with `waypoint unlock all` the panel has tabs Act 1-4 and Interlude, which appears with act 6 waypoints; a click on a `G1_2` node travels and arrives on the waypoint cell (585,1344)): `005a 00 00000000 03 00*21`; Player list `0100 2d 000e000000004000`.

Warp from the panel needs panel `+0x340` != 0 (`0x140bb9910`): a panel opened with M alone cannot warp, only one opened by `0x98` with a waypoint entity. The act tabs list only acts with unlocked waypoints. The panel key is `U` (`0x55`); `M` opens the shop. Flag changes after spawn go by the Player delta `0x0002` flag words (reader `0x141dddd40`, near writer `0x141ddf3de`).

## AreaTransition kinds and clickability
First byte `b` of the component: kind = `b & 0x7f` (`+0x30`; 0 area gate, clickable; 1 teleport, walked onto, not clicked; 3 special; 4 town), bit 7 disabled (`+0x33`; the delta reader `0x141db7be0` reads a `u8` v and calls Enable(v == 0)). Client class vtable `0x1433b6ab8`, reader `0x1416eb710`. Destination tags 0 and 1 take a `u32` (meaning unknown; "set" when non-zero, `0x1416ebb50`), tag 2 a `u16` HASH16. A gate is clickable only with kind 0 and a destination area row (`0x1416ebca0` -> `0x1416ebf90`); otherwise it is locked (Targetable `+0x69` via `0x1416ec070`) and a click walks. HASH16 0 locks the gate. The varuint index depends on town and kind 0, not on the tag.

Server rule: in-instance gates (Telepad, Paired) are sent as kind 0 with the current area's HASH16, and the server teleports on the click (`r4-gates`: `G1_8` secret door gate (861,597) to (1184,184)). Room tags ending in `disabled` (e.g. `teleport3disabled-Arena`, `G1_8` boss gate (792,866)) are quest-gated officially; the server spawns them as plain gates and the client does not show (792,866) (not investigated).

Sent type rule: a placed type is sent as itself only when it has the captured type's component names and the same StateMachine `define_shared*` keys (`AreaTransition_Animate_Toggleable` `define_shared_state = "unlocked"` and `AncientSeal*Portal` `define_shared_checkpoint_state`, sent as themselves with the fog gate bytes, threw `BufferUnderflow` in `G2_6`); otherwise the captured type with the object's own art. Art does not change the blob (`G1_8` `ExitTransition_Mausoleum` with `lachlann_portal.ao` loads).

## Coverage
- Offline `python3 scripts/travel-survey.py --seed N` over 106 areas of acts 1-4 and the interludes: seeds 1-3 pass (348-356 gates; every gate has a target inside its area's connections or an in-instance partner). 179 of 190 area links have a gate back; the 11 connections no gate leads to are town-to-town or quest links (e.g. `G1_town`->`G2_1`, `G4_town`->`G3_town`). The generator fails on 2-3 areas per seed (seed 1 `G2_10_1`, `G4_14`; seed 2 `G2_1`, `G2_10_1`, `G3_5`; seed 3 `G1_14`, `G3_8`): not covered.
- Target rules: Entrance and NextConnection fit the capture; Telepad from tags; Paired, Repeat, FirstConnection have no evidence.
- In game: `r4-areas` loads all 19 areas with special travel objects (seed 1: `G1_8 G1_4 G1_5 G1_15 G2_2 G2_4_3 G2_5_1 G2_6 G2_10_2 G3_town G3_3 G3_5 G3_6_1 G3_6_2 G3_9 G4_4_1 P1_1 P3_5 P3_6`). Gate clicks tested: `G1_town`->`G1_2` (`r4-click`), `G1_8`->`G1_7` and the `G1_8` in-instance teleport (`r4-gates`); waypoint and checkpoint travel (`r4-travel`); unlocks (`r4-unlock`).
- A transfer sent while the loading screen is up makes the client `ExitProcess`; scenarios wait for the client's `[LOADING SCREEN]` line.

## Unknown
The clicks that did not transfer in the capture; the exact gate arrival rule (server approximates); the `_vert` gate head. Backlog: [plans/backlog.md](../plans/backlog.md#world-travel-follow-ups-p9).

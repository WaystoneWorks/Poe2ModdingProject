# Server-side code in the client (0.5.5h)

What the 0.5.5h client contains that bears on a server: how the client applies corrections, the simulation code the server must copy, and leftovers of server or offline modes. All addresses are 0.5.5h (Ghidra `/0.5.5h/PathOfExileSteam.exe`). The movement specs this builds on: [movement-click.md](movement-click.md), [movement-positioned.md](movement-positioned.md), [pathfinding.md](pathfinding.md); B4 facts: [world-travel.md](world-travel.md).

Short answer: the client has **no server, offline or listen mode**. The packet classes can serialize both ways, and the base world class can generate terrain without a renderer. Neither the server's tick nor its handling of client packets is compiled in. What helps B4 is the exact correction rule and the A* fallback below.

## Ranked findings

| # | Finding | Helps |
|---|---|---|
| 1 | Corrections are exact-cell snaps with no tolerance or smoothing, and a zero-vector `0x64` never snaps | B4: high |
| 2 | Start inside a blocking entity: the path search hands the request to a full A* | B4: high (warp arrival) |
| 3 | Entity cell test and push rule of the search | B4: medium |
| 4 | Resync message `0x13c` exists, but only outside lockstep | ruled out for B4 |
| 5 | Predictive mode (tolerant corrections) cannot be reached without patching the client | ruled out (declined) |
| 6 | Packet classes carry both serializer and deserializer | server: wire layouts |
| 7 | Server/client markers in scripts and data (`IfIsServer`, ground effect `ServerOnly`) | server: object scripts |

### 1. How the client applies a correction
**`0x64` MoveDirectionUpdate** (Actor handler `0x142159130`, code from `0x142159207`; message vector at `+0x20`, cell at `+0x28/+0x2c`):
```
if vector == (0,0): no position check at all                     // 0x142159220..0x14215922d
if cell == Positioned grid +0x444/+0x448: nothing                // 0x142159244..0x142159254
if world vf +0x1d8 == 1 (predictive) and |cell-grid|^2 < 0x844:  // 46 cells
    bend the vector toward the cell, no snap                     // 0x14215929e..0x1421593c6
else: Positioned_SetLocationForcedNoCallbacks(P, &cell, (cell + 0.5) * 10.869565)   // 0x14215941c
then the vector drives Actor_StartWasdWalk as usual
```
**`0x1c8` StartAction**: `Actor_InstallQueuedMove` `0x141e50030` snaps with the same function iff `start != grid` in lockstep. In predictive mode it snaps only if the squared distance is `0x844` or more ([movement-click.md](movement-click.md)).

**`Positioned_SetLocationForcedNoCallbacks` `0x141de8e70`**: clamps the cell into the terrain, sets the grid `+0x444` and the world position `+0x490` to the cell centre in the same call, and moves the entity between its 23-cell buckets (bucket vfuncs `+0x38`/`+0x28`). It recomputes the height (`+0x440`, `+0x48c`) when `+0x1e6` bit 3 is set, and calls `Positioned_StopMove` when a line runs (`+0x28c` or `+0x314` not 0). An invalid cell is logged (event `0xff735b2e`), and an entity whose bucket token disagrees with its cell throws. No listener runs, so the Pathfinding and Actor see no "moved" event, and nothing blends the old and new positions.

Consequences for B4:
- In lockstep any difference of one cell or more between the server's cell and the client's grid, at the frame the packet is applied, is a visible jump of exactly that distance. A jump of a fraction of a cell also shows, because the world position `+0x490` returns to the cell centre (the client rests up to about 1.5 cells off its grid after a walk-on, measured in B4).
- A `0x64` with a zero vector never corrects, whatever cell it carries. Only non-zero `0x64`s and every `StartAction` can snap.
- A snap stops the running line, so the client's next line starts at the snapped cell with no carried length ([movement-click.md](movement-click.md)).
- So the server cannot hide a drift: the snaps go away only when the server's cell equals the client's grid. That is what the exact-port rule in [decisions.md](../decisions.md#movement-and-world) requires.

The other forced setter, `SetLocationForced` `0x141de86b0`, does the same clamp and bucket move, then calls Positioned vf `+0x120` (moved listeners), `0x141df2610` and `0x141df3550`. It is used by the resync (finding 4).

### 2. The A* fallback for a start inside an entity
In the search `0x141edeb10`, the start cell (`r15`) is tested at `0x141edf07f` / `0x141edf0aa` / `0x141edf16e` with the entity cell test `0x141ee03a0`. The `r12b` test is different: the terrain's free size at the start (`0x141d1af50`) is smaller than the mover's size + 1. If either test fails, `0x141ee008a` passes all the arguments to **`0x141edc7d0`**, the general A*, and returns its result. This is the case of a player who arrives on the checkpoint's cell after a warp (B4 user test 4).

`0x141edc7d0(goal*, entity, params*, u8, out path[0x88], out count*, out reached*, out start_blocked*, u8 is_retry_hint, u32 node_budget, u8 coarse)`:
- Window: 272 x 272 cells (`0x110`) centred on the start, nodes of 16 bytes in a per-thread pool (`0x1419d2080`, open list `+0x121000`, generation stamp `DAT_1445a5110`). Neighbour offsets are `DAT_142f1f5d0/5d4` (8 directions, order table `DAT_142f1f670`, count per direction class `DAT_142f1f6b8`, parent code `DAT_142f1f610`).
- Step cost 1 (straight) or 1.4142 (diagonal). The heuristic is `0x141edc670` (distance to the goal with the params' goal radius `params+8`).
- **Entity cells:** the start is tested with `0x141ede210` (below). If it is blocked, the start node gets flag `0x20` and `*start_blocked = 1`. A neighbour blocked by an entity can be entered only from a node that has `0x20`, at cost **21** per step, and it keeps `0x20`. Once the path leaves the entity it cannot go back in. So the path leaves the ring by the fewest entity cells, then goes on normally. Terrain is checked with `0x141d1af50` (free size >= size level + 1) and the line test `0x141d1d070`.
- Node budget when `param_10` is 0:
  - Unlimited (`-1`) when the entity has a Player component whose byte `+999` is not 2 or 3, or when `0x141edc720(entity)` holds.
  - Otherwise 1000 for an object with `PetAi` or with `0x1401539f0(entity)+0x144 == 3`, else 100 (10 with `param_9`).
  - With an unlimited budget, a node is skipped when its start distance plus its second distance term reaches the bound (`0x141eddbe9`). The bound is `2 x` the start-to-goal distance against 136 and against 20 (50 when `0x141edc720` holds), through the min/max helpers `0x1401528a0`/`0x1401528b0`, whose order is unchecked.
- If nothing reaches the goal, the closest node by heuristic is used (`*reached = 0`). The path is rebuilt from parent codes and smoothed (string pulling with `0x141d1d070` and `0x141ede210` along each Bresenham segment), at most `0x88` points.
- `coarse = 1` (a retry when the first try failed for a non-player with `0x142482d70(...) != 4`) seeds the open list from a half-tile grid (11.5 cells, costs 11.5 / 16.2634, at most 300 nodes) before the fine search.

Port status: ported for a player (`clientpath.rs` `Search::astar`, called by `plan` when the start is inside a blocking object's ring; unit tests `a_start_inside_a_ring_walks_out_cell_by_cell_then_straight`, `a_path_out_of_a_ring_does_not_cross_it_again`). Tables: neighbour order per parent code `DAT_142f1f670` (codes 0 to 3: 3 neighbours, 4 to 7: 5, 8 = start: 8; counts `DAT_142f1f6b8`), parent code `DAT_142f1f610` = the reverse direction. A new neighbour is skipped (not closed) when `|c - start| + |c - goal| >= bound` (unlimited budget only), closed when its free size is below the level + 1 or it is a ring cell entered from outside one. The rebuild walks the parent chain and keeps a cell when the line from its parent to the last kept cell is blocked by terrain (`0x141d1d070`: true when a cell's free size is below its 4th argument; 0 never blocks) or crosses a ring (`0x141ede210` on each cell of the same integer line); no second thinning pass. The waypoint helper `0x141edea10` only matters for the coarse retry (its list is empty otherwise). Not ported: the coarse retry (non-players only), the node budgets of non-players, the `h == 0` line test `0x141d1d4f0` for a goal band (a point goal needs none), and the A* for a start whose terrain is blocked at the mover's level (the server keeps its level-0 retry, which agreed with the client).

### 3. Entity cell test and pushing
`0x141ede210(ctx, cell, flag)` (the A*) and `0x141ee03a0(ctx, cell)` (the main search, with entities collected first into the 17 x 17 bucket table `DAT_14472e3e0`) are the same test. They walk the 23-cell buckets around the cell (terrain `+0x28`, `0x38` per bucket, entries with bit 7 clear) and call the per-entity test (`0x141ede680` / `0x141ee0790`):
- `R = mover size level + 1 + max(entity size +0x1f8, secondary size +0x1f9)` (or the entity's size level `0x141dd53c0` when the context flag is set). The cell is blocked if `d^2 < (R - 1)^2`, with `d` the distance from the entity's grid cell.
- If the cell is within 20 cells of the mover (`0 < d^2 <= 400`) and the entity can be pushed (`0x141df03c0`), the entity is not a wall. Up to 8 such entities are collected, and a push test `0x141dee9e0(mover, list, step direction clamped to -1..1)` decides for all of them together. The result is cached per entity (`0x14184f440`).

The ring the main search draws for a non-pushable entity ([pathfinding.md](pathfinding.md#the-search-0x141edeb10-wrapper-0x141edc7d0-a-fallback-inside)) uses the same `R`.

### 4. Resync `0x13c` (predictive only)
The session handler `0x1421317e0`, case `0x13c` (from `0x142133b4f`), ignores the message when world vf `+0x1d8` is 2 (lockstep, always the case in game). Layout (serializer `0x14216bda0`, class vtable `0x143521808`): `u8`, varuint count, then count x `{u32 entity, i32 x, i32 y}`. Outside lockstep, if any listed entity is 20 cells or more off its grid (`d^2 >= 400`), every listed entity is set with `SetLocationForced` `0x141de86b0`. Otherwise only those at 20 cells or more are set, each logged as `Resyncing <id>` (event `0x2caa0e3c`). This is the "server resyncs drifted entities" of the PoE1 design in [decisions.md](../decisions.md#movement-and-world). It cannot correct a lockstep client.

### 5. Predictive mode
The world frame mode (`world+0x669`, read through vf `+0x1d8`): 1 predictive, 2 lockstep, 3 auto. The in-game world is built with a constant 2 (`0x1410145b6` -> constructor `0x14213e330`, store `0x14213e714`). The only other writer is the session update at `0x14213063f`. It runs only when the mode is 3, and picks a mode from the latency and the `networking_type` option (global `0x14444fab0`: lockstep above 90 ms goes to 0, else 2 below 70 ms; [movement.md](../protocol/movement.md)). No server message sets it. Predictive mode would give tolerant corrections (the `0x64` bend under 46 cells, `0x1c8` under 46 cells, resync at 20 cells) but local movement on the client. Reaching it needs a DLL patch of the constant, which is the client-authoritative shortcut the user declined.

### 6. Packet classes serialize both ways
Every server-to-client class has a full serializer in vtable slot 1, next to the deserializer in slot 2. Examples: `0x64` and `0x1c8` share the class vtable `0x1435227b8` (serializer `0x141f5a240`: `u16` opcode, `u32`, `u32`, `u8`, `u16` header, then the component body), and `0x13c` uses `0x14216bda0`. So the exact layout the official server writes can be read from the client (`scripts/re/packet_layout.py <opcode>`), which is how our layouts are checked. The constructors (`0x142197070` for component messages, `0x142180510` for the instance) are decode factories. The client-to-server classes are referenced only by their sender and a clone vfunc. For `0x1a5` these are vtable `0x1434fc3d8`, sender `0x14211ef20` and clone `0x141f47600`. No factory decodes client packets, so the server's packet handling is not compiled in.

### 7. Server and client markers
- Object scripts (GEAL) have the directives `IfIsServer` (string `0x14350a5d8`), `IfIsClient` (`0x14350a5f0`) and `IfIsTool` (`0x14350a628`), registered with the other `If*` conditions in `0x1426dfbf0` (map `0x1445e7080`, at `0x1426e0b30`). Script blocks under `IfIsServer` are server behaviour that the `.ot`/`.otc` data still carries, for example lighting a checkpoint. They are a source for B5 and object behaviour.
- Ground effect `object_type` values (parser `0x141d88c90`): `Server` 0, `ServerOnly` 1, `ServerFill` 2, `ClientOnly` 3. The server creates every type except `ClientOnly`.
- `HeadlessWorld_LoadArea` `0x14213ed00` is the base world's area loader without rendering (`world+0x663` 0). It is used by our terrain batch ([terrain/batch.md](terrain/batch.md)), not by a server loop.
- The instance cipher builder `0x14212b1e0` takes an `is_client` flag ([crypto.md](crypto.md#side-channel-keys)), so both sides' key setup is present.

## Ruled out
- No server, offline, single-player or listen-server mode: no such strings. The only "server" strings are the markers above, the `networking_type` values `lockstep`/`predictive` (`0x1433f2608`, `0x1433f26c0`) and the resync log.
- No position smoothing for corrections. "Interpolate" strings (`0x143182a48`...) are names of engine update phases, and `interpolation_speed_ms` belongs to the UI.
- C->S `0x13d` is a 1-byte settings message sent once at spawn, not a resync request ([instance.md](../protocol/instance.md)).
- The world vtable around `0x14351ea38` gave no clean diff between base and client world (`0x14351ea30` holds `0x142197070`, not an RTTI locator). Not pursued.

## Suggested follow-up
1. **Port the A* fallback** (`0x141edc7d0` with `0x141ede210`/`0x141ede680`, push test `0x141dee9e0`) into `clientpath`, with rules tests for a start inside the checkpoint's ring. B4's warp-arrival fix avoids the case, but any start inside a ring still makes the server and the client disagree.
2. Done: the DLL's snap detector (`snap_log`, [client-dll.md](../architecture/client-dll.md)) logs every apply with both cells; `scripts/re/snaps.py` lists the snaps.
3. **Read the push test** `0x141dee9e0` and `0x141df03c0` before monsters or other players move. Pushing decides whether an entity is a wall, which matters for drift as soon as two movers meet.
4. **Mine `IfIsServer` blocks** in the `.ot`/`.otc` scripts (checkpoints, waypoints, doors) for B5 and object behaviour, starting from the parser in `0x1426dfbf0`.
5. Open RE items: the `IfIsServer` lambda's body (no vtable found through RTTI), the `0x64` predictive bend formula (not needed in lockstep), and `0x141edc720` (the player-like test that selects the 50-cell bound).

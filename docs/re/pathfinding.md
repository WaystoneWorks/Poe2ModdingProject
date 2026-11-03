# The client's pathfinder (0.5.5e Hotfix 1)

**The client plans every walk itself, with a bounded jump point search over its 4-bit walkability grid**, for click-to-move, WASD, rolls and sprints. The server's port of it is to be rewritten (PLAN step c/d); the server currently stands still. Addresses: [addresses.md](addresses.md#pathfinder); movement spec: [../protocol/movement.md](../protocol/movement.md#the-clients-pathfinder).

## Where it is used
| Caller | What it plans |
|---|---|
| `Pathfinding_StepAlongPath` (`0x141dcc110`) / path request `0x141dcc6a0` | click-to-move and the Move action's walk. The request clamps the vector to the goal to 126 cells (`0x42fc0000`, squared limit `0x4840`) and calls the search with the goal as target. A plan that ends short of the goal is made again the next step |
| `Actor_StartWasdWalk` (`0x141e4fb40`) and the Actor tick (`0x141e42a00`) | WASD and the sprint stream: goal = the entity's cell + `floor(vector * 0.092)` (`0x142193270`), re-aimed by a timer at Actor `+0x3dc` (0.05 s for the player, 0.25 s for others; 2 frames of 33 ms in the logs). While a sprint's `0x64` stream runs, every frame |
| the Move/roll action handlers | rolls: the goal is the roll's remaining distance ahead, re-planned every frame (a straight leg in the open) |

Other entities use the same code. Nothing is server-side or sent: the server only sends the direction/target, the client plans.

## The search (`0x141ed0510`, wrapper `0x141ece1d0`, A* fallback inside)
Signature (as logged by the hook): `(goal*, entity, params*, ?, out path*, out count*, out flag*, ...)`; `params` holds `min_dist`, `max_dist` (wanted distance to the goal; 0, 0 = the goal cell), `radius` (stop that far from the goal, -1 none) and flags. Returns whether the goal was reached; the path is written goal-first, start last, at most 0x88 cells.

- **Grid.** Terrain `+0xd0/+0xe8/+0x100/+0x118` are four 4-bit layers (`ceil(w/2)` bytes per row; the DLL exports them as `terrain_grid_<hash>.bin`, [../architecture/client-dll.md](../architecture/client-dll.md)). The search uses layer 0 (`FUN_141d0df50`): 0 = wall, 1..4 = distance-to-wall ramp, 5 = clear (read as 255). A cell is **blocked when `level >= value`**; level -1 turns the test off.
- **Level (clearance).** `FUN_141dc7d00(Positioned + 0x1e8)`: the larger of the object sizes `+0x1f8` (`Positioned.object_size`, 0 for characters) and `+0x1f9` (`secondary_object_size`, 4) when the extra flags are set, else `+0x1f8`. A roll/sprint start (`FUN_141b77110`) sets `+0x1fc..+0x200` so the level is 4; the end (`FUN_141b773a0`) clears the flag at `+0x1ff`. So **from the roll's sprint until the sprint ends, cells with value <= 4 are walls**: the sprint keeps about 5 cells off every wall (cells with value 5), while walking and rolling use level 0 and hug walls. If the start cell itself is a wall at level > 0, the search is made again at level 0.
- **Window.** 272 x 272 cells (`0x110`) around the start (node array at `0x1445d8970`, 16 bytes per node: `u16` stamp, `u8` flags, ...). Cells outside the terrain, or outside the ellipse with foci start/goal and focal sum `L = clamp(2 * |start-goal|, 20, 136)` beyond radius `0.433 * L` of the midpoint, count as walls.
- **Costs.** Straight step 1, diagonal 1.4142 (`g`). `h` = distance to the goal after the min/max/radius adjustment plus `0.001 * |cross(goal - start, cell - goal)|` (prefers the straight line). Open list: `std::push_heap`/`pop_heap` on `f = g + h` (MSVC implementation: ties are decided by its sift order, so a port must reproduce it exactly).
- **Jump point search with bounded jumps.** Expanding a node jumps along its direction (and the two forced-neighbour directions) until a forced neighbour, the goal, an obstacle or the jump limit; diagonals first check both straights. The limit is `min(cap, 3 + 5 * max(0, dot(unit_dir, cell - goal) / (max_dist + radius + h)) + 0.2 * (g + h - h_start))` (times 0.7071 for diagonals), `cap = clamp(0.33 * h_start, 5, 22)`. The start node expands in all 8 directions.
- **Result.** If no node reaches `h = 0`, the node with the lowest `h` is the end. The path is rebuilt through the parents, keeping only cells where line of sight (Bresenham over the grid; blocked cells and the window edge stop it) to the last kept cell ends; a second pass takes windows of 5 and drops the cells between two visible ones.
- **Start cell.** The client plans from its own grid cell, not the cell of the position (next section).
- **Line of sight to the start while moving.** When the entity moves along its line (`0x141b87580`: the line at Positioned `+0x208` runs and its current cell is the start cell), both passes test the step that ends at the start with a variant (`0x141edc6e0`, inputs `0x141eca7f0`): from the line point `p` (`0x141ec83d0`, the position after the frame's step in cell-centred coordinates, `world / 10.8696 - 0.5`) instead of the start cell. The start cell is projected onto the line `p -> d` and rounded (`q`); the cells from the start to `q` (one step per axis) must be free, then the float line from `p` to `d` is walked along its major axis from `q`, the minor coordinate `floor` of the line's value plus 0.49 (positive slope) or 0.5. Port: `Params::moving`; `Mover` passes its position minus 0.5 when it moved in the previous frame and plans from the cell on its line.

## Planning cell
Plans start in the client's grid cell, which steps along the current line and is not `floor(world / 10.8696)`: exact rule and port in [movement.md](../protocol/movement.md#client-grid-cell). Where the cell lands in a wall the cell of the position is used.

## Evidence
- DLL hook `path_log` (`modules/client-hook`, `[features] path_log` or `POE_HOOK_PATH_LOG=1`, signature `path_plan`): one `PATHPLAN` line per plan of the local player with goal, start, the 7 params, the level bytes and the waypoints. 541 distinct plans (walks, sprints at level 4, rolls, clicks around obstacles and diagonal walls on `MapRiverside`/`G1_1`) are the fixture `modules/server/crates/poe-game/tests/fixtures/clientpath_plans.json`; 5 of them were planned while moving and this log has no line point. A second fixture with the line state (`clientpath_moving_plans.json`, `path_log` dumps Positioned `+0x1e0..+0x290`; 166 plans of a private `cliffs` game test with `POE_HOOK_PATH_LOG` and `POE_HOOK_MOVEMENT_LOG` in `[client_env]`, 123 while moving; extracted by `scripts/re/pathplans.py`) covers the moving variant. Both are reference data for the port; no test reads them now (the grids come from `dumps/0.5.5e.hotfix1/terrain/grids-keep/` or `grids/`).
- The client's per-frame positions follow the logged paths at walking speed with a mean error of 0.013 cells over 246 plan intervals (7 walk cases).

## Open
- Dynamic obstacles (other entities; `FUN_141ed1da0` / `FUN_141ed2330` mark them as walls in the window) and the second grid layers.
- The A* fallback branch (`0x141ece1d0`) for monsters/pets and when the main search is switched off.
- When the server's flag for the moving variant differs from the client's: the client clears it in the first frame of a new line (34 of 159 plans in moving frames), the server sets it from "moved in the previous frame" and the cell on its line.
- `min_dist`, `max_dist`, `radius` other than the player's (0, 0, -1): monsters keep distance to targets.

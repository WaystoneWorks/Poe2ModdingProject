# Graph-based areas (`.tgr`): generation order and layout

Code: `modules/server/crates/poe-world`.

## Generation order, town first

1. `TerrainGen_Run` seeds the RNG with the area seed (after `prepare`'s throwaway seed-0 draws).
   Hideouts seed it **disabled**: `TerrainGen_Run` (`0x14200d1f0`, call at `0x14200d48c`) passes
   `disabled = WorldAreas.IsHideout` (row `+0x12a`) to `TerrainRng_Seed`, every draw returns its
   lower bound, and the layout does not depend on the seed (`area.rs` `rng.disabled`). Towns
   (`IsTown`) are not disabled; `G1_town` uses the batch seed.
2. Topology choice: [shared-passes.md](shared-passes.md#topology-choice). League mechanic rolls
   come before it, see below.
3. Graph nodes are placed by `0x1420d77c0`: candidates matching the node's TileEdgeKey
   (`0x1420d66f0`, 0x68-byte entries, weight at +0x60), weighted pick `below(total)`, position =
   node cell / 23 minus half the candidate's size (+0x31/+0x32), clamped to the map; must fit
   (`0x141d1a430`), otherwise the candidate is removed and drawn again. Town: total weight 8, draw 3.
   `0x1420d77c0` tests the map (still empty then) and `0x1420d3b50` (a neighbour-exit check that
   needs placed tiles), so there is **no rectangle overlap test at room choice**: rooms may overlap
   after the draw and the settle spiral separates them.
4. Rooms are placed by `0x141f9ce60` (room, x, y, orientation): **every cell** of the room grid, x
   outer, y inner (`.arm` grid row = y). Per cell:
   - `k` slot: key = its edges (file order) with exit/virtual exit, size, corner grounds and
     heights, oriented by the room's orientation. Uniform ground and no edges: skipped (the ground
     is only marked; the fill pass places those). Otherwise the tile set is looked up by (slot tag
     as feature, key) and one candidate is drawn with `below(total weight)`. For `k` slots of one
     ground the cell first tries the ground's fill group (as the fill pass does); when no entry
     fits it is placed from the tile set by its key like any other slot.
   - `f <name>` slot: key 1×1, no edges/grounds, exits 3, feature `<name>` (`forcedblank` →
     `forced_blank.tdt`).
   - The tile-set index (`0x141d16660`) lists `(tile, orientation, weight)` per (feature, key) in
     `.tst` order then orientation order 0..7; `.tst` rotation lists (`I R90 R180 R270 FI FR90 FR180
     FR270`, `0x142f08770`) restrict orientations; the default weight is 1. `.tst` `include
     "<file>"` lines (G3_town: `tiles_waterlowered.tst` includes `tiles_walkable.tst`) add the
     included entries first (`generate::collect_tst`).
   - Room slot height (`+0x72`): the lowest corner height moves into the tile height for node
     rooms too, not only overlay rooms.
5. After the room pass (town): 990 × `below(1024)` (`0x1420dcc50`), one `below(0)` (`0x1420c59aa`),
   the fill pass (66 placements, `0x141f9ee04`: weighted `.gft` pick for the cell's ground, then
   orientation), and a pass that re-places 10 key-slot tiles in other orientations (`0x141fed417`).
   The encampment (15×18, `FI R270`) is placed through the room's fixed-tile list (`0x141facf20`),
   not the place-tile calls above.
6. Generator trace kinds: `below`/`range` with exact call sites, `candidates` (the room pass's
   candidate list), `place` (`0x141faca80`: x, y, orientation, height, tile).
7. Fill pass: [shared-passes.md](shared-passes.md#fill).
8. De-repetition: [shared-passes.md](shared-passes.md#de-repetition).
9. Tile hash: the place function (`0x141d18680`) stores each cell's offset from the tile's corner at
   record +0x34/+0x35; only offset (0, 0) cells are hashed.

### League mechanic rolls (`phase_cad0` `0x14200b380`, `league.rs`)

Before the topology draw (`phase_c360`), map areas draw `below(100)` for up to four mechanics, so
every later draw is shifted. Mechanic index 0, 2, 9 and 0xb (indices into the client's mechanics
table, rows of 0xee bytes from `FUN_14266af70`) are rolled in that order. The chance comes from the
area's `WorldAreaLeagueChances` row (`WorldAreas.LeagueChances`); the row struct offset of column
`c` is `4c + 4`: index 0 `+0x24` with a second chance at `+0x28`, index 2 `+0x40`, index 9 `+0x64`
(column 24, 4 or 6 percent on maps), index 0xb `+0x68` (column 25, 0 on maps).

`0x141e30bd0` rolls one: the chance test is the callback `0x142011a10`: a chance below 1 fails and
one of 100 or more succeeds, both without a draw; only 1..99 draw `below(100) < chance` (for a
chance above 100 the remainder is tested the same way, so a multiple of 100 draws nothing); then,
while the second chance is set, it rolls that and keeps going on a hit (up to the mechanic's
maximum, `+0x8a` of the mechanics row). Stat conditions of `0x141e30a30` / `0x141e301c0` are skipped
(no area stats; the client's stats `0x562f`, `0x24c4`, `0x2436` also skip the rolls, not ported). **`EndgameMaps`** (`0x140b29e50`, keyed by `WorldArea`): when the area is found and its last bool (column 28, row `+0xf0`) is set, there are no rolls at all (JadeCitadel, CopperCitadel, the Expedition logbooks, unique maps). The client skips the rolls (`bVar18`) for towns (`+0x14` `IsTown`), hideouts
(`+0x12a` `IsHideout`), area kinds (`+0x1b4`) 0xf, 0x13, 0x20, 0x21, 0x23, 0x27, row flag `+0x14`,
areas with the tag hash `0x939d55cf` in `Tags` (`+0x133`, not ported) or a special stat; the port
rolls only for `IsMapArea` areas (acts show no such draws).

With success the client adds encounter requests (`BrequelExpandingEncounter`, `StoneCircle`,
`IncursionEncounter` via `0x141ffd930`); a count above 1 only for a chance above 100 (`+0x18c`
counts the rest, not ported). Draw sites: `0x141fb0c3c` (overlay candidate count), `0x141fb0dbc` (phase 1 candidates), `0x141f9e882` (fill group weight), `0x141fe84c5` (outer fill placements, no draws), `0x1420b73e2` (special room pick). Switches: `POE_OLD_ROLL`, `POE_ROLL_MAPS_ONLY`, `POE_NO_INCURSION`.
- **Stone circle** (mechanic 9): adds the `ExtraTerrainFeatures` row `StoneCircle` (room
  `Metadata/Terrain/Gallows/Leagues/StoneCircle/Tiles/StoneCircle_01.arm`, tiles
  `StoneCircle_01..03.tdt`, orientation list `[8]` = any). `league::Rolled` keeps the counts;
  `league::extra_rooms` turns a stone circle into the room and its tiles.
  - `.tgr` placement is `0x1420ccb00` (called by the driver `0x1420cdc60` right after the lattice
    passes, before `0x1420cd380` (shrines) and the overlays; its trace line is the `lattice bdae0`
    view followed by its draws): `0x1420cc8b0` lists the cells that are empty and walkable (corner
    ground missing, or a ground with `.gt` flags 4 and 8; corner without flag 8), row by row,
    discards a `below(n)` and shuffles the list with the forward Fisher-Yates (`uniform(n - i)`,
    swap `i` and `i + k`; the last draw is `uniform(1)`). `0x1420cce40` draws the room's orientation
    once with `below(8)` (feature orientation list holding 8; one `below(8)` per room, not per
    cell), then walks the shuffled list: the first cell where the rotated rectangle lies inside the
    map on free cells (`0x141d1a430`) takes it. The corners under the rectangle whose ground is
    missing or has `.gt` flag 8 take the cell's ground (`0x141d0f0e0` tests the flag on both
    grounds, `0x141d1ace0` sets it), the room is placed with the cell corner's height (`0x141f9b060`;
    the pre-unique pass passes `0xb`, this one `10` and a feature record from `0x141f99420`, which
    only records the rectangle for spawns, with `0x141d191e0` marking the cells), and the budget
    `+0x144` drops by one. The room's slot is a 3x3 key without edges, so the tile comes from the
    feature "StoneCircle" tiles added to the master's tile set (`0x141d165e0` → `0x141d16660`, weight
    1, all orientations: 24 entries, `below(24)` picks tile and orientation at once: entry `tile * 8
    + orientation`). Code: `fill::place_league_rooms`, `TileSet::add`, `Master::add_extra_tile`,
    `Files::league_rooms` (filled by `generate_probed_files`).
  - **The feature list is shared by all graphs of a job**: `0x141f9a300` (called per graph from
    `0x141ffeda0` / `0x142001400`, share = master `+0x152` read by `0x14200bc50`; no master sets it,
    so the budget is the whole remaining list) hands each graph what is left; a placed or queued
    feature leaves the list (`0x141f99ac0`). `Files::take_league` (called by `place_league_rooms`,
    `place_league_rooms_dgr` and `extra_features` for each served request). The league tiles are
    added to a graph's master from the list as it stands before the layout (`area.rs`, `league` is
    read before `dungeon::layout`).
  - **League rooms are overlay feature rooms**: rooms the league pass places before the overlays
    (`0x1420ccb00`; on `.dgr` also the league rooms `0x1420a9640` and the pre-unique room
    `0x1420ab170`) join the generator's room list the overlays read: the whole rectangle gets
    occupancy bit 8, the inner one, shrunk by the room's own overlap (`.arm` dimensions `uint1`), bit
    4. Switch `POE_NO_LEAGUE_RECTS=1`.
  - `.dgr` placement: [dungeon.md](dungeon.md).
- **Incursion request** (the Act 4 interlude areas P3_*, chance 100: no draw, one
  `IncursionEncounter` request), served by `0x1420b9d10` with the room set's `ridge_mission_*`
  rooms like the stone circle; the request's tile is the area's `Incursion2EncounterTilePerArea`
  path (`0x141ffddc0`), else `SpecialTiles` row 3 (`DefaultIncursion`, `WaygateDeviceBase.tdt`,
  `0x14163c730`), added to the tile set (a `.tst` would add a tile set). In P3_2 the container graph
  tries the request first (two `below(7)` with shuffles, nothing fits), then the subgraph serves it.

## Graph layout (Riverbank, `G1_1`)

Per region, `0x142001400` loads the graph, rolls edge existence (`0x141ff8120` → `0x141ffd2a0`: per
edge with exist % ≠ 0, `below(100) < exist` keeps it; exist 0 removes it without a draw), then
`0x1420cdc60` lays the graph out. Seed 1000 → topology 2 of 5 (`intro_3.tgr`, 66×72 tiles; the map
is 69×78 with `OuterBufferSize 3 3 3 0`).

`.tgr` v25 fields (parser `0x142ab6f90` / `0x142ab7930`, caller `0x142939df0`):
- node: x, y, edge count + indices, room type, orientation, descriptions, exist %, height,
  priority, deletion behaviour, lock-orientation flag (node value 4), random offset (4 ints), then x
  and y constraint flags (node values 9 and 10; read by the caller; constrained axes are not
  jittered).
- edge: from, to, internal points, exist %, chirality, priority, edge type, min/max width.

Region orientation (`region.rs`): the axis constraint flags swap for odd orientations; a node with
the lock-orientation flag keeps its orientation (the region's turn does not compose with it).

**Node jitter** (`0x141f02980` builds, `0x141f01e10` applies; `voronoi.rs`, `layout.rs`):
1. Sites = node positions, then every edge's internal points (grid cells, 23 per tile).
2. Voronoi diagram (`0x141f05640`/`0x141f065d0`): Fortune's sweepline in the
   `VoronoiDiagramGenerator` layout, all-integer (edges unnormalised `b = dx`, `a = -dy`, `c =
   (dx²+dy²)/2 + x·dx + y·dy`; circle events at `y + isqrt(d²)` with `0x141979320`; the hash tables
   degenerate, so the beach line is walked from an end and the event queue is one sorted list). Box
   `(0, 0, w·23, h·23)`. `clip_line` (`0x141f06140`) pushes each edge to the front of a list with
   its two site numbers; vertices joined to 1 or 3 edges form the vertex list.
3. Cell graph: a node per distinct vertex; per diagram edge (list order) the **nearest** nodes to
   its ends (`0x141f13af0`: clipped ends are recomputed from the line and can be a cell off),
   skipped when equal or already joined; both sites' cells get the edge. Then the four corners `(0,0)
   (0,h-1) (w-1,0) (w-1,h-1)`, and the border: nodes with ≤ 2 edges on each side, sorted along it,
   chained (`0x141f02070`); each chain edge goes to one cell, chosen among the sites of the chain
   node by an orientation test against the node's first edge (the first chain edge tests from the
   neighbour, the rest from the node, so the signs differ).
4. Per node (then per internal point): triangles (node, cell edge) with weight |cross|/2
   (`0x141f015f0`; a node in a border tile whose cell has an edge on that border takes that edge
   alone, weight 1), `below(total)`, then `a, b = below(128)` (folded when `a+b > 128`), offset
   `((Q-N)·b + (P-N)·a) / 160`.

### Room placement

(`rooms.rs`; trace kinds `node_candidates`, `node_key`, `node_place` from DLL hooks on `0x1420d66f0`
and `0x1420d77c0`). Room nodes are placed in node order, all before any room pass (the passes then
run in the same order):
1. Node key (`0x1420e1e40`): each graph edge (except `.et` types named `Wildcard…`, flag 0x80) goes
   to the side it leaves by, towards its nearest internal point or the other node (`0x1420e0240`:
   `|dx| > |dy|` → right (1) / left (3), else down (2) / up (0)); a side with several edges gives
   one up to a neighbouring side, cheapest angle first (`0x1420e05d0`, angle table `0x142f237a0`,
   side vectors `0x142f1f7d0`). The key is the `.et` per side. For a junction edge the side is
   taken towards the first internal point or, without one, the other end, which for a room edge is
   the exit position, not the room node (`PlacedGraph.ends`): `0x1420d8990` cuts the rooms' edges at
   their exits before `0x1420da220` explodes junctions.
2. Room table: per `.rs` room (its `.arm` tag is the room type) and allowed orientation, the turned
   root-slot key. When no entry of the node's type has the key's edges, `0x1420d41e0` moves an edge
   to a free side (two edges: the first to the following/preceding free side; three: the one after
   the free side back into it, else the one before it forward).
3. Candidates (`0x1420d66f0`): fixed-orientation node → every matching entry, in the node's
   orientation (a room symmetric under a flip appears twice); `(any)`/`(best)` → each matching entry
   in its own orientation if `0x1420c77d0` agrees: per edge, its direction (from/to xor chirality)
   picks the two corners at its end, whose ground types must equal the `.et`'s left/right ground
   (`None`/flag 8 = wildcard) and whose heights its height change; first with the climb check, then
   without. Only `(any)` nodes (orientation byte 8, tested in `0x1420d77c0`) take the quarter turn
   (`0x1420d8d90`); `(best)` (9) and fixed orientations run the side check `0x1420c7b90` instead.
   The client's quarter-turn bottom border test is `h + x == map width` (a typo for `y == map
   height`; not copied). Room-less nodes in the tile list also try rooms of the empty type first
   (`G2_1` topology 4: `stromacliff_join*.arm` for a node whose edges are
   `desert_dune_stromatolite.et` and `desert_dune.et`), before the tile branch. When no room of the
   node's type fits, `0x1420d66f0` falls back to tile-set tiles whose feature is the room type (e.g.
   `endcap` → `Mudburrow/Trail_End_01_02.tdt`); the adjustment check `0x1420d4560` accepts a key
   when tiles of that feature or rooms of that type have it, and the filter lambdas keep only tiles
   of that feature.
4. `below(total weight)`; position = node tile − half the size, snapped to the node's alignment
   (`align<N>` description, else the largest edge size; `0x141ff5bb0` rounds up when the remainder
   is above half), clamped to the map; must fit, else all entries of that room and orientation are
   dropped and another is drawn. Then `0x1420d4a00` keeps it a margin (largest edge size, twice for
   virtual edges) from the map border on each side with an edge.
5. `.et`: name, left/right ground (`wildcard`), numbers `height_change size flag`, then `virtual`
   (two split edges, chiralities, default min/max width) or `random_wiggle`, `can_end`,
   `force_height_zero`. `.gt` flags: the five bools of line 2 (default 1 1 1 1 0), bit 7 for
   Abyss/Water/Pool/Void names. Grounds named only by a room (`arenamud.gt`) have their real flags
   in the lattice passes (`TileMap::use_room_grounds`); the default 0x0f would let the border flood
   run through them.
6. Before placement every room node is "exploded" (`0x1420da220`): each edge gets an internal point
   23 cells from the node towards its side (points within 23 cells removed first, `0x1420d5ba0`);
   this matters for routing, not for the draws so far.
7. **Room settle** (`0x1420d8280`, start of `0x1420d8990`; `rooms::settle`; node tiles use it too,
   `node_tiles::place`). Before a room (or node tile) is placed its margin rectangle is tested: left
   and top margin `align` where those sides have an edge, right and bottom margin the edge's `.et`
   size; the cells must be free (`0x141d1a430`), no side with a non-wildcard edge may touch the map
   border, and the four corner grounds must agree with the lattice's where it is set (equal, or both
   none/`.gt` flag 8, `0x141d1a6a0`/`0x141d0f0e0`/`0x141facc30`). When any test fails the room moves in a square
   spiral of `align`-sized steps (step counts 1,1,2,2,..9, directions through the 9x9 orientation
   table `0x141f9abd0`, vectors `0x142f1f7d0`), first with the margin rectangle, then with the room
   alone; no place throws "Overlapping node tiles".

### Repulsion, exits and routing

(`rooms.rs` `repel`, `routing.rs`; DLL trace kinds `route_edge` and, with `POE_HOOK_ROUTE_GRIDS=1`,
`route_grid` per edge):
1. Placement stage order (`0x1420d9a60`): place room nodes → `0x1420dae80` → tilise each room
   (`0x1420d8990`: room pass, then exits).
2. `0x1420dae80` (no RNG; apply `0x1420db940`): every placed room gives a rectangle (room cells grown on each side with
   an edge by its size, twice for virtual edges, `0x1420da490`); every graph node and then every
   edge internal point gets the sum of the rectangles' pushes (`0x1420da7c0`: inside → out along
   node→point; within 138 cells of a side or corner → a linear fall-off), a room's own node instead
   gets minus the pushes of the four map-border midpoints; pushes apply after all are computed
   (constrained node axes stay), clamped to the map; then each room is centred on its node again
   (snap, fit, border margin with the alignment).
3. Exits (`0x1420d4770`, `0x1420d4b70`, `0x141f00a60`): edge internal points inside the room are
   dropped; each room edge then ends at the room's exit on its side (exit `e`: tile `e / 3`, cell
   `[3, 11, 19][e % 3]` (`0x142f21038`), sides 2/3 counted backwards; virtual edges at the midpoint
   of the virtual exit and the exit) with the side's direction as end offset.
4. Router (`0x1420dcc50`): `below(1024)` per tile (row-major), +1024 on the border, placed tiles
   occupied; every edge reserves its straight legs (`0x1420dd3b0`, Bresenham `0x1420dbde0`: the
   line's tiles +1 use, tiles across within the margin (size + 2, or max width / 23 + 3 for virtual
   edges) + `(m−k+1)·200000/m/100`); edges routed in graph order (`0x1420dc480`): per leg its
   reservation is lifted, a search runs from the leg's end to its start (`0x1420dc130`: neighbours
   left/up/right/down; open set ordered by (g+h, tile index); h = Manhattan × 100; **g = the
   neighbour's own g + 100 + its cost**, i.e. not accumulated: a client quirk that makes it a
   best-first search; tiles in use or occupied are closed except the goal), the path is reserved and
   every 6th tile adds an internal point at `(tile·23 + below(23), tile·23 + below(23))`. Edges
   whose search fails keep their reservation and are tried again after the others; a round that
   routes none throws "Could not permute edges".
5. Junction explode (`0x1420da220`, before routing) applies to junctions (three or more edges, none
   virtual) and virtual nodes that no tile fits at the room stage (`0x1420d9a60` places those that
   fit). Their edges first drop points within **twice** the step (`0x1420d5ba0` radius `2 · s`,
   `lea r8d, [rsi + rsi]`; `node_tiles::explode`, `POE_EXPLODE_R1=1` restores the old radius), then
   each edge gets a point 23 cells out of the node on its side (`0x1420e0240`, clamped to the map),
   at the start of `from` edges and at the end of the others.
6. `.et` fourth number (+0x4d, e.g. `woods.et` `0 3 0 1`): the edge's tiles take their exits from
   the coordinate hash `0x1421a69b0` instead of the path curve (`0x1420c64b0` is not called for
   them).

### Edge smoothing

(`smoothing.rs`; DLL trace kinds `arc_start`, `arc_end`, `round`, `graph_after_smooth1`;
`cargo run -p poe-world --example smooth_check -- <trace>` replays the logged arc steps). After
routing, `0x1420cc670(layout, 1)` (no RNG):
1. Room nodes were split per exit by `0x141f00a60` (the node takes its first edge's exit, every
   other edge gets a new node at its exit, appended in tilise order), so the graph numbering is
   original nodes then exit nodes.
2. Arcs: virtual edges with a start (end) offset get points on a circle tangent to the offset
   direction (`0x1420e0b90` / `0x1420e1490`: centre on the node's perpendicular, radius from the
   chord, 45° steps, polar `0x1421d5000` on the 256-entry sine table `0x142f239a0` with swapped
   interpolation weights and ±127 clamping, so the arc radius is half the computed one); end arcs
   are appended last-first; repeated up to 5 times while anything changes.
3. Corner rounding (`0x1420c2bf0` up to 5 times; per edge `0x1420c1f80`): degree-1 nodes' edges
   first, then every slot of nodes with ≥ 2 edges; walking an edge (and on through degree-2 nodes),
   each corner B between A and C with a sharp enough angle is replaced by the tangent points of a
   circle of radius `max width + 10` (one or both, the second inserted with `0x1420ddd40`), or
   removed / collapsed to the midpoint (`0x1420c1cf0`) when the tangents would overrun.

### Virtual edges and the last graph passes

(`split.rs`; DLL dumps `graph_after_split`, `graph_before_tiles`):
1. Room exits of virtual edges get a pair of virtual end points (virtual exit, exit), ordered by
   `0x1420d5880` (side of the edge they fall on) and `0x1420d4b70` (side of the exit direction).
2. `0x1420cb420`: edges with virtual end points first (from the end that has them), then the rest;
   each chain of virtual edges through degree-2 nodes is split (`0x1420ca510`): the edge is cloned,
   one copy takes split type 0 and the other split type 1 with chirality flags (`0x1420ca0e0`), the
   node moves to the first virtual point and a new node at the second takes the clone; at a junction
   a width `below((max₁+max₂−min₁−min₂)/2 + 1)` and a miter (`0x1420c8c50`) give the points, and
   `0x1420c9070` re-attaches whichever edge does not cross; every internal point gets
   `below(max−min+1)+min` and the two banks are placed by the miter (`0x1420c9a40`); at the chain's
   far end the far node takes the second virtual point and a new node the first.
3. **Off-map ends** (`0x1420c9360`, run for both ends of every virtual edge by the first lambda of
   `0x1420cb420`, `0x1420e9260`; `split.rs::off_map_end`): a dead end (one edge) on the map border
   without virtual end points gets them on the border, a random half width `below(max-min+1)+min`
   either side of the node (corners use both borders with a 2-tile correction). The two banks then
   run off the map instead of meeting in a node that no tile fits.
4. Then: rounding again, nodes sorted by priority (stable, `0x141f13240`), dead ends near the map
   border pushed one cell off the map with an inward offset (`0x1420d9e00`; also dead ends made by
   the virtual-junction split, `area.rs` `junction_made`; `MapCrimsonShores`), node slots compacted
   (`0x1420cc610`), rounding again, and every edge gets a point one step out of each end node along
   its offset (`0x1420c5680`).

Node flags (`+0x88` "fixed", `+0x89` "virtual end"): fixed = room nodes and their exit nodes, plus
dead ends pushed off the map; virtual end = next to a virtual edge in the topology graph
(`0x1420d6420`, `.et` flag 4). The virtual split copies both flags to each new node, and at a
chain's far end sets virtual end on both far nodes unless the far node lies on the map border (the
clone's far node also copies fixed).

**Two virtual edges side by side at a tile-less virtual node** (`0x1420d5510`, from `0x1420d5cf0`):
one width `below(max-min+1)+min` from the first edge's range, the corner of the two offset lines
(candidate chosen by the side tests against the midpoint and the third edge) goes to both edges as
one virtual end point (`node_tiles::virtual_corner`).

**Virtual junctions without tiles** (`0x1420d5cf0`): point drops, pair loop with `0x1420d5440`,
ordering `0x1420d5880`, node split `0x1420d4f00`, and logical links. The split updates the links
(`0x1420c9f60`). `0x1420cc010` resolves them: pairs at identical positions, else `0x1420cb9c0` with
segment distance `0x1421a6260`. Link nodes of degree >2 join the tile list. Nodes made by the split
are **not** in the tile list (it was built from the original nodes at the start of the tile stage),
and that mark survives `resolve_links`, which erases emptied nodes and shifts later indices (keep
the marks by current index).

**Loop chains** (`0x1420c4f50`): a chain that ends where it started is split at point `n/2` into two
halves that share the middle point (the second takes the first edge's far node's other edge), both
are fitted as loops, the second half's tiles minus its first and last are appended to the first, a
closing duplicate is dropped and the tiles are made at once (`0x1420c6f50`, crossings from
`0x1420c6100`: ten control points round the loop, one crossing per tile). The client reads crossing
`i + 1` for the last tile's far side, one past the vector; the port uses (0, 0) there.

### Node tiles

(`node_tiles.rs`, `0x1420d9e00`): at the start of the tile stage `0x1420d6420` sorts the room-less
nodes into lists (`+0x00` virtual, `+0x18` tile, `+0x30` typed, `+0x48` no-edge nodes with points).
The tile list takes dead ends (a virtual one only at the border), nodes with three or more edges,
and nodes whose two edges have different `.et` types; two edges of one type pass through. Nodes
touching a virtual edge that are not dead ends go to the virtual list, and are placed at the room
stage (`0x1420d9a60`, second loop) by `0x1420d77c0` like rooms (rooms of the empty type, else tiles;
`place_node_opt`); the ones nothing fits are exploded later. `0x1420d9e00` walks the tile list. A
dead end near the border (`0x1420d65e0`) is pushed off the map; any other node is tilised like a
room node (`0x1420d77c0`):
1. Key and sides from the node's edges (`0x1420e1e40`, same as rooms).
2. Candidates: the tile-set branch of `0x1420d66f0`. The sizes in which feature-less tiles have the
   key's edges are listed sorted (`0x141d162b0`, map +0x68). For each size, every tile entry of any
   feature with those edges and that size is taken (`0x141d17380`, map +0x20, tst order then
   orientation 0..7), using the swapped size when there is none. The list is then filtered by the
   node's orientation, or for `(any)` by `0x1420c77d0` (climb check first, then without).
3. `below(total weight)`. Position, alignment and fit work as for rooms; the map cells must be free
   (`0x141d1a430`). On failure the first entry with that tile and orientation is dropped. Then
   `0x1420d4a00`. For `(any)`, `0x1420d8d90` turns the tile a quarter either way (orientation table
   `0x141d0dab0`, key turned by `0x141d155f0`) when the summed edge-to-side angle (`0x1420c7e40`,
   degrees) drops; the turned key, including its size, is what later steps use (the recentring in
   `0x1420dae80`). A turn is not allowed if it would put an edge against the border the tile
   touches.
4. `0x1420dae80` with the room flag clear: the tiles' rectangles push every node except those with
   exactly one edge (a tile's own node is not pushed by its own rectangle) and every internal point.
   Each tile is then centred on its node again where the cells are free, and `0x1420d4a00` runs with
   its alignment.
5. `0x1420d8990`: snapped, placed into the map, and the node's edges are cut at the tile and ended
   at its exits (`0x1420d4770`, `0x1420d4b70`). The first edge keeps the node; each other edge gets
   a new fixed node (`0x141f00a60`).

Riverbank seed 1001 needs this for one node: the narrow river changes from `S` to `M`, so the node
takes `NarrowRiver_Mud/StMS_01.tdt` (3×3, o5). Tile-list nodes also adjust a key no tile has
(`rooms::adjust_sides` on an `EdgeView`); a node with edges needing a middle `.et` type that no tile
and no empty-type room has both of fails (`MapSinterRift` node 37, `Design` node 6).

Tile-set index keys (`0x141d164b0`) drop grounds whose `.gt` has flag 0x10 (the fifth bool, e.g.
`wideriver_trim.gt`). `TileDef::key` holds that key. Overlays: [shared-passes.md](shared-passes.md#overlays-toy).

### Edge tiles

(`edge_tiles.rs`, `0x1420c5970`):
1. Occupancy grid (`0x141f03960`, 0x20-byte cells: cost, parent, f, g, h, closed, occupied,
   open-set link): cells under room tiles are occupied. Per edge (`0x1420c5680`): +80 cost on every
   tile its line crosses (`0x141f04d10`, tiles rounded down to the `.et` size); an edge with a fixed
   from node goes to list A (from that end) and its fixed end tiles are taken (`0x141f04a00`);
   otherwise a fixed to node puts it in A from the other end; otherwise list B (from the from end if
   it is a dead end).
2. `below(|A|)` (discarded), A shuffled (`uniform(n−k)` per slot), stably sorted by priority then
   split edges first. A then B: each chain (`0x1420c4f50`, walking through degree-2 nodes,
   `0x1420d3980`) is skipped if it stays within the end tiles of two touching rooms (`0x1420c31d0`);
   free dead ends inside the map repeat their position as a point (`0x1420c33d0`); the path builder
   (`0x1420c3530`) keeps one point per tile and cuts loops.
3. Fit (`0x1420c4270`): from the start node's tile, searches (`0x141f03ee0`) from each path point
   back to the previous one: seeds are all later points (cost `avg×100 + points left`, the first 0,
   estimate `isqrt(d²)×100`), steps cost `(avg + jitter + size)×100` with an estimate of plain
   `isqrt(d²)` and `jitter = ((x+1)·r₁ + (y+1)·r₂) mod 707 / 101`, where `r = v² + (v+1)²`, `v =
   below(16384) + 20000` (two per search). The open set is ordered by (f, cell). Found tiles are
   taken (+80); edges of the path get −60 first (`0x141f04e50`) and each passed segment −20
   (`0x141f05260`); failures backtrack (at most 10 steps). Paths that fit cost +80 on their inner
   tiles; those that do not are retried after the others.
4. Tiles (`0x1420c6f50`), per inner path tile: the sides of the previous and next tile
   (`0x1420c68f0`, room tiles count with their size) get the edge's `.et` and an exit position: the
   middle (`3·size/2`) for `.et` flag 8 (third number); next to a room tile, the room exit seen from
   this side (`0x141fad130`, falling back to the virtual exit); otherwise which third of the side the
   smoothed path crosses (`0x1420c6bc0`, threshold `23·size/6`), where the crossing is a degree-9 de
   Casteljau midpoint over the tile centres padded with four copies of each end (`0x1420c64b0`,
   f32). Grounds (`0x1420c6d90`/`0x1420c6c80`): left/right ground on the two corners of each side,
   swapped by the edge's chirality (`+0x41`) against the path direction; a turn's outer corner copies
   its neighbour. Lookup with no feature, `below(total weight)`.

`.et` data: `+0x48` flags (4 virtual, 8 third number, 0x80 wildcard name), `+0x4b` size, `+0x4c`
first number (the right ground's corner height in tile keys), `+0x4d` hashed crossings
(`0x1421a69b0`; 0 for every Riverbank type). The DLL traces tile keys (`tile_key`, with caller) and
dumps these bytes with each graph edge.

## Heights and the outer fill

- **Height passes.** The `lattice` trace snapshots are taken at function entry (`borders` = before
  `0x1420c84f0`, `flood` = before `0x1420cfa80`, `heights` = before `0x1420c8840`). Port:
  `lattice::height_pass` after the border floods, `lattice::refix_fills` after the overlays' second
  phase, world units in `area.rs` (switches `POE_NO_HEIGHT_PASS`, `POE_NO_EDGE_FALLBACK`,
  `POE_NO_REFIX`, `POE_NO_TGR_STOREY`, `POE_TGR_NO_REPAIR`).
  - `0x1420cfa80`: (1) row by row, every tile origin not yet reached starts the fix-up flood
    `0x1420cf710` (a queue of tile origins). Per tile, `0x1420cecc0` collects the heights its reached
    corners imply (`0x1420cf5c0`: corner height minus the tile's own point height, `0x141d150c0`),
    only at corners whose tile ground is missing or takes heights (`.gt` flag 1); an empty cell takes
    the reached corner heights of its four corners (`0x1420cf420`). None: the real edges (`.et`
    `+0x48` bit 7 clear) give the reached neighbour cell at the edge's exit (`exits / 3` along the
    side): its height minus the tile's point height plus the neighbour's at the shared corner. Still
    none: the four outer corners, any ground. Several: the lowest (`0x142ba1290` is a min-element).
    `0x1420ceae0` sets the tile (cells and corners, `0x141d17f40`), marks its corners and cells
    reached and sets the map's raised flag for a non-zero height; `0x1420d2b60` queues the
    neighbours across corner pairs that take heights (left, right, below, above; an empty cell
    queues all four) and across real edges. (2) With the raised flag (view `+0x20`): the lowest tile
    height is subtracted from every corner (all get flag 2) and every tile. (3) `0x1420cfdb0`: an
    unreached corner with exactly one reached neighbour corner takes its height, until nothing
    changes. (4) `0x1420cff20` (room heights) is not ported.
  - `0x1420d09f0` (after the fill and the overlays): plain tiles (`0x1420d0670`: not inheriting,
    edges empty or wildcards, one ground on the four key corners, `.gt` flag 0x10 grounds counting as
    none) stay unreached, all others count as reached. `0x1420d0c30`, per cell row by row, for a
    plain tile on a ground without `.gt` flag 1: each neighbour left, right, above and below the cell
    that is not plain and whose facing key corner has the tile's ground at a position along the
    tile's side gives its height plus that key corner's height (`.tdt` corner bytes); one distinct
    value sets the tile. `0x1420d2350`, until nothing changes: an unreached plain tile whose reached
    neighbours of the same plain ground give one distinct height takes it.
  - Tile records keep heights in world units (`StoreyHeight` per storey; Design's is 43), for `.tgr`
    maps too, and the outer buffer of a raised `.tgr` map runs with the height repair like a
    dungeon's. P2_1's base height is 1 (every tile one storey, 16, above a zero base).
- **Outer fill levelling rounds** (`0x141fe47a0` loop with `0x141fe5970`, applied by `0x141d17f40`,
  which also rewrites the tile's lattice corner heights): the list holds the cells whose tile handle
  is the outer ground's first fill tile (`cell+8 == local_400`, from `0x141fa2460`), corner heights
  with the `-0x78` wrap, upper middle, apply only at offset (0,0), at most 15 rounds, stop after a
  round without a change above 1. The rounds run only when the generator byte `+8` (never written
  in the decompiles searched; the constructor zeroes it) is non-zero, the outer ground's `.gt` flag
  1 is clear and master `+0x161` (`OuterFillHeightOverride`, parser struct byte 0xd, value byte
  0x1b → `+0x153`) is clear. Ruled out: the lower middle (`min + (max-min)/2`) instead of the upper
  one breaks thousands of matches; excluding cells of tiles placed before the outer fill breaks
  matches too (they belong in the list); `StoreyHeight` is not the cause; treating
  `OverrideMonsterSpawns` like `OverrideSpawns` breaks other areas. `HideoutLimestone` and
  `HideoutClaimable` (rounds never called by the client; four 3x3 fill tiles at inner (2,20), (5,20),
  (8,20), (11,20) stay at height 0 and the lattice corner heights seen by the rounds are
  `{0, 1, 0, 0}`) are the case to watch when touching this.

## Post-unique tiles, overlay phase 2, fill details

- **Post-unique tiles** (`0x142000840` per region after the de-repetition, `0x1420010d0` chooses an
  orientation; `postunique.rs`): `.tst` entries whose `.tdt` feature is exactly `postunique` are not
  in the tile-set index (`0x141d16660` puts them on a separate list at tile-set `+0x80`, with their
  rotation mask). Per entry: every region cell that is the origin of a featureless tile with one
  corner whose lattice flag 8 is clear, and whose turned index key equals the entry's key in some
  allowed orientation, is a candidate with an orientation drawn by `below(n)` among the equal ones;
  (`below(2)` per candidate from `0x142001396`), then `below(count)` picks the cell and the entry replaces that tile (G1_5's
  `T2_WeaponDrop_01..10`). No candidate throws.
- **Overlay phase 2** (`0x141fb0b80` with `param_3` set, `overlay.rs`): before the overlay room is
  placed the tiles under it are recorded in a map keyed by `x * 0x10000 + y` (`0x141fb85e0`: sorted
  by x then y, a later insert overwrites) cell by cell over each tile's whole footprint, then
  removed; after the room (`0x141f9ce60`) every recorded cell in that order that is empty again is
  filled like the fill pass (`0x141f9e0d0`, ground of its corner, walkable when that ground is none
  or has `.gt` flag 4). A cell now holding `OverlayBlank` (`SpecialTiles` row 2, `0x141d15b90` /
  `0x14163c730`, `Metadata/Terrain/overlay_blank.tdt`) gets its old tile back when that was 1x1 with
  only wildcard edges (`0x141faca80`), otherwise the blank goes and the cell is filled; any other
  tile stays. The overlay context (`0x141faf260`) is built once, the two phases run `0x141fb0210`.
  Mission rooms (`special` true, `.arm` tag `mission`) count in the overlay occupancy (bits 4 and 8
  over the room rectangle; `area.rs`, `RoomRect::feature`); only other `special` rooms stay out.
  The client never calls the candidate fit (`0x141faffd0`) for positions overlapping `mission_02`.
  `POE_DBG_OVERLAY` prints FIT lines for comparison with the trace.
- **Master paths starting with `Metadata/` are absolute** (`HideoutLight`'s `master.tsi` names its
  files in full). A `.gft` section whose lines are all commented out (`DefaultHyenas`) is not a
  group: the ground fills from `default`. A master with `TileSet` and no `FillTiles` is valid
  (`G_login`).
- **Sealed tiles** (found, not ported): `0x141d11f50` sets tile data `+0x16f` bit 0 when one of the
  tile's objects (`.tmd`, last quoted string of a line) has a type with an `AreaTransition`
  component or an `InteractionAction` whose `action_name` is `waypoint` (`0x141e7fd50`); only 8
  `.tmd` files name such types, so it does not explain `MapSlash`/`MapSeepage`. Bit 1 is the
  `Spawner` one, ported.

- Ruled out for a raised base height (P2_1): master `+0x146` / `+0x144` and the two ring heights of `0x1420c8840`; the cause was the `.tgr` height passes `0x1420cfa80` / `0x1420d09f0`.

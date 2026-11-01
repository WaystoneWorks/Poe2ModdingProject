# Dungeon layouts (`.dgr`, 0.5.5e Hotfix 1)

Most act 1 areas (G1_3, G1_6, G1_7, G1_8, G1_9, G1_11, G1_12, G1_13–15) use `.dgr` topologies
instead of `.tgr`. The topology choice, the graph load and the node-existence rolls are shared with
`.tgr` ([shared-passes.md](shared-passes.md)); after them the client runs a separate dungeon layout.
Port: `modules/server/crates/poe-world/src/dungeon.rs` (layout) and `dungeon_tiles.rs` (tile pass).
Status: [../../status/terrain.md](../../status/terrain.md). Tools (`area_trace`, `area_vectors`,
`wiggle_check`, debug switches): [README.md](README.md#tools).

## Call chain

- `0x141ff0770` (`.dgr` subgraph driver, per subgraph index):
  - loads the graph (`0x141fa9710`), runs the pruning/existence passes (`0x141fea460`, `0x141fea5a0`,
    `0x141ff0560`, `0x141feaa10`, `0x141fe8ef0`), `0x141fffa80`;
  - region size: graph width × (master +0x149 − master +0x14b) + master +0x14b, same for height.
    Master +0x149 is `RoomUnitSize` (G1_3: 9), +0x14b the shared border, the `.tsi` key
    `RoomOverlap` (default 1; G1_3 has no such key, G1_6/7/8/9, `G1_13_1` and `G3_5` say 1, G1_12
    (unit 29) and `G2_1` (unit 3) say 0). G1_3 (5×6 units): 41×49 tiles, 51×59 with
    `OuterBufferSize 5`. The master parser is `0x142928820`: it compares the key text, parses the
    number into a parse struct (`RoomUnitSize` → byte +0x1c, `RoomOverlap` → byte +0x1e, from the
    `.tsi` key's own value, not from a room's `.arm`) whose constructor `0x14292e3d0` sets the
    defaults (the dword at +0x1c is 0x10000: unit 0, overlap 1); `0x141f94350` copies the parse
    struct into the master (+0x149 / +0x14b). The port reads the key in `area.rs` and passes it to
    `dungeon::layout` (G1_12: map 174×87);
  - builds the dungeon context (`0x1420ad320`) and the **dungeon grid** (0x70 bytes): +0x20
    generator, +0x28/+0x2c width/height in units, +0x30 room unit size, +0x34 border, +0x38 failed
    flag, +0x40 `u32` state per unit cell, +0x58 placed rooms (0x60 bytes each);
  - `0x1420ac560` lays the dungeon out; then per placed room `0x141ff1450`; then the tile pass
    `0x142099e00` + `0x14209c640` (tile placements at `0x142098f4c` and `0x14209fb27`); then
    `0x1420004c0`. Errors: "Dungeon generation failed: …", "Subgraph … extends outside the
    TileMap!".
- `0x1420ac560` (layout):
  1. a per-node lambda (`0x1434eb830`), stable sort `0x141fa8bb0`, `0x1420ad5a0` (calls `0x141fa8890`
     per entry; with master +0x248 set, marks the grid's border cells state 1);
  2. `0x1420aa680`: room placement (below);
  3. `0x1420a99e0`;
  4. when any edge has content: `0x1420a5fd0` (`below(128)` at `0x1420a610a`), `0x141fa8ce0`,
     `0x1420a2df0` (corridor routing, lambda `0x143505a88`), `0x1420a5260`, `0x1420a9b60`,
     `0x1420aa090`;
  5. `0x1420a9710`, `0x1420b1b70`; with master +0x1f8 (extra rooms): `0x1420aa890`, per
     `m_ExtraRooms` entry `0x1420aace0`, then `0x1420aae70`, `0x1420ac0e0`.
- `0x1420aa680`: splits the graph nodes into two lists (lambda `0x143505bb0`), sorts both
  (`0x1420d0f80`) and places each node with `0x1420af950`, first list first. Nodes are placed typed
  first, then typeless, each list stable-sorted by priority (descending).
- `0x1420af950` (place one node; skipped when node +0x88 is set):
  - node +0x58..+0x78: one edge per side; node +0x4c/+0x50 the position, scaled to the grid (`pos ×
    grid size / graph size`);
  - tagged `template`: `0x1420b0660`;
  - no room type (+0x30): `0x1420aff50`;
  - with a room type: the room pick `0x1420ae8d0`, the edge pick `0x142096870`, then `0x1420a7550`
    (stamps the room into the grid).
- `0x1420ae8d0` (room pick): candidates for the type and orientation (`0x1420ad830`, else
  `0x141f8b8c0`), filtered by `0x1420d1290`, then `below(total)` (`0x1420aed49`), placed with
  `0x1420af140`; when `0x1420b16d0` asks, a second `below(total)` re-pick.
- `0x142096870` (edge pick): the node's side edges weighted by edge +0x54 (`below(sum)`,
  `0x142096993`; two weight-100 edges give `below(200)`); returns the edge's +0x70 resource.

## File fields (`0x14292eb20`)

- Header after the three ground lines: `Default%:` branching, extra door, fuzzy %; version > 22: a bool
  `open_extra_doors_into_impenetrable_rooms`. The number of fields an edge record reads depends on
  the `.dgr` file version.
- Node: the `.tgr` fields (`0x142aa4d10`: x, y, edge indices, type, orientation, descriptions, exist
  %, height, priority, deletion behaviour, lock orientation, random offset ×4), then void (`N`/`Y`;
  the token in `.dgr` is `V` for nodes and edges) and branching (0/1). The builder `0x1420963a0`
  keeps type at node +0x20, orientation +0x40, priority +0x42 (sort key), exist % +0x44, height
  +0x48, void +0x88, branching +0x89.
- Edge: the `.tgr` fields (`0x142aa56b0`: from, to, points, exist %, chirality, priority, type),
  then branching chance2, chance1, depth limit, branching type, extra door %, extra door type
  (default `Metadata/Terrain/Dungeon/rooms.et`), fuzzy %, impenetrability, impenetrable value
  (`P`/…), void, accessibility. The builder `0x142096450` stores: +0x30 exist %, +0x38 type, +0x40
  priority, +0x41 chirality, +0x48 chance1, +0x4c chance2, +0x50 depth limit, +0x54 extra door %,
  +0x58 fuzzy %, +0x5c impenetrability, +0x60 impenetrable, +0x61 void, +0x62 accessible, +0x68
  branching type, +0x70 extra door type.
- Node side slots (+0x58..+0x78): `0x141d1c700` gives each edge, in file order, the first free slot
  of both its nodes, so a node's slots are its edges in ascending edge index (`.dgr` only; sorting
  `.tgr` node edges too breaks outdoor areas). `0x141fec340` (merge of the two edges of a removed
  node) takes the first two non-empty slots: the first edge object stays (its weight, `+0x54`, stays)
  and gets the second's far node. After a prune, an edge the merge moved sits in its new node's first
  free slot, which can come after higher edge indices: `dungeon::layout` reads `nodes[n].edges` (the
  slots the prune keeps) and appends any other touching edge by index (`POE_SLOTS_BY_INDEX=1`
  restores index order). The typeless room size pick (`0x1420aff50` → `0x1420afbc0`) takes the edge
  type of the first slot that differs from the default type, else the default's list.
- `.et` numbers: height change, size, centred, random wiggle, `can_end` (fifth), force height zero.
- Ground flag bits (`0x142918bb0`): `+0x24` bit 0..4 the five bools, 0x20 `HideRoof`, 0x40
  `HasWater`, 0x80 name contains Abyss/Water/Pool/Void; `+0x25` bit 0 the name `SynthesisBackground`.
  The graph's three grounds need their `.gt` flags loaded before the tile pass (`area.rs`): a ground
  that reaches the lattice through the settle (`CarverUpperGround.gt` of G3_7: `1 1 1 1 1` = 0x1f)
  otherwise falls back to 0x0f and the fill (`0x141f8fab0`, flag 0x10 = no ground) picks another
  group. Master keys: `ForceOuterGT`, `DoNotFillOutside`, `OverrideSpawns`, `DefaultKillZone`,
  `OuterFillHeightOverride`, `DungeonFillRoomHeightOverride`, `DoorEdgeType`, `FileGroups`,
  `StoreyHeight` (below).

## Rooms (`RoomSet`, `0x141f9abb0` / `0x141f99ca0` / `0x141f98d30`)

- The room type is the `.arm` tag (the quoted string after the sizes; `specialchance N` /
  `special…` prefixes mark special rooms). Shrine, mission, preunique and injector types go to
  separate lists. A room listed twice in a row in the `.rs` merges into one matcher entry with the
  first line's weight.
- `.arm` exit data (`0x142931f30`): 2×(units X + units Y) entries around the room, each a door type
  (string index, 0 = none), a height, (v>29) a height override flag, and for chiral door types a
  chirality and (v>29) its override. Order: top left→right, right top→bottom, bottom right→left,
  left bottom→top (`0x1420af400`).
- Per type, every orientation the `.rs` entry allows becomes a candidate (0x60 bytes: room,
  orientation, units W×H turned, exits turned, `.rs` weight). Turning (`0x141f96670`, `0x141d01150`):
  index i → (i' + A[o]·h + B[o]·w) mod 2(w+h), with i' = 2(w+h)−1−i for mirrored orientations
  (4..7), A = [0,1,1,2,0,1,1,2], B = [0,0,1,1,1,1,2,2]; mirroring flips chirality on chiral door
  types.
- `GetPossibleRooms(type, exits, n)` (`0x141f9ba70`, filter `0x141f9b920`): candidates whose exit
  multiset (door type, height, chirality) contains the node's required exits. `GetExactRooms`
  (`0x141f9b2b0`, `0x141fc04d0`) serves `(best)` nodes; `GetFeatureRooms` (`0x141f8b8c0`) is the
  fallback (all 8 orientations, weight 1). `GetExactRooms` compares door, height byte `+8` and
  chirality `+9` per side, but a door-less side matches a door-less exit of any height (`exact_sides`;
  `.arm` version 36 gives door-less exits the height values -1..-4; the exit parser is a visitor of
  `0x142931f30`, vtable `0x1434eb560`; setting height 0 for every door-less exit loses thousands of
  matches). Debug: `POE_DBG_THINGY` (every `.arm` exit), `POE_DBG_EXACT` (`(best)` candidates with
  their exits).
- The size map (`0x141f99ca0`, called per room as the room set loads) adds a room's sizes once per
  distinct non-default door type of its exits (`+0x58`, 16-byte entries), else under room data
  `+0x180`: the root slot's first set edge (G2_12's `Unique/entrance.arm`: root edges
  `cart_walkway.et`, -, `rooms.et`, `rooms.et`, so it counts under `cart_walkway.et`); a root slot
  without edges keeps the default when an exit has a door. Rooms with only default doors count under
  the default type, whose plain sizes need a full ring at height 0 (`0x141f98d30`). The weight is the
  `.rs` line's; `0x141f99920` parses the orientation mask. `0x141f9a9b0` adds the room to the
  per-ground size lists and, when that type is virtual (`.et` flag 4) with equal split types, adds
  it once more with the split type: a blank room whose first root-key edge type is virtual with
  equal splits counts twice in the fillers (`POE_FILLER_SETS=1` restores the room-set rule; port:
  `DungeonRoom::root_door`, `size_map_final`, old rule `POE_SM_OLD_DEFAULT`).
- Room data `+10` ("own ground"): the lattice settle gives a placed room's points its root ground
  (`+0x13a`) instead of the graph's default when set. It comes from the `.arm` parser callback
  `0x141f96f20` (the header's first field, the string-table count, is below 2: a room that names one
  ground only) and from `0x141f98430`, which also sets it for blank rooms (no tag, `special…` tags
  counting as none; one ground on the four root corners; no doors) whose slots' corners are all as
  walkable (`.gt` flag 4) as the root ground. `0x141f98430` sets the "blank" flag (+9) only for
  rooms without a tag, so a `special` room never has it (a door-less special room needs no ground
  match; a placed special room keeps its own ground in the settle).

## Typed nodes (`0x1420ae8d0`)

1. Required exits: per side slot, the edge's type, max(height of its nodes) − node height, and
   chirality (`0x141f968b0`: (edge from == node) xor edge chirality, chiral door types only).
2. Candidates as above; each is kept when the node orientation is `(any)`/`(best)` or equal to the
   candidate's, and the room fits (`0x1420af400`): its unit cells are free (state ≤ 1) and at least as
   many of its doors lead into the grid as the node has edges. A door facing a placed room whose
   matching door differs marks the candidate (a door of the default edge type or of a `can_end` type
   never marks); marked candidates are dropped when unmarked ones remain.
3. `below(total)` (`0x1420aed49`). Origin (`0x1420af140`): the node's unit cell minus the room's
   extent on mirrored axes (region orientation table), clamped into the grid. If a room next to that
   rectangle is the same `.arm` (`0x1420b16d0`), one more `below(total)`.
4. `0x142096870`: the node's side slots weighted by extra door % (`below(sum)`, `0x142096993`), giving
   the extra door type.
5. Stamp (`0x1420a7550`, `0x1420a7130`): grid cells = room index + 2; the placed record keeps origin,
   size, orientation and the exits turned back through the inverse orientation (`0x142f087c0`).

**Typeless nodes** (`0x1420aff50` → `0x1420afbc0`) skip the side adjustment: `0x1420c7850` calls
`0x1420c5340` only for nodes with a room type; an empty candidate list draws nothing
(`place_node_opt`).

**Accessibility.** An edgeless typed node (`bonfire` of the Gallows village graphs `village_{sn,ws,se,sw}.dgr`)
is not accessible when `0x142097e30` lists the ground-only cells (entry `+0x10`, what the pre-unique
room `0x14209c2d0` tests; `0x142095f10` counts only the node's four slot edges with edge `+0x62`,
and the tags), but its cells are by the time the fill reads the room flag (`+0x15` bit 0, record
byte `+0x10` of `0x14209d0d0`, `0x142098b91`), which offers the chest fill rooms there. The port
keeps both: `GroundCell::early` for the pre-unique room, `accessible` (`node_accessible`,
`PlacedRoom::late_access`, border slot flag 0x40) for the fill. What sets the flag in between is
unknown.

## Trace landmarks (G1_3 seed 1001)

The client used topology 2 (`mudburrows_NW.dgr`) with orientation 4: the placed rooms (entrance 1×2
at unit (4,4), boss 2×2 at (0,0), `nospecial` at (2,0) and (0,2)) and the draws (room picks 1, 4, 1,
4; extra door sums 200 each) fit only that. The draws match the `.tgr` path for the first 11
(existence rolls `0x141feec90`); the dungeon starts at draw 11 (`0x1420aed49`). Later call sites:
`0x1420b0092` (`below(2964)`), `0x1420a6430`, `0x1420a610a`, `0x141fa8323`, `0x1420b13dc`/
`0x1420b14cc`, `0x1420a5014`/`0x1420a5047`, `0x1420a9d1f`, then the tile pass (`0x142098e98`,
`0x14209fa38`), fill, outer buffer and de-repetition as for `.tgr`. Other draw sites seen with no
further meaning: `0x141f8feda`, `0x141fc028f`, `0x1420a219f` (exit wiggle), `0x1420ab7e7`
(encounter requests), `0x14209c36a`, `0x1420c9c81` (`place` line). Debug: `POE_RNG_BT=<draw>` (a
backtrace when the port makes draw number `<draw>`), `POE_DBG_SUBDRAWS` (the draw index at which each
subgraph starts).

## After the rooms (`0x1420ac560` step 4 onwards)

- Corridors (`0x1420a5fd0`, `0x1420a2df0`): one record per placed room with a `below(128)` cost;
  edges batched by priority and container (edge types with one room size / other / default;
  corridor types sorted by path in the graph's own case, a case-sensitive u16 compare `0x141fadfa0`,
  `0x1420a5260`: a discarded `below(n)` and a shuffle, then stable-partitioned: types with one room
  size `0x1420a5730`, other types, the default type). The default edge type (`rooms.et`) is always
  the last container, even with a one-entry room-size list. Edges are shuffled (a discarded
  `below(n)` then a forward Fisher-Yates); placeholders fill free cells; each edge is joined by A*
  over rooms (`0x1420a44b0`: g += isqrt(centre distance in half units)/2, h = (dist/2)(100 − fuzzy) +
  (impenetrability << 7)/100 + fuzzy·cost, open set by (g+h, id); `POE_DBG_ASTAR=1`). Unused
  placeholders are compacted away (swap with the last room, ids remapped). The stage is skipped (no
  records, doors, room assignment) when every edge is removed or void, and a graph without edges has
  no corridor stage.
- **Corridor height marking** (`0x1420a3130`, called by `connect` `0x1420a3ba0` at `0x1420a40a0` and
  by the first loop of the branch pass `0x1420a5800`, which runs it again on each inner room of every
  path of the edge type since `compact` `0x1420a6790` and `fill_placeholders` made new placeholders;
  arguments: next room towards the start, the inner room, the previous room, the edge's door type
  `+0x38`, its chirality `+0x41`): marks every door-less side of the inner room only for a symmetric
  type. For a type that `0x141d04930` calls asymmetric (height change `+0x4c` set, left/right grounds
  `+0x20`/`+0x28` differ, or a virtual type whose split types differ, or whose shared split type is
  itself asymmetric with equal chirality bits) it takes the ring side of the door to the next room
  (`0x141fa7ec0` with the chirality flipped, first position) and to the previous room, and per ground
  that is a wildcard or has `.gt` flag 1 (left with `1 + 2·!chir`, right with `1 + 2·chir`) marks
  side `(k + side) & 3` through `0x1420a3640`. That function checks one ring side for doors and marks
  a different strip: ring top marks the strip above, ring right the strip below, ring bottom the
  strip left, ring left the strip right (`0x1420a35b0`). Marking all sides gave placeholders next to
  an outer-edge corridor a second corridor height, so `branch_starts` (`0x1420a4b90`: exactly one
  height, a byte vector) dropped them. Port: `dungeon.rs` `asymmetric`, `side_marks`, `mark_around`,
  `mark_side`, `mark_strip`; `POE_OLD_MARK=1`. Debug: `POE_DBG_DOOR` (door picks, branch starts with
  the draw index), `POE_DBG_HMARK=x,y`.
- Branching (`0x1420a5260` / `0x1420a5800`): per corridor key, candidates next to corridor rooms;
  count ⌊c·n/100⌋ + (below(100) < remainder); depth rounds grouped by chance2.
- Extra doors (`0x1420a9b60`): per room with an extra door %, shuffled candidate positions,
  `below(100) < pct`, pct −= 100.
- Placeholder rooms (`0x1420b1160`): size-bucket entries of non-unique generic rooms × allowed
  orientations, matched strict / optional extras / any; weight (empty²·10+1)·w; orientation
  `region::pick(mask, below(840))`; one re-pick when a neighbour uses the same room. Matching
  (`0x141f9b5b0`) compares chirality for chiral types.
- `0x1420a9710` (open door counts) draws nothing.
- Special rooms (`0x1420aa890`): `.arm` tags `special` / `specialN` / `specialchance N` (room data +8
  flag, +4 list index, 0xff = chance list, +5 chance, default 100). The room set keeps one list per
  index (`.rs` order) and appends the chance list last. Indexed lists: a discarded `below(n)` and a
  shuffle, then the first entry that places. Chance list: every room with chance ≥ 100, or 1..99 with
  `below(100) < chance`. Placement (`0x1420a7f20`): reachable placed rooms with an `.arm` that is
  neither special nor tagged, whose doors match the special room in its first matching allowed
  orientation (`0x1420a7dc0`: equal doors, or closed where the special door is optional; with
  optional special doors the room needs one of its own); `below(count)` picks the room, `below(weight)`
  the variant. The room keeps its doors and becomes kind 8. The exact-fit candidate list is **sorted
  by placed-room index** (`0x1420cf350`, a lower-bound insert keyed by the room index), not in
  discovery order, for the `below(count)` pick (`0x1420a8528`; `dungeon::place_special`).
- Special-room split (`0x1420a8b00`, used when no room matches exactly): at the corners of each
  eligible room, per allowed orientation, a spot where the special room covers free cells and whole
  non-special untagged rooms of one height (`0x1420a8d40`) with agreeing doors along its sides
  (`0x1420a9140`; a default-type special door may face a closed one, but not all of them). Spots are
  kept sorted by x·65536 + y (`0x1420cf0e0`); `below(spots)`, `below(variants)`; the covered rooms are
  removed (highest index first) and the special room is stamped at the height of the last one removed.
- Mission rooms and feature requests: [Feature rooms](#feature-rooms-and-league-mechanics).
- Filler rooms (`0x1420b1b70`, before and after the special rooms; reserved cells are freed in
  between): per room in order, each side (right, bottom, left, top) whose two turned corners share a
  ground spreads it into the empty cells beyond (`0x1420b2520`, height = room height + that door's
  height), first for grounds with `.gt` flag 2, then the rest, each pass repeated while it places
  anything. The ground's size list (room set +0x98) has per blank room (no tag, one ground, no doors)
  its size and, if not square, the turned size, each with the room's weight, in `.rs` order;
  `below(total)`, and a size that does not fit drops its first entry and is redrawn (`0x1420b28ea`).
  The spot covers the cell: corner at the cell, then shifted left, up, up-left (`0x1420b2d30`); the
  room is drawn among the ground's blank rooms of that size (`0x1420b2ba1`), its orientation with
  `below(840)` (`0x1420b2bb8`). `.tsi` `DungeonFillRoomHeightOverride` (master +0x14d, set flag
  +0x159) replaces the filler room height (`0x1420b1d50`).
- Chirality: a door type is chiral (`0x141d04930`) when it changes height or has two grounds, or is
  a virtual edge whose halves differ or are the same chiral type with equal flags. `.arm` exits carry
  it (the third number up to version 29, the fourth after); mirrored turns flip it. Typed nodes
  require (edge from == node) xor edge chirality (edge value 1). A door between `a` and `b`
  (`0x141fa8150`) gives `a` `!chir` and `b` `chir`; shared positions (`0x141fa7d70`) require those,
  and a chiral door of another type on either side empties the list. Corridors pass the edge's
  chirality (A* neighbour test `(cur, n, chir)`, expansion `(n, cur, !chir)`); branches, extra doors
  and `0x1420a4210` pass 0. Door picks: `0x141fa82c0` shuffles the list of `0x141fa7ec0`; helpers
  `0x141fa7c40`, `0x141fa7d70`, `0x141fa7b60` (port: `shared_doors`, `facing`). Encounter rooms are
  shuffled with `0x1420d1030`.
- Void edges block their cells (Bresenham, `0x1420ad5a0` / `0x141fa8890`).
- `.dgr` node random offsets (`0x141fea460` → `0x141fee9b0`, before the existence rolls): node
  values 5..8 are x min, y min, x max, y max (node +0x78..+0x84); x += min + `range(0, max − min)`,
  then y. The graph turn (`0x141d14cb0`) turns each (min, max) pair as a vector by the region table
  (`[-x, x, -y, y]` indexed like the position), then puts each axis' pair in order; odd and mirrored
  orientations otherwise draw from the wrong ranges. A node with the lock flag (+0x41) keeps its
  orientation. Comma-list room types (`Gates_N, Gates_FN`): `0x141fea5a0` → `0x141fee860` runs right
  after the node offsets for every node, in node order: a room type with a comma keeps one entry,
  `below(count)` (`area.rs` `random_offsets` does both passes).

## Feature rooms and league mechanics

Generator object `+0x48` holds the feature rows, `+0x144` the budget (list size for a one-graph job,
`0x141f8bce0`), `+0x148` the cap. Rolls and the `.tgr` pass: [tgr.md](tgr.md#league-mechanic-rolls-phase_cad0-0x141ffcc50-leaguers).
Master offsets: `+0x1f8` RoomSet, `+0x200` Overlays, `+0x218` FillTiles (not overlays), `+0x230`
OuterGroundType. Two mechanisms, chosen by the room set:
1. **No mission rooms** (`.rs` has no `mission` tag): the feature pass `0x14209a7a0` → `0x14209aa00`
   → `0x14209ae20`, inside the `0x14209c640` block (gate: master has FillTiles), before the injectors
   (`0x14209b490`) and the pre-unique room. Like the `.tgr` pass `0x1420bdc60` with: cell list = the
   ground-only cells (shuffled: discarded `below(n)` + forward Fisher-Yates), cell must be
   accessible, its ground and the lattice corner ground missing or with `.gt` flags 4 and 8,
   rectangle in bounds and free (`0x141d0da00`); pass 0 only: squared rectangle distance
   (`0x14209a6c0`) > 16 to rooms already placed by the pass; pass 1 retries leftovers without the
   check. Port: `fill::place_league_rooms_dgr`.
2. **Room set with mission rooms** (mission table = room set `+0x130`, key = number of `missiontile`
   slots, filtered to rooms whose `.arm` side length equals RoomUnitSize): `0x14209a7a0` removes the
   non-priority features (column 7 of `ExtraTerrainFeatures` = `+0x60`, false for StoneCircle) from
   its list (flag from `+0x130 != +0x138` and master `+0x15a == 0`), and the room assignment step
   `0x1420aae70` (after the special rooms `0x1420aa890`, before `0x1420ac0e0` shrines and the second
   filler pass) handles them. A 3x3 feature `.arm` is queued as a request (`0x1420abd10`); a request's
   room is placed directly with `0x1420a7f20` (its orientation mask, no shuffle) when it is not 3×3,
   or the room set has no mission table and its `.arm` side length is the grid's unit size
   (`extra_features`, served via `take_league`). Requests are served by mission rooms put over placed
   rooms (`0x1420a7f20`, port `place_special`) in a snapshot/retry loop over the table entries
   (groups of the entry, then smaller keys from the back, then every entry from the front); each
   served request draws `below(0x348)` (orientation via `0x1421c3f40` = `region::pick(0, v)`) and
   joins the generator's pending list (`0x141f8acd0`), the feature leaves the list (`0x141f8b4a0`,
   budget-1). The tile pass (`0x142098550`) hosts them: a `missiontile` slot with no tile for its key
   picks `below(n)` among the pending rooms whose oriented size equals the slot (`0x141f8b5f0`), sets
   the 3x3 lattice heights/flag 2, and places the room (`0x141f8ca40`, height = slot height, ground =
   lattice ground at the slot). Port: `dungeon::extra_features`, `Grid::pending`, `TilePass::host` /
   `fill::place_hosted`, league tiles added to the master right after load (the client adds them with
   the feature, `0x141f8b050`).

The feature list is shared by all graphs of a job ([tgr.md](tgr.md#league-mechanic-rolls-phase_cad0-0x141ffcc50-leaguers)).
`Files::take_league`. Not ported: the room-injector passes `0x14209a7a0` / `0x14209b490` (room set
`+0x118` list, gated by `+0x148` of the context; rooms `room_injector*`, `telepad_injector*`,
`tile_injector*`) and the other mechanics (0: `+0x188`, 2: `BrequelExpandingEncounter`).

**Pre-unique room** (`0x14209c2d0`, runs before the overlay context is built when the master has an
overlay list and the room set a `preunique` room): the ground-only cell list is shuffled (a discarded
`below(n)`, forward Fisher-Yates), then walked; each iteration draws `below(0x348)` (an orientation
of the `.rs` mask), and the first cell that is accessible, has no ground or a ground with `.gt` flag
8, and whose room rectangle lies free in the region takes the room (`0x141f8ca40`, height = the
cell's). None fits: "Failed to place pre-unique room". The cell list is sorted by (x, y) only
afterwards (`0x141f92e60`); `dungeon_tiles::TilePass::run` returns it unsorted. A `.tgr` master with
room-set `preunique` rooms runs `0x1420bda10` + `0x1420beac0` after `0x1420be4e0` (the list is
`+0x148` of the room set, built by `0x141f99ca0` from rooms tagged `preunique`).

**`PairedRoomLayoutPlugin`** (the area's `TerrainPlugins` row; MapKarst): its layout hook
`0x141f01890` runs for a graph when an earlier graph of the same grid size exists (MapKarst:
`_upper_01.dgr` and the node-less `_abyss_01.dgr`, both 12×12 units, subgraphs of the container
`Karst_01.dgr`). When both masters name the same `FileGroups` file and it has one group (`Pairs`),
its `.arm` entries pair up in order (upper, lower); with two groups the first lists the upper rooms
and the second the lower ones (not ported); masters with different file groups key the pairs by a
4-character projection key after the group name's last `_` (not ported). `0x141f02b30` per room of
the earlier graph in placement order: skipped unless its rectangle is inside this grid with every
cell state ≤ 1; the room's `.arm` found in the upper list gives the lower partner (`[unique]`),
placed with `below(1)` over the one candidate (`0x141f032ee`) by `0x1420a7550` at the same origin,
with the same orientation, height (`+0x12`) and kind (`+0x14`) and no doors. Port: `dungeon.rs`
`paired_rooms`, `Files::paired_rooms`, `Built::layout` (`POE_NO_PAIRED`).

## Tile pass (`0x14209c640`)

1. Pass A (`0x142098550`), per placed room in order: the `.arm` grid row by row (y outer). Slot
   anchor +0x73 (`origin`: SW 0, SE 1, NE 2, NW 3) moves a multi-cell slot's listed cell to its
   corner; position and key are turned by the room's orientation; the lowest corner height moves into
   the tile height (slot +0x72). Ground-only slots (no feature, edges or heights, one ground; `s`
   slots and `f` without a fill name too) only mark their corners' height and are listed for the fill
   (`0x142097e30`). Odd-sized slots centred on the room's border line (`0x142099d10`) go to the
   border map. Others: tile-set lookup, `below(total)`, place, then `0x141d0b510` (cells and corners
   take the height).
2. Border map (`0x142098100`, sorted by x·65536 + y): the first room's key is stored with the sides
   it covers (4 top, 0x10 right, 2 bottom, 8 left; bit 0 reachable); the second is merged
   (`0x142097470`): corners it covers fully take its ground (none for `.gt` flag 0x10) and height,
   sides only it covers take its edge, shared sides are combined by the `.ecf` (`0x1420a2a40`: edge
   pair + corner height difference → edge; rules without a height number (`canopy.ecf`) apply to any
   difference: (pair, difference, exact) first, then (pair, any); no rule: a lone edge stays, two
   give none; exits kept when equal, else the middle). Heights are rebased to their minimum (signed).
3. Pass B (`0x14209fd40`), x-major: ground-only keys without names are marked. A partial overlap with
   placed tiles is an error; over a placed tile its key is merged in for the sides no room gave
   (0x1c↔0x1a, 0x16↔0x0e, else 0x1e), heights rebased; otherwise sides seen by one room drop their
   flag-0x10 grounds. Named slots draw a name by its tiles' total weight (1 without tiles) until one
   places (a 1×1 `door` becomes a door group cell). Then a uniform key is marked, else `0x14209f1d0`
   with no name (seen |= 0x20, door bookkeeping). `0x14209f1d0`: lookup; without tiles, sides with a
   non-virtual, non-centred edge whose exit is off the middle (size·3/2) and that face another border
   entry (any side with `.tsi` `AllowInteriorOverlapFixes`) take the middle exit one by one until
   tiles exist (`0x14209fb90`); after placing, `0x14209edf0` gives the cell across each moved side
   the middle exit too: a border entry still to come in its key, a placed tile with the same edge and
   side length by drawing it again. The height fallback (`0x141d056e0` / `0x14209fc80`) is not
   ported.
4. Tile lookup (`0x141d0a640`, `TileSet::candidates`): the tile set keeps a second index with the
   corner heights flattened (all four corners to the lowest); when the exact key finds nothing, the
   lookup retries with the flattened key. A key ground with `.gt` flag 0x10 is none (`add` stores the
   tile key that way, the lookup reads the same). Case: grounds compare case-insensitively
   (`grid_fits`, as the client's resource lookup lower-cases).
5. Doors (only with a `door` feature, case-sensitive: the tile pass `0x142099e00` sets `+0x38` only
   when the tile set's feature map, `+0x228` → `+0x50`, `0x141d186f0`, has an entry for `door` (UTF-16
   `0x1434e28d0`) with tiles; Tundra's `Vall_*_Door_01.tdt` have the feature `Door`, so no doors there;
   `POE_DOOR_ANYCASE=1`). Open exits mark their unit's middle cells on the border line (`0x142096c50`);
   straight passages across a marked shared exit become door groups (`0x1420971e0`). Both door passes
   (`0x14209d300`, `0x14209de10`) are called from `0x14209c640` only without `DisableDoors` (`.tsi`,
   master `+0x167`) and with a room overlap. `0x14209d300` (gated by master +0x38), per group without
   a `door` tile: the group runs vertically when its first two cells share x or every cell has both
   side markers (0x18), else horizontally; the anchor is the first cell with the lowest coordinate
   along it. Door sizes for the anchor tile's edges (`0x141d09880`: per feature, keyed by the 4 edges,
   a sorted set of oriented sizes, `0x141d09c30`) that fit the group (len × 1 or 1 × len); a discarded
   `below(n)` and a shuffle; the first size whose key (size set, exits of 3 replaced by size·3,
   virtual exits [w·3, h·3, w·3, h·3]) has `door` tiles wins. Offset along the group: for a 1-wide
   door with an odd unit the cell whose coordinate mod (unit − overlap) is unit / 2, else `below(len −
   span + 1)`; `below(total)`, placed at the cell's height over the old tile. `0x14209de10` (3×3
   spots; `dungeon_tiles.rs` `check_doors`): for every spot in the list pass B built (3x3 tiles
   touching a shared exit), if the cell holds the corner (offset 0,0) of a tile without the `door`
   feature, the `door` tiles for that tile's own oriented key are looked up; a hit draws `below(total)`
   and replaces the tile at the cell's height (`place` with flag 1). Debug: `POE_DBG_BORDER`.
   - **Door-edge walkways without room overlap**: with `DoorEdgeType` (master `+0x250`, e.g.
     `cart_walkway.et`), no `DisableDoors` and a room overlap of 0, `0x14209c640` runs `0x14209e0d0`
     instead of the door passes (both also need the tile set's `door` feature, ctx `+0x38`). The list
     at pass `+0x78` (12-byte entries x, y, side; sorted by x·65536 + y, `0x1420cfd50`, a repeated
     cell takes the later side) is written per room by `0x142096fb0` (the overlap-0 counterpart of
     `0x142096c50`): for every exit with a door, exit index i walks the perimeter (top, right, bottom
     reversed, left reversed) and lists one cell, the middle (`unit / 2`) of the exit's unit on the
     border line, with side 0 top, 1 right, 2 bottom, 3 left. `0x142097e30` (ground-only slots) also
     fills the ctx `+0x70` hash map (node `+0x10` x, y; `+0x20` ground; `+0x28` accessible; `+0x2c`
     height; last write wins) in this case. `0x14209e0d0`: per entry (cell A, side s) whose neighbour B
     across s is listed with the opposite side, `0x14209e310`(A, opposite of s) and (B, s) are tried
     dry (`param_4` = 1) and, if both succeed, run for real in the same order. `0x14209e310`(cell,
     dir): out of the map or an empty cell without a ground-map entry fails; the key is the placed
     tile's (oriented, origin = cell minus record `+0x34/+0x35`, height record `+0x30`) or a 1×1 key
     with the ground on all corners, the height on all corners, exits 3 (height 0 for the placement).
     The facing side (opposite dir) already the door edge: success. Otherwise that side takes the door
     edge with the exit at the middle of the cell's part (`3·off + 1` on top/right, `3·(size − off) −
     2` on bottom/left); if the key had no door edge anywhere, side dir takes it too and, when `door`
     feature tiles exist for that key, the walk recurses into the next cell along dir (offset by the
     key size − 1), and the two-sided tile stands when the recursion succeeds or the edge type has
     `can_end` (`.et` flag 0x10); else only the one-sided key is looked up. Placement `0x14209ec30`:
     `below(total)` over the `door` candidates (after the cells further on), the tile's (w+1)×(h+1)
     corner points lose their ground and flag 1, then `0x141f9e460` places it (no `0x141d0b510`).
6. `place_tile` `0x141f9e460`: with tile data `+0x16f` bit 1 and no edge of a real type the
   orientation is `& 3`. `+0x16f` is set by `0x141d05520` (run when a tile's data is loaded,
   `0x141d068b0`): bit 0 when the tile's model data names an `AreaTransition` object, bit 1 when an
   object's type path contains `Spawner` (the `.tmd` beside the `.tgt`, UTF-16, the quoted type is
   the last field). The Spawner flag is the OR of two `.tmd` sources: the art `.tmd` beside the
   `.tgt` *or* the `.tmd` the `.tdt` names. Port: `Tdt::spawner` (`load_tdt`, only computed for tiles
   whose edges are all wildcards or absent), applied in `TileMap::place` (`CenterHoleLarge_01.tdt`
   loses the mirror bit).
7. Room ground overrides (`0x141f9e900`), then the fill: the listed ground-only cells, stable sorted
   by (x, y), each filled with its ground and its slot height (`0x14209d0d0` → `0x141f8fab0`;
   `0x141f90ad0` uses a passed height unless it is `i32::MIN`, which the `.tgr` fill passes).
   **Fill rooms** (`0x141f8ca40`): a room cell's tile height is the passed fill height (the listed
   ground cell's slot height) plus the slot key's lowest corner; a uniform slot's fill-group tile
   (`0x141f8d73f`) sits at the slot's height byte (`+0x72`, its lowest corner) plus the room's height
   (`param_6`). When the caller passed none (`i32::MIN`), `0x141f8fab0` gives a fill room the middle of
   the corner heights over its whole oriented extent (`0x141f90ad0` with the room's size, room data
   `+0x138`/`+0x139`) and `0x141f8ca40` uses it for every slot (`fill.rs` `place_room`; switches
   `POE_NO_ROOM_HEIGHT`, `POE_NO_SLOT_HEIGHT`). Fill rooms on unwalkable ground (`0x141f91290`): only
   rooms with a point of interest that has a tag are kept out; untagged points of interest do not
   count.
   Exit wiggle (`0x1420a20f0`, after the fill): pass A records square unnamed slots whose edges all
   have the slot's size and one has `.et` random wiggle (fourth number) ≥ 2, or ≥ 1 on the room's
   border line (`0x142098c98`); the fill's listener (`0x14209a440`) records fill tiles the same way
   (wiggle ≥ 1), and so do tiles placed by overlay rooms. The set is ordered by x·65536 + y; a
   discarded `below(n)` and a shuffle; per position whose corner cell still holds such a tile, a
   discarded `below(4)` and a shuffled side order; each side with a wiggle edge takes the hashed exit
   (`0x142196b30`) when it differs, if tiles exist for the key (grounds with `.gt` flag 0x10 left out)
   and for the tile across (its opposite exit `size·3 − exit − 1`), else it is put back. Then the tile
   and each accepted neighbour are drawn again (`below(total)`) and placed. Positions may lie one cell
   outside the region (overhanging tiles).
8. De-repetition and outer buffer as for `.tgr`. The scan `0x141fdd940` skips a tile whose key
   (`0x141fd5dd0`) is uniform: every edge empty or of a type with `.et` flag 0x80 (wildcard name,
   `0x141ef2570`) and one ground on all four corners (class `0x141fdfeed`; `generate.rs` `derepeat_pass`; the room pass
   and fill keep `uniform_ground`; debug `POE_DBG_REPICK`). The outer buffer first fills the region's
   empty cells (grid cells without a room) with the `OuterGroundType`'s first fill tile
   (`0x141fd6170`), see [Heights and the outer fill](#heights-and-the-outer-fill).
9. Cell heights are stored in world units: storeys × `StoreyHeight` (`.tsi`, master `+0x14a`).

## Overlays in the dungeon tile pass

`0x141fa0c40` builds the context after pass B and the doors, phase 1 (`0x141fa1bf0(ctx,1)`) runs,
then the fill of the listed cells (`fill_cells`), then phase 2 `(ctx,2,1)`. In `.dgr` graphs the
candidate scan is cell by cell (generator flag `+0x90` bit 0 turns the 3-tile stride of
`0x141fa1fe0` off), and phase 1 also records the tiles under an overlay for the refill
(`0x141fa2560` refill flag). The context's room list (`param_4+0x58`) is the dungeon grid's placed
rooms: rooms whose `.arm` has a tag mark bit 4 on their rectangle shrunk by the shared border (when
the room's own overlap equals the master's) and bit 8 on the whole rectangle; nodes with tags mark
bit 0x10. Mission rooms count as feature rooms; rooms placed by the special pass do not. Rooms placed
before the context (the league rooms `0x14209a7a0`, the pre-unique room `0x14209c2d0`) count too
(`area.rs` `.dgr` path, `POE_NO_LEAGUE_RECTS`). Tiles the refill places feed the exit wiggle list.
- **Pick weights** (`0x141fa2560`): an entry counts its weight once, or with `MatchAllTileKeys`
  (group flag 0x40) once per orientation of the entry (the ones turning the group's key) whose room
  keys all sit on the laid tiles (`0x141fa3900`); the orientation is then drawn from the whole entry
  mask (`FUN_1421c3f40(mask, below(0x348))`).
- **`!Name` exclusions** (`0x141fa35f0`): the tiles that start inside the candidate rectangle and
  carry a feature name must include every listed name. **`MatchAllTileKeys`** (`0x141fa3900`): the
  check walks every grid slot whose flags `+0x70` / `+0x71` are clear and needs the laid tile at the
  slot's turned position to be an origin cell whose feature (tile data `+0x28`) equals the slot's
  tag (`+0x50`) and whose key (`0x141d08bc0` turned, `0x141d09a80`: grounds with `.gt` flag 0x10
  dropped) equals the slot's turned key (memcmp of 0x4e bytes), tried over the entry's orientations.
  `cnr_overlay_stonewarrior_01.arm` (grid `k..f / ...f / ...f / fffs`) also needs its fill slots (1x1,
  the fill name as feature, `cell_key`) and its `s` slot (a blank 1x1 key without feature; "an `s`
  slot never matches" loses a later phase-2 match) on matching tiles. Port: `overlay.rs`
  `matches_all_keys` (`POE_MATCHALL_K_ONLY=1`, `POE_MATCHKEY_RAW=1` keeps 0x10 grounds). Debug:
  `POE_DBG_MATCHALL=x,y`.
- **`limit=` groups** (`overlay.rs` `run`, FileOrder branch): a group whose rooms have all reached
  their `limit` is not collected (G4_13 `overlay_seagullsoncorpse.arm limit=1` is listed in two groups
  by orientation set 0x0f / 0xf0; the second has no pass in the client).
- **Key-less roots** (`Slot::S`, e.g. `overlay_seagullsoncorpse.arm`: a 1x1 grid with doodads and
  points only): the group key is a blank key of the grid's size with exits and virtual exits 3 × the
  side length, so mirrored orientations give the same key and the room stays one group
  (`Overlays::new`, `POE_SROOT_EXITS0`).
- **Room height** (`0x141fa1230`, `overlay::room_height`): the client walks every slot of the room
  grid (room data `+0x168`, 0x78 bytes each) whose flags `+0x70` / `+0x71` are clear, not only `k`
  slots: border corners against set terrain heights (`terrain - corner`) after subtracting the corner
  height (`+0x42`) and the slot height (`+0x72`); corners whose ground follows heights (`.gt` flag 1,
  or none) must agree, the others vote; `room_pass_oriented` takes the base height and puts each slot
  at `base + lowest corner`, also for negative corner heights (subtract the lowest corner and place the
  tile at it). `f` slots count as 1x1 ground-less slots at height 0 (`POE_RH_K_ONLY=1`); which slot
  kinds set `+0x70` / `+0x71` (`n`, `s`, `o`) is unchecked; `+0x72` is 0 for every slot seen. Debug:
  `POE_DBG_RH=1`, `POE_DBG_RH=x,y`.
- **Fit test** `0x141fa19b0` calls `0x141d0ddc0(map, rect)` before `room_fits` (`0x141f9d380`): true
  only when the rectangle holds at least one tile and every tile record in it (any record with an
  object, its size from the tile data `+0x60/+0x61` turned by record `+0x36`, its corner from
  `+0x34/+0x35`) lies fully inside (`covers_whole_pieces`, with the header size for cells without a
  `piece_at` entry; `POE_PIECES_OLD`). The corner test of `0x141f9d140` passes a lattice ground on
  `+0x25` bit 0 (`SynthesisBackground`), not `0x80` (`overlay::room_fits`). Ground compare is
  case-insensitive. Tool `ofit` (client DLL, `terrain_tools.rs::on_room_fits`, signature `room_fits`
  `0x141f9d380`): every call from the overlay scan as a trace line `ofit x y WxH fFLAGS` / `code e
  <edges> h <heights> g <grounds>`, positions in client coordinates (add 6 to ours); compare with
  `POE_DBG_OVERLAY=1` (candidate groups, picks, `FIT` lines with flags, edges, grounds),
  `POE_DBG_OCC=<file>` (occupancy grid), `POE_DUMP_LATTICE=<file>` (writes `<file>.<w>x<h>`; compare
  with the trace's `lattice 92ce0` view of the same size).
- **Second lattice settle after overlay pass 1**: the corners an overlay room clears (`0x141fa2560`
  clears its whole `(w+1) x (h+1)` corner rectangle: ground 0, flag 1 off) and its tile leaves
  without a ground get the rooms' settle ground (`0x14209a010`) again before the fill; the port runs
  `settle_rooms` again after overlay pass 1 (`POE_NO_RESETTLE=1`; where the client runs it was not
  located). Debug: `POE_DUMP_LAT2=<file>` (lattice after overlay pass 1).
- Overlay rooms may have a root slot that is not a key: the group key is a blank key.

## Settle and lattice

- **Per-room lattice settle** (`0x14209a010`, after the ground overrides,
  `dungeon_tiles.rs::settle_rooms`): lattice points of a placed room without a ground take the room's
  ground (a blank room's own, else the graph's default, graph line 2); a point at the lowest or
  highest height of the map takes the graph's low (line 3) or high (line 1) ground (not
  `impassable_ground.gt`); the point is then set. The room's own ground is used only for
  "walk-uniform" rooms (room data `+10`, see Rooms); otherwise the graph's default ground
  (`uniform_walk`; `Fill_02.arm` of MapBastille is not uniform). Switches `POE_NO_SETTLE`,
  `POE_OLD_EDGE`, `POE_NO_GRFLAGS`, `POE_NO_UNIFORM_WALK`, `POE_OLD_OWN`; debug `POE_DBG_FILLCELL`
  (fill cells and placed tiles), `POE_DBG_SETTLE=x,y` (which room settles a point), `POE_DBG_CELL=x,y`
  (tile at a cell after each dungeon stage), `POE_DBG_FILL=1` (fill list cells with the draw index),
  `POE_DBG_MARK=x,y` (the ground-only slot that lists a cell), `POE_DBG_LATROWS=y0,y1`,
  `POE_DBG_PU_IN`, `POE_DBG_ACC`, `POE_DBG_PU_IN`.
- **Corner writes of tiles that overhang the region.** The client's region is a window into the full
  map. A dungeon tile placed at `y = -1` (or past the far sides) still writes the corner points that
  lie outside the region window; the port keeps those writes as spill entries and replays them in
  `embed` / `paste` with `place`'s corner rule, `0x141d0bc50` (the second loop,
  `0x141d0c047..0x141d0c272`): the ground is always written (through `0x141d0e2b0`, which has its own
  gate: a set cell only takes a different ground when neither ground has `.gt` flag 1 or 4 and
  `0x141d026b0` says no; not ported, no case needed it); the height `d + h` and the set flag only when
  the new ground is null or has `.gt` flag 1, or the old ground is null or has flag 1 (first writer
  wins, e.g. `Cliff_Fill` overlaps). `set_heights` (`0x141d0b510`, called right after `place` at
  `0x142098f71` and `0x14209fb4c`) writes `h + d` on all corners of the tile with no flag rule; the
  corners inside the map are set and the ones outside become `Spill::Height` entries. Post-unique
  tiles see the overhang too: `0x141ff2210` scans the graph's rectangle in the full map (−1..=w ×
  −1..=h with spilled cells, `TileMap::piece_or_spill`; `POE_PU_REGION_ONLY`).
- **Underlying map bounds**: the fill's fit test (`0x141f9e770`) allows one cell of slack past the
  region, but `0x141d0dac0` then tests the underlying map, the region plus its `OuterBufferSize`
  margins (a window: its parent's): with margin 0 a 3×3 fill tile hanging one cell past the bottom
  does not fit, the entry is removed and the retry loop draws `below(rest)` at `0x141f9037a`.
  `TileMap::bounds`, set in `build_dungeon` (`POE_NO_BOUNDS`). Fill tiles may overhang the region by
  one cell (x, y ≥ −1, far side ≤ size + 1; [shared-passes.md](shared-passes.md#region-overhang)), so
  3×3 ground slots on the region's border fill from −1.

## Subgraphs

- `0x141ff7f80` → `0x141ff0770` per subgraph: a `graph` node (`0x1420ae150`) reserves its rectangle
  in the main grid; after the main graph's fill and de-repetition, each subgraph `.dgr` (turned with
  the main region) runs the whole pipeline (offsets, existence rolls, layout, tile pass, fill,
  de-repetition) in a window of the main map at that rectangle (`0x141f9e2b0`). A subgraph's own
  `graph` nodes are generated into the same map (origins relative to the subgraph's grid), **queued
  behind the subgraphs already waiting** (a FIFO over the main graph's list: `_TheForsakenSon.dgr`'s
  nested `_boss.dgr` is generated after `_CaptainRoth.dgr`); `POE_SUB_DEPTH` restores depth-first.
  Then `0x141ff7b90` runs, per graph from the last subgraph to the main one, the outer fill with
  height repair (`0x141fd6170`, on that graph's rectangle with its master's `OuterGroundType`,
  resolved relative to the master's `.tsi`) and the outer buffer (`0x141fd84e0`; empty for
  `OuterBufferSize 0`). A subgraph's region sits inside its master's `OuterBufferSize` margins in the
  reserved block (G1_12: 10 units × 6 + 1 = 61 tiles + 13 per side = 87 = 3 main units of 29); the
  outer fill and margin strips run per subgraph on that block (`outer_buffer_window`). G1_8's secret
  chamber (`_secretchamber.dgr`, `master_secretchamber.tsi`) is one typed node.
- **Windows share the parent's occupancy**: a subgraph is generated straight into the parent map, so
  the cells around its reserved rectangle that the parent already placed are taken for the subgraph's
  tile pass and fill, including the ring of one cell of slack past the window (`0x141f9e770`: x, y ≥
  −1 and x + w ≤ width + 1, then `0x141d0dac0`). The port builds the subgraph in a window map;
  `TileMap::inherit_cells` copies the parent's taken cells into it and `TileMap::release` clears them
  again before the paste, except where the subgraph's own tile covered them (`outer_taken`).
  Switches `POE_NO_INHERIT=1`, `POE_NO_OUTER_TAKEN`; debug `POE_DBG_WIN=1`.
- **Slot alignment**: a subgraph smaller or larger than its reserved slot keeps the slot corner its
  unturned top-left corner turns to: with `(cx, cy) = orient_cell(region orientation, 2, 2, 0, 0)` the
  origin moves by `slot − size` on x when `cx = 1` and on y when `cy = 1` (`.dgr`: units × (unit −
  overlap) + overlap plus the master's margins; `.tgr`: its tile size). Port: `generate_dungeon`
  (`POE_NO_SUB_ALIGN`, debug `POE_SUB_SHIFT`, `POE_SUB_SHIFT_TGR`).
- **`StoreyHeight` by region** (`0x141ffdfe0`): each tile corner cell with a non-zero height is scaled
  (whole tile, `0x141d0b8a0`) by the `StoreyHeight` (master `+0x14a`) of the last region record whose
  rectangle (`+0x40` origin, `+0x48` size; main first, then the subgraphs' reserved blocks in the
  final map) holds it (`0x141d02ee0`), else the main graph's: not by the graph that placed the cell
  (`finish_dungeon` `regions`; `POE_OLD_OWNER`, `POE_NO_SPILL_OWNER`).
- **`FileGroups` subgraphs** (`0x1420ae150`, `dungeon.rs` `FileGroups`): the master's `FileGroups`
  `.fgp` lists a group name line (no `.`) then files (relative to the `.fgp` directory unless they
  start with `Metadata/`); a `graph` node whose first tag is not a `.dgr`/`.tgr` draws `below(count)`,
  and when the group gave files before, draws again `below(unused)` among the unused ones; the pick is
  recorded and replaces the tag.
- **`.tgr` subgraphs inside a `.dgr`** (`area.rs` `build_tgr`; `generate_dungeon` runs it for a
  FileGroups pick that is a `.tgr`; example `tgr_solo`): the subgraph runs the whole outdoor pipeline
  in a window of the parent map (its corners start as the parent's). The unwalkable marking and the
  enclosed-fill marking (`0x141fe1150`) are skipped; the outer fill and the outer buffer of the
  window run later, last subgraph first (`outer_buffer_window`); pasted pieces (`TileMap::paste`)
  have no tile of the parent's set, so the outer strips read their edges from the headers loaded by
  `preload_headers` (`piece_tdt`). **Paste also merges the subgraph's `.gt` flag table and edge flag
  table into the parent map** (the client's tables are global); otherwise the left strip sees ground
  `None` on pasted tiles.
- **Unique tags**: a tag `uniqueA<n>` takes its candidates from a history shared by all graphs of the
  job (main graph and subgraphs, cleared per area; `area.rs` `LETTER_HISTORY`): the first node of
  letter `A` draws, the following ones of the same letter reuse the earlier pick's slot.
- **Sub-seed**: world-map panels draw no sub-seed (`0x141ff9270`): the `below(0xffffffff)` before the
  topology index is skipped when the area kind (`+0x1b4`) is `0x21` (G1..G4, G6 world maps;
  TN_WorldMap has 0x23 and still draws); the sub-seed then comes from the caller's seed word.
- **World maps: `ForceOuterGT`** (`.tsi`, parsed in `FUN_142928820` `0x142929f8c`; also
  `DoNotFillOutside` `0x14292a149`): the outer buffer ring is not tiled by strips (no edge tiles, no
  draws): every empty margin cell takes the outer ground's first fill tile at height 0
  (`black_nofog.tdt`, fill group `BlackInsideWall` of `fill_tiles.gft`; `outer_buffer.rs`).
- **Plugins and extra jobs.** `ShipPlugin` (`TerrainPlugins` row 14 on `WorldAreas.TerrainPlugins`:
  G4_1_1, G4_2_1, G4_3_1, G4_7, G4_9_, G4_11_1a/b, G4_13, G4_14): its hook `0x141f03dc0` (vtable slot
  4) calls `0x141ff99e0` → `0x141ff8b60` for `G4_ship`: right after the main job's
  `below(0xffffffff)` it draws `below(topology count)` and `below(0x348)` (orientation mask pick),
  then the ship graph (`ship_subscene.dgr`, one 22x22 room, its own StoreyHeight 24) is generated
  after the main graph's subgraphs and before any outer fill (its own node offsets, prune, tile pass,
  fill), finished and appended afterwards (`area.rs` `append_job`, `append_jobs`, `extra_job`;
  `POE_OLD_APPEND`). Extra jobs sit in one strip beside the finished map: right of it when width ≥
  height (x = width + 1, y = 0), else below it (x = 0, y = height + 1), one cell apart, always
  advancing along x inside the strip (G4_13 orientation 2: 109 + 1 + 22 + 1 + 69 = 202 × 94;
  orientation 3: 94 × (109 + 1 + 85) = 195 with the ship at (0, 110) and Kalguur at (23, 110)). G4_13
  gets a third job after the ship, `ExpeditionSubArea_Kalguur_Act4` (`0x141efd040` adds it for the
  area whose id hashes to 0x1c03): the client draws `below(topology count)` and `below(0x348)` twice
  (traces `141ff8a5a`, `141ff8ad9`), ship first; the abyss (`Abyss_FILL`) region right of the ship is
  this job. `UltimatumPlugin` (G3_10): its graph hook `0x141f101e0` rebuilds the graph (entrance, the
  trial's chosen rooms, end, `exit_ruin`, the two trial master graphs); the `.dgr` is that graph
  with no trial rooms. Below area level 75 (area `+0xbc`; G3_10 is 38) the end node's type is
  `end_lowlevel` (rooms `passage_end_0N_lowlevel.arm`, whose exit slot is `exit_locked`:
  `ChaosTreasureRoomExit_01_locked.tdt`) joined only to `entrance2`; from 75 it is `end` with
  `teleport1` and `entrance2` (`POE_NO_ULTIMATUM`).

## Heights and the outer fill

- Outer fill (`0x141fd6170`): its height-repair argument is generator byte `+8` (`0x141ff7b90`),
  zeroed by `TerrainGen_Construct` and ORed by `0x141ff0770` after each dungeon graph's tile pass
  with byte `+0x20` of the graph's map view (`local_648`, `0x141f9e2b0`). That byte is set by every
  write of a non-zero height: `0x141f9e460` (place, height argument), `0x142097e30` (ground-only
  slots, unset corners), `0x142098550` (room slots). Flat graphs (every tile and corner at height 0)
  place the outer fill plain in row order. Port: `TileMap::raised`, `Built::raised`, `repair_flag`
  (`POE_NO_REPAIR_ALL`, `POE_REPAIR_ALL`). Neither "a graph has edges" nor "any non-zero height in the
  map" is the rule. The rounds also need the outer ground's `.gt` flag 1 clear and master `+0x161`
  clear ([tgr.md](tgr.md#heights-and-the-outer-fill)).
- `OuterFillHeightOverride <n>` (`.tsi`; parser flag at master `+0x161`, value `+0x153`): the outer
  fill skips the height repair and places every grid tile plain at height n. `OverrideSpawns`
  (parser stack +0x310/+0x311: 1/1 `Dungeon`, 2/2 `Outdoor`; `OuterFillHeightOverride` to +0x32b with
  a set flag at +0x31d; `ExtendActivationDistance client|server|both` to +0x325/+0x324) also places
  plain at height 0, but only with `DefaultKillZone` in the same master (MapCreek, P3_1 have both;
  MapExcavation has `OverrideSpawns` alone and repairs). The store of the `OverrideSpawns` flag is not
  located: the rule is inferred from 17 traced areas (`Master::outer_fill_height`; `POE_OVSP_ANY=1`
  restores the old rule).
- Alignment: the outer fill aligns a 3×3 tile one cell outside when the region's corner and size are
  1 mod 3, in whole-map coordinates (`view x0 % 3 == 1`, `y0 % 3 == 1`, `w % 3 == 1`, `h % 3 == 1` on
  the view `0x141f9e2b0` builds in the final map): a subgraph window's region (Chayula: window region
  7,7 = map 11,131) is not aligned although its window-local corner is (`fill_black`'s `at` = window
  origin + main margins).
- Levelling (`0x141fd7340`): `0x141fd6170` lists every ready cell after `0x141fd6b10`, which places
  nothing when the tile does not fit; the levelling step levels such an empty cell as a 1×1 square,
  setting its record height and its four corners, so the raise travels on (`fill_black` rounds,
  `POE_NO_EMPTY_LEVEL`). Client hook additions: lattice `round` (whole map, only when it changed) and
  `afterround` dumps; `round_corner` (site `0x141fd736b` inside `0x141fd7340`: `x y n h0..h3`, result
  = the cell's current height).
- Strip fill fallback (`0x141fdbebd`, in the row strips of `0x141fd84e0`): with an outer ground, a
  stretch whose first ground is plain but whose fill tile has no ground of its own (tile data
  `+0x62`; `Blank.tdt` from the `default` group of a `.gft` without the ground's group) or a
  non-plain one takes the outer ground's fill tile (`[rbp+0x280]`, `Outskirts_Wall_Fill_Large_01`).
  Port: `Pass::fill_tile` (`POE_STRIP_NO_OUTER`). Trace lines `strip_grounds`.

## Reference notes

- Ruled out: copying the node's fixed-axes flags (`+0x8b`/`+0x8c`, `.tgr` node values 9 and 10) to
  the nodes the virtual junction (`0x1420c6060`) and the splits make: the client builds the
  junction's new nodes with `0x141d1c8d0` (flag bytes 0, copies only `+0x48`); a node clone
  (`0x141d1aeb0`) used when a subgraph is generated (`0x141ff2dd0`) does copy them. Tile nodes of
  `G3_1` topology 1 must not be pushed, a rule not found.
- Ruled out: a merged edge that "weighs 0" (the cause was slot order); a tagged blank room owning its
  ground (`POE_OWN_TAG`) and "the `.arm`'s second bool" (`POE_ARM_OWN`) as room data `+10`; filler
  rooms from all of an area's room sets (see the size map); height 0 for every door-less exit.
- Tools: `lay_cmp <export dir> [--map] [--units margin,step,size] [--at x,y,r] [--lat x0,y0,x1,y1]
  [--margin M] [--dy N]` (cell/cluster diff, placement order against the export's
  `generator_trace.tsv`, lattice heights), `POE_DUMP_ROOMS=1` (rooms after the layout, compared with
  the trace's `derepeat_room` lines). `POE_FORCED_BUDGET=60` for `forced_verify` under many cold
  threads (`HUNG <area> <seed> <topology> <orientation>` marks the "eight hung" abort).

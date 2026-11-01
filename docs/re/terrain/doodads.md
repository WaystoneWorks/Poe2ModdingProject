# Doodads and the collision grid (0.5.5e Hotfix 1)

The two passes that run after the tile layout: the doodad pass (which objects the rooms bring, the
doodad hash) and the collision grid (the four 4-bit cell layers the server needs for walkability).
Port: `modules/server/crates/poe-world/src/{doodads,collision,tdt}.rs`; checks: the examples
`check_doodads`, `check_grids`, `forced_verify` ([README.md](README.md#tools)). Status:
[../../status/terrain.md](../../status/terrain.md). Reference data: the DLL area exports
(`doodads.tsv`, `grids.bin`) in `dumps/0.5.5e.hotfix1/terrain/area-exports/`.

## Doodad pass

Order in `TerrainGen_Run` (see [README.md](README.md#phases-terraingen_run-in-order)): after the
tile layout (and its random draws), `TerrainGen_Doodads` `0x141ff56d0` walks every region's room
placements (the list the de-repetition pass also uses, region +0x58, 0x38-byte entries) and calls
`TerrainGen_TileDoodads` `0x141ff3490` for each. This pass places the doodads of rooms (`.arm`);
the tiles' own objects come from the tile-object pass ([below](#what-decides-whether-an-object-exists)).

1. **Cell and angle** (`0x141fe7a50`). An `.arm` doodad entry has a cell `(ex, ey)` inside the
   room, an angle (`radians1`), a scale, a flip flag, an object type (`stub`, e.g.
   `Metadata/MiscellaneousObjects/Doodad`) and an `.ao` path. The placed cell is the entry cell
   turned by the placement's orientation `o` within the room's `w x h` tiles, plus the placement
   corner times 23. The turn is the table at `0x142f02118` (three bytes per orientation, 9 rows),
   which picks x and y from `(w*23 - ex - 1, ex, h*23 - ey - 1, ey)`: `turn_cell`. Angle:
   orientations 4..7 (mirrored) negate it (`2pi - a`), each quarter turn (`o & 3`) adds `pi/2`,
   wrapped into `0..=2pi`: `turn_angle`.
2. **AOSet pick** (`0x141fe76a0`, orientation pick `0x1421c3f40`). The `.ao` file is looked up
   (component `AOSet` merged over the `extends` chain, base first; `FUN_141d5af20` finds the
   component). While the file has `ao = "<weight> <path>"` choices and no `fixed_ao`, one
   `TerrainRng_Below(total weight)` draw picks the next file (`0x141fe7737`); the path `null` drops
   the entry (no object). A file without `AOSet`, or with `fixed_ao` entries, ends the chain (the
   leaf); then the last `AOSet` seen draws, in this order and only when it uses the feature:
   - rotation, when `random_rotation` (range `-pi..pi` without min/max) or a min/max range is set:
     `below(0x200)`, angle `(max - min) * r / 512 + min`;
   - orientation, when `random_orientation` / `random_flip` set the allowed mask at +0x5c (`0xff` /
     `0x11`): `below(0x348)`, then `orientation_pick(mask, u)` (mask 0 or 0xff: `u & 7`, else the
     `u % n`th allowed bit); the angle is turned by it and orientations 4..7 mirror;
   - scale, when the range is not `1..1`: `below(0x200)`, `(max - min) * u / 512 + min`;
   - translation, when `random_translate_radius > 0`: `below(0x200)` for the distance
     `sqrt(r^2 * u / 512)` and `below(0x200)` for the angle `u / 512 * 2pi`; the offset is
     `floor(d*sin + 0.5), floor(-d*cos + 0.5)`.

   The pick adds its angle and offset to the entry, mirrors the hull (`flip = placement mirrored
   XOR pick mirrored XOR entry flip`) and multiplies the scale. The draws continue the layout's MT
   stream in placement order.
3. **Hash filter** (`+0x2d0` / `+0x2d4` of the object type's data, `0x141ff3490`). An entry adds
   `y + Murmur2_Utf16(.ao path) + (x << 16)` (cells, the path as the room names it, not the leaf)
   to the doodad hash ([README.md](README.md#hashes)) when its object type exists (it has an `.ot`
   of its own; a path with only an `.ao` extending another type is none; e.g. G1_3's
   `Metadata/Chests/SirenEggs/SirenEgg_02` extends `Metadata/Parent`) and the type's merged
   `BaseEvents` sets neither `server_only` nor `client_only` and no `league_category` (a type with
   one counts only when it equals the area's league category, 0 for areas without a league mechanic
   rolled): `type_counts`. The angle is not in the hash.
4. **Static flag.** Only types whose `Positioned.static` is true stamp a hull into the collision
   grid (`type_solid`); the others (monsters, markers) do not. A kind counts, stamps a hull and is
   placed only if it has an `.ot` of its own.

Type flags are read once per process; reading them through `GameData` takes its bundle lock on every
layout and makes batch threads run one at a time.

## Collision grid (`0x141d0e770`)

The terrain object holds four 4-bit cell layers (terrain `+0xd0`, `+0xe8`, `+0x100`, `+0x118`, one
nibble per cell, 23 x 23 cells per tile; exported as `grids.bin`, the `PWG1` format of
`poe_game::grid::Grid`: magic, cells x, cells y, bytes per row, layer count, then each layer 4 bits
per cell, low nibble first). Every layer starts at 5 ("open"). A cell value is a clearance: 0
blocked, 1..4 distance to the nearest blocked cell, 5 open. Layer 0 is the walkability layer (the
server's `walkable`: value above 0), layer 1 the projectile layer; layers 2 and 3 stay at 5 in every
export checked.

`collision::build(map, files, doodads)` does what `0x141d0e770` does, in two stages:

**Tiles.** Row by row over the tile records (`ty` outer):
- the record's sub-tile (`.tdt` sub-tile at the record's index; `SubTile.flags`, `b1`, the LZ4
  list) gives a plane of cell codes (low nibble layer 0, high nibble layer 1) over
  `x0..x0+w, y0..y0+h` of the 23 x 23 tile (planes may reach 4 cells past a side: flag 0x20 up,
  0x40 right, 0x80 down, `b1` bit 0 left);
- flags 1 and 2 both set: the **default plane** (`0x141d05050` + `0x142917610`): all cells 0 on a
  layer whose blocked bit is set (flag 8 layer 0, flag 0x10 layer 1), else open, with 1..4 ramps in
  the margins that are present;
- otherwise plane number `i` of the sub-tile's LZ4 stack (`0x141d051c0`), where `i` is the first
  entry of the `.tdt` hull-plane masks (data +0x173; mask bit per orientation, 0 = all) that serves
  the record's orientation;
- the plane is turned by the orientation (the same `0x142f02118` table, on a 23-cell tile) and
  written as the minimum with what is there (5 counts as unset);
- the sub-tile flags decide what is written: flag 2 clear: with flag 1 clear and fewer than 4
  unwalkable corners both layers take the plane, else layer 0 is blocked over the tile if flag 8 is
  set or all four corners are unwalkable, and only layer 1 takes the plane; flag 2 set: with flag
  0x10 both layers are blocked over the tile, else (flag 1 clear, fewer than 4 unwalkable corners)
  layer 0 takes the plane, else layer 0 is blocked if flag 8 or all four corners are unwalkable;
- a record without a sub-tile blocks both layers over the whole tile;
- **blocking a whole tile** (`0x141d0f610`, `0x141d0fbe0`) also reaches 4 cells into each of the
  four neighbours that has a sub-tile open on that layer, with the default plane's 1..4 ramp;
- a corner is **unwalkable** when it lies outside the map or its lattice flags (the corner-lattice
  of [shared-passes.md](shared-passes.md#corner-lattice)) have bit 8 set.

**Doodad hulls** (`0x141d10650`). Each placed static object stamps the `Hull` block of its leaf
`.ao` (merged over `extends`, base first). A block is a list of sections (`section = ...` starts a
new one) of `walk_tri x0 y0 x1 y1 x2 y2`, `proj_tri ...`, `walk_circle x y r` and `proj_circle x y
r`. The transform is rotation by the doodad angle times the scale, mirrored in x when `flip`. Walk
shapes go to layer 0, projectile shapes to layers 0 and 1 (`stamp_hull`):
- a triangle (`0x141d10d60`) zeroes the cells it covers (the 4-bit fixed-point scan of
  `0x141d1d3d0` / `0x141d18ee0` with the top-left rule), zeroes each corner and stamps the 48-entry
  corner kernel `0x1434bfc30` (values 1..4 around the corner), and for each edge stamps the distance
  (rounded perpendicular distance, up to 4 cells) over two triangles on the outer side of the edge;
- a circle (`0x141d194f0`) lowers every cell within `r + 4` to `ceil(distance - r)`;
- all writes take the minimum (5 counts as unset; 0 always writes), so doodad order does not matter.

## What decides whether an object exists

Found with per-phase grid snapshots of the client (`POE_HOOK_GRID_PHASES`, below). The rules run in
this order for each entry, after the `AOSet` pick and, for room doodads, after the hash:

1. **Side and league filter** (`0x141ff48e0`, generator vtable `+0xa0`). A type with a side flag
   (`+0x2d0`: 1 `server_only`, 2 `client_only`) exists only on its own side: server mode (globals
   `0x1445c995c` or `0x14458c74c` set) keeps `server_only` and drops `client_only`, a client process
   does the opposite. A `league_category` must equal the area's. Port: `Doodad::exists(Side)`;
   `collision::build` takes the side. **The batch exports run in a client process, so they show
   client-side filtering**; the instance server builds `Side::Server`.
2. **Angle rules** (`0x141fe8860`, `0x141fe86f0`). With `a = angle - 0.7603982` (+2pi when
   negative), `AntiTallWallDoodad` is dropped for `a >= 3.1915927`, the upper-tile types
   (`TileUpperDoodad`, `TileUpperDoodadNoOverlap`, `TileUpperDoodad_ExtendDistance`, the two
   `*_extend_tallwall` types) for `a < 3.1915927`. Port: `dropped_by_type`.
3. **Suppressed by a later room** (rooms only, `0x141ff3490`). A type of the 15-type set of
   `0x141fe8420` whose tile lies inside a later placement of the region with flag `+0x1c & 2` is not
   created. That flag is `+SuppressUnderlyingDoodads` of the overlay's `.toy` entry or pass line
   (`Overlays::suppresses`). The doodad still counts for the hash.
4. **No-overlap types** (`0x141fe8040`: `DoodadNoOverlap`, `TileUpperDoodadNoOverlap`;
   `DoodadNoOverlap3` is the listed one) are deferred (`0x141ff4a50`) to `doodads_post`
   (`0x141ff4cd0`, `doodads::no_overlap`): per group in descending key order (rooms key 0, tile
   objects the `.tdt` object group), `below(n)`, a Fisher-Yates shuffle (`uniform(n - k)`, swapping k
   with k + draw), then placed unless a placed cell lies in its 3 x 3 cells. The listed type comes
   last, in order, and also needs no other listed object in its 3 x 3 cells.

The type hashes of these sets are the `ObjectHASH32` column of `Data/Balance/MiscObjects.dat`
(`0x140f60fc0`).

**Tile-object pass** (`0x141ff4030`, vtable `+0x28`, after the doodad pass; `doodads::tile_objects`).
Row by row over tile records that are a tile's corner: the objects of the `.tmd` beside the `.tgt`
(tile data `+0x178`), then of the `.tdt`'s `tmd` (`+0x180`), each through `0x141ff43d0`: the `AOSet`
pick continues the doodad pass's RNG stream, then the entry's orientation mask (trailing `I R90 R180
R270 FI FR90 FR180 FR270`, entry `+0x1e`), the cell turned within the tile's size. They are not in
the hash. A `.tmd` line is `x y flag [wx wy] z angle q0 q1 q2 q3 flip scale "ao" "name" "fmt" "type"
n [orientations]`; the flag says whether the world `x y` is present. Not ported: the
`alttiles/<env>/<env>_<name>.tmd` variant of the art list (`0x141d11c50`) and the per-sub-tile
objects of tiles with data `+0x16d & 2` (`0x141d07630`).

**`.tdt` fields:** the body's first u16 is tile data `+0x16c` (`Tdt::body_flags`); after the `tmd`
string come a string and the object group byte (`+0x170`, sink `+0x58`). Tile data `+0x10` is the
feature string's length (`0x141d161c0`).

## Unwalkable corners

`0x141ff7b90` (called from `TerrainGen_Layout`) runs, per region: outer fill and outer buffer, then
`0x141fe1150` on the region's rectangle if the master's `RoomOcclusion` (`+0x166`) is clear (regions
past the main count only with `+0x164`), and `0x141fe1020` (the map border). `0x141fe1150` runs for
`.tgr` graphs and dungeons alike (`finish_dungeon` runs it on the region, which `regions.tsv` shows
is the whole buffered map) and returns at once for area kinds 0x20 and 0x21 (world-map panels).

The tail of `0x141fe1150`: the enclosed-fill test requires an **empty feature**, not "not
inheriting" (`mark_enclosed_fills`); with the master's `OuterGroundIsOutside` (`+0x165`) and an
`OuterGroundType` (`+0x230`), tiles with body flag 0x40, first sub-tile flag 8, all corner grounds
the outer ground and only empty or wildcard edges get their footprint marked
(`mark_outside_tiles`). Master offsets: `DisableDoors` is `+0x167`, so the keys parsed by
`0x142928820` line up as `OuterGroundIsOutside` `+0x165`, `RoomOcclusion` `+0x166`.

## Tools and checks

- `check_doodads <export or run dirs> [--only forced.tsv]`: generates each export's job and compares
  the doodad set `(x, y, path)` and the hash with `doodads.tsv` and `meta.txt` (`--kinds`: per
  object type how many the client counted; `--verbose`: first differences).
- `check_grids <dirs> [--only F] [--blame] [--dump DIR]`: compares the four layers with `grids.bin`
  (differing cells per layer, bounding box of the first difference; `--blame` attributes cells to
  the tile or doodad that wrote them, with `WORST` lines for the tiles with most differing cells;
  `--dump` writes the port's `PWG1` bytes). Reports `LAYOUT` when the tile or doodad hash already
  differs.
- `check_lattice <dirs> [--list N]`: compares the port's corner flags with `lattice.bin`
  (`LATTICE_MAP=1` draws the differences, `LATTICE_COL=x`, `LATTICE_ROW=y` print grounds and flags).
- `lattice_probe <export> x0 y0 x1 y1`: the corner lattice around a tile range (ground letter and
  flags per corner).
- `forced_verify` reports `doodads match|differ` after the tile hash.
- Batch exports also write `entities.tsv` (objects with cells), `tiledata.tsv` (tile data
  `+0x16c..`), `lattice.bin` (final corners), `regions.tsv` (region rectangles and master flags).
  `POE_HOOK_GRID_PHASES=<Z: dir>` with `POE_HOOK_GEN_TRACE=1` (one thread) writes the grids at each
  generator phase.
- Debug variables: `POE_DBG_DOODADS`, `POE_DBG_DOODAD_ORDER` (picks and draws), `POE_DBG_HULLS`,
  `POE_DBG_GRID_TILE=x,y` (one tile's flags, corners and plane), `POE_DBG_NEAR=x,y,r` (the port's
  doodads near a cell), `POE_DBG_TILEONLY` (the grid after the tile stage), `POE_DBG_CELL=x,y,l` (the
  object that lowers a cell), `POE_DBG_FLOOD=x|all`, `POE_DBG_TMD_DRAWS`, `POE_DBG_TMD_LIST`,
  `POE_NO_TILE_OBJECTS`, `POE_NO_COVERS`, `POE_NO_ANGLE_DROP`, `POE_NO_DGR_UNWALKABLE`.

## Server use

`[terrain] generated_grid` (default off) makes the instance server build the grid with the port
instead of using the grid the client uploaded or the layout cache holds, but only when the generated
tile hash equals the client's; otherwise it warns and keeps the uploaded grid. `poe-world` depends
neither on `poe-game` nor on `poe-config`; the instance server is the adapter
(`poe_world::collision::build(..).pwg1()` into `poe_game::grid::Grid::parse`), see
[../../architecture/instance-world.md](../../architecture/instance-world.md#terrain-grid-sources).

## Results and open points

### Results

- Doodads: every tile-matching export equals `doodads.tsv` (set, hash, draws) except the
  `MapVaalVault` angle case below, and every tile match of the 50-seed batch (72,718 of 218,705
  client layouts) matches the client's doodad hash.
- Collision grid: 4,864 of 5,237 client grid exports on disk equal `grids.bin` (a sample biased
  toward earlier failures), 367 differ, 6 differ in the layout already. Layers 2 and 3 always agree.
  Largest open families: `G2_5_1` (81), `G2_5_2` (38), `MapVaalCity` (32), `G2_2` (23),
  `MapPlantation` (18), `G3_8` (16), `G3_14` (15), `G3_1` (15), `MapRazedFields` (14).

### Open: `MapRazedFields`

1,386 corners are flagged by the client only, a connected network around `woods_trim` and road
grounds (`check_lattice`). They look like the impassable flood entering at (81, 94), but the same
`EdgeInTheWay` (`0x141fe0990`, checked against the disassembly) stops at the first tile boundary in
the port, and the strip tiles are placed before the pass runs (trace `tdiff`), so what lets the
client through is not known.

### Open: grid families

All differ in layer 0 unless noted. Tools: `check_grids --blame`, `POE_DBG_GRID_TILE`,
`lattice_probe`, `POE_DBG_NEAR`.

| Family | Cells | What differs | Findings |
|---|---|---|---|
| `MapSlash` | 771 each | A pocket of three by three tiles around a `CvSM_01.tdt` tile is open in the port and fully blocked in the client | Forcing all nine tiles to four unwalkable corners (a 4 x 4 block of lattice corners with flag 8, so every `clear()` margin falls where the client has it) reproduces `grids.bin` exactly, so the cause is the lattice, not the planes. The pocket's inner corners have no ground in the port's lattice (`-3`), their neighbours are mud. `0x141fe0cc0` (ported, `lattice::mark_enclosed_fills`) is not the cause: it needs a uniform edgeless tile whose outline is already flagged. Suspects: the tile-set option `+0x165` block (tiles with `+0x16c & 0x40` whose four corner grounds equal the tile-set's `+0x230`, which flags the whole footprint), or flood paths blocked by the stubbed `sealed_inside` (tile data `+0x16f` bit 0, read by `0x141fe2500` and `0x141fe1f70` through the record at the corner's own index) |
| `MapSeepage`, `MapUberBoss_IronCitadel` (partly) | 250 to 690 | The port blocks more than the client: whole tiles cleared with the margin ramp, or a wall plane 4 cells longer | The opposite direction to `MapSlash`: the port flags corners the client does not, which fits the `sealed_inside` stub (a sealed tile stops the flood). The `.tdt` field behind `+0x16f` is not mapped (the flag word of `0x142915630` is set bit by bit through a vtable slot `+0x40`) |
| `MapCrimsonShores` | 400 to 1,800 | A circular blob of radius about 10 with the 1..4 clearance ramp is blocked in the client, absent in the port, centred in a `fill_01.tdt` tile (3 x 3, flags 0x03, plane-less) | Not a tile plane and not one of the room doodads. Probably a generator object that is not in `doodads.tsv` (an entity from tile data `+0x1b8`, or a scatter object); an export with `entities.tsv` of a failing layout decides |
| `MapMonument`, `MapFortress`, `G4_5_2`, `G2_10_1`, `MapReservoir` | 150 to 4,900 | Feature tiles (`PrecursorGroundAnchor_*`, `fortress_boss_01`, `Warden_Office`, `JamanraRitualSite_02`) and fill tiles | Same two suspects (unported unwalkable-corner rules, objects outside `doodads.tsv`) |
| `MapVaalVault` | 53 | Two doodads (`SunkenPillar_set.ao`, `random_orientation`, `AOSet` with one choice) have the angle off by pi/2 (ours 3pi and 2.5pi after the pick, the client 2.5pi and 2pi; the seed 35611400 topology 1 orientation 0 layout) | `0x1421c3f40` is ported as decompiled (`mask 0xff`: `u & 7`) and the picks of all other sets (`random_flip`, 1,879 doodads) agree, so the draw `u` (99 and 314, `below(0x348)`) or the mapping from the picked orientation to the angle differs for the full eight-way case. A client trace of `MapVaalVault 35611400 1 0` shows the real draws |

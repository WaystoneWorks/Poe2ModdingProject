# Doodads and the collision grid (0.5.5f)

The two passes that run after the tile layout: the doodad pass (which objects the rooms bring, the
doodad hash) and the collision grid (the four 4-bit cell layers the server needs for walkability).
Port: `modules/server/crates/poe-world/src/{doodads,collision,tdt}.rs`; checks: the examples
`check_doodads`, `check_grids`, `forced_verify` ([README.md](README.md#tools)). Status:
[../../status/terrain.md](../../status/terrain.md). Reference data: the DLL area exports
(`doodads.tsv`, `grids.bin`) in `dumps/0.5.5f/terrain/area-exports/`.

## Doodad pass

Order in `TerrainGen_Run` (see [README.md](README.md#phases-terraingen_run-in-order)): after the
tile layout (and its random draws), `TerrainGen_Doodads` `0x142003d00` walks every region's room
placements (the list the de-repetition pass also uses, region +0x58, 0x38-byte entries) and calls
`TerrainGen_TileDoodads` `0x142001ac0` for each. This pass places the doodads of rooms (`.arm`);
the tiles' own objects come from the tile-object pass ([below](#what-decides-whether-an-object-exists)).

The list grows as rooms are placed: the graph's rooms, pre-placed (league, hosted) rooms, overlay
phase 1 (each room, then its refill rooms), the fill pass, overlay phase 2 (`Overlays::placements`).
Inferred from the client's generator entity ids (`entities.tsv`), not read from the list's code, and
confirmed by the full `grid50` result. The order matters only when an `AOSet` draws: most sets draw the same
number of times and hash the set's path, so a wrong order leaves the doodad hash intact and swaps
leaves (`BlackFernTrunk_set.ao`: other trunks' hulls, ramp cells one off). A leaf mismatch looks like
a hull-transform bug; `circfit.py` over each leaf of the set tells them apart.

1. **Cell and angle** (`0x141ff6080`). An `.arm` doodad entry has a cell `(ex, ey)` inside the
   room, an angle (`radians1`), a scale, a flip flag, an object type (`stub`, e.g.
   `Metadata/MiscellaneousObjects/Doodad`) and an `.ao` path. The placed cell is the entry cell
   turned by the placement's orientation `o` within the room's `w x h` tiles, plus the placement
   corner times 23. The turn is the table at `0x142f15238` (three bytes per orientation, 9 rows),
   which picks x and y from `(w*23 - ex - 1, ex, h*23 - ey - 1, ey)`: `turn_cell`. Angle:
   orientations 4..7 (mirrored) negate it (`2pi - a`), each quarter turn (`o & 3`) adds `pi/2`,
   wrapped into `0..=2pi`: `turn_angle`.
2. **AOSet pick** (`0x141ff5cd0`, orientation pick `0x1421d3dc0`). The `.ao` file is looked up
   (component `AOSet` merged over the `extends` chain, base first; `FUN_141d67e80` finds the
   component). While the file has `ao = "<weight> <path>"` choices and no `fixed_ao`, one
   `TerrainRng_Below(total weight)` draw picks the next file (`0x141ff5d67`); the path `null` drops
   the entry (no object). A file without `AOSet`, or with `fixed_ao` entries, ends the chain (the
   leaf); then the last `AOSet` seen draws, in this order and only when it uses the feature:
   - rotation, when `random_rotation` (range `-pi..pi` without min/max) or a min/max range is set:
     `below(0x200)`, angle `(max - min) * r / 512 + min`;
   - orientation, when `random_orientation` / `random_flip` set the allowed mask at +0x5c (`0xff` /
     `0x11`): `below(0x348)`, then `orientation_pick(mask, u)` (mask 0 or 0xff: `u & 7`, else the
     `u % n`th allowed bit); the angle is turned by it and orientations 4..7 mirror;
     `random_orientation` is `true` (mask `0xff`) or a list of names (`"I R180 FI FR180"`, e.g.
     `street_short_st_set.ao` in `G3_8`): one bit per name, `I R90 R180 R270 FI FR90 FR180 FR270` =
     bits 0..7, that list is `0x55` (`doodads::orientation_names` in `parse_ao`). The pick takes the
     `(u mod count)`th allowed orientation (`0x1421d3dc0`). A client trace of `G3_8 30319231 1 0`
     (`dumps/0.5.5f/terrain/batch/g38trace`) equals the doodad pass and all 112 tile-object
     draws; the tile-object pass starts at MT index 842, the raw value of the server-only scatter's
     first draw (the save/restore);
   - scale, when the range is not `1..1`: `below(0x200)`, `(max - min) * u / 512 + min`;
   - translation, when `random_translate_radius > 0`: `below(0x200)` for the distance
     `sqrt(r^2 * u / 512)` and `below(0x200)` for the angle `u / 512 * 2pi`; the offset is
     `floor(d*sin + 0.5), floor(-d*cos + 0.5)`.

   The pick adds its angle and offset to the entry, mirrors the hull (`flip = placement mirrored
   XOR pick mirrored XOR entry flip`) and multiplies the scale. The draws continue the layout's MT
   stream in placement order.
3. **Hash filter** (`+0x2d0` / `+0x2d4` of the object type's data, `0x142001ac0`). An entry adds
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

## Collision grid (`0x141d1b1a0`)

The terrain object holds four 4-bit cell layers (terrain `+0xd0`, `+0xe8`, `+0x100`, `+0x118`, one
nibble per cell, 23 x 23 cells per tile; exported as `grids.bin`, the `PWG1` format of
`poe_game::grid::Grid`: magic, cells x, cells y, bytes per row, layer count, then each layer 4 bits
per cell, low nibble first). Every layer starts at 5 ("open"). A cell value is a clearance: 0
blocked, 1..4 distance to the nearest blocked cell, 5 open. Layer 0 is the walkability layer (the
server's `walkable`: value above 0), layer 1 the projectile layer; layers 2 and 3 stay at 5 in every
export checked.

`collision::build(map, files, doodads)` does what `0x141d1b1a0` does, in two stages:

**Tiles.** Row by row over the tile records (`ty` outer):
- the record's sub-tile (`.tdt` sub-tile at the record's index; `SubTile.flags`, `b1`, the LZ4
  list) gives a plane of cell codes (low nibble layer 0, high nibble layer 1) over
  `x0..x0+w, y0..y0+h` of the 23 x 23 tile (planes may reach 4 cells past a side: flag 0x20 up,
  0x40 right, 0x80 down, `b1` bit 0 left);
- flags 1 and 2 both set: the **default plane** (`0x141d11a80` + `0x142929890`): all cells 0 on a
  layer whose blocked bit is set (flag 8 layer 0, flag 0x10 layer 1), else open, with 1..4 ramps in
  the margins that are present;
- otherwise plane number `i` of the sub-tile's LZ4 stack (`0x141d11bf0`), where `i` is the first
  entry of the `.tdt` hull-plane masks (data +0x173; mask bit per orientation, 0 = all) that serves
  the record's orientation;
- the plane is turned by the orientation (the same `0x142f15238` table, on a 23-cell tile) and
  written as the minimum with what is there (5 counts as unset);
- the sub-tile flags decide what is written: flag 2 clear: with flag 1 clear and fewer than 4
  unwalkable corners both layers take the plane, else layer 0 is blocked over the tile if flag 8 is
  set or all four corners are unwalkable, and only layer 1 takes the plane; flag 2 set: with flag
  0x10 both layers are blocked over the tile, else (flag 1 clear, fewer than 4 unwalkable corners)
  layer 0 takes the plane, else layer 0 is blocked if flag 8 or all four corners are unwalkable;
- a record without a sub-tile blocks both layers over the whole tile;
- **blocking a whole tile** (`0x141d1c040`, `0x141d1c610`) also reaches 4 cells into each of the
  four neighbours that has a sub-tile open on that layer, with the default plane's 1..4 ramp;
- a corner is **unwalkable** when it lies outside the map or its lattice flags (the corner-lattice
  of [shared-passes.md](shared-passes.md#corner-lattice)) have bit 8 set.

**Doodad hulls** (`0x141d1d080`). Each placed static object stamps the `Hull` block of its leaf
`.ao` (merged over `extends`, base first). A block is a list of sections (`section = ...` starts a
new one) of `walk_tri x0 y0 x1 y1 x2 y2`, `proj_tri ...`, `walk_circle x y r` and `proj_circle x y
r`. The transform is rotation by the doodad angle times the scale, mirrored in x when `flip`. Walk
shapes go to layer 0, projectile shapes to layers 0 and 1 (`stamp_hull`). Before sin/cos the object angle is wrapped fully into [0, 2pi) (`rem_euclid`, negative angles too); where the client normalises it was not located, the evidence is the grid gate (4,979 -> 4,991 identical). The stamp reads the Positioned component (`0x141d1d080`): angle `+0x44c`, scale `[+0x158]+0x74` times `+0x474`, flip `+0x1e4` bit 4, origin cell `+0x444`; `0x141d25ca0` (triangles) and `0x141d25f20` (circles, cells via `0x141d1de30`) match `stamp_hull`. **Anim-driven hulls:** an `.ao` whose `AnimationController` has `anim_driven_subobject` lines (the breakable fences, `WoodenFenceShort01.ao`) is in the client grid twice, unturned and unmirrored and with its final transform (`AoInfo::anim_driven`; `MapPlantation` 800/800 identical). Unturned alone fails map orientations 1 and 7, the final transform alone 0, 6 and 7. Where the client stamps the unturned copy was not traced (eight callers of `0x141d1d080`). Only subtracting 2pi repeatedly, without wrapping negatives, regressed 8 `G2_5_1`/`MapWaywardIsle` exports. Cause: f32 sin/cos of 4pi or -pi/2 differ from 0 or 3pi/2 at cell edges. A `Hull` block may set `disable_rotation = true`; the key parser `0x141d7b530` stores it at hull `+0x88` (one flag for the whole hull). The port (`collision::parse_hull`, `HullSection::disable_rotation`, `stamp_hull`) stamps such hulls with angle 0 and keeps the mirroring; where the client reads `+0x88` was not traced, and keeping the flip scored 5 more byte-identical exports than dropping it. Example: `SunkenCity/Past_Individual_Doodads/WovenBasket07.ao` (12 x 12 square walk_tri).
- a triangle (`0x141d1d790`) zeroes the cells it covers (the 4-bit fixed-point scan of
  `0x141d29e00` / `0x141d25910` with the top-left rule), zeroes each corner and stamps the 48-entry
  corner kernel `0x1434d3ca0` (values 1..4 around the corner), and for each edge stamps the distance
  (rounded perpendicular distance, up to 4 cells) over two triangles on the outer side of the edge;
- a circle (`0x141d25f20`) lowers every cell within `r + 4` to `ceil(distance - r)`;
- all writes take the minimum (5 counts as unset; 0 always writes), so doodad order does not matter.

## What decides whether an object exists

Found with per-phase grid snapshots of the client (`POE_HOOK_GRID_PHASES`, below). The rules run in
this order for each entry, after the `AOSet` pick and, for room doodads, after the hash:

1. **Side and league filter** (`0x142002f10`, generator vtable `+0xa0`). A type with a side flag
   (`+0x2d0`: 1 `server_only`, 2 `client_only`) exists only on its own side: server mode (globals
   `0x1445e15bd` or `0x1445a4105` set) keeps `server_only` and drops `client_only`, a client process
   does the opposite. A `league_category` must equal the area's. Port: `Doodad::exists(Side)`;
   `collision::build` takes the side. The batch exports filter as the client: `grid50` matches
   `Side::Client` (218,655 identical), although the server-only scatter in `TerrainGen_Doodads`
   (draws `below(w*23)`, `below(h*23)` at `0x1420047f9` / `0x142004806`, guarded by the same two
   globals, RNG saved and restored around it, `0x142cc9840`, 5000 bytes) ran in the batch process trace
   (7,686 pairs). The instance server builds `Side::Client` ([Live grid](#live-grid-and-server-side-objects)).
2. **Angle rules** (`0x141ff6e90`, `0x141ff6d20`). With `a = angle - 0.7603982` (+2pi when
   negative), `AntiTallWallDoodad` is dropped for `a >= 3.1915927`, the upper-tile types
   (`TileUpperDoodad`, `TileUpperDoodadNoOverlap`, `TileUpperDoodad_ExtendDistance`, the two
   `*_extend_tallwall` types) for `a < 3.1915927`. Port: `dropped_by_type`.
3. **Suppressed by a later room** (rooms only, `0x142001ac0`). A type of the 15-type set of
   `0x141ff6a50` whose tile lies inside a later placement of the region with flag `+0x1c & 2` is not
   created. That flag is `+SuppressUnderlyingDoodads` of the overlay's `.toy` entry or pass line
   (`Overlays::suppresses`). The doodad still counts for the hash.
4. **No-overlap types** (`0x141ff6670`: `DoodadNoOverlap`, `TileUpperDoodadNoOverlap`;
   `DoodadNoOverlap3` is the listed one) are deferred (`0x142003080`) to `doodads_post`
   (`0x142003300`, `doodads::no_overlap`). The client runs it twice, each run independent (empty
   placed set, group lists cleared): run 1 for the room doodads at the end of `TerrainGen_Doodads`
   (called from `0x1420054b8`), right after the room-doodad AOSet picks and before the tile-object
   pass draws; run 2 for the tile objects after that pass (from `0x14200d8fc`). The server-only
   scatter between the picks and run 1 (draws at `0x1420047f9`/`0x142004806`, AOSet picks at
   `0x141fa4acc`, `0x141fa492d`, `0x141fa4945`, `0x141ff601b`, `0x142005595`/`0x1420055b3`, called
   from `0x142004e27`) is wrapped in an RNG save and restore (`0x142cc9840`): the MT index returns
   to the saved one (i=850) at the first `doodads_post` draw. `area.rs` runs
   `doodads::no_overlap(rng, list, tile_objects)` twice (rooms after `resolve`, tile objects after
   `tile_objects`). `POE_DBG_DOODAD_DRAWS=1` prints every bounded draw of the doodad passes
   (`DOODAD_DRAW n result`). Per group in descending key order (rooms key 0, tile
   objects the `.tdt` object group), `below(n)`, a Fisher-Yates shuffle (`uniform(n - k)`, swapping k
   with k + draw), then placed unless a placed cell lies in its 3 x 3 cells. The listed type comes
   last, in order, and also needs no other listed object in its 3 x 3 cells.

The type hashes of these sets are the `ObjectHASH32` column of `Data/Balance/MiscObjects.dat`
(`0x140f699a0`).

**Tile-object pass** (`0x142002660`, vtable `+0x28`, after the doodad pass; `doodads::tile_objects`).
Row by row over tile records that are a tile's corner: the objects of the `.tmd` beside the `.tgt`
(tile data `+0x178`, loaded by `0x141d14cd0` only when `+0x16c & 8` is clear: the low byte of
`Tdt::body_flags`), then of the `.tdt`'s `tmd` (`+0x180`, `0x141d11f50` from `0x141d132e0`), each through `0x142002a00`: the `AOSet`
pick continues the doodad pass's RNG stream, then the entry's orientation mask (trailing `I R90 R180
R270 FI FR90 FR180 FR270`, entry `+0x1e`), the cell turned within the tile's size. They are not in
the hash. A `.tmd` line is `x y flag [wx wy] z angle q0 q1 q2 q3 flip scale "ao" "name" "fmt" "type"
n [orientations]`; the flag says whether the world `x y` is present. P3_1's
`ambush_CenterHoleLarge_01.tdt` (flags `0x9a`) proves the bit-8 rule: its art `.tmd` repeats the
own list's 11 `SkeletonCave_set.ao` picks, and drawing them twice shifted every later pick.
`+0x178` keeps the last existing `.tmd` of the `.tgt`'s `;` segments; `0x141d14060` returns
when it is null. Without body flag 0x200 (`+0x16d & 2`) the art list is the whole `.tgt` with the
extension swapped (`0x141d148e0`). With it (`doodads::subtile_objects`) the `.tgt` is a `;` list
and each group-origin sub-tile (record `+0x90`, 0x38 bytes, row-major, `+0x60` wide; `+0x31` =
`SubTile::b1`: 8 skip, 2 joined to the left, 4 joined above; bit 1 is the plane margin) places the
`.tmd` of segment `parts[0]` (`+0x36 >> 2`, `0x141d146b0`; skipped when missing), turned by
`parts[1]` (`+0x37 >> 5`; `Landmark_feature_02.tdt`: segments 0..6 of 7, orientations 0..7).
Span (`0x141d13ed0`): 1 + the run of right neighbours with b1 2, 1 + the run of lower neighbours
with b1 4, swapped for odd orientations. Each entry's world point turns in the span box
(`0x142f15238`), plus (x, y) * 250, cell = floor(world * 0.092); angle as `turn_angle`; flip
toggles for orientations 4..7; the orientation mask maps through `0x1435280a0[o + mask * 8]`, the
OR over the mask's bits of an 8 x 8 composition (`ORIENT_COMPOSE`). Height `+0x37 & 0xf`, sign
0x10, times `+0x177` times 7.8125 (no grid effect). The entries replace the art list and go to
`0x142002a00` before the own list. Gate: `forced_verify` 12,848/12,848 grids identical in `G3_1`,
`G2_5_1`, `G2_2`, `MapLostTowers`, `P3_1`, `G2_5_2`. Not ported: the `alttiles/<env>/<env>_<name>.tmd`
variant (`0x141d148e0`, `0x141d1e680`; 111 files: foundry, act3church, marakethdesert, nosnow).

**Binary `.tmd`** (805 of the game's 9,706; 742 version 5, 63 version 6; `doodads::tmd_binary`).
Client parser `0x14292cd30` (entries go to the sink vtable `0x1434d3f18`, slot 0 `0x141d0e690`; the text
line options go to `0x141d0dd40`). First byte = version: 2..6 binary, otherwise the text format
starting `version`. Then a u32 entry count, the entries, then a UTF-16 string table (u32 length in
chars, NUL-terminated strings addressed by char index; `0xffffffff` = none). Entries have no
orientation list (all orientations); cell = floor(world * 0.092).
- v5, `0x24` bytes: world x, world y, height, x-rotation, angle (z rotation), asset-name indices at
  `+0x14` and `+0x18` (passed to `0x14292ffb0`), type string `+0x1c`, `.ao` string `+0x20`; scale 1, no flip.
- v6, `0x2d` bytes: world x, y, height, two rotations, angle `+0x14`, scale `+0x18`, asset names
  `+0x1c`/`+0x20`, type `+0x24`, `.ao` `+0x28`, flip byte `+0x2c`.
  Ruled out: a different angle sign or rotation offset for the `G3_8` street pillars (rotating them
  worsens `G3_8`); `.ao` index `0xffffffff` entries (none in `G3_8`).

**`.tdt` fields:** the body's first u16 is tile data `+0x16c` (`Tdt::body_flags`); after the `tmd`
string come a string and the object group byte (`+0x170`, sink `+0x58`). Tile data `+0x10` is the
feature string's length (`0x141d22bf0`).

## Unwalkable corners

`0x1420061c0` (called from `TerrainGen_Layout`) runs, per region: outer fill and outer buffer, then
`0x141fef780` on the region's rectangle if the master's `DoNotFillOutside` (`+0x166`) is clear (regions
past the main count only with `+0x164`), and `0x141fef650` (the map border). `0x141fef780` runs for
`.tgr` graphs and dungeons alike (`finish_dungeon` runs it on the region, which `regions.tsv` shows
is the whole buffered map) and returns at once for area kinds 0x20 and 0x21 (world-map panels).

The tail of `0x141fef780`: the enclosed-fill test requires an **empty feature**, not "not
inheriting" (`mark_enclosed_fills`); with the master's `OuterGroundIsOutside` (`+0x165`) and an
`OuterGroundType` (`+0x230`), tiles with body flag 0x40, first sub-tile flag 8, all corner grounds
the outer ground and only empty or wildcard edges get their footprint marked
(`mark_outside_tiles`). Master `+0x166` is `DoNotFillOutside`: the DLL's `regions.tsv` shows it set for
`TN_WorldMap` and `MapUniqueLake` (the only masters with that key besides the kind-0x21 world
maps) and clear for the `RoomOcclusion` masters `G2_4_2` and `MapChannel` (run `flags3`). Port:
`area::do_not_fill_outside`, dungeon and `.tgr` paths. `0x14293aaa0` parses the keys into
stack slots `FillOutside` 0x31e, `DoNotFillOutside` 0x31f, `OuterGroundIsOutside` 0x320,
`RoomOcclusion` 0x321, `DisableDoors` 0x322 and hands them to a vtable call (`0x14293eab6`), so
the copy is not one block (the door code reads `DisableDoors` at `+0x167`). No master sets
`OuterGroundIsOutside`; which key is `+0x165` is not proven. Ruled out: `RoomOcclusion` at
`+0x166` (it cost `TN_WorldMap` 74,088 cells per layout).

**`outside_tiles` zones** (`0x14200a1e0`, runs after the layout, after `0x1420061c0`): walks every
region's room placements (region `+0x58`, 0x38-byte entries; corner = placement min, orientation
`+0x1b`) and each room's `.arm` zones (room data `+0xa0`, 0x60-byte entries: name, x_min, y_min,
x_max, y_max, an object type checked by the side filter vtable `+0xa0`, a string, an int; in the file
`"outside_tiles" x0 y0 x1 y1 "" "" 0`, poe_data_tools `ARMFile::zones`). A zone named
`outside_tiles` has its first cell (x_min, y_min) and last cell (x_max-1, y_max-1) turned like a
doodad cell (table `0x142f15238`), and `0x141febcc0` sets lattice flag 8 on every corner from
ceil(min/23) to ceil(end/23) inclusive (end exclusive in cells), clamped to the map. All 97 zones of
this build have empty type strings; 71 `.arm` files use it (ubertavakai, act 4 gallows, plantation,
razedfields, slash, monument, oasis, necropolis, ...). Other zone names handled there:
`hide_teleports`, `boss_sector` (not ported, no grid effect known). Port: `doodads::room_outside`
(collected per placement in `generate::derepeat_pass` into `TileMap::outside`, shifted with the
doodads) and `doodads::mark_outside` (called in `area::generate_with_files` after the graph; switch
`POE_NO_OUTSIDE_ZONES`). `0x141fef650` only flags the map border. Found with the generator-trace
lattice dumps ([batch.md](batch.md#traces-in-batch-mode)) and `check_lattice` with
`LATTICE_GROUNDS=1` (client ground index vs port ground, flag 8 each side).

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
- `forced_verify` reports `doodads match|differ` after the tile hash; `POE_DBG_GRID_DUMP=DIR` writes
  the port's grid and solid objects (`.objects.tsv`) per layout (rule on/off comparisons where no
  client export exists).
- `POE_DBG_HULL_SET=x,y,angle,flip[,scale]` restamps one object (flip 2 leaves it out);
  `runtime/gridtools/anglesweep.sh` sweeps angle x flip with it, `circfit.py` scores circle
  centres and radii against the client grid. Examples `subtile_parts` (per-sub-tile bytes),
  `ao_anim_scan` (animated hulls at non-zero angles).
- Batch exports also write `entities.tsv` (objects with cells), `tiledata.tsv` (tile data
  `+0x16c..`), `lattice.bin` (final corners), `regions.tsv` (region rectangles and master flags).
  `POE_HOOK_GRID_PHASES=<Z: dir>` with `POE_HOOK_GEN_TRACE=1` (one thread) writes the grids at each
  generator phase.
- Debug variables: `POE_DBG_DOODADS`, `POE_DBG_DOODAD_ORDER` (picks and draws), `POE_DBG_HULLS`,
  `POE_DBG_GRID_TILE=x,y` (one tile's flags, corners and plane), `POE_DBG_NEAR=x,y,r` (the port's
  doodads near a cell), `POE_DBG_TILEONLY` (the grid after the tile stage), `POE_DBG_CELL=x,y,l` (the
  object that lowers a cell), `POE_DBG_FLOOD=x|all`, `POE_DBG_TMD_DRAWS`, `POE_DBG_TMD_LIST`,
  `POE_NO_TILE_OBJECTS`, `POE_NO_COVERS`, `POE_NO_ANGLE_DROP`, `POE_NO_DGR_UNWALKABLE`.

## Live grid and server-side objects

The client's live grid is its own generation plus the hull of every static entity in the world,
including entities the server sends:
- **On placement** `0x1421546e0` calls `0x141d198a0`, which stamps the entity's hull
  (`0x141d1d080`) when its type is static (`[Positioned+0x158]+0x20`) and `Positioned+0x1e6` bit 1
  is clear.
- **Full rebuild** `0x141d1e4f0`: every static entity of the world (`TriggerableBlockage` ones only
  while that component's `+0x30` is set). It runs on S→C `0x0181` (world `+0x690` set), after the
  base layers `+0x100`/`+0x118` are copied back to the live `+0xd0`/`+0xe8` (`0x141d22430`), and in
  the hideout editor (`0x14023aae0`, `0x14023afd0`) and `0x142090fd0` (which rebuilds the tiles with
  `0x141d1b1a0` first).
- **`TriggerableBlockage`** stamps when activated (`0x141e0e000`, keeps the delta) and removes the
  stamp with that delta (`0x141e0e9c0`).

So an official client ends with the `Side::Server` grid once the server's `server_only` objects
have arrived. Evidence: in the official capture `2026-10-20_21-51-49` (`G1_town`), the server sent
`HealingWell` at (349, 237), facing 1.3627, and `CraftingBenchEzomyte` at (354, 395), facing
0.0027 (AddObject Positioned). These are the cells and angles the port places for `G1_town` seed 1,
and they are its only two solid `server_only` objects. No live grid of an official session was
compared byte for byte.

Size of the difference (`side_diff`, every 50th `grid50` layout, 4,375): the `Side::Server` grid
differs from `Side::Client` in 812 layouts (86 areas, every town, median 3,300 cells). Only solid
`server_only` types cause it (198 types: towers, `StoneHengeAct1`..`6`, healing wells, crafting
benches, chairs); no `client_only` type is solid. Output in `runtime/r2side/step50.tsv`.

Until the instance server sends these objects, its grid must be `Side::Client`; a `Side::Server`
grid blocks cells the client walks through. Two open points remain, both relevant once it sends
them. Quest-state variants: `G1_11` places all six `StoneHengeAct*` at one spot, but the official
server may send only one. The server-only scatter is not ported.

## Server use

The instance server always builds the grid (and the spawn
layout) with the port and kicks a client whose tile hash differs; it never reads the client's files. `poe-world` depends
neither on `poe-game` nor on `poe-config`; the instance server is the adapter
(`poe_world::collision::build(..).pwg1()` into `poe_game::grid::Grid::parse`), see
[../../architecture/instance-world.md](../../architecture/instance-world.md#terrain-grid-sources).

## Results and open points

### Results

- `grid50` (all 432 areas, 50 seeds per topology and orientation, 218,705 ok client layouts,
  `forced_verify`): tile and doodad hashes all identical; grid hashes 218,655 identical, 0 differ. The
  other 50 rows are `G_login`: the client's grid hash is 0 and its export has no `grids.bin`, so there
  is nothing to compare. Client mode only.
- Every client grid export on disk (`check_grids`, 5,318 from all runs): 5,312 identical, 0 grids
  differ. The other 6 lines (5 jobs; `G2_12` seed 392042115 in two runs) are bad client exports, not
  a generator gap: they come only from the traced runs `w6-b-1`, `w7-1`, `w10-1` and `w11-2`/`w11-4`
  (relaunches after hangs, 5-48 s per layout). Every plain run (`full`, `d1`, `fails1`, `grid50`, and a
  fresh `layout5` re-export of the 5 jobs) gives one other layout, and the server matches it (5 of 5
  identical). Do not use a traced run's export as a reference.

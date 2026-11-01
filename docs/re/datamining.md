# Datamining

## File system
- The client's data is in `GameFiles/Bundles2`: `_.index.bin` plus Oodle-compressed `*.bundle.bin` files.
- Virtual paths are lowercase, e.g. `data/balance/worldareas.datc64`.
- Base-language tables are in `data/balance/`; translations in `data/balance/<language>/`.
- Terrain graphs: `metadata/terrain/**/*.tgr` (148 files). Characters and objects: `metadata/characters/**` (`.ot`, `.otc`, `.ao`, `.act`).

CLI examples (`list`, `extract`, `dump-tables`): [../guides/setup.md](../guides/setup.md#tools).

## Dumps folder
Everything extracted or generated that is not source (terrain grids and layouts, area exports, test vectors, client tables, Ghidra exports, packet captures, strings) lives in the git-ignored `dumps/<version>/`. Layout, producers and regeneration: [dumps/README.md](../../dumps/README.md). `scripts/dumps/migrate.sh` sorts old files from `GameFiles/` and `runtime/` in. Ghidra exports and factory maps are in `dumps/<version>/ghidra/`; a fresh clone must regenerate them (`scripts/re/dump_factory.py`, Ghidra `search_functions_enhanced`; see [README.md](README.md)). The factory dumps feed the deserializer baseline `modules/protocol/opcodes/<version>/deserializers.tsv` of `cargo xtask check-build`. Tables and columns the server reads: `poe_data::used`; checks against `Bundles2` and the dat-schema pin: [../guides/new-game-version.md](../guides/new-game-version.md).

## Tables in the server
`poe_data::GameData::open(game_dir, schema)` then `.table("WorldAreas")` returns a cached `Table`. Rows are read by column name: `row.str("Id")`, `row.int("AreaLevel")`, `row.row_ref("ParentTown")`. Unnamed columns are `"_<index>"`.

Format of `.datc64`:
- `u32` row count, fixed-width rows, eight `0xBB` bytes, then variable data. Little-endian.
- Strings are UTF-16LE, null-terminated, stored as u64 offsets relative to the `0xBB` marker.
- Arrays are `u64 count, u64 offset`. A null reference is `0xFEFE…`.
- Value widths: bool=1, i16/u16=2, i32/u32/f32/enumrow=4, string/row=8, foreignrow/array=16. An interval column holds two values.

The schema is `third_party/dat-schema/schema-poe2.min.json` (dat-schema version 7, rolling `latest` release), filtered to `validFor & 2` (PoE2). Many PoE2 columns are unnamed; name them through RE when the server needs them.

## Verified against 0.5.5e (same data in Hotfix 1)
- `Characters`: 12 rows, ids `Metadata/Characters/<Attr>/<Attr>Four` and `...Fourb` (male/female).
- `WorldAreas`: `G1_1` = "The Riverbank", act 1, level 1, HASH16 3860. Schema row width (736) matches the file.

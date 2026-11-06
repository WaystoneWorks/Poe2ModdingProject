# Terrain generator status

The server's generator (`modules/server/crates/poe-world`) reproduces the client's layouts. What remains (collision, objects) is in [PLAN.md](../PLAN.md). How the client generator works, and the tools: [../re/terrain/](../re/terrain/README.md). Per-combination results: the generated [terrain-matrix.tsv](terrain-matrix.tsv) (`cargo xtask terrain-matrix`).

The client builds its own terrain from the area and seed the server sends, so it loads any area regardless of our generator. The server's copy is what has to match.

## Results

- All three 50-seed client batches match on every layout the client generates (tile hash, and the doodad hash on every match): batch 1 218,705, batch 2 (`full2`, master seed 20261026) 218,802, batch 3 (new seeds, master seed 20261028) 218,678. Matrix: 4469 match, 0 partial, 0 fail, 39 untested, 10 n/a.
- Natural choice (no forced layout): 4,173 of 4,173 (`w13-nat1`) and 8,368 of 8,368 (batch 3) unforced client generations match; world-map pins 102 of 102. The instance server always forces that choice and generates each new instance.
- Vectors: `dumps/0.5.5f/terrain/vectors/forced-results{,-full2,-batch3}.tsv`. Baseline: `runtime/forced-baseline.tsv`.
- **Area-generation re-check (broad sample, 2026-11-01):** 50 seeds x every topology and orientation of all 432 areas (`grid50`): tile and doodad hashes identical in 218,705 of 218,705 ok jobs. 6,695 of 225,400 jobs are client generation exceptions that the game retries with another seed.
- **Grid (collision) status:** `grid_hash` compared on the same 218,705 layouts: 218,655 identical, 0 differ. The other 50 are `G_login`, where the client has no grid (hash 0, no `grids.bin`). Client mode only. The generated grid is the server default (R2 done); open points in [PLAN.md](../PLAN.md).
- **Live mismatches:** the instance server kicks a player whose client hashes differ from the generator's ([../protocol/instance.md](../protocol/instance.md#terrain-check)) (no mismatch log is kept); `cargo xtask terrain-matrix` reads only the vectors dir (`area-vectors-results.txt`, `forced-results.tsv`, `probe-results.tsv`). The popup's exported client layout is the input for `layout_diff` and `area_trace`.
- The client checks a forced topology against the unfiltered list (all league modes); the matrix counts the mode 1 list. The 11 areas with other-mode topologies need a check.

### The rows that do not match
- **Untested (39):** the client fails on every seed, so there is nothing to compare (errors from `dumps/0.5.5f/terrain/batch/full/batch-results.tsv`): `ExpeditionLogBook_Heath` 1:1/3/5/7 ("Non-feature node overlapping another"), `G2_10_1` 5:1/3/5/7 and 7:1/3/5/7 ("Failed to connect edge"), `HideoutPietyArena` 1:0 and `MapUniqueVault` 1:1/3/5/7, 2:1/3/5/7 ("No possible rooms found for room"), `IncursionTemple` / `IncursionTemplePresent` 1:0 ("No walkable area in the level"; built by their league mechanic, out of scope), `MapBackwash` 1:0..7 ("Failed to tilise at tile"), `MapRockpools` 1:0..3 ("While tilising .../bossman.arm"), `Sanctum_1`..`Sanctum_4` 1:0 (`BufferUnderflow` reading their graph in the headless batch). The natural choice never picks them in the client either.
- **N/A (10):** areas without `Topologies` rows (`NULL`, `CharacterSelect`, `PersonalHideout`, `GuildHideout__`, `CurrentTown`, `G2_3s`, `G2_8a`, `MapLeaguePortal`, `EndgameDoodad_MeteorCrater`, `EndgameDoodad_BeastGroundZero`). The 6 world-map panels have no client hash.

## Client batch
`terrain_batch.py plan full --seeds 50` and `run full` make the client generate every combination (4,508) with 50 seeds: 225,400 jobs in 1.3 h of one launch (8 threads, 48 layouts/s, 170 ms per layout, 0 crashes; [batch.md](../re/terrain/batch.md)). The client errors on about 6,600-6,700 jobs per batch (100 areas, mostly `G2_10_1`, `MapBackwash`, `G2_1`, `MapUniqueVault`, `G1_12`).

## Progress of the first batch

| Date | Stage | Matches of 218,705 | Server commit |
|---|---|---|---|
| 10-22 | First run | 37,380 | |
| 10-22 | Wave 2 | 72,718 | `bfa7c6e` |
| 10-23 | Wave 3 | 108,545 | `97c2949` |
| 10-23 | Wave 4 | 176,336 | `a3558f9` |
| 10-24 | Wave 5 | 196,094 | `6fe3299` |
| 10-25 | Wave 6 | 206,746 | `d53ee43` |
| 10-26 | Single agent | 213,860 | `2cf8f68` |
| 10-27 | Single agent | 218,490 | `6eb0e9b` |
| 10-27 | Single agent | 218,653 | `eaad3c0` |
| 10-28 | BossRush_Area1 | 218,702 | `0431880` |
| 10-29 | R1 complete | 218,705 | `319b52e` |

The rules behind each step are in [dungeon.md](../re/terrain/dungeon.md), [tgr.md](../re/terrain/tgr.md) and [shared-passes.md](../re/terrain/shared-passes.md).

## Verification tools (`poe-world/examples/`)
- `area_vectors`: threads (`--threads N`), build filter (`all`, `N`, `>=N`), `--natural`, `POE_VECTOR_BUDGET=<seconds>` per (area, seed), search order with `--hints <earlier results>` and `--probe <probe results> [--runnable-only]` (skips topologies whose probe failed everywhere, so rerun without it for a specific area). Result lines end with `build=N`.
- `area_probe`: `--seeds a,b,c`, `--orientations first|all|N`; one TSV line per attempt. 13,524 attempts take 15 minutes.
- `forced_verify <batch-results.tsv> [--out forced-results.tsv]`: replays a client batch (columns `area seed topology orientation status tile_hash doodad_hash width height ms detail`).
- `generate::CachedFiles` caches files for a run (`area::generate_with_files`): the bundle reader decompresses under one lock, so parallel runs need it.
- Matrix columns: `seeds` (matched/tested), status `match` / `partial` / `fail` (forced results only) / `untested`, `old` (seeds only an older build's vector vouches for); the probe cell covers every probed seed and orientation (`ok 6/6`, `error (4/6 ok): ...`).

## Reference results
- Riverbank (`G1_1`, seed 1000): tile hash 138293894, 5382 cells, 6414 draws in step. Later draws (`0x1415ad965`, …) belong to the doodad/entity stage. `G1_12` 1001 with `2:7`: 174×87, 15138 cells, hash 3369045138, 2385 draws (`area_trace G1_12 1001 dumps/0.5.5f/terrain/traces/act1_traces/G1_12_1001 2:7`).
- Clearfell Encampment seed 1: `town_check` reproduces all 71 room-pass placements (48 draws). `river_gen` covers the Riverbank stages.
- Doodads and the grid: [doodads.md](../re/terrain/doodads.md).

## Not ported yet
Paths no tested job uses (from the RE notes):
- The height fallback of `0x1420ae070` (`0x141d12110` / `0x1420aeb20`).
- Off-map ends of virtual edge splits (`0x1420c9360`); virtual nodes that no tile fits at the room stage (`0x1420d9a60` places those that fit).
- Transition tiles (`0x141fef2f0`) and the tile-set option `+0x165` of the unwalkable-corner flood.
- The corner ground fix-ups of a de-repetition replacement (`0x141fed030`).
- `unique<N>` lettered tags from session history.

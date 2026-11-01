# In-client batch generation (`gen_batch`)

How the client DLL runs the client's own terrain generator in a loop, for any `WorldAreas` row,
seed, forced topology and forced orientation, with no login and no session, and reads back the tile
hash, doodad hash and map size. This is the data source of the terrain port's acceptance test
(every area, every topology and orientation, 50 random seeds). Addresses are Ghidra addresses of
0.5.5e Hotfix 1 (image base `0x140000000`), found by signature at run time
(`modules/client-hook/signatures/0.5.5e.hotfix1.toml`, feature `gen_batch`). Private mode only: the
feature is refused when `poe-hook.toml` says `mode = "official"` and again before every job when the
loader's read-only latch is on.

Use: [the guide](../../guides/setup.md#terrain-batch-generation). Code:
`modules/client-hook/poe-hook-core/src/gen_batch.rs` (jobs, worlds, results), `cxx_guard.rs`
(surviving the generator's exceptions), `poe-hook-shared/src/batch_jobs.rs` (job and result file
formats), `scripts/re/terrain_batch.py` (plan, run, status).

## Result

- The client generates a layout in **about 80 ms (act 1) to 400 ms (act 3, 4) on a worker thread**;
  with eight threads act 1 runs at **118 layouts per second** and all acts at **38 per second**
  ([Measurements](#measurements)). The 225,300 layouts of the acceptance test take about 2 hours
  including the restarts the memory cap makes.
- Tile hash, doodad hash and size are **bit for bit the client's**, e.g. `G1_12 1001 2:7` gives
  `3369045138` at 174x87.
- No login, no server and no game state beyond the loaded data: the client sits at its login
  screen (20 s after the start the bundle index and the `.dat` tables are ready).

## How the generator is run

`HeadlessWorld_LoadArea` `0x14212f680` is the **base world**'s vfunc `+0x1e0` (vtable
`0x143508470`, constructor `0x14212ece0`). The in-game world, `ClientWorld` (constructor
`0x14167d470`, `new(0x17e8)`, vtable `0x14339d1d0`), overrides it with `ClientWorld_LoadArea`
`0x14167b3f0`. The base world has no terrain (its vfuncs `+0x1a0/+0x1a8` raise an "unimplemented"
exception), so a world that can generate has to be a `ClientWorld`: its vfunc `+0x1a8` returns the
terrain object embedded at world `+0x8d0`, `+0x1c8` the generation state at world `+0x4b0`.

Both LoadAreas do the same, which is all `gen_batch` repeats per job:

1. `world +0x4b0 = p2` (u32, 0 in 904 of 929 area exports; the other value is an instance number),
   `world +0x4b4 = seed`, `+0x663 = 0` (headless; the client sets 1); the `LoadArea` vectors `p4`
   (u8 indices into a 0x65-byte table, `0x141d02d20`) and `p5` (u64 list, `+0x508`) stay empty.
2. `TerrainGen_Construct(generator, world)` `0x141fefba0` (base generator vtable `0x1434edf80`, 704
   bytes in the headless version), `TerrainGen_Run` `0x141ffeac0`, read tile hash (world `+0x114`)
   and doodad hash (`+0x118`), the generator destructor `0x141feffc0`.

Differences between the base generator and the client's (`0x143387098`):

| What | Base (headless) | Client |
|---|---|---|
| vtable `+0x20` | `0x141ff4750` | `0x1415a1880` (the "create this object?" filter, adds the client's own tests) |
| vtable `+0x68`, `+0x78`, `+0x80`, `+0xa0`.. | empty or minimal | rendering hooks |
| **generator `+0xe`** | 1 (set by the constructor) | cleared by `ClientWorld_LoadArea` (`local_2fa = 0`) |

`generator +0xe` switches the **tile map validation pass** (`0x141ffdc30` → `0x141f9e080` →
`0x141f9db40`, "Invalid TileMap: Mismatching ground types on corner ..."): the server's generator
validates and throws, the client's does not. Without clearing it, layouts the client generates
(`G1_4 1001 10:2`) throw. `gen_batch` clears it after the constructor; the other phases are shared.

### What the world needs

| Field | Value | Notes |
|---|---|---|
| `+0x98` | the `WorldAreas` row | `+0x1b4` area kind, `+0x2a` hash16, `+0x60` topology count, `+0x68` topology list (16-byte entries) |
| `+0xa0` | the `WorldAreas` table object | a counted reference (`+0x3c`): the Incursion temple rooms (`0x141eff410`) read the table from here and the world's destructor releases it; without it `IncursionTemplePresent` crashed |
| `+0xb8` | league mode, **1** | the `Mode` column the topologies are filtered by (`0x141fdffb0`: mode equal, else 0x39, else mode 1) |
| `+0x128` | the stat map | sorted `(i32 key, i32 value)` pairs, begin `+0x128+8`, end `+0x128+0x10`; set `0x1423ba640(map, key, value)`, get `0x1423ba4e0(map, key)` (0 when absent), 978 callers |
| `+0x58` | terrain plugin list | from AreaInfo; empty |

The `WorldAreas` table object comes from `0x140223710(&out)` (a counted reference; state `+0x40` is
2 when loaded, else wait with `0x1421d7070`); `*(table+0x28)` points at `(begin, end)` of the rows:
**442 rows of 0x2e0 bytes**, row `+0` a pointer to the NUL-terminated UTF-16 id string. `gen_batch`
builds an id → row map once (the count comes from `poe-hook-data/areas.tsv`, which `deploy-client`
writes from the same game data).

### Forcing topology and orientation

`map_force_topology` (stat `0xb92`) and `map_force_orientation` (`0xb93`) are plain entries of the
world's stat map; the server sends them in the first stat record of AreaInfo
(`modules/server/servers/instance-server/src/lib.rs`, `transfer`), and the client's AreaInfo reader
(`0x14211d340`) stores them in `world +0x128`. `TerrainGen` vfunc 0 (`0x141ff9400`, topology pick)
reads them: topology `ebx` = stat `0xb92` (0: not forced), must be `<= row +0x60`; orientation =
stat `0xb93` − 1 when in `1..=8`, else 8 (not forced); then `0x141ff9270(generator, out, topology,
orientation, {count, row +0x68})` picks the graph. `gen_batch` sets the same stats with
`0x1423ba640` before the generator is built: `topology` 1-based as `transfer` does, `orientation + 1`.

**Forced topology index.** The client checks `map_force_topology` against the **raw** `WorldAreas`
list (row `+0x60` entries, all league modes) and takes entry `stat - 1` of row `+0x68` (`0x141ff9400`
checks `stat <= row +0x60`, else throws "Cannot force graph N because area X does not have that many
topologies"; `0x141ff9270` indexes the array, no mode filter). The mode filter is only used when
nothing is forced. In all 442 areas the mode 1 (or 0x39) entries are a **prefix** of the raw list, so
the 1-based index into the port's `topology_entries` is the same index into the raw list. 11 areas
list further mode 54 entries after the mode 1 ones (G1_2 33 raw / 18 mode 1, G1_6 8/4, G1_11 24/12,
G1_13_1 32/16, G2_4_1 8/4, G2_5_2 8/4, G2_8 8/4, G3_2_1 18/9, G3_3 16/8, G3_4 8/4, G3_7 8/4); forcing
an index past the mode 1 entries picks those (not in the matrix). The port's forced handling
(`area::generate_probed_files`) indexes `area::raw_topology_entries` and fails like the client past
its end.

The natural choice (no forced stats, topology 0) uses the world map pins; with none it falls back to
a draw (`0x141ff9400`).

## Threads

Safe for 1 to 12 workers:

- The RNG is thread-local (`TLS + 0x20190`, seeded by every generation); the same jobs give the
  same hashes on 1, 2, 4, 8 and 12 threads.
- The shared caches (`.tdt`/`.arm`/`.tgr` loads, tile-set indexes) are the ones the client uses from
  its own worker threads (it generates world-map panels in parallel). Resources load on first use
  (async, `0x1421d7070` waits), so the first jobs of an area are slower.
- Every job builds its own world and generator and destroys them (`world` vfunc `+0x20` with 1: the
  deleting destructor; the generator `0x141feffc0`), allocated with the game's allocator
  (`0x142bba600` / `0x142bba4e0`; per-thread heaps that accept frees from any thread).
- The ClientWorld constructor bumps a global world counter (`0x1445d8188`) without a lock; two
  workers can get the same id. Nothing depends on it.
- Memory: see [Measurements](#measurements).

## Exceptions: generation failures

The generator **throws `TerrainGenerationException`** (MSVC C++ exception, type
`.?AUTerrainGenerationException@Generation@Terrain@@`) when a layout cannot be built, and nothing
catches it in the client's own load path (the official server picks the seed, so it never sends a
failing one). About 2 % of act 1 jobs: "Dungeon generation failed: Failed to place a special room",
"... Failed to connect edge ...", "... No possible rooms found for room at (x, y) with type
\"empty\"", "Mismatching ground types at (x, y): Cannot place WideRiverWater over ...", "Failed to
find suitable fill tile/room", "Could not find matching overlap tile", and, for
`IncursionTemplePresent` (always; its rooms come from the player's temple, which the batch lacks, as
for any plugin needing session data), "No walkable area in the level". They are results, not bugs:
the port fails the same jobs, and the matrix gets `error` rows with the text. The first characters of
the message are sometimes overwritten (`G1_World...`); classify errors by the rest of the text.

An unhandled throw ends the process, so `cxx_guard.rs` makes a guarded call:

- `gb_try_call` (assembly, `.seh_proc` unwind info so the first-pass stack walk gets past it) saves
  callee-saved registers and the stack position and calls the function.
- `SetUnhandledExceptionFilter` is only reached when **no frame has a matching catch** (the game's
  internal `try`/`catch` keep working), so the filter checks that the thread is inside a guarded
  call and the exception is a C++ one, then jumps back (`gb_longjmp`); the call returns `Err` with
  the type and the message (the exception object holds a string stream: the text is found by scanning
  the object, ending at the stream's write position).
- The filter cannot return `EXCEPTION_CONTINUE_EXECUTION` (a C++ throw is noncontinuable:
  `0xC0000025`); it calls `RtlRestoreContext` itself.
- **The C++ runtime's per-thread state must be put back.** The statically linked runtime keeps a
  chain of executing catch blocks in `__vcrt_ptd` (`0x142c144c8`, field `+0x58`, also
  `+0x20/+0x28/+0x70`); abandoned catch blocks leave entries pointing into dead stack, and the next
  throw reads them (`_IsExceptionObjectToBeDestroyed` `0x142c13c40`: access violation after a few
  hundred recovered exceptions). `call` saves the first `0x98` bytes of that state and writes them
  back after a recovery.
- What the skipped frames held stays held (memory, a lock); the generator and world are destroyed
  afterwards in guarded calls anyway; a destructor that throws leaks.
- Access violations are not recovered: the client dies and `terrain_batch.py` restarts it.

## Job and result files (`<run dir>`)

| File | Who | Contents |
|---|---|---|
| `jobs.txt` | `terrain_batch.py plan` | `area seed topology orientation` per line; topology 1-based (0: not forced), orientation 0-7 (negative: not forced) |
| `export.txt` | by hand | same format: jobs whose `exports/<area>_<seed>_<topology>_<orientation>/` (`layout.tsv`, `doodads.tsv`, `grids.bin`, `meta.txt`) are written |
| `suspects.txt` | `terrain_batch.py run` | jobs that were running when the client died; run first, on one thread |
| `batch-results.tsv` | the DLL | `area seed topology orientation status tile_hash doodad_hash width height ms detail grid_hash`; `grid_hash` is FNV-1a 64 of the job's `grids.bin` bytes (hex, every job, exported or not; `forced_verify` compares it with the port's grid); `status` `ok`, `error` (detail: the exception or the check that failed) or `crash-skip` (written by the script); one `write` and flush per line; jobs already in the file are skipped on a restart |
| `inflight-<n>.txt` | the DLL | the job worker `n` is running (removed when the run ends) |
| `batch-done` | the DLL | written when every job has a line |
| `crashes.tsv`, `state.json`, `seeds.json` | the script | crash counts per job, timing, the plan (master seed, filters) |

Configuration: `[gen_batch]` in `poe-hook.toml` (`enabled`, `dir`, `threads`,
`start_delay_seconds`) or the environment, which the script uses: `POE_HOOK_GEN_BATCH=<run directory
as the game sees it, Z:\...>` (enables it), `POE_HOOK_GEN_BATCH_THREADS=<n>`. Always off in official
mode. The hooks of the area export (driver, add object, doodad hash site) are installed for it; a
batch generation is never exported by the area export itself, and objects and doodads are only
collected for the jobs of `export.txt`. Only layouts are compared: the server-only doodad scatter
(globals `0x1445c995c` / `0x14458c74c`) is not run.

## Addresses

| Address | What |
|---|---|
| `0x14167d470` | `ClientWorld` constructor `(this, frame mode u8, flag u8)`, size `0x17e8`; vtable `0x14339d1d0` (`+0x1a8` terrain at `+0x8d0`, `+0x1c8` state at `+0x4b0`, `+0x1e0` LoadArea, `+0x20` deleting destructor) |
| `0x14212ece0` | base world constructor (only caller: the ClientWorld constructor); vtable `0x143508470` |
| `0x14212f680` | `HeadlessWorld_LoadArea` (base vfunc `+0x1e0`): `(world, u32 p2, u32 seed, vector<u8>* p4, vector<u64>* p5)` |
| `0x141fefba0` / `0x141feffc0` | `TerrainGen_Construct(generator, world)` / generator destructor |
| `0x141ffeac0` | `TerrainGen_Run` (the batch calls it through the area export's driver hook, which passes batch generations through) |
| `0x141ff9400` | topology pick (generator vtable `+0`): reads stats `0xb92` / `0xb93` from `world +0x128`, `world +0xb8`, row `+0x60/+0x68` |
| `0x141ff9270` | picks the graph for a forced topology and orientation |
| `0x141ffdc30` / `0x141f9e080` / `0x141f9db40` | the validation pass (runs when generator `+0xe`) / its driver / the checks ("Invalid TileMap: ...") |
| `0x141d0e2b0` | "Mismatching ground types at (x, y): Cannot place A over B" (throws; tile placement) |
| `0x1423ba640` / `0x1423ba4e0` | sorted `(i32 key, i32 value)` map set / get (the world stats at `+0x128`) |
| `0x140223710` | `WorldAreas.dat` table getter `(out)`; sibling getters exist for every table |
| `0x1421d7070` | resource "ensure loaded" (state `+0x40` == 2) |
| `0x142bba600` / `0x142bba4e0` | the game's allocator / free |
| `0x142c144c8` | `__vcrt_getptd`: the thread's C++ exception state |
| `0x142c13c40` | `_IsExceptionObjectToBeDestroyed` (walks the frame info chain at ptd `+0x58`) |
| `0x141eff410` | Incursion temple room object constructor (reads `world +0xa0`, throws "[INCURSION2] Present-day temple contains Past-only room") |
| `0x14100b2a0` | creates the in-game world (`new(0x17e8)`, constructor `(2, multi)`) and destroys the old one |

## Data-path rules the batch exposed

- `//` in joined game paths (`Shipwrecks//...`, `3_14//Subarea/...`): `generate::normalize_path`
  collapses repeated `/` in every lookup.
- `.dgr` graphs can have an `EnvironmentOverride: "<id>"` line before the ground types (G2_3,
  G2_3a, G4_5_2); the header reader must skip it.
- Container graphs whose master names no `RoomSet`, `TileSet` or `FillTiles` (MapKarst,
  MapDerelictMansion, P1_6, HideoutVampireManor) have an empty set and master and no outer fill of
  their own.
- A room whose root slot is not a key (MapWetlands `forced_rare.arm`: an empty key) is valid.

## Measurements

Development machine (16 cores, 62 GB RAM), act 1 unless noted, one client, `terrain_batch.py run`
defaults (8 worker threads, memory cap 16 GB). "ms" is one job's time on its worker with the others
busy.

- **Act 1 x 50 seeds** (966 combinations, 48,300 jobs): one unattended run, 0 crashes, 0 hangs;
  47,275 ok, 1,025 errors (generator exceptions: `G1_12` 310, `G1_7` 238, `G1_4` 199, `G1_11` 66,
  `HideoutPietyArena` 50, `IncursionTemplePresent` 50 ...); 409 s = 118 layouts per second; per
  layout mean 69 ms, median 53 ms, p95 188 ms.
- **Threads** (3,864 act 1 jobs, cold caches included):

  | threads | 1 | 2 | 4 | 8 | 12 |
  |---|---|---|---|---|---|
  | seconds | 150 | 82 | 51 | 35 | 30 |
  | layouts per second | 26 | 47 | 76 | 111 | 130 |

  Statuses, hashes and sizes are identical for every thread count and between complete runs
  (including one with client restarts).
- **All acts** (every combination x 2 seeds = 9,016 jobs, 8 threads): 234 s = 38.5 layouts per
  second, 277 errors. Per ok layout: act 1 mean 79 ms, act 2 209 ms, act 3 331 ms, act 4 375 ms,
  act 6 255 ms, act 10 231 ms (median 127 ms, p95 967 ms, max 2.7 s). The 225,300 jobs of the
  acceptance test (4,508 combinations x 50 seeds) take about 1.6 h plus about 25 restarts.
- **Memory** (resident set under Proton, sampled every 10 s into `rss.tsv`): client 1.7 GB 10 s
  after the start; 5.1 to 5.2 GB at the login screen when the first job starts; act 1 peaks at 7.4
  to 8.1 GB for every thread count (a few MB per thread) and stays flat (7.7 GB over 48,300 jobs); a
  second pass over 3,864 jobs adds about 0.13 MB per job. Act 10 **leaks about 0.7 to 0.9 MB per
  layout** that the world destructor does not give back (probably generated objects and the
  terrain's side tables): 9.2 GB after 2,304 layouts, 12.2 to 13.1 GB after 6,912. All acts, 9,016
  jobs without restart: 14.9 GB.

Memory is bounded by the number of layouts per client run, not the thread count, so
`terrain_batch.py run` caps the game process's RSS (`--max-rss-gb`, default 16): above it the DLL is
asked to stop (`<run dir>/batch-stop`), the jobs in flight finish (`batch-stopped`), the script stops
the client, starts it again and the run resumes with the jobs without a result (no job lost or
repeated, results identical to a run without restarts). A cap too close to the idle 5 GB would
restart forever, so a launch that makes fewer than 100 jobs raises the cap by 25 %. `--restart-every
N` restarts after N layouts as well. 12 threads add under 1 GB and 17 % throughput; the default is
**8 threads** (half the cores).

## Traces in batch mode

`POE_HOOK_GEN_TRACE=1 python3 scripts/re/terrain_batch.py run <name> --threads 1` writes
`generator_trace.tsv` next to the export of every job in `export.txt` (the trace buffer is global:
one worker thread only).

Tile-map checkpoints (`terrain_tools.rs` `TILE_CHECKPOINTS`) sit at: the graph pipeline entry
`0x141ff0770`, the post-layout stage `0x141ff7b90`, the outer fill `0x141fd6170`, the outer buffer
`0x141fd84e0`, the grid passes `0x141fe1150` / `0x141fe1020`, the overlay candidate scan
`0x141fa2560` (with `occupancy` rows: its occupancy bytes, bit 0 taken; not the per-position fit
test `0x141fa19b0`, called per candidate position, which made traced jobs hang), the placeholder
fill `0x1420a62c0`, the pre-unique room `0x14209c2d0`, the topology choice `0x141ff9400` and every
phase. `tdiff pre_<name> <caller>` lines list the tile records changed since the previous checkpoint
(`x y h<old>-><new> o<old>-><new> s<skip>`, result the tile file, `old>new` when it changed), closed
by a `tdiff_end` count; replaying them gives the tile map at any checkpoint. Extra rows: the
placeholder fill adds `roomgrid` (its room grid, 0 = free) and `placeholder_sizes` (site
`0x1420a637d`: the door type's size list, `w×h:weight` and the total); the pre-unique room adds
`preunique_cells` (its ground-only cell list before the shuffle: index, x, y, accessible, height,
ground); the outer buffer adds `strip_grounds` (site `0x141fdbdf4`: row y, walk limit and the two
grounds compared); the topology choice adds `map_pins` (generator `+0x280`) and `pin_dirs`
(generation state `+0x70`), see [shared-passes.md](shared-passes.md#topology-choice).

Lattice dumps (`terrain_tools.rs`): `unwalkable` at the entry of `0x141fe1150`, `enclosed` at the
entry of `0x141fe0cc0` (signature `lattice_enclosed`), `border` at the entry of `0x141fe1020`.
`check_lattice` with `LATTICE_GROUNDS=1` compares the client's ground index with the port's, with
flag 8 on each side.

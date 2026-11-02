# Plan

The only list of what is left to do and the only status source. Edit it in place and delete what is finished: history belongs in git and [status/history.md](status/history.md). Limit: 1,500 words. User decisions behind this plan: [decisions.md](decisions.md). How to work: [guides/agent-workflow.md](guides/agent-workflow.md).

## Now: R2, server-side collision

The server's collision grid (`poe-world/src/collision.rs`, `[terrain] generated_grid`, off by default) must equal the client's.

**State (2026-11-01):** the generated grid equals the client's in the broad sample (all 432 areas, 50 seeds per topology and orientation, run `grid50`, `terrain_batch.py plan <run> --seeds 50`): 225,400 client jobs, 218,705 ok, 6,695 client generation exceptions (2.97%). `forced_verify` over the 218,705: tile and doodad hashes all identical; **grids 218,655 identical, 0 differ**; the other 50 are `G_login`, where the client has no grid to compare (hash 0, no `grids.bin`). Rules and results: [re/terrain/doodads.md](re/terrain/doodads.md#results-and-open-points), [status/terrain.md](status/terrain.md).

**Limits of that number:** client side only. The client adds the hulls of the static entities the server sends, so the instance server builds the client-side grid until it sends the `server_only` objects ([doodads.md](re/terrain/doodads.md#live-grid-and-server-side-objects)). The `RoomOcclusion` link rests on offset arithmetic from `DisableDoors` and was not tested directly.

Steps:
1. **Live test** on the generated grid with `cargo xtask game-test` ([setup.md](guides/setup.md#game-tests-cargo-xtask-game-test): `walk_to`, `blocked`, `roll`, `max_drift`, spots from `wall_probe`): walls, cliffs, narrow passages, rolls into walls, drift checker on ([movement.md](protocol/movement.md)). `scripts/game-test/walk.toml` already passes one wall in `G1_town` seed 1 (walk stops where the grid says, drift at most 3.93 cells); still to cover: outdoor cliffs (`G1_1`), narrow passages, a dungeon (`G1_8`), rolls straight into walls.
2. **Defaults:** `generated_grid` on; the client upload (`[spawn.upload]`) off as a fallback (closes audit item S-08 for servers that keep it off). Update [server-admin.md](guides/server-admin.md) and [instance-world.md](architecture/instance-world.md).

**Pending:** ask the user before deleting old batch run directories (disk 481 GB free; the new runs take `grid50` 24 MB, `grid50ex` 691 MB, `flags3` small).

**Done when:** live movement collides like the client, and the defaults are flipped. The finish line is the full match, not an area-by-area fallback (user, 2026-10-31).

## T: agents test in game by themselves

Built before the R2 live test, because every later step needs it. The official-server read-only latch stays untouched.

- **T0 Isolated display.** The user installs gamescope (`sudo pacman -S gamescope`). Try the client under nested or headless gamescope with Proton and the hook, and prove input injection and logs still work. It replaces the removed Agents desktop. If it fails, tell the user; tests then run on the normal desktop. **Still open** (gamescope not installed): tests run on the normal desktop meanwhile; `cargo xtask game-test --display gamescope` is where it plugs in, and T1 to T3 must be proven under it later.

**Done when:** an agent runs the R2 wall scenarios with no human, and no window appears on the user's desktop.

## R3: movement 1:1 with the official game

1. **Timing RE:** the `0x2f4` tick message, the client's frame queue and playback (`0x142130440`, speed factors), where the per-frame dt comes from (InitialState `frame_ms` at world `+0x11c`, which we send as 33; frame-queue values read by `0x142130840`), whether official ticks carry a time. Output: a timing section in [movement.md](protocol/movement.md).
2. **Server clock:** deadline scheduling (no `tokio::time::interval` bursts), measured frame dt, catch-up rules after a stall, target 33 ms; the same dt goes to the simulation and, if the client reads one, the tick message.
3. **Server copies of what the client does alone:** action speed factor (attacks while walking, gap #6), sprint coasting (problem 5, needs the capture in R4.1), roll profile, the client pathfinder (`clientpath.rs`), stance changes, collision from R2. Also the one-in-four standing roll against a diagonal wall (4.8 cells off) and the one-waypoint deviation beside a moving entity (5 of 541 plans).
4. **Replay tests** for every input sequence of all official captures (extend the `locomotion.rs` fixtures). Not run yet: W pressed or released during a sprint (needs a combined key entry in the DLL).

**Done when:** every captured sequence replays identically (opcodes, fields, frame offsets).

## R4: entities, transitions, waypoints, world map

1. **Official capture (the user's, about 15 minutes):** checklist in [captures.md](re/captures.md#planned-capture-for-r4-world-map-waypoints-transitions-and-the-open-movement-cases). Tell the user when ready and stop every client job first.
2. **Object stage in `poe-world`:** objects of placed tiles (`.tmd`), rooms (`.arm`) and node tags, with cell and orientation, checked against the client's `entities.tsv` at scale. Sources: [entities.md](protocol/entities.md#where-world-objects-come-from).
3. **`AddObject` (`0x2f7`)** for transitions (including fog doors), waypoints and checkpoints, with the components the capture shows, spawned per instance. Static `server_only` objects with a hull (healing wells, benches, `StoneHengeAct*`) change the client's grid when sent: once the server sends them, stamp the hulls of the objects it actually spawned into its grid ([doodads.md](re/terrain/doodads.md#live-grid-and-server-side-objects)).
4. **Interaction:** clicking a transition sends the player to the connected area (`WorldAreas` connections or the object's target) at the matching transition; waypoint travel between unlocked waypoints. Add a game-test step that clicks a transition (needs a world-to-screen mapping; T3 has walk, roll and wall steps only).
4. **World map (M)** for acts 1 to 4 and the interludes, not the endgame: per-character unlock state (locked by default), what the client needs to show unlocks (from the capture), admin command `unlock <character> [acts|waypoints|all]` and lock, a web admin button.

**Done when:** an admin-unlocked character opens M in every act but the endgame, travels by waypoint and walks between areas without commands.

## After R4 (ask before starting)

**Game features, not started:** NPCs (StateMachine, quest states), monsters and spawns (`killzone`, `.arm` points of interest), chests, skills (replies `0x1ae`/`0x1af`/`0x1b1` are decoded, not sent), buffs, items, equipment, stash, passive tree, combat sync. Web admin inventory and passive panels wait for them. These unlock the deferred items: remote equipment visuals, dynamic obstacles in the pathfinder, party and trade accept/decline, parties.

**Small server and tooling items:**
- Data mods: `config_defaults` layering and server `opcodes` overlays ([mod-host.md](architecture/mod-host.md)).
- Web admin Players page shows class names.
- Ban commands in chat and the server CLI (only the web admin today).
- Rate limit on `GET /api/v1/mods/{id}/{version}.zip`.
- Launcher's nested client-hook pin (harmless; bump with the next launcher change).
- Client loose-file overrides and packet hooks for mods; launcher mod sync against a real server with mods.
- Audit leftovers: S-09 widen instance tickets to `u64`; C-01 pin CI actions by commit; S-13 re-review the launcher's token handling.
- Repo-wide `cargo fmt` in Poe2Server, then a CI check.
- Server release after R2 (ask first).

**Generator inputs the batches hold fixed** (needed for "any seed" in real play):
- Area level: G3_10's level 75+ path, the trial's rooms (UltimatumPlugin `0x141f101e0`).
- League and session state: roll outcomes, Incursion and extra-feature rooms, `unique<N>` lettered tags.
- Paths no tested job uses: listed in [terrain.md](status/terrain.md#not-ported-yet).
- The 39 combinations where the client errors on every seed; Sanctum_1-4, IncursionTemple(Present) and HideoutPietyArena have no comparable client result.
- Whether official servers make the world-map seed non-zero (needs a traced official town load).

**Unconfirmed in game:** Create/delete refusal texts, stale-login 0x0f and rate-limit messages; CharacterList unknown fields (+0x4f, +0x68, +0x74, +0x76; need a capture of a shapeshifted or supporter character); remote play from a second physical machine; a live client-hash update flow with renumbered opcodes (not derived automatically).

## Needs the user

| What | When |
|---|---|
| Install gamescope | now (T0) |
| Official capture, including movement problem 5 | R4.1 |
| G-PARTY capture (a friend answers party invite and trade request) | any time, implementation waits for items |
| Windows tests (launcher install and update, Host a server, Play, restart); needs a machine or VM | when available |
| Optional cleanup: unused `/PathOfExileSteam.exe` in Ghidra, `GameFiles-0.5.5e/` | any time |

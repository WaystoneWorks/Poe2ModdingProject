# Plan

The only list of what is left to do and the only status source. Edit it in place and delete what is finished: history belongs in git and [status/history.md](status/history.md). Limit: 1,500 words. User decisions behind this plan: [decisions.md](decisions.md). How to work: [guides/agent-workflow.md](guides/agent-workflow.md).

## Now: blocked on the user

R3 is done except what needs the official R4.1 capture; R4 step 1 is that capture too, and T0 needs gamescope. Nothing else is open without the user: see "Needs the user". Done in R3: step 1 (server clock, action speed factor, client pathfinder line of sight, stance changes) except sprint coasting; step 2 replay tests (98 official episodes: 64 identical, 34 in `fixtures/episodes/known.json` with a reason; stance rules; W pressed and released during a sprint in the `sprint-w` game test, drift at most 2.5 cells at the end, stream rules by `scripts/re/sprint_check.py`, [movement.md](protocol/movement.md#test-tooling)). Waits for the capture: problem 5 (the client ignores the unscaled `0x64` after a sprint with a stream too, coasts and restarts its walk 21 frames later; the model "coast, then walk on in the key direction" is not applied), gaps #2, #4, #6, #7. Open: the drop of the action speed factor to 0.3 at frame 7 is measured, not traced; no in-game attack test until characters have an attack skill; the standing roll that once ended 4.8 cells off against a diagonal wall (old `G1_1` layout, aimed at the cursor) was not reproduced. R2 open points: the `RoomOcclusion` link rests on offset arithmetic from `DisableDoors` and was not tested directly; the instance server builds the client-side grid until it sends the `server_only` objects.

## T: agents test in game by themselves

Every later step needs it. The official-server read-only latch stays untouched.

- **T0 Isolated display.** The user installs gamescope (`sudo pacman -S gamescope`). Try the client under nested or headless gamescope with Proton and the hook, and prove input injection and logs still work. It replaces the removed Agents desktop. If it fails, tell the user; tests then run on the normal desktop. **Still open** (gamescope not installed): tests run on the normal desktop meanwhile; `cargo xtask game-test --display gamescope` is where it plugs in, and T1 to T3 must be proven under it later.

Open: one clean client `ExitProcess(0)` mid-walk in `cliffs` (`runtime/game-test/cliffs-20261102-121814`), not reproduced in 4 runs.

**Done when:** an agent runs the wall scenarios (`walk`, `cliffs`, `dungeon`) with no human, and no window appears on the user's desktop.

## R3: movement 1:1 with the official game

1. **Server copies of what the client does alone:** left, all waiting for the R4.1 capture: sprint coasting (problem 5), stance toggle and weapon swap while moving (gap #7), attack lengths (gap #6), held-click restart (gap #2).
2. **Replay tests:** every official episode replays or is in `known.json` with a reason (attack length from game data, entry stance timing, held-click restart trigger, and the others there). W during a sprint: ours in `sprint-w`; the official answer waits for the R4.1 capture (gap #4).

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
| Official capture (about 15 minutes), [checklist](re/captures.md#planned-capture-for-r4-world-map-waypoints-transitions-and-the-open-movement-cases). Movement parts, all in step 6/7: problem 5 and gap #4 (W pressed or released during a sprint, step 6), gap #2 (hold the left button 5 s without rolling or attacking, step 6), gap #6 (attacks standing and in a plain walk, with attack-speed gear, step 6), gap #7 (input-mode toggle while walking, weapon swap, step 7) | R4.1, unblocks R3 and R4 |
| G-PARTY capture (a friend answers party invite and trade request) | any time, implementation waits for items |
| Windows tests (launcher install and update, Host a server, Play, restart); needs a machine or VM | when available |
| Decide whether old batch run directories may be deleted (disk 481 GB free; `grid50` 24 MB, `grid50ex` 691 MB, `flags3` small) | any time |
| Optional cleanup: unused `/PathOfExileSteam.exe` in Ghidra, `GameFiles-0.5.5e/` | any time |

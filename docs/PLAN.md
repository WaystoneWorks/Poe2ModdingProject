# Plan

The only list of what is left to do and the only status source. Edit it in place and delete what is finished: history belongs in git and [status/history.md](status/history.md). Limit: 1,500 words. User decisions behind this plan: [decisions.md](decisions.md). How to work: [guides/agent-workflow.md](guides/agent-workflow.md).

## Now: movement restart (exact port)

Principle and decision: [decisions.md](decisions.md#movement-and-world). The server must run an exact port of the client's movement code for all input modes (WASD, click-to-move, controller), roll and sprint. Proof is the user's game tests only; do not ask for one before step (e) is reached.

- (c) done: static RE in [re/movement-positioned.md](re/movement-positioned.md), [click](re/movement-click.md), [roll](re/movement-roll.md), [sprint](re/movement-sprint.md); open items in [wasd-movement.md](re/wasd-movement.md#what-is-left-to-read). Reference capture: `2026-11-03_13-16-29_336` ([captures.md](re/captures.md#planned-movement-capture-for-the-exact-port)).
- (d) One new port behind the seam (`poe_game::movement` `MovementModel`/`Mover`, [instance-world.md](architecture/instance-world.md#the-movement-seam-movementrs)), replacing the `standstill` stub chosen in the instance server's `actor_init`; checked offline against the captures, the kept fixtures (`modules/server/crates/poe-game/tests/fixtures/`) and private LINE logs. 
  - State (NOT GATED): the port (`poe_game::locomotion`) is behind the seam, chosen in `actor_init`, checked offline (`runtime/replay/check.sh`, local): own replay seg2 equal to the official client in all 1173 frames and 784 `0x64`; seg1 differs only near skills and two open items; server and client models agree in every frame (`--free`). All tests pass ([setup.md](guides/setup.md#build-and-test)). Speed stats are done for the stats that exist (class template, admin command `speed`); the gear/buff pipeline does not exist yet.
  - Open items: seg1 f3576 clipped coast one cell; f3669-3724 punch `0x80410041` root motion (skills out of scope); f3786-3915 one cell from a cursor roll during a held click (first heading source unread, [movement-roll.md](re/movement-roll.md#facing-event-first-heading-checked-by-replay)); stat 15916 omission and conditional speed stats need a stat calculator ([movement-positioned.md](re/movement-positioned.md#stats-the-server-sends-ported)); `own_replay`/`sim_replay` take travel 46.0 and level 4 by hand (tools only; the server reads game data).
- Agent game tests pass with the port (2026-11-03: `smoke`, `state`, `walk`, `sprint-w`, `cliffs`, `dungeon`; runs in `runtime/game-test/`).
- (e) User's game tests 2026-11-03. Test 1: minor hitching/snapping. Fixed (NOT GATED): the sprint's Bonk at a wall met at an angle coasts along it ([movement-sprint.md](re/movement-sprint.md)); the model had stopped and the next roll started up to 6 cells behind the client. Ruled out: input timing (answered at sent+1 like official; client never late), terrain (server grid = client grid, G1_8 seed 1), walk speed. Test 2 (after the fix, `POE_HOOK_MOVEMENT_LOG=1`): better, minor snaps left while sprinting and rolling. Test 2 analysed: three line divergences in the whole session (`runtime/replay/linediv.py`), all fixed (NOT GATED): rolls f2368 and f2802 out of the SprintEnd clip were backward rolls (model: forward), and f2802's 0.011-cell offset caused the sprint snap chain f2855-2866 ([movement-roll.md](re/movement-roll.md)); a wall Bonk coast f1451 runs at the clip's played rate (model: 1.5x slow, [movement-sprint.md](re/movement-sprint.md)). The walk "snaps" f540-662 and roll-end landings are the client's own line restarts on integer cells, not server snaps. Test 3: snaps after rolling and changing direction mid roll and in some sprint situations. Replay found 3 divergence runs (f1001-1053, f1837-1847, f1851-1904); causes fixed in the model ([movement-roll.md](re/movement-roll.md)); offline checks pass (seg1 grid_differ 175 unchanged, seg2 exact, user test 2 unchanged, sprint-turn all 411 cells equal, workspace 29 suites ok, live game test sprint-turn PASS with linediv 0 runs). User test 4 (with key log, `INPUT` lines work, [movement.md](protocol/movement.md#movement-trace)): the user reports it feels the same. Analysis: only 2 divergence runs (f2320-2376, f4019-4084); fixed in the model (queued-roll facing, roll started with axes set; [movement-roll.md](re/movement-roll.md)), NOT GATED. Much of what is seen as snaps may be the client's own motion (same discontinuities on the official server), to confirm with the user. Fixed (NOT GATED): the queued roll's clock ([movement-roll.md](re/movement-roll.md)); replay of test 4 is now equal to the client until the old server's snaps at f2345 and f4032, whose chains are rows from the old server, not model errors. The remaining single-frame `0x64` direction differences f3810, f4130, f4268 and the `0x1c8` f3793/f3794 are the old server's input arrival (the row echoes the previous input one frame late; same cell), not model errors. Offline after this: workspace tests all pass, check.sh 27 passed, ut2 4 grid_differ, st 411 equal, seg1 grid_differ 175, seg2 exact, live sprint-turn PASS with linediv 0 runs (`runtime/game-test/sprint-turn-20261103-203106`, port 48444). Trace file appends: `linediv.py` needs the port of that run's last session. Next: user test 5. Open small item: clipped coasts drift about 0.01 in the line accumulator (0x141f62210), 6 single frames in test 3, no cell changes.

## Now: R4

R4 below. The R4.1 capture is recorded: `2026-11-02_18-31-34_336` (not analysed for R4 yet). R3 is done.

Open: P5b game test fails 6-9 cells from drift before the sprint after a teleport (`runtime/game-test/p5-scenario-20261102-193003`, `-193626`); sprint-w, walk, cliffs, dungeon pass (2026-11-02). R2: the `RoomOcclusion` link rests on offset arithmetic from `DisableDoors` and was not tested directly; the instance server builds the client-side grid until it sends the `server_only` objects.

## T: agents test in game by themselves

Every later step needs it. The official-server read-only latch stays untouched.

Open: one clean client `ExitProcess(0)` mid-walk in `cliffs` (`runtime/game-test/cliffs-20261102-121814`), not reproduced in 4 runs.

**Done when:** an agent runs the wall scenarios (`walk`, `cliffs`, `dungeon`) with no human, and no window appears on the user's desktop.

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
| Official capture (about 15 minutes), [checklist](re/captures.md#planned-capture-for-r4-world-map-waypoints-transitions-and-the-open-movement-cases). Still missing for movement: swap and input-mode toggle while walking, rolling or attacking (gap #7), attacks with attack-speed gear (gap #6); R4 parts stay (steps 1-5) | R4.1, unblocks R4 |
| G-PARTY capture (a friend answers party invite and trade request) | any time, implementation waits for items |
| Windows tests (launcher install and update, Host a server, Play, restart); needs a machine or VM | when available |
| Decide whether old batch run directories may be deleted (disk 481 GB free; `grid50` 24 MB, `grid50ex` 691 MB, `flags3` small) | any time |
| Optional cleanup: unused `/PathOfExileSteam.exe` in Ghidra, `GameFiles-0.5.5e/` | any time |

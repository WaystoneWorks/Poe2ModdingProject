# Plan: R4 entities, transitions, waypoints, checkpoints, wells, world map

Step P12 of [../PLAN.md](../PLAN.md) (unchanged scope from the earlier plan, plus checkpoints and wells as the respawn and refill points that [life-flasks.md](life-flasks.md) needs, and the object data that [monsters.md](monsters.md) and [npcs-vendors.md](npcs-vendors.md) build on). R3 is done.

## State
- The R4.1 official capture is recorded: `2026-11-02_18-31-34_336` (not analysed for R4 yet; its movement parts were used for the movement port).
- Open: P5b game test fails 6-9 cells from drift before the sprint after a teleport (`runtime/game-test/p5-scenario-20261102-193003`, `-193626`); sprint-w, walk, cliffs, dungeon pass (2026-11-02). Recheck it with the exact movement port before R4 work.
- R2: the `RoomOcclusion` link rests on offset arithmetic from `DisableDoors` and was not tested directly; the instance server builds the client-side grid until it sends the `server_only` objects.

## Steps
1. **Official capture (the user's, about 15 minutes):** recorded (above); checklist in [../re/captures.md](../re/captures.md#planned-capture-for-r4-world-map-waypoints-transitions-and-the-open-movement-cases). Analyse its R4 parts (steps 1-5) first.
2. **Object stage in `poe-world`:** objects of placed tiles (`.tmd`), rooms (`.arm`) and node tags, with cell and orientation, checked against the client's `entities.tsv` at scale. Sources: [../protocol/entities.md](../protocol/entities.md#where-world-objects-come-from). The same stage yields monster spawn points (`killzone`, `.arm` points of interest) for P17 and NPC placements for P19.
3. **`AddObject` (`0x2f7`)** for transitions (including fog doors), waypoints, checkpoints and wells, with the components the capture shows, spawned per instance. Static `server_only` objects with a hull (healing wells, benches, `StoneHengeAct*`) change the client's grid when sent: once the server sends them, stamp the hulls of the objects it actually spawned into its grid ([../re/terrain/doodads.md](../re/terrain/doodads.md#live-grid-and-server-side-objects)).
4. **Interaction:** clicking a transition sends the player to the connected area (`WorldAreas` connections or the object's target) at the matching transition; waypoint travel between unlocked waypoints. **Checkpoints**: touching one sets the character's respawn point (stored) and shows the client's activation. **Wells**: using one refills life, mana and flask charges once life and flasks exist (the refill hook is a no-op until P13/P14). Add a game-test step that clicks a transition (needs a world-to-screen mapping; T3 has walk, roll and wall steps only). Transfers record the session's previous instance for the terrain-mismatch kick ([terrain-mismatch.md](terrain-mismatch.md)).
5. **World map (M)** for acts 1 to 4 and the interludes, not the endgame: per-character unlock state (locked by default), what the client needs to show unlocks (from the capture), admin command `unlock <character> [acts|waypoints|all]` and lock, a web admin button.

**Done when:** an admin-unlocked character opens M in every act but the endgame, travels by waypoint and walks between areas without commands; touching a checkpoint sets the respawn point.

## T: agents test in game by themselves
Every later step needs it. The official-server read-only latch stays untouched.
Open: one clean client `ExitProcess(0)` mid-walk in `cliffs` (`runtime/game-test/cliffs-20261102-121814`), not reproduced in 4 runs.
**Done when:** an agent runs the wall scenarios (`walk`, `cliffs`, `dungeon`) with no human, and no window appears on the user's desktop.

# Plan: R4 entities, transitions, waypoints, checkpoints, wells, world map

Step P9 of [../PLAN.md](../PLAN.md) (unchanged scope from the earlier plan, plus checkpoints and wells as the respawn and refill points that [life-flasks.md](life-flasks.md) needs, and the object data that [monsters.md](monsters.md) and [npcs-vendors.md](npcs-vendors.md) build on). R3 is done.

## State
- The R4.1 official capture is recorded: `2026-11-02_18-31-34_336` (not analysed for R4 yet; its movement parts were used for the movement port).
- Open: P5b game test fails 6-9 cells from drift before the sprint after a teleport (`runtime/game-test/p5-scenario-20261102-193003`, `-193626`); sprint-w, walk, cliffs, dungeon pass (2026-11-02). Recheck it with the exact movement port before R4 work.
- R2: the `RoomOcclusion` link rests on offset arithmetic from `DisableDoors` and was not tested directly; the instance server builds the client-side grid until it sends the `server_only` objects.

## Steps
1. **Official capture (the user's, about 15 minutes):** recorded (above); checklist in [../re/captures.md](../re/captures.md#planned-capture-for-r4-world-map-waypoints-transitions-and-the-open-movement-cases). Analyse its R4 parts (steps 1-5) first.
2. **Object stage in `poe-world`:** objects of placed tiles (`.tmd`), rooms (`.arm`) and node tags, with cell and orientation, checked against the client's `entities.tsv` at scale. Sources: [../protocol/entities.md](../protocol/entities.md#where-world-objects-come-from). The same stage yields monster spawn points (`killzone`, `.arm` points of interest) for P17 and NPC placements for P19.
3. **`AddObject` (`0x2f7`)** for transitions (including fog doors), waypoints, checkpoints and wells, with the components the capture shows, spawned per instance. Static `server_only` objects with a hull (healing wells, benches, `StoneHengeAct*`) change the client's grid when sent: once the server sends them, stamp the hulls of the objects it actually spawned into its grid ([../re/terrain/doodads.md](../re/terrain/doodads.md#live-grid-and-server-side-objects)).
4. **Interaction:** clicking a transition sends the player to the connected area (`WorldAreas` connections or the object's target) at the matching transition; every fog gate and sub-area transition works. **Waypoints** spawn in their areas; clicking one opens the client's waypoint travel to any unlocked waypoint. **Checkpoints** spawn; touching one sets the character's respawn point (stored) and shows the client's activation; clicking one teleports to another unlocked checkpoint (see the open RE question below). **Wells**: using one refills life, mana and flask charges once life and flasks exist (the refill hook is a no-op until P13/P14). Add a game-test step that clicks a transition (needs a world-to-screen mapping; T3 has walk, roll and wall steps only). The terrain-mismatch kick already returns players to the instance they left ([../protocol/instance.md](../protocol/instance.md#terrain-check)); it remembers every session's last place, so transitions and waypoints need nothing extra.
5. **World map (M)** for acts 1 to 4 and the interludes, not the endgame: per-character unlock state (locked by default), what the client needs to show unlocks (from the capture), the debug unlock commands and overlay buttons of [commands.md](commands.md) and [overlay.md](overlay.md) (act maps, waypoints, checkpoints), a web admin button.

## User decisions (2026-11-05)
- **World map (M)** works for all 4 acts and the interludes; no endgame for now.
- **Waypoints** spawn in their areas, and you can teleport between unlocked waypoints through them.
- **Debug unlock** of act maps and waypoints: a debug command (`unlock <character> act <n>`, `unlock <character> waypoint <area>`, `all`) and an overlay World button to unlock chosen act maps and waypoints.
- **Checkpoints** spawn. Clicking one teleports you to any other unlocked checkpoint, in addition to setting the respawn point. A debug command (`checkpoint unlock all`) and an overlay button unlock all checkpoints of the instance you are in.
- **Every fog gate area transition works**, sub-area transitions included.

**Open RE question:** does the client's own UI offer teleport between checkpoints, or does our overlay have to pick the destination? Clicking a checkpoint should offer the other unlocked checkpoints. Answer from the recorded capture `2026-11-02_18-31-34_336` and the client before building it.

**Open point (method):** how "every" fog gate and sub-area transition is checked: a game test or batch over the areas of acts 1-4 and the interludes. The implementer picks the method.

**Done when:** a character unlocked by the debug command or the overlay button opens M in all 4 acts and the interludes (not the endgame), travels by waypoint, teleports between unlocked checkpoints, walks through every fog gate and sub-area transition (checked by the method above), and touching a checkpoint sets the respawn point.

## T: agents test in game by themselves
Every later step needs it. The official-server read-only latch stays untouched.
Open: one clean client `ExitProcess(0)` mid-walk in `cliffs` (`runtime/game-test/cliffs-20261102-121814`), not reproduced in 4 runs.
**Done when:** an agent runs the wall scenarios (`walk`, `cliffs`, `dungeon`) with no human, and no window appears on the user's desktop.

# Plan: R4 entities, transitions, waypoints, checkpoints, wells, world map

Step P9 of [../PLAN.md](../PLAN.md) (unchanged scope from the earlier plan, plus checkpoints and wells as the respawn and refill points that [life-flasks.md](life-flasks.md) needs, and the object data that [monsters.md](monsters.md) and [npcs-vendors.md](npcs-vendors.md) build on). R3 is done.

## State
- RE: [../re/world-travel.md](../re/world-travel.md) has the capture's R4 parts and the client's messages. Step 1 is done.
- The P5b drift recheck passes with the exact movement port (`teleport-sprint`, 2 runs, at most 2.26 cells, 2026-11-05), so teleports are safe to build on.
- Code (WIP, NOT GATED): `poe_world::objects::travel_objects` (classes by `.ot` components, target rules), `poe-proto` messages and `travel_object_blob`, `Player.quest_flags`, store tables (migration 0011), `[travel]` config, `MoveEvent::Interact` with the walk into reach (`locomotion.rs`), actor spawning, `instance-server/src/travel.rs` (touch, click, hand-off, mask, flags, warp list), commands `unlock`, `lock`, `waypoint unlock all`, `checkpoint unlock all`, `travel status`.
- Batch: `area_objects --survey 1 <out>` over 106 areas: 356 gates. Rules: Entrance 208, NextConnection 12 (both fit the capture), Telepad 49 (tags only), Paired 54, Repeat 18, FirstConnection 15 (no evidence). 231 of 248 area links have a gate back. Generator fails at seed 1 on `G2_10_1` and `G4_14`; `G4_6` and `G4_8a` have no gate.
- Tested in game (2026-11-05, private server): `r4-objects`, `r4-click`, `r4-travel`, `r4-unlock`, `overlay-pages` (Travel row) pass ([setup.md](../guides/setup.md#game-tests-cargo-xtask-game-test)); the `click_cell` step, overlay Travel row, web admin Unlock and server-admin.md section exist. Wells are not spawned (`skip_objects`).
- Remaining: the checked-in batch for every transition (offline survey plus game tests), sample gate clicks in more areas, wells (no blob known), ctrl-click instance list in game, far-click walk drift in game (unit test only), the T item below.
- R2: the `RoomOcclusion` link rests on offset arithmetic from `DisableDoors` and was not tested directly; the instance server builds the client-side grid until it sends the `server_only` objects.

## Steps
1. **Official capture (the user's, about 15 minutes):** recorded (above); checklist in [../re/captures.md](../re/captures.md#planned-capture-for-r4-world-map-waypoints-transitions-and-the-open-movement-cases). Analyse its R4 parts (steps 1-5) first.
2. **Object stage in `poe-world`:** objects of placed tiles (`.tmd`), rooms (`.arm`) and node tags, with cell and orientation, checked against the client's `entities.tsv` at scale. Sources: [../protocol/entities.md](../protocol/entities.md#where-world-objects-come-from). The same stage yields monster spawn points (`killzone`, `.arm` points of interest) for P17 and NPC placements for P19.
3. **`AddObject` (`0x2f7`)** for transitions (including fog doors), waypoints, checkpoints and wells, with the components the capture shows, spawned per instance. Static `server_only` objects with a hull (healing wells, benches, `StoneHengeAct*`) change the client's grid when sent: once the server sends them, stamp the hulls of the objects it actually spawned into its grid ([../re/terrain/doodads.md](../re/terrain/doodads.md#live-grid-and-server-side-objects)).
4. **Interaction:** clicking a transition sends the player to the connected area (`WorldAreas` connections or the object's target) at the matching transition; every fog gate and sub-area transition works. **Waypoints** spawn in their areas; clicking one opens the client's waypoint travel to any unlocked waypoint. **Checkpoints** spawn; touching one sets the character's respawn point (stored) and shows the client's activation; clicking one teleports to another unlocked checkpoint (see the open RE question below). **Wells**: using one refills life, mana and flask charges once life and flasks exist (the refill hook is a no-op until P13/P14). The game-test step `click_cell` clicks a cell. The terrain-mismatch kick already returns players to the instance they left ([../protocol/instance.md](../protocol/instance.md#terrain-check)); it remembers every session's last place, so transitions and waypoints need nothing extra.
5. **World map (M)** for acts 1 to 4 and the interludes, not the endgame: per-character unlock state (locked by default), what the client needs to show unlocks (from the capture), the debug unlock commands and overlay buttons of [commands.md](commands.md) and [overlay.md](overlay.md) (act maps, waypoints, checkpoints), a web admin button.

## User decisions (2026-11-05)
- **World map (M)** works for all 4 acts and the interludes; no endgame for now.
- **Waypoints** spawn in their areas, and you can teleport between unlocked waypoints through them.
- **Debug unlock** of act maps and waypoints: a debug command (`unlock <character> act <n>`, `unlock <character> waypoint <area>`, `all`) and an overlay World button to unlock chosen act maps and waypoints.
- **Checkpoints** spawn. Clicking one teleports you to any other unlocked checkpoint, in addition to setting the respawn point. A debug command (`checkpoint unlock all`) and an overlay button unlock all checkpoints of the instance you are in.
- **Every fog gate area transition works**, sub-area transitions included.

**Answered:** the client's own area map offers checkpoint travel (`0x352` list, `0x353` request); the overlay does not pick destinations ([details](../re/world-travel.md#checkpoint-warp-the-client-has-the-ui)). A checkpoint click opens it (game test passes).

**Method for "every" transition (batch not built yet):** an offline batch over the areas of acts 1-4 and the interludes checks that each transition object has a target and a matching arrival, plus game tests that click sample transitions. State the coverage plainly when done.

**Done when:** a character unlocked by the debug command or the overlay button opens M in all 4 acts and the interludes (not the endgame), travels by waypoint, teleports between unlocked checkpoints, walks through every fog gate and sub-area transition (checked by the method above), and touching a checkpoint sets the respawn point.

## T: agents test in game by themselves
Every later step needs it. The official-server read-only latch stays untouched.
Open: one clean client `ExitProcess(0)` mid-walk in `cliffs` (`runtime/game-test/cliffs-20261102-121814`), not reproduced in 4 runs; the same once loading `G1_2` after a waypoint jump in `r4-travel`, not reproduced.
**Done when:** an agent runs the wall scenarios (`walk`, `cliffs`, `dungeon`) with no human, and no window appears on the user's desktop.

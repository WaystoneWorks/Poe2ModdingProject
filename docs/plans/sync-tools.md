# Plan: movement sync tools (T1)

Movement sync tools (T1). Approved by the user on 2026-11-19; order and status are in [../PLAN.md](../PLAN.md). Delete each step when done, and this file with the last one.

## Purpose
Stop finding B4 snaps one user test at a time: find every divergence between the server's movement copy (`modules/server/crates/poe-game/src/clientsim.rs`) and the client automatically.

Key fact ([server-code.md](../re/server-code.md#1-how-the-client-applies-a-correction)): a snap is exactly "server cell != client grid (Positioned `+0x444/+0x448`) when a non-zero `0x64` or a `StartAction` `0x1c8` is applied". Zero-vector `0x64`s never snap.

Model: O+S. Opus for the DLL hooks and the replay design, Sonnet agents for docs, the scripts' tests and test runs.

## Steps
1. Done (2026-11-19): the DLL's `snap_log` feature (on by default, [client-dll.md](../architecture/client-dll.md)) and `scripts/re/snaps.py <session> [--expect]`. Game test `snap-known` (a teleport onto the `G1_2` seed 1 checkpoint cell, then a WASD walk out) finds 2 snaps of 44.6 and 27.2 cells: the server's model stays inside the ring at (632,1391) while the client walks out to (676,1398). `walk` (now with `snaps.py` as `after`) checks 23 applies and finds no snap.
2. Done (2026-11-19): `scripts/re/first_divergence.py <session>` ([movement.md](../protocol/movement.md#test-tooling)); the movement log's `frame #N` line now ends with `dest (x, y) speed s` (signature fields `positioned.dest_*`, `positioned.speed_*`). Runs as an `after` report of `snap-known` and the `b4-*` tests. Results:
   - User test 4 (`GameFiles/logs/poe-hook/2026-11-19_14-15-23_336`): the replayed server sends the same messages as the live one in every compared frame. First divergences, all 1 to 1.4 cells and all in a roll steered by WASD (the client restarts its line every frame; the model runs about half a cell ahead): G1_2 visit 1 log frame 392, visit 2 frame 249, visit 3 frame 519; the town visit has none. These come before the user's jumps (frames 992 to 1101 in visit 1) and are a separate gap from the ring.
   - `snap-known`: first divergence at log frame 208 (client steps out of the checkpoint ring cell by cell, the model stays at (632,1391): the A* fallback), before its 44-cell snap at frame 300.
3. **Unported-code flags.** The DLL counts and logs (with the frame) hits on client functions not ported:
   - the A* fallback `0x141edc7d0` (start inside an entity);
   - the push test `0x141dee9e0` / `0x141df03c0`;
   - the step check's entity collision `0x141dfdb80`;
   - the clipped branch of the SprintEnd move event end `0x141f70e30`.

   The list lives in the coverage table (step 4).
   Done when: a warp onto the checkpoint logs the fallback.
4. **Coverage table** `docs/re/movement-coverage.md`: one row per client movement function with address, name, ported (where in `clientsim`/`clientpath`) or not, and hits per session from step 3.
   Done when: it lists every function named in `docs/re/movement-*.md`, `pathfinding.md` and the "Clicking an object" section of `world-travel.md`.
5. **Record and replay user sessions.** The game-test runner gets a mode that plays a session's logged keys and mouse events (screen coordinates, same timing) into a hidden client. Risk: clicks land differently if the camera differs; the step 2 report shows where the replay left the original.
   Done when: a replay of a user session reproduces its first snap.
6. **Then B4 in one batch** ([pre-p10.md](pre-p10.md#b4-snaps-at-checkpoints-and-waypoints)):
   - warp and respawn arrival outside the checkpoint's blocking ring;
   - port the A* fallback (spec in [server-code.md](../re/server-code.md#2-the-a-fallback-for-a-start-inside-an-entity)) with rules tests;
   - then the top gaps the tools rank;
   - one user test with the F1 performance overlay on ([debug-features.md](../re/debug-features.md#1-performance-overlay)).

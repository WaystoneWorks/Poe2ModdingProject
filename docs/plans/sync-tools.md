# Plan: movement sync tools (T1)

Movement sync tools (T1). Approved by the user on 2026-11-19; order and status are in [../PLAN.md](../PLAN.md). Delete each step when done, and this file with the last one.

## Purpose
Stop finding B4 snaps one user test at a time: find every divergence between the server's movement copy (`modules/server/crates/poe-game/src/clientsim.rs`) and the client automatically.

Key fact ([server-code.md](../re/server-code.md#1-how-the-client-applies-a-correction)): a snap is exactly "server cell != client grid (Positioned `+0x444/+0x448`) when a non-zero `0x64` or a `StartAction` `0x1c8` is applied". Zero-vector `0x64`s never snap.

Model: O+S. Opus for the DLL hooks and the replay design, Sonnet agents for docs, the scripts' tests and test runs.

## Steps
1. **Snap detector in the DLL** (`modules/client-hook`). For every non-zero `0x64` and every `0x1c8` applied to the local player, log the frame, the opcode, the server cell and the client's grid (`+0x444/+0x448`) before the apply; a `SNAP` line when they differ, with the distance. A script in `scripts/re/` lists a session's snaps.
   Done when: a game test with a known snap reports it and a clean one reports none.
2. **First-divergence report.** Extend the offline replay (`scripts/re/movement_replay_trace.py`, `modules/server/crates/poe-game/examples/sim_replay.rs`, made for official captures) to private sessions: replay the session's server messages and inputs into the sim and print the first frame where the sim's grid differs from the client's logged grid, with that frame's messages and both states. The movement log adds Positioned destination `+0x23c/+0x240/+0x244` (`+0x22d`/`+0x22e`) and speed `+0x274/+0x278` (field map: [debug-features.md](../re/debug-features.md#2-component-debug-printers)). Runs as an `after` step of the B4 game tests and on user sessions.
   Done when: it finds the first divergence of user test 4 (session `GameFiles/logs/poe-hook/2026-11-19_14-15-23_336`).
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

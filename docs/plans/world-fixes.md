# Plan: world fixes (B6, B7, M1, W1)

Steps added by the user on 2026-11-19; order and status are in [../PLAN.md](../PLAN.md). Delete each section when its step is done, and this file with the last one. Travel facts: [world-travel.md](../re/world-travel.md); instance and transfer protocol: [instance.md](../protocol/instance.md).

## B6: hideouts do not load
The client crashes 3 to 4 s after entering any hideout, with C++ exception `.?AVBufferUnderflow@Utility@@` ("Buffer Underflow"): it read past the end of something, most likely a message we send there.
- `HideoutDivine` (seed 1, instance 713877), 2026-11-19 22:28:05: session `GameFiles/logs/poe-hook/2026-11-19_22-27-09_336` (throw at hook time 1795145285.842), dump `runtime/crash-dumps/PoE-1795145285-336.dmp`, server log `runtime/b4/user-test6-server.log`.
- `HideoutExilecon23` (reached with `instance transfer HideoutExilecon23`), 22:31:52: session `GameFiles/logs/poe-hook/2026-11-19_22-31-05_336` (throw at 1795145512.442), server log `runtime/b4/user-test7-server.log`.
- A character saved in a hideout cannot log in again. Until B6 is fixed, move it offline (the backlog's character move command; for now a direct database edit with the server stopped).

1. Find the reader that throws: the crash's stack refs and the last inbound messages in `packets.txt` before it. Compare with an official hideout entry if a capture has one ([captures.md](../re/captures.md)).
2. Fix the message (or the missing one), from the client's reader in Ghidra and the capture, not by guessing fields.

Done when: a hidden game test enters every `WorldAreas` row with `IsHideout` and stays 30 s without a crash, unit tests for the fixed message, docs updated.

## B7: area transfers reconnect and freeze
Every area transfer (waypoint, gate, `transfer` command) looks like a disconnect and a reconnect, and the game freezes for a moment. Measured lead (2026-11-19, `runtime/b4/user-test7-server.log`): `instance transfer pending` at 22:31:44.559, `sending the client on` at 22:31:49.897: 5.3 s between them.

1. Compare with an official transfer in the captures: which messages, whether the client also reconnects to the instance server, and how long the loading screen lasts.
2. Time our transfer step by step (login server, ticket, instance start, terrain, first world message) and find where the 5.3 s goes.
3. Port the official sequence; make the wait no longer than the client's own loading.

Done when: a hidden game test times a waypoint transfer and a gate transfer against the official numbers, and world-travel.md describes the sequence.

## M1: world map state
The world map shows icons unlocked that should not be, and bosses as killed when they are not: either state left over from an official session in the client, or values we send that are wrong or random.

1. Static RE: which messages fill the map (unlocks, waypoints, boss kills, area completion), where the client keeps that state and what each field means; whether the client caches any of it on disk.
2. Capture C-MAP (the user's, official, read-only): the map opened at known progress states. M1 writes its checklist for CT ([pre-p10.md](pre-p10.md#ct-capture-checklist-tool)).
3. Implement per-character map state in the server and store, filled only from real progress.
4. A debug overlay editor for the map state (World page) and a debug command alongside it ([commands.md](commands.md)).

Done when: a new character's map shows nothing unlocked, a hidden game test checks unlocks and a boss kill, the editor and command change the map live, world-travel.md documents the state.

## W1: unused areas
The game data has areas the server does not know, so they cannot be visited. Make every `WorldAreas` row the client can load reachable with `transfer <area>`.

1. List the rows the server cannot host and why (no layout, no generator support, no spawn point, refused by the area list), from the terrain matrix ([terrain.md](../status/terrain.md)) and `area_probe`.
2. Fix by kind, never per area: generator support, spawn points from the area's own data, the area list.
3. The overlay's World page lists them.

Done when: a hidden game test visits a sample of every kind, the terrain matrix and world-travel.md are updated.

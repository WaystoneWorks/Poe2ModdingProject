# Plan: backlog (not ordered; pick up between steps or when a step needs it)

Items kept from the earlier plan, word for word where possible. Ordered work is in [../PLAN.md](../PLAN.md).

## Movement follow-ups (not blocking; movement is gated by user test 6)
- A mouse click during a sprint in WASD mode, then release: both rest one cell apart (client (623,1383), server (622,1382); `time scale 0.1`, `b4-sprint-click` 2026-11-06 before that case was dropped). No object involved.
- Rule tests for: blocked step stops steering, clip keeps rate, early unlimited roll turn, sprint-off key without a 0x64, no turn-around at the sprint switch, no Bonk when the blocked re-aim finds no path.
- Read why the early unlimited roll turn is 0.15 s (clientsim `roll_turn_to_target`: act `+0x244`, 0x14197fa55..0x14197fb68, 0x141d44b20) and which path listener turns off waypoint facing for key walks (`0x141dd9200` `FUN_140ecedc0`).
- A second crazy-keys seed with held clicks.
- `runtime/replay/ckruns.py`/`ckscore.sh` compare one frame off and linediv mixes areas (the hook frame counter restarts per area: split the hook log first).
- Open items of the port (d): seg1 f3576 clipped coast one cell; f3669-3724 punch `0x80410041` root motion (taken by P16 [skills.md](skills.md)); f3786-3915 one cell from a cursor roll during a held click (first heading source unread, [../re/movement-roll.md](../re/movement-roll.md#facing-event-first-heading-checked-by-replay)); stat 15916 omission and conditional speed stats: the calculator ([stats.md](../architecture/stats.md)) now supplies increased and final movement speed; `movement_velocity_+%_when_X` conditions need buff state (P10/P13); the omission pattern of 15916 is still unexplained and not tied to speed; `own_replay`/`sim_replay` take travel 46.0 and level 4 by hand (tools only; the server reads game data).
- Still missing from captures for movement: swap and input-mode toggle while walking, rolling or attacking (gap #7), attacks with attack-speed gear (gap #6). Both are in capture C2.

## Small server and tooling items
- Client crash on an instance transfer, about 1 in 15 test runs since before 0.5.5f (`walk` 2026-11-06, `r4-areas` and `r4-travel` 2026-11-05): an access violation in a Wine DLL about 0.7 s after the old instance disconnects, then the crash helper runs and the client exits 10 s later. `exit_trace` then shows the helper's `ExitProcess(0)`, not the cause: look for `crash] exception` in `poe-hook.log`.
- Data mods: `config_defaults` layering and server `opcodes` overlays ([../architecture/mod-host.md](../architecture/mod-host.md)).
- Web admin Players page shows class names.
- Rate limit on `GET /api/v1/mods/{id}/{version}.zip`.
- Launcher's nested client-hook pin (harmless; bump with the next launcher change).
- Client loose-file overrides and packet hooks for mods; launcher mod sync against a real server with mods.
- Audit leftovers: S-09 widen instance tickets to `u64`; S-13 re-review the launcher's token handling.
- Repo-wide `cargo fmt` in Poe2Server, then a CI check.
- Server release after R2 (ask first).

## World travel follow-ups (P9)
- Official `0x5a`, `0x98` come about 100 ms after the `ActionEvent` of an object click (slot 0's `Interaction` ends); ours in the same frame. No snap.
Facts: [world-travel.md](../re/world-travel.md).
- Wells: no captured blob and both guessed blobs hang the load, so they are not spawned (`[travel] skip_objects`); spawn and refill with P13.
- Instance list (`0xce`) row fields: decode the `u64` and `u32` (rows show "Closed" and 1970 dates).
- Quest-disabled gates: rooms tagged `*disabled` (e.g. `teleport3disabled-Arena`, `G1_8` boss gate (792,866)) come with quests; the client does not show (792,866).
- Generator failures: `G2_10_1`, `G4_14` (seed 1); `G2_1`, `G2_10_1`, `G3_5` (seed 2); `G1_14`, `G3_8` (seed 3).
- The exact `0xce`/`0xcf` and gate arrival rule (the server approximates).
- `r4-areas` failed once (client exited during `G3_6_1`'s load, "client disconnected during terrain generation" about 4 s after forcing the layout) and passed on rerun: unexplained, timing suspected, not caused by C1.

## Generator inputs the batches hold fixed (needed for "any seed" in real play)
- Area level: G3_10's level 75+ path, the trial's rooms (UltimatumPlugin `0x141f1e2c0`).
- League and session state: roll outcomes, Incursion and extra-feature rooms, `unique<N>` lettered tags.
- Paths no tested job uses: listed in [../status/terrain.md](../status/terrain.md#not-ported-yet).
- The 39 combinations where the client errors on every seed; Sanctum_1-4, IncursionTemple(Present) and HideoutPietyArena have no comparable client result.
- Whether official servers make the world-map seed non-zero (needs a traced official town load).

## Suggested in S1, not chosen
The user passed on these on 2026-11-05; offer them again only with a new reason.
- Panic handling (no `catch_unwind` in the server, 131 `unwrap`/`expect`/`panic!` in non-test instance-server code); fuzzing the decoders; a reconnect game test.
- A headless `poe-bot` client, a game test of the real client with a second player (remote blob, late join, `summon`, `tp <player>`, none run in game), a load test.
- The game-data half of P10; the P11 rolling engine and P15 tree rules ahead of their steps.
- `cargo xtask game-test all`; golden entry diff; non-admin and Console game tests.
- Log rotation; a server, hook and launcher release (server 4, hook 10, launcher 5 commits past `server-v0.6.1`, `hook-v0.5.3`, `v0.7.1`).

## Unconfirmed in game
Create/delete refusal texts, stale-login 0x0f and rate-limit messages; CharacterList unknown fields (+0x4f, +0x68, +0x74, +0x76; need a capture of a shapeshifted or supporter character); remote play from a second physical machine; a live client-hash update flow with renumbered opcodes (not derived automatically).

## Later game features (not in this plan)
Quests and quest states, trials and ascendancy trials, stash, trade, buffs beyond flasks and charms, ailments, mana costs and spirit reservation, leech, the endgame atlas, league mechanics behaviour, chests and breakables, socket currency, runes, soul cores, essences, omens, the rest of the skills.

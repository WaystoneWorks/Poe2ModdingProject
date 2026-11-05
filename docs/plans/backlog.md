# Plan: backlog (not ordered; pick up between steps or when a step needs it)

Items kept from the earlier plan, word for word where possible. Ordered work is in [../PLAN.md](../PLAN.md).

## Movement follow-ups (not blocking; movement is gated by user test 6)
- Rule tests for: blocked step stops steering, clip keeps rate, early unlimited roll turn, sprint-off key without a 0x64, no turn-around at the sprint switch, no Bonk when the blocked re-aim finds no path.
- Read why the early unlimited roll turn is 0.15 s (clientsim `roll_turn_to_target`: act `+0x244`, 0x1419746f5..0x141974808, 0x141d380a0) and which path listener turns off waypoint facing for key walks (`0x141dcc110` `FUN_140ec6320`).
- A second crazy-keys seed with held clicks.
- `runtime/replay/ckruns.py`/`ckscore.sh` compare one frame off and linediv mixes areas (the hook frame counter restarts per area: split the hook log first).
- Open items of the port (d): seg1 f3576 clipped coast one cell; f3669-3724 punch `0x80410041` root motion (taken by P16 [skills.md](skills.md)); f3786-3915 one cell from a cursor roll during a held click (first heading source unread, [../re/movement-roll.md](../re/movement-roll.md#facing-event-first-heading-checked-by-replay)); stat 15916 omission and conditional speed stats: the calculator ([stats.md](../architecture/stats.md)) now supplies increased and final movement speed; `movement_velocity_+%_when_X` conditions need buff state (P9/P13); the omission pattern of 15916 is still unexplained and not tied to speed; `own_replay`/`sim_replay` take travel 46.0 and level 4 by hand (tools only; the server reads game data).
- Still missing from captures for movement: swap and input-mode toggle while walking, rolling or attacking (gap #7), attacks with attack-speed gear (gap #6). Both are in capture C2.

## Small server and tooling items
- Data mods: `config_defaults` layering and server `opcodes` overlays ([../architecture/mod-host.md](../architecture/mod-host.md)).
- Web admin Players page shows class names.
- Ban commands in chat and the server CLI (only the web admin today). Fits the command overhaul ([commands.md](commands.md)): `player ban|unban`.
- Rate limit on `GET /api/v1/mods/{id}/{version}.zip`.
- Launcher's nested client-hook pin (harmless; bump with the next launcher change).
- Client loose-file overrides and packet hooks for mods; launcher mod sync against a real server with mods.
- Audit leftovers: S-09 widen instance tickets to `u64`; S-13 re-review the launcher's token handling.
- Repo-wide `cargo fmt` in Poe2Server, then a CI check.
- Server release after R2 (ask first).

## Generator inputs the batches hold fixed (needed for "any seed" in real play)
- Area level: G3_10's level 75+ path, the trial's rooms (UltimatumPlugin `0x141f101e0`).
- League and session state: roll outcomes, Incursion and extra-feature rooms, `unique<N>` lettered tags.
- Paths no tested job uses: listed in [../status/terrain.md](../status/terrain.md#not-ported-yet).
- The 39 combinations where the client errors on every seed; Sanctum_1-4, IncursionTemple(Present) and HideoutPietyArena have no comparable client result.
- Whether official servers make the world-map seed non-zero (needs a traced official town load).

## Unconfirmed in game
Create/delete refusal texts, stale-login 0x0f and rate-limit messages; CharacterList unknown fields (+0x4f, +0x68, +0x74, +0x76; need a capture of a shapeshifted or supporter character); remote play from a second physical machine; a live client-hash update flow with renumbered opcodes (not derived automatically).

## Later game features (not in this plan)
Quests and quest states, trials and ascendancy trials, stash, trade, buffs beyond flasks and charms, ailments, mana costs and spirit reservation, leech, the endgame atlas, league mechanics behaviour, chests and breakables, socket currency, runes, soul cores, essences, omens, the rest of the skills.

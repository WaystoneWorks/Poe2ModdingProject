# Plan: life, mana, energy shield, damage, death, flasks and charms

Steps P13 (pools, regeneration, damage taken, death) and P14 (flasks, charms, belt slots) of [../PLAN.md](../PLAN.md). Needs the stat calculator and items ([items-stats.md](items-stats.md)) and the checkpoints and wells of R4 ([world-travel.md](../re/world-travel.md)).

## User decisions (2026-11-04)
- First pass: **pools, regeneration and recovery** (max life, mana and ES from the calculator, regeneration ticks, ES recharge), and **damage taken and death** (monster hits and a debug command, the mitigation order, death, the death screen, resurrect at checkpoint or town). Hardcore death moves the character to the league's parent ([leagues.md](../guides/server-admin.md#leagues)).
- Not in the first pass: mana costs of skills, spirit reservation, leech and recoup.
- Death is **official-like**: death screen, resurrect at checkpoint, and the official XP penalty.
- Flasks: **life and mana flasks** (use by keys and controller, recovery over time, charges, quality, basic flask mods), **charms**, and **belt-dependent charm slots**.
- The exact messages come from **one combined official capture** (C2, [../re/captures.md](../re/captures.md)).

## P13: pools, regeneration, damage, death
1. **RE (Opus)** from C2 and the client: how current life, mana and ES reach the client (stat set values, a Life component update message, or both), how often official servers send them, what the client predicts (its own regeneration display), the hit message (damage numbers, which hit types), the death message, the death screen and its "Resurrect at checkpoint" / "Resurrect in town" request, the resurrect reply, and the XP penalty display. Results go to `docs/protocol/combat.md` (new).
2. **Pools** (`poe-game::life`): per actor `Pools { life, mana, es, max_* }` from the calculator; regeneration per server tick (life and mana regeneration rates, ES recharge delay and rate as PoB2's CalcDefence gives them); updates sent at the official rate and on every change bigger than the client's display step.
3. **Damage taken** pipeline, in PoB2's order (`CalcDefence`): evasion roll for evadable hits (PoB2's chance to evade formula and the entropy-free or entropy rule the game uses; check PoB2's notes), block roll, armour against physical (PoB2's armour formula), resistances (capped by max), ES before life except for the cases PoB2 lists, stun and ailment thresholds recorded (ailments themselves later). Inputs are a `Hit { damage by type, source, can_evade, can_block }`. Same pipeline for monsters (P17).
4. **Death**: life 0 kills the player: death message, the client's death screen, actions blocked. Resurrect at the last checkpoint touched (R4 checkpoints) or in town, full pools, flasks refilled. **XP penalty** at the official rate (research the 0.5 value and its level range from community sources and the client's death-screen text; config `[death] xp_penalty_percent` defaulting to it). **Hardcore**: the character moves to the HC league's parent (`variant_of` family's non-HC league, as the ending of a league does) and keeps playing there, as official.
5. **Commands**: `heal`, `god`, `nocost` (stored now, used by skills in P16), `damage <n> [type]`, `kill [player]`, `revive [player]`; overlay Debug > Life ([overlay.md](overlay.md)).
6. **Wells and checkpoints**: R4 spawns them; touching a well refills life, mana and flask charges; touching a checkpoint sets the respawn point.
- Done when: an agent game test takes `damage` hits (physical and each element) with known armour, evasion and resists and the life loss equals PoB2's expected damage taken; regeneration and ES recharge match PoB2's rates over 10 s; death shows the death screen, resurrect works at a checkpoint, the XP penalty is applied, and a hardcore death moves the character.

## P14: flasks, charms, belt
1. **RE (Opus)** from C2: the use-flask message (flask slot index; keys 1 and 2, controller), the flask effect (a buff on the player: minimal buff support, AddBuff and RemoveBuff or the client's equivalent), charge updates, charm triggers and their buffs.
2. **Flasks** (`Flasks.dat`, the flask's base and mods): recovery amount and duration, charges used and maximum, quality's effect, basic flask mods (increased recovery, increased charges, reduced charges used, instant recovery fractions, duration). Recovery applies per tick for the duration; overlapping uses follow the game's rule (research: queue or refresh).
3. **Charges**: refilled at wells, checkpoints and town; charge gain on kill comes with monsters (P17, by monster rarity, as the game does).
4. **Charms** (`Charms.dat`-style data in 0.5.5e, found with `poe-data`): triggers (on stun, freeze, ignite, shock, and the rest the basic charms have), their effect buff, charges; charm slots from the belt's stat (0 without a belt with charm slots).
5. **Belt**: charm slot count from the equipped belt; flask slots fixed at two as in game.
6. Overlay Debug > Life: flask charges and `[Refill]`; command `flask refill`.
- Done when: an agent game test uses both flasks by key and by controller input, recovery over time matches the flask data, charges drop and refill at a well, a charm triggers on its condition (forced with a debug command) and charm slots follow the belt.

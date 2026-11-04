# Plan: gems, skill bar and basic skills

Step P16 of [../PLAN.md](../PLAN.md). Needs items (gems are items), the calculator's `CalcOffence`/`CalcActiveSkill` ([items-stats.md](items-stats.md)) and pools ([life-flasks.md](life-flasks.md)). Hits on monsters come with P17 ([monsters.md](monsters.md)). Already known: skill replies `0x1ae`/`0x1af`/`0x1b1` are decoded but not sent; the movement port lists the punch root motion `0x80410041` (seg1 f3669-3724) as open ([../re/movement-positioned.md](../re/movement-positioned.md)).

## User decisions (2026-11-04)
- The **official gem panel**: uncut skill and support gems (from drops and the item creator) are cut into a chosen skill gem, support gems socket into the skill's support slots, skills appear on the skill bar and can be bound on **mouse, keyboard and controller** with the client's own bar UI.
- Skills that work in the first pass: **unarmed punch**, the **default attack of each weapon type**, and **one starter skill per class** (the class's starting gem).
- **Exact port of action timing** (animation timing, root motion, attack and cast speed), like movement, so the client is never snapped. Hits and damage are decided by the server.
- Controller works through the client; the server only needs the assignments and the input messages, and the game tests get a controller scenario.
- Other skills: used in game they answer with a chat line "skill not implemented: <name>" and do nothing.
- No mana costs and no spirit reservation in the first pass ([life-flasks.md](life-flasks.md#user-decisions-2026-11-04)).

## Steps
1. **Data** (`poe-data`): `SkillGems`, `GrantedEffects`, `GrantedEffectsPerLevel`, `GrantedEffectStatSets(PerLevel)`, `ActiveSkills`, `GemTags`, uncut gem bases and their cutting choices, support gem compatibility tags, weapon default attacks (the weapon class's implicit skill), the class starter gems.
2. **RE (Opus, re-tracer)** from C2 and the client:
   - Gem panel: cutting an uncut gem (request and reply), socketing and removing supports, gem levels and quality, the skill list the server sends (`0x1ae`/`0x1af`/`0x1b1` and the rest).
   - Skill bar: how bindings are stored and sent (the client may keep them locally or send them; per input mode: mouse and keyboard, controller).
   - Skill use: the use-skill message (skill id, target cell or entity, held or tapped), the server's action start, the action's duration and root motion. The client's own action timing (Actor actions `+0x238`/`+0x240`, `ActionTypes`, animation `.aoc` timing, attack speed scaling) ported into `poe_game::locomotion`'s actor model, with the punch root motion open item closed first.
   - Results go to `docs/protocol/skills.md` (new) and `docs/re/skills.md` (new).
3. **Gem panel and skill list** (`poe-game::skills`): skills of the character from its gems; support links checked by tags; levels from gem level plus `+N` stats; sent at login and on change.
4. **Skill use**: validate (skill exists, weapon requirement, not dead), start the action with the ported timing (attack or cast speed from the calculator), apply root motion through the movement port, and send what the official server sends. Replay check like the movement work: the C2 skill-use sequences replay with identical opcodes, fields and frame offsets.
5. **Effects of the first-pass skills**: punch and weapon default attacks (melee hit in an arc, or a projectile for ranged weapons, using the weapon's damage); starter skills per class with their real stats (damage, area, projectiles) from `GrantedEffectsPerLevel` and the calculator. Hit detection against monster hulls is server-side (P17); before P17 the skills animate and do nothing else.
6. **Commands**: `gem give`, `skill list`, `skill grant`; overlay Debug > Character (skills section) and Items (gem quick picks).
7. **Game tests**: new agent game test steps "use skill" for mouse and keyboard and for controller; zero divergence (as the movement linediv) while attacking during walks and rolls.
- Done when: a fresh character gets an uncut gem by command, cuts it into its class starter skill, sockets a support, binds it on mouse and keyboard and on controller, uses it and the default attack and punch while walking, rolling and standing without a single snap (divergence 0 over the test), and the skill's stats in the overlay match PoB2.

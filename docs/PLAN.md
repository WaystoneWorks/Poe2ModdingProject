# Plan

The only ordered list of what is left to do and the only status source. Each step has a detailed spec in [plans/](plans/backlog.md) (one file per feature), which is deleted or folded into the topic docs when the step is done. Edit both in place; history belongs in git and [status/history.md](status/history.md). Limit: 1,500 words. User decisions behind this plan: [decisions.md](decisions.md). How to work: [guides/agent-workflow.md](guides/agent-workflow.md).

Movement (the exact port) is done and gated by user test 6 (2026-11-04, [history](status/history.md)); its follow-ups are in the [backlog](plans/backlog.md#movement-follow-ups-not-blocking-movement-is-gated-by-user-test-6).

## Order
Steps run in this order, one per session (or several sessions for big ones). Model: **S** = Sonnet, **O** = Opus (RE or design), **O+S** = Opus designs or does the RE, then hands the routine parts to Sonnet agents. Sign-off is by agent tests (unit, offline checks, agent game tests in headless gamescope); movement keeps the user's game tests.

| Step | What | Model | Spec | Needs |
|---|---|---|---|---|
| P10 | Items, inventory, equipment, weapon sets, stats pipeline, levels and XP, not-implemented chat lines, web admin inventory | O+S | [items-stats.md](plans/items-stats.md#p10-items-inventory-equipment-weapon-sets-levels-opus-for-the-re-sonnet-for-storage-and-web-admin) | C2 |
| P11 | Currency: mod rolling engine, basic orbs, quality currency, gold | O+S | [items-stats.md](plans/items-stats.md#p11-currency-opus-for-the-rules-sonnet-for-tests) | P10 |
| P12 | Item creator and spawner (overlay with art, commands, paste, templates, random, edit in place) | O+S | [item-creator.md](plans/item-creator.md) | P11 |
| P13 | Life, mana, ES, regeneration, damage taken, death and resurrect | O+S | [life-flasks.md](plans/life-flasks.md#p13-pools-regeneration-damage-death) | P10, P9, C2 |
| P14 | Flasks, charms, belt charm slots | O+S | [life-flasks.md](plans/life-flasks.md#p14-flasks-charms-belt) | P13 |
| P15 | Passive tree, ascendancies, weapon-set points, class changer, web admin tree | O+S | [passives.md](plans/passives.md) | P10 |
| P16 | Gems, skill bar (mouse and keyboard, controller), punch, default attacks, class starter skills | O | [skills.md](plans/skills.md) | P13, C2 |
| P17 | Monsters of the Riverbank and Clearfell, AI from game data, combat, XP from kills, monster tools | O | [monsters.md](plans/monsters.md) | P9, P16 |
| P18 | Loot drops, ground items, gold, parties, allocation by the party leader | O+S | [loot-parties.md](plans/loot-parties.md) | P17, G-PARTY |
| P19 | NPCs and vendors | O+S | [npcs-vendors.md](plans/npcs-vendors.md) | P9, P11 |

## Now
- **P1** to **P7** are done (P4: terrain check at area entry, kick to the previous instance, the act's town or character select, DLL popup with layout export; game test `terrain-mismatch` passes and `walk`, `cliffs`, `dungeon` never trigger it. P5: progress tracker site, `cargo xtask tracker gen|check|build|edit`, [guide](guides/tracker.md); the Pages workflow runs once the hub is on GitHub; 2026-11-04). **P6** (overlay layout overhaul: every page, merges, Debug shell; game test `overlay-pages` takes a screenshot per page) is done too (2026-11-04). **P7** (command framework v2: subcommands, aliases, flags, levels, searchable help, Console, `time scale`; game test `commands`) is done (2026-11-04). League fixes (web admin form fits, DLL Minimap page removed, store and web admin moves, hardcore death rule) are done too, and **P7b** (the client's League Migrations window, [login.md](protocol/login.md#league-migrations); game test `leagues`; 2026-11-05). **P8** (`poe-stats`, [stats.md](architecture/stats.md)) is done: the calculator, corpus of 72 and sweep agree with PoB2, login stats come from the calculator; the geared list needs C2 and moved to P10. **P9** (R4: transitions, waypoints, checkpoints, unlocks, world map; [world-travel.md](re/world-travel.md); game tests `r4-objects`, `r4-click`, `r4-travel`, `r4-unlock`, `r4-areas`, `r4-ctrl`, `r4-gates`) is done (2026-11-05); wells and the open gate items are in the [backlog](plans/backlog.md#world-travel-follow-ups-p9). P10 (items) waits for capture C2, which the user cannot record now.

## Needs the user

| What | When |
|---|---|
| Capture **C2** (gameplay, 30-40 minutes, [checklist](re/captures.md#planned-capture-c2-for-gameplay-items-stats-life-flasks-passives-skills-monsters-loot-npcs)); it also covers the movement gaps #6 and #7 | any time before P10 |
| G-PARTY capture (a friend answers party invite and trade request) | before P18 |
| Windows tests (launcher install and update, Host a server, Play, restart); needs a machine or VM | when available |
| Decide whether old batch run directories may be deleted (disk 481 GB free; `grid50` 24 MB, `grid50ex` 691 MB, `flags3` small) | any time |
| Optional cleanup: unused `/PathOfExileSteam.exe` in Ghidra, `GameFiles-0.5.5e/` | any time |

## Backlog
Not ordered: [plans/backlog.md](plans/backlog.md) (movement follow-ups, small server and tooling items, generator inputs, unconfirmed in game, later game features).

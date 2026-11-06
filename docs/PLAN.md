# Plan

The only ordered list of what is left to do and the only status source. Each step has a detailed spec in [plans/](plans/backlog.md) (one file per feature), which is deleted or folded into the topic docs when the step is done. Edit both in place; history belongs in git and [status/history.md](status/history.md). Limit: 1,500 words. User decisions behind this plan: [decisions.md](decisions.md). How to work: [guides/agent-workflow.md](guides/agent-workflow.md).

Movement (the exact port) is done and gated by user test 6 (2026-11-04, [history](status/history.md)); its follow-ups are in the [backlog](plans/backlog.md#movement-follow-ups-not-blocking-movement-is-gated-by-user-test-6).

## Order
Steps run in this order, one per session (or several sessions for big ones). Model: **S** = Sonnet, **O** = Opus (RE or design), **O+S** = Opus designs or does the RE, then hands the routine parts to Sonnet agents. Sign-off is by agent tests (unit, offline checks, agent game tests in headless gamescope); movement keeps the user's game tests.

| Step | What | Model | Spec | Needs |
|---|---|---|---|---|
| V1 | Game update 0.5.5f: the whole project moves to the new build (in progress, NOT GATED, state in the spec) | O | [pre-p10.md](plans/pre-p10.md#v1-game-update-055f) | updated Steam install |
| B4 | Slight snaps when interacting with checkpoints and waypoints | O | [pre-p10.md](plans/pre-p10.md#b4-snaps-at-checkpoints-and-waypoints) | V1 |
| U4 | Launcher and web admin layout: reviewer loop to 9.5/10 with a consistency score, News "Read more" bug, version label on the left | O | [pre-p10.md](plans/pre-p10.md#u4-launcher-and-web-admin-layout) | |
| U5 | DLL overlay layout: reviewer loop to 9.5/10 | O | [pre-p10.md](plans/pre-p10.md#u5-dll-overlay-layout) | V1 |
| CT | Capture checklist tool with user-set keybindings | O+S | [pre-p10.md](plans/pre-p10.md#ct-capture-checklist-tool) | V1 |
| B2 | Bad seeds: a new instance only gets a seed the client accepts, no 30 s wait and kick | O | [pre-p10.md](plans/pre-p10.md#b2-bad-seeds) | |
| B3 | Intro flag set when the wake-up ends, not at entry | O | [pre-p10.md](plans/pre-p10.md#b3-intro-flag) | |
| A1 | `player ban`, `unban`, `ban ip` in chat, overlay and CLI | S | [pre-p10.md](plans/pre-p10.md#a1-ban-commands) | |
| A2 | Automatic database backups as a scheduled task with retention | S | [pre-p10.md](plans/pre-p10.md#a2-automatic-database-backups) | |
| P10a | Static RE of the item blob and inventory messages, C2 checklist checked against it | O | [pre-p10.md](plans/pre-p10.md#p10a-static-re-of-items-before-c2) | |
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
- **P1** to **P7** are done (P4: terrain check at area entry, kick to the previous instance, the act's town or character select, DLL popup with layout export; the kick logic is covered by `terrain_check` unit tests and `walk`, `cliffs`, `dungeon` never trigger it. P5: progress tracker site, `cargo xtask tracker gen|check|build|edit`, [guide](guides/tracker.md); the Pages workflow runs once the hub is on GitHub; 2026-11-04). **P6** (overlay layout overhaul: every page, merges, Debug shell; game test `overlay-pages` takes a screenshot per page) is done too (2026-11-04). **P7** (command framework v2: subcommands, aliases, flags, levels, searchable help, Console, `time scale`; game test `commands`) is done (2026-11-04). League fixes (web admin form fits, DLL Minimap page removed, store and web admin moves, hardcore death rule) are done too, and **P7b** (the client's League Migrations window, [login.md](protocol/login.md#league-migrations); game test `leagues`; 2026-11-05). **P8** (`poe-stats`, [stats.md](architecture/stats.md)) is done: the calculator, corpus of 72 and sweep agree with PoB2, login stats come from the calculator; the geared list needs C2 and moved to P10. **P9** (R4: transitions, waypoints, checkpoints, unlocks, world map; [world-travel.md](re/world-travel.md); game tests `r4-objects`, `r4-click`, `r4-travel`, `r4-unlock`, `r4-areas`, `r4-ctrl`, `r4-gates`) is done (2026-11-05); wells and the open gate items are in the [backlog](plans/backlog.md#world-travel-follow-ups-p9). **C1** (config cleanup: the server is the terrain authority, client terrain upload, research switches and account placeholders removed; [config in setup.md](guides/setup.md#config)) is done (2026-11-05). **U1** (launcher UI review loop) is done: 9/10 after seven reviewer rounds (2026-11-05). **U2** (web admin UI review loop) is done: 9/10 after four rounds (2026-11-05). **U3** (DLL overlay UI review loop) is done: 9/10 after eight rounds (2026-11-05). **B1** (Riverbank intro: the movement-type dialog, spawn cell and facing, no walk in the wake-up; [washed-up.md](re/washed-up.md); game tests `washed-up`, `washed-up-mouse`) is done (2026-11-05). **S1** (suggestions before P10) is done: the user chose B2, B3, A1, A2 and P10a (2026-11-05). The user added V1, B4, U4, U5 and CT ahead of them (2026-11-06). Next: V1, then the table's order; P10 (items) waits for capture C2.

## Needs the user

| What | When |
|---|---|
| Capture **C2** (gameplay, 30-40 minutes, [checklist](re/captures.md#planned-capture-c2-for-gameplay-items-stats-life-flasks-passives-skills-monsters-loot-npcs)); it also covers the movement gaps #6 and #7 | after CT, before P10 |
| G-PARTY capture (a friend answers party invite and trade request) | before P18 |
| Windows tests (launcher install and update, Host a server, Play, restart); needs a machine or VM | when available |
| Decide whether old batch run directories may be deleted (disk 481 GB free; `grid50` 24 MB, `grid50ex` 691 MB, `flags3` small) | any time |
| Optional cleanup: unused `/PathOfExileSteam.exe` in Ghidra, `GameFiles-0.5.5e/` | any time |

## Backlog
Not ordered: [plans/backlog.md](plans/backlog.md) (movement follow-ups, small server and tooling items, generator inputs, unconfirmed in game, later game features).

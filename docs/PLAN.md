# Plan

The only ordered list of what is left to do and the only status source. Each step has a detailed spec in [plans/](plans/backlog.md) (one file per feature), which is deleted or folded into the topic docs when the step is done. Edit both in place; history belongs in git and [status/history.md](status/history.md). Limit: 1,500 words. User decisions behind this plan: [decisions.md](decisions.md). How to work: [guides/agent-workflow.md](guides/agent-workflow.md).

Movement (the exact port) is done and gated by user test 6 (2026-11-04, [history](status/history.md)); its follow-ups are in the [backlog](plans/backlog.md#movement-follow-ups-not-blocking-movement-is-gated-by-user-test-6).

## Order
Steps run in this order, one per session (or several sessions for big ones). Model: **S** = Sonnet, **O** = Opus (RE or design), **O+S** = Opus designs or does the RE, then hands the routine parts to Sonnet agents. Sign-off is by agent tests (unit, offline checks, agent game tests in headless gamescope); movement keeps the user's game tests.

| Step | What | Model | Spec | Needs |
|---|---|---|---|---|
| P3 | Leagues in the database, web admin Leagues page, "needs a league" popup, variants, LeagueFlag banners, mechanics list, dates, lifecycle | O+S | [leagues.md](plans/leagues.md) | |
| P4 | Terrain mismatch: compare tile and doodad hash at entry, kick to the previous instance or town, DLL alert with export | S | [terrain-mismatch.md](plans/terrain-mismatch.md) | |
| P5 | Progress tracker site (static, statuses in `tracker/status.toml`, rows from game data) | S | [tracker.md](plans/tracker.md) | |
| P6 | Overlay layout overhaul of every page, merges, Debug shell | S | [overlay.md](plans/overlay.md#p6-layout-overhaul) | P1 |
| P7 | Command framework v2: subcommands, aliases, flags, levels, searchable help, Console, rework of existing commands, world tools | O+S | [commands.md](plans/commands.md) | P6 |
| P8 | `poe-stats`: PoB2 calculation port, stat map, stat-description formatter, PoB2 cross-check | O+S | [items-stats.md](plans/items-stats.md#p8-poe-stats-crate-the-pob2-port-opus-design-sonnet-for-the-mapping-tables-and-tests) | |
| P9 | Items, inventory, equipment, weapon sets, stats pipeline, levels and XP, not-implemented chat lines, web admin inventory | O+S | [items-stats.md](plans/items-stats.md#p9-items-inventory-equipment-weapon-sets-levels-opus-for-the-re-sonnet-for-storage-and-web-admin) | P7, P8, C2 |
| P10 | Currency: mod rolling engine, basic orbs, quality currency, gold | O+S | [items-stats.md](plans/items-stats.md#p10-currency-opus-for-the-rules-sonnet-for-tests) | P9 |
| P11 | Item creator and spawner (overlay with art, commands, paste, templates, random, edit in place) | O+S | [item-creator.md](plans/item-creator.md) | P10 |
| P12 | R4: object stage, transitions, waypoints, checkpoints, wells, world map; T | O | [r4-world.md](plans/r4-world.md) | |
| P13 | Life, mana, ES, regeneration, damage taken, death and resurrect | O+S | [life-flasks.md](plans/life-flasks.md#p13-pools-regeneration-damage-death) | P9, P12, C2 |
| P14 | Flasks, charms, belt charm slots | O+S | [life-flasks.md](plans/life-flasks.md#p14-flasks-charms-belt) | P13 |
| P15 | Passive tree, ascendancies, weapon-set points, class changer, web admin tree | O+S | [passives.md](plans/passives.md) | P9 |
| P16 | Gems, skill bar (mouse and keyboard, controller), punch, default attacks, class starter skills | O | [skills.md](plans/skills.md) | P13, C2 |
| P17 | Monsters of the Riverbank and Clearfell, AI from game data, combat, XP from kills, monster tools | O | [monsters.md](plans/monsters.md) | P12, P16 |
| P18 | Loot drops, ground items, gold, parties, allocation by the party leader | O+S | [loot-parties.md](plans/loot-parties.md) | P17, G-PARTY |
| P19 | NPCs and vendors | O+S | [npcs-vendors.md](plans/npcs-vendors.md) | P12, P10 |

P3 to P7 are independent of the game work and mostly Sonnet; P8 can start any time (offline). The R4 capture is recorded, so P12 can also be moved earlier when an Opus session is free.

## Now
- **P1** and **P2** are done. **P3** (leagues) is built and agent-tested (store, login list, CLI, web API, art endpoint, web admin page, launcher; game tests `leagues` and `leagues-none` pass, 2026-11-04) but NOT GATED: left are the `leagues` game test creating Dawn through `POST /api/v1/admin/leagues`, the docs (login.md LeagueEntry, setup.md, launcher.md) and folding [plans/leagues.md](plans/leagues.md).

## Needs the user

| What | When |
|---|---|
| Capture **C2** (gameplay, 30-40 minutes, [checklist](re/captures.md#planned-capture-c2-for-gameplay-items-stats-life-flasks-passives-skills-monsters-loot-npcs)); it also covers the movement gaps #6 and #7 | any time before P9 |
| G-PARTY capture (a friend answers party invite and trade request) | before P18 |
| Windows tests (launcher install and update, Host a server, Play, restart); needs a machine or VM | when available |
| Decide whether old batch run directories may be deleted (disk 481 GB free; `grid50` 24 MB, `grid50ex` 691 MB, `flags3` small) | any time |
| Optional cleanup: unused `/PathOfExileSteam.exe` in Ghidra, `GameFiles-0.5.5e/` | any time |

## Backlog
Not ordered: [plans/backlog.md](plans/backlog.md) (movement follow-ups, small server and tooling items, generator inputs, unconfirmed in game, later game features).

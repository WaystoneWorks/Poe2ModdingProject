# Documentation index

Private server for Path of Exile 2 (client **0.5.5e Hotfix 1**), in Rust. Rules: [../CLAUDE.md](../CLAUDE.md). Repositories: [overview.md](overview.md). Start with [guides/setup.md](guides/setup.md), then [architecture/overview.md](architecture/overview.md). Contributing, security, legal: [../CONTRIBUTING.md](../CONTRIBUTING.md), [../SECURITY.md](../SECURITY.md), [disclaimer](../README.md#disclaimer).

## Guides
| Document | Contents |
|---|---|
| [guides/setup.md](guides/setup.md) | Commands, logs, unattended tests, config keys, crash dumps |
| [re/steam-shortcut.md](re/steam-shortcut.md) | Playing the private server from Steam (shortcut) |
| [guides/server-admin.md](guides/server-admin.md) | Server commands, admins, instances, web admin |
| [hosting.md](../modules/server/docs/hosting.md) | Hosting a server: ports, config, systemd, TLS, backups |
| [releasing.md](../modules/server/docs/releasing.md) | Releasing the server (`server-v*`) |
| [guides/official-mode.md](guides/official-mode.md) | Read-only observation of official sessions |
| [guides/client.md](guides/client.md) | Installing the client through the launcher or by hand |
| [guides/new-game-version.md](guides/new-game-version.md) | Supporting a new client build |
| [guides/releasing-hook.md](guides/releasing-hook.md) | Releasing the client hook (`hook-v*`) |
| [guides/launcher.md](guides/launcher.md) | The player launcher |
| [guides/modding.md](guides/modding.md) | Server and client modding hooks |
| [server-list-template/README.md](server-list-template/README.md) | Template of the `Poe2ServerList` repository |
| [mod-index-template/README.md](mod-index-template/README.md) | Template of the `Poe2Mods` repository |
| [guides/agent-workflow.md](guides/agent-workflow.md) | How agents work |
| [guides/tracker.md](guides/tracker.md) | The progress tracker site: statuses, rows, `cargo xtask tracker` |

## Architecture
| Document | Contents |
|---|---|
| [architecture/overview.md](architecture/overview.md) | Data flow and design rules |
| [architecture/crates.md](architecture/crates.md) | Crates and submodules |
| [architecture/client-dll.md](architecture/client-dll.md) | Client DLLs: loader, core, overlay, capture, features |
| [architecture/accounts.md](architecture/accounts.md) | Accounts, tokens, login paths, admins |
| [architecture/instance-world.md](architecture/instance-world.md) | Instance actor, world, movement component |
| [architecture/web-api.md](architecture/web-api.md) | Web API and web admin |
| [architecture/mod-host.md](architecture/mod-host.md) | Server mod host |
| [architecture/stats.md](architecture/stats.md) | Stat calculator `poe-stats`, PoB2 cross-check, stats the server sends |
| [openapi.json](../modules/server/docs/openapi.json) | Generated OpenAPI document |

## Protocol
| Document | Contents |
|---|---|
| [protocol/framing.md](protocol/framing.md) | Encodings, framing, encryption |
| [protocol/login.md](protocol/login.md) | Login messages and hand-off |
| [protocol/instance.md](protocol/instance.md) | Instance messages |
| [protocol/entities.md](protocol/entities.md) | Entity blobs, other players, party, trade |
| [protocol/movement.md](protocol/movement.md) | Lockstep movement |
| [protocol/side-channel.md](protocol/side-channel.md) | DLL to server side channel |

## Reverse engineering and data
| Document | Contents |
|---|---|
| [re/README.md](re/README.md) | How the client is analysed |
| [re/addresses.md](re/addresses.md) | Ghidra addresses |
| [re/update-compatibility.md](re/update-compatibility.md) | What breaks on a new build |
| [re/standalone-login.md](re/standalone-login.md) | Standalone login patch |
| [re/crypto.md](re/crypto.md) | Key exchange and Salsa20 |
| [re/datamining.md](re/datamining.md) | Bundles2 and `.datc64` |
| [re/captures.md](re/captures.md) | Official vs our server, client log |
| [re/wasd-movement.md](re/wasd-movement.md) | Client movement overview, open RE items |
| [re/movement-positioned.md](re/movement-positioned.md) | Exact port: WASD/gamepad, Positioned, line, speed |
| [re/movement-click.md](re/movement-click.md) | Exact port: click-to-move |
| [re/movement-roll.md](re/movement-roll.md) | Exact port: dodge roll |
| [re/movement-capture-index.md](re/movement-capture-index.md) | Movement capture indexes (2026-10-20, 2026-11-02 sessions) |
| [re/movement-sprint.md](re/movement-sprint.md) | Exact port: sprint, end, coast |
| [re/world-travel.md](re/world-travel.md) | Transitions, waypoints, checkpoints, world panel: client facts |
| [re/time-scale.md](re/time-scale.md) | Slowing the simulation with `0x2f5` (`time scale`) |
| [re/terrain/README.md](re/terrain/README.md) | Terrain generator overview |
| [re/terrain/tgr.md](re/terrain/tgr.md) | `.tgr` areas |
| [re/terrain/dungeon.md](re/terrain/dungeon.md) | `.dgr` areas |
| [re/terrain/shared-passes.md](re/terrain/shared-passes.md) | Passes both kinds share |
| [../dumps/README.md](../dumps/README.md) | `dumps/<version>/` |

## Plan, status, research
| Document | Contents |
|---|---|
| [PLAN.md](PLAN.md) | **What is left to do and the current state: start here** |
| [plans/overlay.md](plans/overlay.md) | Debug tab mockups still to build (feature steps) |
| [plans/commands.md](plans/commands.md) | Commands still to add per step (registry v2 is current) |
| [plans/items-stats.md](plans/items-stats.md) | Plan P10-P11: items, currency |
| [plans/item-creator.md](plans/item-creator.md) | Plan P12: item creator |
| [plans/life-flasks.md](plans/life-flasks.md) | Plan P13, P14: life, damage, death, flasks, charms |
| [plans/passives.md](plans/passives.md) | Plan P15: passive tree, ascendancies, class changer |
| [plans/skills.md](plans/skills.md) | Plan P16: gems, skill bar, basic skills |
| [plans/monsters.md](plans/monsters.md) | Plan P17: monsters, AI, XP |
| [plans/loot-parties.md](plans/loot-parties.md) | Plan P18: loot, parties |
| [plans/npcs-vendors.md](plans/npcs-vendors.md) | Plan P19: NPCs, vendors |
| [plans/backlog.md](plans/backlog.md) | Unordered backlog |
| [decisions.md](decisions.md) | Settled user decisions |
| [status/terrain.md](status/terrain.md) | Terrain status |
| [status/terrain-matrix.tsv](status/terrain-matrix.tsv) | Generated terrain match table (`cargo xtask terrain-matrix`) |
| [status/history.md](status/history.md) | What was built when |
| [research/poe1-prior-art.md](research/poe1-prior-art.md) | PoE1 research |
| [research/tools.md](research/tools.md) | Datamining and RE tools |
| [../modules/client-hook/docs/mod-manifest.md](../modules/client-hook/docs/mod-manifest.md) | `mod.toml` spec and mod ABI |

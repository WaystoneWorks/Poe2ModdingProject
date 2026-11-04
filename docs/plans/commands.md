# Plan: debug command overhaul (server commands and the overlay Debug tab)

Step P7 of [../PLAN.md](../PLAN.md) builds the framework, Help, Console and the rework of the existing commands. Every later feature step adds its own commands and the matching overlay controls (listed below with the step that delivers them). Today: one registry `modules/server/servers/instance-server/src/commands.rs` (`Spec { name, group, admin, args, help }`, arg `Kind`s), execution in `exec.rs`, chat prefix `!` (`[commands] prefix`), the overlay builds a generic form per command from the registry over the debug link ([../guides/server-admin.md](../guides/server-admin.md#commands)). Mods add commands ([../architecture/mod-host.md](../architecture/mod-host.md)).

## User decisions (2026-11-04)
- Two permission levels only: **player** and **admin**. Every cheat command is admin-only.
- **Verb-first syntax with subcommands**, e.g. `!item give <base> [--ilvl 82] [--rarity rare] [--ground]`, `!stat add <stat> <value> [--kind increased]`, `!level set 90`, `!points passive add 10`, `!class set Warrior Titan`, with aliases for common ones (`!lvl`, `!tp`).
- **Every command has an overlay counterpart** in the one Debug entry with sub-tabs ([overlay.md](overlay.md#debug-help--console--character--stats--items--world--monsters--life--players)). The generic Commands page goes; a raw Console tab stays.
- Non-admins do not see admin-only commands in `!help`, in the Console's completion, or in the overlay.
- `!help` and the Help tab are **searchable and generated from the registry**.
- Stat edits are a **debug modifier layer** in the stat calculator, saved per character and removable.
- Class change keeps level, XP, items and gold; it resets the passive tree, ascendancy and weapon-set allocations and refunds the points; the player leaves and rejoins the same instance automatically.
- Extra commands wanted: god mode and friends, monster tools, world and time tools, economy and info commands.
- No hotkeys.

## P7: the framework (Opus for the design, Sonnet for the rework)
1. **Registry v2** (`commands.rs`):
   ```rust
   pub struct Spec {
       pub path: &'static [&'static str],   // ["item", "give"]
       pub aliases: &'static [&'static str],// ["give"]  (whole-path aliases: "lvl" = ["level","set"])
       pub category: Category,              // Help, Character, Stats, Items, World, Monsters, Life, Players, Server, Accounts, Research, Mods
       pub level: Level,                    // Player | Admin
       pub args: &'static [Arg],            // positional, then flags
       pub flags: &'static [Flag],          // --ilvl <int>, --ground (bool), ...
       pub summary: &'static str,           // one line
       pub help: &'static str,              // paragraph
       pub examples: &'static [&'static str],
       pub overlay: Option<&'static str>,   // "Debug>Character"
       pub requires: Option<Feature>,       // hidden until the feature exists (Items, Life, Monsters, ...)
   }
   ```
   New `Kind`s with server-side name lists and completion: `Float`, `Duration` (`30s`, `5m`), `Class`, `Ascendancy`, `ItemBase`, `Unique`, `Mod`, `Stat`, `Currency`, `Gem`, `Monster`, `League`, `Waypoint`, `Rarity`, `DamageType`. Names come from `poe-data` (no lists in code). Matching is case-insensitive, accepts ids and display names, quotes for spaces, and suggests the three closest names on a miss.
2. **Parser**: one parser for chat and overlay: subcommand tree walk, positional args, `--flag value` / `--flag`, quoted strings. Errors name the bad argument and show the usage line.
3. **Permissions**: `Level::Admin` checked against the account role at run time (as now). The debug link's `commands` list is filtered per session, so non-admins never receive admin specs. Mod commands keep their declared level.
4. **Feature gating**: commands whose feature is not built yet are left out (so `!help` never lists something that does nothing).
5. **Debug link**: `cmdspec` lines carry the full spec (path, aliases, category, level, args, flags, summary, help, examples, overlay page) as one JSON line; `complete <kind> <prefix>` request and `completion` reply for name completion; `ack` lines keep their format; new `state` lines push live values the Debug tabs show (level, XP, points, life, flags like god).
6. **`!help`**: `!help` lists the categories with the commands this player may use; `!help <word>` searches names, aliases and summaries; `!help <command path>` shows usage, help text, examples, aliases, level and overlay page. Long output is paged (`!help 2`).
7. **Overlay**: Debug entry with tabs (Help, Console, then per category); the Console with history, tab completion and a suggestion strip; Help tab as in the mockup. The other tabs use hand-laid forms ([overlay.md](overlay.md)) that send the same command text. A command without a hand-laid form still appears in its category tab as a generated form, so nothing lacks an overlay counterpart.
8. **Tests**: parser tests (aliases, flags, quotes, errors), permission filtering, a test that every built-in spec has summary, help, at least one example and a category; a test that every spec's `overlay` page exists in the overlay's page list (the hook repository exports its page ids for the test).
9. Docs: server-admin.md command table regenerated from the registry (`cargo xtask commands-doc` writes the table between markers), so it never drifts.

## Rework of the existing commands
| Today | After | Level | Notes |
|---|---|---|---|
| `help [command]` | `help [search or path]` | player | searchable, paged |
| `where` | `where` | player | also prints league, instance players count |
| `who` | `who` | admin | unchanged output, adds league and level |
| `kick <player>` | `player kick <player> [reason]` | admin | alias `kick` |
| `mute`/`unmute` | `player mute <player> [duration]`, `player unmute <player>` | admin | aliases `mute`, `unmute`; duration `30m`, `2h` |
| `announce <message>` | `announce <message>` | admin | |
| `instances` | `instance list` | admin | alias `instances` |
| `instance_new <layout>` | `instance new <area> [seed] [topology] [orientation]` | admin | |
| `transfer <layout>` | `instance transfer <area> [...]` | admin | alias `transfer`, `go` |
| `join <instance>` | `instance join <id>` | admin | alias `join` |
| `close <instance>` | `instance close <id>` | admin | |
| `teleport <x> <y>` | `tp <x> <y>` / `tp <player>` | admin | alias `teleport` |
| `speed [increased] [action]` | removed when P9 lands: `stat add movement_speed_+% 20` replaces it | admin | kept as an alias that writes debug modifiers |
| `terrain` | `terrain compare` | admin | |
| `area_info <area> <seed>` | `research area_info <area> <seed>` | admin | |
| `account ...` | unchanged | admin | |

## New commands (catalogue)
Each row is delivered by its step; the overlay column is the Debug tab.

| Command | Level | Overlay | Step | What |
|---|---|---|---|---|
| `stuck` | player | World | P7 | moves you to the nearest walkable cell, or the checkpoint/town start if none |
| `uptime`, `seed` | player | Help | P7 | server uptime and version; instance seed and layout |
| `save` | player | Character | P9 | saves your character now |
| `inspect <player>` | player | Players | P9 | another player's level, class, equipment summary |
| `area list [search]` | admin | World | P7 | areas from `WorldAreas` with act and level |
| `instance reset` | admin | World | P7 | a fresh instance of the current area, you inside |
| `summon <player>` | admin | Players | P7 | brings a player to you |
| `time scale <factor>` | admin | World | P7 (research) | see "Time scale" below |
| `league list`, `league end <id> <target>` | admin | World | P3 (done) | [server-admin.md](../guides/server-admin.md#leagues) |
| `unlock <character> [acts\|waypoints\|all]`, `lock ...` | admin | World | R4 | world map and waypoints |
| `waypoint unlock all` | admin | World | R4 | alias of `unlock <me> waypoints` |
| `level set <n> [--no-points]` | admin | Character | P9 | sets the level and grants its points unless `--no-points` |
| `xp add <n>`, `xp set <n>` | admin | Character | P9 | XP with level-ups |
| `points passive\|weaponset\|ascendancy add\|set <n>` | admin | Character | P9/P15 | unspent points |
| `stat add <stat> <value> [--kind flat\|increased\|more\|override]` | admin | Stats | P9 | debug modifier |
| `stat list [search]`, `stat show <stat>` | admin | Stats | P9 | calculator values and breakdown |
| `stat remove <stat\|#id>`, `stat clear` | admin | Stats | P9 | removes debug modifiers |
| `item give <base\|unique> [--rarity] [--ilvl] [--quality] [--mods ...] [--ground] [--count n]` | admin | Items | P11 | [item-creator.md](item-creator.md) |
| `item random <class\|base> [--rarity] [--ilvl] [--count n] [--ground]` | admin | Items | P11 | random rolls for loot testing |
| `item paste` (overlay only: clipboard), `item template save\|give\|list\|delete <name>` | admin | Items | P11 | |
| `item edit <slot\|inventory x y>` | admin | Items | P11 | opens the item in the creator |
| `inv clear [--equipped]` | admin | Items | P9 | empties the inventory |
| `currency <orb> [n]` | admin | Items | P10 | gives a stack |
| `gold add\|set <n>` | admin | Items | P10 | gold |
| `class set <class> [ascendancy]`, `ascendancy set <name>` | admin | Character | P15 | rejoins the instance |
| `tree reset [--weaponset 1\|2] [--ascendancy]`, `tree allocate <node>` | admin | Character | P15 | |
| `heal`, `god [on\|off]`, `nocost [on\|off]` | admin | Life | P13 | no damage; no mana cost or cooldown |
| `damage <n> [type]` | admin | Life | P13 | hits you (tests mitigation) |
| `kill [player]`, `revive [player]` | admin | Life | P13 | |
| `flask refill` | admin | Life | P14 | |
| `gem give <gem> [--level n] [--quality n] [--uncut]` | admin | Items | P16 | skill and support gems |
| `skill list`, `skill grant <skill>` | admin | Character | P16 | |
| `spawn <monster> [n] [--rarity] [--level]` | admin | Monsters | P17 | |
| `killall [--radius cells]` | admin | Monsters | P17 | |
| `ai freeze [on\|off]`, `aggro [on\|off]` | admin | Monsters | P17 | stops monster AI; monsters ignore you |
| `monster inspect [id]` | admin | Monsters | P17 | AI state, target, life, skills, cooldowns |
| `loot roll <monster\|rarity> [--level] [--count n]` | admin | Items | P18 | drop table test at your feet |
| `party ...` (debug views) | admin | Players | P18 | party state |
| `npc list`, `vendor refresh` | admin | World | P19 | |

### Time scale (research inside P7)
The client advances its own simulation per frame, and the server runs the exact movement port in lockstep ([../decisions.md](../decisions.md#movement-and-world)). A server-only time scale would desync movement. P7 checks whether the client has a time-scale message (official servers slow time with some effects: "Temporal Chains" style action-speed stats). If one exists it is used; otherwise `time scale` affects only server-side timers (AI, regeneration, cooldowns, buffs) and its help text says so.

## Done when (P7)
- `!help`, `!help item`, `!help instance join` work in chat and in the Help tab; non-admins see only player commands.
- Every reworked command works by its new name and its alias; old names still work.
- The Console runs any command with completion; generated forms exist for commands without a hand-laid form.
- Registry tests pass; `commands-doc` regenerates the server-admin.md table.

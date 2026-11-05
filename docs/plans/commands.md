# Plan: debug commands still to add

Registry v2 is current: subcommands, aliases, flags, levels, name kinds, searchable help and the Debug tabs are described in [../guides/server-admin.md](../guides/server-admin.md#commands) and [../architecture/client-dll.md](../architecture/client-dll.md). Every feature step adds its own commands and the matching overlay controls (listed below with the step that delivers them). A command whose feature is not built stays hidden through `Feature` and `BUILT` in `commands.rs`; a step adds its feature to `BUILT` when its commands work. Mods add commands ([../architecture/mod-host.md](../architecture/mod-host.md)).

## User decisions (2026-11-04)
- Two permission levels only: **player** and **admin**. Every cheat command is admin-only.
- **Verb-first syntax with subcommands**, e.g. `!item give <base> [--ilvl 82] [--rarity rare] [--ground]`, `!stat add <stat> <value> [--kind increased]`, `!level set 90`, `!points passive add 10`, `!class set Warrior Titan`, with aliases for common ones (`!lvl`, `!tp`).
- **Every command has an overlay counterpart** in the one Debug entry with sub-tabs ([overlay.md](overlay.md#debug-help--console--character--stats--items--world--monsters--life--players)).
- Non-admins do not see admin-only commands in `!help`, in the Console's completion, or in the overlay.
- `!help` and the Help tab are **searchable and generated from the registry**.
- Stat edits are a **debug modifier layer** in the stat calculator, saved per character and removable.
- Class change keeps level, XP, items and gold; it resets the passive tree, ascendancy and weapon-set allocations and refunds the points; the player leaves and rejoins the same instance automatically.
- Extra commands wanted: god mode and friends, monster tools, world and time tools, economy and info commands.
- No hotkeys.
- `speed [increased] [action]` stays until P10; then `stat add movement_speed_+% 20` replaces it and `speed` remains as an alias that writes debug modifiers.

## New commands (catalogue)
Each row is delivered by its step; the overlay column is the Debug tab.

| Command | Level | Overlay | Step | What |
|---|---|---|---|---|
| `save` | player | Character | P10 | saves your character now |
| `inspect <player>` | player | Players | P10 | another player's level, class, equipment summary |
| `unlock <character> [acts\|waypoints\|all]`, `lock ...` | admin | World | R4 | world map and waypoints |
| `unlock <character> act <n>`, `unlock <character> waypoint <area>` | admin | World | R4 | one act map (interludes included) or one waypoint |
| `waypoint unlock all` | admin | World | R4 | alias of `unlock <me> waypoints` |
| `checkpoint unlock all` | admin | World | R4 | unlocks every checkpoint of the instance you are in |
| `level set <n> [--no-points]` | admin | Character | P10 | sets the level and grants its points unless `--no-points` |
| `xp add <n>`, `xp set <n>` | admin | Character | P10 | XP with level-ups |
| `points passive\|weaponset\|ascendancy add\|set <n>` | admin | Character | P10/P15 | unspent points |
| `stat add <stat> <value> [--kind flat\|increased\|more\|override]` | admin | Stats | P10 | debug modifier |
| `stat list [search]`, `stat show <stat>` | admin | Stats | P10 | calculator values and breakdown |
| `stat remove <stat\|#id>`, `stat clear` | admin | Stats | P10 | removes debug modifiers |
| `item give <base\|unique> [--rarity] [--ilvl] [--quality] [--mods ...] [--ground] [--count n]` | admin | Items | P12 | [item-creator.md](item-creator.md) |
| `item random <class\|base> [--rarity] [--ilvl] [--count n] [--ground]` | admin | Items | P12 | random rolls for loot testing |
| `item paste` (overlay only: clipboard), `item template save\|give\|list\|delete <name>` | admin | Items | P12 | |
| `item edit <slot\|inventory x y>` | admin | Items | P12 | opens the item in the creator |
| `inv clear [--equipped]` | admin | Items | P10 | empties the inventory |
| `currency <orb> [n]` | admin | Items | P11 | gives a stack |
| `gold add\|set <n>` | admin | Items | P11 | gold |
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

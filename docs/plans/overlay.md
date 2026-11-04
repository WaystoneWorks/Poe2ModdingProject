# Plan: Debug tab layouts (overlay)

P1 (look, Settings) and P6 (layout overhaul of every page, merges, Debug shell) are done and described in [client-dll.md](../architecture/client-dll.md#overlay-overlay) and [server-admin.md](../guides/server-admin.md#overlay-pages-our-server-only-debug-group). What is left here is the mockups of the Debug tabs that still are shells; each feature step ([commands.md](commands.md), [items-stats.md](items-stats.md), [item-creator.md](item-creator.md), [life-flasks.md](life-flasks.md), [monsters.md](monsters.md)) builds its tab in `modules/client-hook/poe-hook-core/src/ui/debug_tab.rs` and deletes its mockup here; delete this file when none is left. Page furniture to use: `ui/widgets.rs`. Non-admins do not see admin-only tabs (`admin_only` in `ui/mod.rs`); no hotkeys for commands.

### Debug (Help | Console | Character | Stats | Items | World | Monsters | Life | Players)
Help, Console and World exist (P6); Help's detail pane also shows aliases and flags once the command framework (P7) sends them.
Shared rule: each tab is a set of forms built from the server's command registry ([commands.md](commands.md)), laid out by hand for the common actions, with a "Results" strip at the bottom showing the last 20 `ack` lines. A tab whose commands are all admin-only is hidden for non-admins.

Help:
```
+------------------+-----------------------------------------------+
| [search]         | !level set <level> [--no-points]              |
| Character        | Sets your level. Grants the passive, weapon   |
|   level          | set and ascendancy points that level gives    |
|   xp             | unless --no-points.                           |
|   points         | Examples:  !level set 90                      |
|   class          | Aliases:   !lvl                               |
| Items            | Permission: admin    Overlay: Debug>Character |
|   item           | [Open form]                                   |
| ...              |                                               |
| Overlay pages    |                                               |
+------------------+-----------------------------------------------+
```
Console:
```
+------------------------------------------------------------------+
| <Server> Level set to 90 (+89 passive, +24 weapon set points)    |
| > !item give "Iron Ring" --ilvl 80                               |
| <Server> Gave Iron Ring (normal, ilvl 80)                        |
|                                                                  |
| [!_______________________________________________] [Run]         |
|  suggestions: item give | item edit | item clear                 |
+------------------------------------------------------------------+
```
History with up/down, tab completion of command names and of item, stat, monster and area names (lists come from the server).

Character:
```
Class [Mercenary v] Ascendancy [Witchhunter v] [Apply (rejoins)]
Level [ 12 ] [-][+] [Set]   [x] grant points
XP    1,234 / 5,000 [####......] [Add 10%] [Set]
Points  passive 11 [-][+]  weapon set 0 [-][+]  ascendancy 0 [-][+]
[Reset passive tree] [Reset ascendancy] [Save now]
```
Stats (stat editor): left a searchable list of every stat the calculator knows (implemented ones first), right the selected stat's breakdown (base, flat, increased, more, final; sources: class, level, items, tree, debug) and a form "Add debug modifier: [flat|increased|more|override] [value] [Add]". Below, a table of the active debug modifiers with remove buttons and `[Clear all]`.

Items (item creator, [item-creator.md](item-creator.md)):
```
+--------------------+---------------------------+---------------------+
| [search bases]     | Base  Iron Ring           |  .---------------.  |
| > Rings            | Rarity [Rare v] ilvl [80] |  | [item art]    |  |
|   Iron Ring        | Quality [0] Corrupted [ ] |  | Grim Loop     |  |
|   Ruby Ring        | Name [Grim Loop]          |  | Iron Ring     |  |
| > Uniques          | Implicit                  |  |---------------|  |
|   Mageblood        |  [+ add] Adds 1-4 phys    |  | +25% fire res |  |
| Templates          | Explicit                  |  | +40 to life   |  |
|   my ring          |  [+ add] +40 to life [T1] |  | ILLEGAL: ...  |  |
| [Paste item text]  |  ...                      |  '---------------'  |
+--------------------+---------------------------+---------------------+
[Give to inventory] [Drop at feet] [Save template] [Random x N]
```
World: area search (`area list` results) with a layout form (the existing `layout_form.rs`), `[Transfer]`, `[New instance]`; the instance table (from today's Instances page, admin); teleport (cell or player), waypoint unlocks, `stuck`, time and seed info.

Monsters: monster search, count, rarity, level, `[Spawn]`, `[Kill all]`, toggles `freeze AI`, `no aggro`; an inspector of the nearest or selected monster (server AI state, target, life, skills, cooldowns) from the debug link.

Life: life, mana, ES bars with `[Heal]`, `[Damage N type]`, toggles `god`, `no cost`; `[Kill me]`, `[Revive]`; flask charges `[Refill]`.

Players (admin): online table (name, account, area, instance, ping) with row buttons `[Kick] [Mute] [Inspect] [TP to] [Summon]`, and `[Announce]`.

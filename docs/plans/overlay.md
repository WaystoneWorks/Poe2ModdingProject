# Plan: Debug tab layouts (overlay)

P1 (look, Settings) and P6 (layout overhaul of every page, merges, Debug shell) are done and described in [client-dll.md](../architecture/client-dll.md#overlay-overlay) and [server-admin.md](../guides/server-admin.md#overlay-pages-our-server-only-debug-group). What is left here is the mockups of the Debug tabs still to build; each feature step ([commands.md](commands.md), [items-stats.md](items-stats.md), [item-creator.md](item-creator.md), [life-flasks.md](life-flasks.md), [monsters.md](monsters.md)) builds its tab in `modules/client-hook/poe-hook-core/src/ui/debug_tab.rs` and deletes its mockup here; delete this file when none is left. Page furniture to use: `ui/widgets.rs`. Non-admins do not see admin-only tabs (`admin_only` in `ui/mod.rs`); no hotkeys for commands.

### Debug (Help | Console | Character | Stats | Items | World | Monsters | Life | Players)
Help, Console, World and Players exist ([server-admin.md](../guides/server-admin.md#overlay-pages-our-server-only-debug-group)); below are the tabs still to build, plus what the existing ones gain.
Shared rule: each tab is a set of forms built from the server's command registry ([commands.md](commands.md)), laid out by hand for the common actions, with a "Results" strip at the bottom showing the last 20 `ack` lines. A tab whose commands are all admin-only is hidden for non-admins.

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
World gains (R4) buttons to unlock chosen act maps and waypoints, and `[Unlock all checkpoints in this instance]`.

Monsters: monster search, count, rarity, level, `[Spawn]`, `[Kill all]`, toggles `freeze AI`, `no aggro`; an inspector of the nearest or selected monster (server AI state, target, life, skills, cooldowns) from the debug link.

Life: life, mana, ES bars with `[Heal]`, `[Damage N type]`, toggles `god`, `no cost`; `[Kill me]`, `[Revive]`; flask charges `[Refill]`.

Players gains `[Inspect]` per row (P10).

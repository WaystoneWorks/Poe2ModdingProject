# Plan: DLL overlay look, layout and Settings

Step P6 (layout overhaul) of [../PLAN.md](../PLAN.md); P1 (look, Settings, `overlay.toml`) is done and described in [client-dll.md](../architecture/client-dll.md#overlay-overlay). The Debug group's pages are built here as a shell; their commands come from [commands.md](commands.md) and each feature step. Current overlay: [../architecture/client-dll.md](../architecture/client-dll.md#overlay-overlay). Code: `modules/client-hook/poe-hook-core/src/ui/` (`mod.rs` sidebar, pages and notices; `theme.rs`; one `*_tab.rs` per page).

## User decisions (2026-11-04)
- Look: ImGui's stock `StyleColorsDark`, stock spacing and rounding, and the built-in ProggyClean font scaled by `overlay.scale`. Cinzel and the Ash & Blood colours leave the overlay. The launcher and web admin keep Ash & Blood.
- Navigation: keep the sidebar of folding groups and tidy it. An entry with several pages shows tabs, as it does now.
- The **Features** page becomes **Settings**, with one checkbox "Show slow hook popups". Warnings are still logged when it is off.
- Overlay user settings are saved in `logs/poe-hook/overlay.toml`, which the overlay writes itself. `poe-hook.toml` stays deploy-written, and deploys never overwrite `overlay.toml`.
- Merges: Player + Stats + Actions into one Player page; Log + Game log into one Log page; Sync state + Desync into one Sync page; Coverage and Notes become tabs of Packets.
- One **Debug** sidebar entry with sub-tabs replaces SERVER > Commands; a raw Console tab stays.
- Non-admins do not see admin-only controls or tabs at all (not greyed out). The server sends the role and the allowed commands over the debug link.
- The ASCII mockups below are the approval; no HTML previews before building.
- Every page gets a full redesign, the research pages too.
- No hotkeys for commands.

## P6: layout overhaul
Rules for every page:
- **Toolbar row** at the top: filter box first (`Ctrl+F` focuses it), then toggles, then buttons, right-aligned counters ("1,204 rows").
- **Tables**: `RowBg | BordersInnerV | Resizable | ScrollY | Sortable` where sorting makes sense, frozen header row, monospace for hex and addresses, right-aligned numbers. Empty state text in `muted` ("No packets yet: connect to a server").
- **Detail panes**: list on the left, detail on the right with a draggable splitter (`child_window` widths saved in `overlay.toml`).
- **Status chips**: small coloured text tags (`ok`/`warn`/`bad`) instead of free text: `PRIVATE`, `OFFICIAL read-only`, `ADMIN`, `sync ok`.
- Every page has a one-line `muted` description under its tab bar and a `(?)` hover help.

### Sidebar after the overhaul
```
PLAY            Status
                Player        [Overview | Stats | Actions]
                Entities      [Entities | Watches]
                Minimap
DEBUG           Debug         [Help | Console | Character | Stats | Items | World | Monsters | Life | Players*]
                Sync
LOGS            Log
RESEARCH (fold) Packets       [Messages | Opcodes | Notes]
                Protocol
                Timing
                RE tools      [Scanner | Hooks]
SETTINGS        Settings
                                              * admin only, hidden for others
```
The DEBUG group (with Sync) is hidden while the read-only latch is on, as SERVER is now. Instances moves into Debug > World. The page search box (and `Ctrl+K` palette) also finds Debug commands by name and opens their form.

### Status
```
+------------------------------------------------------------------+
| [PRIVATE] [ADMIN] [sync ok]  127.0.0.1:20481  Clearfell (G1_2)   |
| 144 fps   core 0.5.0 (reloaded 12:03)   session 2026-11-04_12-00 |
| [Reload core] [Snapshot] [Hide overlay]                          |
|------------------------------------------------------------------|
| > Connections (3)                                                |
|   time     kind      address          socket   trusted           |
|   12:00:01 login     127.0.0.1:20481  0x2f4    yes               |
| > Features: 14 ok, 1 OFF (inspect: sig X matched 0 times)        |
| > Loaded mods (2)                                                |
+------------------------------------------------------------------+
```
Feature health (from the signature resolution) moves here from the log, red when a feature is OFF.

### Player (Overview | Stats | Actions)
```
Overview                                   Stats
+-------------------------------+          +------------------------------------------+
| Kaia  Lv 12 Mercenary         |          | [filter stat id/name] [x] changed only   |
| Area G1_2 seed 1234 inst 7    |          | set: [0 own v]  rows 312                 |
| Cell 412,288  facing 1.57     |          | stat                 id    value  server |
| Life 140/140  Mana 60/60      |          | max_life             1234   140    140   |
| Action: DodgeRoll (0.3 s)     |          | movement_speed_+%      15    10     10   |
| Speed: move +10% action 0%    |          |   (yellow = changed <3 s, red = client  |
+-------------------------------+          |    and server disagree)                  |
                                           +------------------------------------------+
Actions: table time | slot | action | type id | duration, newest first, [pause] [clear].
```
The Stats tab gets a "server" column from the debug link (P8 and later), so client and server stats can be compared side by side.

### Entities (Entities | Watches)
```
+---------------------------+--------------------------------------+
| [filter path/id] [alive]  | Entity 0x1a3  Metadata/Monsters/...  |
| id   name        grid     | grid 400,280  dist 12                |
| 1a3  Drowned     400,280  | Components                           |
| 1a4  Waypoint    410,300  |  Positioned  0x...  [watch]          |
| ...                       |  Life        0x...  [watch]          |
+---------------------------+--------------------------------------+
```
Watches: an expression row editor on top (`[expr] [len] [Add]`), a table below (name, address, value, changed age), with per-row remove.

### Minimap
Full-height canvas, toolbar: layer selector (walk / projectile / both / height), zoom slider, `[follow player]`, `[show server position]`, `[Export area]`. Hover shows the cell coordinate and the four grid values. Legend in the corner.

### Debug (Help | Console | Character | Stats | Items | World | Monsters | Life | Players)
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

### Sync
Header with live chips (`linediv 0`, last snap, frames sent), then the desync table (frame, client cell, server cell, delta, reason) with `[Copy TSV]` and a small plot of the per-frame delta.

### Log (one viewer)
Toolbar: source `[hook | client | both]`, level `[all | info | warn | error]`, filter, `[Follow]`, `[Copy shown]`, `[Open folder]`. Rows are coloured by level; client-log rows tagged `CLIENT`.

### Packets (Messages | Opcodes | Notes)
```
Messages: [filter name/0x..] [in][out] [hide noise] [pause] [follow]   8,201
+-------------------------------+----------------------------------+
| seq  t      dir op     name   | 0x01a7 InstanceTick  in  42 B    |
| 812  12.01  in  01a7   Tick   | decoded fields (tree)            |
| ...                           | hex (16 per row, ascii)          |
+-------------------------------+ [Copy] [Hide this opcode]        |
                                | note: [______] [Save]            |
                                +----------------------------------+
```
Opcodes: today's coverage table (opcode, name, ours, official, size, seen this session) plus the visibility checkbox column that today lives in the opcodes list. Notes: today's Notes table with a filter.

### Protocol
List of opcodes on the left (filter, "no name yet"), right the field table (offset, size, samples, distinct, looks like, last value), the reader/writer functions, and the note editor. `[Export now]` in the toolbar.

### Timing
Plots on top (frame time, tick lag, ms per hook), a summary table below (min, mean, p99, max) with `[Reset]`.

### RE tools (Scanner | Hooks)
Scanner: address/expression bar, `[Set baseline]`, `[x] changed rows only`, results table with `[Watch]` per row. Hooks: the table (callback, calls, calls/s, avg us, max ms, ms/s) sorted by ms/s, slow rows red, `[Reset counters]`.

### Settings
```
General
  [x] Show slow hook popups
  [ ] Movement log (per-frame position in the log)
  [x] Position sync (reports to our instance server)
  Scale [1.00 ----|----]  (overrides poe-hook.toml overlay.scale)
> Deployed config (edit poe-hook.toml, then Reload core)
  mode private | crash_log true | crypto_bypass true | ...
```

### Popups and notices
`ui::notice` stays the small corner notice. A new `ui::alert(Alert)` is a centred modal for things that need reading: the terrain mismatch ([../protocol/instance.md](../protocol/instance.md#terrain-check)) is the first user and `ui/alert.rs` is built ([../architecture/client-dll.md](../architecture/client-dll.md#alert-popups)). An alert has a title, `key: value` rows, buttons (`Copy report`, `OK`) and is queued like notices.

## Steps and gates
- P6: Sonnet (UI work), one session per two or three pages: Status, Player, Entities, Minimap; Log, Sync, Settings; Packets, Protocol, Timing, RE tools; the Debug shell (Help and Console wired to the existing commands; other tabs show "comes with <step>" until their step). Gate: `cargo xtask` overlay build, the sidebar tests, and an agent game test that opens every page (screenshot per page into `runtime/game-test/`).

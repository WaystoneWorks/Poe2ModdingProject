# Plan: progress tracker website

Step P5 of [../PLAN.md](../PLAN.md). A public page in the hub that shows what is implemented, like the reference tracker the user showed (overall percentage and bar, status counters, section cards with ring progress, search with filters, expand and collapse, rows with status pills, recent changes), in the web admin's style (Ash & Blood tokens from `modules/web-admin/src/tokens.css`).

## User decisions (2026-11-04)
- **Static site, statuses in a data file in the hub**, changed by commits. Agents update statuses in the same commit as the work. A local editor writes the file.
- **Sections generated from 0.5.5e game data plus project sections.**
- Statuses: **Unknown, Not implemented, Partial, Implemented, Fully functional, Not planned**. **No hour estimates**: progress is weighted by row count.
- Hosted on **GitHub Pages of the hub** once the hub is on the new account ([hosting.md](hosting.md)); until then built and opened locally.
- Row names come from a committed **names-only `tracker/rows.json`** (id, section, display name) generated from local game data. No stats, values, art or other table columns.

## Layout of the hub
```
tracker/
  rows.json        generated: [{id, section, group, name}] (names only)
  status.toml      hand and agent edited: id = { status = "partial", note = "...", link = "docs/..." }
  sections.toml    section order, titles, descriptions, which generator fills them
  site/            Svelte + Vite app (copies tokens.css from web-admin at build time)
xtask: tracker gen | tracker build | tracker edit
.github/workflows/tracker.yml   build and deploy to Pages on push to main (paths: tracker/**)
```
- Row ids are stable: `gem:<SkillGems id>`, `unique:<id>`, `passive:<PassiveSkills id>`, `asc:<Ascendancy id>`, `class:<id>`, `base:<BaseItemTypes id>`, `stat:<Stats id>`, `currency:<id>`, `monster:<MonsterVarieties id>`, `area:<WorldAreas id>`, `mechanic:<id>`, `cmd:<command path>`, `proj:<slug>` for project rows.
- A row missing from `status.toml` is **Unknown**.

## Sections
Generated (`tracker gen` from `poe-data`): Classes and Ascendancies; Skill gems; Support gems; Passive notables and keystones (small nodes grouped by their stat instead of one row each); Unique items; Base item types (grouped by item class); Stats and mods (the stats used by mods, passives and gems); Currency; Flasks and charms; Monsters and bosses (by act); Areas (campaign by act, interludes, endgame); League mechanics; Trials.
Project (hand-written in `sections.toml` with `proj:` rows): Server systems (accounts, login, chat, instances, terrain generator, movement, transitions and waypoints, world map, parties, trade, loot, vendors), Client DLL (overlay pages, debug commands, official read-only mode), Launcher, Web admin, Tooling and modding.
Automatic statuses where code knows: rows of stats come from `poe-stats`'s implemented map (`implemented` when mapped), `cmd:` rows from the command registry; `tracker gen` writes these into `status.toml` under an `[auto]` table that hand edits do not override.

## The page
```
+---------------------------------------------------------------------------------+
| PROGRESS   12.4%  ######............................................  of 13,100 |
| (Unknown 11,977) (Not impl 300) (Partial 263) (Impl 410) (Fully 120) (Not plan 30)|
| [Classes 0%] [Skill gems 1.2%] [Uniques 0%] [Passives 0.5%] [Monsters 0%] ...   |
|---------------------------------------------------------------------------------|
| [Search...  fireball  is:implemented  -is:fully_functional  in:gems ] [+][-]    |
|                                                                                 |
| v CLASSES AND ASCENDANCIES                          3/22  ######....  14%       |
|   (Partial)          Warrior                                                    |
|   (Not implemented)  Titan                                                      |
| > SKILL GEMS                                        2/420 .........  0.5%       |
|                                                    | RECENT CHANGES            |
|                                                    | stat:base_maximum_life    |
|                                                    | Unknown -> Fully          |
|                                                    | 2026-11-20  commit abc123 |
+---------------------------------------------------------------------------------+
```
- Filters as in the reference: free text, `is:<status>`, `-is:<status>`, `in:<section>`; URL hash keeps the query so links can be shared.
- Status pills coloured with the web admin tokens; a row's note and link (to the doc or commit) on hover.
- **Recent changes**: `tracker build` reads `git log -p tracker/status.toml` and writes the last 50 status changes (row, old, new, date, commit) into the site data.
- Read-only on the web; no logins.

## `tracker edit` (local editor)
`cargo xtask tracker edit` serves the same site on `127.0.0.1` with the status pills as dropdowns and a notes field; saving writes `status.toml` (sorted, stable formatting). Nothing is committed by it.

## Agent rule (CLAUDE.md)
A commit that implements or changes something with a tracker row updates `tracker/status.toml` in the same commit (as docs do). `tracker gen` runs in `cargo xtask` checks to catch rows whose id no longer exists.

## Done when
`tracker gen` makes `rows.json` from local data, `tracker build` makes the static site in `runtime/tracker-site/` that opens locally with all sections, filters, progress and recent changes; `tracker edit` changes a status; the Pages workflow is ready (runs once the hub is on GitHub).

# Plan: leagues managed in the web admin

Step P3 of [../PLAN.md](../PLAN.md). Wire format of the league list and the character's league: [../protocol/login.md](../protocol/login.md#leagueentry-0xe8-bytes-reader-0x142716e10). Today the leagues come from `[[leagues]]` in `modules/server/config/server.toml` (Standard, Hardcore), read by `servers/login-server/src/session.rs` (league list, creation check) and `servers/poe-server/src/main.rs` (CLI `character create`).

## User decisions (2026-11-04)
- Applies to every server: a new server has **no league**. Leagues live in the database and are managed in the web admin.
- With no league, login works as now and the server **does not send the league list** (`0x001b`). The web admin shows a "This server needs a league" popup until one exists.
- The old `[[leagues]]` config block is **dropped**, with no migration (dev servers recreate their leagues).
- Creating a league with "Hardcore" and/or "SSF" ticked creates the official set of linked variants.
- Banner: picked from the game's own league art, the `LeagueFlag` rows the client already uses for the character banner (CharacterEntry `+0x4d` = row + 1).
- League mechanics: a list built from game data, stored only, with a "not implemented yet" tag.
- Lifecycle: active, hidden (no new characters), ended (characters move to a chosen permanent league). Deleting a league is allowed only when it has no characters, after typing its name.
- Extra fields: start and end dates (auto-end at the end date), and a default league.

## Data model (`poe-store`, new migration)
```
leagues(
  id TEXT PRIMARY KEY,            -- wire id, e.g. "Dawn", "Hardcore Dawn"
  display_name TEXT,              -- LeagueEntry +0x60
  family TEXT,                    -- the base league's id, the same for all four variants
  hardcore INTEGER, ssf INTEGER,  -- this row's flags
  variant_of TEXT NULL,           -- +0x80: base league id for variants, NULL for the base
  permanent INTEGER,              -- +0xe0 bit 7 (creation banner, not in "Join")
  flag_row INTEGER NULL,          -- LeagueFlag row of the banner
  mechanics TEXT,                 -- JSON list of mechanic ids, stored only
  starts_at INTEGER NULL, ends_at INTEGER NULL,   -- unix ms, sent as +0xd0 / +0xc8
  state TEXT,                     -- active | hidden | ended
  migrate_to TEXT NULL,           -- the permanent family characters move to at the end
  is_default INTEGER,             -- one row at most
  sort INTEGER, created_at INTEGER)
```
Characters keep their `league` text. A trait `LeagueStore` in `poe-store` (list, create family, update, end, delete-if-empty) is used by the login server, the web API and the CLI.

## Variants
Creating family "Dawn" with HC and SSF ticked makes four rows: `Dawn`, `Hardcore Dawn` (hardcore, variant_of Dawn), `SSF Dawn` (ssf, variant_of Dawn), `HC SSF Dawn` (hardcore and ssf, variant_of Dawn). Variant names follow the official pattern and can be renamed later. Each variant can be hidden on its own.

## Research first (Opus or re-tracer, short)
1. **No league list.** Check what the client does when `0x001b` is not sent at all: the character list, the "Join" list, and pressing Create. If it waits or crashes, send an empty list instead and record which one works in login.md.
2. **SSF on the wire.** The SSF flag in LeagueEntry: `+0xa0` (probably the SSF base's id) and the LeagueFlag IsSSF column. Read the character-creation banner builder `0x140e7ca80` and `0x1406bee00` for how a solo-self-found checkbox pairs a variant with its base (as the Hardcore checkbox does through `+0x80`).
3. **Non-permanent leagues at creation.** Banners are built only for `+0xe0 bit 7` entries. Check how a challenge league (no bit 7, in the "Join" list) is chosen for a new character (official: Join switches the selected league, then Create). The plan's "permanent" checkbox depends on this.
4. **Mechanics source.** Find the game table that lists league mechanics for 0.5.5e (candidates: `LeagueInfo`, `LeagueProgress`, the league-specific `*` tables in `dumps/<version>/client-tables`). Use `poe-data`, not a hand list. If no single table lists them, build the list from the tables that exist and note the source.
5. **Dates.** Which of `+0xd0` (start), `+0xd8`, `+0xc8` (end) the select screen uses for "starts in" and "ended", and their unit (from the existing notes: u64; check ms vs s).

## Server (Sonnet after the research)
1. Remove `LeagueConfig` and `[[leagues]]` from `poe-config`, `server.toml` and the config editor's schema. A leftover block gives a startup warning "`[[leagues]]` is ignored; leagues are in the web admin".
2. Login server: league list from `LeagueStore` (state `active`, start time passed or within the client's "starts in" window; `hidden` and `ended` not sent). Creation check: refuse unknown, hidden, ended or not-started leagues with the existing refusal codes. No leagues: no list (or the empty list from research 1).
3. Default league: sent first; the CLI `character create` uses it when no league is given.
4. End: at `ends_at`, or by "End now", move characters: base to `migrate_to`, hardcore to `migrate_to`'s hardcore variant, SSF to its SSF variant, HC SSF to the HC SSF variant, each falling back to the base when the variant does not exist. Characters online are moved at their next character list (or disconnected with a notice). Write an audit line per character.
5. CLI: `poe-server league list|create|end|delete` (offline, like `account`). Chat commands for admins: `!league list`, `!league end <id> <target>` ([commands.md](commands.md)).

## Web API (`poe-web-api`, OpenAPI regenerated, web admin `npm run gen:api`)
| Method and path | Role | What |
|---|---|---|
| `GET /api/v1/leagues` | public | active leagues: id, display name, flags, dates, banner URL |
| `GET /api/v1/admin/leagues` | admin | every league with state and character count |
| `POST /api/v1/admin/leagues` | admin | create a family: `{name, hardcore, ssf, permanent, flag_row, mechanics, starts_at, ends_at, default}` |
| `PATCH /api/v1/admin/leagues/{id}` | admin | display name, banner, mechanics, dates, state (active/hidden), default |
| `POST /api/v1/admin/leagues/{id}/end` | admin | `{migrate_to}`; ends the family |
| `DELETE /api/v1/admin/leagues/{id}` | admin | only with no characters; body `{confirm: "<id>"}` |
| `GET /api/v1/data/league-flags` | admin | LeagueFlag rows: row, id, IsHC, IsSSF, art URL |
| `GET /api/v1/data/league-mechanics` | admin | mechanics from game data |
| `GET /api/v1/art/{path}` | public, cached | a game image converted to PNG (DDS decode on the server from its own game files; nothing is committed). Also used by the item creator and the tracker-free web views |

## Web admin (`modules/web-admin`, Ash & Blood style)
New **Leagues** page in the nav, between Characters and Instances.
```
LEAGUES                                                   [+ New league]
+------------------------------------------------------------------------+
| [banner] Dawn            DEFAULT  ACTIVE   12 characters                |
|          Hardcore Dawn   HC       ACTIVE    3 characters                |
|          SSF Dawn        SSF      HIDDEN    0                           |
|          HC SSF Dawn     HC SSF   ACTIVE    1                           |
|          Starts 2026-11-10 18:00  Ends 2027-02-10 18:00                 |
|          Mechanics: Breach, Ritual (not implemented yet)                |
|          [Edit] [Hide/Show] [End league...] [Delete...]                 |
+------------------------------------------------------------------------+
```
New league dialog:
```
+-------------------------------- New league ----------------------------+
| Name [Dawn____________]                                                 |
| Banner  [art][art][art][art][art] ...   (LeagueFlag rows; HC/SSF art    |
|                                          is picked for the variants)    |
| [x] Hardcore variant   [x] SSF variants   [x] Permanent   [x] Default   |
| Starts [date time] (empty = now)   Ends [date time] (empty = never)     |
| Mechanics (stored, not implemented yet)                                 |
|   [ ] Breach [ ] Delirium [ ] Expedition [ ] Ritual [ ] ...             |
| Creates: Dawn, Hardcore Dawn, SSF Dawn, HC SSF Dawn                     |
|                                              [Cancel] [Create league]   |
+-------------------------------------------------------------------------+
```
End dialog: target permanent family (select), the per-variant mapping it implies, a count of characters moved, typed confirmation.

"Needs a league" popup: a modal on the first-run Setup page's last step and on every admin page load while no active league exists: "This server has no league. Players can log in but cannot create characters." `[Create a league]` opens the dialog; `[Later]` hides it for the session. The Dashboard also shows a red card until a league exists.

## Launcher
Server details (My servers and Browse) show the server's active leagues with banners from `GET /api/v1/leagues` (banner art through the server's art endpoint). The Host page, after creating a server, opens its web admin at the Leagues page.

## Done when
- A fresh server has no league; the client logs in and the select screen behaves as research 1 recorded; the web admin popup shows.
- Creating "Dawn" with HC and SSF makes four leagues; the client shows them with the chosen banners; characters can be created in each; dates and hidden state work.
- Ending "Dawn" into "Standard" moves every variant's characters to the right target.
- Server, web API and web admin tests pass; an agent game test creates a character in a web-admin-created league.

# League migrations in game (P7b, Opus: client RE)

Goal: a player moves their own character from SSF to the trade league, or from hardcore to softcore, with the client's own **League Migrations** button on character select (the `>>` button above the character list, tooltip "League Migrations"). Done already: the rules and storage, `LeagueStore::migrate_character(character_id, kind, actor, now)` with `MoveKind::LeaveSsf` / `LeaveHardcore` (one way, same family; [server-admin.md](../guides/server-admin.md#leagues)), the audit lines, and the admin move in the web admin. Missing: the protocol between that window and the server, which nobody has read.

## What the client has (`dumps/<version>/strings/clientstrings.txt`)
- Button and window: `LeaguesWithProgressButtonLabel` / `LeaguesWithProgressWindowTitle` "League Migrations", `...WindowDesc` "List of leagues with progress that can be migrated."
- Per character **Migrate** (`SoloSelfFoundMigrateCharacterButton`, popup "Migrate this character to the league shown above"), **Migrate All** (`SoloSelfSoundMigrateAllButton`: every character of the account in that league, with items, stash tabs, hideouts, masters, Atlas state and the guild stash for a guild leader), From/To league labels (`CharacterMigrationFromLeague`, `...ToLeague`), confirmation texts (`SSFMigrateConfirmationTitle`, `...MessageAll`, `SSFMigrationConfirmationMessageChar`, `LastCharacterMigrationWarning`), errors (`MigrationFailedTitle`, `MigrateCharacterUnavailableError`), the ended-league notice (`LoginPendingMigration`, `LoginMigrateTitle`).
- The league list entry (`LeagueEntry`, [login.md](../protocol/login.md#leagueentry-0xe8-bytes-reader-0x142716e10)) already carries "SSF-of" (+0x60) and "HC-of" (+0x80): the client may derive the target league from them.

## To find out (Ghidra on the string references, then a test with the DLL on our server)
1. Which client-to-server message a Migrate / Migrate All click sends, its layout, and which reply the client waits for (success, `MigrationFailed`).
2. What decides that the button lists a league ("leagues with progress"): data from the server, or the league flags of the characters.
3. Whether hardcore to softcore has a path in this window or only SSF; if not, the fallback is a chat command for players (`migrate`) that calls the same store method.
No official capture of a migration exists (official servers are read-only; a capture is the user's to make, ask first).

## Server side to build
Handler for the message(s) found, calling `migrate_character` per character (and a `migrate_account`-style loop for Migrate All, in one transaction), refusing online characters of another session, then refreshing the character list the client shows. Game test `leagues` extended with a migration (agent game test, headless gamescope).

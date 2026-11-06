# Plan: before P10 (B2, B3, A1, A2, P10a)

Steps the user chose in S1 on 2026-11-05 from a list of 30 suggestions; order and status are in [../PLAN.md](../PLAN.md). Delete each section when its step is done, and this file with the last one. Suggestions not chosen: [backlog.md](backlog.md#suggested-in-s1-not-chosen).

## B2: bad seeds
The client throws `TerrainGenerationException` on about 3% of generation jobs ([terrain.md](../status/terrain.md#results): 6,695 of 225,400, mostly `G2_10_1`, `MapBackwash`, `G2_1`, `MapUniqueVault`, `G1_12`), and the docs say the game retries with another seed. Our server keeps the seed, so the player waits 30 s and is kicked (`terrain_check::Reason::NoHashes`, `servers/instance-server/src/lib.rs` near line 250). Seen in the game test once in about 10 runs: `client_terrain_generation_failed (no hashes in 30 s)`, `G1_1` seed 3227977988.

1. Reproduce offline: run seed 3227977988 through the client batch ([batch.md](../re/terrain/batch.md)) and the server generator (`area_probe`). Record whether the generator fails on the seeds the client fails on: compare the error rows of `dumps/0.5.5e.hotfix1/terrain/batch/full/batch-results.tsv` with `forced_verify`.
2. Find how the client and the official server handle the throw (who picks the next seed, which message carries it), from Ghidra and the existing captures. Do not guess: an official retry may be invisible in the captures.
3. Fix: a new instance only gets a seed the client accepts. If the generator fails on exactly those seeds, retry seeds server-side at instance creation (attempt limit in `server.toml`); otherwise port the missing throw conditions into `poe-world`. Never special-case an area. The backlog's generator failures (`G2_10_1`, `G4_14`, `G2_1`, `G3_5`, `G1_14`, `G3_8`) go through the same path: an area that fails on every attempt keeps today's "runs without a server grid".

Done when: unit tests over the failing seeds of the batch results, a game test entering `G1_1` on seed 3227977988 succeeds on another seed without a kick, and the backlog and [instance.md](../protocol/instance.md#terrain-check) are updated.

## B3: intro flag
`set_intro_done` runs at entry (`servers/instance-server/src/lib.rs` near line 369), so a player who leaves before the wake-up (or crashes) loses the intro. Set it when the wake-up ends (`waking_until` in `poe-game/src/locomotion.rs`), or on the first of the client's clearing signals ([washed-up.md](../re/washed-up.md#client-behaviour)). A player who leaves during the wake-up washes up again on the next entry: check the spawn too, since `saved character location` runs on leaving.

Done when: rules or unit test, and a game test (variant of `washed-up`) that leaves before the wake-up, re-enters and washes up again, then finishes and does not on a third entry.

## A1: ban commands
`player ban <name> [--duration] [--reason]`, `player unban <name>`, `ban ip <addr>` in the registry (`servers/instance-server/src/commands.rs`, next to `player kick`; admin level; overlay Players tab), and the same in the CLI next to `poe-server account ...`. They use the existing store calls (`ban_account`, `ban_ip`, `lift_ban`, `poe-accounts/src/lib.rs`), so web admin bans and these are one list. A ban kicks an online player, with the text of `bans::banned_text`.

Done when: command unit tests, a `commands` game test line, the overlay control, [server-admin.md](../guides/server-admin.md#commands) and the backlog line removed.

## A2: automatic database backups
A new scheduled task kind `backup` (`poe-web-api/src/scheduler/kind.rs`, next to `restart`; Schedule page in `modules/web-admin`) with `keep` (retention) and a target directory (`[server]` config, default `runtime/backups/`). Uses SQLite's online backup so it runs while the server is up; no shutdown, no countdown. New hosted servers get no task unless the host adds one. Failures show on the Schedule page and in the log. No restore tool: restoring stays a stopped-server file copy, documented.

Done when: `poe-web-api` tests (backup opens and holds the data, retention deletes the oldest, a write during backup is fine), web admin build and `cargo xtask openapi --check`, [hosting.md](../../modules/server/docs/hosting.md#backups-updates-and-maintenance) and [server-admin.md](../guides/server-admin.md#scheduled-tasks).

## P10a: static RE of items before C2
Part 1 of [P10](items-stats.md#p10-items-inventory-equipment-weapon-sets-levels-opus-for-the-re-sonnet-for-storage-and-web-admin), from Ghidra only: the item blob (reader `0x1425aa790`, serializer `0x1425aa4d0`), and the client's inventory messages and the server's replies from the opcode table and handlers. Results go to a new `docs/protocol/items.md`, each field marked static (unconfirmed until C2). Then check [capture C2's checklist](../re/captures.md#planned-capture-c2-for-gameplay-items-stats-life-flasks-passives-skills-monsters-loot-npcs) against it and add any case the code shows and the checklist misses (rare item, corrupted, socketed, stack split, and so on).

Done when: every byte of the blob's reader has a field or a named unknown, the `poe-proto` decoder sketch parses the serializer's layout in a unit test only if it can be done without captures, and P10's spec lists what is still only C2's to answer.

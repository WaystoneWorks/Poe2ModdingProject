# Plan: before P10 (V1, B4, U4, U5, CT, B2, B3, A1, A2, P10a)

Steps the user asked for on 2026-11-06 (V1 to CT) and chose in S1 on 2026-11-05 (B2 to P10a); order and status are in [../PLAN.md](../PLAN.md). Delete each section when its step is done, and this file with the last one. Suggestions not chosen: [backlog.md](backlog.md#suggested-in-s1-not-chosen).

## V1: game update 0.5.5f
The user reports 0.5.5f adds only supporter packs, so no breaking change is expected; `check-build` proves or disproves that, nothing is assumed. Everything moves to the new build, which becomes the only supported one (as with Hotfix 1, [decisions.md](../decisions.md#scope-and-order)). Read the exact version name from the build.

Follow [new-game-version.md](../guides/new-game-version.md) in order: `revert-client`, replace `GameFiles/` from the updated Steam install (read-only copy; the guide's step is the one allowed change outside the deploy commands), keep the old exe, `bundlediff`, `check-build`, signatures, version file, opcode folder, launcher copy, tests, in-game check. Then the rest of the project: Ghidra import ([re/README.md](../re/README.md#a-new-build-in-the-ghidra-project)), CLAUDE.md's build and Ghidra path, `docs/re/addresses`, and every RE address in docs and comments if the image moved (script it from `addr_map`; say in the docs which case holds). About 295 tracked files name `0.5.5e`: script the change, and separate names of the build from history that must stay. `dumps/<new>/`: regenerate what depends on the exe; move terrain vectors and game data unchanged only if `bundlediff` shows no data or terrain file changed, otherwise rerun the batches.

Done when: `check-build` is clean, unit tests of every module and the guide's in-game check pass, the game tests `smoke`, `walk`, `cliffs`, `dungeon`, `r4-travel`, `washed-up`, `commands`, `overlay-pages` pass, `client_hash` is confirmed, `status = "supported"`. The official comparison (guide step 6.4) waits for the user's next official session. Ask before release tags; players on the launcher need the releases, so raise it at the end.

**State (WIP, NOT GATED).** The patch is more than supporter packs. Build name `0.5.5f`, revision 328049. `check-build` exits 0; server, protocol and hook unit tests pass; launcher tests not run yet.
- Protocol: instance opcodes from `0x2ef` up +3, from `0x35d` up +4 (client-to-server ones derived the same way, game tests must confirm `WarpRequest`, `ExitReport`, `Unknown0354`, `Unknown035a`). InstanceDetails has a new astring after the area hash (client +0x40, sent empty; meaning unread). `SocialEntry` class grew but its deserializer is unchanged. Unnamed classes `0x29`, `0x238`, `0x1f1` changed. Old tables stay in Poe2Protocol `capture-opcodes/0.5.5e.hotfix1/` for replay of old captures.
- Client: `instance_ciphers` was inlined, so it is now a site with `session.key_material` (`+0x58`); World moved (`+0x98..0x665` +8, `0x666` +0x2a, `0x668..0x680` +0x2c, `0x690` up +0x28); `dump_factory.py` login base is 1 and factory 2's first switch base is 0x1ae (old baseline labels were off by one).
- Data (`dumps/0.5.5f/bundlediff.tsv`): 699 `.datc64` changed (171 English tables), 2 `.ot`, 2 `.arm` (`past_town_01`, `kalguur_dock_town`), 64,272 files added, 1,040,488 shader cache files unread. So terrain vectors do not carry over unchecked: rerun the batches (about 2 hours, one client at a time).
- 31 addresses could not be placed by script (`0x14212ac10`, `0x14212ac80`, `0x14171ce50` and others, mostly in `docs/re/`; `runtime/v1/conv2.py` prints them): fix or list them in update-compatibility.md.

Left: Ghidra (import in `/0.5.5f/` done, analysis was running: wait, `save_program`, `PortFromAddrMap.java` with `dumps/0.5.5f/addr_map.tsv`, save); game tests `smoke`, `walk`, `cliffs`, `dungeon`, `r4-travel`, `washed-up`, `commands`, `overlay-pages`; `client_hash` then `hashes_confirmed = true`, `status = "supported"`, `cargo xtask versions`; launcher `cargo test`; batches; docs (`update-compatibility.md`, `decisions.md` scope line, `re/README.md`, `dump_factory.py` usage, guide: `capture-opcodes/`, per-opcode renumber check, `bundlediff` `unread`, `dumps/README.md`); clear `dumps/0.5.5e.hotfix1/` once nothing needs it (the old exe stays), and `GameFiles-0.5.5e.hotfix1/` after the Ghidra port.

## B4: snaps at checkpoints and waypoints
The user sees slight teleports when interacting with checkpoints and waypoints. Their guess: an interaction range issue, the server not agreeing with what the client does. This is movement, so the [exact port principle](../decisions.md#movement-and-world) applies: no DLL snap patch, no fitting.

Facts ([world-travel.md](../re/world-travel.md)): a far click gets official `StartAction` and ack at the click, no `0x64`, `ActionEvent` on arrival; a click from 41.4 cells acted 0.4 s later at 26.0 cells; clicks from up to 25.5 cells act at once.

1. Reproduce and measure: hidden game test with `"dev.drift_check" = true`, click and walk into both object kinds, from near, far and moving, in WASD and mouse mode. Log every `0x64` the server sends and the client's own position per frame (movement log), so each snap has a frame, a distance and a cause. A snap also comes from the checkpoint touch or the interaction's walk, not only range: test each.
2. Compare with the official sequence in `2026-11-02_18-31-34_336` (parts 1-5 of its checklist), and read the client's interaction walk in Ghidra: stop distance, how it ends, what it sends.
3. Port the client's rule into `poe-game`, with rules tests from the capture.

Done when: new game tests with `max_drift` show no correction in every case above, and the user's game test confirms (movement keeps user sign-off). Add the facts to world-travel.md.

## U4: launcher and web admin layout
The user finds the two inconsistent in layout and cluttered, with some things in the wrong order, after several attempts. U1 and U2 scored 9/10 and did not solve it: each reviewed one UI alone and mostly patched what was there. So this step changes the method. The style (Ash & Blood) is fine and stays; this is about layout.

Two fixes first, launcher:
- News, "Read more" (`modules/launcher/src/pages/News.svelte`): opening a post shrinks the UI, then expands it, and it looks different afterwards. Find the cause and test it.
- The launcher version in the bottom right goes on the left.

Method:
1. **Reviewer:** the thread's main agent (Opus 5.5, medium) starts a fresh sub-agent each round (`Agent`, `model: "opus"`, `effort: "medium"`, `run_in_background: false`). It reports only. Its brief: score the whole layout of the launcher and the whole web admin out of 10, every page and dialog, from headless screenshots at several window sizes as well as the source. Separate scores: launcher, web admin, consistency between them (same kind of page has the same skeleton: title, primary action, filters, content, in the same places; same order of information). Name for each page what comes first and whether it should; clutter; suggestions including restructuring, not only patches. Calibration: the user rejected a result scored 9/10, so every score above 8 cites screenshot evidence, and a reviewer does not reward an earlier round's work for being better than before.
2. **Layout rules first:** before page work, the main agent writes one page in the docs (`docs/architecture/ui-layout.md`): the page skeletons and ordering rules both apps follow. Later fixes apply the rules rather than one page's complaint.
3. **Replace, do not add:** if a layout could be better another way, change it; do not keep a poor layout and add to it.
4. **Drastic changes ask first:** navigation structure, merging or splitting pages, moving a page's main content. Show the user a mockup through AskUserQuestion with options and previews, recommended first; build after the answer ([decisions.md](../decisions.md#launcher-and-web-admin)).
5. Repeat until all three scores reach **9.5/10**. Record each round here.

Seeing the UI: headless only (web admin against a dev server, launcher frontend with its Tauri calls mocked); never the user's browser. Done when: 9.5/10 on all three, launcher `cargo test`, `cargo fmt --check`, frontend tests and build; web admin build and tests, `poe-web-api` tests, `cargo xtask openapi --check`; docs updated. No release unless the user asks.

Scores: none yet.

## U5: DLL overlay layout
The user finds the overlay a cluttered mess and wants the layout changed; U3's 9/10 did not solve it. Same method as U4, target **9.5/10**: reviewer sub-agent (Opus 5.5, medium) scoring every page from the hidden `overlay-pages` screenshots (`runtime/game-test/overlay-pages/`), layout rules added to `ui-layout.md`, replace rather than add, drastic changes asked first with ASCII mockups. The look (ImGui `StyleColorsDark`, stock font) stays; earlier layout decisions such as "the sidebar stays" may be proposed for change this way, not changed silently. Code: `modules/client-hook/poe-hook-core/src/ui/`.

Done when: 9.5/10, `cargo xtask build-dll`, `cargo test -p poe-hook-shared`, `cargo fmt --check`, `overlay-pages` passes, docs updated.

Scores: none yet.

## CT: capture checklist tool
For official captures the user records, C2 first: an overlay page showing the checklist with the current step, and keybindings the user sets in the overlay. **Official servers are read-only:** this tool only reads keys and writes local files; nothing is sent, altered or injected, and it works under the read-only latch.

- Actions, each bindable: next step, previous step, add a marker, show or hide the checklist. Bindings live in `logs/poe-hook/overlay.toml`, warn on a conflict, have an unbound state, and must not swallow the key from the game. They are the one exception to "no hotkeys" (that decision covers commands).
- Each step or marker writes a line to `markers.jsonl` in the session folder: time, capture frame, packet index, step id, step text. The current step survives a client restart in the same session.
- Checklists are data files, one per capture, starting with C2; [captures.md](../re/captures.md) links to the file so the steps have one owner. Selecting one is a page control.
- `scripts/re/capture_steps.py <session>`: splits `packets.jsonl` by step, prints a per-step summary and flags steps with no marker.

Done when: unit tests, a hidden private-server game test (bindings by `auto_keys`, markers checked by the script), `official-mode.md` and client-dll.md updated, C2's "note the clock time" wording replaced. Official use is the user's.

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
Part 1 of [P10](items-stats.md#p10-items-inventory-equipment-weapon-sets-levels-opus-for-the-re-sonnet-for-storage-and-web-admin), from Ghidra only: the item blob (reader `0x1425bab20`, serializer `0x1425ba860`), and the client's inventory messages and the server's replies from the opcode table and handlers. Results go to a new `docs/protocol/items.md`, each field marked static (unconfirmed until C2). Then check [capture C2's checklist](../re/captures.md#planned-capture-c2-for-gameplay-items-stats-life-flasks-passives-skills-monsters-loot-npcs) against it and add any case the code shows and the checklist misses (rare item, corrupted, socketed, stack split, and so on).

Done when: every byte of the blob's reader has a field or a named unknown, the `poe-proto` decoder sketch parses the serializer's layout in a unit test only if it can be done without captures, and P10's spec lists what is still only C2's to answer.

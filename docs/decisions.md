# User decisions

Lasting choices the user made, so nobody asks again. Keep one line per decision and replace a line when a decision changes. Limit: 1,800 words.

## Scope and order
- Client 0.5.5e Hotfix 1 (`0.5.5e.hotfix1`) is the only supported build; older addresses and files are gone (2026-10-29).
- Order (2026-11-04): the step table in [PLAN.md](PLAN.md); R4 goes where it fits best (before life and monsters). Items, stats and the rest no longer wait for R4.
- PLAN.md is the ordered index; each step's detailed spec is a file in [plans/](plans/backlog.md), deleted when done (2026-11-04). No handoff files (2026-10-31). Agents at 300k hand off to a new T3 thread themselves; Opus delegates routine work to Sonnet (2026-10-31).

## Terrain
- Goal: 1:1 tile hash, doodad hash and collision grid for every area, topology and orientation in the default league mode (4,508 combinations). The 84 league-mode topologies and the client's server-only spawn scatter in the doodad pass are out of scope.
- Acceptance: client batches with 50 random seeds; a combination counts when every seed matches or has a documented reason (39 combinations error in the client on every seed). Out of scope: the 10 fixed areas, Incursion temples, effects of successful league rolls. Never special-case an area.
- `[terrain] generate` and `force_layout` default on.
- 2026-11-02: the generated collision grid and spawn layout are the default (`generated_grid = true`); the client terrain upload (`[spawn.upload]`) is off, a fallback for trusted hosts and areas the generator cannot make. Closes audit S-08 for the default config.

## Movement and world
- **Principle (2026-11-03): the server runs an exact port of the client's movement code.** The client predicts its own movement; the server is authoritative and corrects it (a `0x64` with a cell that differs from the client's grid snaps it: `0x1421497c0` -> `0x141ddb6f0`). Official servers show no snaps because their code matches the client's; fitting or approximating cannot work. Source: https://www.pathofexile.com/forum/view-thread/889669/filter-account-type/staff (Chris Wilson, 2014: client prediction is mandatory, the server resyncs drifted entities).
- Restart (2026-11-03): the earlier port still snapped in the user's game test. One exact port for all input modes (WASD, click-to-move, controller), roll and sprint, from full RE of Positioned, Pathfinding and Actor. No DLL snap patch, no client-authoritative shortcut (both declined). The old simulation is deleted behind a trait seam ([PLAN.md](PLAN.md)). Proof: the user's game tests only, after offline checks. The user captures official WASD, click-to-move, controller.
- Timing: the simulation steps a fixed `dt = frame_ms / 1000` (33 ms) per tick, because the client advances each frame by the `frame_ms` of its marker (RE 2026-11-02, [movement.md](protocol/movement.md#timing)). Absolute 33 ms deadlines; frames missed in a stall are sent as a burst, like official servers.
- Sprint end (2026-11-02): the official client coasts at walking speed after a release-ended sprint (30 frames), our replies match the official ones, so it is client state. Revisit when Player +0x20a (`0x141b76f01`) is traced ([movement.md](protocol/movement.md#coasting-after-a-sprint)).
- Proof: every input sequence of the official captures replays with identical opcodes, fields and frame offsets.
- Movement curves are required game data, no stand-in (2026-11-03): the server refuses a player without the curves or the class `offset_scale`.
- Unlocks: per character, locked by default; admin command and web admin button.
- The terms-of-service screen stays hidden: never set account flag byte 0 bits 2, 3, 4 or 7.

## Public release
- MIT licence only. All repos public. Private vulnerability reporting on. Official mode stays public and documented ([official-mode.md](guides/official-mode.md)), with a launcher entry "Official (read-only)".
- Commits use the owner account's GitHub noreply address, set per repository. Keep `CLAUDE.md` and co-author trailers. Keep the HNC `key_xor` table as a documented constant behind a narrow gitleaks allowlist. Keep `terrain-matrix.tsv`.
- Machine-hash Steam login removed. Test passwords are never real. Launcher app id `org.poe2modding.launcher`. The `ConnectEx` guard exists.
- Findings: no credential, capture, GGG asset or game table in history. Exception (2026-11-04): the tracker's names-only `tracker/rows.json` (id, section, display name). Real `AddObject` test blobs hold only anonymised names. Official-capture fixtures are movement-only.

## Mods
- Native Rust libraries (versioned C ABI) plus data-only mods; no WebAssembly or Lua tier for now.
- One `mod.toml` and zip per mod, `side = "client" | "server" | "both"`. SDK in its own repo; server loader in Poe2Server; shared parser in `poe-hook-mods`.
- Required mods come from the server (`/api/v1/mods/{id}/{version}.zip`, exact version and SHA-256 pin). The Poe2Mods index is for the browser only.
- Launcher sync: Off / Ask / Auto; Auto means everything, code included. Per-server mod sets: other mods are off there unless enabled.
- The hook reports loaded mods at login and the server refuses a mismatch; `[mods] allow_extra_client_mods` allows extra client-only mods.
- Server mods just load (owner's responsibility; ABI and version checks refuse incompatible ones). Never hot-reload.
- Known limits: "required" is a promise a modified client can ignore; a server-only override of a table the client also reads is a trap, so the loader warns.

## Launcher and web admin
- Launcher: Tauri 2 and Svelte. No launcher login: Play opens the game's login screen pointed at the selected server, and rows offer Web admin and Create account. No account creation in the launcher.
- Several hosted servers at once, each with its own folder and shared packages; free ports chosen automatically. Delete really deletes after typing the name. Servers tabs: My servers / Browse public / Host. Server update: notify and one click, with backup.
- Square window frame (rounded corners blanked the window in nested KWin). "Minimize while the game runs" means minimize on start, restore on exit (meaning unconfirmed).
- Web admin: Stop/Restart with countdown, live charts, Players with bans, config editor on for admins, scheduled restarts, MOTD. First admin is created on a loopback-only first-run page; `/register` is the public page; the game's Create account button opens it (`register_url`).
- UI style: direction "Ash & Blood" with the rune seal logo (launcher, web admin, tracker site; not the DLL overlay). For redesigned screens, the user sees a mockup before building; for the overlay, the ASCII mockups in its plan are enough (2026-11-04).

## Config (2026-11-05)
- The server is the terrain authority: generation, its own grid and its forced layout are always on, not options. The client terrain upload and the mismatch log go.
- Research and test switches go (seed sweep, known seeds, remote blob experiments, fake terrain hash, movement trace); drift check, position sync and debug link stay.
- Account placeholders go: full access is always on, stash tabs and the account name prefix leave the config.
- Game and protocol facts stay in the config. Plan: [plans/config-cleanup.md](plans/config-cleanup.md).

## New features (2026-11-04)
Specs in [plans/](plans/backlog.md); each spec repeats its decisions in detail.
- Sign-off for new features: agent tests are enough (unit, offline checks, agent game tests). Movement keeps the user's game tests.
- Hosting: GitHub, pushed by hand one repository at a time with named refs only (`git push origin main`, never `--all` or `--mirror`). Release binaries are built only in CI, because a local build embeds the builder's home path; `cargo xtask release-mirror` output is for local tests and is never published. The launcher and server read a configurable release source.
- Overlay: ImGui `StyleColorsDark` with the stock font; the sidebar stays; Features becomes Settings with one "Show slow hook popups" checkbox; settings in `logs/poe-hook/overlay.toml`; every page redesigned; one Debug entry with sub-tabs and a Console replaces the Commands page; non-admins do not see admin-only controls; no hotkeys.
- Leagues: in the database, managed in the web admin; new servers have none; without a league login works and no league list is sent; the `[[leagues]]` config is dropped without migration; HC/SSF checkboxes create the official variants; banners are `LeagueFlag` rows; mechanics listed from game data and stored only; states active/hidden/ended with migration; start and end dates; a default league. Moving a character (2026-11-04): players only leave SSF and hardcore, one way, through the client's own League Migrations button; admins move any offline character to any league in the web admin; a league stores its hardcore death rule (softcore or stay) now, used by P13.
- Terrain mismatch: tile and doodad hash at entry; everyone is always kicked to the previous instance, else the town, else character select; the DLL shows an alert with hashes and a copy button and exports its layout.
- Stats: PoB2's calculation rules ported to Rust (latest PoB2 = 0.5.5e), checked against PoB2 headless; the server computes and sends every stat.
- PoB2 reference pinned to the latest commit `bb52d6b3`, not the latest release, because v0.23.1 predates the 0.5.5 data (user decision 2026-11-05). Owner: [architecture/stats.md](architecture/stats.md).
- Items: inventory and equipment, no stash; basic orbs and quality currency first; a chat line per not-implemented stat on every equip (and per not-implemented passive line on allocation); new characters start empty.
- Life: pools, regeneration, damage taken and death (official-like with the XP penalty) first; flasks, charms and belt charm slots; no mana costs or spirit yet.
- Passives: ascendancy points only by command until trials exist; free refunds; weapon-set points with swap; the web admin edits inventory and tree for admins.
- Commands: two levels, every cheat is admin-only; verb-first subcommands with aliases; every command has an overlay counterpart; stat edits are a debug modifier layer; class change keeps level and items and resets the tree, rejoining the instance.
- Item creator: anything allowed with "illegal" tags, game-style tooltip with art, paste, templates, bulk and random spawn, edit in place; overlay and commands only.
- Skills: the official gem panel; punch, weapon default attacks and one starter skill per class; exact port of action timing.
- Monsters: the Riverbank and Clearfell first; AI from game data only, no AI calibration capture; XP from kills.
- Loot: game data plus configurable tables with cited community research; official-like ownership with the party leader's allocation setting; basic parties. NPCs and vendors, checkpoints and wells are in the plan.
- Tracker ([guides/tracker.md](guides/tracker.md)): static site, statuses in a hub file edited by commit, sections from game data plus project sections, no hour estimates (rows weigh equally; partial counts 0.5, implemented 0.85, fully functional 1, not planned is left out), built locally until GitHub Pages is available.

## Repositories
- The hub holds docs, xtask and scripts; everything else is a submodule under `modules/`; nested submodules stay so each repo builds alone. Versions live in Poe2Protocol. Repo map: [overview.md](overview.md).

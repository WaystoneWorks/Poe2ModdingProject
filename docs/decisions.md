# User decisions

Lasting choices the user made, so nobody asks again. Keep one line per decision and replace a line when a decision changes. Limit: 1,000 words.

## Scope and order
- Client 0.5.5e Hotfix 1 (`0.5.5e.hotfix1`) is the only supported build; older addresses and files are gone (2026-10-29).
- Order: R2 collision finished fully, then R3 movement, then R4 entities and world map (2026-10-31). Items and entities stay deferred until then, with everything depending on them.
- One central plan ([PLAN.md](PLAN.md)); no handoff files, no tracker (2026-10-31). Agents at 300k hand off to a new T3 thread themselves; Opus delegates routine work to Sonnet (2026-10-31).

## Terrain
- Goal: 1:1 tile hash, doodad hash and collision grid for every area, topology and orientation in the default league mode (4,508 combinations). The 84 league-mode topologies and the client's server-only spawn scatter in the doodad pass are out of scope.
- Acceptance: client batches with 50 random seeds; a combination counts when every seed matches or has a documented reason (39 combinations error in the client on every seed). Out of scope: the 10 fixed areas, Incursion temples, effects of successful league rolls. Never special-case an area.
- `[terrain] generate` and `force_layout` default on.
- 2026-11-02: the generated collision grid and spawn layout are the default (`generated_grid = true`); the client terrain upload (`[spawn.upload]`) is off, a fallback for trusted hosts and areas the generator cannot make. Closes audit S-08 for the default config.

## Movement and world
- **Principle (2026-11-03): the server runs an exact port of the client's movement code.** The client predicts its own movement; the server is authoritative and corrects it (a `0x64` with a cell that differs from the client's grid snaps it: `0x1421497c0` -> `0x141ddb6f0`). Official servers show no snaps because their code matches the client's; fitting or approximating cannot work. Source: https://www.pathofexile.com/forum/view-thread/889669/filter-account-type/staff (Chris Wilson, 2014: client prediction is mandatory, the server resyncs drifted entities).
- Restart (2026-11-03): the earlier port still snapped in the user's game test. One exact port for all input modes (WASD, click-to-move, controller), roll and sprint, from full RE of Positioned, Pathfinding and Actor. No DLL snap patch, no client-authoritative shortcut (both declined). The old simulation is deleted behind a trait seam ([PLAN.md](PLAN.md)). Proof: the user's game tests only, after offline checks. The user captures official WASD, click-to-move, controller.
- Timing: the simulation steps a fixed `dt = frame_ms / 1000` (33 ms) per tick, because the client advances each frame by the `frame_ms` of its marker (RE 2026-11-02, [movement.md](protocol/movement.md#timing)). Absolute 33 ms deadlines; frames missed in a stall are sent as a burst, like official servers.
- Sprint end (2026-11-02): the official client coasts at walking speed after a release-ended sprint (30 frames), our replies match the official ones, so it is client state (`sprint_release_ends_at_sprint_speed = true` follows our client). Revisit when Player +0x20a (`0x141b76f01`) is traced ([movement.md](protocol/movement.md#coasting-after-a-sprint)).
- Proof: every input sequence of the official captures replays with identical opcodes, fields and frame offsets.
- Movement curves are required game data, no stand-in (2026-11-03): the server refuses a player without the curves or the class `offset_scale`.
- Unlocks: per character, locked by default; admin command and web admin button.
- The terms-of-service screen stays hidden: never set account flag byte 0 bits 2, 3, 4 or 7.

## Public release
- MIT licence only. All repos public. Private vulnerability reporting on. Official mode stays public and documented ([official-mode.md](guides/official-mode.md)), with a launcher entry "Official (read-only)".
- Keep the commit email, `CLAUDE.md`, co-author trailers. Keep the HNC `key_xor` table as a documented constant behind a narrow gitleaks allowlist. Keep `terrain-matrix.tsv`.
- Machine-hash Steam login removed. Test passwords are never real. Launcher app id `org.poe2modding.launcher`. The `ConnectEx` guard exists.
- Findings: no credential, capture, GGG asset or game table in history. Real `AddObject` test blobs hold only anonymised names. Official-capture fixtures are movement-only.

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
- UI style: direction "Ash & Blood" with the rune seal logo. For redesigned screens, the user sees a mockup before building.

## Repositories
- The hub holds docs, xtask and scripts; everything else is a submodule under `modules/`; nested submodules stay so each repo builds alone. Versions live in Poe2Protocol. Repo map: [overview.md](overview.md).

# Plan: config cleanup (C1)

Step C1 of [../PLAN.md](../PLAN.md). The user checked the config options on 2026-11-05 ([decisions.md](../decisions.md#config-2026-11-05)). Removing an option means removing its code path too, not only the key. Old configs that still name a removed key must load (ignore it with a warning, as `security_warnings` does for removed keys) so the launcher's carried-over `server.toml` keeps working.

## Remove (always on, option gone)
- `[terrain] generate`, `generated_grid`, `force_layout`: the server always generates each new instance, uses its own grid and spawn layout, and forces its layout. Areas the generator cannot make (`travel-survey.py` lists them) keep today's fallback of no server grid only if no client upload is needed; decide and document what they get (likely the client's files with no terrain check, as on a generator error today).
- `[terrain] mismatch_log` and the `cargo xtask terrain-matrix` reader of it (`xtask/src/terrain_matrix.rs`). `hash_timeout_secs` stays.

## Delete (code and option)
- Client terrain upload: `[spawn.upload]` (enabled, max_bytes, max_layout_bytes, max_grid_bytes, wait_ms, wait_upload_secs), `[spawn] layout_dir`, `filler`, and the upload path (`instance-server` `terrain_store.rs`, `sync.rs` upload offers, `spawn.rs` layout cache). The client DLL side that offers uploads (`poe_hook_core::side`, "terrain upload ... offer refused") goes in client-hook. `[spawn] intro_areas`, `start_tiles`, `player_spacing` stay. Check `poe-world` `filler` uses: generator code keeps its own constants if it needs them.
- `[dev] known_seeds`, the seed sweep (`sweep`, `sweep_results`, env `POE_SWEEP`), `remote_blob_omit`, `remote_animated_path`, `fake_terrain_hash`, `movement_trace` (and `scripts/re/movement_trace.py`, uses in `scripts/dev-config.py`, `scripts/re/gen_crazy_keys.py`, game tests `crazy-keys`, `sprint-turn`, `terrain-mismatch`). The game test `terrain-mismatch` needs `fake_terrain_hash`: delete it or test the kick another way (unit test). `drift_check`, `position_sync`, `debug_link`, `drift_interval_ms` stay.
- `[accounts] full_access` (always full access), `stash_tabs` (official new-account default "1".."4" in code or protocol data), `name_prefix` (the launcher `host.rs` and `poe-store` use it: decide the auto-account name without it).

## Keep
Game and protocol facts stay in the config (user decision): `[instance] tick_ms`, `first_entity_id`, `[network.login] close_after_handoff`, `[accounts] flags`, `[chat]`, `[travel]`, `[movement]`, `[player]`, `[inventories]`, `[spawn]` start options.

## Done when
`server.toml` and `server.example.toml` no longer have these keys; the code paths are gone; `cargo xtask server test`, `openapi --check`, `cargo test -p xtask`, client-hook and launcher builds pass; the web admin Config page and the launcher Host page still work; game tests `walk`, `cliffs`, `dungeon`, `r4-objects`, `r4-areas` pass hidden; docs (hosting.md, setup.md, instance-world.md, server-admin.md) describe the new behaviour. Release only if the user asks.

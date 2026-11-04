# Plan: kick a player whose terrain does not match the server's

Step P4 of [../PLAN.md](../PLAN.md). Terrain status: [../status/terrain.md](../status/terrain.md). The client reports **C→S `0x009a` TerrainHashes** (`u8, u32 tile hash, u32 doodad hash`) after it generates an area ([../protocol/instance.md](../protocol/instance.md)); the server's generator computes both hashes (`poe-world` `hash.rs`, `generate.rs`, `doodads.rs`). Today a mismatch is only logged, and the player keeps walking on a grid that differs from the client's, which shows up as snaps.

## User decisions (2026-11-04)
- Compare **tile and doodad hash at area entry**.
- **Everyone is always kicked** on a mismatch: no config switch, no admin exception.
- Destination: the **previous instance** at the place the player left it; if it no longer exists, a new instance of the act's **town**; if that also mismatches, back to **character select**.
- The DLL shows a popup like the slow-hook notice but larger, with area, seed, layout (topology and orientation), both hashes on both sides, a **Copy report** button, and it **exports the client's layout automatically**.

## Server (instance server; Sonnet, Opus only if the hash source is unclear)
1. **Expected hashes per instance.** When an instance is created with `generated_grid = true`, keep the generator's `(tile_hash, doodad_hash)` in the instance. Instances without a generated layout (the uploaded-terrain fallback, the 10 fixed areas) have no expected hashes: their check is skipped with an `info` log line "terrain check skipped: no generated layout".
2. **Compare** in the `0x009a` handler: equal means ok. Otherwise a mismatch record: account, character, instance id, area id and name, seed, topology, orientation, client and server tile hash, client and server doodad hash, server build (git describe), client build.
3. **No hashes.** If the client never sends `0x009a` within `[terrain] hash_timeout_secs` (default 30) after the area load started, treat it as a mismatch with reason "client terrain generation failed" (the client throws `TerrainGenerationException` on some seeds and then never reports).
4. **Previous instance.** Each player session keeps `previous: Option<(instance id, cell, transition id)>`, set on every transfer (commands, transitions, waypoints once R4 exists). On a mismatch the session is transferred there (same cell, or in front of the transition). If that instance closed, create or join the act town's instance (`WorldAreas` act and `IsTown`, from `poe-data`), placed at its start. If the destination also mismatches, or two kicks happened within 60 s, disconnect to character select with the reason in the log.
5. **Order of events:** send the alert on the debug link, wait up to 3 s for the DLL's `ack export` (so the client still has the area loaded when it exports), then transfer. Without a DLL (no debug link) transfer at once and send a `<Server>` chat line instead.
6. **Records:** the mismatch line in the server log at `warn`, and a row in `<data>/terrain_mismatches.tsv` (same fields plus time) that `cargo xtask terrain-matrix` can read, so live mismatches feed the terrain status.
7. Tests: unit tests for compare, timeout and destination choice (previous, town, select, loop guard); an instance-server test with a fake client that reports wrong hashes; a dev-only switch `[dev] fake_terrain_hash = true` (refused unless `[dev]` is on) that makes the server expect a wrong hash, for the game test.

## Debug link message
`Kind::Debug` lines (side channel, [../protocol/side-channel.md](../protocol/side-channel.md)):
```
alert	terrain_mismatch
area	G1_2 (Clearfell)
seed	123456789
layout	topology 3, orientation 1
tile	client 0x1a2b3c4d  server 0x5e6f7081
doodad	client 0x11111111  server 0x11111111
reason	tile hash differs
dest	previous instance 7 (G1_1 Riverbank)
report	terrain-mismatch build=0.5.5e.hotfix1 server=<git> area=G1_2 seed=123456789 topo=3 orient=1 tile=1a2b3c4d/5e6f7081 doodad=11111111/11111111
end
```
The DLL answers `Kind::Command` `ack export <path>` after its export (or `ack export failed <why>`).

## DLL (Sonnet)
1. `devlink.rs` parses `alert` blocks into `ui::Alert` ([overlay.md](overlay.md#popups-and-notices)).
2. On `terrain_mismatch`: run the existing area export (Minimap's "Export area": `terrain_layout_*.tsv`, `terrain_grid_*.bin`) into the session folder with the mismatch's hashes in the file names, then send the ack.
3. Popup (centred modal, stays until OK):
```
+------------- Terrain does not match the server --------------+
| Area     G1_2 (Clearfell)    seed 123456789                   |
| Layout   topology 3, orientation 1                            |
| Tile     client 1a2b3c4d   server 5e6f7081   DIFFERENT        |
| Doodad   client 11111111   server 11111111   same             |
| You were moved to: previous instance 7 (G1_1 Riverbank)       |
| Client layout exported: logs/poe-hook/<session>/terrain_...   |
|                                [Copy report] [Open folder] [OK]|
+---------------------------------------------------------------+
```
4. The overlay opens on its own for the alert even if it is hidden (the alert is drawn without the main window).

## Done when
- A forced mismatch (`fake_terrain_hash`) in an agent game test: the popup shows, the layout files exist, the player is in the previous instance; with the previous instance closed, the player lands in the town; a second forced mismatch in a row goes to character select.
- Matching areas (the game tests `walk`, `cliffs`, `dungeon`) never trigger it.
- Docs: instance.md (`0x009a` handling), side-channel.md (alert lines), client-dll.md (alerts), server-admin.md (what players see), terrain.md (live mismatch file).

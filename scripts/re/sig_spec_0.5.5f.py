"""Spec for scripts/re/sig_gen.py: the 0.5.5f entries of modules/client-hook/signatures/0.5.5f.toml.

Addresses are Ghidra addresses (image base 0x140000000) of client 0.5.5f (0.5.5f, revision 328049).
Made from the previous build's spec with scripts/re/addr_map.py (every address moved by its function's delta). `features` names the
DLL features that are off when the entry does not resolve (see poe-hook-core `start_features`).
For another build, run the generator on that exe with the (moved) addresses.
"""
SPEC_NAME = "sig_spec_0.5.5f.py"

BUILD = dict(
    version="0.5.5f",
    build_revision="328049",
    revision_pattern="25 53 2e 70 6f 65 63 61 70 00 00 00 00 00 00 00 20 <rev:bytes6> 00",
    pe_timestamp=0x6AED487D,
    image_size=0x04CBA000,
    exe_sha256="7e0d36655e6e788202d2d588429c45064bbf87caec95938ebb19a317947c834e",
)

DUMP = ["dump_object_types"]
# gen_batch (in-client batch terrain generation) needs everything the area export needs, plus its own.
EXPORT = ["area_export", "gen_batch"]
BATCH = ["gen_batch"]
TRACE = ["generator_trace"]

SIGS = [
    # ---- loader: standalone login ----
    dict(name="client_platform_detect", addr=0x1421a6e90, features=["login_patch"],
         expect="40 55 53", patch="31 c0 c3",
         note="ClientPlatform_Detect; patch = xor eax,eax; ret (platform 0)"),
    dict(name="standalone_patcher_run", addr=0x140118C10, features=["patcher_skip"],
         expect="48 8b c4", patch="b0 01 c3",
         note="StandalonePatcher_Run; patch = mov al,1; ret (skip the patcher)"),
    dict(name="client_platform_get", addr=0x14010C450, features=["login_cache"],
         note="cached platform getter; anchor of the two cache globals"),
    dict(name="platform_cache_guard", addr=0x14472f634, kind="ref", anchor="client_platform_get",
         features=["login_cache"], note="thread-safe-static guard of the cached platform"),
    dict(name="platform_cache_value", addr=0x14472f638, kind="ref", anchor="client_platform_get",
         features=["login_cache"], note="the cached platform value (i32)"),
    # ---- crypto bypass and side channel ----
    dict(name="verify_and_derive", addr=0x1421AEFE0, features=["crypto_bypass"],
         note="signature check + key derivation (hooked, replaced for trusted servers)"),
    dict(name="crypto_dh_agree", addr=0x1421AEE10, features=["crypto_bypass"],
         note="DH agree + SHA-512 into the session key buffer; anchor of the key buffer offset"),
    dict(name="instance_session_handler", addr=0x142131210, features=["side_channel"],
         note="game-session packet handler; anchor of instance_ciphers and session.key_material"),
    dict(name="instance_ciphers", addr=0x1421312E7, kind="site", anchor="instance_session_handler",
         features=["side_channel"],
         note="EnableEncryption case, before the packet-cipher allocation (the builder is inlined since 0.5.5f): rbx = instance details"),
    # ---- packet capture ----
    dict(name="read_message", addr=0x1421D5A10, features=["packets"]),
    dict(name="session_send", addr=0x14212EB20, features=["packets"]),
    dict(name="stream_flush", addr=0x1421a7f90, features=["packets"]),
    dict(name="packet_flush_plaintext", addr=0x1421a8007, kind="site", anchor="stream_flush",
         features=["packets"], note="after the lock, before the cipher; rbx = stream"),
    dict(name="login_session_loop", addr=0x1420F5C10, features=["packets"],
         note="receive loop of the login session (caller of read_message); its .pdata range gives the channel"),
    dict(name="instance_session_loop", addr=0x14212FE10, features=["packets"],
         note="receive loop of the instance session; its .pdata range gives the channel"),
    dict(name="stream_read", addr=0x1421A7D00, features=["packets"]),
    dict(name="stream_write", addr=0x1421A7E30, features=["packets"]),
    # ---- entity and world research (dump_object_types) ----
    dict(name="sim_frame_processor", addr=0x142143530, features=DUMP,
         note="frame processor; unique caller, anchor of object_type_lookup"),
    dict(name="object_type_lookup", addr=0x14169bf40, kind="ref", anchor="sim_frame_processor",
         features=DUMP, expect_fn=True, note="a clone-like function: found by its unique caller"),
    dict(name="read_initial_state", addr=0x141E7F190, features=DUMP),
    dict(name="path_plan", addr=0x141EDE540, features=["path_log"],
         note="grid pathfinder (JPS-style search, A* fallback): (goal*, entity, params*, ..., out path*, out count*, ...); hooked by path_log to log the player's plans"),
    dict(name="entity_destroy", addr=0x141E7F690, features=DUMP),
    dict(name="ui_set_visible", addr=0x1427C12B0, features=["ui_panels"],
         note="UI element SetVisible (element, bool): flags +0x168 bit 11, parent +0xb8, name wstring +0x98; hooked by the state export"),
    dict(name="actor_sim_handler", addr=0x142158B60, features=["position_sync", "inspect"],
         note="Actor component simulation handler (0x64 WASD, 0x1c8 start action, ...)"),
    dict(name="roll_end", addr=0x141B85035, features=["position_sync"],
         note="end of a dodge roll: reads the sprint-key bit"),
    dict(name="noop_reader", addr=0x14010C9B0, features=["entity_trace"], pdata=False,
         note="shared `ret 0` stub used as the reader of components without initial state"),
    dict(name="entity_update", addr=0x141E7F100, features=DUMP),
    dict(name="frame_drain", addr=0x14213f8f0, features=DUMP),
    dict(name="entity_tick", addr=0x141E8B960, features=DUMP),
    dict(name="game_update", addr=0x141687120, features=DUMP),
    dict(name="set_orientation", addr=0x141DE99D0, features=DUMP),
    dict(name="load_area_client", addr=0x141683940, features=DUMP),
    dict(name="load_area_headless", addr=0x14213E730, features=DUMP + BATCH,
         note="HeadlessWorld_LoadArea (base world vfunc +0x1e0): the sequence gen_batch repeats; anchor of the world generation fields"),
    dict(name="positioned_reader", addr=0x141DE5B50, features=DUMP + EXPORT),
    dict(name="terrain_construct", addr=0x1415AC140, features=DUMP + EXPORT,
         note="sets the terrain vtable; anchor of terrain_vtable"),
    dict(name="terrain_vtable", addr=0x14339A108, kind="ref", anchor="terrain_construct",
         features=DUMP + EXPORT, note="identifies the area terrain object inside the world"),
    # ---- entity probe (calls game functions 5 s after the player spawned) ----
    dict(name="probe_anchor", addr=0x140238ba0, features=["entity_probe"],
         note="calls the render getter, the visibility refresh and the terrain sampler"),
    dict(name="entity_get_render", addr=0x1401558B0, kind="ref", anchor="probe_anchor", index=0,
         features=["entity_probe"], expect_fn=True, note="entity -> Render component by name"),
    dict(name="render_refresh", addr=0x1416B2160, kind="ref", anchor="probe_anchor",
         features=["entity_probe"], expect_fn=True),
    dict(name="terrain_sample", addr=0x141D19FD0, kind="ref", anchor="probe_anchor",
         features=["entity_probe"], expect_fn=True, note="terrain height at (x, y)"),
    dict(name="positioned_height", addr=0x141DF2770, features=["entity_probe"]),
    # ---- area export ----
    dict(name="terrain_driver", addr=0x14200D1F0, features=EXPORT),
    dict(name="terrain_add_object", addr=0x142005F20, features=EXPORT),
    dict(name="tile_doodads", addr=0x142001AC0, features=EXPORT + TRACE),
    dict(name="doodad_hash_site", addr=0x142001DF3, kind="site", anchor="tile_doodads",
         features=EXPORT, note="right after a doodad's path hash: eax = hash, r15 = tile entry"),
    # ---- gen_batch: a synthetic world and generator (docs/re/terrain/batch.md) ----
    dict(name="world_construct_client", addr=0x1416859C0, features=BATCH,
         note="ClientWorld constructor (this, frame mode u8, flag u8); the batch makes its own worlds"),
    dict(name="terrain_gen_construct", addr=0x141FFE1D0, features=BATCH,
         note="TerrainGen_Construct(generator, world): base generator vtable 0x143503478"),
    dict(name="terrain_gen_destroy", addr=0x141FFE5F0, features=BATCH, note="generator destructor"),
    dict(name="terrain_topology_pick", addr=0x142007A30, features=BATCH,
         note="reads map_force_topology (0xb92) / map_force_orientation (0xb93) from the world stats; anchor of fields"),
    dict(name="world_replace", addr=0x141013960, features=BATCH,
         note="creates the in-game world and destroys the old one through vfunc +0x20 (deleting destructor)"),
    dict(name="vcrt_getptd", addr=0x142C26748, features=BATCH,
         note="__vcrt_getptd(): the thread's C++ exception state (+0x20/+0x28 exception and context records, +0x58 frame info chain, +0x70 ...); gen_batch restores it after a recovered throw"),
    dict(name="game_alloc", addr=0x142BCC880, features=BATCH, note="the game's allocator: (size) -> block"),
    dict(name="game_free", addr=0x142BCC760, features=BATCH, note="the game's free: (block)"),
    dict(name="flat_map_anchor", addr=0x140B5D220, features=BATCH,
         note="calls flat_map_set once; anchor of it (the set function itself has no unique prefix)"),
    dict(name="flat_map_set", addr=0x1423CA520, kind="ref", anchor="flat_map_anchor", index=0,
         features=BATCH, expect_fn=True,
         note="sorted (i32 key, i32 value) vector set (this, key, value); the world stats at world +0x128"),
    dict(name="world_areas_table", addr=0x140225df0, features=BATCH,
         note="(out) -> reference-counted Data/Balance/WorldAreas.dat table object"),
    dict(name="resource_wait_loaded", addr=0x1421E6EF0, features=BATCH,
         note="blocks until a resource (state +0x40 == 2) is loaded"),
    dict(name="room_check_user", addr=0x141F0D4F0, features=BATCH,
         note="Incursion temple room constructor: reads the WorldAreas table object from world +0xa0; anchor of world.area_table"),
    dict(name="table_rows_user", addr=0x141D0F750, features=BATCH,
         note="reads table +0x28 -> (begin, end) of the rows; anchor of table.rows"),
    # ---- generator trace (research, off by default) ----
    dict(name="terrain_seed_rng", addr=0x141FAA7C0, features=TRACE),
    dict(name="mt_next", addr=0x140A65F30, features=TRACE, pdata=False),
    dict(name="uniform_int", addr=0x141F1BA50, features=TRACE),
    dict(name="rng_below", addr=0x141FAAA10, features=TRACE),
    dict(name="rng_range", addr=0x141FAAAE0, features=TRACE),
    dict(name="room_pass", addr=0x141F9CE60, features=TRACE),
    dict(name="room_candidates", addr=0x141F9D4E5, kind="site", anchor="room_pass", features=TRACE,
         note="right after the tile-set lookup: rax = the candidate list"),
    dict(name="place_tile", addr=0x141FACA80, features=TRACE),
    dict(name="derepeat", addr=0x141FEBF70, features=TRACE),
    dict(name="node_place", addr=0x1420D77C0, features=TRACE),
    dict(name="node_candidates", addr=0x1420D66F0, features=TRACE),
    dict(name="route_edge", addr=0x1420DC480, features=TRACE),
    dict(name="room_fits", addr=0x141FAB9A0, features=TRACE,
         note="TileKey fits the terrain at a position: (lattice ctx, &pos, key, wild) -> 0 or a failure code; traced for the overlay candidate scan"),
    dict(name="split_virtual", addr=0x1420CB420, features=TRACE),
    dict(name="smooth_edges", addr=0x1420CC670, features=TRACE),
    dict(name="arc_start", addr=0x1420E0B90, features=TRACE),
    dict(name="arc_end", addr=0x1420E1490, features=TRACE),
    dict(name="round_corners", addr=0x1420C1F80, features=TRACE),
    dict(name="edge_tiles", addr=0x1420C5970, features=TRACE),
    dict(name="lattice_borders", addr=0x1420C84F0, features=TRACE),
    dict(name="lattice_flood", addr=0x1420CFA80, features=TRACE),
    dict(name="lattice_heights", addr=0x1420C8840, features=TRACE),
    dict(name="lattice_92ce0", addr=0x141FA1480, features=TRACE),
    dict(name="lattice_bdae0", addr=0x1420CCB00, features=TRACE),
    dict(name="lattice_be360", addr=0x1420CD380, features=TRACE),
    dict(name="lattice_fill", addr=0x141FA1800, features=TRACE),
    dict(name="lattice_round", addr=0x141FE5970, features=TRACE),
    dict(name="lattice_enclosed", addr=0x141FEF2F0, features=TRACE),
    dict(name="round_corner", addr=0x141FE599B, kind="site", anchor="lattice_round", features=TRACE,
         note="after the corner-set call of one levelling step: rsi = &(x, y), [rsp+0x30..0x38] = vector of the tile's set corner heights"),
    dict(name="tile_lookup", addr=0x141D17070, features=TRACE),
    dict(name="path_crossings", addr=0x1420C64B0, features=TRACE),
    dict(name="tdiff_graph", addr=0x141FFEDA0, features=TRACE),
    dict(name="tdiff_post", addr=0x1420061C0, features=TRACE),
    dict(name="tdiff_outer_fill", addr=0x141FE47A0, features=TRACE),
    dict(name="tdiff_outer_buffer", addr=0x141FE6B10, features=TRACE),
    dict(name="tdiff_grid_fd0", addr=0x141FEF780, features=TRACE),
    dict(name="tdiff_grid_ea0", addr=0x141FEF650, features=TRACE),
    dict(name="tdiff_overlay_scan", addr=0x141FB0B80, features=TRACE),
    dict(name="tdiff_placeholder", addr=0x1420B5160, features=TRACE),
    dict(name="tdiff_preunique", addr=0x1420AB170, features=TRACE),
    dict(name="tdiff_topology", addr=0x142007A30, features=TRACE),
    dict(name="strip_grounds", addr=0x141FEA424, kind="site", anchor="tdiff_outer_buffer", features=TRACE,
         note="outer buffer row strips (0x141fe6b10), the fill branch: [rsp+0x40] = row y, [rsp+0x44] = walk limit, [rbp+0x10] / rbx = the two grounds compared"),
    dict(name="placeholder_sizes", addr=0x1420B521D, kind="site", anchor="tdiff_placeholder", features=TRACE,
         note="after the door type's size list lookup: rdi = the list (begin, end; 12-byte entries w, h, weight; total weight at +0x18)"),
    dict(name="phase_prepare", addr=0x14200D0A0, features=TRACE),
    dict(name="phase_cad0", addr=0x14200B380, features=TRACE),
    dict(name="phase_c360", addr=0x14200AC10, features=TRACE),
    dict(name="phase_dab0", addr=0x14200C360, features=TRACE),
    dict(name="phase_de60", addr=0x14200C710, features=TRACE),
    dict(name="phase_b930", addr=0x14200A1E0, features=TRACE),
    dict(name="phase_terrain_e5f0", addr=0x141D1B1A0, features=TRACE),
    dict(name="phase_vt50_ab20", addr=0x1420093D0, features=TRACE),
    dict(name="phase_doodads", addr=0x142003D00, features=TRACE + EXPORT),
    dict(name="phase_vt28_3eb0", addr=0x142002660, features=TRACE),
    dict(name="phase_vt58_4730", addr=0x142002EE0, features=TRACE),
    dict(name="phase_doodads_post", addr=0x142003300, features=TRACE),
    dict(name="phase_heights_post", addr=0x14200C950, features=TRACE),
    dict(name="phase_tile_hash", addr=0x141D20D80, features=TRACE + EXPORT),
    # ---- test input ----
    dict(name="aim_report_tick", addr=0x14016FD30, features=["auto_keys_focus"],
         note="AimReport_Tick: compares GetForegroundWindow with the game window pointer"),
    dict(name="game_window_ptr", addr=0x1445F0768, kind="ref", anchor="aim_report_tick",
         features=["auto_keys_focus"], note="pointer to the game window handle"),
]

ENT = ["dump_object_types", "area_export", "position_sync"]
PS = ["position_sync"]
INSPECT = ["inspect"]
PKT = ["packets"]

FIELDS = [
    # ---- entity: the component loop of Entity_ReadInitialState ----
    dict(anchor="read_initial_state", features=ENT, items=[
        dict(name="entity.type", disp=0x8, at=0x141E7F230),
        dict(name="type.lookup", disp=0x28, at=0x141E7F242),
        dict(name="lookup.serialized_count", disp=0x78, at=0x141E7F248),
        dict(name="entity.components_begin", disp=0x10, at=0x141E7F251),
        dict(name="component.owner", disp=0x8, at=0x141E7F259),
        dict(name="component.vt_reader", disp=0x98, at=0x141E7F265),
        dict(name="entity.tick_base", disp=0x58, at=0x141E7F26F,
             note="the frame-tick hook receives entity + this"),
    ]),
    dict(anchor="entity_update", features=ENT, items=[
        dict(name="entity.components_end", disp=0x18, at=0x141E7F10F)]),
    dict(anchor="entity_destroy", features=ENT, items=[
        dict(name="entity.world", disp=0x78, at=0x141E7F703)]),
    dict(anchor="entity_destroy", features=ENT, items=[
        dict(name="entity.id", disp=0x88, at=0x141E7F749)]),
    dict(anchor="entity_get_render", features=INSPECT, items=[
        dict(name="lookup.names_begin", disp=0x28, at=0x1401558E9),
        dict(name="lookup.names_end", disp=0x30, at=0x1401558F5),
    ]),
    # ---- Positioned ----
    dict(anchor="positioned_reader", features=ENT, items=[
        dict(name="positioned.grid_x", disp=0x444, at=0x141DE5C52),
        dict(name="positioned.grid_y", disp=0x448, at=0x141DE5C82),
        dict(name="positioned.facing", disp=0x44C, at=0x141DE5CA9),
    ]),
    dict(anchor="positioned_reader", features=ENT, items=[
        dict(name="positioned.world_x", disp=0x490, at=0x141DE5F49),
        dict(name="positioned.world_y", disp=0x494, at=0x141DE5F72),
    ]),
    dict(anchor="set_orientation", features=ENT, items=[
        dict(name="positioned.facing_lock", disp=0x1E5, at=0x141DE99DF,
             note="byte; bit 1 = orientation locked"),
        dict(name="positioned.facing_set", disp=0x44C, at=0x141DE99F9, agrees_with="positioned.facing"),
    ]),
    dict(anchor="positioned_reader", features=ENT, items=[
        dict(name="world.vt_terrain", disp=0x1A8, at=0x141DE5CFC,
             note="world vtable slot: returns the terrain object")]),
    # ---- Actor ----
    dict(anchor="actor_sim_handler", features=PS + INSPECT, items=[
        dict(name="actor.action0", disp=0x238, at=0x142159824),
        dict(name="actor.action1", disp=0x240, at=0x14215983D),
    ]),
    dict(anchor="actor_sim_handler", features=PS + INSPECT, items=[
        dict(name="action.type", disp=0x120, at=0x14215914D, note="u16 at an action object")]),
    dict(anchor="actor_sim_handler", features=INSPECT, items=[
        dict(name="actor.dir_x", disp=0x400, at=0x142158E5F),
        dict(name="actor.dir_y", disp=0x404, at=0x142158E6A),
    ]),
    dict(anchor="roll_end", features=PS + INSPECT, items=[
        dict(name="actor.sprint_flags", disp=0x2A2, at=0x141B85113, note="byte; bit 5 = sprint key held")]),
    # ---- world ----
    dict(anchor="frame_drain", features=["dump_object_types"], items=[
        dict(name="world.frame_mode", disp=0x669, at=0x14213F91C)]),
    dict(anchor="frame_drain", features=INSPECT, items=[
        dict(name="world.pause", disp=0x890, at=0x14213F9A9, note="u16 flags: +0x890 pause, +0x891 next flag")]),
    dict(anchor="frame_drain", features=INSPECT, items=[
        dict(name="world.frame_queue", disp=0x6D0, at=0x14213FAC1)]),
    dict(anchor="game_update", features=INSPECT, items=[
        dict(name="game.update_accumulator", disp=0x17F4, at=0x14168715D)]),
    dict(anchor="load_area_client", features=["area_export", "dump_object_types", "gen_batch"], items=[
        dict(name="world.area", disp=0xA0, at=0x14168395F),
        dict(name="area.kind", disp=0x1B4, at=0x14168396B),
    ]),
    dict(anchor="load_area_client", features=["area_export", "dump_object_types", "gen_batch"], items=[
        dict(name="world.tile_hash", disp=0x11C, at=0x141683B9C)]),
    dict(anchor="load_area_client", features=["area_export", "dump_object_types", "gen_batch"], items=[
        dict(name="world.doodad_hash", disp=0x120, at=0x141683C3E)]),
    # gen_batch: what a synthetic world needs (docs/re/terrain/batch.md)
    dict(anchor="load_area_client", features=BATCH, items=[
        dict(name="world.stats", disp=0x130, at=0x141683E2B,
             note="the world's stat map (sorted i32 key/value pairs at +8..+0x10; map_force_* live here)")]),
    dict(anchor="load_area_headless", features=BATCH, items=[
        dict(name="world.gen_flag", disp=0x66B, at=0x14213E761, note="u8, cleared before a headless generation"),
        dict(name="world.gen_state", disp=0x4B8, at=0x14213E768, note="the generation state (u32 +0, seed u32 +4)"),
        dict(name="world.gen_seed", disp=0x4BC, at=0x14213E76E),
    ]),
    dict(anchor="terrain_topology_pick", features=BATCH, items=[
        dict(name="world.league_mode", disp=0xC0, at=0x142007CCA, note="u32 mode column the topologies are filtered by"),
        dict(name="area.topology_count", disp=0x60, at=0x142007B69),
        dict(name="area.topology_list", disp=0x68, at=0x142007B80, note="16-byte entries"),
    ]),
    dict(anchor="terrain_gen_construct", features=BATCH, items=[
        dict(name="generator.validate", disp=0xE, at=0x141FFE1FC,
             note="u8, 1 after construction: runs the tile map validation pass (0x14200c360, throws TerrainGenerationException); the client clears it")]),
    dict(anchor="world_replace", features=BATCH, items=[
        dict(name="world.vt_delete", disp=0x20, at=0x141014098, note="vtable slot: deleting destructor (this, 1)")]),
    dict(anchor="resource_wait_loaded", features=BATCH, items=[
        dict(name="resource.state", disp=0x40, at=0x1421E6F02, note="2 = loaded")]),
    dict(anchor="table_rows_user", features=BATCH, items=[
        dict(name="table.rows", disp=0x28, at=0x141D0F7F1, note="pointer to (begin, end) of the table rows"),
        dict(name="resource.refs", disp=0x3C, at=0x141D0F794, note="i32 reference count (lock inc / lock dec)")]),
    dict(anchor="room_check_user", features=BATCH, items=[
        dict(name="world.area_table", disp=0xA8, at=0x141F0D5F5,
             note="reference-counted WorldAreas table object (the world's area row belongs to it); the world's destructor releases it")]),
    # ---- generator and terrain ----
    dict(anchor="terrain_driver", features=EXPORT, items=[
        dict(name="generator.world", disp=0x38, at=0x14200D762),
        dict(name="generator.terrain", disp=0x28, at=0x14200D77B),
    ]),
    dict(anchor="terrain_driver", features=EXPORT, items=[
        dict(name="generator.state", disp=0x30, at=0x14200D7C1)]),
    dict(anchor="terrain_driver", features=EXPORT, items=[
        dict(name="state.seed", disp=0x4, at=0x14200D49B, note="u32 at the generation state")]),
    dict(anchor="phase_tile_hash", features=EXPORT + DUMP, items=[
        dict(name="terrain.width", disp=0x18, at=0x141D20DAC),
        dict(name="terrain.height", disp=0x20, at=0x141D20DAF),
    ]),
    dict(anchor="phase_tile_hash", features=EXPORT + DUMP, items=[
        dict(name="terrain.tiles", disp=0x28, at=0x141D20DFE)]),
    # ---- network streams ----
    dict(anchor="stream_read", features=PKT, items=[
        dict(name="stream.error", disp=0x252, at=0x1421A7D1D),
        dict(name="stream.msg_read", disp=0x278, at=0x1421A7D2A),
    ]),
    dict(anchor="stream_read", features=PKT, items=[
        dict(name="stream.recv_base", disp=0x298, at=0x1421A7D73),
        dict(name="stream.recv_end", disp=0x2A0, at=0x1421A7D7A),
        dict(name="stream.recv_head", disp=0x268, at=0x1421A7D84),
    ]),
    dict(anchor="stream_write", features=PKT, items=[
        dict(name="stream.send_len", disp=0x258, at=0x1421a7ea5)]),
    dict(anchor="stream_write", features=PKT, items=[
        dict(name="stream.send_buf", disp=0x280, at=0x1421A7E44)]),
    dict(anchor="stream_flush", features=PKT, items=[
        dict(name="stream.send_sent", disp=0x260, at=0x1421a8007)]),
    dict(anchor="instance_session_handler", features=["side_channel"], items=[
        dict(name="session.key_material", disp=0x58, at=0x1421312FD, note="64-byte key material inside the stored InstanceDetails")]),
    dict(anchor="session_send", features=PKT, items=[
        dict(name="session.stream", disp=0x20F8, at=0x14212EB3A)]),
    # ---- crypto ----
    dict(anchor="crypto_dh_agree", features=["crypto_bypass"], items=[
        dict(name="crypto.key_buffer", disp=0x60, at=0x1421AEF70,
             note="pointer to the 64-byte key buffer inside the crypto session")]),
]

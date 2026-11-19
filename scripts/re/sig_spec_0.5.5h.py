"""Spec for scripts/re/sig_gen.py: the 0.5.5h entries of modules/client-hook/signatures/0.5.5h.toml.

Addresses are Ghidra addresses (image base 0x140000000) of client 0.5.5h (revision 329201).
Made from the previous build's spec with scripts/re/addr_map.py (every address moved by its function's delta). `features` names the
DLL features that are off when the entry does not resolve (see poe-hook-core `start_features`).
For another build, run the generator on that exe with the (moved) addresses.
"""
SPEC_NAME = "sig_spec_0.5.5h.py"

BUILD = dict(
    version="0.5.5h",
    build_revision="329201",
    revision_pattern="2d 00 63 00 72 00 61 00 73 00 68 00 00 00 <rev:bytes6> 00",
    pe_timestamp=0x6AFB7637,
    image_size=0x04CBB000,
    exe_sha256="dfc10ef7e4e4411df7418779c5467d804def225e80814be6ee88f96cbd10dcca",
)

DUMP = ["dump_object_types"]
# gen_batch (in-client batch terrain generation) needs everything the area export needs, plus its own.
EXPORT = ["area_export", "gen_batch"]
BATCH = ["gen_batch"]
TRACE = ["generator_trace"]

SIGS = [
    # ---- loader: standalone login ----
    dict(name="client_platform_detect", addr=0x1421a7460, features=["login_patch"],
         expect="40 55 53", patch="31 c0 c3",
         note="ClientPlatform_Detect; patch = xor eax,eax; ret (platform 0)"),
    dict(name="standalone_patcher_run", addr=0x140118C10, features=["patcher_skip"],
         expect="48 8b c4", patch="b0 01 c3",
         note="StandalonePatcher_Run; patch = mov al,1; ret (skip the patcher)"),
    dict(name="client_platform_get", addr=0x14010C450, features=["login_cache"],
         note="cached platform getter; anchor of the two cache globals"),
    dict(name="platform_cache_guard", addr=0x144730664, kind="ref", anchor="client_platform_get",
         features=["login_cache"], note="thread-safe-static guard of the cached platform"),
    dict(name="platform_cache_value", addr=0x144730668, kind="ref", anchor="client_platform_get",
         features=["login_cache"], note="the cached platform value (i32)"),
    # ---- crypto bypass and side channel ----
    dict(name="verify_and_derive", addr=0x1421AF5B0, features=["crypto_bypass"],
         note="signature check + key derivation (hooked, replaced for trusted servers)"),
    dict(name="crypto_dh_agree", addr=0x1421AF3E0, features=["crypto_bypass"],
         note="DH agree + SHA-512 into the session key buffer; anchor of the key buffer offset"),
    dict(name="instance_session_handler", addr=0x1421317e0, features=["side_channel"],
         note="game-session packet handler; anchor of instance_ciphers and session.key_material"),
    dict(name="instance_ciphers", addr=0x1421318b7, kind="site", anchor="instance_session_handler",
         features=["side_channel"],
         note="EnableEncryption case, before the packet-cipher allocation (the builder is inlined since 0.5.5f): rbx = instance details"),
    # ---- packet capture ----
    dict(name="read_message", addr=0x1421D5FE0, features=["packets"]),
    dict(name="session_send", addr=0x14212F0F0, features=["packets"]),
    dict(name="stream_flush", addr=0x1421a8560, features=["packets"]),
    dict(name="packet_flush_plaintext", addr=0x1421a85d7, kind="site", anchor="stream_flush",
         features=["packets"], note="after the lock, before the cipher; rbx = stream"),
    dict(name="login_session_loop", addr=0x1420F61E0, features=["packets"],
         note="receive loop of the login session (caller of read_message); its .pdata range gives the channel"),
    dict(name="instance_session_loop", addr=0x1421303e0, features=["packets"],
         note="receive loop of the instance session; its .pdata range gives the channel"),
    dict(name="stream_read", addr=0x1421A82D0, features=["packets"]),
    dict(name="stream_write", addr=0x1421A8400, features=["packets"]),
    # ---- entity and world research (dump_object_types) ----
    dict(name="sim_frame_processor", addr=0x142143b00, features=DUMP,
         note="frame processor; unique caller, anchor of object_type_lookup"),
    dict(name="object_type_lookup", addr=0x14169c550, kind="ref", anchor="sim_frame_processor",
         features=DUMP, expect_fn=True, note="a clone-like function: found by its unique caller"),
    dict(name="read_initial_state", addr=0x141E7F760, features=DUMP),
    dict(name="path_plan", addr=0x141EDEB10, features=["path_log"],
         note="grid pathfinder (JPS-style search, A* fallback): (goal*, entity, params*, ..., out path*, out count*, ...); hooked by path_log to log the player's plans"),
    dict(name="entity_destroy", addr=0x141E7FC60, features=DUMP),
    dict(name="ui_set_visible", addr=0x1427C1970, features=["ui_panels"],
         note="UI element SetVisible (element, bool): flags +0x168 bit 11, parent +0xb8, name wstring +0x98; hooked by the state export"),
    dict(name="actor_sim_handler", addr=0x142159130, features=["position_sync", "inspect", "snap_log"],
         note="Actor component simulation handler (0x64 WASD, 0x1c8 start action, ...)"),
    dict(name="install_queued_move", addr=0x141E50030, features=["snap_log"],
         note="Actor_InstallQueuedMove (actor, slot*): snaps to the StartAction start actor+0x3bc iff it differs from the grid (lockstep); hooked by snap_log"),
    dict(name="set_location_forced_nc", addr=0x141DE8E70, features=["snap_log"],
         note="Positioned_SetLocationForcedNoCallbacks (positioned, cell*, world*): the snap setter; hooked by snap_log"),
    # ---- unported movement code (unported_log, T1 step 3; docs/re/movement-coverage.md) ----
    dict(name="astar_general", addr=0x141EDC7D0, features=["unported_log"],
         note="general A* (goal*, entity, params*, ...): the search 0x141edeb10 falls back to it for a start inside an entity; hooked by unported_log"),
    dict(name="push_test", addr=0x141DEE9E0, features=["unported_log"],
         note="push test (mover Positioned, pushables list*, step dir): hooked by unported_log"),
    dict(name="can_push", addr=0x141DF03C0, features=["unported_log"],
         note="can mover push other (mover Positioned, other Positioned): hooked by unported_log"),
    dict(name="check_step", addr=0x141DEA740, features=["unported_log"],
         note="Positioned_CheckStep (P, out, cell, z, probe); anchor of step_entity_hit"),
    dict(name="step_entity_hit", addr=0x141DEADC1, kind="site", anchor="check_step", features=["unported_log"],
         note="CheckStep: the entity collision 0x141dfdb80 hit (out = 3): rdi = P, rbp+0xe60 = hit Positioned; hooked by unported_log"),
    dict(name="move_event_end", addr=0x141F70E30, features=["unported_log"],
         note="MoveEvent end time (event): clipped when event+0xa8 and the clip cell +0xa0 differs from +0x98; Positioned [[event+0xb0]+0x98]; hooked by unported_log"),
    dict(name="roll_end", addr=0x141B85695, features=["position_sync"],
         note="end of a dodge roll: reads the sprint-key bit"),
    dict(name="noop_reader", addr=0x14010C9B0, features=["entity_trace"], pdata=False,
         note="shared `ret 0` stub used as the reader of components without initial state"),
    dict(name="entity_update", addr=0x141E7F6D0, features=DUMP),
    dict(name="frame_drain", addr=0x14213fec0, features=DUMP),
    dict(name="entity_tick", addr=0x141E8BF30, features=DUMP),
    dict(name="game_update", addr=0x141687730, features=DUMP),
    dict(name="set_orientation", addr=0x141DE9FA0, features=DUMP),
    dict(name="load_area_client", addr=0x141683f50, features=DUMP),
    dict(name="load_area_headless", addr=0x14213ED00, features=DUMP + BATCH,
         note="HeadlessWorld_LoadArea (base world vfunc +0x1e0): the sequence gen_batch repeats; anchor of the world generation fields"),
    dict(name="positioned_reader", addr=0x141DE6120, features=DUMP + EXPORT),
    dict(name="positioned_debug_info", addr=0x141dec130, features=DUMP,
         note="Positioned debug printer (=== Positioned Info ===, never called); anchor of the movement destination and speed fields"),
    dict(name="terrain_construct", addr=0x1415AC750, features=DUMP + EXPORT,
         note="sets the terrain vtable; anchor of terrain_vtable"),
    dict(name="terrain_vtable", addr=0x14339B108, kind="ref", anchor="terrain_construct",
         features=DUMP + EXPORT, note="identifies the area terrain object inside the world"),
    # ---- entity probe (calls game functions 5 s after the player spawned) ----
    dict(name="probe_anchor", addr=0x140238ba0, features=["entity_probe"],
         note="calls the render getter, the visibility refresh and the terrain sampler"),
    dict(name="entity_get_render", addr=0x1401558B0, kind="ref", anchor="probe_anchor", index=0,
         features=["entity_probe"], expect_fn=True, note="entity -> Render component by name"),
    dict(name="render_refresh", addr=0x1416B2770, kind="ref", anchor="probe_anchor",
         features=["entity_probe"], expect_fn=True),
    dict(name="terrain_sample", addr=0x141D1A5A0, kind="ref", anchor="probe_anchor",
         features=["entity_probe"], expect_fn=True, note="terrain height at (x, y)"),
    dict(name="positioned_height", addr=0x141DF2D40, features=["entity_probe"]),
    # ---- area export ----
    dict(name="terrain_driver", addr=0x14200D7C0, features=EXPORT),
    dict(name="terrain_add_object", addr=0x1420064F0, features=EXPORT),
    dict(name="tile_doodads", addr=0x142002090, features=EXPORT + TRACE),
    dict(name="doodad_hash_site", addr=0x1420023c3, kind="site", anchor="tile_doodads",
         features=EXPORT, note="right after a doodad's path hash: eax = hash, r15 = tile entry"),
    # ---- gen_batch: a synthetic world and generator (docs/re/terrain/batch.md) ----
    dict(name="world_construct_client", addr=0x141685FD0, features=BATCH,
         note="ClientWorld constructor (this, frame mode u8, flag u8); the batch makes its own worlds"),
    dict(name="terrain_gen_construct", addr=0x141FFE7A0, features=BATCH,
         note="TerrainGen_Construct(generator, world): base generator vtable 0x143504548"),
    dict(name="terrain_gen_destroy", addr=0x141FFEBC0, features=BATCH, note="generator destructor"),
    dict(name="terrain_topology_pick", addr=0x142008000, features=BATCH,
         note="reads map_force_topology (0xb92) / map_force_orientation (0xb93) from the world stats; anchor of fields"),
    dict(name="world_replace", addr=0x141013eb0, features=BATCH,
         note="creates the in-game world and destroys the old one through vfunc +0x20 (deleting destructor)"),
    dict(name="vcrt_getptd", addr=0x142C26E08, features=BATCH,
         note="__vcrt_getptd(): the thread's C++ exception state (+0x20/+0x28 exception and context records, +0x58 frame info chain, +0x70 ...); gen_batch restores it after a recovered throw"),
    dict(name="game_alloc", addr=0x142BCCF40, features=BATCH, note="the game's allocator: (size) -> block"),
    dict(name="game_free", addr=0x142BCCE20, features=BATCH, note="the game's free: (block)"),
    dict(name="flat_map_anchor", addr=0x140B5D480, features=BATCH,
         note="calls flat_map_set once; anchor of it (the set function itself has no unique prefix)"),
    dict(name="flat_map_set", addr=0x1423CAAF0, kind="ref", anchor="flat_map_anchor", index=0,
         features=BATCH, expect_fn=True,
         note="sorted (i32 key, i32 value) vector set (this, key, value); the world stats at world +0x128"),
    dict(name="world_areas_table", addr=0x140225df0, features=BATCH,
         note="(out) -> reference-counted Data/Balance/WorldAreas.dat table object"),
    dict(name="resource_wait_loaded", addr=0x1421E74C0, features=BATCH,
         note="blocks until a resource (state +0x40 == 2) is loaded"),
    dict(name="room_check_user", addr=0x141F0DAC0, features=BATCH,
         note="Incursion temple room constructor: reads the WorldAreas table object from world +0xa0; anchor of world.area_table"),
    dict(name="table_rows_user", addr=0x141D0FD20, features=BATCH,
         note="reads table +0x28 -> (begin, end) of the rows; anchor of table.rows"),
    # ---- generator trace (research, off by default) ----
    dict(name="terrain_seed_rng", addr=0x141FAAD90, features=TRACE),
    dict(name="mt_next", addr=0x140A65F30, features=TRACE, pdata=False),
    dict(name="uniform_int", addr=0x141F1C020, features=TRACE),
    dict(name="rng_below", addr=0x141FAAFE0, features=TRACE),
    dict(name="rng_range", addr=0x141FAB0B0, features=TRACE),
    dict(name="room_pass", addr=0x141F9D430, features=TRACE),
    dict(name="room_candidates", addr=0x141F9DAB5, kind="site", anchor="room_pass", features=TRACE,
         note="right after the tile-set lookup: rax = the candidate list"),
    dict(name="place_tile", addr=0x141FAD050, features=TRACE),
    dict(name="derepeat", addr=0x141FEC540, features=TRACE),
    dict(name="node_place", addr=0x1420D7D90, features=TRACE),
    dict(name="node_candidates", addr=0x1420D6CC0, features=TRACE),
    dict(name="route_edge", addr=0x1420DCA50, features=TRACE),
    dict(name="room_fits", addr=0x141FABF70, features=TRACE,
         note="TileKey fits the terrain at a position: (lattice ctx, &pos, key, wild) -> 0 or a failure code; traced for the overlay candidate scan"),
    dict(name="split_virtual", addr=0x1420CB9F0, features=TRACE),
    dict(name="smooth_edges", addr=0x1420CCC40, features=TRACE),
    dict(name="arc_start", addr=0x1420E1160, features=TRACE),
    dict(name="arc_end", addr=0x1420E1A60, features=TRACE),
    dict(name="round_corners", addr=0x1420C2550, features=TRACE),
    dict(name="edge_tiles", addr=0x1420C5F40, features=TRACE),
    dict(name="lattice_borders", addr=0x1420C8AC0, features=TRACE),
    dict(name="lattice_flood", addr=0x1420D0050, features=TRACE),
    dict(name="lattice_heights", addr=0x1420C8E10, features=TRACE),
    dict(name="lattice_92ce0", addr=0x141FA1A50, features=TRACE),
    dict(name="lattice_bdae0", addr=0x1420CD0D0, features=TRACE),
    dict(name="lattice_be360", addr=0x1420CD950, features=TRACE),
    dict(name="lattice_fill", addr=0x141FA1DD0, features=TRACE),
    dict(name="lattice_round", addr=0x141FE5F40, features=TRACE),
    dict(name="lattice_enclosed", addr=0x141FEF8C0, features=TRACE),
    dict(name="round_corner", addr=0x141FE5F6B, kind="site", anchor="lattice_round", features=TRACE,
         note="after the corner-set call of one levelling step: rsi = &(x, y), [rsp+0x30..0x38] = vector of the tile's set corner heights"),
    dict(name="tile_lookup", addr=0x141D17640, features=TRACE),
    dict(name="path_crossings", addr=0x1420C6A80, features=TRACE),
    dict(name="tdiff_graph", addr=0x141FFF370, features=TRACE),
    dict(name="tdiff_post", addr=0x142006790, features=TRACE),
    dict(name="tdiff_outer_fill", addr=0x141FE4D70, features=TRACE),
    dict(name="tdiff_outer_buffer", addr=0x141FE70E0, features=TRACE),
    dict(name="tdiff_grid_fd0", addr=0x141FEFD50, features=TRACE),
    dict(name="tdiff_grid_ea0", addr=0x141FEFC20, features=TRACE),
    dict(name="tdiff_overlay_scan", addr=0x141FB1150, features=TRACE),
    dict(name="tdiff_placeholder", addr=0x1420B5730, features=TRACE),
    dict(name="tdiff_preunique", addr=0x1420AB740, features=TRACE),
    dict(name="tdiff_topology", addr=0x142008000, features=TRACE),
    dict(name="strip_grounds", addr=0x141FEA9F4, kind="site", anchor="tdiff_outer_buffer", features=TRACE,
         note="outer buffer row strips (0x141fe70e0), the fill branch: [rsp+0x40] = row y, [rsp+0x44] = walk limit, [rbp+0x10] / rbx = the two grounds compared"),
    dict(name="placeholder_sizes", addr=0x1420B57ED, kind="site", anchor="tdiff_placeholder", features=TRACE,
         note="after the door type's size list lookup: rdi = the list (begin, end; 12-byte entries w, h, weight; total weight at +0x18)"),
    dict(name="phase_prepare", addr=0x14200D670, features=TRACE),
    dict(name="phase_cad0", addr=0x14200B950, features=TRACE),
    dict(name="phase_c360", addr=0x14200B1E0, features=TRACE),
    dict(name="phase_dab0", addr=0x14200C930, features=TRACE),
    dict(name="phase_de60", addr=0x14200CCE0, features=TRACE),
    dict(name="phase_b930", addr=0x14200A7B0, features=TRACE),
    dict(name="phase_terrain_e5f0", addr=0x141D1B770, features=TRACE),
    dict(name="phase_vt50_ab20", addr=0x1420099a0, features=TRACE),
    dict(name="phase_doodads", addr=0x1420042d0, features=TRACE + EXPORT),
    dict(name="phase_vt28_3eb0", addr=0x142002c30, features=TRACE),
    dict(name="phase_vt58_4730", addr=0x1420034b0, features=TRACE),
    dict(name="phase_doodads_post", addr=0x1420038d0, features=TRACE),
    dict(name="phase_heights_post", addr=0x14200CF20, features=TRACE),
    dict(name="phase_tile_hash", addr=0x141D21350, features=TRACE + EXPORT),
    # ---- test input ----
    dict(name="aim_report_tick", addr=0x14016FD30, features=["auto_keys_focus"],
         note="AimReport_Tick: compares GetForegroundWindow with the game window pointer"),
    dict(name="game_window_ptr", addr=0x1445F17A8, kind="ref", anchor="aim_report_tick",
         features=["auto_keys_focus"], note="pointer to the game window handle"),
]

ENT = ["dump_object_types", "area_export", "position_sync"]
PS = ["position_sync"]
INSPECT = ["inspect"]
PKT = ["packets"]

FIELDS = [
    # ---- entity: the component loop of Entity_ReadInitialState ----
    dict(anchor="read_initial_state", features=ENT, items=[
        dict(name="entity.type", disp=0x8, at=0x141E7F800),
        dict(name="type.lookup", disp=0x28, at=0x141E7F812),
        dict(name="lookup.serialized_count", disp=0x78, at=0x141E7F818),
        dict(name="entity.components_begin", disp=0x10, at=0x141E7F821),
        dict(name="component.owner", disp=0x8, at=0x141E7F829),
        dict(name="component.vt_reader", disp=0x98, at=0x141E7F835),
        dict(name="entity.tick_base", disp=0x58, at=0x141E7F83F,
             note="the frame-tick hook receives entity + this"),
    ]),
    dict(anchor="entity_update", features=ENT, items=[
        dict(name="entity.components_end", disp=0x18, at=0x141E7F6DF)]),
    dict(anchor="entity_destroy", features=ENT, items=[
        dict(name="entity.world", disp=0x78, at=0x141E7FCD3)]),
    dict(anchor="entity_destroy", features=ENT, items=[
        dict(name="entity.id", disp=0x88, at=0x141E7FD19)]),
    dict(anchor="entity_get_render", features=INSPECT, items=[
        dict(name="lookup.names_begin", disp=0x28, at=0x1401558E9),
        dict(name="lookup.names_end", disp=0x30, at=0x1401558F5),
    ]),
    # ---- Positioned ----
    dict(anchor="positioned_reader", features=ENT, items=[
        dict(name="positioned.grid_x", disp=0x444, at=0x141DE6222),
        dict(name="positioned.grid_y", disp=0x448, at=0x141DE6252),
        dict(name="positioned.facing", disp=0x44C, at=0x141DE6279),
    ]),
    dict(anchor="positioned_reader", features=ENT, items=[
        dict(name="positioned.world_x", disp=0x490, at=0x141DE6519),
        dict(name="positioned.world_y", disp=0x494, at=0x141DE6542),
    ]),
    dict(anchor="set_orientation", features=ENT, items=[
        dict(name="positioned.facing_lock", disp=0x1E5, at=0x141DE9FAF,
             note="byte; bit 1 = orientation locked"),
        dict(name="positioned.facing_set", disp=0x44C, at=0x141DE9FC9, agrees_with="positioned.facing"),
    ]),
    dict(anchor="positioned_reader", features=ENT, items=[
        dict(name="world.vt_terrain", disp=0x1A8, at=0x141DE62CC,
             note="world vtable slot: returns the terrain object")]),
    dict(anchor="positioned_debug_info", features=DUMP, items=[
        dict(name="positioned.dest_y", disp=0x240, at=0x141dec8be,
             note="i32; the destination is (+0x23c, or +0x244 when dest_alt is set; this), swapped when dest_swap is set"),
        dict(name="positioned.dest_alt", disp=0x22E, at=0x141dec8cf, note="byte"),
        dict(name="positioned.dest_swap", disp=0x22D, at=0x141dec8de, note="byte"),
    ]),
    dict(anchor="positioned_debug_info", features=DUMP, items=[
        dict(name="positioned.speed_num", disp=0x274, at=0x141dec9a7, note="f32; Movement Speed = speed_num / speed_den"),
        dict(name="positioned.speed_den", disp=0x278, at=0x141dec9b0, note="f32"),
    ]),
    # ---- Actor ----
    dict(anchor="actor_sim_handler", features=PS + INSPECT, items=[
        dict(name="actor.action0", disp=0x238, at=0x142159df4),
        dict(name="actor.action1", disp=0x240, at=0x142159E0D),
    ]),
    dict(anchor="actor_sim_handler", features=PS + INSPECT, items=[
        dict(name="action.type", disp=0x120, at=0x14215971D, note="u16 at an action object")]),
    dict(anchor="actor_sim_handler", features=INSPECT, items=[
        dict(name="actor.dir_x", disp=0x400, at=0x14215942F),
        dict(name="actor.dir_y", disp=0x404, at=0x14215943A),
    ]),
    dict(anchor="roll_end", features=PS + INSPECT, items=[
        dict(name="actor.sprint_flags", disp=0x2A2, at=0x141B85773, note="byte; bit 5 = sprint key held")]),
    # ---- world ----
    dict(anchor="frame_drain", features=["dump_object_types"], items=[
        dict(name="world.frame_mode", disp=0x669, at=0x14213FEEC)]),
    dict(anchor="frame_drain", features=INSPECT, items=[
        dict(name="world.pause", disp=0x890, at=0x14213FF79, note="u16 flags: +0x890 pause, +0x891 next flag")]),
    dict(anchor="frame_drain", features=INSPECT, items=[
        dict(name="world.frame_queue", disp=0x6D0, at=0x142140091)]),
    dict(anchor="game_update", features=INSPECT, items=[
        dict(name="game.update_accumulator", disp=0x17F4, at=0x14168776D)]),
    dict(anchor="load_area_client", features=["area_export", "dump_object_types", "gen_batch"], items=[
        dict(name="world.area", disp=0xA0, at=0x141683F6F),
        dict(name="area.kind", disp=0x1B4, at=0x141683F7B),
    ]),
    dict(anchor="load_area_client", features=["area_export", "dump_object_types", "gen_batch"], items=[
        dict(name="world.tile_hash", disp=0x11C, at=0x1416841AC)]),
    dict(anchor="load_area_client", features=["area_export", "dump_object_types", "gen_batch"], items=[
        dict(name="world.doodad_hash", disp=0x120, at=0x14168424E)]),
    # gen_batch: what a synthetic world needs (docs/re/terrain/batch.md)
    dict(anchor="load_area_client", features=BATCH, items=[
        dict(name="world.stats", disp=0x130, at=0x14168443B,
             note="the world's stat map (sorted i32 key/value pairs at +8..+0x10; map_force_* live here)")]),
    dict(anchor="load_area_headless", features=BATCH, items=[
        dict(name="world.gen_flag", disp=0x66B, at=0x14213ED31, note="u8, cleared before a headless generation"),
        dict(name="world.gen_state", disp=0x4B8, at=0x14213ED38, note="the generation state (u32 +0, seed u32 +4)"),
        dict(name="world.gen_seed", disp=0x4BC, at=0x14213ED3E),
    ]),
    dict(anchor="terrain_topology_pick", features=BATCH, items=[
        dict(name="world.league_mode", disp=0xC0, at=0x14200829A, note="u32 mode column the topologies are filtered by"),
        dict(name="area.topology_count", disp=0x60, at=0x142008139),
        dict(name="area.topology_list", disp=0x68, at=0x142008150, note="16-byte entries"),
    ]),
    dict(anchor="terrain_gen_construct", features=BATCH, items=[
        dict(name="generator.validate", disp=0xE, at=0x141FFE7CC,
             note="u8, 1 after construction: runs the tile map validation pass (0x14200c930, throws TerrainGenerationException); the client clears it")]),
    dict(anchor="world_replace", features=BATCH, items=[
        dict(name="world.vt_delete", disp=0x20, at=0x1410145e8, note="vtable slot: deleting destructor (this, 1)")]),
    dict(anchor="resource_wait_loaded", features=BATCH, items=[
        dict(name="resource.state", disp=0x40, at=0x1421E74D2, note="2 = loaded")]),
    dict(anchor="table_rows_user", features=BATCH, items=[
        dict(name="table.rows", disp=0x28, at=0x141D0FDC1, note="pointer to (begin, end) of the table rows"),
        dict(name="resource.refs", disp=0x3C, at=0x141D0FD64, note="i32 reference count (lock inc / lock dec)")]),
    dict(anchor="room_check_user", features=BATCH, items=[
        dict(name="world.area_table", disp=0xA8, at=0x141F0DBC5,
             note="reference-counted WorldAreas table object (the world's area row belongs to it); the world's destructor releases it")]),
    # ---- generator and terrain ----
    dict(anchor="terrain_driver", features=EXPORT, items=[
        dict(name="generator.world", disp=0x38, at=0x14200DD32),
        dict(name="generator.terrain", disp=0x28, at=0x14200DD4B),
    ]),
    dict(anchor="terrain_driver", features=EXPORT, items=[
        dict(name="generator.state", disp=0x30, at=0x14200DD91)]),
    dict(anchor="terrain_driver", features=EXPORT, items=[
        dict(name="state.seed", disp=0x4, at=0x14200DA6B, note="u32 at the generation state")]),
    dict(anchor="phase_tile_hash", features=EXPORT + DUMP, items=[
        dict(name="terrain.width", disp=0x18, at=0x141D2137C),
        dict(name="terrain.height", disp=0x20, at=0x141D2137F),
    ]),
    dict(anchor="phase_tile_hash", features=EXPORT + DUMP, items=[
        dict(name="terrain.tiles", disp=0x28, at=0x141D213CE)]),
    # ---- network streams ----
    dict(anchor="stream_read", features=PKT, items=[
        dict(name="stream.error", disp=0x252, at=0x1421A82ED),
        dict(name="stream.msg_read", disp=0x278, at=0x1421A82FA),
    ]),
    dict(anchor="stream_read", features=PKT, items=[
        dict(name="stream.recv_base", disp=0x298, at=0x1421A8343),
        dict(name="stream.recv_end", disp=0x2A0, at=0x1421A834A),
        dict(name="stream.recv_head", disp=0x268, at=0x1421A8354),
    ]),
    dict(anchor="stream_write", features=PKT, items=[
        dict(name="stream.send_len", disp=0x258, at=0x1421a8475)]),
    dict(anchor="stream_write", features=PKT, items=[
        dict(name="stream.send_buf", disp=0x280, at=0x1421A8414)]),
    dict(anchor="stream_flush", features=PKT, items=[
        dict(name="stream.send_sent", disp=0x260, at=0x1421a85d7)]),
    dict(anchor="instance_session_handler", features=["side_channel"], items=[
        dict(name="session.key_material", disp=0x58, at=0x1421318CD, note="64-byte key material inside the stored InstanceDetails")]),
    dict(anchor="session_send", features=PKT, items=[
        dict(name="session.stream", disp=0x20F8, at=0x14212F10A)]),
    # ---- crypto ----
    dict(anchor="crypto_dh_agree", features=["crypto_bypass"], items=[
        dict(name="crypto.key_buffer", disp=0x60, at=0x1421AF540,
             note="pointer to the 64-byte key buffer inside the crypto session")]),
]

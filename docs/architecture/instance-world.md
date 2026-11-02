# Instance world

How instances and the simulation are organised: the instance directory, the instance actor that owns one `World` per instance and serves every session in it, and the `World` in `modules/server/crates/poe-game`. Wire side: [../protocol/instance.md](../protocol/instance.md). Movement spec: [../protocol/movement.md](../protocol/movement.md). Instance commands: [../guides/server-admin.md](../guides/server-admin.md#instances).

## Instance server

- **Instance directory** (`poe_cluster::InstanceDirectory`, in-process `MemoryInstances`): every instance (area, seed, forced topology and orientation, its players, since when it is empty). Find, create, join, leave, close and idle expiry work; towns and hideouts are persistent. It is metadata and the close signal; the running simulation is the [instance actor](#the-instance-actor).
- **One actor per instance.** `modules/server/servers/instance-server/src/actor.rs`: a tokio task owns the instance's `World`, entity counter and frame clock; every session of the instance (any number, any account) is a join on it. `run_session` (`lib.rs`) is a pipe between the client connection and the actor.
- **Live registry** of online players (`live.rs`): who, kick, tell, broadcast, mute.
- **Terrain:** the client generates the terrain itself from area and seed. The server picks the start cell from the layout and cell grid the DLL exports to `dumps/0.5.5e.hotfix1/terrain/{layouts,grids}/` (`[spawn] layout_dir`, `spawn.rs`; a remote client uploads them instead and `terrain_store.rs` caches them, [../protocol/side-channel.md](../protocol/side-channel.md#terrain-upload)). `[spawn.start_tiles.G1_1] point` is a grid cell in the start tile's own orientation (the Riverbank start is on the shore beside the intro tree, inside the `Intro_Tree_01` tile); the server finds which of the 8 rotations or mirrors the tile was placed with (`PlacedTile`, from the sub-tile index in the layout export, [client-dll.md](client-dll.md#layout-export-format)) and maps the point onto the map. Server-side generation (`[terrain] generate`, `!terrain`) is for comparison only: [../status/terrain.md](../status/terrain.md). Until it covers every area the server uses seeds the client is known to accept (`[dev] known_seeds`, from live logs) or a random one.
- **Saved location:** when a session ends the server stores the character's area, terrain seed and cell (`poe_store::Location`, migration `0005_character_location.sql`); the next login into that area gets the same seed and spawns on the saved cell (or the nearest walkable cell if blocked). A character never in the game starts at the area's start position.
- **Entities:** the players (ids from `[instance] first_entity_id`, 12000). NPCs need their StateMachine and quest states ([../protocol/entities.md](../protocol/entities.md)); `POE_NPC=<metadata path>` adds one more object for experiments.

## The World (`modules/server/crates/poe-game`)

One `World` per instance. It knows nothing about sockets, packets or opcodes: sessions feed it typed input, the tick loop calls `tick()`, and it returns typed events.

| Module | Contents |
|---|---|
| `world.rs` | `World`, `WorldConfig`, `Entity`, `EntityId`, `Event`, `WorldEvent` |
| `locomotion.rs` | the movement component: `Locomotion`, `MoveInput`, `MoveEvent`, `MoveState`, `MovementConfig` |
| `grid.rs` | `GridSource` (terrain for the simulation), `Grid` (the client's dump), `VecGrid` |
| `movement.rs` | `Walkable`, `Mover` (advance, slide, roll speed profile, `Motion`) |
| `clientpath.rs` | port of the client's pathfinder (jump point search, level-dependent wall clearance, [../re/pathfinding.md](../re/pathfinding.md)); `Mover` plans walks, WASD, sprints and rolls with it (`[movement] pathfinder = "client"`) |
| `pathfinding.rs` | the older A* (`find_path`) with line-of-sight smoothing, selected by `pathfinder = "approx"` |

### World
```rust
let mut world = World::new(WorldConfig::new(movement_config), Arc::new(grid)); // Arc<dyn GridSource>
let me = world.spawn_player((x, y));            // EntityId, ids unique per world (first_entity_id)
world.input(me, MoveInput::Direction { x: 180, y: 0 });   // queued; answered by the next tick
let events: Vec<WorldEvent> = world.tick();     // one frame; the caller owns the timing
```
- **Frame clock.** `frame()` counts ticks; `tick()` advances exactly one frame of `tick_ms` (default 33). The world never reads a clock: the instance's timer calls `tick()`, so replays, tests and a paused instance (`set_paused`) need no special cases.
- **Entities.** `Entity { id, next_buff, movement, config }`: a struct with components as fields (no ECS); `config` is an optional per-entity `MovementConfig` (`spawn_player_with_config`) for class-dependent values. `next_buff` is the buff index allocator shared by every component that adds buffs. `despawn`, `teleport(id, cell)` (reported as `MoveEvent::Teleport`), `set_grid` (the grid can arrive after the world).
- **Counters.** `StartAction` ids come from one world-wide counter (the official one is server-wide, 32768+, `first_action_id`).
- **Events.** `tick()` returns `WorldEvent { frame, entity, event }`, ordered by entity id and within an entity in send order. `Event` is `#[non_exhaustive]` (today only `Movement(MoveEvent)`). `frame` is the batch the message belongs to: the session sends every event of a tick before the `SimulationTick` marker.
- **N players.** Everything is per entity. The [instance actor](#the-instance-actor) spawns every player into one world and relays each event to every session.

### GridSource
```rust
pub trait GridSource: Walkable + Send + Sync {
    fn size(&self) -> (i32, i32);
    fn nearest_walkable(&self, cell, radius) -> Option<(i32, i32)>;   // default impl
}
```
`Walkable` (per cell `walkable(x, y)`, optional `clearance`) is the trait `Mover` and the A* use. Implementations: `Grid` (the DLL's `terrain_grid_<tile hash>.bin`; parsing lives here, `instance-server/src/spawn.rs` re-exports it), `VecGrid` (tests, tools), `Open` (no terrain). The world only sees the trait.

### Terrain grid sources
The instance server (`servers/instance-server/src/lib.rs`) chooses where the grid comes from:
- **The client's grid** (default): the DLL's `terrain_grid_<tile hash>.bin`, from the layout cache or uploaded ([../protocol/side-channel.md](../protocol/side-channel.md#terrain-upload)).
- **The generated grid** (`[terrain] generated_grid = true`): `poe_world::area::generate_with` makes layout and doodads, `poe_world::collision::build(&map, files, &doodads, Side::Client)` the four cell layers (client side, because the server does not send the `server_only` objects yet: [doodads.md](../re/terrain/doodads.md#live-grid-and-server-side-objects)), and `.pwg1()` their bytes in the `PWG1` format the DLL exports; `poe_game::grid::Grid::parse` reads them. Used only when the generated tile hash equals the one the client reported; otherwise (error, panic or different layout) the server logs a warning and keeps the client's grid. Byte-for-byte status per area: [../re/terrain/doodads.md](../re/terrain/doodads.md).

`poe-world` depends neither on `poe-game` nor on `poe-config`, and `poe-game` does not depend on `poe-world`. `PWG1` is the contract between them and the instance server is the adapter: one serialise/parse per instance, but the generator stays a pure library (game data in, bytes out) usable without the simulation.

### Movement component (`Locomotion`)
Server-authoritative movement for the client's lockstep mode ([../protocol/movement.md](../protocol/movement.md)). Inputs mirror the client packets; output events are semantic and in the order the official server sends the messages.

| `MoveInput` | Client packet |
|---|---|
| `Direction { x, y }` | `0x63` MoveDirection (WASD vector) |
| `UseSkill(UseSkill)` | `0x1a5` (skill, flags, target flags, optional entity, x, y) |

| `MoveEvent` | Server message |
|---|---|
| `MoveAck { dir, cell }` | `0x64` (dir already scaled while sprinting) |
| `ActionStart { kind, skill, action, cell, target, entity, unk }` | `0x1c8` (flags `0x410` for Roll/Other, 0 for Move) |
| `TargetAck { skill, x, y }` | `0x1af` |
| `SprintState { held }` | `0x2e7` |
| `Teleport { cell }` | a `0x64` with a non-zero direction and the new cell (the client snaps at 46+ cells), or a StartAction |

Other inputs: `UpdateSkillTarget` `0x1a8`, `SkillInputEnd` `0x1ac`, `SkillReleased { skill, flag }` `0x1ad`, `SprintInput { held }` `0x2e6`, `Aim`/`AimEntity`/`AimMode` `0x62` (mode 2 / 3 / 0 and 1). Other events: `ActionEvent` `0x1ca`; `Stats` `0x1d3` set 0 (`MoveStat::id()` is the game stat id, the session resolves the network key from `poe-data`); `SkillAck` `0x1ae` (the session ORs the "confirmed" target flag `0x04`); `TargetAck` `0x1af`; `InputEndAck`/`ReleasedAck` `0x1b1`/`0x1b2`; `SprintState` `0x2e7`; `BuffAdded`/`BuffRemoved` `0x1eb` (flag `0x02` when `fade`) / `0x1ec`; `AimEcho` `0x1dc` kind 0; `StanceChanged` `0x2f9` (Player component, stance byte).

State machine (`MoveState`): `Idle`, `Walking(Direction(v) | Target { goal })`, `Rolling(Rolling { start_frame, held, offset, action, sprint, sprinted })`, `Sprinting(SprintRun)`. A sprint starts at `t0 + 15` inside the roll (`Rolling.sprint`) and becomes `Sprinting` when the roll action ends at `t0 + 30`.

Frame order inside `Locomotion::tick`: (1) the entity moves one frame, (2) queued inputs are handled in arrival order and answer directly, (3) due timeline events run (roll stats at +16, sprint start +15, roll end +30, `must_sprint` off +35, stance), (4) the frame's `MoveAck` (unscaled after a direction change, scaled per frame while the sprint stream runs), then events that follow it, (5) a sprint end by key release. A movement started by a reply in frame `F` first moves in `F + 1`, as on the client. `Mover` does the walking (path, wall sliding, roll speed profile, sprint scale).

`MovementConfig` holds what the logic would otherwise hard-code: skill ids (`SkillIds { move_skill, roll_skill }`), the three sprint buff rows (`SprintConfig.buff_rows`), roll distance, frame offsets (15, 16, 30, 35), sprint scale and the wire length of a sprinting direction (550), sprint stat values, walking speed. `MovementConfig::new(skills, buff_rows)` fills the official values; skill ids and buff rows come from game data when the session builds it. Other speeds use `spawn_player_with_speed`.

### Tests
Unit tests per state transition (`locomotion.rs`, `world.rs`, `grid.rs`, `movement.rs`); **replay tests** (`modules/server/crates/poe-game/tests/replay.rs`) feed input sequences from official captures into a `World` and compare events per frame (kind, order, fields, frame offsets; cells with a tolerance, wide during rolls: [roll path](../protocol/movement.md#roll-path-and-speed-profile)); two are `#[ignore]`d with the gap that explains them. Fixtures (`modules/server/crates/poe-game/tests/fixtures/*.json`) hold only the local player's movement and skill messages, regenerated with `python3 scripts/re/movement_fixtures.py build` (needs `dumps/0.5.5e.hotfix1/captures/official/` and `cargo xtask dll-data`). `instance-server/src/replay_tests.rs` runs the same fixtures through an actor as encoded packets; `actor_tests.rs` drives one `Actor` with fake sessions (entry batches, relay with identical bytes, leave sequence, supersede, kick, close, idle end, pause for one player). Behaviour the captures do not show is marked `// UNVERIFIED (gap #n)` in the code, matched to the movement spec's [gap list](../protocol/movement.md#gap-list).

## Wiring the movement into the instance server

Two pure mappings that know neither sessions nor the actor, in `modules/server/servers/instance-server/src/`:

| File | Role |
|---|---|
| `movement.rs` | `client_input(name, reader)`: client packet (by name in the opcode table) to `MoveInput`. `Codec::encode(entity, &MoveEvent)`: event to the official messages (`Out { name, bytes, trace }`). Opcodes come from `instance.toml` through `poe-proto`; stat keys through a `StatKeys` closure over the game's `Stats` table; no entity or session state. |
| `player.rs` | the session's side: `OwnedSkill`, `sim_config` (builds the `MovementConfig` from game data: Move skill = `0x20000000 | ActionTypes.Move`, the roll skill = the owned skill whose action type is DodgeRoll with its `dodge_roll_base_travel_distance`, walking speed `Pathfinding.base_speed`, the class's `sprint_movement_speed_+%`, `[movement] sprint_buff_rows` and the sprint coasting keys) and `Player`, the handle to the session's entity in the actor. |
| `sync.rs` | the side-channel sessions (HMAC-authenticated UDP datagrams keyed by session: position reports, debug link, [side-channel.md](../protocol/side-channel.md)) and `DriftCheck` ([movement.md](../protocol/movement.md#drift-checker)). Reports never feed the simulation; the opt-in drift checker (`[dev] drift_check`) only reads them. |
| `terrain_store.rs` | the terrain cache in `[spawn] layout_dir`: authenticated TCP upload of the client's layout and grid (validation, per tile hash), and the wait `spawn.rs` uses. |
| `actor.rs`, `appearance.rs`, `lib.rs` | the instance actor, the blobs that describe a character, the session loop ([below](#the-instance-actor)). |

- **Frames.** An input received between ticks is queued and answered by the next tick (`r+0`). The tick's events are sent in order, then the `SimulationTick` marker. The `frame` of a `WorldEvent` is that batch's number.
- **Header.** `(entity, 0, 0, 0)` for everything except `0x64` (`(entity, entity, 9, 0)`) and the stance delta (`(entity, 0xffffffff, 0, 0)`); official servers use ordering values in `u1a` the client does not need.
- **Terrain.** The world is created with `Arc<dyn GridSource>`: the client's dump `Grid` (DLL export or upload; `Open` when missing). The saved or start cell is moved to the nearest walkable cell first.
- **Dev teleport**: `World::teleport`, reported by the next tick as a `0x64` pair.

## The instance actor

One task per instance owns everything shared. Sessions never touch the `World`.

```
client A ── run_session ──Cmd──►┐                       ┌──Frame──► run_session ── client A
client B ── run_session ──Cmd──►│ instance actor (World)│──Frame──► run_session ── client B
                                └ one clock, one entity counter, one grid
```

### Ownership and lifetime
- `InstanceServer::actors` (`actor::Actors`) maps the instance id to an `ActorHandle` (an unbounded `mpsc` sender, the player count, the area). `poe-cluster`'s `MemoryInstances` stays the directory (what an instance is, who is in it, when it closes); it has no game types, so the handles live in the instance server, and the actor writes the directory's player list (`join`/`leave`), so `instances`, the overlay and the web API come from the actors.
- **Created by the first join** (`Actors::join`; a join retries when the actor ends in between, and fails when the instance is gone from the directory). The first joiner supplies the world's default `MovementConfig` and the grid; every entity carries its own `MovementConfig` (`World::spawn_player_with_config`), so classes share a world with their own sprint bonus, roll distance and speed.
- **Ends** when the directory closes the instance (`close`, idle expiry; remaining sessions are disconnected), or after `[instance] idle_minutes` without players, towns and hideouts too (their directory entry stays; the next join starts a fresh actor and world). While nobody is in it the clock does not tick. Ending drops every output channel, which ends the sessions left.
- **Entity ids** come from one counter per instance, starting at `[instance] first_entity_id` (12000: the official counter gives players 12000 and up). Never reused.
- **One clock**: a `tokio` interval of `[instance] tick_ms` calls `World::tick()`; commands that arrived before the tick are drained first, so an input received before the tick is answered by it (`r+0`).
- A session is a `SessionId` (a process-wide counter) and the live registry is keyed by it, not by the client's port. A duplicate login of an account ends the old session (`LoginSessions::supersede`).

### Messages
| Session to actor (`actor::Cmd`) | |
|---|---|
| `Join { request, reply }` | `JoinRequest`: session id, character name, wanted spawn cell (the actor moves it to a free walkable cell at least `[spawn] player_spacing` from the players there, `spawn::spread`), speed, `MovementConfig`, grid, `Appearance` (class object type key, the local `AddObject` blob as a function of the final cell, the remote `PlayerBlob`), `want_debug`, the session's output channel. Reply: `Joined { entity, add_objects, players, own }`. |
| `Input { session, input }` | a `MoveInput` for the session's entity (queued, answered by the next tick) |
| `Leave { session, reply }` | the session ends (disconnect, kick, transfer, supersede, error); the reply is the cell the entity stood on |
| `Teleport { session, cell }` | dev/admin |
| `SetPaused { session, paused, reply }` | the escape menu; the reply says whether it was applied |

Local chat is not an actor message: `chat::deliver` sends it through `live.rs` to every session whose registered instance id matches the actor's key.

**Actor to session: encoded packets, not semantic events.** A tick's events are encoded once (`Codec`) and the same bytes go to every session in a `Frame { head, events, trace, own }`, because the official server relays each entity's simulation messages unchanged to every client (a remote player's `0x64` has the same header `(A, A, 9, 0)` as the local one; the acks `0x1ae`/`0x1af`/`0x1b1` are relayed with the remote entity id). Per-session encoding would repeat work and let copies diverge. What differs per session:
- `Frame::head`: lifecycle messages for this session before the events: another player's `AddObject`, the removal sequence of one that left, the release of a pause.
- `Joined::add_objects`: the entry batch of the joining session (other players in remote form, then itself in local form).
- `Frame::events`: shared by all sessions except where an event of the session's own entity has an owner-only stat (`Stats.IsParty` false, e.g. `stun_threshold_+%_final_while_performing_action` in a roll batch): the owner gets the full encoding, everybody else `Codec::encode_for_others` (the official server leaves those stats out of what it relays; [../protocol/entities.md](../protocol/entities.md#remote-roll-check)). The shared bytes are the others' view.
- `Frame::own`: the session's own pose (frame, cell, exact position, optional debug state) for the drift checker, `where`, the debug link and the saved location.
- `Frame::events` ends with the `SimulationTick` marker, so a paused or idle frame is still a frame.

### Join
1. The session finishes its terrain handshake, builds the `Appearance` (`appearance.rs`) and sends `Join`.
2. The actor spawns the entity and answers `Joined`. To the **joining** session: `LocalPlayers`, `PlayerEntity` (`0x24`, the entity id), the `AddInventory`s, then `add_objects` (players already there as `PlayerBlob` remote `AddObject`s with current cell and stance, then itself with the local blob, header `(id, 0xffffffff, 0, 0)`), a `SimulationTick`, and `InitialState` with `PlayerState.player_id` = the entity id. To every **other** session: one `AddObject` for the newcomer (remote form) in the head of the next frame, nothing else.
3. The local blob is the one that always worked (the class's `.ao` path in Animated). The **remote blob** (`appearance::remote_blob`) is the official remote layout from [entities.md](../protocol/entities.md#local-vs-remote-addobject-blob): flags 2, class object type key, name, class, `level` and other base stats, the character's skills, life pools, `Animated` with flags `0x80` (no path), Player flags `0x0c` in combat stance and 0 otherwise, `+0x3e7` = 2, the three animation set names from `[player] animation_sets` (official: weapon dependent; characters have no equipment yet, so unarmed), the four official shapeshift/trailer bytes. Not filled (no data): equipment visuals, link records, buffs, stat sets, quest flag words. The two-client test ([hosting.md](../../modules/server/docs/hosting.md#local-two-client-test)) shows the other player correctly without them; only its model looks darker than the local one.
4. A session whose client crashes or leaves right after joining is removed by a `Leave` (a closed output channel counts as one).

### Relay
Every `WorldEvent` of any entity goes to every session in the instance in the same frame (`0x64`, `0x1dc`, `0x1c8`, `0x1ca`, `0x1d3`, `0x2e7`, acks, buffs, stance). Interest management is the whole instance (the official town shows no player radius). Movement trace lines in a frame name their entity; a session traces only its own.

### Leave
On a disconnect, kick, transfer, supersede, close or error the session's `Player` is dropped (or `Player::leave` called), which sends `Leave`; the actor despawns the entity and puts into the next frame of every remaining session, in this order: `PresenceChanged` (`01 01 01 00`), `DestroyEntity` and `EntitySleep` at key 0, `RemoveObject` at key `0xffffffff`. The entity's queued inputs never run. Because the drop does it, every exit of `run_session` is covered, including a duplicate-login supersede.

### Pause
In a **town** the client never pauses (the official town capture has no `PauseRequest`), so `InitialState` flags there are `4`, not `7`: bits 0/1 would start the client's world paused with nothing to release it ([instance.md](../protocol/instance.md)). The server also uses `4` in hideouts (unverified there). The escape menu pauses the world only for a **single player** (official solo behaviour): `SetPaused` is applied when the session is alone in the actor, and the session answers its client with `SetPause(paused)`. With other players the request is refused, the world keeps running and the client gets `SetPause(false)` (the official multiplayer reply is not captured: UNVERIFIED). A pause is released when a second player joins (the paused session gets `SetPause(false)` in its next frame) or when the pausing player leaves.

### Admin and the web API
- `instances` (chat command, overlay, `AdminControl`) lists the directory's players, which only the actor writes, with the actor's count.
- `close` closes the instance in the directory: its actor ends and its sessions are disconnected. `transfer`/`join` hand the session a ticket for another instance and end the session (a `Leave` first); the web API's `transfer_player` kicks the live session after handing off.

### Party and trade
`social.rs`: `Social` (inside `Live`, `live.social`) keeps the open parties and trades and one queue of `SocialOut` messages per session (`register` at session start with the character's `Person`: names, level, class, area hash, instance and entity id; `unregister` at the end). The session loop writes the queue to its client like a chat line (`run_session`, `Some(out) = social_in.recv()`), outside the actor's frames, so it works between instances. `handle_client_message` routes `PartyInvite`, `PartyInviteCancel`, `TradeRequest` and `TradeCancel` to `Social` (a refusal comes back as a server chat line) and **only logs** `PartyAccept` and `PartyDecline`. A trade request sends the two trade-window `AddInventory` (slot `0x79`) before the `TradeState` (without them the client crashes); a cancel for a closed trade is ignored silently. A session that ends cancels its open parties and trades. Messages and what is verified: [../protocol/entities.md](../protocol/entities.md#party-and-trade-flows). Tests (`social.rs`): the inviter's batch and the cancel against the official bytes (anonymised), the invitee's and target's batches, a trade cancelled by either side, a leaving player ending what it had open, and refusals.

## Not built yet
- **Lockstep with several clients:** all clients follow the instance's frame clock. Two real clients on a LAN worked (relayed walk and roll, chat, leave); how the client treats other entities' actions arriving late over a bad link is untested.
- **Movement authority:** the server owns every player's position (the DLL drift checker only compares); exactness depends on server-side terrain.
- **Shared instances by default:** `play_character` finds or creates per area; towns and hideouts are persistent. Official behaviour is per-party instances for zones and shared towns, which needs parties.
- **Late join, remote blob extras, parties:** a late join was never captured (assumed the same `AddObject`); whether the client needs the optional parts of the official remote blob (stat sets, buffs, flag words, equipment visuals) and party/trade accept/decline/timeout are open ([../protocol/entities.md](../protocol/entities.md)). `InitialState` stays local-only (121 bytes in a town with three other players).
- **Interest ranges** (wake zone toggling for objects) when NPCs exist.

# Movement

How the client moves the player and what an **official** server sends back, from seven read-only official capture sessions (`dumps/0.5.5e.hotfix1/captures/official/`, 2026-10-14..20; `2026-10-20_18-41-14_336` has the client's per-frame positions) and the client's code. The tool behind every sequence is `scripts/re/movement_sequences.py` ([Reproducing](#reproducing)). Code: `modules/server/crates/poe-game/src/locomotion.rs` (the movement component, [instance-world.md](../architecture/instance-world.md)), `world.rs`, `movement.rs`, `clientpath.rs` (port of the client's pathfinder, [docs/re/pathfinding.md](../re/pathfinding.md)), `pathfinding.rs` (older approximation); `modules/server/servers/instance-server/src/{movement,player}.rs` (packet glue, [below](#server-implementation)); messages in `modules/protocol/poe-proto/src/instance.rs` and `skill.rs`.

Six sessions are **WASD input mode** only; the 2026-10-20 session adds **click-to-move mode** (f3287-4662), standing and chained rolls, sprints into walls, an input-mode toggle and client positions (`poe-hook.log`, "frame #n ... world ... grid", same frame numbers). Missing: [gap list](#gap-list); frame index: [capture index](#capture-index-2026-10-20-session).

Conventions:
- Frame numbers count the server's `0x02f4` ticks received by the client. A **batch** is the run of simulation messages before a tick marker. `f` = frame the client sent an input in; a reply "at `f+1`" arrives after one more tick. Round trip on the official servers: median 50 ms, p90 62 ms, so **the reply is at `f+1` for ~93 %** of inputs (`f+0` ~6 %, `f+2` <1 %). The server controls only that all replies of one input share the first batch after it arrived (`r+0`); `r+k` is k batches later.
- Cells are grid cells (23 per tile). Position fields in replies are the **server's** player cell at that tick.
- The header of a simulation message is `(entity, u14, u18, u1a)` ([instance.md, Frame ordering](instance.md#frame-ordering)). Official replies to the local player use `(player, 0, 0, 0)` or an ordering value in `u1a`; zeros are valid.

## Client facts

### Lockstep: the server starts every movement
- The in-game world is created in frame mode 2 (world +0x661, constructor `0x14212ece0` called from `0x14100b979` with a constant 2): **lockstep**.
- The client's `[NETWORKING] networking_type` option (`auto`/`lockstep`/`predictive`, read by `0x141939fc0`) is a PoE1 leftover. With `auto`, the session update (`0x142120cf0`) only switches a world whose +0x661 is 3: below 70 ms latency it picks 2, above 90 ms it picks 0.
- So pressing W, clicking or pressing Space sends a request and nothing moves until the server answers. The skill senders (`0x14210faa0`, `0x14210fec0`, `0x14210ff40`, `0x14210fd30`) skip their local path when `world +0x661 == 2`, and the Player component handlers for the replies (`0x1ae`..`0x1b2`) run only outside predictive mode ([addresses](../re/addresses.md#skill-acknowledgements-buffs-sprint)).
- The answer starts the movement on the client, which then moves the entity itself every simulation frame (`dt = frame_ms / 1000`, [instance.md](instance.md)) along paths from its own pathfinder ([below](#the-clients-pathfinder)) until the movement ends. The server simulates the same movement to know where the player is.
- Messages that carry a position (`0x64`, `0x1c8`) make the client snap to the server's position only when its own is **46 cells or more** away (squared distance >= `0x844`: `0x1421497c0` for `0x64`, `0x141e41c60` for `0x1c8`; snap = `0x141ddb6f0` SetLocationForcedNoCallbacks). Closer, `0x64` only bends the walk direction and `0x1c8` keeps the client's position. In lockstep (world vfunc +0x1d8 = 1 is the *other* mode) a `0x64` whose cell differs from the client's is a forced placement **only when its direction is not zero**; a `(0,0)` update ignores its cell.
- **Frame playback** (`0x142130440`): the client plays received frames in real time with a speed factor: 1.01x with one spare frame queued, up to 5x with a long queue, 1.0x once drained. It never runs past the last received frame, so late frames freeze movement and bursts make it rush. Details: [timing](#timing).

### Timing
All addresses Hotfix 1; world offsets from the game world object (frame mode 2).

**Frame queue** (`0x142134260`, called for every received simulation packet):
- Packets other than `0x2f4`/`0x2f5` go into the packet vector (world +0x6b0 begin, +0x6b8 end, +0x6c8 drain cursor).
- **`0x2f4` has no body** (official: always 2 bytes, the opcode only, in all 8 captures). It pushes a null separator into the packet vector and pushes the **current world +0x11c** (`frame_ms`) into a `std::deque<u32>` of frame lengths (world +0x688; map +0x690, map size +0x698, offset +0x6a0, count +0x6a8). Only when world +0x661 (frame mode) and world +0x86a (started: set by the world start `0x14212fd90`) are set; markers that arrive earlier are dropped, so the `0x2f4` after the player's `AddObject` and before `InitialState` closes no frame, and the world start applies everything queued at once.
- **`0x2f5`** (`u8`) is applied on arrival: world vfunc +0x178 (`0x140b27ac0`: `mov [world+0x11c], edx`) sets the frame length for markers received after it, 0-255 ms. Official servers never send it (0 in all captures); their `InitialState` has `frame_ms = 33` (`00 21`).

**Playback** (`0x142130440(world, ctx, f32 dt)`, `dt` = real time of the render frame from the session update `0x142120cf0`, 4th argument; no clamp traced). Fields: +0x66c time bank, +0x670 speed factor, +0x674 played simulation time not yet given to the visual update, +0x668 real time while the queue is empty (reset when not empty), +0x680 highest look-ahead count. Each call:
1. Look-ahead: with `bank + dt * speed`, count the queued frames that fit (each `ms / 1000`); `R` = frames left over. +0x680 = max(+0x680, R).
2. Target factor: 5.0 for `R >= 60`, 2.0 for 30-59, 1.5 for 2-29, 1.01 for 1, none for 0. **speed = max(speed, target)**: it only rises here.
3. `bank += dt * speed`. While the next frame's length fits in the bank: drain it (world vfunc +0x3c0 = `0x14212ecd0`, a jump to `0x142130840(world, frame_dt)`), `bank -= frame_dt`, +0x674 += frame_dt.
4. Visual update: `v = min(+0x674, dt * speed)`; if `v > 0`, vfunc +0x3c8 (`0x142130d80`, posts a task job) gets `(dt, v)` and +0x674 -= v.
5. Bank cap: at most the next queued frame's length (or world +0x11c when the queue is empty). A starved client plays at most one frame as soon as the next marker arrives; it does not bank the time it waited.
6. If this call played every queued frame and speed > 1, speed = 1.0. So the factor drops only when the queue drains, which is why the steady walk runs at 1.01 with short steps each time the client catches up ([speeds](#speeds)).

**Per-frame dt.** The drain `0x142130840` pops one frame length from the deque and applies that frame's packets in order key phases ([instance.md](instance.md#frame-ordering)); the entity update `0x142137270` gets **`frame_dt = recorded frame_ms / 1000`**, or 0 while paused (world +0x868). The client never measures frame time for the simulation: real time only decides **when** frames play, not how far they advance. The server's simulation must use the same fixed `dt = frame_ms / 1000` per tick (ours: `World::tick`, `tick_ms`). Measured dt would put it out of step with the client.

**Official tick clock** (`scripts/re/tick_timing.py`, all 8 official captures; times are the DLL's receive times):
- Rate 30.26-30.32 ticks/s; within an area the mean spacing is 32.98-33.02 ms, and between stalls the lag against an ideal 33 ms clock stays within about 80 ms over 4-5 minutes (no drift): **absolute 33 ms deadlines**.
- **Stalls are caught up with a burst:** a 1,353 ms gap was followed by 41 ticks back to back (`2026-10-15_23-03-45`), a 1,203 ms gap by 36. Lag before and after was the same, so no frame was lost. Once, in the busy town (`2026-10-20_21-51-49`), a 270 ms gap lost about 5 frames for good.
- Our server does the same ([server implementation](#server-implementation), `servers/instance-server/src/clock.rs`).

### Speeds
- Walking: the Pathfinding component (constructor `0x141dcd1a0`) stores `Pathfinding.base_speed` at +0x550 and a multiplier of 1.0 at +0x55c; the getter `0x141dccfa0` returns `base_speed × (1 + movement_velocity_+permyriad/10000) × (1 + virtual_action_speed_+%/100) × multiplier`. Units are **cells per second**; characters have `base_speed = 37` (**1.23 cells per 33 ms frame**, measured 37.0 cells/s).
- Sprinting: the official stats `base_move_speed_+%_from_sprint = 50` and `movement_velocity_+permyriad = 5000` give 1.5x: measured mean step **1.83..1.89 cells per frame**.
- **Mean speed equals the server's; per frame the client's steps are bumpy.** The DLL's `dt` is exactly 0.033 in every frame, the server's tick spacing is 33.00 ms, and a 94-frame W walk (114.8 cells) gives a client mean step of 1.2210-1.2216 against the server's `37 * 0.033 = 1.2210`. The client's steady step is **1.2333 = 37 / 30 = 1.01 x 1.2210** (playback factor 1.01 while a frame is queued) with one short step of about 1.08 every 9 to 12 frames when it has caught up with the last frame. It never runs past received frames, so it keeps the server's pace; the per-frame difference is at most 0.15 cells (a stop ends one step, 1.2 cells, ahead of the server: the constant 1.2-1.3 in the drift checker). So `speed * dt` per tick is the right model; `speed / 30` is only the steady step (used for the coast).
- **Action speed factor (attacks while walking).** An attack does not stop a walk (WASD, click or a walk restarted after a sprint); the client multiplies the walking speed by the Actor's factor (+0x440, into Pathfinding +0x55c). The running action sets a target `1 + A/100 x (1 + B/100)` (A `movement_speed_+%_final_while_performing_action`, B `virtual_movement_speed_penalty_%_while_performing_action`) and a ramp rate (`movement_speed_acceleration_+%_per_second_while_performing_action` / 100); after `movement_speed_while_performing_action_locked_duration_%` of the action it ramps back to 1 ([addresses](../re/addresses.md#skill-acknowledgements-buffs-sprint)). Measured on the client's steps (2026-10-20, 4 attacks while walking: f2090, f2394, f4005, f4142; factor = step / 1.2333): frames 1-5 after the attack's `0x1c8` fall about 0.05 per frame (1.5/s), frame 6 is a partial step, **from frame 7 the factor is 0.28-0.31**, and from frame 13 (17 once) it rises about 0.053 per frame back to 1. The drop at frame 7 is not explained by the ramp (another call sets the factor at once; not traced). Attack stats come from the weapon, which the server does not model, so the server uses these measured values (`[movement] attack_speed_*`: floor 0.3, ramp 1.5/s, snap at 7, ramp back after 12; `locomotion::AttackSpeedConfig`, `Mover::factor`). A roll resets the factor to 1 (unverified). Replay fixtures `attack_while_click_walking` (worst 1.5 cells from the client, 7.4 without the factor) and `attack_ends_sprint_then_walk` (1.9, 12.4 without).
- Dodge roll: `dodge_roll_travel_distance` (`0x141aa9250`, stat `0x57fa`) = 46 cells. Measured in 30 official rolls: 45.2..46.3 cells along the path in 29-31 frames, see [Roll path and speed profile](#roll-path-and-speed-profile).

## The client's pathfinder
The client plans every walk itself (algorithm, addresses, evidence: [../re/pathfinding.md](../re/pathfinding.md)): a bounded jump point search over layer 0 of its 4-bit cell grid, then two line-of-sight thinning passes. It is used for click-to-move, WASD (goal = cell + `floor(vector * 0.092)`, re-aimed every 0.05 s = 2 frames), the sprint stream (every frame) and rolls (every frame, goal = the roll's remaining distance ahead). Cells whose grid value is **at most the entity's pathing level** are walls: level 0 while walking and rolling (hugs walls), **level 4 from the roll's sprint until the sprint ends** (keeps about 5 cells off walls). The plan starts from the client's own grid cell, a digital line that trails the position by up to half a cell.

Server: `poe_game::clientpath::plan` is a port (536 of 541 plans the client logged come out identical, `cargo test -p poe-game --test clientpath`); `Mover` plans walks, WASD, sprints and rolls with it and follows the first legs at walking speed; a coast after a sprint carries on in the last step's direction until a wall. Not ported: dynamic obstacles (other entities), the A* fallback branch, the line-of-sight variant next to the start of a moving entity (5 of 541 plans differ in one waypoint). `[movement] pathfinder = "approx"` selects the old A* with wall sliding.


Drift checker, port against `approx` (cells, max in a second / after the stop): rock-field walks 29.7 / 29.6 → 1.3-2.3 / 0.8-1.4, standing tap roll into a wall 14.8 / 14.7 → 6.0 / 1.4, cursor sprints towards a wall 8.2 / 8.2 → 4.0 / 0.5, click walks towards a rock field 6.3 / 6.3 → 1.2-1.4 / 0, open ground unchanged (sprints 3.9 / 0.15-0.5, rolls 3.9-4.2 / 0.7-1.1). The old pathfinder failed next to walls: it hugged the wall where the client keeps off it (sprints) or planned another way round a rock field.

## Messages

### Client → server
| Op | Name | Body |
|---|---|---|
| `0x63` | MoveDirection | `u8 1, varint x, varint y, u8[3]`. Sent when the held direction changes. Vectors of length ~180 in grid axes: `(127,127)`, `(180,0)`, `(-127,-127)` …, `(0,0)` = stop. **Arbitrary angles are the cursor direction**: with Space held and no WASD key (a sprint, also standing or after the keys are released) the client sends the direction to the cursor every frame it changes (`(94,-153)`, `(-163,76)` …); the third trailer byte is `1` in click-to-move mode, `0` in WASD mode (also `[0,0,0]` for W and for the cursor in WASD mode, so no flag there). `(0,0)` is never sent while a roll or sprint runs (0 of 380). |
| `0x62` | AimTarget | `u8 player, u8 mode`; mode 2: `i32 x, i32 y` **absolute cell**; mode 3: `u32 entity`; modes 0/1: nothing (once at entry). About one mode-2 per frame while the cursor moves, only in combat stance. |
| `0x1a5` | UseSkill | `u8 player`, skill block: `u32 skill, u16 flags, u8 0xff, u8 target flags, [u32 entity if flags & 8], i32 x, i32 y` (x, y **relative to the player's cell**, absolute with a target entity). |
| `0x1a8` | UpdateSkillTarget | `u8 player, i32 x, i32 y (relative), u32 skill`. About every 70 ms (2 frames) while a roll or sprint runs (key held or not) and while a held skill runs. |
| `0x1aa` | UpdateSkillTargetEntity | `u8 player, u32 entity, u32 skill`. |
| `0x1ac` | SkillInputEnd | `u8 player`. Held skill input ended: Space released (always together with `0x2e6` held=0), attack button released. |
| `0x1ad` | SkillReleased | `u8 player, u32 skill, u8 0`. The release of the Move skill (a click-to-move press: 2 frames after the press for a click, at the end of a clean hold; 5 of 12 holds ended without one) and, **in click-to-move mode, of the roll key** (instead of `0x1ac`, sent with `0x2e6 held=0`). |
| `0x2e6` | SprintInput | `u8 player, u8 held`. Space down / up. |
| `0x200` | StanceRequest | `u8 player, u8 value`. Input mode toggle (mouse and keyboard <-> WASD), together with `0x62` mode 0 (value 1) or mode 1 (value 4) in the same frame. Answered by a stance delta, see [Input mode and stance](#input-mode-and-stance). |

Skill ids (official server; basic actions are `0x20000000 | ActionTypes key`):

| Id | Skill |
|---|---|
| `0x20002909` | Move |
| `0x80000040` | **Dodge roll** (stats: `deal_no_damage`, `base_deal_no_damage`, …) |
| `0x80400040` | main attack (damage stats), `target flags` 0x08 on an entity |
| `0x2000c266` | basic action used with a target entity (interaction) |
| `0x2000b7d9` | the intro's wake-up action (reply to the first click) |
| `0x40000005`/`6` | `0x1d8` stat containers of other entities (`attack_time_ms_for_stat_scaling_effects`) |

Target flags seen on `0x1a5`: `0x00` plain press, `0x08` target entity, `0x10` held repeat, `0x01`/`0x02` extra input bits (`0x13`, `0x1b` on held repeats). The server's ack echoes `flags` and `u8` and sets `0x04`.

### Server → client (all simulation messages with the 11-byte header)
| Op | Name | Body after the header |
|---|---|---|
| `0x64` | MoveDirectionUpdate | `varint dir x, varint dir y, varint cell x, varint cell y, bool`. Direction: the `0x63` vector verbatim while walking, **scaled to length 550 and truncated toward zero while sprinting** (`v × 550 / |v|`: `(0,-550)`, `(388,-388)`, `(94,-153)` → `(287,-468)`, not `(287,-467)`; `(-53,172)` → `(-161,525)`; matches 294 of 309 replies, the others answer the previous input; `×550/180` fits only 72). The cell is the server's player cell. The bool is `0xf1` (true) in 94 % of the replies, `0` otherwise (every 31st frame of a sprint stream, otherwise sporadic); the client ignores it. |
| `0x1c8` | StartAction | `u16 flags (0x80 = entity follows), [u32 entity], varint cell x/y (start), varint target x/y (absolute), u32 skill, u16 action id, u8 0xff`. **Flags = the `0x1a5` flags \| `0x10` for a start an input caused** (roll/attack `0x410`, `0x450` in click-to-move mode, Move press `0x410`, held repeat `0x10`); a restart the server issues itself (held click every ~15 frames, walk resumed after a roll) carries the last request's flags without `0x10`, header `(player, 9, 1)`/`(0, 8)`. Action ids are one **server-wide counter** (32768+, e.g. 32872 → 32875 → 32877 across all entities). |
| `0x1ae` | UseSkillAck | the skill block with **absolute** x/y and `target flags \| 0x04` ([skill.rs](../../modules/protocol/poe-proto/src/skill.rs)). |
| `0x1af` | UpdateSkillTargetAck | `i32 x, i32 y, u32 skill`: absolute target = server player cell + the relative offset of the `0x1a8`. |
| `0x1b0` | UpdateSkillTargetEntityAck | `u32 entity, i32 x, i32 y (the entity's cell), u32 skill`. |
| `0x1b1` | SkillInputEndAck | no body. |
| `0x1b2` | SkillReleasedAck | `u32 skill, u8` (header `u1a` = 6). A release of the roll key (`0x1ad` roll skill) is answered by `0x1b1` **and** `0x1b2`, then `0x2e7`. |
| `0x2e7` | SprintState | `u8 held`. Echo of `0x2e6` (sets Actor +0x2a2 bit 5). |
| `0x1d3` | StatsUpdate | `u8 set, varuint n, n × (varuint key, varint value)`. |
| `0x1eb` / `0x1ec` | BuffAdded / BuffRemoved | `u16 index, u16 buff row, …` / `u16 index` (see [skill.rs](../../modules/protocol/poe-proto/src/skill.rs)). |
| `0x1ca` | (action event) | no body; with every roll start and when an attack ends a sprint. Actor case `0x14214a2be` decrements a counter (+0x348). |
| `0x1dc` | SetAimTarget | `u8 kind (0 cell, 1 entity), i32 x, i32 y`, header `(player, 0, 0, 0)`. |
| `0x2f9` | ComponentDelta | player stance and flags (component 6). |
| `0x2a6` | (orientation lerp) | read by the `0x1df` reader: `f32, u8` after the header; `0.05` at entry and when the stance goes to combat, `0.2` when it goes to 0; always with a stance delta. |

Reader addresses: `0x1ae` `0x142186980` = sim header + `SkillUseParams_Read` (`0x141ecdf80`), `0x1af` `0x141f6d6a0` (3 × u32), `0x1b0` `0x142186a60` (4 × u32), `0x1b1` header only, `0x1ac` sender `0x14210fec0` (one `u8`), `0x1b2` (`u32, u8`). All decode every captured instance with zero leftover bytes ([Reproducing](#reproducing)).

### Request/reply pairs
Every client skill message has exactly one reply (equal counts: 1a5:1ae, 1a8:1af, 1ac:1b1, 1aa:1b0, 1ad:1b2, 2e6:2e7; also `0x63`:`0x64`, `0x62` mode 2:`0x1dc` when echoed, `0x200`+`0x62` mode 0/1:`0x2a6`+`0x2f9`). Offsets: `f+1` ~93-98 %, `f+0` ~6 %, `f+2` <1 %. A Move press or held repeat gets `0x1c8` + `0x1ae` in one batch; a `0x1ad` gets `0x1b2` (and `0x1b1` for the roll key) at `f+1` in 12 of 13 cases.

### Opcodes official servers never send for movement
Over 6 sessions (~35 000 simulation messages): **`0x1cb` UpdateActionTarget: 0, `0x1df` SetOrientation: 0**. Steering is done with `0x1af`, facing with `0x1dc`. (Our server must not use `0x1cb`, `0x1df` or a `0x64` toward the cursor for held clicks.) Also absent: any server `0x63`-like position-only message, `0x65`, `0x1a9` (absolute target update).

## State machine

States of the local player's movement on the server: `Idle`, `Walking(v)`, `Rolling`, `Sprinting(v)`. `v` is the last `0x63` vector (its `(0,0)` is `Idle`). `r+k` columns are batches relative to the first reply batch `r+0`. `t0` is the roll's start batch.

| From | Event (C→S) | To | Reply |
|---|---|---|---|
| Idle / Walking | `0x63 v≠0` | Walking(v) | `r+0`: `0x64 v, cell` |
| Walking(v) | `0x63 v'≠0` | Walking(v') | `r+0`: `0x64 v', cell` (also while Rolling) |
| Walking(v) | `0x63 (0,0)` | Idle | `r+0`: `0x64 (0,0), cell` |
| Idle / Walking | `0x2e6 held=1` + `0x1a5 roll` | Rolling | `r+0`: roll batch (below) |
| Rolling | `0x1a8` (every 2 frames) | Rolling | `r+0`: `0x1af`, once per `0x1a8` |
| Rolling | `0x63 v` | Rolling | `r+0`: `0x64 v, cell`. A roll along the WASD keys **turns with the new vector** (2 frames after the `0x63`, [roll direction](#roll-direction)); walking resumes when the roll ends |
| Rolling, key released up to `t0+14` | `0x1ac` + `0x2e6 held=0` (click-to-move mode: `0x1ad` roll + `0x2e6`) | Rolling → Walking/Idle at `t0+30` ([roll action](#roll-action-length)) | `r+0`: `0x1b1` (+`0x1b2`), `0x2e7 held=0`; `t0+16`: roll-end stats |
| Rolling, key still down at `t0+15` (released from `t0+19` on: sprint anyway) | (nothing) | Sprinting | `t0+15`: sprint start; `t0+30`: roll end; `t0+35`: `must_sprint=0` (and the sprint end, if the key went up before) |
| Rolling | `0x1a5` roll, 0.3-0.9 s after the previous start | Rolling | `r+0`: `0x2e7`, `0x1ae`; the new roll starts at `t0+30` ([chained rolls](#roll-action-length)) |
| Rolling | `0x1a5` attack | attack at `t0+24` / `t0+35` | `r+0`: `0x1ae` only; see [roll action](#roll-action-length) |
| Idle / Walking | `0x1a5` Move press (click) | Walking(target) | `r+0`: `0x1c8` Move (flags `0x410`), `0x1ae`; release `0x1ad` → `0x1b2` |
| Walking(target), click held | `0x1a5` Move, target flags `0x10`, every 2 frames | Walking(new target) | `r+0`: `0x1c8` Move (flags `0x10`), `0x1ae`; every ~15 frames a server `0x1c8` restart |
| Sprinting | `0x63 v` | Sprinting(v) | from the first `0x63` after sprint start: a `0x64` **every frame**, direction scaled to length 550 (no `0x63` after the sprint start: no stream, the client walks on by itself) |
| Sprinting | `0x1ac` + `0x2e6 held=0` | Walking(v) | `r+0`: `0x1b1`, `0x2e7 held=0`, `0x64`, sprint-off buffs/stats; `r+1`: `0x64 v` unscaled |
| Sprinting | the player is blocked by a wall | Walking, blocked | same frame as the stall: sprint-off (first half), `r+1`: `0x64` unscaled, `+7..8`: second half ([end of sprint](#end-of-sprint)) |
| Sprinting | `0x1a5` attack | Attack | sprint-off stats + `0x1c8` attack; `0x2e7 held=0` follows when the key goes up |

### Roll batch (`r+0`), identical in all 45 rolls
Order of the reply to `0x2e6 held=1` + `0x1a5 {roll}` (client sends both in the same frame, `0x2e6` first):

1. `0x2e7` SprintState `held=1`
2. `0x1c8` StartAction: `skill 0x80000040`, flags `0x410`, start cell = server player cell, target = cell + the relative cursor offset, `action id`, `0xff`; header `(player,0,0,0)`
3. `0x1ca` header only, `u1a=9`
4. `0x1d3` `is_dodge_rolling=1`, `u1a=9`
5. `0x1ae` UseSkillAck, `u1a=10`, target flags `0x04`, absolute cell = start cell + offset
6. `0x1d3` `stun_threshold_+%_final_while_performing_action=100, virtual_heavy_stun_threshold_+%_final=100, virtual_light_stun_threshold_+%_final=100`, header `(player,player,5,6)`

An earlier unanswered `0x1a8` is answered first (`0x1af` before this batch's messages). The batch is the same **standing** (no WASD key; 24 of the 30 rolls of the 2026-10-20 session, 16 of them taps) and in click-to-move mode (`0x1a5` flags `0x440`, `0x1c8` flags `0x450`).

**Deferred start.** Three cases have `0x2e7`/`0x1ae` in `r+0` and the `0x1c8`, `0x1ca` and stats in a later batch with scheduled headers `(player,player,5,8)`, `(…,5,17)`, `(…,5,25)` (`0x1c8` `u1a` 8): (a) the press and its release arrive in one batch (inputs queued while the game was paused: `0x2e6` 1, `0x1a5`, `0x1ac`, `0x2e6` 0 in one frame; then `r+0` is `0x2e7` 1, `0x1ae`, `0x1b1`, `0x2e7` 0 and the roll starts at `r+1`); (b)/(c) a roll asked for while the previous roll's action still runs ([chained rolls](#roll-action-length)).

### Roll end and sprint (timeline in frames after the roll's `0x1c8`, `t0`)
The offsets are constant (server logic, not latency); measured in all 45 rolls. `k` is the client frame the key-up was sent in (the reply is in `k+1`):

| Frame | Tap (key released up to `t0+14`; 24 rolls) | Hold (key still down at `t0+15`; 21 sprints) |
|---|---|---|
| `t0+0` | roll batch | roll batch |
| key release (`k`) | `0x1b1`, `0x2e7 held=0` | (see end of sprint) |
| `t0+15` | – | `0x1eb` ×3 (indices n, n+1, n+2; buff rows 2758 `0xac6`, 2737 `0xab1`, 2853 `0xb25`, flags 0) and `0x1d3` `sprint_blend_time_override_ms=1, is_sprinting=1, must_sprint=1, all_hits_stun_you=1, virtual_skill_ignore_namelocking_dynamically=1`, header `(player,player,5,2)` |
| `t0+16` | `0x1d3` stun thresholds 0 + `is_dodge_rolling=0` (roll over) | – |
| `t0+30` | – | `0x1d3` stun thresholds 0 + `is_dodge_rolling=0`; `0x1d3` `base_move_speed_+%_from_sprint=50, movement_velocity_+permyriad=5000`; `0x1eb` ×2 (buff index n+1 `0xab1` again and n `0xac6` with flags `0x02` = f32 `0.1`) |
| `t0+35` | – | `0x1ec` buff index n; `0x1d3` `must_sprint=0`, header `(player,player,3,0)` |

So **`is_dodge_rolling` is cleared 16 frames (533 ms) after the roll on a tap and 30 frames (1 s) when Space is still down at frame 15**, and the sprint begins at frame 15 while the roll is still running.

**The boundary** (30 rolls): releases at `t0+2..t0+14` (the longest taps, 500-549 ms) never sprint; releases from `t0+19` (667 ms and longer) always sprint (`t0+15` stats, roll stats at `t0+30`); `t0+15..t0+18` was not hit ([gap list](#gap-list)). The server decides by "key still held when the `t0+15` batch is built" (a release sent in client frame `t0+14` arrives for that batch). **A release between `t0+15` and `t0+34` does not end the sprint** (seen at `t0+19`, click-to-move mode): it is answered at once (`0x1b1`, `0x1b2`, `0x2e7 held=0`), the scaled `0x64` stream goes on, and the `t0+35` batch holds `0x1ec n`, `must_sprint=0`, the `0x64`, (held click: a `0x1c8` Move, flags 0), then the sprint-off events `0x1ec n+1`, sprint stats 0, `0x1ec n+2`, `all_hits_stun_you=0` (headers `(9,10)`). The sprint is over at `t0+35` at the earliest.

### Roll action length
The roll *action* lasts **30 frames in both cases** (client log `action start/end slot 0: DodgeRoll` exactly 30 frames apart in 23 of 30 rolls; 24 when an attack cut it (3), 31 (2), 57 across a pause (1)). After a tap roll's stats at `t0+16` the server still treats the player as rolling until `t0+30`:
- **Aim is not echoed** (`0x62` → `0x1dc`) for aims up to `t0+26` at least; the `0x1a8`/`0x1af` pairs go on.
- **A new roll waits.** Inputs `g` frames after the previous start `P`: `g=9` (key released again at `P+14`): acked (`0x2e7`, `0x1ae` in `r+0`), **no start at all**; `g=27/28`: acked at `r+0`, started at `P+30` with the scheduled headers; `g=29` (previous start itself late): started at `r+1 = P+31`; `g=31..34`: started at once (`r+0`, normal headers). Rule: a roll asked for while `r+0 <= P+30` starts at `max(r+0+1, P+30)`. Undecided: whether the dropped `g=9` press was dropped because its key was up when the lock ended or because the later press (`g=28`) replaced it (single slot, last wins).
- **An attack waits for the roll** (3 tap rolls): `0x1ae` at `r+0` for every attack press (repeats too, target flags `0x14`/`0x0c`), no `0x1c8`. The **last** attack's `0x1c8` (target = that press' cursor cell, `0x1ca` `u1a` 7) comes at **`t0+24`** and cuts the roll (the client's DodgeRoll action ends there). If Space is still held at `t0+15` the attack starts with the sprint's end at `t0+35`: `0x1ec n`, `must_sprint=0`, the scaled `0x64`, the attack `0x1c8` (flags `0x10` when the last press was a held repeat), `0x1ec n+1`, sprint-off stats, `0x1ca`, `0x1ec n+2`, `all_hits_stun_you=0`, no second `0x1ae`. The `0x1c8` target of an attack on a hovered monster (target flags `0x08`) is the monster's current cell, not the press' coordinates.
- **Click-to-move repeats** (`0x1a5` Move, target flags `0x10`) during a roll or sprint are acked (`0x1ae`) and nothing starts; the held click's walk resumes at the end of the roll with a server `0x1c8` Move (flags = last request's, header `(0,8)`) towards the latest target (`t0+30`).
- Our roll covers its 46 cells in the same number of frames, see [Roll path and speed profile](#roll-path-and-speed-profile).

### Roll direction
**The client rolls along the WASD vector when a movement key is held, and towards the cursor when none is** (30 rolls): 5 of 6 rolls with a key held went along the key vector (within 3 degrees) although the `0x1c8` target pointed 16-156 degrees elsewhere (the sixth was against a wall); the 24 standing rolls went towards the cursor. The `0x1c8` target is the cursor either way (`cell + offset of the 0x1a5`) and is ignored when a key is held.
- **Held keys**: the direction is the key vector at any time of the roll: `0x63` sent in the roll (client frame `t0+11`, `(127,-127)` → `(180,0)`) is answered at once with a walking `0x64` and the roll **turns 2 frames after the `0x63`** (`t0+13`; the `0x64` is `f+1`, the step with the new direction `f+2`), and turns back after the next one (`t0+26` → `t0+28`). The roll distance stays 46 cells.
- **Standing**: the first 3 frames go in about the client's facing/cursor direction (within 5-15 degrees); from the first `0x1af` (sent at `t0+3`, applied at `t0+4`) the roll follows the `0x1a8` offsets (`0x1af` = server cell + offset) with a lag of 2 frames (offset sent in frame `f` shows in the step of `f+2`), turning in steps every 2 frames. Our server (offset at the press, re-aimed by each `0x1a8` handled at r+0, moving from the next tick) has the same lag.
- **Blocked**: a roll along a wall slides (SW roll against a wall at 109 degrees instead of 135).
- Not captured: a key pressed during a roll that started standing, a key released during a roll along the keys.

**Heading source** (`DodgeRoll_InitHeading` `0x141b8bda0`, from `DodgeRoll_OnStart` `0x141aa8500`): the roll's angle (action `+0x40`) is the held input vector when the client holds an input axis (Actor `+0x400`/`+0x404`, action "use input" flag `+0x5e`); otherwise the direction from the entity to the action's target (the `0x1c8` target, re-aimed by every `0x1af`); the entity's facing (Positioned `+0x44c`) when the target is its own cell. The server: WASD vector, else cursor offset, else the last direction it moved or aimed in (`Locomotion::facing`).

**Against the client's positions:** in click-to-move and clean standing rolls the first steps deviate from the direction to the target by -11 to +10 degrees for 2 to 3 frames (`-45` exactly in the standing roll at f517: a diagonal first leg from the client's path planning of the 46-cell destination), then follow the `0x1a8` offsets with the 2-frame lag. The server stays within **3.5 cells of the client over the whole roll** in the replay tests (worst 2.5, 0.7, 2.0, 2.9; fixtures `click_mode_roll_south`, `click_mode_roll_east`, `click_mode_roll_west`, `standing_tap_roll`).

### Roll path and speed profile
Client steps per frame from `poe-hook.log` (cells per 33 ms frame, 30 rolls, `dt` 0.033 in every frame; the 6 standing rolls on open ground, mean; the first step is in frame `t0+1`, one frame after the `0x1c8`):

| `t0+` | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| step | 3.89 | 3.74 | 3.45 | 3.27 | 3.02 | 2.72 | 2.54 | 2.30 | 1.98 | 1.76 | 1.59 | 1.35 | 1.23 | 1.16 | 1.06 |

| `t0+` | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| step | 0.99 | 0.97 | 0.94 | 0.94 | 0.94 | 0.94 | 0.95 | 0.93 | 0.85 | 0.74 | 0.68 | 0.49 | 0.31 | 0.16 | 0.04 | 0 |

- It falls about **0.215 per frame from 3.9 to 1.2 (t0+13), levels out at 0.94 until `t0+23` and tapers to zero by `t0+31`**. Sum 45.9: the roll covers `dodge_roll_travel_distance` (46 cells) in 30 frames (36 cells in the first 16, 34 in 14); straight-line displacement 42.6-46.2 (the cursor steering bends the path).
- Walking resumes at `t0+30` (tap) with the walking speed 1.23 (WASD) or stands (no key): the standing roll ends **without any `0x64`**; the next message is the next input's reply. A held-key roll's `0x64`s are only the replies to `0x63`.
- **Positions agree**: the `0x1c8` start cell is within 0.2-2.9 cells of the client's position before the first roll step, and 600 `0x64` cells (also after rolls) within 0-2.8 (median 0): the official server simulates the same roll path. A roll along the keys that our server simulated towards the cursor made the client jump 36 cells at the next roll's `0x1c8` (the roll start places the client on its start cell), and the drift never recovered.
- `modules/server/crates/poe-game/src/movement.rs` plays the table frame by frame (`ROLL_STEPS`, 30 values, sum 45.9; `roll_speed(t, sprint)`). A blocked step costs no distance and does not end the roll (the client's roll runs its 30 frames against a wall too).
- **A roll that becomes a sprint (key still down at `t0+15`) does not taper**: the 7 sprint rolls step 0.91, 0.96, 1.02, 1.08, 1.09, 1.11, 1.20, 1.34, 1.36, 1.46, 1.49, 1.52, 1.54, 1.70 in `t0+16..t0+29` and about 2.4 in `t0+30`, then sprint at 1.86 (`ROLL_SPRINT_STEPS`, `Mover::sprint_roll`). The tap table would leave the server about 10 cells behind.

### End of sprint
`r+0` batch: `0x1b1`, `0x2e7 held=0`, `0x64` (still scaled), then `0x1ec` (index n+1), `0x1d3` `base_move_speed_+%_from_sprint=0, movement_velocity_+permyriad=0, sprint_blend_time_override_ms=0, is_sprinting=0, virtual_skill_ignore_namelocking_dynamically=0`, `0x1ec` (index n+2), `0x1d3` `all_hits_stun_you=0` (headers `(player,player,9,7)`); `r+1`: `0x64` with the **unscaled** vector. The `0x64` comes after the other replies of its frame (input replies, timeline events): in the key-release case the sprint-off events follow it; in the roll/sprint timeline frames (`t0+30`, `t0+35`) the timeline events come first and the stream message last.

If the player used an attack (`0x1a5` `0x80400040`) while sprinting, the attack ends the sprint (key release and attack in one frame): `0x1a8` ack, `0x1b1`, `0x2e7 held=0`, `0x1ec`, `0x1d3 must_sprint=0`, the attack's `0x1c8`, `0x1ec n+1`, sprint-off stats, `0x1ca`, attack `0x1ae`, **`0x64` unscaled** at `r+0`, `0x1ec n+2`, `0x1d3 all_hits_stun_you=0`; the key release (`0x1ac`+`0x2e6 held=0`) then gets `0x1b1`/`0x2e7 held=0` with no stats. Sprint end causes over 21 sprints: key up 10, attack 8, wall 3, held-click Move 0.

- **Wall**: the server stops the sprint in the batch where its own cell stops advancing (3 of 3): `0x1ec n+1` and the sprint-off stats (headers `(0,4)` or `(9,6)`) in that batch, the **unscaled** `0x64` one frame later (none when no stream had started), and `0x1ec n+2` + `all_hits_stun_you=0` (header `(3,0)`) **7-8 frames after** the first half. The client's step in that frame is partial (0.28, 0.86 of 1.86). The sprint does not restart while the key stays down; the key release then gets `0x1b1`, `0x2e7 held=0` and, if WASD was released, the `0x64 (0,0)`.
- **Key up before `t0+35`**: ends at `t0+35` ([the boundary](#roll-end-and-sprint-timeline-in-frames-after-the-rolls-0x1c8-t0)).
- **An attack asked for during the roll**: ends it at `t0+35` ([roll action](#roll-action-length)).

### Coasting after a sprint
What the client does when a sprint ends, from its own per-frame positions (`poe-hook.log`) in the official capture and in six sessions of ours:
- **The client's Move action ends with the sprint-off batch** (`action end slot 1: Move`) **but the entity does not stop**: it keeps moving along its last direction for **30 frames, about 20 cells, the step falling linearly** `1.309 - 0.0444 n` cells per frame, n = 0..29 (zero at n 29.5; walking is 1.233; residual under 0.02, sum 19.95). Official ends at f1795 and f4585 fit it. A plain walk stop has no such tail (step 1.23 and stop), nor does a wall.
- **Timing**: the batch's own frame still has the sprint step, the next one none, the first coasting step is two frames after the batch (f4585: 1.85, none, 1.31).
- **The official server simulates it**: after the `0x64 (0,0)` at f1797 (cell 439,993) its next position message, f1883, has (449,979), where the client's coast ended.
- **A held key restarts the walk, and only the unscaled `0x64` does it**: f2394 `0x64 (127,-127)` → client `action start slot 1: Move` at f2395, first step f2396 (a Move start steps 1.23 from its first frame). `Actor_StartWasdWalk` (`0x141e4fb40`) only starts while the client holds an input axis (Actor `+0x400`/`+0x404` not both 0), so with the keys already up (the client sends the `(0, 0)` vector 2 frames after the Space release) the `0x64` restarts nothing and the coast runs out. **Caveat (in game):** with W held since before the roll (no `0x63` after the sprint start) the unscaled `0x64` did not restart the walk either: the client coasted 30 frames and resumed by itself ([problem 5](#test-tooling)).
- With W held since before the roll there is no stream; a server that walks on at 1.23 drifts 10 to 13 cells. After a cursor sprint released with Space only, a server that stops at the `(0, 0)` is 17 cells off the client's coast.
- **Not the coast:** after an attack at f2393 the restarted walk is slowed by the [action speed factor](#speeds).
- **The coast itself has no constant in the client we found**: the speed getter (`Pathfinding_GetSpeed`, stats `0xec`, `0xc39`, `0x44a`) drops from 1.5x to 1.0x at once when `movement_velocity_+permyriad` goes 5000 → 0, and the Move action that would apply a speed ramp is over. The numbers (1.309, 0.0444, 30 frames) are measured and live in config (`[movement] sprint_coast_*`).

Server model (`Locomotion::end_sprint`, `Motion::Coast`):
- **Key held** (`wasd` not zero; **wrong for the no-stream case**, problem 5): the unscaled `MoveAck` goes out at r+1 whether or not a stream ran, and the walk resumes after `sprint_restart_delay_frames` (2: Move start 2 frames after the batch, first step one later).
- **No key** (`wasd` zero): the entity coasts: `Motion::Coast`, `sprint_coast_delay_frames` (1) frames after the batch the first step `sprint_coast_start_scale` (1.0614) x `walk_speed / 30` (1.309), falling by that over `sprint_coast_frames` (29.5), along the last direction. A zero vector does not stop a coast; a new vector walks on at once.
- **Cursor sprint** (Space only, no key down): the keys are already up when the unscaled `MoveAck` arrives, so a `(0, 0)` up to `sprint_release_window_frames` (6) after the sprint-off batch turns the restart into the coast from the step the client is at. Cursor vectors (`Locomotion::is_cursor_vector`): a free angle, or a key-shaped vector (axis or exact diagonal, W is `(127, 127)`) that the roll key's cursor offset (`0x1a5`/`0x1a8` target, every 2 frames while Space is down) points along within `sprint_cursor_match_degrees` (10). Any other key vector is a real key: its release stops at once. **Click-to-move mode has no keys** (`MoveInput::CursorDirection`): the sprint coasts at the sprint-off batch without waiting for the `(0, 0)`, and cursor vectors in flight are ignored for the release window. When the client's `(0, 0)` arrives in the frame the unscaled `MoveAck` is due, that ack still goes first (a `(0, 0)` in its place stopped the client's coast). Open: W pressed during the sprint with the cursor within 10 degrees of W is taken for the cursor (rare); a key released within the window of the Space release is modelled as the cursor case, not verified with real timing.
- Tests: `locomotion.rs` unit tests (`a_sprint_ended_with_a_key_held_is_restarted_by_the_unscaled_ack`, `a_sprint_ended_after_the_cursor_direction_coasts_to_a_stop`, `a_zero_vector_while_coasting_does_not_cut_it_short`, `a_new_direction_during_the_coast_walks_on_at_walking_speed`, `a_key_released_just_after_the_sprint_stops_at_once`, `a_click_mode_sprint_on_an_exact_diagonal_coasts_whenever_the_zero_comes`, `a_click_mode_sprint_ignores_cursor_vectors_in_flight`, `a_new_click_mode_vector_long_after_the_sprint_walks_on`, `the_unscaled_ack_still_comes_first_when_the_zero_arrives_in_the_same_frame`, `an_exact_diagonal_vector_along_the_cursor_is_a_cursor_sprint_in_wasd_mode_too`, `the_same_vector_with_the_cursor_elsewhere_is_a_key_and_stops_at_once`, `a_free_angle_zero_four_to_five_frames_after_the_sprint_off_still_coasts`), fixture `sprint_wasd_released_then_space_up` with the client's positions (`replay.rs`: within 3 cells from the sprint-off frame on, 2.6 at worst), `instance-server` `a_sprint_without_a_stream_ends_with_the_unscaled_direction`.
- **Not captured**: the official answer to a sprint without a stream ended by key-up with W still held.

### Sprint stream
From the **reply to the first `0x63` after the sprint started** until the sprint ends, the server sends **one `0x64` per frame** with the current direction scaled to length 550 and the server's cell, advancing 1.83..1.89 cells per frame (client 1.85-1.88). A new `0x63` changes the vector in the next frame's `0x64` (`(127,-127)` → `(388,-388)`, `(0,-180)` → `(0,-550)`). **Without a `0x63` after the sprint started there is no stream** (WASD held since before the roll: no `0x64` at all; the client walks on by itself). With Space held and **no** key the client sends the cursor direction as `0x63` every frame it changes and the stream follows it; releasing all keys while Space stays down sends a cursor vector, not `(0,0)`. The bool of the stream's `0x64` is `0` every 31st frame.

## Scenario sequences

`movement_sequences.py scen --scenario <name>` prints them per session.

### WASD start / turn / stop
- Every `0x63` has exactly one `0x64` in ~1000 direction inputs. **Start/turn**: `f: 0x63 v` → `f+1: 0x64 v` with the player's cell (e.g. `0x63 (-127,-127)` at f856 → `0x64 (-127,-127) cell (284,1141)` at f857). **Stop**: `0x63 (0,0)` → `0x64 (0,0) cell`.
- No other message accompanies WASD (the stance delta comes at entry, [Stance](#input-mode-and-stance)). The reply cell moves ~1.23 cells per frame; the client turns when it receives `0x64` and puts the entity on the centre of the cell it is given, so the server sends its own simulated cell and never corrects the client. While rolling the server still answers each `0x63` at once with a walking `0x64` (a roll along the keys turns with it, [roll direction](#roll-direction)). With Space down and no key the client sends the cursor direction ([sprint stream](#sprint-stream)).

### Click-to-move
2026-10-20 session (click-to-move mode `f3287-4662`): 12 presses (6 single clicks of 2 frames, 6 holds of 0.2-16 s), 356 held repeats. Fixtures `click_single`, `click_held_reaim`.
- **Press** (`0x1a5` Move `0x20002909`, flags `0x400`, target flags 0, `x,y` = cursor relative to the player's cell): in `r+0`: `0x1c8` StartAction Move, **flags `0x410`**, start = the server's cell, target = cell + offset, header `(player,0,0,0)`, new action id; then `0x1ae` (flags `0x400` echoed, target flags `0x04`, absolute target = the `0x1c8` target; header `u1a` 3, 4 for the first press after a pause or at entry). No `0x64`, `0x1af`, stats or `0x2f9`. The client walks to the target at 1.23 cells per frame from the `0x1c8`'s frame (dip to 1.08 about every 11 frames) along its own path.
- **Release** (`0x1ad`, skill, 0): `0x1b2 (skill, 0)` one batch after (`f+1`, 12 of 13). Single clicks: the release follows the press by 1-2 frames and the walk goes on (a click's walk is not stopped by its release).
- **Held click**: while the button is down the client sends `0x1a5` Move with **target flags `0x10`**, flags 0, the current cursor offset, **every 2 frames** (never `0x1a8` for Move). Every repeat gets `0x1c8` Move (**flags `0x10`**, start = the server's cell, target = the new cursor cell, new action id) + `0x1ae` (flags 0, target flags `0x14`, absolute target) in the next batch: a repeat re-aims by starting a new action. Additionally the server sends a `0x1c8` Move **about every 15 frames** with the latest request's flags without `0x10` (`0x400` right after the press, else 0), header `u18=9, u1a=1`, target = the previous target (first one 2 frames after the press in hold 1, 6 in hold 2; trigger unknown).
- **Arrival**: no message at all (the client's Move action ends by itself); no walk reached its target in the session (every walk was interrupted by the next click within 17-35 frames).
- **Roll, sprint or stun during a hold**: the repeats are acked (`0x1ae`) and nothing else; the walk resumes with a server `0x1c8` Move at the end of the roll (header `(0,8)`, flags of the last request) or, after a sprint that ended at `t0+35`, in the sprint-off batch. Not every repeat after that gets a `0x1c8` (the one right after a sprint's end got only the ack).
- **Holds end without a release**: 5 of the 6 holds had no `0x1ad` (rolls, attacks or stuns in between); the repeats just stop (hold 2: press f3527, last repeat f4002). A server must treat a hold that is quiet for 6 frames as over.
- Not captured as such: WASD while a click walks, click while rolling, click on a wall.
- The mouse-mode client sends **no `0x62` aims at all** (0 in `f3300-4600`), so no `0x1dc` echoes; roll and sprint messages are as in WASD mode, with `0x1a5` flags `0x440` and `0x1c8` flags `0x450` for the roll.
- The intro click (skill `0x20002909` with `u16 flags` = the player's entity id, every earlier session) is different: `0x1a5` + `0x1ad` in one frame → the four `0x1d8` skill stats containers + `0x1d3` (skill-list bootstrap), `0x1c8` StartAction **skill `0x2000b7d9` (wake-up)**, `0x1ae`, and `0x1b2` in the next batch.

### Sprint
Hold Space after the roll: the sequences above. `0x2e6` is sent once on down and once on up. Held Space continues the `0x1a8`/`0x1af` pairs every 2 frames; in click-to-move mode a sprint hold sends cursor-direction `0x63` every frame (trailer byte 1), held-click repeats go on (acked) and the `0x64` stream is as in WASD mode. `0x62` aims are not echoed while sprinting (116/116) or rolling (150/150). Not captured: Space re-pressed while sprinting, the roll key re-pressed within 0.2 s.

### Input mode and stance
`0x2f9` ComponentDelta, component 6 (Player), mask `0x0400` = stance byte, `0x1000` = a second byte that echoes a request value. Stance changes in the captures:
- **At entry**: 2026-10-15/17: `f10: mask 0x0400, stance=1` (9 frames after the client's first `0x62` mode 1); 2026-10-14: `f10: mask 0x0402` (flag words, stance=1), `f11: mask 0x1400 (stance=0, +0x3e7=1)`; 2026-10-20: `f15: mask 0x0400, stance=1` (14 frames after the `0x62` mode 1 at f1) and a `0x2a6` with `0.05`.
- **Input-mode toggle** (2 of 2, standing; fixtures `stance_to_mouse_mode`, `stance_to_combat_mode`): the client sends **`0x200 {player, value}` and `0x62` mode 0 or 1 in the same frame** (WASD → click-to-move: value 1, mode 0; back: value 4, mode 1) and the server answers in `r+0` with `0x2a6` (`f32` 0.2 for value 1, 0.05 for value 4) and a `0x2f9` of mask `0x1400`: **stance byte 0 / 1** and the second byte = the value (`00 01`, `01 04`). `0x62` aims are sent only in combat stance and WASD mode.
- Not captured: a change while walking, rolling or sprinting, the weapon swap. Seen but unidentified: `C>S 0xfe {1, 1|0}` at f2573/f2620 (47 frames apart, standing) answered by `S>C 0x1d5` + `0xff`.
- Other Player deltas: `mask 0x0402/0x0002` flag words after the first skill release and new areas, `mask 0x0201` experience after kills, `mask 0x2000 (00)` on level-ups.

### Aim
- C→S `0x62` mode 2 with the **absolute** cell under the cursor, at most one per frame, about every frame while the mouse moves; none in click-to-move mode. S→C `0x1dc` kind 0 with the same cell, header `(player,0,0,0)`, at `f+1` (94 %). Not every input is echoed: **never while rolling or sprinting**, mostly not while an attack runs (204/237), 0.5 % of idle/walking inputs.
- Mode 3 (entity, hovered) is sent often but only 11 `0x1dc` with kind 1 exist: not echoed one-to-one. Facing is entirely a `0x1dc` effect; there is no `0x1df`.

### Stun
One light stun (f4072, a monster hit the player while attacking): `0x1d3` `is_light_stunned=1, is_immobilised=1` (header `(7,11)`), `0x1eb` buff row 2404 (flag `0x02`), `0x1d3 on_full_energy_shield=0` (`(7,14)`); 7 frames later `0x1d3 number_of_times_stunned_in_past_duration_from_ot=1` and `virtual_light_stun_threshold_+%_final=50`; **15 frames after the start the stats go back** (`is_light_stunned=0, is_immobilised=0`, header `(5,1)`) and the attack asked for meanwhile starts (`0x1c8` flags `0x410`, header `(5,2)`, `0x1ca`). Attacks and Move presses during the stun get their `0x1ae` only; the server cell stays put. Knockback (`0x1e0`) and stuns while walking or rolling: not captured.

## Capture index: 2026-10-20 session
`dumps/0.5.5e.hotfix1/captures/official/2026-10-20_18-41-14_336/` (13 299 instance messages, 4 765 frames, 33 min; `check_capture`: every movement message decodes with 0 errors and 0 leftover bytes; only `AddInventory` items mismatch). Frame = capture frame, `T` = tap, `H` = hold, the number is the frames Space was down:

| Item | What is there |
|---|---|
| 1 standing roll, 5 taps + hold | f516 T7, f560 T8, f606 T5, f652 T3, f696 T3, f744 T4; hold f1132 H125 (sprint, cursor-follow stream, wall f1243, Space up f1257) |
| 2 taps 0.1/0.3/0.45/0.5 s | mostly **standing** (the keys were up): T3 (f652, f696, f3645, f3679), T4-8 (f516-f745, f1477, f1514, f1581, f1600, f1633), walking: T7 (f2458), T8 (f2065), T12 (f1934); T14 (f1572, f4178). No 9-frame (0.3 s) tap, 15-18 not hit |
| 3 chained re-press | f1476/1514 (38 apart), then after a pause f1570 (press+release in one frame), f1581 (+9), f1600 (+28), f1633 (+31); f3607 H20, f3645 T3 (+38), f3679 T3 (+34), f3711 T5 (+31), f3742 H155 (+29); no re-press while sprinting |
| 4 stop all WASD during sprint / roll | f1793-1796: keys released with Space down (cursor vector, then Space up, `(0,0)`); no `(0,0)` during a roll or sprint |
| 5 attack while rolling; Esc during a sprint | attacks in the roll at f1946, 1991, 2075-2088, 4033; Esc (`SetPause`) f1543-1570, 1844-1852, 3224-3238, 4612-4628, never during a roll or sprint |
| 6 weapon swap | not found (`0xfe` f2573/2620, `0x200` f3286/4662 are input mode) |
| 7 sprint into wall / monsters | wall: f1243, f1918, f2873; monsters: sprints ended by attacks f2393, 4056, 4142, 4262 |
| 8 roll with monster hovered; get hit | no `0x1aa`/`0x1b0`; one light stun f4072 |
| 9 click-to-move | hold f3325 (41 frames), singles f3375, 3410, 3441, 3473, 3492, 3509, hold f3527-4002 with rolls, f4069/4100/4160/4462 holds with attacks and rolls |
| 10 held click + Space | inside holds: f3607 H20 (sprint cut short, ends f3643), f3645 T3, f3679 T3, f3711 T5, f3742 H155 (sprint 3759-3897); f4105 H52, f4178 T14, f4216 H64 (holds f4100-4259); f4484 H100 (hold f4462-4583) |

## Reproducing
```
python3 scripts/re/movement_sequences.py never                                  # opcodes never sent
python3 scripts/re/movement_sequences.py scen --scenario wasd roll sprint stance aim [--max N] [--verbose]
python3 scripts/re/movement_sequences.py events <session> --from 2470 --to 2660 [--aim] [--all]
python3 scripts/re/movement_sequences.py list
cd modules/protocol && cargo run -p poe-proto --example check_capture -- opcodes/0.5.5e.hotfix1 <packets.jsonl>
python3 scripts/re/movement_fixtures.py build        # rewrites modules/server/crates/poe-game/tests/fixtures/*.json from PRESETS
cargo test -p poe-game --test replay                 # replays them through the World
```
The script's decoders match `poe-proto`'s (`skill.rs` has round-trip tests built from capture bytes). It needs no dependencies; stat and action names come from `GameFiles/poe-hook-data/` (written by `cargo xtask dll-data`) when present.

## Server implementation
The instance server is thin glue around the `poe-game` World (design: [instance-world.md](../architecture/instance-world.md)):

- **Input.** `modules/server/servers/instance-server/src/movement.rs` `client_input` maps a client packet, looked up by name in the opcode table, to a `MoveInput`: `0x63` MoveDirection, `0x1a5` UseSkill, `0x1a8` UpdateSkillTarget, `0x1ac` SkillInputEnd, `0x1ad` SkillReleased, `0x2e6` SprintInput, `0x62` AimTarget (mode 2 `Aim`, mode 3 `AimEntity`, modes 0/1 `AimMode`). `Player::input` sends it to the instance actor, which queues it in the instance's `World`. Nothing is answered at once.
- **Tick.** The instance actor's frame clock (`servers/instance-server/src/clock.rs`; `[instance] tick_ms`, the same value as InitialState `frame_ms`; one per instance, shared by its sessions) calls `World::tick()` at absolute deadlines `start + n * tick_ms` (restarted when an empty instance gets a player). After a stall it runs the missed frames back to back and sends each, like official servers; a burst is capped at 59 frames (`MAX_BURST`, one below the client's 5x playback threshold), beyond that the rest is dropped (warning `stall: catching up at most 59 frames`) and the deadline base moves to now. `dt` stays `tick_ms / 1000` per frame. The frame's events are encoded by `Codec::encode` (opcodes from `instance.toml`, stat keys from the `Stats` table, skill ids and walking speed from class and game data, `[movement]` sprint keys: `sprint_buff_rows` and the coasting values) and sent in order to every session, followed by the `0x2f4` SimulationTick marker. A reply arrives in the first batch after the input (`r+0`).
- **Event to message.** `MoveAck` is `0x64` (header `(entity, entity, 9, 0)`, the unscaled vector, or scaled to length 550 while sprinting), `ActionStart` is `0x1c8` (`flags` = the request's flags plus `0x10`), `ActionEvent` is `0x1ca`, `Stats` is `0x1d3` set 0, `SkillAck` is `0x1ae` (the "confirmed" target flag `0x04` is set here), `TargetAck` `0x1af`, `InputEndAck` `0x1b1`, `ReleasedAck` `0x1b2`, `SprintState` `0x2e7`, `BuffAdded`/`BuffRemoved` `0x1eb`/`0x1ec`, `AimEcho` `0x1dc` kind 0, `StanceChanged` a `0x2f9` Player component delta (header `(entity, 0xffffffff, 0, 0)`), `Teleport` a `0x64` with direction `(1, 0)` and the new cell followed by one with `(0, 0)`. All other headers are `(entity, 0, 0, 0)`.
- **`0x1ca`** has no fields; the glue defines the empty message locally and sends it only if the opcode table (`instance.toml`, `ActionEvent = 0x01ca`) lists it. The client only decrements a counter for it.
- **Terrain.** The world runs on the client's walkability grid dump (`spawn::client_grid`), or without collision (`Open`) when the dump is missing. Walks, WASD, rolls and sprints are planned with the port of the client's pathfinder (`[movement] pathfinder = "client"`, the default). The server's position is authoritative.
- **Pause.** `0x1ff` PauseRequest calls `World::set_paused`: frames still count (the tick marker is still sent), but nothing moves or is answered, and inputs wait.
- **Unknown or unanswered.** `0x1aa` UpdateSkillTargetEntity is decoded and logged only (no entities to target yet, so no `0x1b0`). A movement packet the table does not know ends the batch as any unknown client message does.
- **Sprint end and roll heading:** the sprint's end restarts or coasts ([above](#coasting-after-a-sprint)), the roll heading falls back to the facing ([roll direction](#roll-direction)). `[movement] sprint_coast_*`, `sprint_restart_delay_frames` and `sprint_release_window_frames` (capture values by default) reach `Locomotion` through `player::sim_config`.

### Drift checker
The DLL's per-frame position report (a sealed side-channel `Kind::Report` frame, [side-channel.md](side-channel.md); `modules/server/servers/instance-server/src/sync.rs`, DLL side `position_sync.rs`) does not touch the simulation. With `[dev] drift_check = true` (default off; needs `[dev] position_sync` and the DLL) the session logs, every `[dev] drift_interval_ms` (default 1000 ms), one `drift` line at info level:

`drift server=x,y client=x,y cells=<now> max_cells=<largest since the last line> samples=<n> state=<server movement state>`

`cells` is the distance in grid cells between the server's exact position and the client's latest report (reports older than 250 ms count as none). The client trails the server by about two frames of reply latency: expect up to ~2.5 cells walking, ~4 sprinting, ~0 standing. Real drift grows over time or stays high while standing. A warning is logged once if the checker is on and no reports arrive within 5 s. The overlay's Sync state page shows the same distance (`drift_cells`). Server-side only.

## Lag
- **No lag compensation to turn on.** The world is always lockstep and the client plays frames as they arrive; `0x1d` PingReply only feeds the latency display. Lag comes from the server: late frames freeze movement. Run `--release` for play (a debug build's old A* took ~108 ms per 33 ms frame on the Riverbank grid); the server warns when a frame takes longer than the tick. The A* uses flat arrays over a box around start and goal (`MARGIN` 24 cells) with a node budget.
- **Unknown client messages end the parse of their whole batch** (no length prefix): an undecoded `0x1a8` once lost a `0x1a5` in the same batch. `SkillInputEnd` (`0x1ac`) stays in `[client_body_sizes]` for the same reason. The DLL sends reports (and the debug link) to `position_sync_port` (set by `cargo xtask deploy-client` from `[network.instance] public_port`); only the [drift checker](#drift-checker) reads them.

## Pause
`0x1ff` PauseRequest also pauses the server simulation (`World::set_paused`): nothing moves on either side while the escape menu is open in a solo game (verified with D held across a 2 s pause: both sides ended one cell apart).

## Saved location
- When a session ends (exit to character selection, log out, closing the game or a dropped connection), the instance server stores the character's area, the area's terrain seed and its grid cell (`poe_store::Location`, migration `0005_character_location.sql`).
- On the next login into that area, the login server puts the location in the ticket. The instance server sends the same seed, so the layout is the same, and spawns the player on the saved cell (or the nearest walkable cell if it is blocked). Characters that have never been in the game start at the area's start position.

## Test tooling
Key and mouse injection for movement tests (`in:`, `inclick:`, `inpress:`, `indown:`/`inup:`/`wait:`, posted keys such as Space) and `movement_log`: [../guides/setup.md](../guides/setup.md#poe-hookkeys-entries), [../architecture/client-dll.md](../architecture/client-dll.md#movement-log). `movement_log` (the DLL's read-only per-frame position log, `frame #n ... world ... step ... grid`) is where the official captures' client positions and the roll tables come from; the unattended tests set it through `POE_HOOK_MOVEMENT_LOG`.

**A roll test needs a real hold of Space**: the plain `0x20` entry (and `0x20:ms`) posts key-down and key-up in one go, the client's polled key state reads "up", and `0x1a5` and `0x1ac` arrive together before the roll starts: the client then sends **no `0x1a8`** (4 of 4 rolls) and rolls along its facing. Use `indown:0x20`, `0x20`, `wait:250`, `inup:0x20` (a hold: `0x20:1400` between them).

**Measured drift (cells, in the second / after the stop):** walking and rolling stay under about 4.3 / 1.4; click-to-move 1.3 / 0; held click 2.5 / 2.2. Free-angle and exact-diagonal cursor sprints end 0.03-0.48 off. Sprints with W held since before the roll remain 8.9-16 off (problem 5). The test method is in [agent-workflow.md](../guides/agent-workflow.md#movement-checks). The client's own coast is visible in every free-angle run (steps 1.85 falling by 0.1 a frame over 30 frames).

Open problem:
5. **Sprint ended with W held since before the roll: the unscaled `0x64` does not restart the client (8.9 to 17 cells of drift).** Three WASD-mode runs (Space 0.8, 1.0, 1.4 s): the server sends the unscaled `MoveAck` at r + 1 as `end_sprint` plans (`out-dir 127 127`); the client logs `action end slot 1: Move` at the sprint-off batch and **coasts 30 frames** (steps 1.28 falling to 0.04) although W is down, then starts a Move **by itself 31 frames after the batch** (first step 1.12 rising to 1.17). The server walks on at 1.23 from r + 2 and is 14 to 17 cells ahead until W is released. With a stream (a `0x63` during the sprint, the six official sprints) the restart works; the likely rule is that `Actor_StartWasdWalk` needs the Actor's input axis, which no `0x63` after the roll set. A fitting model: with no stream and a key held, coast like the no-key case, then walk on in the key direction from batch + 32 (a W release during the coast leaves it stopped). Not applied: the official answer is uncaptured.

Ruled out (sprint towards a diagonal wall, drift 11 cells): not the sprint end but the pathfinder clearance gap; fixed by the client's pathing level 4 while sprinting ([pathfinder](#the-clients-pathfinder)).

## Movement trace
`[dev] movement_trace` (empty = off) writes `runtime/movement-trace.tsv`; `scripts/re/movement_trace.py` lists the frames where the player moved backwards or stalled.

## Gap list
What the seven official captures **still do not cover**. A new capture is one read-only official session by the user (DLL in `Official` mode); keep the recording intact (`packets.jsonl`, `poe-hook.log` with `movement_log` on). The markers `UNVERIFIED (gap #n)` in `modules/server/crates/poe-game/src/locomotion.rs` use these numbers.

| # | Missing | Why it matters | What to do in the session |
|---|---|---|---|
| 1 (med) | **Release between `t0+15` and `t0+18`** (only up to `t0+14` and from `t0+19` seen); a release at `t0+31..34` | exact threshold of the 16/30-frame split and of the sprint end at `t0+35` | taps of 0.5, 0.52, 0.55, 0.6 s (15-18 frames) while standing and walking |
| 2 (med) | **Click-to-move details**: a walk that reaches its target (no arrival message seen), a click on a wall or unreachable cell, WASD pressed during a click walk, the trigger of the held click's 15-frame restarts, the repeat right after a sprint's end that got no `0x1c8` | arrival state, A* goal rules, takeover rules | click once on open ground and **wait 3 s**; click on a wall and on a roof edge; walk by click and press W; hold the button 5 s without rolling or attacking |
| 3 (med) | **Rolls and sprints re-pressed**: Space pressed again **while sprinting**, a tap-roll followed by a press at 15-27 frames, a queued roll whose key is already up when the lock ends (single slot vs "key must be held"), a press exactly 30 frames after the previous start | the roll queue rule | roll, release, press again after 0.5, 0.6, 0.8 s and release at once; while sprinting release and press Space within 0.2 s |
| 4 (med) | **WASD pressed during a roll that started standing**, WASD released during a roll along the keys; WASD stop during a sprint with Space released first | the roll heading rule when the keys change | roll standing, press W during the roll; roll with W, release W during the roll |
| 5 (med) | **Esc menu during a roll or a sprint**; a click-to-move press during a roll | pause/cancel rules | open and close the menu during a sprint and during a roll |
| 6 (med) | **Attacks in a plain WASD walk** (the 4 captured were click walks or walks after a sprint), attacks at another attack speed (lock 12 frames in 3 of 4, 16 once), a roll that cuts an attack while walking, an attack during a roll in the last frames (`t0+25..29`) | the action speed factor's timing; the `t0+24` window edges | attack with the main skill while walking with W held, with and without attack speed gear; roll during an attack while walking |
| 7 (med) | **Weapon swap** (nothing found), stance/input-mode change while walking, rolling or sprinting | `0x200` timing relative to movement; the `0xfe`/`0x1d5` pair | swap weapon sets while walking and standing; toggle the input mode while walking |
| 8 (low) | **Sprint against a monster** (blocked by an entity, not a wall), knockback (`0x1e0`) and stuns while walking or rolling, `0x1b0`/`0x1aa` with a Move or roll | stream while blocked by entities; movement refusal while stunned | sprint into a pack; get hit while walking and while rolling; roll while a monster is hovered |
| 9 (low) | Buffs with definition-dependent `0x1eb` fields (flag `0x10`, rows with a `u16`/vector from the definition; 6 of 51 `0x1eb` in the captures decode with 2 bytes left) | only the three sprint buffs are fully decoded | (no capture needed: decode the buff definition table) |
| 10 (low) | The monster's cell in the `0x1c8` target of an attack on a hovered monster (505,963 vs the press' 454,969): needs entity positions in the world, and the `u1a` header values (1/3/4/8/17/25) of the replies | entity-targeted attacks | (server work: entity positions) |

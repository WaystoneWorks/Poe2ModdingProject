# WASD movement: the client's whole path

**Principle (user decision 2026-11-03):** the server must run an exact port of the client's movement code, never a fit; see [decisions.md](../decisions.md#movement-and-world).

Overview of the exact-port spec (user decision 2026-11-03: restart from scratch). The exact pseudocode is in the four files of the Map; this file keeps the actor tick order, the frame order, the measured rules and the open items. All addresses are Hotfix 1. Status: the server runs a stand-still stub ([instance-world.md](../architecture/instance-world.md#the-movement-seam-movementrs)), the port is to be rewritten (PLAN step d); static RE is done, open items: [What is left to read](#what-is-left-to-read), plus [public sources](#public-sources). Wire messages stay in [movement.md](../protocol/movement.md); the search itself is in [pathfinding.md](pathfinding.md).

Cell and world: `world = (cell + 0.5) * 10.869565` (`0x142193230`), `cell = floor(world * 0.092)` (`0x142193270`). Stats are keyed `Stats.dat row + 1` (`GameFiles/poe-hook-data/stats.tsv`).

## Map

- [movement-positioned.md](movement-positioned.md): `0x63` sender, `0x64` handler, `Actor_StartWasdWalk`, `Positioned_MoveToWaypoint`, facing, line (`Line_*`), step check, speed. Also the follow-path, line-end and facing rules.
- [movement-click.md](movement-click.md): `0x1c8` Move handler, `Actor_PlanMove`, plan timer, held click, arrival.
- [movement-roll.md](movement-roll.md): roll start, per-frame step, curves, sprint switch, end.
- [movement-sprint.md](movement-sprint.md): sprint start, sprint turn, end check, end, coast (`MoveEvent`), `0x64` interaction, stats.

## Actor tick order (`0x141e42a00`, `Actor`, `dt`)

Only what moves the player, in code order. Offsets are from the Actor. Slot 0 action `+0x238`, Move slot `+0x240` (type at action `+0x120`, Move = `0x2909`), axes `+0x400/+0x404`, axes-fresh flag `+0x414`, plan timer `+0x3dc`, animation `+0x380`.

1. `+0x3fc` timer down; `0x141f5e630`; `0x141e40b50` (start of the queued action `+0x248`, re-entry guard `+0x2a2` bit 0: an animation `0x36a`, `0x36b`, `0x371`, `0x372` drops an action with `vfunc +0x70`; sets `+0x41c = 0.03`; a non-slot-0 action goes to the Move slot through `0x141e41c60` then a plan `0x141e42650`, a slot-0 action through `0x141e41c60` then `0x141e4ea40`).
2. No action or Move with timer `<= 0`: `0x141e3ff70` (next queued action).
3. Without a Pathfinding group (`Player` modes 2, 3 at Player `+999`): `+0x3e8`, `+0x3ec` timers.
4. Group leader branch (Positioned `+0x4c0` set): follows the leader's axes. Not used for a solo player.
5. **Axes not zero:** no Move action -> `Actor_StartWasdWalk(actor, 0)` (`0x141e4fb40`); Move with `+0x3dc <= 0` -> re-aim `0x141e50320`.
6. Mode 1 entities (`vfunc +0x1d8 == 1`) with Move, no slot 0, timer `<= 0`: replan (`0x141e42650`). Not the local player.
7. Action finished (`vfunc +0xa0`) handling; queued skills.
8. Action with a facing tolerance: `vfunc +0x340` and `0x141e5c2f0` (tolerance `action_required_target_facing_angle_tolerance_degrees`, `vfunc +0x348`, `0x14197e160`, default 2 pi) -> replan or slot-0 replan.
9. `+0x424`, `+0x428`, `+0x430` timers: on expiry replan. `+0x430` is 0x86 words: the action speed factor ramp (`Actor_SetActionSpeedFactorNow`).
10. Slot-0 action update `vfunc +0x1c0` (only when the action is running, `+0x2a0` bit 1). **Move has no per-frame update of its own.**
11. Parts in `+0x270..+0x278`: `part vfunc[0x38]` (the sprint end check `0x141b76da0` is one, see below).
12. Speed factor ramp (`+0x444`, target `+0x448`), written to Pathfinding `+0x55c`; a change re-issues the step (`Pathfinding_StepAlongPath`).
13. **Tail: `+0x41c`, `+0x3dc`, `+0x420`, `+0x418` go down by `dt`, clamped at 0.**

## Frame order (`0x142137270(entities, dt...)`)

For each entity in key order (key at entity `+0x88`, frame state at world `+0x678`, `+0x67c` component, `+0x67e` phase): packets with a smaller key (`0x1421343c0`), then for each component in list order: set `+0x67c` = its index, **`0x142130360` drains the packets keyed to this component**, then `vtable +0x50(dt)`. Then component `0xff`, drain, and `0x141e7d970(entity + 0x58, dt)` (the hook's `entity_tick`, where `LINE` and `frame #N` are logged, so they show the state **after** the whole frame).

The player's first component is Positioned, the Actor is later. So in one frame:

1. Positioned tick: advance the line by `dt`, make its steps. The grid moves here.
2. Packets for the Actor: `0x64` (snap against the grid of step 1, then a plan), `0x1c8`, ...
3. Actor tick: re-aim if the timer is out, sprint end check, timer down.
4. Log.

Checked with `LINE`: under a stream `el = 0` in every frame (plan after the advance); without one `el` alternates 0, 0.033 (Actor tick plans). The cell in a `0x64` must equal the grid after that frame's step 1. Key values of `0x64` are in the 11-byte header ([movement.md](../protocol/movement.md)): confirm it is the Actor's component index in `0x142130360`.

## Frame drain and path events (read while porting)

- **Drain positions.** Player components: 0 Positioned, 1 Stats, 2 Pathfinding, 3 Buffs, 4 Life, 5 Animated, 6 Player, 7 PlayerClass, 8 Inventories, 9 Actor. A message runs at its header key: order key 0 before all entities, else just before component `+0x18`'s tick. Official keys for the local player: `0x1c8` input starts and `0x2e7` `(0,0,0)`, so **before the Positioned tick** (this is the "first step" of a roll: its line advances in the same frame); `0x64` `(player,9,0)`; server `0x1c8` restarts `(player,9,1)`; sprint-on stats and buffs `(player,5,2)`; others `(5,6)`, `(5,8)`, `(3,0)`, `(9,4)`, `(9,7)`, `(9,10)`, `(0,0,9)`.
- **Positioned listener of Pathfinding** (vtable `0x1434d19c8`): `+8` `0x141dccdb0` line done; `+0x10` `0x141dcce50` blocked = `EndPath(pf, 0)`; `+0x18` `0x141dcce60` stopped = `EndPath(pf, 1)` unless `pf+0x560` bit 2.
- **`0x141de4c30`** (the stop of `EndPath` when entity `+0x8c` bit 3, and of `DodgeRollMove_Stop`): no line stop; sets Positioned `+0x1e5` bit 7, clears the bytes as `0x141de5f50` does, fires "stopped". `Positioned_RunLine` ends the line after its next tick: this is the measured stop step. The player uses it (replay: exact with it).
- **Distance mode:** `L+0x60 = L+0xc9`, and `L+0xc9` is the curve's has-data flag (`L+0xa0+0x29`). `Pathfinding_StepAlongPath` passes `+0x9b = 1` (zero both curve slots) unless Player `+0x3e4` or `pf+0x53d`, and mode byte `+0x9a = 0` (`Positioned +0x1e3` decides); it restores `+0x1e3` afterwards.
- **Dynamic obstacles change real plans:** official `goal=484,539 reached=0` on a layer-0 walkable cell (seg1 f718-726). The server's search needs its entities ([pathfinding.md](pathfinding.md#open)).

## Plan cadence

`FUN_141e42650(actor)` is the only plan entry: it sets `+0x3dc` to 0.05 s (entity has a `Player` component) or 0.25 s, when the action's `vfunc +0x300` is 0, then `Pathfinding_FollowPath` (`0x141dcbf30`) with the action's target (`vfunc +0xd8`, action `+0x150`).

At `dt = 0.033`: plan in frame n, timer 0.017 after the tail, 0 after the next tail, plan in n+2. **So a plan every second frame, from the Actor tick alone.** The `LINE` log agrees. With a `0x64` stream a plan runs every frame: each `0x64` calls `Actor_StartWasdWalk`, which ignores the plan timer and re-arms it ([movement-positioned.md](movement-positioned.md)). A zero vector with zero axes also runs `StartWasdWalk(A, 0)`; the handler's early return is only for a zero vector with non-zero axes and `+0x414 == 0`. In lockstep a click Move plans only at its `0x1c8` and at a line end with waypoint index 0 ([movement-click.md](movement-click.md)).

Goal, in both `Actor_StartWasdWalk` and the re-aim `0x141e50320`: `goal = cell + floor(axes * 0.092)` (per axis, `0x142193270`), then `0x141e504b0` (group clamp only).

`Actor_StartWasdWalk` refuses when: `+0x4ba` path (remote), entity flag `+0x8c` bit 0, Actor `+0x2a1` bits 1 or 2, `+0x2a0` bit 6, animation `0x36a`, `0x36b`, `0x371`, `0x372`. A push at least as fast (Positioned `+0x480`, `+0x484`) stops it. With both axes zero it ends a running Move (`0x141e45da0(actor, 1)`) when action `+0x122 == 0`.

## Owned by the four files

- **Follow path, waypoint, line end** (`0x141dcbf30`, `0x141dcc6a0`, `0x141dcc110`): 126-cell search window, path index, `Pathfinding_OnLineDone`: [movement-positioned.md](movement-positioned.md) and [movement-click.md](movement-click.md).
- **Sprint turn** (`0x141dcc460`): 180-cell line along the turned facing; the turn is `dodge_roll_sprint_turn_rate` = 150 degrees/s x `dt` (`pf+0x580` = 0.033) = 4.95 degrees per plan; no turn within 8.1 degrees: [movement-sprint.md](movement-sprint.md).
- **Positioned move** (`0x141de31a0`), **facing** (`atan2(dy, dx)` of the integer delta, f32, mode 2 minus pi): [movement-positioned.md](movement-positioned.md).
- **Line** (`Line_Setup`, `Line_Advance`, `Line_Step`, `Line_End`, `Line_Point`; `round` = `floorf(x + 0.5f)`), **tick, apply, check** (forgiveness `+0x1e4` bit 2 holds until the first free step; a blocked result 5 takes the cell only with a z target; out of map with `+0x1e5` bit 7 returns 0): [movement-positioned.md](movement-positioned.md).
- **`0x64`** (`0x1421497c0`): snap, then `StartWasdWalk` every time; early return only for a zero vector with non-zero axes and `+0x414 == 0`: [movement-positioned.md](movement-positioned.md).
- **Roll** (`DodgeRoll_*`, `DodgeRollMove_*`, curves, optional length, heading): [movement-roll.md](movement-roll.md).
- **Sprint part** (start `0x141b77110`, end check `0x141b76da0`, end `0x141b773a0`, animation choice, coast `MoveEvent`): [movement-sprint.md](movement-sprint.md). The no-keys axes need Player `+0x20a` (`sprint_continues_with_move_input`).
- **Speed** (`Pathfinding_GetSpeed` `0x141dccfa0`: `movement_velocity_cap` 1098, `PF+0x558`, `PF+0x554`): [movement-positioned.md](movement-positioned.md#7-speed).
- **Wire**: the `0x63` trailer is cell x, cell y (0,0 in lockstep) and a bool = click-to-move mode AND `is_sprinting` ([movement.md](../protocol/movement.md)).

## Tap, then hold during the roll (settled, official)

A roll released before `t0+15` never sprints, even with the key down again at `t0+15`: a press during the roll is queued, the new roll starts at `t0+30` and sprints at its own `+15` (official `2026-11-02_18-31-34_336` f12190: release +6, press +23, `0x1c8` +30, sprint +45; same f3713, f1047). A press before `t0+15` held past it was never captured: same rule assumed. Our server sent the sprint into the released roll, which is the sprint with no animation: `Due::SprintStart` must test `released`, not `held`.

## Rules measured with the harness

Measured with the deleted `line_compare` harness (client `LINE` log against a model). Unless an address is given, the reason in the client is unread.

- **Sprint end:** the check runs in the Actor tick after the re-aim, and `SprintEnd` refuses walks until `0.75 / rate` has passed. After a sprint with no `0x64` stream `SprintEnd` coasts ~19 cells, then refuses walks until 0.75/rate with the speed after the stats (T 1.007 s, 30 frames), then the held key walks on. `rate` = speed x 10.869565 / (600 x `offset_scale`). A frame with a non-zero `0x64` plan uses the speed at the frame's start (T 0.671), a frame without one the speed after its stats (T 1.007).
- **Coast:** starts in the next frame's Animated tick. Target = grid + round(facing x curve end x `offset_scale` / 10.869565), speed = |target - grid| / time. The animation's end stops it.
- **Bonk:** a blocked step (`FUN_141ddcfc0`) or a plan with no way on (all waypoints on the start cell) ends the path with no replan, then the end check plays the Bonk: same clip and rate, no move (wall run: 21 still frames at both walls). Ruled out: the sprint's layer 2 grid as the blocker (5 on every cell there).
- **Sprint sent into a released roll:** the client takes the stats (turn, speed) but runs no sprint part: no sprint curve, no 300-cell line, no `SprintEnd`, level 0. Confirms the tap-then-hold fix.
- **Roll:** a 46-cell roll on open ground runs 49 cells (game curves): each frame's line runs from the cell to `left` past the line's point. The search level is fixed at the action's start. The 300-cell line runs along the waypoint direction (differs from the target once `left` < 10). A roll stops making lines when |target - cell| < 1.6 (1.41 to 2 fit), but the curve restart still runs that frame while `left` > 1.
- **Backward roll** (`+0x3f`, `0x141b8c494` mode 2, `0x141de3afa`: facing `atan2 + pi/2 - pi`): `_bwd_` curves. Weak rule: at least 90 degrees between the heading and the direction to the target, and not while `SprintEnd` plays (one roll each way). `+0x8fa` should gate it (`0x141b8bf27`), its value there is unread.
- **First step of a roll:** none when a line runs and made no step this frame, and the roll is one step shorter (weak: f85, f386 in `stuck`; the curve then drifts 0.006 cells, which causes f574).
- **`0x64 (0, 0)`:** the line runs through the next Positioned tick, then stops, and the next line does not continue it (`+0x61`).
- **Cursor roll:** the first heading is a three-cell rounding of the integer target, then each `0x1af` aims it: [movement-roll.md](movement-roll.md#facing-event-first-heading-checked-by-replay). The 1.66-cell drift while Idle after a stop is the client's smoothed world point past the cell centre.

Open: wall run f400-410, f2456-2512 (1 cell behind, no `LINE` there); frames after f1090 in `stuck` are old server bugs (rolls the client refused), not a test.

## Port design

The port (to be rewritten, PLAN step c/d) is driven only by what the server sends, as the harness was: it applies the tick's outgoing events in batch order (`MoveAck` first, then `SprintState`, then the rest) and then runs the Actor tick. `MoveAck` -> snap check and axes; `ActionStart` -> start the roll or walk to the target; `Stats` -> sprinting flag, `must_sprint`, scale; `Teleport` -> place. The Positioned tick runs at step 1 of the frame and its grid cell goes in the frame's `0x64`. Curve switch and roll extension only when the roll was not released; a bonk detected after the Positioned tick ends the sprint at the wall.

## Curves and offset scale

Game data the port needs (the server loads it in `poe_game::motion_data` and refuses a player without it):
- `art/models/charactersfour/animations/basedodgeroll/onerig.amd`: `dodge_unarmed_01`, `dodge_unarmed_bwd_01`, `dodge_unarmed_01_sprinting`, `dodge_unarmed_bwd_01_sprinting` (roll, backward roll, and their sprinting variants). `dodge_unarmed_01` x 46 / 500 equals every measured roll step.
- `art/models/charactersfour/animations/basesprint/onerig.amd`: `sprint_end_unarmed_01` (750 ms, 46 positions, end 242.425 world units).
- Curve value at `t`: `FUN_141ecccc0`, linear between positions (see [movement-roll.md](movement-roll.md), section 3).
- `offset_scale`: from the class `.ao` (`Melee { offset_scale = 0.9 }`, keys tab-indented, following `extends`); it scales the coast target and the sprint-end rate ([rules](#rules-measured-with-the-harness)).

## What is left to read

Union of the open items of the four files; decompiles are large, batch a few at a time and filter output.

- Tap-then-hold: log `+0x380`, `+0x2a0` and `is_sprinting` (the sprint with no animation, `0x141e57b80`); the `0x64` header's component key (drain `0x142130360`: `+0x67c` component, `+0x67e` phase).
- Positioned: who clears Actor `+0x414`; who decrements the sender cooldown `G+0x8bc8` (captured `0x63` gaps down to 19 ms); monster/NPC collision (`P+0x198`, `P+0x1d8`, `0x141de2b90`, `0x141de0f40`, team table `DAT_142f08ab0`, `0x141df03c0`); `0x64` predictive bend (not needed in lockstep); gamepad iso constants `0x14360c0d4`, `0x14360d9f4` and when `world+0x112` is set; `A+0x2a1` bit 0, `A+0x91a`; smoother `0x141ec9fe0`, `0x141eca2d0`.
- Click: Positioned `+0x1e4` bit 0 setter; Actor `+0x250` (assumed 0); `A.vfC0`, `0x141e5c2f0`, skill flags `0x30`, `0x74`, `0x75` of the Move skill; `0x141d10070`, `0x141dee840`, `0x141d104f0` (arrival line-of-walk tests); component order of Pathfinding, Positioned, Actor; `0x141e4dce0` waypoint handler (`0x141ddf430`, `0x141ddc820`); `(A+0x210)+0xe8`.
- Roll: `0x141ed0510` path storage order; Actor `+0x8fa`, object `0xe4fa`, `0x141f832b0`; `0x141b912d0`, `part+0xa0` setter; caller of `DodgeRollMove_Tick` and the AnimationController tick order; stats `0x5121`, `0x478c`, `0x10a2`, `0x596b`, `0x5f2f`, `0xec`, event `0xb91f` time; `Positioned_MoveToWaypoint` first step in the same frame. Loader gaps (rate clock, `_moving` and floating variants, weapon-set clips, segments, event time): see the end of [movement-roll.md](movement-roll.md).
- Sprint: caller of the part's `+0xa8` start and `first`, `DAT_1445c69b0 +0x48`; `0x141d0fcf0`; who sets Positioned `+0x1e7` bit 0; who replaces `+0x380` when `SprintEnd` ends; Positioned `+0x46c/+0x470/+0x474` (assumed 1); `0x141f63640`, `0x141f66ae0` coast blocked cells; event data to `MoveEvent` fields; `0x2e8` first byte; mode-1 correction in `0x64`.

Then: an offline harness feeding recorded inputs (movement trace `in-*` lines) through the new module, comparing its grid per tick with `LINE cur` until the first divergence of each episode; one short official capture with `LINE` (include "tap Space, then tap and hold during the roll"); port as one module, no fit constants.

## Public sources

No public PoE2 movement spec, emulator or movement opcodes exist (4 web agents, 2026-11-03). Useful only:
- GGG staff thread on client-side prediction and resync: https://www.pathofexile.com/forum/view-thread/889669/filter-account-type/staff
- Data tables: https://github.com/poe-tool-dev/dat-schema (poe2 schema).
- GameHelper2 (Gordin), PoE2 0.5.5 client offsets: Render `CurrentWorldPosition` `0x138`, world-to-grid `10.86957`, Actor `AnimationId` `0x8B0`.
- Community numbers, unverified: roll about 3.7 m, roll size 0 since Dec 2024, sprint grace period since 0.3.0c.

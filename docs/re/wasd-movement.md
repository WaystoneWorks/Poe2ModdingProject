# WASD movement: the client's whole path

The one spec for the port (user decision 2026-11-02: full RE first, then one module replacing the fit-based code on `Mover`). All addresses are Hotfix 1. Status: **RE in progress**, see [What is left to read](#what-is-left-to-read). Wire messages stay in [movement.md](../protocol/movement.md); the search itself is in [pathfinding.md](pathfinding.md).

Cell and world: `world = (cell + 0.5) * 10.869565` (`0x142193230`), `cell = floor(world * 0.092)` (`0x142193270`). Stats are keyed `Stats.dat row + 1` (`GameFiles/poe-hook-data/stats.tsv`).

## Actor tick order (`0x141e42a00`, `Actor`, `dt`)

Only what moves the player, in code order. Offsets are from the Actor. Slot 0 action `+0x238`, Move slot `+0x240` (type at action `+0x120`, Move = `0x2909`), axes `+0x400/+0x404`, axes-fresh flag `+0x414`, plan timer `+0x3dc`, animation `+0x380`.

1. `+0x3fc` timer down; `0x141f5e630`; `0x141e40b50` (queued action start).
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

## Plan cadence

`FUN_141e42650(actor)` is the only plan entry: it sets `+0x3dc` to 0.05 s (entity has a `Player` component) or 0.25 s, when the action's `vfunc +0x300` is 0, then `Pathfinding_FollowPath` (`0x141dcbf30`) with the action's target (`vfunc +0xd8`, action `+0x150`).

At `dt = 0.033`: plan in frame n, timer 0.017 after the tail, 0 after the next tail, plan in n+2. **So a plan every second frame, from the Actor tick alone.** The `LINE` log agrees. With a `0x64` stream a plan runs every frame because the `0x64` handler restarts the walk (handler not read yet).

Goal, in both `Actor_StartWasdWalk` and the re-aim `0x141e50320`: `goal = cell + floor(axes * 0.092)` (per axis, `0x142193270`), then `0x141e504b0` (group clamp only).

`Actor_StartWasdWalk` refuses when: `+0x4ba` path (remote), entity flag `+0x8c` bit 0, Actor `+0x2a1` bits 1 or 2, `+0x2a0` bit 6, animation `0x36a`, `0x36b`, `0x371`, `0x372`. A push at least as fast (Positioned `+0x480`, `+0x484`) stops it. With both axes zero it ends a running Move (`0x141e45da0(actor, 1)`) when action `+0x122 == 0`.

## Follow path (`0x141dcbf30` -> `0x141dcc6a0` -> `0x141dcc110`)

- `0x141dcb810`: arrival check; true ends the path.
- `0x141dcc6a0`: `|goal - cell|^2 < 0x4840` (126 cells) searches to the goal, else to `cell + 126 * unit` (`0x141ed0510`, port `clientpath.rs`). Path array Pathfinding `+0xd4`, count `+0x518`, index `+0x570 = count - 1`. Bit 8 of `+0x560`: no search, two-point path (goal, cell).
- Empty path: `0x141dccac0(pf, 0)` or path-failed delegates; Move ends, which is the sprint's Bonk ([end check](#sprint-end-check-0x141b76da0)).

### The waypoint and the sprint turn (`0x141dcc110`, `0x141dcc460`)

`Pathfinding_StepAlongPath(pf, i)`: waypoint `w = pf[+0xcc + i * 8]`. For an entity with a `Player` component `w` goes through `0x141dcc460`; other entities use it raw. **This is the rule of the sprint turn, in full:**

```
if is_sprinting (0x5746) == 0: return w
d = normalize(((w - cell) + 0.5) * 10.869565)     // note the +0.5, 0x142193230 on the cell delta
f = facing vector, (sin(+0x44c), -cos(+0x44c))    // 0x140163cf0
c = dot(d, f)
if c > 0.99: return w                             // within about 8.1 degrees: straight to the waypoint
a = dodge_roll_sprint_turn_rate (0x5794) * pf[+0x580] * pi/180     // pf+0x580 starts at 1.0
if c > -0.99 and acos(c) < a: return w
if d.y*f.x - d.x*f.y < 0: a = -a
r = (f.x*cos a - f.y*sin a, f.x*sin a + f.y*cos a)
return floor((world(cell) + r * 180 * 10.869565) * 0.092)
```

So the line's end is 180 cells along the turned facing, and the facing then turns to that target in `Positioned_MoveToWaypoint` (below), which rounds it through the integer cell. This explains the `LINE` data (`runtime/poe-hook-port1.log` frames 405-421: -5.1, -9.9, -14.8 ... -34.6 degrees, then the goal), the "5 degrees per plan", and why plans under 8.1 degrees go straight. Frame 1216, the earlier "48 degree jump", was a walk (`is_sprinting` 0). `0x141dcce80` sets `pf+0x580` (no direct callers, vtable or delegate: find who, it also replans).

The step then: speed = `Pathfinding_GetSpeed`, delegates at Pathfinding `+0x20..+0x28` get the request (`vfunc +0x18`), then `Positioned_MoveToWaypoint(positioned, request)` (`0x141de31a0`), or `0x141de3c20` when Positioned `+0x1e6` bit 8.

## Positioned move (`0x141de31a0`)

Refused when: attached (`entity +200`), a push is at least as fast, Positioned `+0x1e6` bit 4. Speed 0 stops (`0x141de5f50`). Target == cell: done delegates, no line. Otherwise:

1. Orientation mode = request's or `+0x1e3`: modes 1, 3, 4: facing = `atan2(target - cell) + pi/2`; mode 2: the same (backwards variant). Through `0x141ddc820`. Exact `atan2` arguments still to read: **the port needs them.**
2. `FUN_141ec86a0(+0x208, cell, z, target, z, speed, -1)` sets up the line. Second line at `+0x368` when `+0x49a` bit 7.
3. World smoother `+0x2e0` gets `(target + 0.5) * 10.869565` (`FUN_141ec9fe0`). Overshoot `+0x454` cleared. `0x141de4bc0`: delegates.

Other callers of the line setup: `0x141dddcc0` (next waypoint, end of a line), `0x141de4ff0` (z change, restarts a line mid-way), `0x141de5190(speed)` (re-issue at a new speed, same end), `0x141ec8c00`.

## Line

Layout, stepping and the frame order are measured from the `LINE` log; offsets from `L = Positioned + 0x208`: `+0` s; `+0xc` p; `+0x18` q; `+0x24` flag (walk s to q); `+0x25` swap major/minor; `+0x26` swap z; `+0x28` sign; `+0x2c` slope; `+0x34` end (major, minor, z); `+0x40` current major; `+0x44` current minor; `+0x48` z; `+0x4c` minor accumulator; `+0x60` distance mode (rolls, thr = 1); `+0x6c` len; `+0x70` T = len/speed; `+0x74` 1/T; `+0x7c` elapsed; `+0x80` distance; `+0x84` thr = T/|major delta| (distance mode: len/|major delta|); `+0x88` acc; `+0x8c` count; `+0x90` pending; `+0x94` time per step.

- `FUN_141ec86a0` sets it up. `FUN_141ec82e0` adds `dt` (+pending) to elapsed and acc.
- `FUN_141ddc9d0` (Positioned tick, called by `FUN_141ddc950(pos, dt)`) loops while `thr <= acc` (or flag and `acc > 0`): `FUN_141ec8cb0` makes ONE step, `FUN_141ddcfc0` checks it (non-zero = blocked: `FUN_141de5f50` stop, unread), `FUN_141dddcc0` applies the grid cell and, at a line's end, starts the next waypoint's line (new `FUN_141ec86a0`, speed from a list) or finishes and stores overshoot at `+0x454`.
- `acc` starts at `thr * (|e-q| - |e-p|)`. With flag set, as soon as `acc > 0` the grid walks s to q in one go.
- New line's `p`: the old line point if the line ran, its current cell == s and `|s-p|^2 < 4`; otherwise `p = s`.
- True state: line point `= p + (e-p) * clamp(el/T)` (`FUN_141ec83d0`); its step is exactly `speed * dt` (sprint 55.5 cells/s, 3.663 per 2 frames). **World position `+0x490` is not the line:** a separate smoother `+0x2e0` drives it (`FUN_141ec9fe0`, `FUN_141eca2d0`). Fits to the logged position are invalid (ruled out: 1.2333 bumpy step, `sprint_line_fit.py`'s 69 %).

## Frame order

`0x64` is applied before that frame's update. A roll's `0x1c8` makes one step at once (action start: plan from the `0x1c8` cell, step, second plan, all before frame log N), so during a roll `L(N).cur` leads the logged position by a frame. Walking: server `g(N) == L(N).cur`.

## Roll (`FUN_141b8c720` -> `FUN_141b8c7f0`, per frame)

`+0x3e` waits for a running line to finish, then `FUN_141b8d440`. Then with `+0x3d`: `FUN_141b8cf70` = distance left; whole cells passed go to the part at `+0xa0`; with `+0x3c` and distance `> 1` step `FUN_141b8c7f0`. Goal = `round(line point + max(distance left, 10) * heading)` (`FUN_141b8d1f0`), steps by a curve in distance mode (`FUN_141ecc780`), no planning for the last 1.6 cells. Heading: [addresses](addresses.md) `DodgeRoll_InitHeading`. `ROLL_STEPS`, `ROLL_SPRINT_STEPS` in `movement.rs` come from `LINE`; the last 5 tap and last 2 sprint values are estimates: read `FUN_141ecc780`.

## Sprint part (vtable `0x1434525d8`)

The roll skill carries a part: `+0x48` end check `0x141b76da0`, `+0xa0` `0x141b76fc0` (floating effect), `+0xa8` start `0x141b77110` (through `0x141415c30`), `+0xb0` end `0x141b773a0`.

### Sprint start (`0x141b77110`)
Sets Positioned `+0x1fc..+0x200` (pathing level). If `(Player timer > 0 or Player +0x20a) and axes are zero`: **axes = trunc(facing * 180)**, `+0x414 = 1`, `Actor_StartWasdWalk(actor, edge)`. That is the 16-cell plan (`floor(180 * 0.092)`) of a sprint with no keys. Then a `Standing` animation check may flip the facing by pi.

### Sprint end check (`0x141b76da0`), per frame
Only when the action's `+0x144` has bit 1 and not bit 2.

1. `is_sprinting` 0 or `is_immobilised` != 0: end, `vfunc +0xb0(0, 0)` (plain `SprintEnd`).
2. No slot 0, no Move, Actor `+0x2a0` bit 7 clear, and (no push or `dodge_roll_is_replaced_by_locusts` 0): end with Bonk (`vfunc +0xb0(1, 0)`). This is what fires when a plan comes back empty.
3. Otherwise `must_sprint` != 0: keeps going.
4. Otherwise, with `(Player timer > 0 or Player +0x20a)`: keeps going while Actor `+0x2a2` bit 5 or an axis is set, ends when neither. Without: keeps going while `+0x2a2` bit 5 is set. End = `vfunc +0xb0(0, 0)`.

### Sprint end (`0x141b773a0`)
Ends Move (`0x141e45da0(actor, 0)`). Clears Positioned `+0x1e7` bit 0 unless slot 0 is `0xedcc`-type (`-0x12b4`). Stops the entity (`0x141de4de0`) unless Actor `+0x2a3` bit 0. Clears `+0x1ff`. With no slot-0 action, alive and `+0x2a3` bit 0 clear: `SprintEnd` animation from row `0x368` `m_ExtraAnimations`, index `bonk != 0` (or `bonk + 2` with stat `0x4862 is_floating`), via `0x141e57b80`.

## What is left to read

In this order, keeping notes here. Decompiles are large: batch a few at a time and filter scripts' output (a `ghidra` xref listing cost 40k tokens).

1. `FUN_140132800` and Player `+0x20a`: what "timer > 0 or +0x20a" is. Decides the tap-then-hold case: **the sprint with no animation** (the open bug). Also the `0x141e45da0`, `0x141e57b80` paths and which animation Move picks (`0x141e4f860`, `0x141e4f750`).
2. `0x64` handler `0x1421497c0` (`0x14214992e`): snap and the restart that gives a plan every frame; `0x141ddb6f0`.
3. Positioned tick `FUN_141ddc950`, `FUN_141ddc9d0`, `FUN_141ec8cb0`, `FUN_141ddcfc0`, `FUN_141dddcc0`, `FUN_141ec8f00`, `FUN_141de5f50`, `FUN_141de4de0`, overshoot `+0x454`; `FUN_141ec86a0`, `FUN_141ec82e0`, `FUN_141ec83d0` from code, not the log.
4. `atan2` arguments of `0x141de31a0` (`0x141de3962`), `0x141ddc820`.
5. Roll: `0x141b8bda0`, `FUN_141b8d440`, `FUN_141b8cf70`, `FUN_141b8c7f0`, `FUN_141b8d000`, `FUN_141b8d1f0`, `FUN_141ecc780`.
6. Move action end `0x141e45da0`, queued start `0x141e3ff70`, `0x141e40b50`, `FUN_141e3fcb0`.
7. Bonk `0x36b`, the coast `0x141f5f650` ([coast](../protocol/movement.md#coasting-after-a-sprint) already holds the rate), and who sets `pf+0x580` (`0x141dcce80`).
8. Value of `dodge_roll_sprint_turn_rate`: check the stats the official server sends (the data gives 5 degrees).

Then: an offline harness feeding recorded inputs (movement trace `in-*` lines) through the new module, comparing its grid per tick with `LINE cur` until the first divergence of each episode; one short official capture with `LINE` (include "tap Space, then tap and hold during the roll"); port as one module, delete the fit-based code (`turn_sprint`, `SPRINT_TURN_RATE`, fit constants), keep the tests that describe client behaviour.

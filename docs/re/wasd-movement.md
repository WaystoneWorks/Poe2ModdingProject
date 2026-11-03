# WASD movement: the client's whole path

The one spec for the port (user decision 2026-11-02: full RE first, then one module replacing the fit-based code on `Mover`). All addresses are Hotfix 1. Status: **RE in progress**, see [What is left to read](#what-is-left-to-read). Wire messages stay in [movement.md](../protocol/movement.md); the search itself is in [pathfinding.md](pathfinding.md).

Cell and world: `world = (cell + 0.5) * 10.869565` (`0x142193230`), `cell = floor(world * 0.092)` (`0x142193270`). Stats are keyed `Stats.dat row + 1` (`GameFiles/poe-hook-data/stats.tsv`).

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

**End of a line, same tick** (Pathfinding listener vtable `0x1434d19c8`, `+8` = `0x141dccdb0`, the Positioned done delegate): arrived (`0x141dcb810`) -> `0x141dccac0(pf, 0)` ends the path. Else `index -= 1`: above 0 -> `Pathfinding_StepAlongPath(next)`; otherwise `0x141dcc6a0` plans again. The new line has `p = s` (the old one is done, `len = 0`), and the tick loop's `advance(0)` gives it the `pending` overshoot from `FUN_141ec8f00`. `0x141dccac0` with arg 0: `FUN_141de4de0` (stop), then done or failed delegates on `+0x18` (`FUN_14020ad50` arrived, `FUN_14020ad94` failed).

The step then: speed = `Pathfinding_GetSpeed`, delegates at Pathfinding `+0x20..+0x28` get the request (`vfunc +0x18`), then `Positioned_MoveToWaypoint(positioned, request)` (`0x141de31a0`), or `0x141de3c20` when Positioned `+0x1e6` bit 8.

## Positioned move (`0x141de31a0`)

Refused when: attached (`entity +200`), a push is at least as fast, Positioned `+0x1e6` bit 4. Speed 0 stops (`0x141de5f50`). Target == cell: done delegates, no line. Otherwise:

1. Orientation mode = request's or `+0x1e3`: modes 1, 3, 4: facing = `atan2(target - cell) + pi/2`; mode 2: the same (backwards variant). Through `0x141ddc820`. Exact `atan2` arguments still to read: **the port needs them.**
2. `FUN_141ec86a0(+0x208, cell, z, target, z, speed, -1)` sets up the line. Second line at `+0x368` when `+0x49a` bit 7.
3. World smoother `+0x2e0` gets `(target + 0.5) * 10.869565` (`FUN_141ec9fe0`). Overshoot `+0x454` cleared. `0x141de4bc0`: delegates.

Other callers of the line setup: `0x141dddcc0` (next waypoint, end of a line), `0x141de4ff0` (z change, restarts a line mid-way), `0x141de5190(speed)` (re-issue at a new speed, same end), `0x141ec8c00`.

## Line

Layout, stepping and the frame order are measured from the `LINE` log; offsets from `L = Positioned + 0x208`: `+0` s; `+0xc` p; `+0x18` q; `+0x24` flag (walk s to q); `+0x25` swap major/minor; `+0x26` swap z; `+0x28` sign; `+0x2c` slope; `+0x34` end (major, minor, z); `+0x40` current major; `+0x44` current minor; `+0x48` z; `+0x4c` minor accumulator; `+0x60` distance mode (rolls, thr = 1); `+0x6c` len; `+0x70` T = len/speed; `+0x74` 1/T; `+0x7c` elapsed; `+0x80` distance; `+0x84` thr = T/|major delta| (distance mode: len/|major delta|); `+0x88` acc; `+0x8c` count; `+0x90` pending; `+0x94` time per step.

**Setup `FUN_141ec86a0(L, s, z, e, z2, speed, index)`** (read from code; 2D here, with `z` ignored when `0x7fffffff`):

```
running = (+0x61 == 0) and len != 0 and old current cell == s
p = s
if running:
    p' = old line point
    if p' != e and |s - p'|^2 < 4: p = p'
    else: running = false
dir = e - p
if running:
    t = dot(dir, s - p) / |dir|^2
    q = round(p + dir * t); flag = (q != s)
else:
    q = s; flag = false
d = e - q                                  // integers
swap = |d.x| < |d.y|, or on a tie while running |dir.x| < |dir.y|    // major = y when swapped
distance_mode = +0xc9                      // stored at +0x60
len = |dir|; T = len / speed; 1/T at +0x74
D = |dir.major|
step_time +0x94 = T / D
thr +0x84 = distance_mode ? len / D : T / D
slope +0x2c = dir.minor / D; sign +0x28 = sign(e.major - q.major)
k = |e.major - q.major| - D
acc +0x88 = thr * k
minor_acc +0x4c = p.minor - slope * k + (slope > 0 ? 0.49 : 0.5)
current (+0x40, +0x44) = s; elapsed, distance, count, +0x61 = 0; +0x98 = 1
```

**Advance `FUN_141ec82e0(L, dt)`:** `x = dt + pending; pending = x; elapsed += x`. Distance mode: `x = curve(+0xa0, x, rate, 0, +0x64)` (`FUN_141ecc780`, rate `+0x78` or `+0x74`), `+0x98 = rate * pending / x` (1 if `x <= 0`), `x *= len` (`* (+0x74 / +0x78)` when `+0x78 > 0`). Then `pending = 0; acc += x; distance += x`.

**Step `FUN_141ec8cb0`, one call:**
- Flag set: current moves one cell towards q on each axis (acc untouched). Reaching q clears the flag; if q's major is already the end, `acc -= T` (or `len` in distance mode).
- Flag clear and `thr <= acc`: `count += 1; major += sign; acc -= thr; minor_acc += slope; minor = floor(minor_acc)`.
- Returns the cell (swap undone). Line done when `major == end major`: then `FUN_141ec8f00`: `pending = acc` (distance mode: `+0x98 * step_time * acc / thr`), at least 0; `thr = 0; len = 0`.

**Point `FUN_141ec83d0`:** `p + (e - p) * clamp(elapsed / T)`, distance mode `distance / len`.

**Positioned tick `FUN_141ddc950(pos, dt)`:** skipped when entity data `+0x20` is set and `+0x1e6` bit 1 clear. Push timer `+0x480 -= dt` (at least 0). `+0x454 = 0`. Then `FUN_141ddc9d0`:
```
if thr == 0: return
advance(dt)
while thr <= acc or (flag and acc > 0) [or the z-curve is off]:
    if entity gone: return
    done = step()
    r = check(cell)                       // FUN_141ddcfc0
    if r != 0:                            // blocked: stop FUN_141de5f50, delegates
        return
    if not apply(cell, done):             // FUN_141dddcc0, false = finished
        if thr == 0: acc = 0; pending = 0; finish (below); return
        if pending > 0: advance(0)
        continue
    // true: keep looping (next line started or not done)
finish when +0x1e5 bit 7: FUN_141ec8f00, acc = pending = 0, smoother to the cell (FUN_141eca2d0), bytes cleared
```
**Apply `FUN_141dddcc0`:** grid `+0x444 = cell`; `FUN_141ed3e40` (occupancy), `FUN_141dd88f0`. Not done: returns true. Done, with `+0x1e6` bit 5 (a Positioned-owned waypoint list, not used by WASD plans): next list entry. Otherwise: **overshoot `+0x454 = elapsed - T` when positive**, done delegates (`FUN_14020ad94` on `+0x18`), returns false. So WASD plans have one line each; the delegate may start the next waypoint: read the Pathfinding handler (left to read).

**Check `FUN_141ddcfc0(pos, out, cell, z, probe)`, result `out[0]`:** 0 free.
- Outside the terrain (`width * 23`, `height * 23`): stop, result 2.
- Skipped (0) when Positioned `+0x1e4` bit 5, `+0x49a` bit 2, or `+0x269`.
- Walkability, `+0x49a` bit 3 clear: mode = 1 with `+0x1e6` bit 3; 2 for a Player with `+0x1e7` bit 1 (the sprint's flag); else `+0x499`. `level = +0x1f8 + 1` (0 skips). Free when `level <= FUN_141d0df50(grid, cell, mode)`. Otherwise result 2, except with `+0x1e7` bit 2: a side probe (normal * 30 cells, `FUN_141d18ce0`) and a search (`FUN_141ed0510`) can allow it when the way round is under 30 cells: sets `+0x49a` bit 3 and stores the cell at `+0x45c`.
- Entities (only when not the sprint's flag): `FUN_141df0190` hit -> 3, with the entity in `out[1]`; `FUN_141de0f40` -> 4; height -> 5.
- With `+0x1e4` bit 2 (set by the path request when the search's `param_8` came back set) a non-2 result is forgiven once: result 0.
- Group boundary (Positioned `+0x4c0`): `FUN_141ddf430`.

**A blocked step, in the tick:** the cell is not applied (the grid stays on the last free cell); `FUN_141de5f50`; result 5 still takes the cell; done delegates unless `+0x1e5` bit 7 (`FUN_141defd50`). `FUN_141de5f50`: `FUN_141ec8f00`, smoother to the cell, resets `+0x499`, `+0x464`, `+0x4ac`, `+0x479`, `+0x47b`, `+0x47c`, clears `+0x1e6` bit 5. `FUN_141de4de0` (the sprint's stop): when a line is running, `+0x490 = +0x2e0` if still on the line's start cell, `FUN_141de5f50`, delegates; otherwise only the smoother. No cell change either way.

- True state is the line point; its step is exactly `speed * dt` (sprint 55.5 cells/s, 3.663 per 2 frames). **World position `+0x490` is not the line:** a separate smoother `+0x2e0` drives it (`FUN_141ec9fe0`, `FUN_141eca2d0`). Fits to the logged position are invalid (ruled out: 1.2333 bumpy step, `sprint_line_fit.py`'s 69 %).

## Frame order

### `0x64` (`0x1421497c0`, from `0x14214992e`)
Non-zero vector and cell != grid: **snap** `0x141ddb6f0`: grid = cell, world `+0x490 = (cell + 0.5) * 10.869565`, and with a line or smoother running `FUN_141de5f50`, `acc = pending = 0`. The line is dead (`len = 0`), so the next line starts at `p = s`, the cell's centre. (Predictive mode only: under 46 cells, `0x844`, it bends instead.) So a wrong cell loses the sub-cell phase, and the next plan's line differs from the server's: wrong cells come in runs. The vector: when it and the axes are both zero and `+0x414 == 0`, nothing more; otherwise `axes = vector; +0x414 = 1; Actor_StartWasdWalk(actor, edge)`, `edge` = axes were zero and the vector is not. `Actor_StartWasdWalk` does not look at the plan timer, so **each `0x64` is a plan**, and it re-arms the timer: under a stream the tick's re-aim never fires, one plan per frame. The server must make the same plans: the plan's goal, line and (when sprinting) turn all depend on them.

### Facing
`Positioned_MoveToWaypoint` (`0x141de3962`), modes 1, 3, 4 with target != cell: `facing = atan2(target.y - cell.y, target.x - cell.x) + pi/2`, integers converted to float, `fmod 2 pi`, plus `2 pi` if negative, through `0x141ddc820`. Mode 2 the same (`0x141de3a..`, backwards variant unread). The facing therefore turns once per plan, to the integer target. Sprint turn input: this facing.

A roll's `0x1c8` makes one step at once (action start: plan from the `0x1c8` cell, step, second plan, all before frame log N), so during a roll `L(N).cur` leads the logged position by a frame. Walking: server `g(N) == L(N).cur`.

## Roll (`FUN_141b8c720` -> `FUN_141b8c7f0`, per frame)

Action layout: `+0x3c` steering on, `+0x3d` curve set, `+0x3e` wait for the line to end, `+0x40` heading (radians, facing convention), `+0x4c` total distance (`int`, `dodge_roll_travel_distance`), `+0x50` cells reported, `+0x20` path scratch (search args at `+0x458`, count `+0x450`), `+0x28` animation state, `+0x30` animation name, `+0x48` optional bend.

Per frame `FUN_141b8c720`: `+0x3e` waits while a line runs, then `FUN_141b8d440`. Then with `+0x3d`: `left = FUN_141b8cf70`; whole cells passed since last time go to the part at `+0xa0`; with `+0x3c` and `left > 1`: `FUN_141b8c7f0`.

**The curve is the animation's.** `FUN_141b8d440`: `FUN_141dde090(pos, name, 0, length)` loads the roll animation's movement curve into both Positioned curve slots (`+0x2a8` = `L + 0xa0`, `+0x330`, `FUN_141ecc540`), with `length = +0x1bc - +0x1b8` of the animation state, and `FUN_141dde3f0(pos, elapsed +0x1a4, length)` sets the time. `left = (1 - clamp((value(+0x2a8) - +0x2b4) / (+0x2b8 - +0x2b4))) * total`, where value is `FUN_141eccb30` when the curve has data (`+0x2d1`), else `+0x2c8`.

`FUN_141ecc780(curve, dt, rate, out, stop_segment)`: `x = rate * length * dt` unless looping; adds to position `+0x20`; segments of 0x38 bytes at `curve_data + 0x48` (time `+0x28`, duration `+0x2c`, rate `+0x30`, `+0x34`), `FUN_141ecd190` finds the value. Returns the curve's progress delta over the segment. **So the table of steps per frame comes from data: dump it from the animation (`.ast`) or read the segments at runtime with the hook, instead of the `LINE`-fitted `ROLL_STEPS`, `ROLL_SPRINT_STEPS`** (last 5 tap, last 2 sprint values there are estimates).

Step `FUN_141b8c7f0`: `(goal, flag) = FUN_141b8d1f0`; target = `FUN_141b8d000(goal)` (unread); stop when `|goal - cell| <` `FUN_140132800` (a constant, 1.6 measured). `speed = FUN_141b8d770` = `left / ((length - elapsed) / rate)`, `rate` = animation state `+0x178` (1 with `+0x1d4`) x `+0x1b0`: the distance left over the animation time left, recomputed each frame (so `sp` in the `LINE` log rises and falls with the curve); speed 0: if a line runs, `+0x3e = 1` and `FUN_141de4de0`. `FUN_141dde3f0(pos)`; flag sets Positioned `+0x1e4` bit 2. `FUN_141b8fe20`, `FUN_141b90060`: line checks that shorten the target (unread). Bend `+0x48` rotates the target. Then `Positioned_MoveToWaypoint(pos, {target, speed, ...})`, so the facing and line rules above apply.

`FUN_141b87580(pos)` = a line runs (`len != 0`, `+0x269` clear) and its start cell is the current cell. `FUN_141b8d000` (target): the same point as the goal below with `left` itself instead of `max(left, 10)`, heading taken as `atan2` of the vector to it.

`FUN_141b8d1f0`: `v = rotate((0, -max(left, 10)), heading)`; without `FUN_141b87580(pos)`: `goal = cell + round(v)`, with it: `goal = round(line point + v)`. Then the search (`FUN_141ed0510`) from the cell; the path's first waypoint, or the cell when under 2 nodes.

Heading `DodgeRoll_InitHeading` (`0x141b8bda0`): axes non-zero and action `+0x5e`: `atan2` of the axes through `0x142193270` (floored cells) `+ pi/2`; else towards the target `+0x150`; else the facing. `+0x3f = 1` when Actor `+0x8fa` and at least 90 degrees from the facing.

## Sprint part (vtable `0x1434525d8`)

The roll skill carries a part: `+0x48` end check `0x141b76da0`, `+0xa0` `0x141b76fc0` (floating effect), `+0xa8` start `0x141b77110` (through `0x141415c30`), `+0xb0` end `0x141b773a0`.

### Sprint start (`0x141b77110`)
Sets Positioned `+0x1fc..+0x200` (pathing level). If `(Player timer > 0 or Player +0x20a) and axes are zero`: **axes = trunc(facing * 180)**, `+0x414 = 1`, `Actor_StartWasdWalk(actor, edge)`. That is the 16-cell plan (`floor(180 * 0.092)`) of a sprint with no keys. Then a `Standing` animation check may flip the facing by pi.

### Sprint end check (`0x141b76da0`), per frame
Only when the action's `+0x144` has bit 1 and not bit 2.

1. `is_sprinting` 0 or `is_immobilised` != 0: end, `vfunc +0xb0(0, 0)` (plain `SprintEnd`).
2. No slot 0, no Move, Actor `+0x2a0` bit 7 clear, and (no push or `dodge_roll_is_replaced_by_locusts` 0): end with Bonk (`vfunc +0xb0(1, 0)`). This is what fires when a plan comes back empty.
3. Otherwise `must_sprint` != 0: keeps going.
4. Otherwise, with Player `+0x20a` set: keeps going while Actor `+0x2a2` bit 5 or an axis is set, ends when neither. Without: keeps going while `+0x2a2` bit 5 is set. End = `vfunc +0xb0(0, 0)`.

Actor `+0x2a2` bit 5 is the sprint key held (setter `0x141e5c1f0(actor, held)`, clearing also zeroes `+0x915`). Player `+0x20a` is the **client option `sprint_continues_with_move_input`** (key compared at `0x141013881`, value through `0x1419395f0`, stored at `0x1410138c1`; also `0x14100f436`, `0x142763fc8`, `0x142bb543e`), not server state. Read how it reaches the client (config file or a message) and whether the server can know it: with it on, a sprint runs on after the key's release while an axis is set. The `0x140132800` call before it reads a local 0.0, so "timer > 0" never holds (Ghidra shows `0 < xmm0`; `0x141b76ef0`, same in `0x141b77110`). This is why the official client's end of a sprint can differ from ours with the same replies.

### Which animation (`0x141e4f750`, `0x141e4f860`)
Move animation: Actor `+0x91c` if not `0x43f`; else `is_sprinting` != 0 -> **`0x368` (sprint)**; `+0x8fa` -> `0xc3`; by orientation mode (Move action's `vfunc +0x100`, Buff `0xe4fa`, or Positioned `+0x1e3`): 2 -> `0x97`, 3 -> `0x9b`, 4 -> `0x9a`, else 4 (run). Only re-chosen at the tail of a plan (`0x141e42650`): Actor `+0x2a0` bit 7 set before and after the plan and (`+0x8fa` or the animation `+0x380` differs from the choice or the speed changed) -> `0x141e4f860(actor, -1)`, and on a speed factor change in the tick. So the sprint animation starts at the first plan after `is_sprinting` arrives, if bit 7 is set: the tap-then-hold case with no animation is either bit 7 clear or `is_sprinting` not set while the line runs sprint speed; check with a log of `+0x380`, `+0x2a0` and the stat.

### Sprint end (`0x141b773a0`)
Ends Move (`0x141e45da0(actor, 0)`). Clears Positioned `+0x1e7` bit 0 unless slot 0 is `0xedcc`-type (`-0x12b4`). Stops the entity (`0x141de4de0`) unless Actor `+0x2a3` bit 0. Clears `+0x1ff`. With no slot-0 action, alive and `+0x2a3` bit 0 clear: `SprintEnd` animation from row `0x368` `m_ExtraAnimations`, index `bonk != 0` (or `bonk + 2` with stat `0x4862 is_floating`), via `0x141e57b80`.

## What is left to read

In this order, keeping notes here. Decompiles are large: batch a few at a time and filter scripts' output (a `ghidra` xref listing cost 40k tokens).

1. Log `+0x380`, `+0x2a0` and `is_sprinting` for the tap-then-hold case: **the sprint with no animation** (the open bug). `0x141e57b80` if needed.
2. The `0x64` header's component key (drain `0x142130360` confirmed: `+0x67c` component, `+0x67e` phase).
3. How the Actor ends Move on the path's delegates; use of overshoot `+0x454`; who sets Positioned `+0x1e7` bits 1, 2 (the sprint's `0x141b77110` sets `+0x1fc..+0x200`; `0x141b773a0` clears `+0x1e7` bit 0). The curve file: which data holds "movement animations" (segments of 0x38 bytes with a float frame table; `FUN_141ecd190`, `FUN_141ecc540`).
4. `0x141ddc820` (sets the facing; side effects), mode 2's facing.
5. Roll: `FUN_141b8fe20`, `FUN_141b90060`, `FUN_141ecd190`, `FUN_141ecc540`, `FUN_141eccb30`, `FUN_141dde3f0`, the action start and the first step (`0x1c8`), and the roll animation's curve data.
6. Move action end `0x141e45da0`, queued start `0x141e3ff70`, `0x141e40b50`, `FUN_141e3fcb0`.
7. Bonk `0x36b`, the coast `0x141f5f650` ([coast](../protocol/movement.md#coasting-after-a-sprint) already holds the rate), and who sets `pf+0x580` (`0x141dcce80`).
8. Value of `dodge_roll_sprint_turn_rate`: check the stats the official server sends (the data gives 5 degrees).

Then: an offline harness feeding recorded inputs (movement trace `in-*` lines) through the new module, comparing its grid per tick with `LINE cur` until the first divergence of each episode; one short official capture with `LINE` (include "tap Space, then tap and hold during the roll"); port as one module, delete the fit-based code (`turn_sprint`, `SPRINT_TURN_RATE`, fit constants), keep the tests that describe client behaviour.

# Dodge roll, local player (exact-port spec, Hotfix 1)

Exact-port spec for the roll: start, per-frame step, curves, sprint switch, end. Overview: [wasd-movement.md](wasd-movement.md); siblings: [positioned](movement-positioned.md), [click](movement-click.md), [sprint](movement-sprint.md).

All addresses Hotfix 1. `pos` = Positioned (`entity+0x98`), `actor` = Actor, `act` = the DodgeRoll action
(class vtable `0x143427c50` region), `part` = the roll movement part (0xb8 bytes, vtable `0x143453f68`,
`act+0x430`), `ac` = AnimationController component (`part+0x28`), `C` = movement curve run at `pos+0x2a8`
(second copy at `pos+0x330`), `L` = path line at `pos+0x208` (so `C = L+0xa0`).
Helpers: `round(x)` = `0x1405226a0` = floor(x+0.5); `floor` = `0x140161d90`; `rot(v,a)` = `0x142196700`
= (x cos a - y sin a, x sin a + y cos a); `wrap(a)` = fmod(a, 2pi) (`0x140a3a730`), +2pi if < 0;
`ang(d)` = wrap(atan2(d.y, d.x) + pi/2) (`0x142c421c8` = atan2f(y,x)); `len_i(v)` = `0x1401639b0` =
sqrt(x*x+y*y) of an int2; `clamp01` = `0x140109ca0`; `max` = `0x14014dcb0`. Names below are set in Ghidra.

## Part layout (`part`)
`+0x08` act; `+0x20` path search scratch (0x478, `0x141ed39d0`; `+0x450` waypoint count, waypoints at
`+0x04 + 8*i`, `+0x474..+0x477` search flags, `+0x475` = search "strict" flag); `+0x28` ac; `+0x30` curve
metadata (`0x141d37ae0(ac+0x180, ac+0x190)`); `+0x38` stat `0xec` (int); `+0x3c` steering on (init 1);
`+0x3d` curve loaded; `+0x3e` waiting for a running line; `+0x3f` backward; `+0x40` heading (rad);
`+0x44` optional line length (int), `+0x48` its has-flag; `+0x4c` total distance (int); `+0x50` whole
cells reported; `+0x54..+0x63` the 16-byte start block (below); `+0xa0` cells-travelled listener
(vfunc `+0x10(&delta)`); `+0xa8`, `+0xb0` delegate slots on pos/actor.
Constructor (in `DodgeRoll_OnStart` and clone `0x141b8bc00`): `+0x3c` dword = 1, `+0x40` = 0, `+0x48` = 0,
`+0x4c..+0x5b` = 0, `+0x5c` = 0x0101, `+0x61` = 0, `+0xa0..+0xb7` = 0.

## 1. Start (`0x1c8` -> action start)

### `DodgeRoll_OnStart` `0x141aa8500` (act vfunc in `0x143427c50`)
```
pos+0x1fc = (pos+0x1f8 /*level*/, 1); grid rebuild (0x141d0fcf0); pos+0x200 = 1   // search level fixed now
act+0x45c = int(sqrt(1 + stat(0xec)/10000) * stat(0x57fa))      // 0x141aa9250, dodge_roll_travel_distance
blk = { +0x00 int act+0x45c, +0x04 byte stat(0x5121), +0x05 stat(0x5121)?3:0, +0x06 stat(0x478c)!=0,
        +0x07 0, +0x08 1, +0x09 1, +0x0a 1 (-> part+0x5e), +0x0b 1, +0x0c ?, +0x0d 0 }
part = new 0xb8; act parts list += {type 8, part}; act+0x430 = part
DodgeRoll_InitHeading(part, &blk, &cb)            // copies blk to part+0x54..+0x63
FUN_141a3cec0(act)                                // base action start (animation)
DodgeRollMove_Start(part)
pos+0x1e7 |= 1
actor vfunc +0xd0; act+0x461 = (actor "Standing" lookup 0x141e531e0 == actor+0x2be)
```
So **`part+0x5e` is always 1 for DodgeRoll** (constant in `blk`); `+0x5c` = 1 (play rate restart),
`+0x5d` = 1 (orientation handling), `+0x58/+0x59` path level flags, `+0x5a` strict search.

### `DodgeRoll_InitHeading` `0x141b8bda0`
```
part+0x54..+0x63 = blk
if actor && (actor+0x400 != 0 || actor+0x404 != 0) && part+0x5e:
    c = (floor(ax*0.092), floor(ay*0.092))   // 0x142193270 on float(axes); ints
    part+0x40 = ang(float(c))
else:
    if act+0x150 == pos+0x444 && act+0x154 == pos+0x448: part+0x40 = pos+0x44c   // facing
    else: part+0x40 = ang(float(act+0x150 - pos+0x444, act+0x154 - pos+0x448))
    if !actor: part+0x3f = 0; return
part+0x3f = 0
if actor+0x8fa:
    d = wrap(part+0x40 - pos+0x44c); if d < -pi: d += 2pi elif d > pi: d -= 2pi
    if |d| >= pi/2: part+0x3f = 1         // backward roll
```
Constants `0x14360c124` = pi/2, `0x14360c40c` = 2pi, `0x14360da2c` = -pi, `0x14360c2ec` = pi.

**Actor `+0x8fa`** (byte; when it changes: `actor+8 -> +0x8d |= 8`, `actor+0x10 = 1`, and if `actor+0x2a0`
bit 7: re-choose move animation `0x141e4f860(actor, -1)`; it selects move animation `0xc3` in
`0x141e4f750`). Writers:
- `0x141dd3ea0` (listener, vtable `0x1433a8018`, `this-0x170` = entity): `+0x8fa = (arg4 == 0) ||
  no entity sub-object 0xe4fa (0x141e7d6a0(entity+0x58, 0xe4fa)) || 0x141f832b0(it) ||
  slot-0 action type == 0x62e`.
- `0x141f82a90`: `+0x8fa = (actor animation-set name 0x141e5b7f0 == global string 0x144713528)`.
- `0x141dcfff0` (`0x141dd062f`): sets 1 under a `+0x70` condition.
- Action start `0x141bdc5e0` (a charge-type action; random direction when its target is its own cell)
  sets 1; `0x141c474d0` (another action's end, unless `+0x144` bit 1) sets 0.
Meaning not settled: looks like a "strafe / face-the-aim" stance flag (true when the entity has no `0xe4fa`
object). Its value for an unarmed player was not read: log `actor+0x8fa` at a roll start (x64dbg/hook).

### `DodgeRollMove_Start` `0x141b8bfa0` (first step, same call)
```
part+0x28 = ac; part+0x30 = curve meta of ac's current animation
if part+0x5c && actor+0x388 list entry: replay the animation with rate ac+0x1b0 (0x141d44a30)
part+0x20 = new search scratch (if none); delegates +0xa8 (pos), +0xb0 (actor)
if part+0x54 < 1: log "base travel distance <= 0"; return
part+0x4c = part+0x54                         // total, int cells
part+0x38 = stat(0xec)
Tlen = (ac+0x190 == -1) ? 0 : ac+0x1bc - ac+0x1b8
Positioned_SetMoveCurve(pos, part+0x30, ac+0x1a4 /*elapsed*/, Tlen)   // NOTE start = elapsed, not 0
goal, flag = DodgeRollMove_Goal(part)
target = DodgeRollMove_Target(part, goal)
speed = DodgeRollMove_Speed(part)
if !part+0x5d: pos+0x1e3 = 0  elif part+0x3f: pos+0x1e3 = 2   // orientation mode 2 = backward
if flag: pos+0x1e4 |= 4
if goal != pos cell: 
    out = target; DodgeRollMove_ClipToWalkable(cell, target, {part, pos+0x1e8, pos, &out}); target = out
    Positioned_MoveToWaypoint(pos, {&target, speed, 0x7fffffff, cbs, 0, 0, 0, (part+0x59, 1), part+0x58})
part+0x3d = 1; part+0x3e = 0
```
Unlike the per-frame step there is **no** `CheckClearCells` and no bend here. The curve is loaded from
the animation's current time, so `C[3]` = C(elapsed at start).

## 2. Per frame

### `DodgeRollMove_Tick` `0x141b8c720` (part vfunc `+0x48`)
```
if part+0x3e:
    if pos+0x28c != 0 && !(pos+0x1e5 & 0x80): return       // a line still runs
    part+0x3e = 0; DodgeRollMove_ReloadCurve(part)
if part+0x3d:
    left = DodgeRollMove_DistanceLeft(part)
    n = int(float(part+0x4c) - left)
    if n > part+0x50: if part+0xa0: part+0xa0->vfunc+0x10(&(n - part+0x50)); part+0x50 = n
    if part+0x3c && left > 1.0: DodgeRollMove_Step(part)
```
A blocked step clears `part+0x3d`: Positioned "blocked" delegates `0x141defd50` -> listener vtable `0x143453ce0` `+0x10` `0x141b8d4e0` (`this` = part+0x10). The roll then makes no more lines until `ReloadCurve` (`part+0x3e` path or the sprint switch).

### `DodgeRollMove_ReloadCurve` `0x141b8d440`
`Positioned_SetMoveCurve(pos, part+0x30, 0, Tlen)`; `Positioned_SetMoveCurveTime(pos, ac+0x1a4, Tlen)`;
`part+0x3d = 1`. (Here `C[3]` = C(0).)

### `DodgeRollMove_DistanceLeft` `0x141b8cf70`
`v = pos+0x2d1 ? MoveCurve_Value(C, C[8]) : pos+0x2c8`;
`left = (1 - clamp01((v - C[3]) / (C[4] - C[3]))) * float(part+0x4c)`.

### `DodgeRollMove_Speed` `0x141b8d770`
```
r = ac+0x178; if r != 0 && ac+0x1d4: r = 1; r *= ac+0x1b0
if r == 0: return 0
Tleft = Tlen / r - ac+0x1a4 / r
if Tleft == 0: log "exactly at end of animation"; return 0
return DistanceLeft / Tleft
```

### `DodgeRollMove_Goal` `0x141b8d1f0` -> (goal, flag)
```
scratch+0x475 = stat(0x10a2) != 0 || part+0x5a
v = rot((0, -max(left, 10)), part+0x40)
if !0x141b87580(pos): g = cell + (round(v.x), round(v.y))
else:                 P = line point (0x141ec83d0(pos+0x208)); g = (round(P.x+v.x), round(P.y+v.y))
flag = 0
if !scratch+0x477:
    ok = 0x141ed0510(&g, scratch[0], scratch+0x458, scratch+0x475, scratch+0xc, scratch+0x450,
                     scratch+0x476, &flag, scratch+8, 0, scratch+0x474)
    if ok: return (*(int2*)(scratch + 8*count - 4), flag)     // element count-1 of the waypoint array
if count < 2: return (cell, flag)
return (*(int2*)(scratch + 8*count - 4), flag)
```
Which end of the path element `count-1` is (first step or goal) depends on `0x141ed0510`'s storage
order; the earlier note "first waypoint" is consistent if the path is stored goal-first. Unverified.

### `DodgeRollMove_Target` `0x141b8d000`(part, goal)
```
left = DistanceLeft (no max with 10)
if !0x141b87580(pos): a = ang(float(goal - cell)); t = cell + round(rot((0,-left), a))
else: P = line point; a = ang(float(goal) - P); t = round(P + rot((0,-left), a))
```

### `DodgeRollMove_Step` `0x141b8c7f0`
```
goal, flag = Goal(part); target = Target(part, goal)
d = sqrt(|goal.x-cell.x|^2 + |goal.y-cell.y|^2)
if 0.0 > d: return                 // 0x140132800 reads a local set to 0.0: never true (dead check)
speed = Speed(part)
if speed == 0:
    if pos+0x28c == 0 || (pos+0x1e5 & 0x80): return
    part+0x3e = 1; Positioned_Stop(pos) /*0x141de4de0*/; return
Positioned_SetMoveCurveTime(pos, ac+0x1a4, Tlen)      // curve restart even if no line follows
if flag: pos+0x1e4 |= 4
counter = 2
DodgeRollMove_CheckClearCells(cell, target, {part, pos, &counter})
if counter > 0: return              // fewer than 2 clear cells beyond the start: no line this frame
out = target; DodgeRollMove_ClipToWalkable(cell, target, {part, pos+0x1e8, pos, &out}); target = out
k = 0
if part+0x48:                                        // optional length (sprint), see 4.
    k = speed / len_i(target - cell)
    a = ang(float(goal - cell))                      // goal (search waypoint), not target
    target = cell + round(rot((0, -float(part+0x44)), a))
Positioned_MoveToWaypoint(pos, {&target, speed, 0x7fffffff, cbs, 0, word 0x14305c380, 0,
                                (part+0x59, 1), part+0x58, word part+0x60, 0})
if part+0x48: pos+0x280 = k (L+0x78); pos+0x318 = k
part+0x3e = 0
```
**The 1.6-cell stop is not a constant**: it is `counter`. The walk must pass 2 cells other than the start
without a block, so a target within 1 Bresenham step (max(|dx|,|dy|) < 2) makes no line, as does a
block in the first 2 cells. With `left > 1` in Tick this gives the measured 1.41..2.

### `DodgeRollMove_CheckClearCells` `0x141b8fe20`(from, to, ctx{part, pos, &counter})
Bresenham over the major axis from `from` to `to` inclusive (err starts at -major/2, err += minor;
if err > 0: minor step, err -= major). For each cell p:
```
lvl = (int)(char)pos+0x1f8 + 1
if lvl != 0 && (walk(p, mode 0) /*0x141d0df50*/ < lvl || 0x141b90b10(grid, p, lvl)): return false
if p != pos cell: if --counter < 1: return false
```
`0x141b90b10(grid, p, lvl)`: locks `grid+0x140`, scans the buckets of the dynamic-object hash
(`grid+0x28`, 0x38 per bucket, width `grid+0x18`, height `grid+0x20`) in the box
`p +- (lvl - 2 + grid+0x138)` (clamped, `0x140163b80(.., 0x17)` = to bucket coords) and returns true when
`0x141b912d0(bucket, ...)` reports a blocker. Not read: `0x141b912d0` (which objects block; the server
can treat it as "no dynamic blockers" until monsters/objects block rolls).

### `DodgeRollMove_ClipToWalkable` `0x141b90060`(from, to, ctx{part, pos+0x1e8, pos, &out})
Same Bresenham. For each cell p: `layer = (pos+0x1e5 & 0x80) ? pos+0x498 : pos+0x499`;
`lvl = (char)pos+0x1f8`; if `lvl != -1 && walk(p, layer) < lvl + 1`: return 0 (out = last good cell);
else `*out = p`. So the target becomes the last walkable cell on the straight line (the start cell itself
counts; if it is blocked, `out` stays the original target).

## 3. Curves (`C` at `pos+0x2a8`, floats; `meta` = onerig.amd animation)
`meta`: `+0x20` duration ms (u32), `+0x2c` loop, `+0x30..+0x38` positions (f32), `+0x48..+0x50`
segments (0x38 each: `+0x10..+0x18` frame table f32, `+0x28` scale, `+0x2c` offset, `+0x30`, `+0x34`),
`+0x68` value per loop, `+0x70` frame count.
`C`: `[0]` range, `[1]` C(t_restart), `[2]` t_restart, `[3]` C(load start), `[4]` C(load end),
`[5]` load end, `[6]` end-start, `[7]` end - t_restart, `[8]` t (current), `[9]` duration s,
`+0x28` loop, `+0x29` has data (positions >= 2 or segments >= 2), `+0x2a` segments >= 2, `+0x30` meta.

- `Positioned_SetMoveCurve` `0x141dde090`(pos, meta, s, e): s,e finite and >= 0 -> `MoveCurve_Load(C2 =
  pos+0x330 too)`; otherwise logs and loads (0, 0). Both `pos+0x2a8` and `pos+0x330`.
- `Positioned_SetMoveCurveTime` `0x141dde3f0`(pos, t, e): `MoveCurve_SetTime` on both.
- `MoveCurve_Load` `0x141ecc540`(C, meta, s, e): `C.meta = meta; loop = meta+0x2c; flags; [9] = ms/1000;
  SetTime(C, s, e); if has data: if [0]==0: log, has=0 else [3] = [1], [4] = Value(e); else [3] = s, [4] = e;
  [5] = e; [6] = e - s`.
- `MoveCurve_SetTime` `0x141ecc710`(C, t, e): `[2] = [8] = t; [7] = e - t; if has: [1] = Value(t),
  [0] = Value(e) - [1] else [0] = e - t`.
- `MoveCurve_Value` `0x141eccb30`(C, t): segments -> `SegmentValue(t, [9], meta)`; positions ->
  `LinearValue(t, [9], meta)`.
- `MoveCurve_LinearValue` `0x141ecccc0`(t, T, meta): `n = #positions; if t < 0: 0;
  loops = floor(t/T); x = (n-1) * (fmod(t,T)/T); i = floor(x) (clamped 0..n-1), j = i+1 (clamped);
  p[i] + (p[j]-p[i])*(x-i) + (p[n-1]-p[0])*loops`. Same as `motion_data::Curve::value`.
- `MoveCurve_SegmentValue` `0x141ecd190`: `x = (fmod(t,T)/T) * (frames-1)`, walk segments by
  `#table-1` frames, `(lerp(table[k], table[k+1] or 1.0)) * seg+0x28 + seg+0x2c + floor(t/T) * meta+0x68`.
  Not used by the unarmed rolls (segment count 0).
- `MoveCurve_Advance` `0x141ecc780`(C, dt, r, out, stopSeg): `x = loop ? dt : [7]*r*dt`;
  no data: `[8] += x; return dt*r`; positions only: `old = Value([8]); [8] += x;
  return (Value([8]) - old) / [0]`; segments: rescaled by `[6]/[7]`, `[9]/[6]`, per-segment rate
  `+0x30`, `stopSeg` (not used for the roll).
- Caller `Line_Advance` `0x141ec82e0`(L, dt): `acc = dt + L+0x90; L+0x90 = acc; L+0x7c += acc;
  if L+0x60: r = L+0x78 > 0 ? L+0x78 : L+0x74; f = Advance(C, acc, r, 0, L+0x64);
  L+0x98 = f > 0 ? r*acc/f : 1; dist = L+0x78 <= 0 ? L+0x6c*f : (L+0x74/L+0x78)*f*L+0x6c;
  L+0x90 = 0; L+0x88 += dist; L+0x80 += dist`.
- `Line_Setup` `0x141ec86a0`(.., speed): `L+0x6c = |end - start|`, `L+0x70 = len/speed`,
  `L+0x74 = speed/len`, `L+0x78 = 0`, `L+0x64` = stop segment.

**Distance per frame (roll, positions branch):** with the line from `Step` (len = |target - start|,
speed = left/Tleft, `C` restarted at elapsed `t`, `[7] = Tlen - t`):
`x = (Tlen - t) * (speed/len) * dt = rate*dt*left/len`; `f = (C(t+x) - C(t)) / (C(Tlen) - C(t))`;
step = `len * f`. When `len == left` (open ground, no clip), `x = rate*dt` and the line covers exactly
the curve fraction of the remaining distance. With the optional length (`L+0x78 = speed/|real target|`):
`x` uses the real target's pace and `dist = |real| * f`, so the 300-cell line runs at the real pace.

**Animation time** (`ac` = AnimationController, its player at `ac+0x180`): `AnimationController_Tick`
`0x141d44e10`(ac, dt) (component vtable `0x1434c0518`): pending seek `ac+0x220` -> `0x141d46800`;
then `AnimPlayer_Advance` `0x141d44fb0`(ac+0x180, ac, dt):
```
ac+0x1c0 += dt
r = ac+0x178; if r != 0 && ac+0x1d4: r = 1; r *= ac+0x1b0
t_new = min(r*dt + ac+0x1a4, ac+0x1bc - ac+0x1b8)
while ac+0x1ac /*next event time*/ <= t_new: fire event (0x141d45c30) ... (end of clip: next queued
      animation 0x141d44560, loop, or 0x141d3a690(.., 0xe018) restart)
ac+0x1a4 = t_new
```
So **elapsed += dt * ac+0x178 * ac+0x1b0** (ac+0x178 forced to 1 by `ac+0x1d4`), clamped at the clip end.
Rate setters: `0x141d46c80` (`+0x1b0`), `0x141d46ee0` (`+0x178`).

## 4. Sprint switch, optional length, end

### `DodgeRoll_OnAnimationEvent` `0x141aa89d0` (event id `0xb91f` at event `+0x38`)
```
if 0x141b76f50(act) /* stat 0x596b == 0 && !actor+0x916 && (actor+0x2a2 & 0x20) && actor+0x915 */:
    child = act vfunc +0x7a0(act); act+0x448 = child; start it (0x14197c310); DodgeRoll_StartSprint(child)
if !act+0x448 && stat(0x5f2f):                       // DodgeRollMoveCancel
    act+0x462 = Player+0x20c ? (axes != 0) : (Player+0x22c != 0 /*pending Move*/)
    if act+0x462: anim = act animation list[6 + part+0x3f] (0x14196f960);
        DodgeRollMove_SwitchAnimation(part, anim, keep = act+0x461 && part+0x3f, (act+0x468, 1))
if part+0x3f && act+0x461 && (act+0x448 || act+0x462):
    clear act+0x240, +0x244, +0x258, +0x268; pos+0x1e3 = 1; facing += pi (0x141ddc820)
Action_OnAnimationEvent(act, ev)
```
The 0.5 s (`t0+15`) sprint moment is this animation event; its time is in the animation's event list,
not in code.

### `DodgeRoll_StartSprint` `0x141aa92e0`(child)
Creates the sprint part (factory `DAT_1445d8508`, parts list type `0x15`, `child+0x438`);
**`child+0x430 (part) +0x44 = 300, +0x48 = 1`** (literal 300, one 8-byte store);
anim index = `(stat 0x4862 is_floating ? 8 : 4) + part+0x3f` (4/5 = `_sprinting`, 8/9 floating);
optional effect when `DAT_1445c995c`; `DodgeRollMove_SwitchAnimation(part, anim, 0, (child+0x468, 1))`;
sprint part `vfunc +0xa0(part+0x3f)` (`0x141b76fc0`).

### `DodgeRollMove_SwitchAnimation` `0x141b8cd50`(part, anim, keep, opt)
Gets the new clip's meta (`0x141e55510`, `0x141d37ae0`); if found: `part+0x30 = meta`;
`frac = ac+0x1a4 / Tlen`; plays the clip from the same fraction (`0x141d2c560`, `0x141d44560`, rate
`ac+0x1b0`, `opt` passed to the clip build); `DodgeRollMove_ReloadCurve(part)`; `if keep: part+0x3e = 0`.
So the roll continues on the new curve at the same normalised time; `C[3]` = C_new(0).

### `DodgeRoll_OnEnd` `0x141aa8ef0`
```
base end (0x14197a9f0)
DodgeRollMove_Stop(part): Line stop 0x141de4c30(pos); part+0x3d = 0; pos+0x1e3 = 1 if !part+0x5d or part+0x3f
if act+0x448 && its sprint part:
    if act+0x468 == 1 && !part+0x3f: actor+0x90c = 0x1401913e0(0.5)
    sprint part vfunc +0xa8(part+0x3f && !act+0x461)        // sprint start 0x141b77110
    return
if part+0x3f && act+0x461 && !act+0x462: facing += pi (0x141ddc820) + notify
pos+0x200 = 0; pos+0x1e7 &= ~1
```
`act+0x461` = (`0x141e531e0(actor, "Standing")` == actor `+0x2be`), written once in `DodgeRoll_OnStart` at 0x141aa87ca. By replay it is false in every recorded session (crazy-keys 2026-11-03 f4079-4112 wall roll: client facing stayed 4.712 through the sprint switch, the line at the 0x64 axes (388,388) went (691,646)>(903,434) L299.8; official seg1/seg2 unchanged). So a backward roll never turns around at the sprint event nor at a non-sprint end, the target window stays open after the switch, and the sprint start at the roll's end turns a backward roll (`vfunc +0xa8(part+0x3f && !act+0x461)`; user test 2 f2398 0.829 -> 3.970). Stance `+0x2be` writers: 0x141e52d10 (set stance; callers 0x14140b8ab, 0x1421476cb, 0x14200c4e8, 0x141e52d03, 0x14214ae8d in the message handler 0x1421497c0). Ruled out: "a turned roll closes its target window" (crazy-keys f5885).

`act vfunc` `0x141aa8d60`: orientation answer (`0x5346` buff -> 1 or 2 when backward; backward -> 0;
attack-ready -> 3).

### Roll length
`dodge_unarmed_01`, `_bwd_01`, `_01_sprinting`, `_bwd_01_sprinting` in `basedodgeroll/onerig.amd`:
`once`, **1000 ms**, a `0` line, 61 positions (0 .. 500, -500, 638.838, -638.837), 0 segments.
At rate 1 and dt 1/30 the clip ends after 30 frames: the 30-frame action.

## What the loader (`motion_data.rs`) lacks
- The rate: the port must keep an animation clock `elapsed += dt * rate`, `rate = ac+0x178 * ac+0x1b0`
  (skill/action speed), clamped to the clip end; speed and the curve restart use it.
- `_moving` variants (`dodge_unarmed_01_moving`, `_bwd_01_moving`) for MoveCancel (stat `0x5f2f`), and
  floating sprint variants (index 8/9; names unread).
- The clip chosen by weapon set (`dodge_<set>_01...`, 42 sets in the file), not only unarmed.
- Segments (count line after the positions) and `meta+0x68` for segment curves (none for unarmed).
- The animation event time (`0xb91f`) that starts the sprint, from the animation's event data (`.ast`?).

## Start order, end, re-aim (checked by replay)
- **Start order:** `Actor_InstallQueuedMove` `0x141e41c60` snaps, then `0x141e4ea40`: a running Move (`+0x2a0` bit 7) with `vf50 == 0` gets `Actor_EndMoveAction(A, 1)` (next-tick stop `0x141de4c30`, path ended, curves cleared), and only then `0x141e4ecc0` starts the action. So the path's end does not clear the roll's curve.
- **End:** the end of the clip ends the action in the Animated tick (inferred: 31st tick, f913; the Actor tick of that frame plans the walk).
- **Vtable** `0x143427ab0`: `+0x30` `DodgeRoll_OnEnd`, `+0x130` `0x141aa8ed0` -> `0x141b8c6a0` (**set heading**: `part+0x40 = ang(target - grid)`), `+0x1a0` `DodgeRoll_OnStart`, `+0x1c0` update `0x141a3b010` -> `0x141974090` (base update).
- **Re-aim by axes:** `0x14197d060(act)`, from the base update, needs action `+0x240`: stat `0x479e` `dynamic_target_updating_prioritises_movement_vector` with axes != 0 -> `target = grid + floor(axes*0.092)`, `0x14197cf50(act, target)`, `act+0x24d = 1`; else stat `0x479d` `dynamic_target_updating_uses_movement_vector` with axes != 0 and Player `+0x214` != the skill -> same without `+0x24d`. Condition around the call in `0x141974090` (`0x141974813`) unread; replay fits "every frame, before the part's tick".
- **Re-aim by `0x1af`:** `0x141e5b250` -> if `act+0x240` and `!act+0x24d`: `0x14197cf50`. So a key held locks out the cursor.
- `0x14197cf50(act, target)`: with `+0x244 > 0`, `+0x260 +0x74 > 0`, `+0x268 > 0` or `+0x26c > 0` it only stores `+0x250`, `+0x258 = 1`; else `vf130(target)`, then `vf138` -> `0x141971b80`.
- **Stat listener** `DodgeRoll_OnStatChanged` `0x141b8d4f0` (slot `+0xc0` of `0x143454070`, `this = part+0x18`; renamed in Ghidra): with `part+0x5f`: `ac+0x1b0` = `(1+stat(0xec)/1e4) / (1+stat at start/1e4) * ((int)((sqrt(1+stat at start/1e4) - 1)*100)/100 + 1)`, times the controller rate `1+action%/100`. Its buff `0xab2` test and the `part+0x3e` new line (a new line from the running line's end at `DodgeRollMove_Speed`) are not ported; the rest is ported.

## Facing, event, first heading (checked by replay)
- **Facing at start:** `0x141e4ea40`: when the queued action's vf `+0x340` is true and its target != grid, facing = `ang(target - grid)` before the running Move ends and before `InitHeading`. So a key-held roll with the cursor at least 90 degrees from the keys is a backward roll (`_bwd_` clip); this was the old "float drift" (rolls f1133.. of the reference capture). `+0x8fa` is set for the player in that capture (backward rolls exist). `vf+0x340` (0x1413ca570) = (`vf+0x348() != 2*pi`) and gates the facing turn in 0x141e4ea40. Slot `+0x348` is 0x14197e160: it returns 2*pi (const 0x14360c40c) when `act+0x142` bit 4 is clear and Actor `+0x2b4` != 0 and equals the skill id `act+0xf8 -> +0x40`, or when stat 0x46a7 (18087) is 0; else stat 0x46a7 * pi (0x14360c2ec) / 180 (0x14360ca90). Writer of Actor `+0x2b4`/`+0x2b8`: 0x141e45250 (an action ended, ~95 callers) copies {slot-0 action (`+0x238`) skill id, or 0 when the slot is empty; timer 0} at 0x141e452fb, then starts the queued action and Actor_StartWasdWalk. The Actor tick adds dt to `+0x2b8` and clears `+0x2b4` at >= 15.0 (0x141e4462e, 0x14360c508). Measured (crazy-keys run 2026-11-03-224516, flip test `runtime/replay/flipcmp.sh`): a plain 15 s memory of every roll end is wrong (replays much worse); the kept rule (queued roll, roll in the SprintEnd clip) is right for ~22 of 24 checked rolls. Open exceptions: f5111 (roll 3 frames after a plain roll end with a WASD walk running: client forward roll with the walk facing 2.356, model backward; forward matches the client's first line exactly, dist 3.6424 len 24.7938) and f5170 (cursor roll 29 frames after a sprint end: the client's line matches a backward curve with the turned facing, so its heading source differs from the model's `ang(round(unit*3))`). Which calls of 0x141e45250 store the roll's id is unread. Fitted by replay: (1) a roll queued into a running roll keeps the facing (user test 4 f2319: client facing 0.0 stays, forward roll, target (388,875) behind; the model used to go backward); (2) a roll that cuts the SprintEnd clip keeps the sprint's facing, and `DodgeRoll_InitHeading` 0x141b8bda0's |d| >= pi/2 test then gives a backward roll (`dodge_unarmed_bwd_01`) when rolling back against the sprint. Evidence for (2): user test 2 f2802 (keys and cursor up, sprint was going down: the client's roll line lengths fit the bwd curve to 0.0001 cells, the forward one is off by up to 0.027) and official seg1 f3578 (first frame len 42.2940 = bwd, forward gives 42.2676). A roll 3 to 450 frames after a roll's end does turn; a time window after the end made all replays worse (ruled out). Ported in `ClientSim::on_start_roll` (field `Roll.from_sprint_end`). Rule tests `a_roll_queued_into_a_roll_keeps_the_facing` and `a_roll_out_of_the_sprint_end_against_the_sprint_is_backward` in `modules/server/crates/poe-game/tests/rules.rs`.
- **Backward roll after the sprint event:** the rule is `act+0x461` above (false in every session), so a backward roll out of the SprintEnd clip stays backward after the sprint event (orientation 2, facing = line heading + pi) and turns around only at its sprint start at the end. Evidence: user test 3 f995-1002 (client facing stays 5.498 until the reversal, then 0.897, 2.231, 2.356; model equal, line ends (342,1095), (339,724)); user test 2 f2398 (0.829 -> 3.970). A reversal mid-roll hits the tie d = about -pi in the turn block 0x141974a90: with facing 5.4977875, d < -pi (constants 0x14360da2c = -pi, 0x14360c2ec = pi) so it wraps to +pi and the turn goes through the positive side. The old model flipped at the event and turned the other way (per-frame snaps f1001-1053). Rule test `a_backward_roll_out_of_the_sprint_end_stays_backward_after_the_event`.
- **Sprint switch needs Actor `+0x915`** (`0x141b76f50`): hook `player actions` lines of user test 3 show 915=1 at the roll's start with the key held (f1821), 915=0 after the release (f1824), still 0 after a new press during the roll (f1826, `2a2` back to 0x60), 1 at the next roll's start (f1851). So releasing and pressing again during a roll does not sprint; the press queues another roll. Writer of `+0x915` unread. Ported as `Roll.key_held` in ClientSim; rule test `a_key_pressed_again_during_a_roll_does_not_make_it_sprint`. The old model used only the key state and sprinted at f1836 (snaps f1837-1904).
- **Correction chain:** after a server correction the client sits on the corrected cell while the server's model keeps its sub-cell point, so per-frame snaps follow for about 50 frames (f1851-1904); fixing the first divergence removes the chain.
- **Event `0xb91f` is `sprint_start` at 0.5 s of the roll timeline: `AnimPlayer_Advance` sets `ac+0x1a4` = event time before firing, so the curve restarts at 0.5, not at the frame's elapsed. The switch to `_sprinting` runs if the key is held. A backward roll that sprints flips here: `pos+0x1e3 = 1`, facing += pi.
- **Target update (`GP_dodge_roll_base_01`, `StartTargetUpdateEventType` `3000 0 1` from time 0 to 1.0, `sprint_start` at 0.5; timeline `metadata/characters/timelines/base_dodge_roll/base_dodge_roll.atl`, UTF-16 JSON):** event type `0x1a` in `0x141979b60` sets `act+0x240` (window), `+0x244` = first value in radians per second, `+0x260` = the event. Before the window a `0x1af` only sets `act+0x150` (`0x141e5b250`). Inside it `0x14197cf50` stores `target - grid` at `act+0x250`, flag `+0x258` (vf `+0x140` false); each action update (`0x141974a90`) takes `e = grid + stored`, `want = ang(sign*off)` (`sign` = -1 when vf `+0x530`, `part+0x3f`, backward), `d` = wrapped `want - facing`; if `|d| > dt*rate`, `e = grid + sign*round(rot((0,-|off|), facing + clamp(d)))`. Then vf `+0x130` `0x141b8c6a0` sets the heading from `e`; vf `+0x138` is false (`0x140107b00`) so **the facing does not change**. Checked by f3545 (a 107 degree jump, 99 degrees per frame). The axes aim (`0x14197d060`) needs the same window. The window event at 0x14197a5f6..0x14197a625 sets `+0x240 = 1`, `+0x244`, `+0x268`, `+0x26c`, `+0x24c`, `+0x24d = 0` and calls 0x14197d060 at once. The event runs with the axes of before a `0x64` later in the same batch, so a roll out of a cursor walk (`0x1c8` before `0x64 (0,0)` in the batch, UseSkill flags 0x440) gets `+0x24d = 1` and ignores `0x1af` (0x141e5b250 checks `+0x24d`) until the sprint switch: user test 4 f4016-4030 (facing 2.583..2.923, line x end 485, equal to the model), steering again from f4031 (line end (537,1202)); the release at the sprint switch is by replay, code unread. Other mouse rolls with axes 0 before the start steer at once (f4088, f4174, f4371). Rule test `a_roll_started_with_the_axes_still_set_ignores_the_cursor_until_the_sprint`. 0x141e5b160 is the applicability check of `0x1af` (needs Actor `+0x2a0` bit 1, window `act+0x240`, not (`act+0x148` != 0 and `act+0x24c`), or vf `+0x300`; skill match via vf `+0x120`).
- **First heading of a cursor roll (no axes):** measured, 13 of 13 rolls (incl. the private `(28,-17)` case, which replaces the old "exact cursor point" reading) and float-exact in `clientsim`: heading = `ang(round(unit(target - grid) * 3))`. The first `0x1af` then aims at the exact integer target. **The code that does this is not found:** read how `act+0x150` or the heading gets the 3-cell vector. `DodgeRoll_InitHeading` (above) computes atan2 of `act+0x150 - grid` with no rounding, so `act+0x150` must hold `grid + round(unit*3)` when it runs: the exact target instead of the measured vector makes the replay far worse (seg1 grid_differ 175 -> 596). Who writes `act+0x150` is unread.
- **Move during a roll:** stays queued (`A+0x248`), starts in the Actor tick after the clip's end (f3429).
- `0x80410041` is the unarmed punch (a skill): it replaces a running roll, moves on a time-mode line towards its target, and a Move during its recovery walks slowed (Actor `+0x430`). Out of scope until the server sends skills; the offline replay follows the client log while one runs.
- **Sprint start plans twice:** the roll's end in the Animated tick starts a walk on the held axes at once, then the frame's `0x64` plans again; each plan makes its sprint turn (f2995, f3566, two `PATHPLAN` rows).
- **Clock of a queued roll:** a roll queued into a running roll starts at that clip's end in the frame's Animated tick; the tick plays the old clip out and only the rest of the frame's time goes to the new clip. User test 3 f1851 and test 4 f2319: old clip at 0.99, dt 0.033, new clip's `ac+0x1a4` = 0.023, so line time `T` (Tleft) = 0.977. Ported as `Roll.elapsed` starting at old elapsed - length (negative, -0.01) in `on_start_roll`; curve loaded at 0. Replay of test 4 is exact to the log's 4 decimals from f2320 (len 40.1932, 36.8011, 33.6587, 30.6421; T 0.95351, 0.92018, 0.88922, 0.85659) to the old server's snap at f2345. Fitted by replay, the code that carries the time is unread. First steps of such a roll: 3.8068, 3.3921 (rule test `a_roll_queued_into_a_roll_keeps_the_facing`).
- Ruled out: the hook's `LINE ... T=` field is the line time `len/speed` (`t_total`), not a clock, so its per-frame step varies per roll (0.0323..0.0336 in normal rolls, because len differs from `left` by the target's rounding); the earlier "queued roll clip rate 0.973, first curve time 0.0522" was misread from it and from `rollinv.py` (which uses len as left). Rate is 1.0.

## Not read / open

- `0x141ed0510` path storage order (is element `count-1` the first step?).
- Value and meaning of Actor `+0x8fa` for a normal player; object `0xe4fa`; `0x141f832b0`.
- `0x141b912d0` dynamic blockers; who sets `part+0xa0` (cells-travelled listener).
- Where `DodgeRollMove_Tick` is called from (act update vs. actor parts) and the AnimationController's
  tick order against Positioned/Actor in a frame (decides whether Speed sees this frame's elapsed).
- Stat names `0x5121`, `0x478c`, `0x10a2`, `0x596b`, `0x5f2f`, `0xec`; the `0xb91f` event's time.
- `Positioned_MoveToWaypoint` first step in the same frame (doc claim, not re-verified here).

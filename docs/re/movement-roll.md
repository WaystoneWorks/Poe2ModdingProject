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
- **Stat listener** `0x141b8d4f0` (slot `+0xc0` of `0x143454070`, `this = part+0x18`): with `part+0x5f`: rate `0x141d46c80` = `(1+stat(0xec)/1e4) / (1+part+0x38/1e4) * ((int)((0x14020af80(1+part+0x38/1e4) - 1)*100)/100 + 1)`; with `part+0x3e` set: a new line from the running line's end at `DodgeRollMove_Speed`. Not ported yet.

## Not read / open
- **Float drift in `clientsim`:** rolls f883..f1081 of the reference capture match the client's `p`, `len`, `acc` to 0.002; from f1133 the first advance is 0.7% short in the client (3.7065 against 3.7329 cells), as if `ac+0x1a4` or the rate differed. Something between f1097 and f1133 persists; it flips rounding (f1192, f1282, f1375 snap).
- `0x141ed0510` path storage order (is element `count-1` the first step?).
- Value and meaning of Actor `+0x8fa` for a normal player; object `0xe4fa`; `0x141f832b0`.
- `0x141b912d0` dynamic blockers; who sets `part+0xa0` (cells-travelled listener).
- Where `DodgeRollMove_Tick` is called from (act update vs. actor parts) and the AnimationController's
  tick order against Positioned/Actor in a frame (decides whether Speed sees this frame's elapsed).
- Stat names `0x5121`, `0x478c`, `0x10a2`, `0x596b`, `0x5f2f`, `0xec`; the `0xb91f` event's time.
- `Positioned_MoveToWaypoint` first step in the same frame (doc claim, not re-verified here).

# Dodge roll, local player (exact-port spec, 0.5.5f)

Exact-port spec for the roll: start, per-frame step, curves, sprint switch, end. Overview: [wasd-movement.md](wasd-movement.md); siblings: [positioned](movement-positioned.md), [click](movement-click.md), [sprint](movement-sprint.md).

All addresses 0.5.5f. `pos` = Positioned (`entity+0x98`), `actor` = Actor, `act` = the DodgeRoll action
(class vtable `0x14343cdb8` region), `part` = the roll movement part (0xb8 bytes, vtable `0x143469100`,
`act+0x430`), `ac` = AnimationController component (`part+0x28`), `C` = movement curve run at `pos+0x2a8`
(second copy at `pos+0x330`), `L` = path line at `pos+0x208` (so `C = L+0xa0`).
Helpers: `round(x)` = `0x140525880` = floor(x+0.5); `floor` = `0x140168860`; `rot(v,a)` = `0x1421a6580`
= (x cos a - y sin a, x sin a + y cos a); `wrap(a)` = fmod(a, 2pi) (`0x140a3d1b0`), +2pi if < 0;
`ang(d)` = wrap(atan2(d.y, d.x) + pi/2) (`0x142c54448` = atan2f(y,x)); `len_i(v)` = `0x14016cb50` =
sqrt(x*x+y*y) of an int2; `clamp01` = `0x14010c5d0`; `max` = `0x1401528b0`. Names below are set in Ghidra.

## Part layout (`part`)
`+0x08` act; `+0x20` path search scratch (0x478, `0x141ee1a00`; `+0x450` waypoint count, waypoints at
`+0x04 + 8*i`, `+0x474..+0x477` search flags, `+0x475` = search "strict" flag); `+0x28` ac; `+0x30` curve
metadata (`0x141d44560(ac+0x180, ac+0x190)`); `+0x38` stat `0xec` (int); `+0x3c` steering on (init 1);
`+0x3d` curve loaded; `+0x3e` waiting for a running line; `+0x3f` backward; `+0x40` heading (rad);
`+0x44` optional line length (int), `+0x48` its has-flag; `+0x4c` total distance (int); `+0x50` whole
cells reported; `+0x54..+0x63` the 16-byte start block (below); `+0xa0` cells-travelled listener
(vfunc `+0x10(&delta)`); `+0xa8`, `+0xb0` delegate slots on pos/actor.
Constructor (in `DodgeRoll_OnStart` and clone `0x141b99e10`): `+0x3c` dword = 1, `+0x40` = 0, `+0x48` = 0,
`+0x4c..+0x5b` = 0, `+0x5c` = 0x0101, `+0x61` = 0, `+0xa0..+0xb7` = 0.

## 1. Start (`0x1c8` -> action start)

### `DodgeRoll_OnStart` `0x141ab54e0` (act vfunc in `0x14343cdb8`)
```
pos+0x1fc = (pos+0x1f8 /*level*/, 1); grid rebuild (0x141d1c720); pos+0x200 = 1   // search level fixed now
act+0x45c = int(sqrt(1 + stat(0xec)/10000) * stat(0x57fa))      // 0x141ab6230, dodge_roll_travel_distance
blk = { +0x00 int act+0x45c, +0x04 byte stat(0x5121), +0x05 stat(0x5121)?3:0, +0x06 stat(0x478c)!=0,
        +0x07 0, +0x08 1, +0x09 1, +0x0a 1 (-> part+0x5e), +0x0b 1, +0x0c ?, +0x0d 0 }
part = new 0xb8; act parts list += {type 8, part}; act+0x430 = part
DodgeRoll_InitHeading(part, &blk, &cb)            // copies blk to part+0x54..+0x63
FUN_141a49ea0(act)                                // base action start (animation)
DodgeRollMove_Start(part)
pos+0x1e7 |= 1
actor vfunc +0xd0; act+0x461 = (actor "Standing" lookup 0x141e610d0 == actor+0x2be)
```
So **`part+0x5e` is always 1 for DodgeRoll** (constant in `blk`); `+0x5c` = 1 (play rate restart),
`+0x5d` = 1 (orientation handling), `+0x58/+0x59` path level flags, `+0x5a` strict search.

### `DodgeRoll_InitHeading` `0x141b99fb0`
```
part+0x54..+0x63 = blk
if actor && (actor+0x400 != 0 || actor+0x404 != 0) && part+0x5e:
    c = (floor(ax*0.092), floor(ay*0.092))   // 0x1421a30f0 on float(axes); ints
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
Constants `0x143621d4c` = pi/2, `0x143622034` = 2pi, `0x14362365c` = -pi, `0x143621f14` = pi.

**Actor `+0x8fa`** (byte; when it changes: `actor+8 -> +0x8d |= 8`, `actor+0x10 = 1`, and if `actor+0x2a0`
bit 7: re-choose move animation `0x141e5d750(actor, -1)`; it selects move animation `0xc3` in
`0x141e5d640`). Writers:
- `0x141de1050` (listener, vtable `0x1433b9068`, `this-0x170` = entity): `+0x8fa = (arg4 == 0) ||
  no entity sub-object 0xe4fa (0x141e8b690(entity+0x58, 0xe4fa)) || 0x141f918d0(it) ||
  slot-0 action type == 0x62e`.
- `0x141f910b0`: `+0x8fa = (actor animation-set name 0x141e696e0 == global string 0x14472b958)`.
- `0x141ddd180` (`0x141ddd7bf`): sets 1 under a `+0x70` condition.
- Action start `0x141c0b270` (a charge-type action; random direction when its target is its own cell)
  sets 1; `0x141c53b50` (another action's end, unless `+0x144` bit 1) sets 0.
Meaning not settled: looks like a "strafe / face-the-aim" stance flag (true when the entity has no `0xe4fa`
object). Its value for an unarmed player was not read: log `actor+0x8fa` at a roll start (x64dbg/hook).

### `DodgeRollMove_Start` `0x141b9a1b0` (first step, same call)
```
part+0x28 = ac; part+0x30 = curve meta of ac's current animation
if part+0x5c && actor+0x388 list entry: replay the animation with rate ac+0x1b0 (0x141d51990)
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

### `DodgeRollMove_Tick` `0x141b9a930` (part vfunc `+0x48`)
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
A blocked step clears `part+0x3d`: Positioned "blocked" delegates `0x141dfd170` -> listener vtable `0x143468e20` `+0x10` `0x141b9b6f0` (`this` = part+0x10). The roll then makes no more lines until `ReloadCurve` (`part+0x3e` path or the sprint switch).

### `DodgeRollMove_ReloadCurve` `0x141b9b650`
`Positioned_SetMoveCurve(pos, part+0x30, 0, Tlen)`; `Positioned_SetMoveCurveTime(pos, ac+0x1a4, Tlen)`;
`part+0x3d = 1`. (Here `C[3]` = C(0).)

### `DodgeRollMove_DistanceLeft` `0x141b9b180`
`v = pos+0x2d1 ? MoveCurve_Value(C, C[8]) : pos+0x2c8`;
`left = (1 - clamp01((v - C[3]) / (C[4] - C[3]))) * float(part+0x4c)`.

### `DodgeRollMove_Speed` `0x141b9b980`
```
r = ac+0x178; if r != 0 && ac+0x1d4: r = 1; r *= ac+0x1b0
if r == 0: return 0
Tleft = Tlen / r - ac+0x1a4 / r
if Tleft == 0: log "exactly at end of animation"; return 0
return DistanceLeft / Tleft
```

### `DodgeRollMove_Goal` `0x141b9b400` -> (goal, flag)
```
scratch+0x475 = stat(0x10a2) != 0 || part+0x5a
v = rot((0, -max(left, 10)), part+0x40)
if !0x141b95790(pos): g = cell + (round(v.x), round(v.y))
else:                 P = line point (0x141ed6400(pos+0x208)); g = (round(P.x+v.x), round(P.y+v.y))
flag = 0
if !scratch+0x477:
    ok = 0x141ede540(&g, scratch[0], scratch+0x458, scratch+0x475, scratch+0xc, scratch+0x450,
                     scratch+0x476, &flag, scratch+8, 0, scratch+0x474)
    if ok: return (*(int2*)(scratch + 8*count - 4), flag)     // element count-1 of the waypoint array
if count < 2: return (cell, flag)
return (*(int2*)(scratch + 8*count - 4), flag)
```
Which end of the path element `count-1` is (first step or goal) depends on `0x141ede540`'s storage
order; the earlier note "first waypoint" is consistent if the path is stored goal-first. Unverified.

### `DodgeRollMove_Target` `0x141b9b210`(part, goal)
```
left = DistanceLeft (no max with 10)
if !0x141b95790(pos): a = ang(float(goal - cell)); t = cell + round(rot((0,-left), a))
else: P = line point; a = ang(float(goal) - P); t = round(P + rot((0,-left), a))
```

### `DodgeRollMove_Step` `0x141b9aa00`
```
goal, flag = Goal(part); target = Target(part, goal)
d = sqrt(|goal.x-cell.x|^2 + |goal.y-cell.y|^2)
if 0.0 > d: return                 // 0x140135140 reads a local set to 0.0: never true (dead check)
speed = Speed(part)
if speed == 0:
    if pos+0x28c == 0 || (pos+0x1e5 & 0x80): return
    part+0x3e = 1; Positioned_Stop(pos) /*0x141df2040*/; return
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
Positioned_MoveToWaypoint(pos, {&target, speed, 0x7fffffff, cbs, 0, word 0x14306fb50, 0,
                                (part+0x59, 1), part+0x58, word part+0x60, 0})
if part+0x48: pos+0x280 = k (L+0x78); pos+0x318 = k
part+0x3e = 0
```
**The 1.6-cell stop is not a constant**: it is `counter`. The walk must pass 2 cells other than the start
without a block, so a target within 1 Bresenham step (max(|dx|,|dy|) < 2) makes no line, as does a
block in the first 2 cells. With `left > 1` in Tick this gives the measured 1.41..2.

### `DodgeRollMove_CheckClearCells` `0x141b9e030`(from, to, ctx{part, pos, &counter})
Bresenham over the major axis from `from` to `to` inclusive (err starts at -major/2, err += minor;
if err > 0: minor step, err -= major). For each cell p:
```
lvl = (int)(char)pos+0x1f8 + 1
if lvl != 0 && (walk(p, mode 0) /*0x141d1a980*/ < lvl || 0x141b9ed20(grid, p, lvl)): return false
if p != pos cell: if --counter < 1: return false
```
`0x141b9ed20(grid, p, lvl)`: locks `grid+0x140`, scans the buckets of the dynamic-object hash
(`grid+0x28`, 0x38 per bucket, width `grid+0x18`, height `grid+0x20`) in the box
`p +- (lvl - 2 + grid+0x138)` (clamped, `0x14016cd20(.., 0x17)` = to bucket coords) and returns true when
`0x141b9f4e0(bucket, ...)` reports a blocker. Not read: `0x141b9f4e0` (which objects block; the server
can treat it as "no dynamic blockers" until monsters/objects block rolls).

### `DodgeRollMove_ClipToWalkable` `0x141b9e270`(from, to, ctx{part, pos+0x1e8, pos, &out})
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

- `Positioned_SetMoveCurve` `0x141deb240`(pos, meta, s, e): s,e finite and >= 0 -> `MoveCurve_Load(C2 =
  pos+0x330 too)`; otherwise logs and loads (0, 0). Both `pos+0x2a8` and `pos+0x330`.
- `Positioned_SetMoveCurveTime` `0x141deb5a0`(pos, t, e): `MoveCurve_SetTime` on both.
- `MoveCurve_Load` `0x141eda570`(C, meta, s, e): `C.meta = meta; loop = meta+0x2c; flags; [9] = ms/1000;
  SetTime(C, s, e); if has data: if [0]==0: log, has=0 else [3] = [1], [4] = Value(e); else [3] = s, [4] = e;
  [5] = e; [6] = e - s`.
- `MoveCurve_SetTime` `0x141eda740`(C, t, e): `[2] = [8] = t; [7] = e - t; if has: [1] = Value(t),
  [0] = Value(e) - [1] else [0] = e - t`.
- `MoveCurve_Value` `0x141edab60`(C, t): segments -> `SegmentValue(t, [9], meta)`; positions ->
  `LinearValue(t, [9], meta)`.
- `MoveCurve_LinearValue` `0x141edacf0`(t, T, meta): `n = #positions; if t < 0: 0;
  loops = floor(t/T); x = (n-1) * (fmod(t,T)/T); i = floor(x) (clamped 0..n-1), j = i+1 (clamped);
  p[i] + (p[j]-p[i])*(x-i) + (p[n-1]-p[0])*loops`. Same as `motion_data::Curve::value`.
- `MoveCurve_SegmentValue` `0x141edb1c0`: `x = (fmod(t,T)/T) * (frames-1)`, walk segments by
  `#table-1` frames, `(lerp(table[k], table[k+1] or 1.0)) * seg+0x28 + seg+0x2c + floor(t/T) * meta+0x68`.
  Not used by the unarmed rolls (segment count 0).
- `MoveCurve_Advance` `0x141eda7b0`(C, dt, r, out, stopSeg): `x = loop ? dt : [7]*r*dt`;
  no data: `[8] += x; return dt*r`; positions only: `old = Value([8]); [8] += x;
  return (Value([8]) - old) / [0]`; segments: rescaled by `[6]/[7]`, `[9]/[6]`, per-segment rate
  `+0x30`, `stopSeg` (not used for the roll).
- Caller `Line_Advance` `0x141ed6310`(L, dt): `acc = dt + L+0x90; L+0x90 = acc; L+0x7c += acc;
  if L+0x60: r = L+0x78 > 0 ? L+0x78 : L+0x74; f = Advance(C, acc, r, 0, L+0x64);
  L+0x98 = f > 0 ? r*acc/f : 1; dist = L+0x78 <= 0 ? L+0x6c*f : (L+0x74/L+0x78)*f*L+0x6c;
  L+0x90 = 0; L+0x88 += dist; L+0x80 += dist`.
- `Line_Setup` `0x141ed66d0`(.., speed): `L+0x6c = |end - start|`, `L+0x70 = len/speed`,
  `L+0x74 = speed/len`, `L+0x78 = 0`, `L+0x64` = stop segment.

**Distance per frame (roll, positions branch):** with the line from `Step` (len = |target - start|,
speed = left/Tleft, `C` restarted at elapsed `t`, `[7] = Tlen - t`):
`x = (Tlen - t) * (speed/len) * dt = rate*dt*left/len`; `f = (C(t+x) - C(t)) / (C(Tlen) - C(t))`;
step = `len * f`. When `len == left` (open ground, no clip), `x = rate*dt` and the line covers exactly
the curve fraction of the remaining distance. With the optional length (`L+0x78 = speed/|real target|`):
`x` uses the real target's pace and `dist = |real| * f`, so the 300-cell line runs at the real pace.

**Animation time** (`ac` = AnimationController, its player at `ac+0x180`): `AnimationController_Tick`
`0x141d51d70`(ac, dt) (component vtable `0x1434daba0`): pending seek `ac+0x220` -> `0x141d53760`;
then `AnimPlayer_Advance` `0x141d51f10`(ac+0x180, ac, dt):
```
ac+0x1c0 += dt
r = ac+0x178; if r != 0 && ac+0x1d4: r = 1; r *= ac+0x1b0
t_new = min(r*dt + ac+0x1a4, ac+0x1bc - ac+0x1b8)
while ac+0x1ac /*next event time*/ <= t_new: fire event (0x141d52b90) ... (end of clip: next queued
      animation 0x141d514c0, loop, or 0x141d47110(.., 0xe018) restart)
ac+0x1a4 = t_new
```
So **elapsed += dt * ac+0x178 * ac+0x1b0** (ac+0x178 forced to 1 by `ac+0x1d4`), clamped at the clip end.
Rate setters: `0x141d53be0` (`+0x1b0`), `0x141d53e40` (`+0x178`).

## 4. Sprint switch, optional length, end

### `DodgeRoll_OnAnimationEvent` `0x141ab59b0` (event id `0xb91f` at event `+0x38`)
```
if 0x141b85160(act) /* stat 0x596b == 0 && !actor+0x916 && (actor+0x2a2 & 0x20) && actor+0x915 */:
    child = act vfunc +0x7a0(act); act+0x448 = child; start it (0x141987670); DodgeRoll_StartSprint(child)
if !act+0x448 && stat(0x5f2f):                       // DodgeRollMoveCancel
    act+0x462 = Player+0x20c ? (axes != 0) : (Player+0x22c != 0 /*pending Move*/)
    if act+0x462: anim = act animation list[6 + part+0x3f] (0x14197acc0);
        DodgeRollMove_SwitchAnimation(part, anim, keep = act+0x461 && part+0x3f, (act+0x468, 1))
if part+0x3f && act+0x461 && (act+0x448 || act+0x462):
    clear act+0x240, +0x244, +0x258, +0x268; pos+0x1e3 = 1; facing += pi (0x141de99d0)
Action_OnAnimationEvent(act, ev)
```
The 0.5 s (`t0+15`) sprint moment is this animation event; its time is in the animation's event list,
not in code.

### `DodgeRoll_StartSprint` `0x141ab62c0`(child)
Creates the sprint part (factory `DAT_1445f0918`, parts list type `0x15`, `child+0x438`);
**`child+0x430 (part) +0x44 = 300, +0x48 = 1`** (literal 300, one 8-byte store);
anim index = `(stat 0x4862 is_floating ? 8 : 4) + part+0x3f` (4/5 = `_sprinting`, 8/9 floating);
optional effect when `DAT_1445e15bd`; `DodgeRollMove_SwitchAnimation(part, anim, 0, (child+0x468, 1))`;
sprint part `vfunc +0xa0(part+0x3f)` (`0x141b851d0`).

### `DodgeRollMove_SwitchAnimation` `0x141b9af60`(part, anim, keep, opt)
Gets the new clip's meta (`0x141e63400`, `0x141d44560`); if found: `part+0x30 = meta`;
`frac = ac+0x1a4 / Tlen`; plays the clip from the same fraction (`0x141d38fe0`, `0x141d514c0`, rate
`ac+0x1b0`, `opt` passed to the clip build); `DodgeRollMove_ReloadCurve(part)`; `if keep: part+0x3e = 0`.
So the roll continues on the new curve at the same normalised time; `C[3]` = C_new(0).

### `DodgeRoll_OnEnd` `0x141ab5ed0`
```
base end (0x141985d50)
DodgeRollMove_Stop(part): Line stop 0x141df1e90(pos); part+0x3d = 0; pos+0x1e3 = 1 if !part+0x5d or part+0x3f
if act+0x448 && its sprint part:
    if act+0x468 == 1 && !part+0x3f: actor+0x90c = 0x1401970e0(0.5)
    sprint part vfunc +0xa8(part+0x3f && !act+0x461)        // sprint start 0x141b85320
    return
if part+0x3f && act+0x461 && !act+0x462: facing += pi (0x141de99d0) + notify
pos+0x200 = 0; pos+0x1e7 &= ~1
```
`act+0x461` = (`0x141e610d0(actor, "Standing")` == actor `+0x2be`), written once in `DodgeRoll_OnStart` at 0x141ab57aa. By replay it is false in every recorded session (crazy-keys 2026-11-03 f4079-4112 wall roll: client facing stayed 4.712 through the sprint switch, the line at the 0x64 axes (388,388) went (691,646)>(903,434) L299.8; official seg1/seg2 unchanged). So a backward roll never turns around at the sprint event nor at a non-sprint end, the target window stays open after the switch, and the sprint start at the roll's end turns a backward roll (`vfunc +0xa8(part+0x3f && !act+0x461)`; user test 2 f2398 0.829 -> 3.970). Stance `+0x2be` writers: 0x141e60c00 (set stance; callers 0x14141416b, 0x142156a6b, 0x14201ac28, 0x141e60bf3, 0x14215a22d in the message handler 0x142158b60). Ruled out: "a turned roll closes its target window" (crazy-keys f5885).

`act vfunc` `0x141ab5d40`: orientation answer (`0x5346` buff -> 1 or 2 when backward; backward -> 0;
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
- **Start order:** `Actor_InstallQueuedMove` `0x141e4fa60` snaps, then `0x141e5c930`: a running Move (`+0x2a0` bit 7) with `vf50 == 0` gets `Actor_EndMoveAction(A, 1)` (next-tick stop `0x141df1e90`, path ended, curves cleared), and only then `0x141e5cbb0` starts the action. So the path's end does not clear the roll's curve.
- **End:** the end of the clip ends the action in the Animated tick (inferred: 31st tick, f913; the Actor tick of that frame plans the walk).
- **Vtable** `0x14343cc18`: `+0x30` `DodgeRoll_OnEnd`, `+0x130` `0x141ab5eb0` -> `0x141b9a8b0` (**set heading**: `part+0x40 = ang(target - grid)`), `+0x1a0` `DodgeRoll_OnStart`, `+0x1c0` update `0x141a47ff0` -> `0x14197f3f0` (base update).
- **Re-aim by axes:** `0x1419883c0(act)`, from the base update, needs action `+0x240`: stat `0x479e` `dynamic_target_updating_prioritises_movement_vector` with axes != 0 -> `target = grid + floor(axes*0.092)`, `0x1419882b0(act, target)`, `act+0x24d = 1`; else stat `0x479d` `dynamic_target_updating_uses_movement_vector` with axes != 0 and Player `+0x214` != the skill -> same without `+0x24d`. Condition around the call in `0x14197f3f0` (`0x14197fb73`) unread; replay fits "every frame, before the part's tick".
- **Re-aim by `0x1af`:** `0x141e69140` -> if `act+0x240` and `!act+0x24d`: `0x1419882b0`. So a key held locks out the cursor.
- `0x1419882b0(act, target)`: with `+0x244 > 0`, `+0x260 +0x74 > 0`, `+0x268 > 0` or `+0x26c > 0` it only stores `+0x250`, `+0x258 = 1`; else `vf130(target)`, then `vf138` -> `0x14197cee0`.
- **Stat listener** `DodgeRoll_OnStatChanged` `0x141b9b700` (slot `+0xc0` of `0x143469db8`, `this = part+0x18`; renamed in Ghidra): with `part+0x5f`: `ac+0x1b0` = `(1+stat(0xec)/1e4) / (1+stat at start/1e4) * ((int)((sqrt(1+stat at start/1e4) - 1)*100)/100 + 1)`, times the controller rate `1+action%/100`. Its buff `0xab2` test and the `part+0x3e` new line (a new line from the running line's end at `DodgeRollMove_Speed`) are not ported; the rest is ported.

## Facing, event, first heading (checked by replay)
- **Facing at start:** a roll's start does not turn the player. `0x141e5c930` turns to the target only when the action's vf `+0x340` (`0x1413d2e00` = vf `+0x348` != 2*pi) is true; for the roll (vtable `0x14326ea60`, `+0x340` = `0x1413d2e00`, `+0x348` = `0x1419894c0`) it is always false. `0x1419894c0` returns 2*pi when `act+0x142` bit 4 is clear and Actor `+0x2b4` == the skill id (`act+0xf8 -> +0x40`), else stat `0x46a7` (18087 `action_required_target_facing_angle_tolerance_degrees`, read from the action's stat set via `0x1419807d0` / `0x141980850`: `act+0x1e8` list indexed by `act+0x19c`, else the skill's stats `0x141e93860`) * pi/180, or 2*pi when that stat is 0. The roll always has `+0x142` = `0x10` (bit 4 set) and no stat 18087 (DodgeRollPlayer stat set row 1634 has none; only crossbow/grenade/projectile skills carry it), so it is 2*pi in all 321 logged roll starts (hook `TOL` rows, crazy-keys 2026-11-03 23:57). Actor `+0x2b4` holds the roll's id 1 almost always (writer `0x141e53140` stores the slot-0 skill id before starting the queued action; Move lives at Actor `+0x240` type `0x2909` id `0x20002909`, the roll at `+0x238` type `0xed4c` id 1) but it does not matter.
  - The facing a roll starts with is Positioned `+0x44c` as left by: (a) the `0x1dc` SetAimTarget echo: Actor handler `0x142158b60` case `0x1dc` (kind 0: cell at msg `+0x24`; kind 1: entity id at `+0x2c`) calls `0x141e5e830` (call at `0x14215a3b9`), which stores the aim cell at Actor `+0x1d4` and calls Positioned_SetFacing towards it when Actor `+0x2a1` bits 0, 1, 7 are clear (never set in play: values 0x0/0x4/0x10/0x14/0x20), slot 0 (`+0x238`) is empty or its vf `+0x338` is true (the roll's is `0x140108d20` = false, so no aim turn while a roll, its sprint or its SprintEnd clip runs), Actor `+0x380` is not `0x36a`/`0x36b`/`0x371`/`0x372`, object `0xe4fa` (`0x141f918d0`) passes, and the cell != grid; 606 of 606 such writes came from `0x14215a3be` in crazy-keys 2026-11-04 00:28; (b) the waypoint steps of a roll or sprint (Positioned_MoveToWaypoint `0x141df0400`, call `0x141df0c21`); (c) a WASD key walk does not face its waypoints: no SetFacing from `0x141df0c26` in any plain key walk (crazy-keys 2026-11-04 00:20/00:45, e.g. f707-715, f813-836, f1188-1217) while Positioned `+0x1e3` is 1 (LINE rows o=1 in 3560 rows, 2 in 751), so the request's `+0x9a`/`+0x99` override must be set by a listener of the path (Pathfinding_StepAlongPath `0x141dd9200` calls `FUN_140ecedc0` on `pf+0x20` with the request; it starts with `+0x9a` = 0 and restores `+0x1e3` after); which listener and on what condition is unread (fitted: a key walk not sprinting keeps the facing, server Moves and sprints face the path). Then `DodgeRoll_InitHeading` `0x141b99fb0` compares the heading with `+0x44c` (|d| >= pi/2 with Actor `+0x8fa` set: backward, `part+0x3f` = 1). So a key-held roll with the cursor at least 90 degrees from the keys is a backward roll because of the aim facing (the old "float drift", rolls f1133.. of the reference capture). `+0x8fa` is set for the player in that capture.
  - Ported: `ClientSim::on_aim_target` (from `MoveEvent::AimEcho`), `step_along` keeps the facing for a key walk not sprinting, `on_start_roll` no longer turns. Model facing equals the client's at all 107 roll starts of crazy-keys 2026-11-04 00:45. Replays: seg1 grid_differ 175 line_drift 8, seg2 grid_same 1173 line_drift 25 (now with the official session's 2700 aim inputs), ck0 line_drift 188 -> 161. Rule test `the_aim_echo_sets_the_facing_and_a_key_walk_keeps_it`. Ruled out: the old fitted rules (turn to the target unless queued or in the SprintEnd clip; the `+0x2b4` 15 s memory, timer `+0x2b8` cleared at `0x141e5251e`; a time window after a roll's end). Evidence kept from the old fits: user test 4 f2319 (roll queued into a roll, client facing 0.0, forward), user test 2 f2802 and official seg1 f3578 (first frame len 42.2940 = bwd, forward 42.2676): a roll out of the SprintEnd clip against the sprint is backward by `InitHeading`. Rule tests `a_roll_queued_into_a_roll_keeps_the_facing`, `a_roll_out_of_the_sprint_end_against_the_sprint_is_backward` in `modules/server/crates/poe-game/tests/rules.rs`.
- **Backward roll after the sprint event:** the rule is `act+0x461` above (false in every session), so a backward roll out of the SprintEnd clip stays backward after the sprint event (orientation 2, facing = line heading + pi) and turns around only at its sprint start at the end. Evidence: user test 3 f995-1002 (client facing stays 5.498 until the reversal, then 0.897, 2.231, 2.356; model equal, line ends (342,1095), (339,724)); user test 2 f2398 (0.829 -> 3.970). A reversal mid-roll hits the tie d = about -pi in the turn block 0x14197fdf0: with facing 5.4977875, d < -pi (constants 0x14362365c = -pi, 0x143621f14 = pi) so it wraps to +pi and the turn goes through the positive side. The old model flipped at the event and turned the other way (per-frame snaps f1001-1053). Rule test `a_backward_roll_out_of_the_sprint_end_stays_backward_after_the_event`.
- **Sprint switch needs Actor `+0x915`** (`0x141b85160`): hook `player actions` lines of user test 3 show 915=1 at the roll's start with the key held (f1821), 915=0 after the release (f1824), still 0 after a new press during the roll (f1826, `2a2` back to 0x60), 1 at the next roll's start (f1851). So releasing and pressing again during a roll does not sprint; the press queues another roll. Writer of `+0x915` unread. Ported as `Roll.key_held` in ClientSim; rule test `a_key_pressed_again_during_a_roll_does_not_make_it_sprint`. The old model used only the key state and sprinted at f1836 (snaps f1837-1904).
- **Correction chain:** after a server correction the client sits on the corrected cell while the server's model keeps its sub-cell point, so per-frame snaps follow for about 50 frames (f1851-1904); fixing the first divergence removes the chain.
- **Event `0xb91f` is `sprint_start` at 0.5 s of the roll timeline: `AnimPlayer_Advance` sets `ac+0x1a4` = event time before firing, so the curve restarts at 0.5, not at the frame's elapsed. The switch to `_sprinting` runs if the key is held. A backward roll that sprints flips here: `pos+0x1e3 = 1`, facing += pi.
- **Target update (`GP_dodge_roll_base_01`, `StartTargetUpdateEventType` `3000 0 1` from time 0 to 1.0, `sprint_start` at 0.5; timeline `metadata/characters/timelines/base_dodge_roll/base_dodge_roll.atl`, UTF-16 JSON):** event type `0x1a` in `0x141984ec0` sets `act+0x240` (window), `+0x244` = first value in radians per second, `+0x260` = the event. Before the window a `0x1af` only sets `act+0x150` (`0x141e69140`). Inside it `0x1419882b0` stores `target - grid` at `act+0x250`, flag `+0x258` (vf `+0x140` false); each action update (`0x14197fdf0`) takes `e = grid + stored`, `want = ang(sign*off)` (`sign` = -1 when vf `+0x530`, `part+0x3f`, backward), `d` = wrapped `want - facing`; if `|d| > dt*rate`, `e = grid + sign*round(rot((0,-|off|), facing + clamp(d)))`. Then vf `+0x130` `0x141b9a8b0` sets the heading from `e`; vf `+0x138` is false (`0x140108d20`) so **the facing does not change**. Checked by f3545 (a 107 degree jump, 99 degrees per frame). The axes aim (`0x1419883c0`) needs the same window. The window event at 0x141985956..0x141985985 sets `+0x240 = 1`, `+0x244`, `+0x268`, `+0x26c`, `+0x24c`, `+0x24d = 0` and calls 0x1419883c0 at once. The event runs with the axes of before a `0x64` later in the same batch, so a roll out of a cursor walk (`0x1c8` before `0x64 (0,0)` in the batch, UseSkill flags 0x440) gets `+0x24d = 1` and ignores `0x1af` (0x141e69140 checks `+0x24d`) until the sprint switch: user test 4 f4016-4030 (facing 2.583..2.923, line x end 485, equal to the model), steering again from f4031 (line end (537,1202)); the release at the sprint switch is by replay, code unread. Other mouse rolls with axes 0 before the start steer at once (f4088, f4174, f4371). Rule test `a_roll_started_with_the_axes_still_set_ignores_the_cursor_until_the_sprint`. 0x141e69050 is the applicability check of `0x1af` (needs Actor `+0x2a0` bit 1, window `act+0x240`, not (`act+0x148` != 0 and `act+0x24c`), or vf `+0x300`; skill match via vf `+0x120`).
- **First heading of a cursor roll (no axes):** measured, 13 of 13 rolls (incl. the private `(28,-17)` case, which replaces the old "exact cursor point" reading) and float-exact in `clientsim`: heading = `ang(round(unit(target - grid) * 3))`. The first `0x1af` then aims at the exact integer target. **The code that does this is not found:** read how `act+0x150` or the heading gets the 3-cell vector. `DodgeRoll_InitHeading` (above) computes atan2 of `act+0x150 - grid` with no rounding, so `act+0x150` must hold `grid + round(unit*3)` when it runs: the exact target instead of the measured vector makes the replay far worse (seg1 grid_differ 175 -> 596). Who writes `act+0x150` is unread.
- **Move during a roll:** stays queued (`A+0x248`), starts in the Actor tick after the clip's end (f3429).
- `0x80410041` is the unarmed punch (a skill): it replaces a running roll, moves on a time-mode line towards its target, and a Move during its recovery walks slowed (Actor `+0x430`). Out of scope until the server sends skills; the offline replay follows the client log while one runs.
- **Sprint start plans twice:** the roll's end in the Animated tick starts a walk on the held axes at once, then the frame's `0x64` plans again; each plan makes its sprint turn (f2995, f3566, two `PATHPLAN` rows).
- **Clock of a queued roll:** a roll queued into a running roll starts at that clip's end in the frame's Animated tick; the tick plays the old clip out and only the rest of the frame's time goes to the new clip. User test 3 f1851 and test 4 f2319: old clip at 0.99, dt 0.033, new clip's `ac+0x1a4` = 0.023, so line time `T` (Tleft) = 0.977. Ported as `Roll.elapsed` starting at old elapsed - length (negative, -0.01) in `on_start_roll`; curve loaded at 0. Replay of test 4 is exact to the log's 4 decimals from f2320 (len 40.1932, 36.8011, 33.6587, 30.6421; T 0.95351, 0.92018, 0.88922, 0.85659) to the old server's snap at f2345. Fitted by replay, the code that carries the time is unread. First steps of such a roll: 3.8068, 3.3921 (rule test `a_roll_queued_into_a_roll_keeps_the_facing`).
- Ruled out: the hook's `LINE ... T=` field is the line time `len/speed` (`t_total`), not a clock, so its per-frame step varies per roll (0.0323..0.0336 in normal rolls, because len differs from `left` by the target's rounding); the earlier "queued roll clip rate 0.973, first curve time 0.0522" was misread from it and from `rollinv.py` (which uses len as left). Rate is 1.0.

## Not read / open

- `0x141ede540` path storage order (is element `count-1` the first step?).
- Value and meaning of Actor `+0x8fa` for a normal player; object `0xe4fa`; `0x141f918d0`.
- `0x141b9f4e0` dynamic blockers; who sets `part+0xa0` (cells-travelled listener).
- Where `DodgeRollMove_Tick` is called from (act update vs. actor parts) and the AnimationController's
  tick order against Positioned/Actor in a frame (decides whether Speed sees this frame's elapsed).
- Stat names `0x5121`, `0x478c`, `0x10a2`, `0x596b`, `0x5f2f`, `0xec`; the `0xb91f` event's time.
- `Positioned_MoveToWaypoint` first step in the same frame (doc claim, not re-verified here).

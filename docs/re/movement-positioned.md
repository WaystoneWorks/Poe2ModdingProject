# Positioned move: WASD / gamepad walk, lockstep (exact-port spec, 0.5.5f)

Exact-port spec for the `0x63` sender, the `0x64` handler, `Actor_StartWasdWalk`, the Positioned move, line, step check and speed. Overview and frame order: [wasd-movement.md](wasd-movement.md); siblings: [click](movement-click.md), [roll](movement-roll.md), [sprint](movement-sprint.md). Wire layout: [movement.md](../protocol/movement.md).

Read from Ghidra `/0.5.5f/PathOfExileSteam.exe` (decompile + disassembly where the decompiler hides
xmm arguments). All math is **f32** (SSE `ss` instructions, f32 constants) unless stated.
`CORRECTION:` marks a point where the earlier notes were wrong; the docs now follow this file.
Offsets: `A+` Actor, `P+` Positioned, `L+` line (`L = P+0x208`), `PF+` Pathfinding.

Helpers (all verified):
- `0x1421a30b0` Cell_ToWorld: `w = ((f32)c + 0.5f) * 10.869565f` per axis (`0x1436219a8` = 0.5, `0x1436220d4` = 10.869565).
- `0x1421a30f0` Cell_FromWorld: `c = (i32)floorf(w * 0.092f)` per axis (`0x14362178c` = `0x3dbc6a7f` = 0.092f; `0x140168860` = floorf, then cvttss2si).
- `0x140525880` RoundHalfUp: `floorf(x + 0.5f)` (ties go up, -2.5 -> -2).
- `0x140a3d1b0` / thunk `0x142cc42c4` = fmodf; `0x142c54448` = atan2f(y, x); `0x1401528b0` = max(*a,*b) (returns ptr), `0x1401528a0` = min; `0x140153400` = clamp(x, lo, hi).
- Constants: pi/2 `0x143621d4c` = 1.5707964f, 2pi `0x143622034` = `0x40c90fdb`, pi `0x143621f14` = `0x40490fdb`.

Renamed in Ghidra: `Game_SendMoveDirection_63` 0x1421228d0, `InputKeyboard_UpdateMoveDirection` 0x14017c420,
`InputGamepad_StickToMoveVector` 0x140174640, `Actor_ReaimWasdWalk` 0x141e5e210, `Positioned_SetFacing` 0x141de99d0,
`Positioned_SetLocationForcedNoCallbacks` 0x141de88a0, `Positioned_StopMove` 0x141df31b0, `Positioned_ReissueAtSpeed` 0x141df23f0,
`Positioned_RunLine` 0x141de9b80, `Positioned_CheckStep` 0x141dea170, `Positioned_ApplyStep` 0x141deae70,
`Line_Setup` 0x141ed66d0, `Line_Advance` 0x141ed6310, `Line_Step` 0x141ed6ce0, `Line_End` 0x141ed6f30, `Line_Point` 0x141ed6400.

---------------------------------------------------------------------------------------------------
## 1. C->S `0x63` MoveDirection

### Sender `Game_SendMoveDirection_63` (0x1421228d0)(game G, f32 v[2])
```
if G+0x8b88: return
if (G+0x1a8)->+0x20f0->+0x868 and (G+0x75e0 == 0 or G+0x75e2): return
if (G+0x1a8)+0x2734 != 0: return
if G+0x8bc8 > 0: return                    // send cooldown, see end
x = RoundHalfUp(v[0]); y = RoundHalfUp(v[1])
if (x, y) == (G+0x79b8, G+0x79bc): return  // ONLY ON CHANGE (last sent vector)
G+0x79b8 = (x, y)
world = G+0x1a0
if world+0x669 != 2:                       // NOT lockstep: predict locally
    actor = G+0x198
    if (x,y) != 0 or actor.axes == 0 or actor+0x414:
        old = actor.axes; actor.axes = (x,y); actor+0x414 = 1
        Actor_StartWasdWalk(actor, old == 0 and (x,y) != 0)
pkt = {op 0x63, +0x10 u8 = G+0x181, +0x18 (x,y), +0x20 cell, +0x28 bool}
cell = (world+0x669 != 2) ? local player Positioned+0x444 : (0,0)
flag = (Player(G+0x188)+999 == 1) and stat is_sprinting(0x5746) != 0
send; flush (0x1421a7f90)
if (x,y) != 0: 0x14013f780(G+0xf50); G+0x75e2 = 1
G+0x8bc8 = 0x3d088889 (= 1/30 s)
```
Wire (deserializer `0x141f48a70`, clone `0x141f48af0`, vtable `0x1434fb608`):
`u8 (G+0x181), varint x, varint y, varint cell.x, varint cell.y, u8 flag`.
- CORRECTION (movement.md "u8 1, varint x, varint y, u8[3]"): the "u8[3]" trailer is **cell x, cell y (always 0,0 in lockstep), bool**.
  The bool is **`Player+999 == 1 && is_sprinting`**, not "cursor direction / click-to-move mode" as such (Player+999 = 1 is the
  click-to-move input mode, so it is 1 only for a sprint in that mode; matches the capture: 291/1115 with flag 1, all others 0).
- Varint (checked on capture `2026-11-03_13-16-29_336`): one byte `0x00..0x7f` = 7-bit signed (`0x40..0x7f` negative), two bytes
  `0x80|hi6, lo` = 14-bit signed. (`bf 4c` = -180, `7c` = -4.)
- Sent only when the rounded vector changes and the 1/30 s cooldown has run out (a change inside the cooldown is simply
  re-evaluated next input frame). In lockstep (`world+0x669 == 2`, the game) nothing moves locally.

### Keyboard / cursor vector `InputKeyboard_UpdateMoveDirection` (0x14017c420)(input I)
```
v = (0,0) at I+0x434 (x), I+0x438 (y)
if WASD mode (I+0x418) and foreground window and no UI capture:
    for each of 4 bindings (table 0x143625ba0 = action 0..3): GetKeyState(key) < 0 (and modifier):
        0: v.y += 1   1: v.x -= 1   2: v.y -= 1   3: v.x += 1
if is_sprinting (0x5746):                  // cursor direction while sprinting
    held = Actor+0x2a2 bit5 (sprint key); s579a = stat 0x579a; p = 0x141de1b80(Player)
    WASD mode:  if v == 0 and not (s579a == 0 and p and not held): v = cursor
    click mode: if s579a or held: v = cursor; elif p and (I+1000)->+0xe8 == 0x61: v = cursor
    cursor: screen projection of player world (+0x490, z 0x141df2770) -> s;
            v.x = mouse.x - (s.x - cx); v.y = (s.y - cy) - mouse.y    (mouse ints at +0x71c, centre DAT_1445a4c00/254)
if |v|^2 > 0.01:
    n = v / |v|; m = min(|n|, 1) (= 1); Lr = m*150 + 30 (= 180)
    d = ((n.y + n.x)*Lr, (n.y - n.x)*Lr)          // 45 degree turn: screen -> grid axes
    v = d / |d| * Lr                                // length 180
send(v)                                             // through RoundHalfUp in the sender
```
So keys and cursor always give length 180: W = (127,127), W+D = (180,0), D = (127,-127). Matches captures.

### Gamepad `InputGamepad_StickToMoveVector` (0x140174640) and `0x140175b80`
`0x140175b80` (per frame, from the gamepad controller update `0x140174af0`): `stick = vfunc+0x120(I, &, 0, 1)`;
`I+0x43c = (|stick|^2 > 0.09)` (**dead zone 0.3**); `I+0x440 = StickToMoveVector(mode 1, no lock)`; sends `I+0x440` if `I+0x43c`
else `(0,0)`. `0x140174af0` sends `(0,0)` when its arg 2 is set or `I+0x510 > 0`.
```
StickToMoveVector(I, out, actor, mode, lock):
  s = vfunc+0x120(I, &, mode ^ 1, 1)
  [lock and aim-lock active: s replaced by a rotated aim direction; not used for the sent vector]
  if |s|^2 <= 0.0002: out.valid = 0; return
  sy = -s.y
  m  = min(sqrtf(s.x^2 + sy^2), 1.0)
  Lr = m*150 + 30                                  // 30..180, sent vectors >= 0.3*150+30 = 75
  if world+0x11a == 0: d = ((sy + s.x)*Lr, (sy - s.x)*Lr)
  else:                d = (sy*Lr*c1, s.x*Lr*c2)   // c1 0x143621cfc, c2 0x143623624 (decompile: 1.414, -1.414)
  out = d / |d| * Lr; out.valid = 1                // (0,0) if |d| <= 0
```
Capture check (gamepad phase): 1093 non-zero `0x63`, lengths 76.4 .. 180.6, e.g. (-54,-54), (-120,135).
**The axes are used as sent (analog, no normalisation or quantisation beyond RoundHalfUp in the sender).**

---------------------------------------------------------------------------------------------------
## 2. S->C `0x64` handler (case 100 in `0x142158b60`; msg `+0x20` vector, `+0x28` cell)
```
A = actor; world = entity+0x78; P = entity+0x98
if world.vfunc+0x1d8() == 1 (predictive) and entity id (+0x88) is found in world+0x610 set: return
v = msg.vector
if v != 0 and msg.cell != P.grid(+0x444,+0x448):
    if world mode == 1 and |cell - grid|^2 < 0x844: bend v (predictive only; not read further)
    else: Positioned_SetLocationForcedNoCallbacks(P, msg.cell, world point (cell+0.5)*10.869565 f32)
if v == 0 and A.axes != 0 and A+0x414 == 0: return
old = A.axes; A.axes(+0x400,+0x404) = v; A+0x414 = 1
Actor_StartWasdWalk(A, old == 0 and v != 0)
```
CORRECTION (wasd-movement.md "when it and the axes are both zero and +0x414 == 0, nothing more"): the early return is
**vector zero AND axes NON-zero AND +0x414 == 0**. Zero vector with zero axes still runs `StartWasdWalk(A, 0)`.
The same gate is in the sender's predictive branch. Who clears `+0x414` is not read (Actor tick?).

### `Positioned_SetLocationForcedNoCallbacks` (0x141de88a0)(P, cell, world)
```
terrain = world.vfunc+0x1a8(); W = terrain+0x18 * 23; H = terrain+0x20 * 23
if cell or floor(world*0.092) outside [0,W)x[0,H): log error (continue)
if P+0x49c != 0x7fffffff: assert bucket == grid/23; bucket remove (vfunc+0x38)
P.grid = clamp(cell, 0..W-1, 0..H-1)
P+0x490 = world
if P+0x1e6 bit3: P+0x440 = height(terrain, cell) (0x141d19e00); P+0x48c = -h * 7.8125
bucket add (vfunc+0x28)
if L.thr(+0x28c) != 0 or P+0x314 != 0 (smoother rate): Positioned_StopMove(P); acc(+0x290) = 0; pending(+0x298) = 0
```
Note: the grid is clamped, no callbacks, facing untouched.

---------------------------------------------------------------------------------------------------
## 3. `Actor_StartWasdWalk` (0x141e5da30)(A, edge)
```
world = entity+0x78
if A+0x4ba or world+0x118 or (world.vfunc+0x188() and not entity+0x8c bit6):
    if A+0x4ba and world+0x118 == 0 and world.vfunc+0x1d8() == 0: A.vfunc+0x208(A)   // remote path
    return
if entity+0x8c bit0 or A+0x2a1 bit1 or A+0x2a0 bit6 or A+0x2a1 bit2 (re-entry): return
if A+0x380 in {0x36a,0x36b,0x371,0x372}: return
if A+0x2a1 bit0:                      // controlled entity: forward a request instead (not the local player walk)
    if world mode != 0 or axes == 0 or no Player: return
    A+0x2b0 = (A+0x2b0 + 1) & 0x7fff, 0 -> 1, |0x8000 when mode 0
    Player-actor 0x141e4dab0(0x2000b7d9, target = player grid, ...); return
save = world+0x128; world+0x128 = 0
if P+0x480 > 0 and P+0x484 >= Pathfinding_GetSpeed(PF, entity, 1): goto out     // push at least as fast
if A.axes == 0:
    if Move(A+0x240) and type(+0x120) == 0x2909 and Move+0x122 == 0: 0x141e53c90(A, 1)   // end WASD Move
    goto out
Pl = Player
if A+0x2a0 bit1 (slot 0 running) and slot0.vfunc+0x50() == 0:          // slot-0 action not cancellable by default
    if Pl and Pl+999 in {2,3}: goto out
    if stat 0x4e2e of slot 0 == 0:
        ref = (A+0x40c, A+0x410) != 0 ? (A+0x40c, A+0x410)          // axes at the action's start (0x141e5cbb0)
                                       : facing vector (0x14016d130)
        if dot(ref, axes) >= 0: goto out                            // only a reversal cancels
    if slot0 type -0x12b4 or ... (vfunc+0x300 & !(+0x142 bit5)) or A+0x420 > 0 or slot0.vfunc+0x290() == 0: goto out
    0x141e4e7c0(A); A.vfunc+0x378(A); 0x141e532c0(A, 0); if slot 0 still there and not vfunc+0x50: goto out
goal = P.grid + Cell_FromWorld((f32)axes.x, (f32)axes.y)        // 0x141e5de6a: cvtdq2ps of +0x400/+0x404, then 0x1421a30f0
if edge and Move type 0xc266 and Pl and Pl+0x20c: 0x141e53c90(A, 0)
if A+0x91a: start the alternate move skill (+0x918 id) into A+0x240, 0x141e5c610(A); goto out
if no Move: create from skill list (lower_bound id 0x20002909, < 0x2000290a) into A+0x240; Move+0x122 = 0
elif Move type != 0x2909: goto out
A+0x2a1 |= 4
0x141e5e3a0(A, &goal)                  // group clamp (P+0x4c0 only)
Move+0x150 = goal; listeners (Move+0x2e8..0x2f0) vfunc+0x98(goal, Move+0x148)
FUN_141e50540(A)                       // plan (timer 0.05 for a Player)
A+0x2a1 &= ~4; world.vfunc+0xa0()
out: world+0x128 = save
```
**Goal rule, exact:** `goal.i = grid.i + (i32)floorf((f32)axes.i * 0.092f)` per axis. Not symmetric: 127 -> +11 (11.684), -127 -> -12;
180 -> +16 (16.56); -180 -> -17; gamepad (-67,77) -> (-7, +7).

### `Actor_ReaimWasdWalk` (0x141e5e210)(A), from the Actor tick when the plan timer is out
```
if Move and type 0x2909 and !(A+0x2a1 bit2) and Move+0x122 == 0 and (!(A+0x2a0 bit1) or slot0.vfunc+0x50()):
    goal = grid + Cell_FromWorld((f32)A+0x400, (f32)A+0x404)        // 0x141e5e295
    0x141e5e3a0(A, &goal); A+0x2a1 |= 4; Move+0x150 = goal; listeners vfunc+0x98; FUN_141e50540(A); A+0x2a1 &= ~4; world.vfunc+0xa0()
```
Note `Move+0x122 == 0` (a locally created WASD Move); a server-numbered Move is never re-aimed.

### `0x141e5e3a0`(A, goal): group clamp
Only with `P+0x4c0` (group): if the goal is outside the group box (`+0x40..+0x54` edges/normals), `0x141dec690` then
`0x141ed97c0` clamp, re-expressed as grid + floor(world delta * 0.092) (`0x14016cb50`, `0x14016cc10`). Solo player: no-op.

---------------------------------------------------------------------------------------------------
## 4. `Positioned_MoveToWaypoint` (0x141df0400)(P, req)
`req`: `+0` target ptr (i32 x, y), `+8` speed f32, `+0xc` target z, `+0x48` / `+0x88` functors (done / fail, copied to P+0x160 / P+0x1a0),
`+0x90` mode byte, `+0x91/+0x90` set flag, `+0x92` flags word -> P+0x49a, `+0x94/95`, `+0x96/97` -> P+0x47b/+0x47c,
`+0x98` -> P+0x479, `+0x99/+0x9a` orientation mode (else P+0x1e3), `+0x9b` reset curves.
```
if entity+200 (attached): return 0
if P+0x480 > 0 and speed <= P+0x484: return 0          // push at least as fast
P+0x480 = 0
if P+0x1e6 bit4: return 0
if speed is inf / NaN: log; Positioned_StopMove; clear P+0x49a..0x49b; return 0
P+0x1e6 &= ~0x20
if req+0x9b: zero both curve slots (P+0x2a8.., P+0x330..)
if req+0x92 bit4: P+0x49a |= 0x10
keep = req+0x92 bit6
if req+0x92 bit0: [predictive only: vfunc+0x108 time-based move] else
    if L.thr != 0 and !(P+0x1e5 bit7) and P+0x49a bit0: event; delegates FUN_140ecedc0; return 0
if L.thr != 0 and !(P+0x1e5 bit7): event; data+0xc8 list; delegates FUN_140ecedc0 ("stopped")
if speed == 0 and !keep: Positioned_StopMove; clear 0x49a; P+0x1e5 &= 0x7f; return 0
if target == grid and !keep: event; lists +0xb0, +0xc8; delegates FUN_14020ad94 (done); clear 0x49a; return 0
P+0x1e5 &= 0x7f
P+0x160 = req done functor; P+0x1a0 = req fail functor
P+0x499 = req+0x91 ? req+0x90 : P+0x498 (walk mode);  P+0x49a = req+0x92; P+0x479 = req+0x98
P+0x47b = req+0x95 ? req+0x94 : data+0x2e;  P+0x47c = req+0x97 ? req+0x96 : data+0x2f
mode = req+0x9a ? req+0x99 : P+0x1e3
if mode in {1,3,4} and target != grid:                       // 0x141df0bc2
    a = atan2f((f32)(t.y - grid.y), (f32)(t.x - grid.x)) + 1.5707964f
    a = fmodf(a, 2pi); if a < 0: a += 2pi
    Positioned_SetFacing(P, a)
if mode == 2 and target != grid:                             // 0x141df0d5a, backwards
    a = atan2f(dy, dx) + 1.5707964f; a = fmodf(a, 2pi); if a < 0: a += 2pi
    a -= pi                                                  // 0x141df0db7 (can be negative; SetFacing wraps)
    Positioned_SetFacing(P, a)
[z: tz == 0x7fffffff and P+0x440 or P+0x48c set, no bit3, no bit2: P+0x440 = 0x7fffffff, P+0x48c = 0]
if !keep:
    z_end = (P+0x1e6 bit2 or (bit3 and tz == INT_MAX)) ? P+0x440 : tz
    Line_Setup(L, grid, P+0x440, target, z_end, speed, -1)
    if P+0x49a bit7: Line_Setup(P+0x368, same)               // second line
    smoother (P+0x2e0) to Cell_ToWorld(target) from P+0x490 (0x141ed8010)
    if P+0x454 > 0: P+0x454 = 0                              // overshoot cleared
    0x141df1e20(P, target)
return 1
```
CORRECTION / precision: atan2 arguments are **(dy, dx) as f32 of the integer delta target - grid** (y first), the result is f32;
mode 2 is **the same angle minus pi**. The wrap is done twice (here and in SetFacing).

### `Positioned_SetFacing` (0x141de99d0)(P, a)
`if P+0x1e5 bit1: return` (facing locked). NaN: `P+0x44c = 0`, log. Else `P+0x44c = fmodf(a, 2pi)`; `if < 0: += 6.2831855`. No other side effect.

### `0x141df1e20`(P, target): `P+0x450 = 0x141df2bd0(P, 0)` (slope pitch of the smoother; 0 in 2D); `world.vfunc+0xa0`;
event `data+0xb0`; delegates on `P+0x18` with `FUN_14025613c(entity, target)` ("move started").

### `Positioned_StopMove` (0x141df31b0)(P)
`Line_End(L)`; target = `P+0x53c ? P+0x534 : Cell_ToWorld(grid)`; smoother `0x141ed8300(P+0x2e0, target, P+0x490, P+0x48c)`;
`P+0x499 = P+0x498; P+0x53c = 0`; clear `P+0x49a..0x49b`; `P+0x464 = P+0x4ac = P+0x479 = 0`; `P+0x47b/c = data+0x2e/0x2f`; `P+0x1e6 &= ~0x20`.
No cell change, no delegates.

### `0x141df2040`(P): stop with callbacks
```
P+0x160 = stub (vtable 0x1434e7c18); P+0x1a0 = stub (0x1434e7b80)      // drop done / fail functors
if L.thr == 0: if P+0x314 != 0: smoother to Cell_ToWorld(grid); return
if grid == L.s (+0x208,+0x20c): P+0x490 = P+0x2e0 (smoothed point)
if P+0x49a bit0: P.vfunc+0x110(P, 1)
Positioned_StopMove(P); event data+0xc8; delegates FUN_140ecedc0 ("stopped")
if L.thr == 0: acc = pending = 0
if data+0x25: entity+0x8d |= 8; P+0x10 = 1
```

### `Positioned_ReissueAtSpeed` (0x141df23f0)(P, speed)
```
if L.thr == 0 or P+0x1e5 bit7: return
end = un-swapped L end (L+0x34 major, L+0x38 minor; swap flag L+0x25, z swap L+0x26)
if L+0x61 (curve line): restart the curve segment at the new speed (list speeds P+0x4e0/+0x510); return
z_end = P+0x1e6 bit2 ? P+0x440 : line's z end
Line_Setup(L, grid, P+0x440, end, z_end, speed, -1)       // continues the line (running path of Setup)
if P+0x314 != 0: re-time the smoother to the new T (L+0x70)
```

---------------------------------------------------------------------------------------------------
## 5. Positioned tick

### `0x141de9b00`(P, dt)
```
if data(P+0x158)+0x20 and !(P+0x1e6 bit1): return
if P+0x480 > 0: P+0x480 = max(P+0x480 - dt, 0)
P+0x454 = 0
Positioned_RunLine(P, dt)            // dt stays in xmm1
```
### `Positioned_RunLine` (0x141de9b80)(P, dt)
```
if L.thr == 0: return
Line_Advance(L, dt)
loop:
  while L.thr <= L.acc or (L.flag(+0x24) and L.acc > 0) or z_curve_mismatch:
      if P+0x198 (collision delegate) == null: return
      (cell, z, done) = Line_Step(L)
      P+0x53c = 0
      r = Positioned_CheckStep(P, &out, cell, z, probe 0)
      if r == 0:
          if Positioned_ApplyStep(P, cell, z, done): continue loop        // true: no advance
          goto after
      // blocked
      if P+0x49a bit0: P.vfunc+0x118(P)
      payload: point = (line running, !bit7, !L+0x61) ? Line_point : 0; speed = L.len(+0x274) / L.T(+0x278)
      Positioned_StopMove(P)
      if L+0x54 != INT_MAX (z target) and r == 5: grid = cell; z...; 0x141de5aa0(P)
      world.vfunc+0xa0()
      if !(P+0x1e5 bit7): event data+0xc8; 0x141dfd170(P+0x18) ("blocked" delegates)
    after:
      if L.thr == 0: acc = pending = 0; goto finish
      if L.pending > 0: Line_Advance(L, 0.0)                              // 0x141de9e58: xmm1 = xmm6 = 0
      continue loop
finish (also on loop exit): if P+0x1e5 bit7:
      clear bit7; Line_End(L); acc = pending = 0; smoother to Cell_ToWorld(grid); P+0x499 = P+0x498; clear P+0x49a; P+0x464 = 0
```
z_curve_mismatch (3D only): `L+0x54 != INT_MAX and (i32)(c*L+0x5c*c*0.5 + c*L+0x58) + L+0x54 != L+0x48`, `c = count * thr`.
CORRECTION: a blocked result 5 takes the cell **only when the line has a z target** (`L+0x54 != 0x7fffffff`).

### `Positioned_ApplyStep` (0x141deae70)(P, cell, z, done)
```
P.grid = cell; if !(P+0x1e6 bit2) or bit3: P+0x440 = z
0x141ee1e70(P+0x1e8, P, cell) (occupancy); 0x141de5aa0(P)
if !done: return true
if P+0x1e6 bit5 (waypoint list P+0x4c8..0x4d0, index P+0x528, speeds P+0x4e0):
    idx += 1
    if idx != count:
        if grid != list[idx]:
            Line_Setup(L, grid, P+0x440, list[idx], bit2 ? P+0x440 : INT_MAX, speeds[idx], P+0x530 + idx)
            if !(bit6): smoother to Cell_ToWorld(list[idx]) else (sprinting stat or L+0x61): acc = pending = 0
            if pending > 0: Line_Advance(L, 0)
            return true
        if bit6: start a curve segment in place; return true
    P+0x1e6 &= ~0x20
P+0x499 = P+0x498; clear P+0x49a; P+0x464 = 0; P+0x4ac = 0
if L.T(+0x278) - L.elapsed(+0x284) < 0: P+0x454 = elapsed - T             // overshoot
if !(P+0x1e5 bit7): world.vfunc+0xa0; event data+0xc8; delegates on P+0x18 with FUN_14020ad94 ("done")
return false
```
WASD plans do not use bit 5 (one line per `Positioned_MoveToWaypoint`); the next waypoint comes from the Pathfinding
done delegate (`0x141dd9ea0`, documented in wasd-movement.md).

### `Positioned_CheckStep` (0x141dea170)(P, out, cell, z, probe) -> out[0]
```
out = 0
outside [0, W*23) x [0, H*23):
    probe == 0: StopMove; if P+0x1e5 bit7: clear it, return (result 0!) else event, out = 2, 0x141dfd170 delegates
    probe != 0: out = bit7 ? 0 : 2;  return
if P+0x49a bit0 and P+0x4ac and P+0x4a4 == grid: out = 1
sprint = P+0x1e7 bit1 and Player
if P+0x1e4 bit5 or P+0x49a bit2 or L+0x61 (curve/roll line): goto group
if !(P+0x49a bit3):
    mode  = P+0x1e6 bit3 ? 1 : (sprint ? 2 : P+0x499)
    level = (i8)P+0x1f8 + 1
    if level != 0 and walkability(terrain, cell, mode) (0x141d1a980) < level:
        if P+0x1e7 bit2: side probe 30 cells along the normal (0x141d25710) + search (0x141ede540); way round < 30 cells:
             P+0x49a |= 8, P+0x45c = probe cell, P+0x464 = 1, z mode... -> free
        else out = 2
else (going round): if P+0x1e7 bit2 and P+0x464 and dot(end - L.s, grid - P+0x45c) >= 0: P+0x49a &= ~8 (restore z)
if out == 0 and !sprint:                                           // ENTITY COLLISION
    emode = P+0x49a bit5 ? 1 : P+0x499
    r = max((i8)P+0x1f8, P+0x1fd ? (i8)P+0x1fc : (i8)P+0x1f9) + 1
    if 0x141dfd5b0(terrain, cell, r, emode, filter): out = 3, out[1] = hit Positioned
    elif collected pushables > 1 and probe == 0 and !0x141dee1a0(P, list, L+0x98*L+0x94, cell - grid): out = 4
    then (Player and stats): 0x141dfd7e0(...) second pass
    if out == 0 and !sprint and z != INT_MAX and !(bit3) and !(P+0x1e5 bit4) and z - (z_target ? P+0x488 : 0) < height(cell): out = 5
if P+0x1e4 bit2 and !sprint:                                       // forgiveness
    out == 0: if probe == 0: P+0x1e4 &= ~4
    out != 0 and != 2: if Player, stats, out == 3, hit+0x1e4 bit3, hit data+0x68 and !0x141dfda10(own grid): keep out
                       else out = 0
group: if P+0x4c0 and cell outside the group box: out = 0x141dec690(P, cell) when non-zero
```
CORRECTION: the forgiveness is not "once": `+0x1e4` bit 2 forgives every non-2 result until the first free step clears it.
CORRECTION: an out-of-map step with `+0x1e5` bit 7 returns 0 (after StopMove), not 2.

**Entity collision, walking local player (answer to the question):** yes, it runs whenever the sprint flag (`P+0x1e7` bit 1)
is clear. `0x141dfd5b0` scans the spatial buckets (cell size 23) in a box of radius `r - 2 + max_radius`, `0x141e00560` takes
every other Positioned `o` with `(i8)o+0x1f8 != -1`, skipping `o` whose walk mode (`o+0x1e5 bit7 ? o+0x498 : o+0x499`) is 1 when
`emode == 0`, and tests `|o.grid - cell|^2 < (max(o+0x1f8, o+0x1f9) + r - 1)^2` (u32 compare; `r` clamps to 1), then
the filter `0x141deabc0(o)`:
```
if o == self or o.entity+200 == self.entity: no
if self is not a "Projectile" entity and o.data+0x1d: no
out[1] = o
if o+0x1e4 bit3 and o+0x1e5 bit0: return Player ? 0x141de0890(Player, o.data+0x30) : no
if o+0x1e4 bit3 and o.data+0x68: return stats ? stat(...) != 0 : isProjectile
if o+0x1e5 bit6: return self+0x1d8 functor(o)
team: ta = self team (P+0x1e0 bit15 / low byte, or the owner's via 0x141deb9c0/0x141deb980), tb = o's
if hostile bit differs and table DAT_142f1bc10[(tb & 0xff)*256 + ta] bit set: no (pass through)
if self+0x1e5 bit7: yes
if self+0x198 functor(o):                         // the collision delegate checked in RunLine
    if 100 collected or !0x141defdf0(self, o): yes  // hard block
    collect o (pushable)                            // -> result 4 path
no
```
So whether a monster/NPC blocks the walking player depends on the team table and the `+0x198` delegate (set by the
owner, not read) and `0x141defdf0`; not resolved here.

---------------------------------------------------------------------------------------------------
## 6. Line (L = P+0x208)

Layout confirmed: `+0` s (i32 x,y,z), `+0xc` p (f32 x,y,z), `+0x18` q (i32 x,y,z), `+0x24` flag, `+0x25` swap, `+0x26` z swap,
`+0x28` sign, `+0x2c` slope, `+0x30` z slope, `+0x34` end (major, minor, z), `+0x40` cur major, `+0x44` cur minor, `+0x48` cur z,
`+0x4c` minor acc, `+0x50` z acc, `+0x54` z target (INT_MAX), `+0x60` distance mode (copied from `+0xc9`), `+0x61` curve line,
`+0x64` index, `+0x68` speed, `+0x6c` len, `+0x70` T, `+0x74` 1/T, `+0x78` optional rate (0), `+0x7c` elapsed, `+0x80` distance,
`+0x84` thr, `+0x88` acc, `+0x8c` count, `+0x90` pending, `+0x94` step time, `+0x98` curve rate factor.
After the swap, "x" = major, "y" = minor in every stored vector (s is stored before the swap and is not swapped).

### `Line_Setup` (0x141ed66d0)(L, s, sz, e, ez, speed, index)
```
L.speed = speed; L.s = (s, sz); L+0x54 = INT_MAX
running = L+0x61 == 0 and L.len != 0 and unswap(L.cur) == s       // cur major/minor (z slot when L+0x26)
fz = (sz == INT_MAX) ? 0 : (f32)sz
sf = ((f32)s.x, (f32)s.y, fz)
if running:
    p = Line_Point(L)                                // old line, written to L.p
    if p.x == (f32)e.x and p.y == (f32)e.y:  running = false; p = sf
    elif |sf.xy - p.xy|^2 >= 4.0:            running = false; p = sf
    elif sz != INT_MAX and L.cur_z == INT_MAX: p.z = (f32)sz
else: p = sf
dir = ((f32)e.x - p.x, (f32)e.y - p.y, sz == INT_MAX ? 0 : (f32)ez - p.z)
if running:
    t = dot(dir.xy, sf.xy - p.xy) / |dir.xy|^2
    q = (RoundHalfUp(dir.x*t + p.x), RoundHalfUp(dir.y*t + p.y), sz)  // floorf(x + 0.5f)
    flag = (q.xy != s)
else: q = (s, sz); flag = 0
d = e - q (i32)
swap = |d.x| < |d.y|  or  (running and |d.x| == |d.y| and fabsf(dir.x) < fabsf(dir.y))
if swap: exchange x/y in q, p, dir; L+0x25 = 1                      // e.major = e.y etc.
[z swap when sz != INT_MAX and |e.major - q.major| < |ez - q.z|: exchange major and z; L+0x26 = 1]
L+0x60 = L+0xc9
L.cur = (s.major, s.minor, sz)                                       // the start CELL, not q
L.end = (e.major, e.minor, ez)
len = |dir| (3D, f32)                                                // 0x14020d6e0
T = len / speed;  L+0x70 = T; L+0x74 = 1/T; L+0x78 = 0
D = fabsf(dir.major); inv = 1/D
L+0x98 = 1.0; L+0x94 = T*inv; thr(L+0x84) = (L+0x60 ? len : T) * inv
slope(L+0x2c) = dir.minor * inv
k = |e.major - q.major| (i32);  sign(L+0x28) = (q.major < e.major) ? 1 : -1
L.elapsed = L.distance = 0
acc(L+0x88) = thr * ((f32)k - D)
minor_acc(L+0x4c) = (p.minor - slope*((f32)k - D)) + (slope > 0 ? 0.49 : 0.5)
[z: L+0x30 = dir.z*inv; L+0x50 = p.z - zslope*(k - D) + (zslope > 0 ? 0.49 : 0.5)]
L+0x64 = index; count = 0; L+0x61 = 0
```
CORRECTION / precision vs wasd-movement.md "Setup": `round` = **floorf(x + 0.5f)** (ties toward +inf), not round-half-away;
the "p' != e" test is an exact f32 compare of the old line point with the integer end; `|s - p'|^2 < 4` is f32 on xy only;
the swap tie uses fabsf of the float direction; `D` is the float `|dir.major|` (from p), `k` the integer `|e - q|` major;
`sign` is -1 when `q.major == e.major`. Everything else in the doc's setup is right (0.49/0.5 rule: `slope > 0` -> 0.49).

### `Line_Advance` (0x141ed6310)(L, dt): as in the doc.
`x = dt + pending; pending = x; elapsed += x;` distance mode: `rate = L+0x78 > 0 ? L+0x78 : L+0x74; x = curve(L+0xa0, x, rate, 0, L+0x64)`;
`L+0x98 = x <= 0 ? 1 : rate*pending/x`; `x *= len` (`* (L+0x74/L+0x78)` when `L+0x78 > 0`). `pending = 0; acc += x; distance += x`.
Note `elapsed` is always time, `acc` is time (walk) or distance (curve).

### `Line_Step` (0x141ed6ce0)(L) -> (cell, z, done)
```
ready = thr <= acc
if L+0x61 == 0:
    if !flag:
        if ready: count++; cur.major += sign; acc -= thr; minor_acc += slope; cur.minor = (i32)floorf(minor_acc)
                  [z: if cur.z != INT_MAX and L+0x54 == INT_MAX: z_acc += zslope; cur.z = floorf(z_acc)]
    else:                                               // walk to q first, one cell per axis per call
        cur.major += sign(q.major - cur.major); cur.minor += sign(q.minor - cur.minor)
        if cur == q: flag = 0; [cur.z = q.z]; if cur.major == end.major: acc -= (L+0x60 ? len : T)
    curve_done = false
else: curve_done = ready                                // L+0x61 lines end when thr <= acc
[z target L+0x54 != INT_MAX and !flag: tz = min(ready ? count*thr : elapsed, T); cur.z = (i32)(tz*L+0x5c*tz*0.5 + tz*L+0x58) + L+0x54; zdone = T <= that]
cell = unswap(cur)
done = cur.major == end.major or zdone or curve_done
if done: Line_End(L)
```
Confirmed: `minor = floor(minor_acc)` (f32 floorf, not round); flag steps leave `acc` untouched; one major step per call.

### `Line_End` (0x141ed6f30)
`if thr != 0: pending = L+0x60 ? L+0x98 * L+0x94 * (acc / thr) : acc; if pending < 0: pending = 0; thr = 0; len = 0`. Matches.

### `Line_Point` (0x141ed6400)
`f = clamp(L+0x60 ? distance/len : elapsed/T, 0, 1)`; `point = p + ((f32)end - p) * f` per component (major, minor, z), then unswap. Matches.

---------------------------------------------------------------------------------------------------
## 7. Speed

### `Pathfinding_GetSpeed` (0x141dda090)(PF, _, subtract, _)
```
if PF+0x554 >= 0: return PF+0x554                       // fixed speed override
i = (i8)(PF+0x548)->+0x59;  if i < 0: return PF+0x55c * PF+0x550
st = stats of entity component i
f = max(stat 236 movement_velocity_+permyriad, -10000) / 10000.0 + 1.0
a = stat 3129 virtual_action_speed_+%; if a != 0: f *= max(a, -100) / 100.0 + 1.0
cap = max(stat 1098 movement_velocity_cap, 0)
base = PF+0x550 (Pathfinding.base_speed); if subtract: base = max(base - PF+0x558, 0)
v = base * f * PF+0x55c
if cap != 0: v = min(v, cap)
return v
```
CORRECTION (movement.md "Speeds"): add the `movement_velocity_cap` (1098) min, the `PF+0x558` subtraction (the step
`Pathfinding_StepAlongPath` 0x141dd92a3 and `StartWasdWalk`'s push test call with `subtract = 1`), the -10000 / -100 clamps and the
`PF+0x554` override. Units cells/s; `37 * 1 * 1 * 1 = 37` for a plain walk.

### Actor speed factor (Actor tick `0x141e508f0`, `0x141e5209b..0x141e521d1`)
```
if A+0x444 (ramp rate) > 0:
    s = copysign(A+0x444, A+0x448 - A+0x440)          // 0x140e9a740
    A+0x440 += s * dt
    if sign(A+0x440 - A+0x448) == sign(s): A+0x440 = A+0x448; A+0x444 = 0     // reached / passed the target
    f = A+0x440; if A+0x3f8 > 0: f = min(f, A+0x3fc)
    m = f * A+0x438
    if m != PF+0x55c:
        PF+0x55c = max(m, 0)
        if PF+0x560 bit0 (path running): PF+0x560 |= 4; Pathfinding_StepAlongPath(PF, PF+0x570); PF+0x560 &= ~4   // new line at the new speed
    if A+0x2a0 bit7: 0x141e5d750(A, ...)               // re-choose the move animation
```
Only runs while a ramp is active (`A+0x444 > 0`). A plain walk: `A+0x440 = 1`, no ramp, `PF+0x55c = 1`, speed = GetSpeed.

### Stats the server sends (ported)
- The client reads only 236, `virtual_action_speed_+%` (`0xc39`/3129) and `movement_velocity_cap` (1098): speed = base x (1 + 236/10000) x (1 + action%/100) x attack factor, capped.
- Server value of 236 = round((100 + increased + sprint%) x (100 + final) - 10000, to 100); `increased` = `base_movement_velocity_+%`, `final` = `combined_movement_velocity_+%_final` (11001). Fits every official value (0/5000; -400/4400 final -4; -300/4600 final -3; 600/5400 increased 10 final -4); round vs round-up undecidable.
- `base_move_speed_+%_from_sprint` (174) and `virtual_skill_ignore_namelocking_dynamically` (24200) are in the sprint lists only when nothing else changes speed ("plain"); also in the must_sprint list (2026-11-02 f11215 `[(22325,1),(22342,1),(22426,1),(23258,1)]`; 72 of 73 sprints pair with the sprint-on list). Official non-plain sprint end f11239: `[(236,-400),(22325,0),(22342,0)]` then `[(23258,0)]`; ours match.
- A running line takes a new speed at its next plan (one frame later).
- Open: `stun_threshold_+%_final_while_performing_action` (15916) is missing from official roll stun lists in blocks of rolls (2026-10-20: 10 rolls, 2026-11-02: 26), not tied to speed; still unexplained ([stats.md](../architecture/stats.md)); ours always sends it. Other `movement_velocity_+%_when_X` stats need conditions and a stat calculator: not handled; official 236 = 8000 at `(P,10,1)` and 12000 from other buffs.
- Roll travel distance: `DodgeRoll_SetTravelDistance` `0x141ab6230` = `(int)(sqrt(1 + stat 0xec/10000) * stat 0x57fa dodge_roll_base_travel_distance)`, stat `0xec` = 236 (ported). Roll rate listener: [movement-roll.md](movement-roll.md#start-order-end-re-aim-checked-by-replay).
- Sprint end clip time runs at the current speed's rate (left starts at the move time, minus dt x rate each frame): a wall-ended sprint blocks walks 30 frames at walking speed (seg2 f800-828).

---------------------------------------------------------------------------------------------------
## Aim and stun messages (moved verbatim from the protocol doc)
#### Aim
- C→S `0x62` mode 2 with the **absolute** cell under the cursor, at most one per frame, about every frame while the mouse moves; none in click-to-move mode. S→C `0x1dc` kind 0 with the same cell, header `(player,0,0,0)`, at `f+1` (94 %). Not every input is echoed: **never while rolling or sprinting**, mostly not while an attack runs (204/237), 0.5 % of idle/walking inputs.
- Mode 3 (entity, hovered) is sent often but only 11 `0x1dc` with kind 1 exist: not echoed one-to-one. Facing is entirely a `0x1dc` effect (conditions: [movement-roll.md](movement-roll.md#facing-event-first-heading-checked-by-replay)); there is no `0x1df`.

#### Stun
One light stun (f4072, a monster hit the player while attacking): `0x1d3` `is_light_stunned=1, is_immobilised=1` (header `(7,11)`), `0x1eb` buff row 2404 (flag `0x02`), `0x1d3 on_full_energy_shield=0` (`(7,14)`); 7 frames later `0x1d3 number_of_times_stunned_in_past_duration_from_ot=1` and `virtual_light_stun_threshold_+%_final=50`; **15 frames after the start the stats go back** (`is_light_stunned=0, is_immobilised=0`, header `(5,1)`) and the attack asked for meanwhile starts (`0x1c8` flags `0x410`, header `(5,2)`, `0x1ca`). Attacks and Move presses during the stun get their `0x1ae` only; the server cell stays put. Knockback (`0x1e0`) and stuns while walking or rolling: not captured.

## Not read / open
- Who clears Actor `+0x414` (axes-fresh) and what it gates elsewhere.
- Who decrements the sender cooldown `G+0x8bc8` (real time or frame time; captured 0x63 gaps go down to 19 ms, so the
  capture's send times or the decrement are not plain 33 ms frames).
- Collision outcome for monsters/NPCs: the `P+0x198` / `P+0x1d8` delegates, `0x141defdf0`, `0x141dee1a0` (result 4), team table
  `DAT_142f1bc10` contents, `0x141dfd7e0`.
- `0x64` predictive bend (vfunc+0x1d8 == 1, < 46 cells): not ported (lockstep never uses it).
- Gamepad iso constants `0x143621cfc` / `0x143623624` (decompiler shows 1.414 / -1.414) and when `world+0x11a` is set.
- `A+0x2a1` bit 0 (StartWasdWalk forwards a request `0x2000b7d9`), `A+0x91a` alternate move skill.
- Smoother `0x141ed8010` / `0x141ed8300` internals (world point only; the grid does not depend on it).

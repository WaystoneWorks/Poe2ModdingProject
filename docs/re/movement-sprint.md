# Sprint, local player (exact-port spec, Hotfix 1)

Exact-port spec for the sprint: start, turn, end check, end, coast, `0x64` interaction, stats. Overview: [wasd-movement.md](wasd-movement.md); siblings: [positioned](movement-positioned.md), [click](movement-click.md), [roll](movement-roll.md).

All addresses Hotfix 1. `stat(x)` = `(*stats->vtbl[0])(stats, x)`; the stats are either
`FUN_141975470(action, action+0x19c)` (the skill/action's owner stats) or
`FUN_14014efc0(entity)+0x160` (entity Stats component); both give the player's stats.
Stat keys checked in `GameFiles/poe-hook-data/stats.tsv`:
`0x5746` 22342 is_sprinting, `0x579a` 22426 must_sprint, `0x5794` 22420 dodge_roll_sprint_turn_rate,
`0x4686` 18054 is_immobilised, `0x698c` 27020 dodge_roll_is_replaced_by_locusts,
`0x4862` 18530 is_floating, `0xc39` 3129 virtual_action_speed_+%, `0xec` 236 movement_velocity_+permyriad,
`0xae` 174 base_move_speed_+%_from_sprint.

Object paths: `part+8` = the roll action; `action+0xf0 -> +8` = entity; `entity+0x98` = Positioned.
Actor: slot 0 `+0x238`, Move slot `+0x240` (type `+0x120`, Move = `0x2909`), axes `+0x400/+0x404` (i32),
axes-fresh `+0x414`, animation `+0x380`, stance `+0x2be`.

Renamed in Ghidra: `SprintPart_Start` 0x141b77110, `SprintPart_EndCheck` 0x141b76da0,
`SprintPart_End` 0x141b773a0, `Pathfinding_SprintTurnWaypoint` 0x141dcc460, `Pathfinding_Tick` 0x141dcce80,
`Positioned_RootOffsetToCell` 0x141de6030, `MoveEvent_Start` 0x141f5f650, `MoveEvent_GetTargetCell` 0x141f61000,
`MoveEvent_MovePositioned` 0x141f61de0, `MoveEvent_ClipToWalkable` 0x141f63560,
`SelectAnimationVariationForMovementSpeed` 0x141e56ae0.

## 1. Sprint start `SprintPart_Start` 0x141b77110 (part vtable 0x1434525d8 +0xa8)

`0x141415c30(part, first)` (vtable 0x1431c9e10, the microtransaction-effect subclass) calls it with the
same args, then `0x141415f70` (cosmetic sprint effects only, no movement).

```
start(part, first /*dl*/):
  pos = Positioned
  lvl = pos[+0x1f8]                                  // u8
  if stat(0x698c dodge_roll_is_replaced_by_locusts) == 0 and (i8)pos[+0x1f8] < (i8)pos[+0x1f9]:
      lvl2 = pos[+0x1f9] else lvl2 = pos[+0x1f8]     // signed max
  pos[+0x1fc] = pos[+0x1f8]; pos[+0x1fd] = 1         // optional<u8>
  pos[+0x1fe] = lvl2;        pos[+0x1ff] = 1         // optional<u8>
  pos[+0x200] = 1
  FUN_141d0fcf0(pos[+0x1f0]->[+0x78]->vtbl[+0x1a8](), pos[+0x1f0][+0x98])   // re-register in the grid (unread)
  actor = Actor; player = Player
  // 0x140132800 returns *(float*)&local where local = 0.0 -> the "timer > 0" test is always false
  if player[+0x20a] != 0 and actor[+0x400] == 0 and actor[+0x404] == 0:
      f = (sin(pos[+0x44c]), -cos(pos[+0x44c]))     // 0x140163cf0 via 0x142cadf00
      a = (cvttss2si(f.x*180.0), cvttss2si(f.y*180.0))   // truncation toward zero, ints
      old = actor[+0x400..+0x407]; actor[+0x400] = a; actor[+0x414] = 1
      Actor_StartWasdWalk(actor, edge = old == (0,0) && a != (0,0))   // 0x141e4fb40
  if first:
      i = 0x141e531e0(actor, "Standing")   // stance index by name in the actor's stance table (+0x210/+0x218, +0x234)
      if i != actor[+0x2be]:               // current stance is not Standing
          0x141ddc820(pos, pos[+0x44c] + pi)    // flip the facing
          DAT_1445c69b0->vtbl[+0x48](DAT_1445c69b0, entity, 0x140163ce0(pos))
```
CORRECTION: the no-keys axes need Player `+0x20a` (`sprint_continues_with_move_input`) set; without the
option the sprint start sets no axes and starts no walk. The pathing level second slot is
`max(+0x1f8, +0x1f9)` only when `dodge_roll_is_replaced_by_locusts` is 0. Start writes no `+0x1e7` bit.
The `Standing` flip only runs when `first` != 0 (caller unread) and the actor's stance is not `Standing`.

## 2. Sprint turn `Pathfinding_SprintTurnWaypoint` 0x141dcc460 (verified)

```
turn(pf, out, w):                         // w = waypoint cell
  st = Stats(entity)                      // FUN_14014efc0(entity)+0x160
  if stat(0x5746) == 0: return w
  c0 = pos[+0x444]
  d  = normalize(((w - c0) as f32 + 0.5) * 10.869565)    // 0x142193230 then 0x14010b1b0
  f  = (sin(+0x44c), -cos(+0x44c))
  c  = dot(f, d)                          // 0x14010b0d0
  if c > 0.99: return w
  a  = (f32)stat(0x5794) * pf[+0x580] * 0.017453292
  if c > -0.99 and |acos(c)| < a: return w           // 0x142cb0dbc acos, 0x140106960 abs
  if d.y*f.x - d.x*f.y < 0: a = -a
  r = (f.x*cos a - f.y*sin a, f.x*sin a + f.y*cos a)
  return world_to_cell(world(c0) + r * 180.0 * 10.869565)   // world(c)=(c+0.5)*10.869565; 0x142193270
```

`Pathfinding_Tick` 0x141dcce80 is Pathfinding vtable 0x1434d1e88 `+0x50` (the per-frame component tick,
arg `dt`); it is the only writer:
```
tick(pf, dt):
  pf[+0x580] = dt
  pf[+0x578] = facing vector (sin, -cos)
  pf[+0x574] += dt                         // time since the plan
  if pf[+0x560] & 1 (following a goal):
     if pf[+0x540] and !arrived(pf, *pf[+0x540], pf+0x520, pf[+0x564], 0):    // 0x141dcb810
        if pf[+0x574] < 2.0 or pf[+0x568] == *pf[+0x540]:
            if pf[+0x574] < 0.7: return
            if |pf[+0x568] - *pf[+0x540]|^2 < 4096.0: return
        replan 0x141dcc6a0(pf)
     else: 0x141dccac0(pf, 0)             // end the path
```
CORRECTION: `pf+0x580` is the frame `dt` (= `frame_ms/1000` = 0.033), not a factor; the stat is degrees per
second: `dodge_roll_sprint_turn_rate = 150` (`Metadata/Characters/Character.ot`), so the turn is
150 x 0.033 = 4.95 degrees per plan (the measured "0.99" = 0.033 x 30). `pf+0x574/+0x568` give the
replan rule for a goal path (every 2 s, or after 0.7 s once the goal moved 64 cells).

## 3. End check, end, Bonk

### `SprintPart_EndCheck` 0x141b76da0 (part +0x48, per frame; verified with one CORRECTION)
```
check(part):
  a = part[+8]
  if !(a[+0x144] & 2) or (a[+0x144] & 4): return
  if stat(0x5746)==0 or stat(0x4686)!=0: part->End(0, 0); return
  actor = Actor
  if actor[+0x238]==0 and actor[+0x240]==0 and !(actor[+0x2a0] & 0x80):
      if !(pos[+0x480] > 0.0 and stat(0x698c) != 0):     // +0x480 = push speed (+0x484 its speed)
          part->End(1, 0); return                         // Bonk
  if stat(0x579a) != 0: return
  if player[+0x20a]:
      if (actor[+0x2a2] & 0x20) or actor[+0x400] or actor[+0x404]: return
  else:
      if actor[+0x2a2] & 0x20: return
  part->End(0, 0)
```
CORRECTION (small): when the no-action test holds but the entity is pushed with the locust stat, it
falls through to the `must_sprint`/key tests (no Bonk), it does not keep going unconditionally.

### `SprintPart_End` 0x141b773a0 (part +0xb0, `(part, bonk, no_anim)`)
```
end(part, bonk, no_anim):
  0x14197c470(a)          // once (a[+0x144] |= 4): action finish vfuncs +0x410/+0x390, parts +0x70, delegates
  if actor[+0x240] and actor[+0x240][+0x120] == 0x2909: 0x141e45da0(actor, 0)   // end Move
  if !(actor[+0x238] and actor[+0x238][+0x120] == 0xedcc): pos[+0x1e7] &= ~1
  keep = actor[+0x2a3] & 1
  if !keep: 0x141de4de0(pos)                  // stop
  u16 pos[+0x1ff] = 0                         // clears +0x1ff and +0x200
  if !no_anim and actor[+0x238] == 0 and Life(+0x1e0) > 0 and !keep:
      i = stat(0x4862 is_floating) ? bonk + 2 : (bonk != 0)
      anim = AnimationRow(0x368).m_ExtraAnimations[i]   // 0x36a SprintEnd, 0x36b Bonk (+2: 0x371, 0x372 assumed)
      0x141e57b80(actor, {anim, rate_factor 1.0, ...})  // play
  actor[+0x2a1] &= ~4
```
Ported rule: the SprintEnd clip plays only with slot 0 empty (`actor+0x238 == 0`): a roll or an attack holding slot 0 means no clip, no coast, no walk refusal. The walk after an attack that ends a sprint restarts at once under the attack slow-down (fixture `attack_ends_sprint_then_walk` passes); the attack's end is not modelled in the client model, the slow-down ramp stands for it. Values from game data: `GP_sprinting_end_base_01` move `end_time` 0.75 (`metadata/characters/timelines/base_sprint/base_sprint.atl`), SprintEnd `sprinting_end_*_01 : speed = 600` (`metadata/characters/character.act`; no class `.act` overrides it except int/forms/demonform).

CORRECTION: Move is ended only when the Move slot holds a `0x2909` action; the floating index is `bonk+2`
(0 -> 2, 1 -> 3); `no_anim` (3rd arg, always 0 from the check) skips the animation; `Life+0x1e0 > 0` is the
alive test.

### Play animation `0x141e57b80(actor, req)` (type-3 = movement-speed animation)
For a row with type `+0x4d == 3` (`SprintEnd` is): `v = 0x141e4db00(actor) * req.factor(+0x4c, 1.0)`
where `0x141e4db00 = Pathfinding_GetSpeed(pf) * 10.869565` (world units/s), then
`SelectAnimationVariationForMovementSpeed` 0x141e56ae0:
```
pick variation: entries (0x58 bytes) with (!(fl&1) or min(+0x18) <= v) and (!(fl&2) or v < max(+0x1c)),
                weighted random (+0x08) with the actor's seed (+700 / req+8)
base = entry.speed(+0x0c); if 0: stance default (+0x50); if 0: 1.0      // 600 for sprinting_end_*
den  = base * pos[+0x158][+0x74] (offset_scale) * pos[+0x474]
if stat(0xc39 virtual_action_speed_+%) != 0: den *= 1 + max(stat, -100) / 100
rate = |den| > 1.19e-7 ? v / den : 0
```
then state rate (AnimationController state `+0x30`) = rate. Walks are refused while Actor `+0x380`
(the current animation, set here) is in `0x36a..0x36b` or `0x371..0x372`: `Actor_StartWasdWalk`
0x141e4fb40 returns at once (`(int)actor[+0x380] - 0x36a < 2`, `- 0x371 < 2`). So the refusal lasts as
long as that animation is current: clip 0.75 s / rate.

Bonk: `sprinting_end_*_01_bonk` views the same `sprint_end_*` clip and inherits `AU_sprinting_end_base_01`
-> `GP_sprinting_end_base_01`, so it **does** carry the MoveEvent, which coasts like SprintEnd. The target is
clipped to walkable (`MoveEvent_ClipToWalkable` 0x141f63640): a head-on wall leaves under 2 cells (no move, the 3
official wall Bonks); a wall met at an angle gives a coast along the wall to the clip's end. Seen in game test
`sprint-turn` case 4 (G1_8 seed 1, 2026-11-03): after the Bonk the client coasted 6 cells along the wall at about
0.55 cells/frame. The port does the same (`ClientSim::sprint_part_end` always queues the coast), and the coast's
speed uses the clip's rate when the MoveEvent fires (the sprint-off stats have already dropped the speed), not the
rate at the sprint's end. Before the fix the model stood at the wall and the next roll started 6 cells behind the
client (a snap).

## 4. SprintEnd coast: MoveEvent

Checked by replay: the coast line is a **curve line**: `MoveEvent_Start` calls `Positioned_SetMoveCurve(pos, clip, start, e)` with `e` from `0x141f62210` (`end` unclipped; clipped: `|end_cell - cell| * 10.869565 / (|off| / (end - start)) + elapsed`, the clipped branch is not ported yet). `0x141f63640` after the clip: fewer than 2 cells beyond the start = no move at all (f1455). The move event's end (clip end, tick 31) stops the line where it is, short of its end cell (f1755). **A blocked sprint step** ends the sprint in the Positioned tick with no coast and no plan on the next `0x64` (official `0x1d3` keyed to component 0, f3064, f3300); this overrides the Bonk inference above. Which layer: the export's layer 2 is all 5 at that wall, layer 0 fits; who sets `P+0x1e7` bit 1 is unread.

Timeline `GP_sprinting_end_base_01`: MoveEventType "move", time 0.0, end_time 0.75,
data `1 1 0 Everything 0 0 NoOverride 1.000000`. Event setup `0x141f60b20` (this = MoveEvent + 0x10):
```
start = ev.time(+0x0c); end = ev.end_time(+0x84); src_state = req(+0x4c)
off = ev.offset(+0x48..+0x50) (x negated when pos[+0x1e4] & 0x10)
disp = curve(anim, end) - curve(anim, start)        // 0x141ecd530 root curve value
if off == 0: off = disp scaled by ev(+0x68) (the 1.0) ...  // stored at MoveEvent+0x20..+0x28
```
`MoveEvent_Start` 0x141f5f650:
```
state(+0x94) = 2
(tgt, ok) = MoveEvent_GetTargetCell(ev); if !ok: return
// GetTargetCell, type != 3, no +0x4a/+0x4b, no running slot-0 action:
//   tgt = Positioned_RootOffsetToCell(pos, ev+0x20, scaled=1, from_cell=1)
dist(+0x7c) = |tgt - cell| (sqrt of int dx^2+dy^2, f32)
ctrl = AnimationController; st = ctrl+0x180 (main) or the state with id ev+0x1c
if tgt == cell: if anim[+0x68] <= 0: return; dist = anim[+0x68]
rate = ctrl[+0x178]; if rate != 0 and st[+0x54]: rate = 1.0; rate *= st[+0x30]; if rate <= 0: return
dur = (end - start) / rate; if dur <= 0: return
speed = dist / dur                                  // cells per second
if ev[+0x4b]: speed = max(speed, Pathfinding_GetSpeed); dur = dist / speed
(end_cell, clipped) = MoveEvent_ClipToWalkable(...)  // trace cell->tgt (mode < 2), pathing level pos[+0x498] (1 in mode 3)
if 0x141f63640(...) fails (Bresenham walk test, modes 0/4): end_cell = cell
if end_cell != cell:
   MoveEvent_MovePositioned(&end_cell, speed, flags, ev+0x48, entity)  // -> Positioned_MoveToWaypoint(pos, {end_cell, speed, orient})
state = 1
```
`Positioned_RootOffsetToCell` 0x141de6030 (`scaled`, `from_cell` both 1 here):
```
k = pos[+0x158][+0x74] (offset_scale) * pos[+0x474]
v = (pos[+0x46c] * off.x, pos[+0x470] * off.y)
r = (cos(t)*k*v.x - sin(t)*k*v.y, sin(t)*k*v.x + cos(t)*k*v.y)     // t = pos[+0x44c]; 0x140222f30 cos, 0x140222f40 sin
p = (cell + 0.5) * 10.869565 + r                                    // from_cell=0 would use pos[+0x490]
tgt = (floor(p.x * 0.092), floor(p.y * 0.092))                      // 0x14360bb64 = 0.092f
z  = k * off.z - grid_height(pos) * 7.8125
```
CORRECTION: target is `floor((world(cell) + R(facing) * off * offset_scale * pos+0x474) * 0.092)` with
`world(cell) = (cell + 0.5) * 10.869565`, not `grid + round(...)` (equal except at .5 ties). Speed is
`|tgt - cell| / ((0.75 - 0) / rate)` in cells/s (the unclipped distance: a clipped coast ends early).
Orientation mode: from `ev+0x48 +0x10` (1..4 -> 0..3), else `pos[+0x158][+0x2e]`.
`rate` = AnimationController `+0x178` (1 + virtual_action_speed%) x state `+0x30` (the type-3 rate above).
So with no action speed: `rate = speed_units / (600 * offset_scale * pos+0x474)`; matches the docs'
formula (Positioned `+0x474` = 1 assumed).

## 5. `0x64` handler `0x1421497c0` (case 100)

No sprint branch. In full:
```
if actor mode (vfunc +0x1d8) == 1 and the entity is in the world's list +0x608..+0x610: return
dir = msg[+0x20] (i32 x,y); c = msg[+0x28]
if dir != 0 and c != pos[+0x444]:
   if mode == 1 and |c - cell|^2 < 0x844: smooth correction (0x142196700 ...)
   else: 0x141ddb6f0(pos, c, (c + 0.5) * 10.869565)      // snap
if dir == 0 and actor axes != 0 and actor[+0x414] == 0: return
old = axes; axes(+0x400) = dir; actor[+0x414] = 1
Actor_StartWasdWalk(actor, old == 0 and dir != 0)
```
The sprint's length-550 vector is only the axes: `Actor_StartWasdWalk`/re-aim turn it into the plan
target `cell + world_to_cell(axes)` (550 x 0.092 = 50 cells, 180 -> 16), and the sprint turn then limits
the heading. A `(0,0)` never snaps.

## 6. `sprint_continues_with_move_input` (Player +0x20a)

Client config option, section `UI` (`[UI]` in the game's config ini), key `sprint_continues_with_move_input`:
settings callback `0x141013620` (on change) and `0x14100f3f3..0x14100f46e` (on load) set
`Player(+0x188 of the game state)[+0x20a] = value` and **send `0x2e8`** (vtable 0x1434e52b8, writer
0x141f380c0): body `u8 game[+0x181]`, `u8 bool value`. Same message class carries `0x31c`
(`GENERAL crossplay_disabled`, inverted). So the server receives the option: `0x2e8` is the "about 0.8 s
after spawn" message in instance.md (opcode `Unknown02e8` in instance.toml). The meaning of the first
byte (game `+0x181`) is unread.

## 7. Stats

- `is_sprinting` 0x5746: end check, sprint turn, animation choice 0x141e4f750 (`0x368`), `0x141e5d610`
  (Actor is-sprinting = `+0x915` or the stat), others at 0x140178193, 0x141890a66.., 0x141e411b8, 0x141e44b7d,
  0x141e4dd1c/0x141e4deba, 0x141e4edb7/0x141e4eed8, 0x141e4f4c4, 0x141e52571, 0x141ecdae1, 0x141eedd66,
  0x141f6708a, 0x141f678ca, 0x142006365 ... (byte search `BA 46 57 00 00`, 28 hits; not read).
- `must_sprint` 0x579a: end check (keeps the sprint); `0x141e3ff70` (can-start-action): while it is set a
  queued action (+0x248) may start only if its skill type (`+0xf8 -> +0x44`) is `0xedcc` (roll) or
  `0x56d7`; anything else waits (the attack waits until `must_sprint` goes off). Also 0x1401783dd, 0x141e4943c (unread).
- `dodge_roll_sprint_turn_rate` 0x5794: only `Pathfinding_SprintTurnWaypoint` (single hit 0x141dcc52a), deg/s.
- `base_move_speed_+%_from_sprint` 174: no `mov edx,0xae` stat read near movement (7 byte hits, none in
  movement code); the client's speed is `Pathfinding_GetSpeed` 0x141dccfa0 from `movement_velocity_+permyriad`
  (0xec), which the server sends with it (5000). The server folds 50% into the permyriad stat.

## Not read
- Caller of the part's `+0xa8` start and the meaning of `first` (Standing flip); `DAT_1445c69b0 +0x48`.
- `FUN_141d0fcf0` (grid re-register at start); who sets Positioned `+0x1e7` bit 0.
- Who replaces Actor `+0x380` when `SprintEnd` ends (the exact frame the refusal ends: clip end vs. one
  tick later); Positioned `+0x46c/+0x470/+0x474` values (assumed 1).
- `0x141f63640`/`0x141f66ae0` trace details (which cells count as blocked for the coast).
- Event data string -> MoveEvent fields (`+0x48`, `+0x4a`, `+0x4b`, `+0x8d`, `+0x54` type); inferred from behaviour.
- `0x2e8` first byte; mode-1 smooth correction path in `0x64`.

# Click-to-move: `0x1c8` Move to arrival (exact-port spec, Hotfix 1)

Exact-port spec for click-to-move in lockstep (local player). Overview: [wasd-movement.md](wasd-movement.md); siblings: [positioned](movement-positioned.md), [roll](movement-roll.md), [sprint](movement-sprint.md). Wire layout: [movement.md](../protocol/movement.md).

All addresses Hotfix 1. `A` = Actor component, `P` = Positioned (`entity+0x98`), `pf` = Pathfinding
(`entity->components[(A+0x210)+0xe4]`), `M` = the Move action (type `0x2909` at `+0x120`).
World mode = `world vfunc +0x1d8` (2 = lockstep in game, 1 = predictive). Raw tick decompile: `actor_tick_141e42a00.c`.

## Move action class
- Registered by name `"Move"` (type id = `fold16(FNV-1-style hash)`: `h = h*0x1000193 ^ c`, `id = (h>>16 ^ h) & 0xffff` -> `0x2909`), registry `0x141982310`, call site `0x141ccff66`.
- `MoveAction_Create` `0x141cd1af0`: size `0x358`, base ctor `0x14196e9f0(obj, 0x2909, ...)`, vtable **`0x1433e96f0`**, `+0x350` byte = 0.
- Action fields: `+0x120` type, `+0x122` action id, `+0x142` flags (u16), `+0x148` target entity, `+0x150` target cell (i32 x,y), `+0x180` start cell (from `0x1c8`), `+0xf8` skill.
- Vfuncs used (vtable offsets -> impl):

| off | impl | Move result |
|---|---|---|
| `+0x48` | `0x14196f7b0` | `vf70` is 1 -> **false** (Move goes to the Move slot, not slot 0) |
| `+0x70` | `0x140140d40` | 1 |
| `+0x80` | `0x1419851c0` | `+0x350` = 0 if `remap(|target-grid|, 6..13.5 -> 0.2..1)` < 0.4, 1 if > 0.8 (animation flag only) |
| `+0x88` | `0x1419852d0` | Player mode 2/3 only: `0x141971b80(M, &M+0x150)` |
| `+0xd8` | `0x1413ca440` | goal ptr: target entity ? `&ent.P+0x444` : **`&M+0x150`** |
| `+0x100` | `0x1401651e0` | orientation byte[1] = 0 (none: Positioned `+0x1e3` decides) |
| `+0x1f0` | `0x1419850f0` | **`sqrt(|grid - M+0x150|^2) >= 9.0`** (can start) |
| `+0x218` | `0x1401073d0` | 0 |
| `+0x220` | `0x1419850b0` | entity target ? `max(P+0x1f8,P+0x1f9)+2` : 0 |
| `+0x228` | `0x1413ca520` | `vf220 - vf258` = 0 for a point |
| `+0x238` | `0x140107600` | 1 |
| `+0x240` | `0x14197ac80` | 2 if skill flag 8 or stat `0x4944`; Player & no entity target: `walkable(goal, mode 0)` (`0x141d0df50`) ? 1 : 2; else 1 |
| `+0x248` | `0x14197ad70` | entity ? `(i8)ent.P+0x1fa` : **-1** |
| `+0x250` | `0x14197ada0` | `[0] = size(P) (0x141de5660) + (A+0x210)+0xf8`, `[1] = entity ? ... : 0x141d0d3d0(grid, goal) + 15` |
| `+0x258` | `0x1401073d0` | 0 |
| `+0x300` | `0x14197e120` | skill flag `0x30` and not `+0x144` bit 1 (channel); Move: 0 assumed (data not checked) |
| `+0x340` | `0x1413ca570` | `vf348 != 2pi` (`0x14197e160`, facing tolerance stat; default 2pi -> false) |
| `+0xa0` | `0x14196f6a0` | stance/weapon index (not movement) |

## 1. `0x1c8` handler (Actor sim handler `0x1421497c0`, case `0x1c8`)
Message (reader `0x141f69830`): `+0x3a` u16 flags (bit 7: target entity id u32 at `+0x20` follows, bit then cleared), `+0x2c/+0x30` start cell, `+0x24/+0x28` target cell, `+0x34` skill id u32, `+0x38` action id i16, `+0x3c` u8.
```
if msg.action_id >= 0 and byte A+0x250 != 0:          // predicted-action path; must be 0 in lockstep (the client walks)
    if |msg.start - grid|^2 < 0x2110: return; else P set location 0x141ddaf30; return
skill = find(A vfunc+0x168 ->+0x148 list, msg.skill_id); if skill stat 0x1dea: return
M = 0x141e892b0(skill, A+0x250, msg+0x3c)                // factory -> MoveAction_Create
M+0x122 = action_id; 0x14197cc40(M, msg.target)         // M+0x150 = target (+ notify M+0x2e8 list vf+0x98)
M+0x142 = msg.flags | 0x8000;  M+0x180 = msg.start
if msg.target_entity: 0x14197ccc0(M, entity)            // M+0x148
Actor_QueueAction(A, &M, &msg.start)                    // 0x141e3f100
```
`Actor_QueueAction` `0x141e3f100` (server action, flags < 0):
```
if A+0x4ba (remote): ...; if world+0x110: return 0; if entity+0x8c bit0: return 0
if (A+0x2a1 bit0) and M.vf2f0()==0 and Player stat 0x3e64==0: 0x141dd13f0(player, id); return 1   // refused
if queued(A+0x248) and queued+0x142 bit 12 (0x1000): return 0          // unreplaceable queued action
destroy queued (vf160, vf40, listeners 0x140ec62d0, 0x14197ab10, A+0x2a0 &= ~0x20, A+0x920 = 0)
A+0x248 = M; A+0x3bc = msg.start (8 bytes); A+0x920 = GetTickCount()
if P+0x1e4 bit0: return 1            // deferred: started by Actor tick step 1
Actor_StartQueuedAction(A)           // 0x141e40b50, runs now, inside the packet drain
```
`Actor_StartQueuedAction` `0x141e40b50`, Move branch only:
```
if A+0x2a2 bit0: return; set bit0 (re-entry guard, cleared at exit)
(first block skipped: type == 0x2909)
(A+0x2a0 bit1 slot-0 combo block: not for a plain click walk)
if !Actor_CanStartAction(A, 0, M+0x142, 0): return   // 0x141e3ff70: server flags (<0) -> true unless
                                                     // world vf188 gate, entity+0x8c bit0, A+0x2a1 bit1
if !M.vf1f0():   0x141e5d9f0(A, M) (feedback); destroy M; return      // TARGET WITHIN 9 CELLS: dropped,
                                                                      // the running Move is untouched
if M.vf70 and anim A+0x380 in {0x36a,0x36b,0x371,0x372}: destroy M; return
if A+0x2a0 bit6 or entity+0x8c bit0: destroy; if !A.vfC0(skill id, type): destroy
(skill flags 0x74/0x75, 0x7c27e6cc: not Move)
save world+0x120 byte, clear it; A+0x41c = 0.03
if slot0 (A+0x238) and !slot0.vf50: Actor 0x141e453d0(A,0) (cancel slot 0)
M.vf48 == false ->
    Actor_EndMoveAction(A, 0)                                   // old Move ends, LINE KEEPS RUNNING
    if A+0x240 == 0 and (no slot0 or (slot0.vf50 and M.vf70)):
        A+0x2a0 &= ~0x10; if bit5: A+0x2a0 = (A+0x2a0 & ~0x30) | 0x10
        Actor_InstallQueuedMove(A, &A+0x240)                    // 0x141e41c60
        Actor_PlanMove(A)                                       // 0x141e42650: first plan, same frame
        world vfunc +0xa0; restore world+0x120
```
`Actor_InstallQueuedMove` `0x141e41c60` (entry also `0x141e41d20`, mid-function):
```
if *slot: return
if A+0x3bc.x != INT_MIN:
    lockstep (mode 2): snap iff start != grid          // exact, no tolerance
    predictive (mode 1): snap iff |start-grid|^2 >= 0x844
    snap = 0x141ddb6f0(P, &start, world((start+0.5)*10.869565))   // stops a running line
*slot = A+0x248; A+0x248 = 0; A+0x920 = 0; delete old *slot
A+0x2b2 = M+0x122; listeners A+0x18 <- 0x14020ad50(A, M); A.vf348()
if M+0x148: M+0x150 = ent.P+0x444 (notify)
A+0x2b0 = (A+0x2b0 + 1) & 0x7fff, 0 -> 1                 // move counter
if M.vf340 and !0x141e5c2f0: Player+0x260 = stat 0x46dc / 1000
```
Flags: `0x8000` = from server (set by the handler). Bit 12 `0x1000` blocks replacing a queued action. Bit 10 `0x400` and bit 0 are only read on client-initiated paths (`0x141e3f100`, `0x141e3ff70` with flags >= 0, `0x14196f7b0`). **`0x10` is never tested at `+0x142`** (no `test [..+0x142],0x10` in the binary): `0x10`/`0x400`/`0x410` are request echoes with no effect on a server Move.

## 2. Plan `Actor_PlanMove` `0x141e42650`
```
if !A+0x240: return; if !A+0x238: 0x141f5e820(A+0x1c0)
M.vf80()                                   // +0x350 anim flag
pf = components[(A+0x210)+0xe4]; if !pf: return
A+0x3b8 = M+0x148 ? ent+0x88 : 0
if !slot0 or slot0.vfE0()==1.0: Actor_ApplyActionSpeedFactor(A, M)
if M.vf300()==0: A+0x3dc = has Player component ? 0.05 : 0.25
(Player mode 2/3 at Player+999, non-Move with entity: A+1000 = A+0x3e0)
moving = A+0x2a0 bit7; v0 = moving ? Pathfinding_GetSpeed(pf) : 0
goal = M.vfD8()                            // &M+0x150 for a point
A+0x2a1 |= 4
arg = (A+0x424 <= 0) ? M.vf258() : 0       // 0 for Move
req = Action_GetPathRequest(M)             // 0x14197abb0
ok = Pathfinding_FollowPath(pf, goal, &req, arg)
A+0x2a1 &= ~4
if !ok: A+0x150 += 1; listeners A+0xb8.. and A+0x20.. <- 0x140ec62e4(A, type, &goal)   // path failed
if moving and A+0x2a0 bit7 and (A+0x8fa or anim A+0x380 != 0x141e4f750(A) or speed != v0): 0x141e4f860(A, -1.0)
```
`Action_GetPathRequest` `0x14197abb0` -> req (7 dwords): `[0] = max(vf218,1)-1`, `[1] = max(vf228,1)-1`, `[2] (i8) = vf248`, `[3] = vf238`, `[4] (u8) = vf240`, `[5],[6] = vf250(1.0)`. **Point Move: `r0 = 0, r1 = 0, mode = -1, count = 1`, `[4]` = 1 (goal walkable) or 2.**

`Pathfinding_FollowPath` `0x141dcbf30`:
```
pf+0x540 = goal ptr; pf+0x520..+0x538 = req
pf+0x52c = (pf+0x560 bit1) ? 1 : clamp(req[3] or 1, ..5); clamp req[0], req[1] to 0x400; pf+0x564 = arg
s = Pathfinding_GetSpeed(pf, .., 1)
stop = (P+0x480 > 0 and s <= P+0x484) or pf+0x560 bit1 or s <= 0 or P+0x49a bit4;  if stop: req[0] = 0
if Pathfinding_IsArrived(pf, *goal, req, arg):
    if pf+0x560 bit0: Pathfinding_EndPath(pf, 0); return 1
    pf+0x560 &= ~8; pf+0x540 = 0; pf+0x18 listeners <- 0x14020ad50 (arrived); P+0x18 <- 0x140ec62d0; return 1
if stop: pf+0x560 &= ~8; Pathfinding_EndPath(pf, 0); return 0
return Pathfinding_Plan(pf)
```
`Pathfinding_Plan` `0x141dcc6a0` (search itself in pathfinding.md):
```
pf+0x574 = 0                                    // time since plan
bit3 of pf+0x560: two-point path (goal, cell), count 2
else d = goal - grid; |d|^2 < 0x4840 ? search(goal) : search(grid + 126*unit(d)) (no success flag)
if pf+0x52c > 1: pf+0x52c = 1; arrival re-check (same as FollowPath arrived branch)
if count (pf+0x518) != 0:
    search flag -> P+0x1e4 |= 4
    pf+0x570 = count - 1; pf+0x568 = *goal       // goal at plan time
    if !(pf+0x560 bit0): pf+0x18 listeners <- 0x14025613c (started); P+0x18 <- 0x14019ad14(&pf+0x568); bit0 = 1
    bit2 set; Pathfinding_StepAlongPath(pf, pf+0x570); bit2 clear; return found
else: bit0 ? Pathfinding_EndPath(pf,0) : (pf+0x540 = 0; listeners <- 0x14020ad94 (ended); P+0x18 <- 0x140ec62fc); return 0
```
Path array `pf+0xd4` (`[0]` = goal end, `[count-1]` = start); `Pathfinding_StepAlongPath(pf, i)` reads `pf+0xcc + i*8` = path `[i-1]`.

`Pathfinding_IsArrived` `0x141dcb810(pf, goal, req, arg, out)`:
```
r0 = (pf+0x560 bit1 or speed <= 0) ? 0 : min(req[0], 0x400); r1 = min(req[1], 0x400); n = bit1 ? 1 : clamp(req[3], 1..5)
d2 = |grid - goal|^2
mode = (i8)req[2]
mode < 0 -> 0x141dcba70:
    if d2 < r0^2: false
    if d2 <= r1^2: true if grid == goal or req[4] == 2; else los = 0x141d104f0(terrain, grid, req[5], goal, req[6], arg, req[4]); return !los
    if n != 0 and d2 <= (r1+n)^2:
        p = goal + normalize(grid-goal) * r1
        if !0x141d10070(terrain, grid, p, min(P+0x1f8+1, 5), P+0x498) and !0x141dee840(terrain, grid, p, max(P+0x1f8,P+0x1f9)+1, P+0x498): true
    false
mode >= 0 -> 0x141dcbc20 (entity radii; not a point Move)
```
**Point Move (r0 = r1 = 0, n = 1): arrived iff `grid == goal`, or `d2 == 1` (one orthogonal cell) and the step onto the goal is blocked (`0x141d10070` false and `0x141dee840` false).**

`Pathfinding_OnLineDone` `0x141dccdb0` (Positioned listener vtable `0x1434d19c8` slot `+8`, `this = pf+0xc0`; fired by the Positioned apply `0x141dddcc0` when a line ends, inside the Positioned tick):
```
if !(pf+0x560 bit0): return
if goal ptr and Pathfinding_IsArrived(pf, *goal, pf+0x520, pf+0x564): Pathfinding_EndPath(pf, 0); return
pf+0x570 -= 1
if pf+0x570 > 0: Pathfinding_StepAlongPath(pf, pf+0x570)   // next waypoint, same tick (advance(0) overshoot)
else: Pathfinding_Plan(pf)                                  // index 0: replan from grid (partial path / blocked)
```
`Pathfinding_EndPath` `0x141dccac0(pf, keep_line)`:
```
if !(pf+0x560 bit0): return
if !keep_line: bit2 set; entity+0x8c bit3 ? 0x141de4c30 : 0x141de4de0(P) (stop: smoother, 0x141de5f50 if a line runs); bit2 clear
arrived = goal ptr and Pathfinding_IsArrived(...)
pf+0x560 &= ~9; pf+0x518 = 0; pf+0x540 = 0
arrived ? (pf+0x18 <- 0x14020ad50 (slot +0x10); P+0x18 <- 0x140ec62d0(entity, &goal))
        : (pf+0x18 <- 0x14020ad94 (slot +0x08); P+0x18 <- 0x140ec62fc)
```
`Pathfinding_Tick` `0x141dcce80` (component tick, `vtable+0x50(dt)`, already named by another agent) - **arrival is checked every frame here too**:
```
pf+0x580 = dt; pf+0x578 = facing vector (0x140163cf0(P)); pf+0x574 += dt
if !(pf+0x560 bit0): return
if !goal ptr or Pathfinding_IsArrived(...): Pathfinding_EndPath(pf, 0); return
if pf+0x574 >= 2.0 and pf+0x568 != *goal: Pathfinding_Plan(pf); return
if pf+0x574 < 0.7 or |pf+0x568 - *goal|^2 < 4096: return
Pathfinding_Plan(pf)
```
A point Move's goal never moves (`pf+0x568 == *goal`): no tick replans. So `pf+0x580` = `dt` exactly (the sprint turn's `rate * pf+0x580`).

### Actor's Pathfinding listener (Actor `+0x158`, vtable `0x1434da888`, set in Actor ctor `0x142147160`)
| slot | thunk fired by pf | impl |
|---|---|---|
| `+0x00` | `0x14025613c` path started | `Actor_OnPathStarted` `0x141e4db60`: `A+0x2a0 |= 0x80` (**moving**), `A+0x2a1 |= 0x10`, move animation `0x141e57b80(A, anim 0x141e4f750, speed stat 0x6996, 0x5735/1000)`, `0x141e4f9b0(A,0)` |
| `+0x08` | `0x14020ad94` ended, not arrived | `0x1416d5080` -> `Actor_OnPathEnded(A, 0)` |
| `+0x10` | `0x14020ad50` arrived | `0x1416d5070` -> `Actor_OnPathEnded(A, 1)` |
| `+0x18` | StepAlongPath request (`vfunc +0x18`) | `0x141e4dce0` waypoint (group bounds, facing, orientation `P+0x1e3` from `M.vf100`) |

`Actor_OnPathEnded` `0x141e4dfa0(A, arrived)`:
```
save/clear world+0x120; A+0x2a0 &= ~0x80; clear P+0x2a8..+0x2d8, P+0x330..+0x360
if !arrived: (WASD Move with axes and not in plan) ? re-aim 0x141e50320 : Actor_EndMoveAction(A, 0)
else if A+0x240: Actor_OnPathArrived(A)
if no slot0, no Move, A+0x2a1 bits 1,2 clear, A+0x2a0 bit6 clear, entity+0x8c bit0 clear, bit3 set, (A+0x210)+0x100 == 0:
    world vfa0; Actor_StartQueuedAction(A); if still idle and Actor_CanStartAction(A,0,0,0) and !(A+0x2a1 bit1): A+0x18 <- 0x14020ad94(A, 0)
if 0x141e4e270(A, 0): idle animation 0x141e57b80
restore world+0x120
```
`Actor_OnPathArrived` `0x141e4e720`:
```
M = A+0x240; clear A+0x85d
if M.vf340 (false for Move): face target 0x141e50940, 0x141f5ebc0(...)
if !0x141e4e350(A, M): return            // Move: vf70 = 1 -> true
M.vf88()
if type 0x2909 and axes A+0x400/404 != 0 and M+0x122 == 0: re-aim; return    // client WASD only
(M.vf70 = 1: the 'perform skill at destination' block is skipped)
Actor_EndMoveAction(A, 0)
```
`Actor_EndMoveAction` `0x141e45da0(A, stop)`:
```
M.vf38(); A+0x240 = 0; A+0x2a0 &= ~0x10
if pf+0x540 == &M+0x150: pf+0x568 = M+0x150; pf+0x540 = &pf+0x568      // path keeps a copy of the goal
listeners A+0x18 <- 0x141d6d494(A, M); event 0x4be8c69a; stat 0x46dc: Player+0x260 = 0
if stop and A+0x2a0 bit7: Pathfinding_EndPath(pf, 0)                   // only stop=1 stops the line
0x14197ab10(M); delete M
```
**Arrival frame:** the grid reaches the goal in the Positioned tick (frame step 1, `0x141ddc9d0`); the apply of that cell ends the line -> `Pathfinding_OnLineDone` -> arrived -> `Pathfinding_EndPath(pf,0)` -> `Actor_OnPathEnded(A,1)` -> `Actor_OnPathArrived` -> `Actor_EndMoveAction`: **the Move ends in the same tick as the last step**, before that frame's packets and Actor tick. `Pathfinding_Tick` catches the case where the goal is reached without a line end (frame order of the Pathfinding component not read).

## 3. Plan timer `+0x3dc` and replans of a target Move (Actor tick `0x141e42a00`)
- Step 2 (lines 152-185 of the decompile): `(A+0x210)+0xe8 == -1`, no slot 0, Move type `0x2909` and `+0x3dc <= 0` -> `Actor_CanStartAction(A,0,0,0)` and `!(A+0x2a1 bit1)` -> listeners `A+0x18 <- 0x14020ad94(A, 0)`: "ready for the next action" (input queue). **No plan.** (`+0xe8 != -1`: `vf300` or timer > 0 skip; else same notify and `Actor_StartQueuedAction`.)
- Step 5: axes non-zero only (`0x64`); a click walk has axes 0.
- Step 6: `mode == 1` (predictive) and Move and `!(A+0x2a0 bit7)` and no slot 0 and `+0x3dc <= 0` -> plan. **Not in lockstep.**
- Step 8: `M.vf340` false -> no plan. Step 9: `+0x424` (action speed timer, scaled by `A+0x228+0x178`), `+0x428` (`param_1[0x85]`), the `+0x2a2` bit 3 / `+0x4a0` target block -> plan; none is armed by a click walk.
- `0x1ca` handler: `A+0x2a0 |= 0x10`; Move and bit7 clear -> plan (predictive only: returns unless mode 1).
- Tail: `+0x3dc -= dt` (clamped 0).
**So in lockstep a point Move plans only: at its `0x1c8` (first plan), at each `Pathfinding_OnLineDone` with index 0 (partial path beyond 126 cells or a blocked line), never on the 0.05 s timer. Goal is `M+0x150`, unchanged.**

## 4. Speed
`Pathfinding_GetSpeed` `0x141dccfa0(pf, .., reduce)`: `pf+0x554 >= 0` -> that value. Else stats component index `(i8)(pf+0x548)+0x59` (< 0: `pf+0x550 * pf+0x55c`): `f = 1 + max(stat 0xec, -10000)/10000`; stat `0xc39` != 0: `f *= 1 + max(v,-100)/100`; `base = pf+0x550`, `reduce`: `base = max(base - pf+0x558, 0)`; `v = base * f * pf+0x55c`; stat `0x44a` > 0: `v = 0x14014dca0(v, cap)` (cap). Same for Move and WASD. `pf+0x580` writer = `Pathfinding_Tick` (`= dt`).

## 5. Held click (new `0x1c8` Move while a Move runs)
- A Move closer than 9 cells does not start (vf `+0x1f0` `0x1419850f0`); test in `crates/poe-game/tests/rules.rs`.
- Same path as a press: new action, `Actor_StartQueuedAction` in the packet drain. If `|grid - new target| < 9.0`: dropped, old Move continues to its old target.
- Otherwise `Actor_EndMoveAction(A, 0)`: old Move deleted, **no line stop**, `pf+0x560` bit0 stays (no new "started" event, `A+0x2a0` bit7 stays), `pf+0x540` points at the saved old goal copy until the new `FollowPath`.
- Snap only when `0x1c8.start != grid` (lockstep exact); a snap stops the line (`0x141ddb6f0` -> `0x141de5f50`), so the new line starts at the snapped cell with `len = 0` (no continuity).
- No snap: new plan from the grid; `Positioned_MoveToWaypoint` -> `FUN_141ec86a0` keeps continuity (`running` = `+0x61 == 0`, `len != 0`, old current cell == s; `p` = old line point if `p != e` and `|s-p|^2 < 4`).
- Server restarts (`0x1c8` same target, header `(player,player,9,1)`) take the identical path: replan from the grid, line continuity kept.

## Server: knowing the arrival
No C->S message exists. The server runs this logic itself: the Move ends in the tick where the ported Positioned tick applies the goal cell (or `d2 == 1` with a blocked step), via the ported `Pathfinding_OnLineDone`/`Pathfinding_Tick` arrival test with `r0 = r1 = 0, n = 1`.

## Not read / open
- Positioned `+0x1e4` bit 0 (defers the start to Actor tick step 1): who sets it.
- Actor `+0x250` byte (the predicted-action branch of `0x1c8`): assumed 0 in lockstep.
- `A.vfC0(skill id, type)` and `0x141e5c2f0` for Move; skill flags `0x30` (vf300), `0x74`/`0x75` for the Move skill (data).
- `0x141d10070`, `0x141dee840`, `0x141d104f0` (line-of-walk tests in the arrival rule) not read.
- Component order of Pathfinding vs Positioned vs Actor in the player's component list (`Pathfinding_Tick` position in the frame).
- `0x141e4dce0` waypoint handler details (group bounds `0x141ddf430`, facing `0x141ddc820`).
- `(A+0x210)+0xe8` meaning (component index; -1 for the player assumed).

Renamed in Ghidra: `Actor_InstallQueuedMove` `0x141e41c60`, `Actor_StartQueuedAction` `0x141e40b50`, `Actor_QueueAction` `0x141e3f100`, `Actor_CanStartAction` `0x141e3ff70`, `Actor_PlanMove` `0x141e42650`, `Actor_EndMoveAction` `0x141e45da0`, `Actor_OnPathEnded` `0x141e4dfa0`, `Actor_OnPathArrived` `0x141e4e720`, `Actor_OnPathStarted` `0x141e4db60`, `Pathfinding_FollowPath` `0x141dcbf30`, `Pathfinding_IsArrived` `0x141dcb810`, `Pathfinding_OnLineDone` `0x141dccdb0`, `Pathfinding_EndPath` `0x141dccac0`, `Pathfinding_Plan` `0x141dcc6a0`, `Action_GetPathRequest` `0x14197abb0`, `MoveAction_Create` `0x141cd1af0`.

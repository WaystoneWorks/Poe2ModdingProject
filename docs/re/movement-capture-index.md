# Movement capture indexes

Frame indexes of official captures used for the movement port; the protocol facts are in [movement.md](../protocol/movement.md).

## Capture index: 2026-10-20 session
`dumps/0.5.5f/captures/official/2026-10-20_18-41-14_336/` (13 299 instance messages, 4 765 frames, 33 min; `check_capture`: every movement message decodes with 0 errors and 0 leftover bytes; only `AddInventory` items mismatch). Frame = capture frame, `T` = tap, `H` = hold, the number is the frames Space was down:

| Item | What is there |
|---|---|
| 1 standing roll, 5 taps + hold | f516 T7, f560 T8, f606 T5, f652 T3, f696 T3, f744 T4; hold f1132 H125 (sprint, cursor-follow stream, wall f1243, Space up f1257) |
| 2 taps 0.1/0.3/0.45/0.5 s | mostly **standing** (the keys were up): T3 (f652, f696), T4-8 (f516-f745, f1477), walking: T7 (f2458), T8 (f2065), T12 (f1934); T14 (f1572, f4178). No 9-frame (0.3 s) tap, 15-18 not hit |
| 3 chained re-press | f1476/1514 (38 apart), f1570 (press+release in one frame), f1581 (+9), f1600 (+28), f1633 (+31); f3607 H20, f3645 T3 (+38), f3679 T3 (+34), f3711 T5 (+31), f3742 H155 (+29); no re-press while sprinting |
| 4 stop all WASD during sprint / roll | f1793-1796: keys released with Space down (cursor vector, then Space up, `(0,0)`); no `(0,0)` during a roll or sprint |
| 5 attack while rolling; Esc during a sprint | attacks in the roll at f1946, 1991, 2075-2088, 4033; Esc (`SetPause`) f1543-1570, 1844-1852, 3224-3238, 4612-4628, never during a roll or sprint |
| 7 sprint into wall / monsters | wall: f1243, f1918, f2873; monsters: sprints ended by attacks f2393, 4056, 4142, 4262 |
| 8 roll with monster hovered; get hit | no `0x1aa`/`0x1b0`; one light stun f4072 |
| 9 click-to-move | hold f3325 (41 frames), singles f3375-3509, hold f3527-4002 with rolls, f4069/4100/4160/4462 holds with attacks and rolls |
| 10 held click + Space | inside holds: f3607 H20 (sprint cut short, ends f3643), f3742 H155 (sprint 3759-3897), f4105 H52, f4178 T14, f4216 H64, f4484 H100 |

## Capture index: 2026-11-02 session
`dumps/0.5.5f/captures/official/2026-11-02_18-31-34_336/`: 27 episodes. Frame = capture frame.

| Item | What is there |
|---|---|
| Sprint ends | 18; causes in `runtime/r3-2026-11-02-sprint-ends.txt`: release 12, attack 3, `t0+35` 1, other 2 |
| Held click during a sprint | f7746, f7910 (Space released); 2026-10-20_21-51-49 f8873, f8952, f9154 |
| Deferred rolls | f8037, f8075 |
| Space re-press | f2178 |
| Weapon swaps | f5464 (auto), f6088 (requested), f11798 (auto, ending a sprint) |
| Input-mode toggles | f7577, f8287 |
| Held roll repeats | f11801, f12757 |
| Key changes during rolls and sprints | `runtime/r3-2026-11-02-gap4.txt`: 61 during sprints, 54 during rolls, 3 presses during a roll (one in a standing tap roll), 3 releases during tap rolls; all replay identically |

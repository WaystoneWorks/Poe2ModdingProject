# Time scale

Is there a client-honoured way to slow or speed the whole simulation? Static RE of 0.5.5h, and the private-server run below. Frame queue and playback: [movement.md](../protocol/movement.md#timing).

## The mechanism: `0x2f8` SimulationFrameValue
There is no time-scale message, but `frame_ms` works as one, because the client's simulation time is the sum of recorded frame lengths.

- `0x2f8` (`u8`, 0-255 ms; official servers never send it) sets world +0x124 through vfunc +0x178 (`0x140b2afc0`) on arrival. Each later `0x2f7` pushes that value into the frame deque (`0x1421439a0`). So it must precede the marker of the first frame at the new length.
- Playback `0x14213fac0` drains a frame only when marker and bank allow, and passes `ms / 1000` as `frame_dt`.
- `frame_dt` reaches all simulation: `0x14213fec0` to the entity loop `0x142146a60` (component vfunc +0x50, `0x141e8bf30`) and `0x14213f630`.
- Visuals use played time, not real time: `0x142140400` captures only world and `v` (`min(+0x674, dt * speed)`), and its job `0x142147ca0` passes `v` to component vfunc +0x58 and `0x141e8c140`. So animation scales with movement.

**Slower (s < 1):** keep the 33 ms real tick and send `frame_ms = round(33 * s)`. The bank is capped at the next frame's length, so a starved client plays one frame per marker: simulation rate = `frame_ms` per marker. Granularity is 1/33. Stretching the real tick instead also works but lowers the update rate.

**Faster (s > 1):** limited by the speed factor +0x670, which needs a queue: 1.5x at 2+ spare frames, 2x at 30+, 5x at 60+. Up to 1.5x costs about 2 frames of latency; beyond that at least 30 frames (1 s or more). Above 5x the queue grows without bound.

**Scope:** whole instance. The instance has one clock and one `dt`, so all its sessions must get the same value.

## Server implementation and result
`time scale <factor>` ([../guides/server-admin.md](../guides/server-admin.md#commands)) sets the instance's frame length: the actor (`Cmd::SetFrameMs`) sends `0x2f8` to every session before the marker of the first frame at the new length and calls `World::set_tick_ms`, so the world steps with `dt = frame_ms / 1000` while the real tick stays `[instance] tick_ms`. Factors run from 1/33 to 1 in whole milliseconds; factors above 1 are refused (they need a frame queue and add latency).

Private-server result (game test `commands`, same walk at both factors): at factor 0.5 the walk covers about 58% of the distance (21.2 cells against 36.8), and the drift stays low (max 0.71 and 1.51 cells, under the test's limit of 2).

The roll's timeline in `poe-game` `locomotion.rs` keeps game time: `TAP_END_FRAMES`, `ATTACK_CANCEL_FRAMES`, `MUST_SPRINT_END_FRAMES` and `WALL_STUN_OFF_FRAMES` were measured at 33 ms and are stretched to the frame length (`game_frames`), like the roll's own clock. In frames, at 3 ms `must_sprint` went off before the sprint started and a click queued in the roll was dropped (game test `b4-roll-click`; rules test `a_scaled_frame_keeps_the_roll_timeline_in_game_time`). Input cadences (`CLICK_RESTART_FRAMES`, `STALE_FRAMES`, `RELEASE_WINDOW_FRAMES`) and the `clientsim.rs` frame counts stay in frames (not checked at other frame lengths).

## Still real time
Client timer list world +0x878 (decremented with real `dt` in `0x14213fac0`, purpose unknown), the session's report and latency logic (`0x1421303e0`; +0x11c read at `0x142130938` as `rtt + 2 * frame_ms`), AimTarget's 33 ms cadence, audio, UI. Effects of these untested.

## Ruled out
- Multiplier on real `dt` inside `0x1421303e0`: passed straight to playback, no `mulss`/`divss`.
- Strings: `use_world_speed` and `TimeMultiplier` sit in the particle and material loaders (`0x14290171b`, `0x142b30a70`); `scale_simulation_speed` (`0x1428fa6b4`) and `shine_time_scale` by location and name only.
- `SetPause` `0x1fe` (world +0x890): dt 0 only.
- Stats (name search of `stats.datc64`, no code read): `*_time_passed_+%` look like buff timers, `action_speed_+%` and `map_*_speed_+%` per entity; no world time stat.
- `frame_ms = 0`: drains at once with dt 0; use `SetPause`.

## Unknown
- Client behaviour at very low `frame_ms` (only 0.5 was run).
- `TimeStop`, `TrialmasterTimestop` (action classes, `0x1413ee01b`, `0x1413ec3fb`): behaviour not read.
- Where the caller of `0x1421303e0` gets real `dt`; no sweep of all instance handlers for a global time write.

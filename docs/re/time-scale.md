# Time scale

Is there a client-honoured way to slow or speed the whole simulation? Static RE of 0.5.5e Hotfix 1; no private-server run yet. Frame queue and playback: [movement.md](../protocol/movement.md#timing).

## The mechanism: `0x2f5` SimulationFrameValue
There is no time-scale message, but `frame_ms` works as one, because the client's simulation time is the sum of recorded frame lengths.

- `0x2f5` (`u8`, 0-255 ms; official servers never send it) sets world +0x11c through vfunc +0x178 (`0x140b27ac0`) on arrival. Each later `0x2f4` pushes that value into the frame deque (`0x142134260`). So it must precede the marker of the first frame at the new length.
- Playback `0x142130440` drains a frame only when marker and bank allow, and passes `ms / 1000` as `frame_dt`.
- `frame_dt` reaches all simulation: `0x142130840` to the entity loop `0x142137270` (component vfunc +0x50, `0x141e7d970`) and `0x14212ffb0`.
- Visuals use played time, not real time: `0x142130d80` captures only world and `v` (`min(+0x674, dt * speed)`), and its job `0x1421383a0` passes `v` to component vfunc +0x58 and `0x141e7db80`. So animation scales with movement.

**Slower (s < 1):** keep the 33 ms real tick and send `frame_ms = round(33 * s)`. The bank is capped at the next frame's length, so a starved client plays one frame per marker: simulation rate = `frame_ms` per marker. Granularity is 1/33. Stretching the real tick instead also works but lowers the update rate.

**Faster (s > 1):** limited by the speed factor +0x670, which needs a queue: 1.5x at 2+ spare frames, 2x at 30+, 5x at 60+. Up to 1.5x costs about 2 frames of latency; beyond that at least 30 frames (1 s or more). Above 5x the queue grows without bound.

**Scope:** whole instance. The instance has one clock and one `dt`, so all its sessions must get the same value.

## Server requirements
- Simulate with `dt = frame_ms / 1000` in the same frame as the marker; real tick and `dt` become separate values (today both are `tick_ms`).
- Rules counted in frames were measured at 33 ms and need review at another `frame_ms`: the `*_FRAMES` constants in `poe-game` `locomotion.rs` and `clientsim.rs` (for example `ATTACK_CANCEL_FRAMES`, `TAP_END_FRAMES`).

## Still real time
Client timer list world +0x850 (decremented with real `dt` in `0x142130440`, purpose unknown), the session's report and latency logic (`0x142120cf0`; +0x11c read at `0x142121248` as `rtt + 2 * frame_ms`), AimTarget's 33 ms cadence, audio, UI. Effects of these untested.

## Ruled out
- Multiplier on real `dt` inside `0x142120cf0`: passed straight to playback, no `mulss`/`divss`.
- Strings: `use_world_speed` and `TimeMultiplier` sit in the particle and material loaders (`0x1428eeddb`, `0x142b1e130`); `scale_simulation_speed` (`0x1428e7d74`) and `shine_time_scale` by location and name only.
- `SetPause` `0x1fe` (world +0x868): dt 0 only.
- Stats (name search of `stats.datc64`, no code read): `*_time_passed_+%` look like buff timers, `action_speed_+%` and `map_*_speed_+%` per entity; no world time stat.
- `frame_ms = 0`: drains at once with dt 0; use `SetPause`.

## Unknown
- Client behaviour at low `frame_ms` (never exercised officially): needs a private-server run.
- `TimeStop`, `TrialmasterTimestop` (action classes, `0x1413e517b`, `0x1413e355b`): behaviour not read.
- Where the caller of `0x142120cf0` gets real `dt`; no sweep of all instance handlers for a global time write.

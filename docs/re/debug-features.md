# Debug features in the client (0.5.5h)

What the retail client keeps of its debug and developer tooling, how to turn each part on, and how much it helps movement sync (B4: [../plans/pre-p10.md](../plans/pre-p10.md), [world-travel.md](world-travel.md)). The correction rule, the `0x13c` resync message and predictive mode are in [server-code.md](server-code.md); the command-line options are in [standalone-login.md](standalone-login.md). All addresses are 0.5.5h.

**Summary.** The retail build is stripped: there is no developer console, no cvar system, no `[DEBUG]` config section, no internal-build check, and the debug-draw script functions do nothing. What is left is a performance overlay with a network line, per-component debug printers that nothing calls, client warnings in `Client.txt` when the server's action messages do not match the client's state, and a chat command table with resync rows that have no command text.

## Ranked for B4

| # | Finding | How to turn it on | Helps B4 |
|---|---|---|---|
| 1 | [Performance overlay](#1-performance-overlay): CPU, GPU, `network` (latency), `server`, frame time, FPS | **F1** in game | medium: shows late frames and latency during a snap |
| 2 | [Positioned debug printer](#2-component-debug-printers) `0x141dec130`: grid cell, position, destination, speed, moving flags | no caller; the DLL can call it | medium: a field map for the movement log |
| 3 | [Action-desync warnings](#3-action-desync-warnings-in-clienttxt) in `Client.txt` | always on | low now (our server sends none of those packets), high once skills exist |
| 4 | [Chat command table](#4-chat-command-table): `ForceResync`, `ForceResyncPlayer`, `/debug`, `/verify` | type the command; the resync rows need a data mod | low |
| 5 | [`command_line.txt`](#5-command_linetxt) | file in `My Games\Path of Exile 2` | low: test convenience |
| 6 | [Script debug functions](#6-script-geal-debug-functions) (`ProximityTriggerDebug`, `EnableGEALDebugging`) | object scripts only | none: bodies stripped |
| 7 | [Client cheat registry](#7-client-cheat-registry) | none reachable | none |

## 1. Performance overlay
- **Toggle:** action `performance_overlay` (client string `ActionTogglePerfGraphs`, "Toggle Performance Metrics"), default key **F1** (`performance_overlay=112` in `[ACTION_KEYS]` and `[WASD_ACTION_KEYS]` of `poe2_production_Config.ini`). Works on our server; no flag needed.
- **Settings** (`[UI]`): `performance_metrics_state` (reader `0x141948a30`, absent from the test prefix's config until the overlay is toggled), `performance_metrics_graph_mode` (`0x1419488c0`; the prefix has `all`), `performance_metrics_bars`, `performance_metrics_transparency`. Loaded by `0x1417595a0` into globals `0x143a24040` (state at `0x143a24044`).
- **Draw:** `0x141759ca0`. Text lines `cpu: {} ms`, `gpu: {} ms`, `network: {} ms`, `server`, `mem`, `vram`, `drive: {}/s`, `shader: {}`; graphs `latency {:.0f} ms`, `frame {:.0f} ms`, `{:.0f} fps`. Client strings: `TelemetryLatency`, `TelemetryFPS`, `TelemetryFrameTime`, `TelemetryServerFrameTime`.
- **Data:** stats block `0x1445ec460`. The frame loop accumulates with `0x141050380`, which closes a sample every 0.25 s (`0x14104ff30`); the last 80 samples are kept; `0x1410507b0` builds the current sample and `0x141050b20` blends the last two for display.
  - `network` is the latency estimate, session `+0x2260` (`u32`), set from the first `u16` of every `PingReply` `0x1d` ([instance.md](../protocol/instance.md#frame-reports-and-ping-replies)); stored each frame by `0x141050dc0` (stats `+0x11c`), called at `0x1410131bb` in `0x141012960`.
  - `server` is a float at `+0x4f8` of the object that `0x141012960` walks (stats `+0x120`). Its source is not read; the client string names it "Server Frame Time (ms)".
- **Use for B4:** the user or a game test can watch frame time and latency while a snap happens. A stall in our `0x2f7` stream freezes the client's frame playback and a burst makes it rush ([movement.md](../protocol/movement.md#lockstep-the-server-starts-every-movement)); the overlay shows that without a capture. The latency line shows only what our `PingReply` reports.

## 2. Component debug printers
Each component class has a debug-info method that writes `=== <Name> Info ===` and its fields into a wide string stream (argument 2, stream at `+0x10`). Header strings `0x1433baf28` (`=== `) and `0x1433baf38` (` Info ===`) are used by 29 such functions (for example `0x141dec130` Positioned, `0x141e11010`, `0x141dd5f10`). **Nothing in the retail exe calls them**: the entity inspector that used them is compiled out. Only the DLL could call one (Positioned: vtable `0x1434e8e60`, slot `+0x68`).

What the **Positioned printer `0x141dec130`** reads (useful field map for the movement log):
| Label | Source |
|---|---|
| Object / Targetting size | `+0x1f8` / `+0x1fa` (i8) |
| Movement size | `max(+0x1f8, +0x1fd ? +0x1fc : +0x1f9)` |
| Pathing size | `0x141dd53c0(+0x1e8)` |
| Location, Tile Index | grid `+0x444`/`+0x448`; tile = cell / 23 |
| Position, Orientation | world `+0x490`/`+0x494`; `+0x44c` |
| Scale | `[+0x158]+0x74 x +0x474` |
| Is Moving | `+0x28c != 0` and `+0x1e5` bit 7 clear and `+0x269 == 0` (Is Sweeping: without the `+0x269` test) |
| Movement Destination | only while moving: the pair (`+0x23c`, or `+0x244` when `+0x22e` is set) and `+0x240`, swapped when `+0x22d` is set |
| Movement Speed | `+0x274 / +0x278` |
| Flags | `+0x1e4` bit 4 flipped, bit 3 collidable (and `+0x1e6` bit 0 clear); `+0x1e5` bit 1 locked orientation, bit 2 locked scale |

## 3. Action-desync warnings in Client.txt
The Actor handler `0x142159130` logs a warning (WARN level, `Client.txt`) whenever a server action message does not match the client's own action state. These are the client's only built-in desync detectors.
| Opcode (case) | Warning |
|---|---|
| `0x1f9` (`0x142159f0e`, executes through `0x14215b000`) | "Instant/Triggered actionwas serialized to the client, but the client failed to execute the action." (`0x14351fab0`) with skill instance, action, object and target ids and flags; "Client couldn't execute/perform \<a triggered \| an instant\> action from the server" (`0x14351fd48`, `0x14351fce8`); "Instant/Triggered action - Client failed to create aciton." |
| `0x1fa` (`0x14215a07e`) | "GEAL Triggered action with animation event ..." (`0x14351f930`, `0x14351fa60`) |
| `0x1fb` (`0x14215a39b`) | "Attempted to clone detached action to client ..." (`0x14351f410`, `0x14351f500`), "Clone detached action - Client failed to create action." |
| `0x1cc` (`0x142159dda`) | "InstanceClientFinishChannellingAction id did not match current channelled action" (`0x14351f1d0`) |
| `0x311` (`0x14215ac90`) | "Matching object found for InstanceClientActionUpdate, but no matching action was found on object to update." (`0x14351f230`): the update's skill (`+0x120`/`+0x122`/`+0x124`) and action id (`+0x3c`) match neither slot 0 nor a detached action |
| `0x1d8`, `0x1d9` | "Client recieved InstanceClientSkill(Minion)Stats packet for a container this skill doesn't have" |

In the user's `GameFiles/logs/Client.txt` (2026-05-03 to 2026-11-19) these come only from official sessions (`0x311`: 33810; `0x1f9`: 1900 "failed to execute" and 1697 "couldn't execute a triggered action"); 826 private sessions have none, because our server sends none of these packets yet. Once it sends skill actions, a game test can fail on any of them. The log writer `0x14219ef40` (message hash, time, tick, level) has no level filter: DEBUG lines already reach `Client.txt`.

## 4. Chat command table
`Data/Balance/Commands.datc64` (64 rows; loader `0x1401d5730`) lists the client's slash commands with `SendsGenericCommandPacket`: when true the client sends the row to the server instead of handling it. Rows of interest:
- `ForceResync` and `ForceResyncPlayer` (PoE1's `/oos`): **no command text**, so they cannot be typed. A client data mod that gives them a command would make the client send them; what the official server answers is unknown (no capture).
- `Debug` (`/debug`) and `Verify` (`/verify`): typed, sent to the server.
- Opcode and layout of the "generic command packet" are not read; our server sees only `0x16` ChatSend ([instance.md](../protocol/instance.md)).

## 5. command_line.txt
`0x140115900` builds `Documents\My Games\Path of Exile 2\command_line.txt` and calls the option parser `0x1423dc990` in the same function, so the file adds options to the command line (contents format not read). None of the options is a debug mode; `--test-synchronous-simulation` ("Forces simulation to be updated before other jobs") and `--disable-assert-box` are the closest.

## 6. Script (GEAL) debug functions
Object scripts have `ProximityTriggerDebug`, `EnableGEALDebugging`, `EnableStateMachineDebugLogging`, `DebugBreak`, `Assert`, `Log`, `Info`, `ShowMeshColliders`, `ShowAllMeshColliders` and `DoCheat` (names from the RTTI lambdas; registration `0x1400e7470`). `ProximityTriggerDebug` (`0x142069f30`) only checks its trigger index and draws nothing. They run only from object scripts in the game data, not on request.

## 7. Client cheat registry
`Cheats::ClientInterpreter` registers three functions at start-up (`0x1400390e0`, constructor `0x14163c090`, check `0x141e92890`): `ListFunctions`, `listcheats`, `whatischeat` (they print "Function List:", `0x141632a60`). No real cheat is registered in the client and no input path to them was found.

## Ruled out
- No `[DEBUG]` or developer section in the config: the config sections read are `UI`, `GENERAL`, `SOUND`, `DISPLAY`, `LOGIN`, `ACTION_KEYS`, `WASD_ACTION_KEYS`, `LANGUAGE`, `NOTIFICATIONS`, `CACHED_DATA`, `TUTORIAL_FLAGS`, `NETWORKING`. Keys read but missing from the test prefix's config are ordinary (`advanced_mod_display`, `always_attack_in_place`, `chat_language`, ...).
- `[NETWORKING] networking_type` cannot change the in-game mode ([server-code.md](server-code.md#5-predictive-mode)): values `auto`, `lockstep` enabled, `predictive` and `hybrid` disabled in the table `0x142f195d0` (flags `0x142f19a94`).
- No pathfinding, collision or entity-bounds drawing: the minimap's "Walkability" pass draws terrain only, and `DynamicWalkability.hlsl` is a ground-effect distance field.
- No server-position display and no correction smoothing ([server-code.md](server-code.md#ruled-out)).
- No internal or developer build check: "internal" strings are library errors or `ClientInternal*` component names.

## Suggested follow-up
1. **Overlay in game tests:** press F1 in a B4 game test and screenshot it at each snap, or read the stats block `0x1445ec460` from the DLL into the movement log (latency `+0x11c`, server `+0x120` each frame). Check what our `PingReply` puts in the first `u16`, so `network` means something.
2. **Destination in the movement log:** log Positioned `+0x23c`/`+0x240`/`+0x244` with `+0x22d`/`+0x22e` and `+0x274`/`+0x278` next to the grid cell, so a drift sample shows where the client thinks it is going and how fast.
3. **Fail game tests on action warnings:** once the server sends `0x1f9`/`0x311`, scan `Client.txt` after each game test for the warnings above.
4. **Generic command packet:** type `/debug` on our server with the DLL packet trace on to learn its opcode and layout; then `/debug` (or a data-mod `/oos` on `ForceResync`) could ask our server for a drift report, a client-native alternative to `!` commands.
5. Read the source of the overlay's `server` value (`+0x4f8` in `0x141012960`).

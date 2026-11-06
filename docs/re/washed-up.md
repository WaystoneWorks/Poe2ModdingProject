# Washed-up intro (Riverbank, `G1_1`)

Owner of the new-character intro: the wake-up animation, the movement-type dialog, the first messages and the spawn cell. Movement in general: [movement.md](../protocol/movement.md).

## Client behaviour
- Player flags bit 0 in the blob (reader `0x141dcf4a0`, Player `+0x206`) with stat `0x3e64` == 0 sets Actor `+0x2a1` bit 0 and starts the `WashedUp` animation.
- On `G1_1` (HASH16 `0x0f14`) with `+0x206` set the client's UI (`0x140fdb204`) forces input mode 1 (`0x14193d720`); that is why it sends `0x200 {1}` and `0x62` mode 0 at entry.
- While Actor `+0x2a1` bit 0 is set `Actor_QueueAction` (`0x141e3f100`) refuses other actions and calls `0x141dd13f0`, which queues `0x2000b7d9` itself. `0x141cc9a30` clears `+0x206` and bit 0 when the wake-up ends.

## The movement-type dialog
The client shows "Select a movement type" (Mouse, WASD buttons; at 2560x1440 Mouse (1180,1244), WASD (1377,1244)). Until it is answered neither keys nor clicks send anything: no `0x63`, no `0x1a5`. Choosing a button sends in one frame: `0x200 {value}` (WASD: 4), `0x62` mode 1, `0x1a5` Move with `u16 flags` = the player's entity id, `unk` 0xff, target = absolute (0,0) as an offset from the player, and `0x1ad`. The four official sessions of 2026-10-14 (4 of 4) answered 4.2 s to 19.9 s after AddObject.

## Official answer and ours
Official, in `r+0` (wire order): `0x2a6` 0.05, `0x1ec`, four `0x1d8`, `0x1d3`, `0x1c8` StartAction flags 0 (grid = target = the player's cell, skill `0x2000b7d9` = `0x20000000 | ActionTypes key 47065`, row `WashedUp`, `u8` 0xff), `0x1ca`, `0x1ae` (target flags 4, x,y 0), `0x1b2`, `0x2f9` Player delta.

Ours sends `0x1c8`, `0x1ca`, `0x1ae`, `0x1b2` and the stance answer, in the order `0x1ae`, `0x1b2`, `0x1c8`, `0x1ca`; not the `0x1ec`/`0x1d8`/`0x1d3`/flag-word delta. The client plays and ends the wake-up correctly without them.

## Length
`WashedUp` plays 187 frames (game-test movement log: frames 201-388, 187-374, 197-384, 182-369; classes Dex and Str, other classes not measured); `[movement] wake_frames`. While it plays the client starts no walk though the `0x64` answers come; a key still down at its end starts `Move` in that same frame (384 to 384).

## Spawn
Official cell and facing per placement, in the AddObject Positioned (`PlacedTile` transform numbers):
- transform 5 (tile at map tile x 9, y 45; seeds 3288279597, 70523716): cell (238,1164), facing 1.8896.
- transform 2 (tile x 12, y 45; seeds 3491751247, 2108363952): cell (284,1141), facing 5.9644.

Both come from one point in the tile's own orientation: cell (8,31), centre mapped through the placement then floored, facing 3.46041 rad, with facing = `atan2(dy,dx) + pi/2` (`0x141ddc820`). Other placements seen on our layouts ((307,1371), (1095,307)) have no official sample.

## Ruled out
- The server used to treat the first `0x1a5` as a walk to (0,0) and send facing 0.
- The server used to walk during the wake-up; a key pressed then walked only the server, so the client's next move snapped to the server's cell (game test run: 14.58 cells of drift).

## Tests
`scripts/game-test/washed-up.toml` (WASD), `washed-up-mouse.toml`; rules tests in `poe-game/tests/rules.rs`; `official_washed_up_spawns` in `instance-server/src/spawn.rs`.

# Captures: official servers vs ours, and the live client log

## Official servers vs ours
Tools: the DLL's Packets/Protocol/Coverage tabs, `modules/protocol/poe-proto/examples/check_capture.rs` (decodes every captured message with our layouts; `--dump <channel> <in|out> <0xop>` prints them) and `scripts/re/packets_diff.py`.
Run `check_capture` inside the Poe2Protocol submodule (not a member of the hub's workspace): `cd modules/protocol && cargo run -p poe-proto --example check_capture -- opcodes/0.5.5e.hotfix1 <packets.jsonl> [--show N]`, with captures from `dumps/0.5.5e.hotfix1/captures/`.
Compare with a capture of our server: `third_party/pyenv/bin/python scripts/re/packets_diff.py <official>/packets.jsonl <ours>/packets.jsonl [--channel instance] [--seq 40]`. Making a capture: [../guides/setup.md](../guides/setup.md#official-servers-read-only-observation), [../architecture/client-dll.md](../architecture/client-dll.md#packet-capture-packets-packetsrs).

## Layout check
Every official message we have a decoder for decodes without errors or leftover bytes, except two richer forms we do not support (our server sends the simple forms): `AreaInfo` optional blocks and `AddInventory` items.

## Movement capture 2026-10-20
`dumps/0.5.5e.hotfix1/captures/official/2026-10-20_18-41-14_336/`: read-only official session with standing and chained rolls, taps around the sprint threshold, stops during a sprint, attacks during rolls, sprints into walls, click-to-move and held clicks with rolls, an input-mode toggle. The DLL's movement log was on: `poe-hook.log` has the client's position per frame (`frame #n ... world ... step ... grid`, same frame numbers as the capture) and action starts/ends (`action start slot 0: DodgeRoll`). `check_capture` decodes every movement message with 0 errors and 0 leftover bytes. Results: [../protocol/movement.md](../protocol/movement.md) (index at "Session 2026-10-20"), fixtures `modules/server/crates/poe-game/tests/fixtures/` (`scripts/re/movement_fixtures.py`).

## Town capture with other players 2026-10-20
`dumps/0.5.5e.hotfix1/captures/official/2026-10-20_21-51-49_336/` (read-only official; 29,412 instance messages): the Riverbank cleared, then Clearfell Encampment for 160 s with three other players (WASD and click-to-move, waypoint, stash, NPCs), party invites (one cancelled by us), a whisper and a cancelled trade request. The `actions` log is on (client frame + 4527 = capture frame in the town; no per-frame positions).
- Remote players' `AddObject`, removal, relayed actions, party and trade: [../protocol/entities.md](../protocol/entities.md#other-players-add-actions-remove-party-and-trade). Decoders in `poe-proto` (`player_blob.rs`, `remote.rs`) decode every message of the session without errors or leftover bytes except `AddInventory` items, `BuffAdded` flag `0x10` and `SetAimTarget` kind 1 (a `u32 entity` after `x, y`). Anonymised fixtures: `modules/protocol/poe-proto/tests/data/`. Names and chat are not copied anywhere.
- Click-to-move (local player, `f8667-9183`, 7 presses and 189 held repeats): two single-click walks reached their target with no message at arrival (`f8988` 44.6 cells in 34 frames, `f9027` 32 cells in 26 frames: 1.2-1.3 cells per frame; the next click's `StartAction` starts exactly at the previous target). A held click's server restarts (`StartAction` Move, flags 0, header `(self, 9, n)`) came 13-17 frames and 13.6-17.7 cells apart. Not yet in [../protocol/movement.md](../protocol/movement.md) (gap 2).

## Planned: capture for R4 (world map, waypoints, transitions) and the open movement cases
For R4 of [PLAN.md](../PLAN.md) (and R3's open cases). The user records it (read-only official session); Claude only prepares and reverts the client.
Before: Claude stops any client batch, runs `cargo xtask deploy-client --official` with the DLL's movement and actions logs on.
In the game (a character with at least two acts' waypoints; about 15 minutes; wait about 2 s between steps):
1. In a town: open the world map (M), switch to another act, switch back, close it.
2. Use the town waypoint: open it, travel to another waypoint, then back to the town.
3. In a field area: walk through a normal area transition into the next area, then back through it.
4. Walk through a fog-covered transition (the misty doorway kind), and back.
5. Touch a checkpoint (the glowing marker in the field).
6. Movement: hold W, tap Space to roll and keep W held until the sprint starts, keep going a few seconds, then release W (three times); click an attack while walking (five times; movement gap #6: also five attacks standing and five in a plain WASD walk without a roll, ideally once more with attack-speed gear or a speed buff on, so the attack lengths show). Held click (gap #2): hold the left mouse button for 5 s without rolling or attacking (twice; shows the 15-frame restart trigger).
   Then (movement gap #4) twice each: hold Space with no key (sprint towards the cursor), press W after the sprint starts, release Space with W still held, release W a second later; hold W, roll and keep Space held, release W while sprinting, then Space.
7. Stance (movement gap #7): while walking with W held, toggle the input mode to click-to-move and back (twice); swap weapon sets once while walking and once during a roll or attack (standing is captured).
8. Log out normally.

Recorded: `2026-11-02_18-31-34_336` (movement parts of steps 6 and 7; the R4 parts 1-5 are not analysed yet). It covered: held click 5 s, W-held sprints and releases, attacks standing and walking, W pressed or released during sprints and rolls (gap #4), Space re-press, weapon swaps and input-mode toggles standing ([movement.md](../protocol/movement.md#capture-index-2026-11-02-session)). Not covered: swap or input-mode toggle while walking, rolling or attacking (gap #7); attacks with attack-speed gear (gap #6).
After: Claude runs `cargo xtask deploy-client` (private again), turns the desktop rules back on and moves the session to `dumps/<version>/captures/official/`.

## Planned: movement capture for the exact port
For steps (c) and (d) of the movement restart in [PLAN.md](../PLAN.md): the reference the new port is checked against offline. The user records it (read-only official session); Claude only prepares and reverts the client.

What the DLL logs in official mode (checked in `modules/client-hook`, 2026-11-03): the read-only latch only stops what sends or changes something. These are observers gated only by the signature table, so they start on the verified Hotfix 1 build (`poe-hook.log`: `feature path_log: on`; an unverified build starts only `packets`, `crash_log`, `exit_trace`):
- `[packets] capture`: every login and instance message (`packets.jsonl`).
- `movement_log` (`POE_HOOK_MOVEMENT_LOG=1`, needs `dump_object_types`): per-frame `frame #n` position lines, the `LINE` log of the path line state, WASD direction, facing, SetOrientation stacks, action starts and ends.
- `path_log` (`POE_HOOK_PATH_LOG=1`): one `PATHPLAN` line per plan ([pathfinding.md](pathfinding.md)).
- `state_export` (`POE_HOOK_STATE=250`): `GameFiles/poe-hook-state.json`.

Off in official mode: position sync, side channel and debug link, crypto bypass, fake focus, auto keys, layout export, mods.

Before: no client or batch running. Claude runs `cargo xtask deploy-client --official`. The user starts Steam, then `POE_HOOK_MOVEMENT_LOG=1 POE_HOOK_PATH_LOG=1 POE_HOOK_STATE=250 cargo xtask run-client` from the hub root, logs in with Steam and enters a field area with open ground and walls (about 10 minutes; wait about 2 s between steps so they separate in the logs).
1. WASD (input mode WASD): walk W 2 s and stop; W, then W+D, then D (turns); a full circle through all 8 directions; walk into a wall and along it.
2. Sprint: hold W, tap Space and keep it held until the sprint starts, sprint 3 s, release (three times); sprint turns (switch keys while sprinting, and a slow circle); sprint into a wall.
3. Rolls standing: tap Space towards the cursor, then away from it (cursor behind the character); tap-and-hold Space both ways (the sprint after the roll). Then the same while walking with W.
4. Click-to-move (switch the input mode to click-to-move): short clicks (5 cells), long clicks (40+ cells), a click behind a wall (the path goes round), hold the left button 5 s while moving the cursor; rolls and a sprint (hold Space) in this mode.
5. Controller (gamepad): walk with the stick in several directions and stop; slow and full tilt; rolls (tap) and sprint (hold the roll button) with the stick held; a sprint turn.
6. Log out normally.

After: Claude runs `cargo xtask deploy-client` (private again) and moves the session folder to `dumps/<version>/captures/official/`.

## Matched to official
| What | Official (ours now matches) |
|---|---|
| Local player index | 1 (`LocalPlayers` entry, `PlayerEntity 01 01`, first byte of `AddInventory`); the client copies it into its messages (`0062 01 ..`, `0063 01 ..`) |
| Inventories at entry | 118 inventories (ids 1-94, 122-144) with real sizes and a flags byte (0x00/01/03/04/60/61/65): `modules/protocol/opcodes/0.5.5e.hotfix1/inventories.tsv`. **Without ids 122-144 the client never starts the world** |
| `MoveDirectionUpdate` (`0x64`) | header (entity, entity, 9 = Actor component, 0), last byte `0xf1` |
| Cursor facing | client `0x0062` AimTarget (mode 2 = cell), server echoes `0x01dc` SetAimTarget one frame later. The client only sends cells in WASD input mode and while the Player component is in combat stance, which official servers set with a `0x02f9` ComponentDelta on the first Move; ours does it on the first movement or skill. In click-to-move mode the client sends no AimTarget, so the DLL cursor report + SetOrientation lock stays for it |
| `0x0062` size | 4, 8 or 12 bytes by mode (decoded by mode in `client_body_sizes`) |
| Login `0x003c` | four zero u32 before the key-exchange reply |
| Login `0x0017` | u16 `0x0014` right after `InstanceDetails` makes the client `shutdown()` its login connection, which our transfers need (`[network.login] close_after_handoff`) |
| `AddObject` header (player) | (0xffffffff, 0, 0), with and without the first-visit intro |
| AreaInfo league (+0x38) | the character's league |
| InitialState | flags 7 (zone) or 4 (town: no PauseRequest follows, bits 0/1 would freeze it), four stash tabs "1".."4" (`[accounts] stash_tabs`), character flags `68 40 00`, player entry `0x40`/`7` |
| Entry order | `LocalPlayers`, `PlayerEntity`, inventories |

## Open (by priority)
1. **Player component deltas at entry**: official servers send flag words (`0x0002`, 5 entries; key 0x08 added after the first Move) and combat stance 1, then stance 0 with `+0x3e7 = 1`; after kills, deltas with mask `0x0201` (experience 17, 34, 51 and +0x209 set). Ours sends only the stance.
2. **Messages official servers send at entry that we do not** (sizes in the session's `protocol.tsv`): `0x0021` = MonsterVarieties rows to preload (`u8`, `u16` count, `u16`, count x `u16` row, count x `u8`; session dispatcher `0x1421220f0` case `0x142123bac`; needed for monsters); `0x0066` = skill bar (389 bytes: `u8` local, `bool`, `u8` count, 64-byte records: `u32` skill id, ...; reader `0x142153f60`; needed for skills); `0x005a` = `u32` + 22 bytes kept on the session (+0x2318, all zero officially); `0x00c6` = a social-list entry (account name `Name#1234`). Others: `0x0043`, `0x0045`, `0x018b`, `0x018c`, `0x0229`, `0x0226`, `0x0237`, `0x003a`, `0x02db`, `0x00c4`, `0x02d8`, `0x0325` (5.5 KB), `0x0329`, `0x0320`, `0x031d`, `0x0271`, `0x00de` (per-inventory data), `0x02a6`, `0x0352`, `0x0358`, `0x0222`.
3. **AreaInfo** 221 vs 39 bytes: layout in [../protocol/instance.md](../protocol/instance.md); missing are the object-type preload list (needs the area's spawns), a u16 key list, scalar bytes and the optional blocks.
4. **CharacterList**: for characters that have played, still missing: `unk_51` 0x40, the 91-byte gear blob (component 8 delta format) and the stat pairs.
5. Skills, monsters, items, the sprint buff: the captures have the sequences.

## Live client log (`Client.txt` from real play, read only)
The user's log from official sessions (rules and location: [../../CLAUDE.md](../../CLAUDE.md)) shows what a correct session looks like.
- `scripts/re/clientlog_entries.py`: per-entry timelines (area, seed, first log lines with ms offsets).
- `scripts/re/clientlog_terrain.py`: (area, level, seed, tile hash, doodad hash) test vectors into `dumps/0.5.5e.hotfix1/terrain/vectors/terrain-vectors.tsv`: 1,744 vectors across 260 areas for the terrain generator ([terrain/README.md](terrain/README.md)); towns and hideouts always use seed 1.
- A live `G1_1` entry follows the same client log order as ours up to `[SCENE] Set Source [The Riverbank]`. Live then shows `Joined guild …` and `InstanceClientSetSelfPartyInvitationSecurityCode = 0` (server messages we don't send), `Tried to SetExtraActivationRangeAroundTile() after level generation was complete` (client-side noise, see [terrain/README.md](terrain/README.md#client-side-facts)), and the washed-up intro dialogue.
- Log lines: `Connected to <host> in Nms.` is the login connection; `Got Instance Details from login server` the hand-off; `Connecting to instance server at <ip>:<port>`; `Generating level N area "<AreaId>" with seed <u32>` the client generating its terrain.

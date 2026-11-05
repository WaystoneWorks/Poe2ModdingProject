# Side channel (client DLL and our instance server)

Everything the client DLL says to our instance server outside the game protocol: per-frame **position reports** and the **debug link** (overlay commands and state) over UDP, and the **mod report** over a TCP side stream. Frames are authenticated; there is no fallback to unauthenticated datagrams.

Code: `modules/client-hook/poe-hook-shared/src/sidechannel.rs` (framing, keys, replay window; one implementation for both sides), DLL `poe-hook-core/src/{side,position_sync,devlink}.rs`, server `modules/server/servers/instance-server/src/{sync,side_stream}.rs`.

## Session keys
Both sides hold the instance session's 64-byte **key material**: the server issues it in the ticket (`Ticket::keys`, random per hand-off) and sends it in `InstanceDetails` (login stream, encrypted); the client passes it to the instance cipher builder `0x14212ac10` (`rdx` = `InstanceDetails + 0x38`), which the DLL hooks ([../re/crypto.md](../re/crypto.md#side-channel-keys)). Every transfer to another instance is a new ticket, so a new session.

From the material `m` (HMAC-SHA256 with `m` as the key):

| Value | Derivation |
|---|---|
| session id (`u64`) | first 8 bytes of `HMAC(m, "poe2-side/v1/session")`, little-endian |
| client-to-server key | `HMAC(m, "poe2-side/v1/c2s")` (32 bytes) |
| server-to-client key | `HMAC(m, "poe2-side/v1/s2c")` |

The labels are unrelated to the Salsa20 streams and the HNC channel, so the keys are independent of them. The session id is sent in clear in every frame; the keys never leave either side. The server registers the session when it redeems the ticket (`ClientReports::register`) and forgets it when the connection ends.

## Frame
All integers little-endian.

| Offset | Size | Field |
|---|---|---|
| 0 | 3 | magic `PSS` |
| 3 | 1 | version (`1`); any other value is rejected |
| 4 | 1 | kind |
| 5 | 1 | flags (0) |
| 6 | 8 | session id |
| 14 | 8 | counter |
| 22 | n | payload |
| 22 + n | 16 | tag: first 16 bytes of `HMAC-SHA256(key, bytes[0 .. 22 + n])` |

The key is the client-to-server key for kinds 1, 2, 4, 5 and 6 and the server-to-client key for kind 3, so a frame cannot be reflected back at its sender (the receiver also rejects a kind that travels the wrong way). The tag is compared in constant time.

| Kind | Name | Way | Transport | Payload |
|---|---|---|---|---|
| 1 | Report | C to S | UDP | 26 bytes: `u16 flags` (actor `+0x2a2`), `u32 frame`, `f32 x`, `f32 y` (grid cells), `u16 action`, `u16 action2`, `i16 cursor x`, `i16 cursor y`, `u16 window width`, `u16 window height` |
| 2 | Command | C to S | UDP | text: a server command line (the overlay's, [../guides/server-admin.md](../guides/server-admin.md)); `registry` asks for the command registry; `complete <kind> <typed>` asks for names ([below](#command-registry)) |
| 3 | Debug | S to C | UDP | text lines `key<TAB>value` (simulation state), `cmds`/`instances` lists, `state`/`online` lines, `completion`/`name` replies, `ack<TAB>command<TAB>result`, [`alert` blocks](#alerts); at most about 3000 bytes |
| 4, 5 | (retired: terrain Upload, UploadOffer) | | | the server refuses them (`REPLY_AUTH`) |
| 6 | ModReport | C to S | TCP | the loaded client mods, see [Mod report](#mod-report) |

### Counters and replay protection
Each sender numbers the frames of a stream from 1, rising by one. The receiver keeps a 64-wide sliding window per stream (`ReplayWindow`): a counter is accepted once if it is above the highest seen, or inside the window and not seen yet; counter 0, duplicates and anything more than 64 behind the top are rejected. The window moves **only after the tag verified**.

Streams: the client's UDP stream (kinds 1 and 2, shared counter), the client's TCP stream (kind 6, own counter), and the server's debug stream (kind 3; the DLL keeps the window). A new session starts every stream at 1.

### Server rules
- Datagrams arrive on the instance bind address, UDP, same port number as the TCP listener. No source address filter; identity is the session id plus the tag.
- A datagram is dropped silently if it is malformed, has another version, names an unknown session, fails the tag, travels the wrong way, has an unexpected kind, or replays a counter. The first rejection and every thousandth are logged (`side-channel datagram rejected`, with the reason).
- Debug frames go to the source address of the session's latest **authentic** datagram (NAT rebinding follows; spoofed packets cannot redirect it).
- Reports never move the player; only the drift checker reads them ([movement.md](movement.md#drift-checker)).

## Command registry

The overlay is generated from the server's command registry ([../guides/server-admin.md](../guides/server-admin.md#commands)). Debug datagrams (about 3000 bytes each; a longer list continues in another datagram):

- `cmds<TAB>begin` (or `more` in a continuation), then one `cmdspec<TAB><JSON>` line per command the account may use, then `you<TAB>account<TAB>admin 0/1<TAB>prefix`. The JSON is `poe_hook_shared::cmdspec::CmdSpec`: `path`, `aliases`, `category`, `admin`, `args` (`name`, `kind`, `optional`), `flags` (`name`, `kind` or null for a switch, `help`), `summary`, `help`, `examples`, `overlay` (a Debug tab). `kind` is `int`, `float`, `text`, `rest`, `bool`, `duration`, `choice=a|b`, `seed`, `topology`, `orientation` or a name kind (`area`, `player`, `instance`, `class`, `stat`, ...). A line over 2900 bytes (a long mod help) is cut.
- `complete <kind> <typed>` (Command frame, name kinds only) is answered by `completion<TAB>kind<TAB>typed` and a `name<TAB>id<TAB>display` line per match, prefix matches first, at most 30. Player, instance and league lists are empty for non-admins.
- `state<TAB>begin`, then `state<TAB>key<TAB>value` (character, level, class, league, area, instance, seed, cell, time_scale, muted), about every second; for admins also `online<TAB>character<TAB>account<TAB>area<TAB>instance<TAB>league<TAB>level<TAB>muted` per online player.

## Alerts
A Debug datagram that starts with `alert<TAB><kind>` is a popup for the player. One kind exists, `terrain_mismatch` (sent by the [terrain check](instance.md#terrain-check)); the block is `key<TAB>value` lines up to `end`:
```
alert	terrain_mismatch
area	G1_2 (Clearfell)
seed	123456789
layout	topology 3, orientation 1
tile	client 0x1a2b3c4d  server 0x5e6f7081
doodad	client 0x11111111  server 0x11111111
reason	tile hash differs
dest	previous instance 7 (G1_1 Riverbank)
report	terrain-mismatch build=0.5.5e.hotfix1 server=<git describe> area=G1_2 seed=123456789 topo=3 orient=1 tile=1a2b3c4d/5e6f7081 doodad=11111111/11111111 reason=tile_hash_differs
end
```
`none` stands for hashes the client never sent. The DLL (`poe_hook_shared::alert::parse_terrain_mismatch`, `devlink.rs`) exports the client's layout, answers with a Command `ack export <folder>` (or `ack export failed <why>`) and shows the popup ([client-dll.md](../architecture/client-dll.md#alert-popups)). The server waits 3 s for the ack. Alerts are sent once; a lost datagram means no popup (the kick still happens).

## Side stream
The TCP side stream on the instance port carries only the hook's mod report. The server tells it from a game connection by peeking the first four bytes: `STREAM_MAGIC` (`PSUP`) is not a game opcode (a `Hello` starts with its u16 opcode). Server: `servers/instance-server/src/side_stream.rs`; frame cap 1 MiB, 10 s deadline.

```
client                                         server
PSUP u32 len  frame(ModReport, payload)  ->
                                         <-    PSUR u8 status u16 len text
```

`PSUR` is `STREAM_REPLY_MAGIC`; the reply is not authenticated. Statuses: `0` stored, `2` rejected (reason in the text), `3` authentication failed (unknown session, bad tag, replay). The server closes the connection after the reply. The former terrain upload (kinds 4 and 5, `REPLY_SEND`/`REPLY_HAVE`) is gone: the server generates the terrain itself and reads no client files. The DLL still writes `terrain_layout_<hash>.tsv` and `terrain_grid_<hash>.bin` to its dump dir (RE and the mismatch popup, [../architecture/client-dll.md](../architecture/client-dll.md#layout-export-format)) but sends nothing.

## Mod report
`Kind::ModReport` (6): the client mods the hook has loaded, sent once per instance session so a server that requires client mods can check them at login ([../architecture/mod-host.md](../architecture/mod-host.md#the-login-check-of-the-clients-mods)). Framing as above (`PSUP`, `u32 length`, one sealed frame). The server answers `PSUR` with status `0` ("stored") or `2` (the payload does not decode); an unknown session, bad tag or replayed counter is `3`.

Payload (little-endian), `poe_hook_shared::modreport`:

| Field | |
|---|---|
| `u8 format` | `1`; anything else is rejected |
| `u16 count` | at most 64 |
| per mod: `u8 id length`, id, `u8 version length`, version (UTF-8) | the mod's `id` and `version` |
| `[u8; 32]` | SHA-256 of the installed `mod.toml`, byte for byte |
| `u8 has_dll`, then `[u8; 32]` when 1 | SHA-256 of the entry DLL; 0 for a data-only mod |

An empty list (`count` 0) is valid: the hook runs, no mod is loaded. A client without a report is an old hook (or one that never reached the server). The hook sends it from a background thread once the loader has finished and the connection to a trusted server is known (retrying for about a minute), only when a side-channel session exists: never in official mode, never while read-only, never to an untrusted address. The server keeps the newest report per session (`ClientReports::store_mod_report`) and `InstanceServer::client_mod_verdict` waits for it up to `[mods] report_wait_secs`. A consistency check, not anti-cheat.

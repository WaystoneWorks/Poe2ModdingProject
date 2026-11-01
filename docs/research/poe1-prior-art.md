# PoE1 prior art: protocol and architecture

Nearly all public detail is PoE1: **KiwiNet** (0.8.8 beta, 2011, C# emulator) and **exileSniffer** plus the **Testudo Binarii** blog (3.x client, 2018). No published RE of the PoE2 protocol exists; treat everything below as a hypothesis to check against 0.5.5e. Sources are in `third_party/reference/`, listed at the end.

## Architecture
- The **login server** handles auth, leagues, characters and selection, then sends **instance details**:
  - 0.8.8: `u32 SessionId, wstring WorldAreaId, u8 n, {astring host, astring port}[n]`.
  - 3.x (`0x0F`): `u32, u32 AreaCode, u32 ConnectionID, u8 n, {u16, u16 port, u32 IPv4, 20 bytes}[n]`, then a 64-byte key blob (32-byte Salsa20 key, IV at +32, IV at +48).
- The client connects to the **instance server**; its first message carries the ticket: `wstring CharacterName, u32 SessionId` (0.8.8) or `0x0003, u32 ConnectionID` (3.x).
- **Instance -> instance transfer:** the server sends instance details again (3.x `0x18`, new key blob) and the client reconnects.
- Backend services: Login, Master, Account/Owner, Instance (KiwiNet's server-to-server opcodes).
- Ports: login 20481, instance 6112. Official PoE2 gateways use 21261-21279 (`gateway_list.txt`).

## Encryption (3.x)
- Crypto++. Ephemeral DH (p/q/g in the binary); the server's key is DSA-signed against a static public key in the client.
- The shared secret goes through SHA-512 to a 32-byte Salsa20 key plus an 8-byte IV per direction.
- **Instance keys come from the login server's hand-off**; no new handshake.
- Sniffers found keys by scanning client memory for the Salsa20 constant `"expa"` (`0x61707865`); the state words are permuted.
- 2025 RageZone reports say the IV/key scheme changed since 2018, and people disable client crypto for emulation.
- 0.5.5e has an "HNC Protocol Violated" error; PoE1 3.x had an HNC challenge/response (`0x0D`/`0x0E`).

## Framing
- No length prefix: the stream cannot be split without every layout. Big-endian integers; the opcode is a u16 in 3.x (u8 in 0.8.8).
- `wstring` = u16 character count + UTF-16LE. Hosts and ports are ASCII strings with a u16 length.
- Varint: `0xxxxxxx` / `10xxxxxx` / `110xxxxx` / `1110xxxx`, the top payload bit as the sign for the signed variant.
- Entity id in 3.x: 4+4+2 bytes. Object types are identified by the Murmur2 hash of the metadata path.

### Login opcodes (3.x)
| ID | Meaning |
|---|---|
| `0x02` | ephemeral pubkey |
| `0x03` | auth: `u32, wstring account, 32B exe hash, 32B cred hash, 32B MAC hash, u8, u8` |
| `0x04` | auth reply |
| `0x09` | delete char |
| `0x0B` | select: `u32, u8 index` |
| `0x0D` | create: `wstring name, wstring league, u64, wstring class` |
| `0x0F` | gameserver details |
| `0x10` | char list: `u32 n, {wstring name, wstring league, u8, u8, u32 level, u32, u8 class, u8, u8}[n], u32, u8` |
| `0x11` | final |
| `0x13` | league list |
| `0x23` | request leagues |

### Instance opcodes (3.x)
| ID | Meaning |
|---|---|
| `0x0F` | area info: `u32 areaCode, wstring, u32 variant, flags, u16 n, u32 preload[n]` |
| `0x10F` | client finished loading |
| `0x110` | player id |
| `0x133` | heartbeat |
| `0x136` | add object: `id, u32 murmur, u16 len, blob` |
| `0x137` | update object |
| `0xEA` | remove object |
| `0x16` | action predictive: `u32 x, u32 y, u16 skill, u16 count, u8 mod` |
| `0xD9` | used skill |
| `0xEB` | start skill |
| `0xF1` | life/mana/ES update |

0.8.8 used different numbers: WorldObject add/update/remove were 100/101/102.

## Area and terrain
- The server sends an area id and a **u32 seed**; the client generates the terrain and replies `TerrainGenerationResult(u32 TileHash, u32 DoodadHash)`. The server compares with its own and disconnects on a mismatch (`TerrainGenerationOutOfSync`). **We use this as an oracle:** our generator is correct when it reproduces the client's hashes.
- PoE2 memory tools (POE2Radar): tiles are 23x23 grid cells, 250 world units per tile, 4 grid layers.
- The generator algorithm has never been published (see GGG's ExileCon 2019 talk "Procedural World Generation").

## Simulation
- KiwiNet ticks at about 30 Hz (33 ms) and sends a frame duration; heartbeat timeout about 6 s.
- Objects: full add/remove plus per-component deltas, serialized in the object template's order, `Positioned` first.

## Sources
- https://github.com/Crypto137/KiwiNet: `docs/Packets/*.md`, `src/KiwiNet.Protocols/`, `src/KiwiNet.InstanceServer/Network/RemotePlayer.cs`
- https://github.com/ncatlin/exileSniffer: `packetIDs.h`, `key_grabber_thread.cpp`, `*_packet_deserialisers.cpp`
- Testudo Binarii, parts 1-3:
  - http://tbinarii.blogspot.com/2018/05/reverse-engineering-path-of-exile.html
  - http://tbinarii.blogspot.com/2018/05/reverse-engineering-path-of-exile_0.html
  - http://tbinarii.blogspot.com/2018/05/reverse-engineering-path-of-exile-game.html
- https://github.com/Sikaka/POE2Radar: PoE2 terrain memory layout
- RageZone emulator threads 1249465 and 1247222 (2025-26)

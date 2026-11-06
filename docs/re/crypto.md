# Login crypto (0.5.5f)

## Official scheme
**Library:** Crypto++, identified by RTTI names (`DL_GroupParameters_GFP`, `DL_PublicKeyImpl<DL_GroupParameters_DSA>`, `SignatureVerificationFailed`).

**Handshake:**
1. The client sends `KeyExchange` (0x0002): `u16 key_len (128), key, u16 sig_len (0)`. The key is its ephemeral 1024-bit Diffie-Hellman public value.
2. The server replies with `KeyExchange` (0x0002): `u16 key_len, key, u16 sig_len, sig`. The client parses it into a packet object (key as `std::string` at +0x10, signature at +0x30).
3. The login dispatcher (switch at `0x1420f71e3`, opcodes 0x02-0x47) handles opcode 2 at `0x1420f7210` and calls the **verify-and-derive** routine `0x1421aefe0(session, &key, &sig)`:
   - Verifies the DSA signature over the server key against GGG's built-in key; failure throws **"General Rhoa Failure #3"**.
   - Calls `0x1421aee10` (Crypto++ `DH2::Agree` unified DH, combining the static keys at session+0x750/+0x758 with the ephemeral pair); failure throws **"General Rhoa Failure #1"**.
   - Hashes the agreed value with SHA-512 into the 64-byte buffer at `session+0x60`.
4. The dispatcher builds the stream cipher with `0x1421af380(obj, key_material, is_client=1)` and installs it on the Tcpstream with `0x1421a8500`.

**Crypto session constructor** `0x1421adc10`: loads two DH groups from hex strings (a 1024-bit group for the ephemeral keys and a larger one), stores static keys and loads a BER DSA public key validated at level 3 (failure throws **"General Rhoa Failure #2"**).

## Stream cipher
`0x1421af380` creates two Crypto++ Salsa20 instances (key setup `0x142b15570`; vtables `0x143523850` and `0x143524328`). For a client (`is_client = 1`) the key material `m` is split:

| Direction | Key | IV |
|---|---|---|
| client->server (client encrypts) | `m[0..32]` | `m[32..40]` |
| server->client (client decrypts) | `m[0..32]` | `m[48..56]` |

The IV offset is `((is_client ^ 1) + 2) * 16` for the first instance and `(is_client + 2) * 16` for the second. Both directions are continuous keystreams over the whole connection. Rounds: the Crypto++ default (20).

## Private-server bypass (`poe-hook` feature `crypto_bypass`)
- The DLL finds the verify-and-derive routine by its prologue pattern and replaces it with one that writes `SHA-512(server key bytes)` into the key buffer and returns: no signature check, no DH.
- The server (`modules/server/servers/login-server/src/handshake.rs`) sends 128 random bytes as its key with an empty signature, then derives the same key material (`poe_net::KeyMaterial::from_server_public_key`).

## Other crypto in the binary
- `0x1421acdb0`: SHA-384(8-byte seed), then Salsa20, applied in place to a buffer. Used by `0x142111ca0`, a loader for **server-delivered code modules**: decrypts the module, checks an FNV-1a hash, manually maps a PE, resolves its imports, calls its entry point and wipes memory with a MurmurHash-based PRNG. Anti-cheat style; our server does not send modules unless the client requires one.
- `0x142bd45a0` / `0x142bd4710`: a ChaCha-based CSPRNG in the memory allocator. Not network related.
- The "HNC Protocol Violated" string (`0x1435288d8`) belongs to the HNC side channel below.

## HNC side channel
The instance EnableEncryption handler (`0x1421312e0`) creates two cipher pairs from the 64-byte key material in `InstanceDetails` +0x60:
1. The packet ciphers (`0x14212ac10` -> `0x1421af380`).
2. The HNC bit queue at stream +0xd0 (built in `0x1421312e0`, the builder is inlined since 0.5.5f, -> `0x1421d5170`). Its key material is the session material XORed with a 64-byte table (`0x142f23aa0`), then six byte pairs swapped; the Salsa20 key/IV split is the same as for the packets (is_client = 1). Table and swaps: `modules/protocol/opcodes/0.5.5f/hnc.toml` (`HncKeys::derive`).

The client's outgoing HNC bytes ride in `0x1c` frame reports, the server's in `0x1d` ping replies (bit layouts in [../protocol/instance.md](../protocol/instance.md)). An idle stream is zero bytes; the server sends keystream bytes (encrypted zeros). The client accepts them for minutes; all-zero bits crash it.

## Side-channel keys
Our DLL needs a secret that only this session's client and our server know, to authenticate its UDP side channel ([../protocol/side-channel.md](../protocol/side-channel.md)). The instance key material is that secret: `0x14212ac10(out, key material, &is_client)` is the packet-cipher builder called once by the instance EnableEncryption handler (`0x142131210`, call at `0x142131323`, `rdx = InstanceDetails + 0x38` read from `[r15 + 0x2108]`), its only caller. It calls `0x1421af380`, which creates the two Salsa20 instances from the 64 bytes. The DLL (`side.rs`) hooks the builder at entry (`JmpBack`), copies the 64 bytes, derives the session keys and never logs them. It captures only when the latch is off and every recorded connection is trusted (`custom_server`), so an official server never gives it a session. The login handshake's `SHA-512` material is not used: it belongs to the login connection, not the instance session.

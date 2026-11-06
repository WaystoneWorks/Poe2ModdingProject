# Official mode: observing a session on the official servers

Besides the private server, the client hook has **official mode**: you play the real game on the official servers with the hook loaded, and the hook only *watches*. It logs packets, the client's own state and a few snapshots to files on your machine.

**Read the risk section first.** The mode is read-only for the game's state and the servers, but not invisible: the hook is still a foreign DLL inside the game process. Nothing here is endorsed by Grinding Gear Games; you use it at your own risk (see the [disclaimer](../../README.md#disclaimer)).

## What it does and does not do

| It does | It does not |
|---|---|
| Starts your own copy of the game (`GameFiles/`, never the Steam install) with the original realm list, so the normal Steam login and official realms work | Send anything to an official server that the game would not send itself |
| Records every login and instance message (plaintext, read inside the client after decryption) to `packets.jsonl` and `packets.txt` | Change, inject, replay or block a packet |
| Writes logs, an optional per-frame movement log, and snapshots and area exports you ask for in the overlay | Move your character, press keys, or change game memory values |
| Shows an overlay (Insert) with packets and coverage; the badge `OFFICIAL: read-only` is always visible | Patch the login, bypass the key exchange, or use the debug link, position sync or the mod report |
| Redacts the bodies of login, credential and ticket messages before storing them | Load mods (the mod loader does not read the mods folder in this mode) |

### The read-only latch

In official mode the DLL sets its **read-only latch** at start; it never turns off for that process. Every part of the hook that could send, alter or inject anything checks it first: the crypto bypass, position sync, the side channel to a private server, the test-input and window-title hooks, the login patch, key injection and the mod loader. `login_mode` is forced to `steam` and `trusted_servers` to empty, by the deploy and again when the DLL reads the config. The latch also comes on in a private-mode client the first time it connects to an address that is not loopback or a trusted server, so a config mistake cannot turn a private client into a writer on the official servers. Details and tests: [client-dll.md](../architecture/client-dll.md#modes-and-the-read-only-latch). At start the DLL writes a line to `poe-hook.log` with the latch and guard state.

## The risk

- **The DLL still patches game code in memory.** It installs inline detours on game functions and a Vulkan hook for the overlay, and is loaded as `version.dll` in the game folder. "Read-only" means the game's state and the servers are not touched, not that the process is unmodified.
- **It can be detected.** Anti-cheat and the terms of service can treat any injected DLL as a violation, even a passive one. The game can also load server-delivered code modules that inspect the process.
- **Your account is at risk**: a warning, temporary or permanent ban is possible. Do not use official mode on an account you care about or with purchases. A throw-away account is safer, although the terms apply to it too.
- **Captures contain your play**: your character's data, inventory, chat and names of nearby players. Only the login messages are redacted. Never post a capture or log without reading it, and never attach one to a public issue.
- **The hook is built for one client build.** With an unverified build only the pure observers start. Use the build named in `modules/protocol/versions/0.5.5f.toml` and update your `GameFiles/` copy when the game is patched.
- The launcher offers this mode only as the explicit **Official (read-only)** entry of its game version dropdown, after the warning is accepted ([From the launcher](#from-the-launcher)); it never uses it by itself.

If that is not acceptable, stop here: playing through Steam's own untouched install is unaffected by this project.

## Requirements

- A hub checkout with submodules and tools ([setup.md](setup.md#clone), [setup.md](setup.md#tools)).
- A **copy** of the game files in `GameFiles/` of the same build as the live game. Never point the tooling at Steam's folder; the project never writes to the Steam install or its Proton prefix.
- Linux: Steam running (the client exits at once without it) and a Proton installed through Steam; the copy runs in its own prefix (`third_party/proton-prefix`).

## Step by step

1. **Deploy in official mode.**
   ```sh
   cargo xtask deploy-client --official
   ```
   Builds the DLLs (`--no-build` skips that), restores the original `gateway_list.txt` from `gateway_list.txt.orig`, installs `version.dll` and `poe_hook_core.dll`, and writes `mode = "official"`, `login_mode = "steam"` and an empty `trusted_servers` into `poe-hook.toml`. Everything stays inside `GameFiles/`; originals are backed up first. The command ends with `official, read-only`.
2. **Start Steam**, then run the game from the copy:
   ```sh
   cargo xtask run-client
   ```
   The login screen is the normal Steam one. The badge and the `poe-hook.log` line confirm the mode. **Insert** shows or hides the overlay; **Home** saves a snapshot.
3. **Play**, then **close the game**; the files are complete when the process has ended.
4. **Find the output.** Per run, `GameFiles/logs/poe-hook/<date>_<time>_<pid>/` holds `packets.jsonl` and `packets.txt` (one record per message: direction, channel, opcode, name, size, hex), logs and snapshots. `GameFiles/poe-hook.log` is the DLL's log, `GameFiles/logs/Client.txt` the game's. `scripts/dumps/migrate.sh` copies packet sessions to `dumps/<version>/captures/{official,local}/` (git-ignored). Comparing captures: [captures.md](../re/captures.md).
5. **Switch back.**
   ```sh
   cargo xtask deploy-client      # private server again (gateway entry, standalone login)
   cargo xtask revert-client      # or: take the hook out of the copy altogether
   ```
   `deploy-client` without `--official` points the copy at the private server again (and resets the remembered realm); `revert-client` restores the original files ([client.md](client.md#going-back-to-the-official-game)).

## From the launcher

The [launcher](launcher.md#official-read-only) offers the same mode: choose **Official (read-only)** at the top of the game version dropdown.

- **Install** downloads the *current* official build from Steam with your own Steam login (DepotDownloader, no pinned manifests) into `<data>/game/official`, separate from every private version; *Download again* updates it, *Repair* re-checks it.
- **Play** asks once for the risk section to be accepted, then deploys what `deploy-client --official` deploys (no position sync, no output folder) and starts the game as shipped: the Steam login happens in the game. Linux uses a separate Proton prefix (`<data>/proton-prefix-official`); Steam must be running.
- **Servers, Account, Host a server and Mods are hidden** while it is selected.
- **A newer official build than the hook knows:** the hook switches its features off by itself (`NOT verified` in `poe-hook.log`); the game runs without an observer until a hook release for the new build.
- The launcher never writes a trusted server or a private gateway for this mode and never touches the latch. It has not been played against the official servers from the launcher; the deploy files are covered by unit tests.

## Settings that matter

`GameFiles/poe-hook.toml` has the hook's other options (packet capture size and redaction, movement log, overlay keys). Official mode forces the safety-relevant ones; keep `redact` on. Keys: [client-dll.md](../architecture/client-dll.md#login-mode-and-trusted-servers), [features](../architecture/client-dll.md#features-features).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| The client exits at once, log says `Unable to init Steam API` | Steam is not running |
| The login screen shows the private server's realm or the account-name screen | `GameFiles/` was last deployed for the private server: run `deploy-client --official` again |
| Overlay missing or features off, `NOT verified` in the log | The game build differs from the one the hook knows: update `GameFiles/` to the build in `modules/protocol/versions/0.5.5f.toml`, or wait for a hook release ([new-game-version.md](new-game-version.md)) |
| The game freezes for seconds when monsters appear | `entity_trace` from an earlier private session is on; set it to `false` in `poe-hook.toml` |
| You were disconnected or warned | Stop using the mode; see the risk section |

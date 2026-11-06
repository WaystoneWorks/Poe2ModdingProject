# When GGG ships a new game build

Step by step, from the new files to the in-game check. What breaks and why: [../re/update-compatibility.md](../re/update-compatibility.md). Everything that names a build lives in one file per build, `modules/protocol/versions/<version>.toml` (Poe2Protocol, next to `opcodes/<version>/`; paths relative to the consumer's working directory: the hub or Poe2Server).

## What defines a supported build

| Piece | Where | Read by |
|---|---|---|
| **Version file** `modules/protocol/versions/<version>.toml`: depots and manifests, exe sha256, size and PE fingerprint (timestamp, image size), build revision, key-file sizes and floors, opcode folder, signature table path, features that must resolve, known `client_hash` values, strings the exe must contain, data anchors and row counts, dat-schema pin | repository root | `cargo xtask` (deploy, `check-build`), the servers (`[game] version`), the launcher |
| Launcher copy | `modules/launcher/versions/<version>.toml`, byte-identical, written by `cargo xtask versions` (`--check` compares; `check-build` and a test compare too) | the launcher (separate repository, its `build.rs` embeds every file there) |
| Opcode tables | `modules/protocol/opcodes/<version>/` (`login.toml`, `instance.toml`, `hnc.toml`, `inventories.tsv`, `deserializers.tsv`) and `poe_proto::opcodes::EMBEDDED` | servers (from the folder), the DLL (compiled in) |
| Signature table | `modules/client-hook/signatures/<version>.toml`, listed in `poe-hook-sig/src/embedded.rs` `TABLES` | the DLL, `check-build` |
| Data | `dumps/<version>/` (git-ignored), `docs/re/addresses-<version>.md` | tools, scripts (`scripts/re/version.py` picks the newest version file, or `$POE_VERSION`) |

`[game] version` in `modules/server/config/server.toml` selects the version file. `protocol_dir` defaults to the file's `[protocol] opcodes`, so a new build is a new file plus one changed config value. A version without a file is a start-up error naming the known ones.

Kinds of patch: **data** (`Bundles2` changes, exe byte-identical: steps 1, 2, 4 and the data part of 5), **hotfix** (rebuilt exe, the common case: functions move, most signatures survive), **major** (new league or 0.6: messages and generator passes change).

## 1. Update `GameFiles/`

- `GameFiles/` is a copy of the client install. Never touch the Steam install or its Proton prefix.
- Undo the deploy first so the `.orig` backups describe the old files: `cargo xtask revert-client`.
- Replace the copy: let Steam update its install and copy it again, or install the build with the launcher into another folder and point `[game] game_dir` at it.
- Keep the old build as `GameFiles-<old>/` (git-ignored, outside `GameFiles/`) and copy the old exe to `dumps/<old>/exe/`. Delete `GameFiles-<old>/` once the Ghidra project has the new build ([../re/README.md](../re/README.md#a-new-build-in-the-ghidra-project)).
- Do not deploy yet (the DLL's signature table does not know the build). `check-build` takes any exe path.
- Data changes: `cargo run --release --manifest-path scripts/re/bundlediff/Cargo.toml -- GameFiles-<old> GameFiles > dumps/<new>/bundlediff.tsv` (added, removed and changed virtual files; a few minutes). No `.datc64`, `.tgr`, `.dgr`, `.tdt`, `.tmd` or `.arm` among them means the server's data and terrain inputs are unchanged. A file whose bundle is not installed on one side is reported as `unread`, not compared (0.5.5f: about a million shader cache files, no server input); check that no server input is among them.

## 2. `cargo xtask check-build GameFiles/PathOfExileSteam.exe`

```
cargo xtask check-build <exe> [--bundles <game dir>] [--version <v>] [--report <file>]
```

Reads the exe, scans it with the DLL's own matcher (`poe-hook-sig`) and writes `dumps/<version>/check-build.md`; the console shows a summary per block and every warning and failure. `--bundles` is the folder with `Bundles2/` (default `[game] game_dir`). The version file compared with is the one whose exe sha256 (or PE fingerprint) matches, else the config's `[game] version`, else the newest (`--version` to choose).

| Block | What it reports |
|---|---|
| Identity | exe size, sha256, PE timestamp and image size against the version file; the revision string in the exe (as `Client.txt` prints it); the signature table's `[build]`; the recorded `client_hash`; the launcher copy; the build of the terrain vectors |
| Signatures | every `[[sig]]`: **found** (address, distance from the table's `ghidra` address), **missing**, **ambiguous** (matched n times) or failed (bytes at the address, not a function start, a site inside an instruction) |
| Struct offsets | every `[[field]]`: found (value, or "changed: old -> new"; the DLL reads the new one), missing, ambiguous, anchor failed |
| Features | per DLL feature: on or OFF, required or research |
| Opcodes | tables load; the HNC `key_xor` found by value; **deserializer drift** (below) |
| Strings | option strings, file names and log texts the tools depend on |
| Game data | each table the server reads (`poe_data::used::USED`): it opens, every used column is in the schema and decodes, the schema's row width equals the file's (a narrower file is an error); dat-schema against the pin; row counts; row anchors (`Stats` `actor_scale_+%` at 1913, `ActionTypes` `Move` with key 10505, ...); the config's sprint buff rows |
| Files | key-file sizes of the install |

Exit code: **0** everything found and the build matches; **1** warnings (a research feature's entry missing, row count changed, schema pin differs, no baseline); **2** a required feature's entry missing, ambiguous or different, a row anchor moved, a table does not decode, identity differs. "Required" is the version file's `[client_hook] required_features`; others are research. On a new build step 2 fails on identity and on whatever moved: that is the work list for steps 3 and 4.

## 3. Regenerate the signatures

Needed when step 2 shows missing or ambiguous entries, or the build changed at all (the table is chosen by the exe's PE timestamp and image size).

1. Re-analyse the exe in Ghidra ([../re/README.md](../re/README.md)) and find the moved functions: every entry still found gives its new address (the report lists it), missing ones sit near their old neighbours; string anchors survive best (`Unable to deserialise packet`, `General Rhoa Failure #3`, `Tile hash`, ...).
2. Copy `scripts/re/sig_spec_<old>.py` to `sig_spec_<new>.py`, set `BUILD` (version, revision, PE timestamp, image size, sha256) and the changed addresses.
3. `third_party/pyenv/bin/python scripts/re/sig_gen.py scripts/re/sig_spec_<new>.py GameFiles/PathOfExileSteam.exe > modules/client-hook/signatures/<new>.toml`
4. `cargo run --release -p poe-hook-sig --example resolve -- GameFiles/PathOfExileSteam.exe` in `modules/client-hook` (exit 1 on any difference from the table's own addresses).
5. Add the file to `TABLES` in `modules/client-hook/poe-hook-sig/src/embedded.rs` and rebuild (`cargo xtask build-dll`).

If every signature already resolves, copy the old table, change `[build]` (version, `build_revision`, `pe_timestamp`, `image_size`, `exe_sha256`) and refresh `ghidra` and `value` with `sig_gen.py` or the `resolve` output.

**Hotfix rebuilds without Ghidra:** `third_party/pyenv/bin/python scripts/re/addr_map.py GameFiles-<old>/PathOfExileSteam.exe GameFiles/PathOfExileSteam.exe --out dumps/<new>/addr_map.tsv` aligns the two exes' `.pdata` function lists by size and writes an old-to-new map (`same`: moved by a delta; `gap`/`lost`: changed bodies, the functions the patch touched); `--map <va>...` translates any old code address. Copy the spec, set `BUILD`, move every address by the map (named entries can take the `resolve` output); find data addresses that appear only in notes by searching the new exe for the vtable's or table's mapped pointers. Then steps 3 to 5; the generated table must differ from the old one only in `[build]` and addresses. If the revision string moved, write a new `revision_pattern` (bytes around the six digits that match once).

## 4. Add the version file and opcode folder

Both live in Poe2Protocol: commit there first, then the pointers in Poe2Server and the hub. Name the build with letters, digits and dots only (`0.5.5f`, not `0.5.5f`): the name ends up in release and package file names, and the launcher and mod manifests refuse anything else.

1. Copy `modules/protocol/versions/<old>.toml` and change: `version`, `build_revision` (what `check-build` printed, the `Build Revision:` of `Client.txt`), `status = "experimental"` until step 6 passes, `[exe]` (`sha256`, `size`, `pe_timestamp`, `image_size`; from the report's fingerprint table), the depots and manifests (Steam download dialog or DepotDownloader; old manifests may disappear), `[verify]` sizes (`ls -l` the key files), `[protocol] opcodes`, `[client_hook] signatures`, `[client] hashes = ["<new exe sha256>"]` with `hashes_confirmed = false`, `[data]` (`schema_sha256`, `row_counts`, anchors; after a data patch the anchors' row indices are what the server's keys depend on: change config and anchors together).
2. When every deserializer is unchanged and nothing is renumbered (a client-only hotfix), keep `[protocol] opcodes` pointing at the old folder and skip this step. Otherwise `cp -r modules/protocol/opcodes/<old> modules/protocol/opcodes/<new>`, fix headers and renumbered or new opcodes (compare the factory dumps opcode by opcode: a class's deserializer at a new opcode is a renumber, and the client-to-server numbers are not in any dump, so the game tests confirm them), keep the old table in Poe2Protocol `capture-opcodes/<old>/` so old captures replay, add it to `EMBEDDED` in `modules/protocol/poe-proto/src/opcodes.rs` (a test fails when a folder is missing there). Regenerate the drift baseline: dump the factories (`dump_factory.py`, output `dumps/<new>/ghidra/{login,instance,instance2}_factory*_s2c.json`; `find_switches.py` prints the arguments; for a switch with an index table `--bytes <rva>`) and run `cargo xtask check-build <exe> --version <new> --write-fingerprints`.
3. `cargo xtask versions` (copies the file to the launcher), then `cargo xtask check-build GameFiles/PathOfExileSteam.exe` again: it must exit 0.
4. Set `version = "<new>"` in `modules/server/config/server.toml` (and the example, and `runtime/server.dev.toml`); move `dumps/<old>` aside if its generated data must not mix with the new one. When the terrain inputs did not change (step 1), link the old data: `ln -s ../<old>/terrain dumps/<new>/terrain`. Tests that name the newest version or the config's version string (`poe-config`, the launcher's depot and mod-flow fixtures) need the new name or a pinned old version.
5. When an old build is dropped, move the Ghidra addresses in docs and comments with `scripts/re/convert_addrs.py <old exe> <new exe> <addr_map.tsv> <files>` (code by the map, data by the code's references; it lists what it cannot place) and move `dumps/<old>/` into the new folder.

### The launcher and the version dropdown

The launcher's `build.rs` embeds **every** `modules/launcher/versions/<version>.toml` that has a `version` and a `build_revision` (oldest revision first; `depotdownloader.toml` is skipped), so a second supported build needs no launcher code: `cargo xtask versions` copies the file, a rebuild embeds it, and the title-bar dropdown lists it (newest first, below *Official (read-only)*). The newest revision is the default. Everything version-dependent reads the selected file: install folder (`<data>/game/<version>`, or the per-version folder in Settings), depots and manifests, verification, hook deploy, Play, the mods' compatibility check, the server-package filter of Host a server (`poe-server-v<ver>-game-<version>-...`), and the "needs client X" marks on the server list.

To check: add the file, `cargo test` in `modules/launcher/src-tauri` (`every_embedded_version_is_selectable` walks all versions), `npm run dev` and open `http://localhost:1420/?mock&versions` for a preview with a second version. "Official (read-only)" is not a version file: it reuses the newest file's depots **without** manifests ([launcher.md](launcher.md#game-versions-and-the-official-mode)).

## 5. Tests

```
cargo build && cargo xtask server test               # hub (xtask) and server
cargo test                                          # in each submodule you changed (modules/protocol, modules/client-hook)
cargo test; npm run check                           # modules/launcher/src-tauri, and the frontend if it changed
cargo xtask versions --check
cargo xtask check-build GameFiles/PathOfExileSteam.exe      # exit 0
python3 scripts/check-links.py
```

The `xtask` tests run `check-build` on `GameFiles/PathOfExileSteam.exe` and on a copy with one byte of a required function changed (skipped without `GameFiles/`). Replay tests protect only the build whose captures they replay: for new layouts the user takes new official captures (read-only) and the replay tests get a new capture version.

## 6. The in-game check

Run on the GameFiles copy of the new build, at the user's decision (never the Steam install):

1. `cargo xtask deploy-client`, start the server, start the client: the standalone login screen, no patcher window, the character list and an instance (crypto bypass, key hook), movement (position sync), the overlay (F-keys), an instance with a generated terrain (no tile hash kick). `GameFiles/poe-hook.log` prints the signature summary: every feature `ok`, no "build NOT verified".
2. **The `client_hash`.** While `hashes_confirmed = false` the login server logs `client_hash cannot be checked yet ... client_hash=<hex>` for every login whose hash is not in `[client] hashes` (a listed hash is accepted silently). The hash is a SHA-256 of the whole exe (`LoginClientHash_Get32`, `0x1420f65d0`), so it should equal `[exe] sha256`; confirm it, then set `hashes_confirmed = true` (and `cargo xtask versions`). If it differs, record the logged value in `[client] hashes` first. From then on the server refuses any other client.
3. **The refusal.** With `hashes_confirmed = true`, log in with a client of another build (or temporarily change one hash in the file): the client shows "There has been a patch that you need to update to. Please restart Path of Exile." (our notice names the server's version). `[security] allow_unknown_client = true` lets such a client in (logged).
4. An official read-only session (`deploy-client --official`) when the user plays one: compare with the previous build's captures.
5. Only then `status = "supported"`.

## What the server does with the client's version

The client sends no version string. The 32-byte `client_hash` of `0x0003` (standalone) and `0x0005` (Steam) is a hash of its executable, so it identifies the build before any account is looked at: the login server judges it against `[client] hashes` of the version `[game] version` selects. A known hash is accepted; an unknown one is refused with `BackendErrors` code 8 (`InvalidProtocolVersion`, the client's own "you need to update" popup) plus a notice naming the server's version. While `hashes_confirmed = false`, or when the file lists no hash, nothing is refused and the hash is logged. `[security] allow_unknown_client = true` accepts any hash (logged as a warning). The check is skipped when the config has no version file (`Config::parse`, tests). It protects the login channel; the instance channel needs a ticket from a login that passed it.

## Not automated yet

Factory dumps behind the drift baseline (`dump_factory.py` arguments come from Ghidra), renumber detection, client-to-server layouts, rejection of unknown `.tgr`/`.dgr`/`.tdt`/`.ot` format versions, a pinned dat-schema download, cross-checking the DLL's side-channel hello with the server, `symbols.tsv` per build.

**Deserializer drift.** `opcodes/<version>/deserializers.tsv` holds a fingerprint (function bytes with call/jump targets, RIP-relative and stack displacements, frame sizes and image addresses wildcarded; `xtask/src/fingerprint.rs`) of each server-to-client deserializer. `check-build` fingerprints the new exe's ~100,000 functions and reports each entry *unchanged* or *layout changed* (**FAIL** for an opcode named in `instance.toml`/`login.toml`, a warning otherwise: re-read the message in Ghidra and fix `poe-proto`). Renumbered opcodes are not derived: find the factory switch with `scripts/re/find_switches.py <function> <length>`, dump it with `scripts/re/dump_factory.py`, compare by hand.


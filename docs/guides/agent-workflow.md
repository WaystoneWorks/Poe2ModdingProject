# Agent workflow

How agents work on this project: what past sessions learned the hard way. Commands, logs and test tools: [setup.md](setup.md). Limit: 2,000 words.

## Session size
- One task from [../PLAN.md](../PLAN.md) per session. At 300k context tokens or at the end of the task: commit, update PLAN.md and the topic doc, stop, and give the user a one-line prompt for the next session. `scripts/context-guard.py` warns at 250k and 300k. No handoff files.
- Why: every tool call resends the whole conversation. 90% of this project's tokens went out above 200k context, 64% above 400k.
- Sonnet is the default. Use Opus for hard RE and design.
- Script the analysis: batch checks, gates and logs print a short summary, with full output in `runtime/`. No raw logs or long decompiles when a script can answer.
- Do not resume a huge old session or agent; start a new one from PLAN.md. A delegated agent that stopped early with a small context may be continued in its thread.

## Talking to the user
- Short status messages. Report at a finished step, a gate or a failure. While the user tests the client, wake only on crashes, exits, errors or the awaited event.
- Questions go through AskUserQuestion, recommended option first. Ask before larger changes, releases or anything outward-facing.
- When the user says usage is low: commit (WIP allowed, marked NOT GATED), stop your processes, update PLAN.md.

## Machine limits
- Builds, gates and client batches: `nice -n 19`, `CARGO_BUILD_JOBS=4`; a gate uses at most 8 threads when alone, otherwise 4; one heavy job per agent. VS Code crashed at 100% CPU.
- Processes survive an editor restart: check `ps` before rerunning. Run long gates detached (`setsid nohup ... & disown`), since background tasks die at 2 h; check with `pgrep -x` before waiting on one.
- Never `pkill -f` or `pgrep -f` with a pattern in your own command line: it kills your shell (exit 144). Find the PID (`ps -eo pid,comm,args`) and kill that. Never touch processes you did not start; the user may be playing another game.
- Only one process drives the game client. Write `runtime/client.lock` (name, time), remove it after, and check it and `pgrep -a -f PathOfExileSteam` first.

## Commits and checks
- Commit each working step, docs in the same commit. Submodules first, then the hub pointer; bump nested submodules of Poe2Server together.
- Hub: `cargo build && cargo test`, `cargo xtask versions --check`, `python3 scripts/check-links.py`.
- Server: `cargo xtask server test`, `cargo xtask openapi --check`. **No `cargo fmt` in Poe2Server** (not fmt-clean).
- Client hook: `cargo fmt --all --check`, `cargo xtask build-dll`.
- Launcher: `npm run check`, `npm test`; in `src-tauri`, `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`. Web admin: `npm run check`, `npm test`, `npm run build`. Stale `node_modules` after a pull: `npm ci`.
- Check `git status` for stray files (a mistyped redirect once left a file named `1`). Never put passwords or tokens in prompts; use throwaway accounts (`poe-server account create <name> --password-stdin`).
- Releases only after asking: bump the version, changelog, tag (`v*` launcher, `server-v*`, `hook-v*`), watch the workflow, bump the hub. [releasing.md](../../modules/server/docs/releasing.md), [launcher.md](launcher.md#releasing).
- If the auto-mode classifier blocks starting an agent, ask the user to switch to manual mode; do not work around it.

## In-game testing
Steam may be started for private tests. Never log in to official servers; before a user's capture, stop every client job and run `cargo xtask deploy-client --official`, then deploy back to private.
- **Never `SendInput`:** it types into whatever the user has focused. Use the hook's in-process input (`GameFiles/poe-hook.keys`): `in:`, `indown:`, `inup:`, `inclick:`, `inmove:`, `wait:`, `text:`, `cmd:`, `close`. Space must be a posted key (`0x20`). Snapshot `0x24`, overlay `0x2d`, F8 `0x77`.
- No Spectacle screenshots and never the user's browser. Prefer logs, the hook's snapshots and F8 shots (in the test prefix's `My Games/Path of Exile 2/Screenshots`). UI previews use headless Chromium: `runtime/ui-rework/shot/shot.mjs` (launcher `?mock`, web admin `FIXTURES=./admin-fixtures.mjs`, `SIGNEDOUT=1`, `SETUP=1`).
- Test with fresh clients: a second area entry in one process can hide bugs. Restarting only the server lets a client log in again without relaunching. The client takes about 2 minutes to start.
- `POE_HOOK_TRACE` crashes the client at some function entries (for example `0x140ece810`). Core panics are logged as `PANIC:` in `poe-hook.log` before the abort.
- x64dbg is allowed without asking on the `GameFiles/` client in private sessions, one agent at a time.

### Movement checks
- Input mode: real WASD needs `user_input_mode=wasd` and `last_selected_KBM_input_mode=wasd` in the test prefix while the client is closed, restored afterwards. In `mouse_and_keyboard`, W does not move. `use_wasd_to_move` is unrelated.
- Server config: `python3 scripts/dev-config.py --out runtime/<name>.toml`, `drift_check = true`; read `drift server=... max_cells=...` from `runtime/server-run.log`. `G1_1` open ground (grid 1866332366): x 985..1110, y 600..740. `python3 scripts/re/send_dev.py "teleport x y"`.
- The cursor changes reliably only after a double move: `inmove:1000,300`, `wait:300`, `inmove:<x>,<y>`, `wait:400`. Tap roll: `indown:0x20`, `0x20`, `wait:250`, `inup:0x20`. Sprint: `indown:0x20`, `0x20:1400`, `inup:0x20`.
- Window 2560x1440, player near 1280,590: cursor right is offset `(+38,-29)`, left `(-30,+32)`, up `(+45,+45)`, down `(-35,-35)`. Per-frame truth: `runtime/movement-trace.tsv` and `GameFiles/logs/poe-hook/<session>`.
- Hidden-desktop runs broke sprint-end checks (23-28 cells against 0.1-4.2 visible). Prove any new isolated display (PLAN T0) with the same case. Two-client tests: `scripts/test-mp.sh`.

## RE
Static first. Ghidra must be open (the user starts it with `GHIDRA_MCP_ALLOW_SCRIPTS=1 GHIDRA_MAXMEM=32G`); load MCP tools with ToolSearch; check `docs/re/README.md`. MCP calls abort after 30 minutes and leave an aborted transaction (restart needed), so run long scripts on a background thread. Fallback: `scripts/re/disasm.py` (needs `capstone`); run RE scripts with `third_party/pyenv/bin/python`. Port the client's logic with addresses in the docs.

## Terrain method
- **Client exports** (`gen_batch` in the hook): `scripts/re/terrain_batch.py run <run> --threads 8 --no-deploy`; stop with `terrain_batch.py stop`; [batch.md](../re/terrain/batch.md). Runs live in `dumps/0.5.5e.hotfix1/terrain/batch/<run>/` (batches `full`, `full2`, `batch3`, `batch3-nat`, `w13-nat1`); old run directories can be pruned for space. Traces: `POE_HOOK_GEN_TRACE=1`, one thread, `--stall 1500` for slow areas (BossRush_Area1 takes 13 minutes).
- **Regression gate:** `POE_FORCED_BUDGET=60 nice -n 19 <target>/release/examples/forced_verify <batch-results.tsv> --out <out.tsv> --threads 8`, about 2 h a batch, output only at the end. Compare with `runtime/forced-baseline.tsv` on (area, seed, topology, orientation): no `match` may become a fail. Quick checks: `runtime/wave6/match-sample-in.tsv` (15,000 jobs), `runtime/wave5/b/regress.py`. All three batches: `runtime/r1/gate4.sh` (about 6 h). Natural choice: `forced_natural`, `area_vectors --natural`. Vectors: `dumps/0.5.5e.hotfix1/terrain/vectors/forced-results{,-full2,-batch3}.tsv`.
- **After a gate:** merge results into the vectors by key, make it the new baseline (keep the old copy), run `cargo xtask terrain-matrix`, add an entry to [terrain.md](../status/terrain.md).
- **Rebuild an example before using it** (`cargo build --release -p poe-world --example <name>`): an old binary almost replayed a batch on pre-fix code. Copy the binary before a long gate.
- **Finding a divergence:** `area_trace -- <area> <seed> <export dir> [topology[:orientation]]` compares every lattice checkpoint and prints the first RNG divergence (`POE_SHOW_OURS=1`). Also `layout_diff`, `lay_cmp`, `tgr_diff`, `check_doodads`, `check_grids --blame`, `check_lattice`, `lattice_probe`, `map_dirs`, `map_pins`, `tsi_keys`. Scripts: `runtime/w7/{run.sh,sum.sh,runclient.sh}`, `runtime/w8/ofitdiff.py`.
- **Debug switches:** listed in [dungeon.md](../re/terrain/dungeon.md) and [tgr.md](../re/terrain/tgr.md). `POE_DBG_OCC=<file>` writes to a file named by its value. `POE_RNG_BT=<draw>` backtraces a draw.
- **Parallel agents** (only if the user asks): one Poe2Server worktree each, `git -C modules/server worktree add ../../runtime/wt/<x> -b terrain-<x>`, `modules/*` symlinked to `modules/server/modules/*`, `CARGO_TARGET_DIR=runtime/wt/<x>-target`, `git add crates` only. Check `git diff --stat <base> HEAD -- modules` before merging: agents committed the symlinks twice. Merge into a merge worktree, keep both sides of conflicts, run one full gate on the merged code. Never `git stash` in a shared tree.

## UI
Design tokens are identical in the launcher and web admin (`src/tokens.css`, `src/lib/motion.ts`); change both. Overlay: `ui/theme.rs`, `ui/follow.rs`; ImGui style tokens must be separate `let` bindings, because an array drops them in the wrong order and dear-imgui-rs panics, closing the client. A core hot-reload hides the overlay.

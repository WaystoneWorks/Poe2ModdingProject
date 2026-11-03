# CLAUDE.md

A Rust private server for **Path of Exile 2, client 0.5.5e Hotfix 1** (`0.5.5e.hotfix1`, the only supported build), for personal and educational modding. This repo is the hub (docs, RE notes, scripts, `xtask`); the code is in submodules under `modules/` ([docs/overview.md](docs/overview.md)).

**Start here:** [docs/PLAN.md](docs/PLAN.md) is the only plan and status. Read only what your task needs: [docs/index.md](docs/index.md) maps the rest, [agent-workflow.md](docs/guides/agent-workflow.md) has working rules, [decisions.md](docs/decisions.md) has settled choices.

## Hard rules
- **Never touch the Steam install** (`~/.local/share/Steam/steamapps/common/Path of Exile 2`) or its Proton prefix (`compatdata/2694490`). Use only `GameFiles/`.
- `GameFiles/` changes only through `cargo xtask deploy-client` / `revert-client` / `deploy-core`. Never hand-edit it.
- **Movement: the server must run an exact port of the client's movement code; see [decisions.md](docs/decisions.md#movement-and-world).**
- **Official servers are read-only.** The DLL may observe and log official sessions the user plays; it never sends, alters or injects anything there. Claude never logs in; captures are the user's.
- The Steam install's live `Client.txt` is a read-only reference: never modify or commit it (copy excerpts into `runtime/`).
- No hardcoding: opcodes in `modules/protocol/opcodes/<version>/*.toml`; ports, leagues, start areas in `modules/server/config/server.toml`; client builds in `modules/protocol/versions/<version>.toml`; game data from `poe-data`; subsystems behind traits.
- External tools in `third_party/`; generated data in git-ignored `dumps/<version>/`; local files in `runtime/`.
- Commit and push after each working step (`origin main`), submodules first, then the hub pointer.
- Ghidra: `/0.5.5e.hotfix1/PathOfExileSteam.exe`. Every RE address in docs and comments is a Hotfix 1 address.
- Allowed without asking: Steam, the server and the client for private-server tests; x64dbg on the `GameFiles/` client in private sessions. Ask for official captures.

## Session rules
- **One task per session, 300k context at most.** At the end of the task: commit, update PLAN.md and the topic doc, stop. **Keep working until 300k: do not stop or hand off before it, and going over 300k to finish the handoff is fine. At 300k with the task unfinished, hand off yourself** (T3 Code): commit (WIP marked NOT GATED), update PLAN.md, then call `t3_thread_launch` (load it with ToolSearch; workspace `root`; model per the next rule) whose `message` is the handoff: the task, state, files touched, what failed, next steps, and "read CLAUDE.md first". No handoff files. Tell the user the new thread's link and stop.
- **Model routing:** Opus only for hard RE (Ghidra, client traces, porting generator rules) and heavy code design. Everything else (docs, tests and test runs, launcher and web admin UI, config, small fixes, batch runs, summarising logs) goes to Sonnet. An Opus agent hands such a step to a project agent in `.claude/agents/` (`Agent` with `subagent_type` `tester`, `doc-writer` or `batch-runner`, all Sonnet; `re-tracer` is Opus; `run_in_background: false`) with a short brief, and gets back a short report. A Sonnet agent that hits hard RE says so and recommends an Opus thread.
- Script the analysis: print summaries, keep raw output in `runtime/`.

## Doc rules (`python3 scripts/check-links.py` enforces links and word limits)
- One owner per topic; link, never copy. Docs state what is true now, not what happened. Keep every address, offset, opcode and format.
- A failed theory stays only as a short "ruled out" line, when it would otherwise be retried.
- New work goes in PLAN.md and is deleted when done. No new plan, handoff or status files. RE findings go in `docs/re/`. Docs change in the same commit as the code.

## Memory rules
- Memory holds only durable user preferences and pointers to things outside the repo: never progress, status, plans, commit hashes or anything the docs or git record.
- One fact per file, about 100 words at most, 15 files at most. Update or delete before adding.
- Project facts go in the docs. User decisions go in [decisions.md](docs/decisions.md).

## Where things are
- Commands, logs, unattended tests, dev config: [docs/guides/setup.md](docs/guides/setup.md). Build and run the server from the hub: `cargo xtask server build|run|test`.
- Server commands and admins: [docs/guides/server-admin.md](docs/guides/server-admin.md). Hosting and releases: `modules/server/docs/`.
- Architecture: [docs/architecture/](docs/architecture/overview.md). Protocol: [docs/protocol/](docs/protocol/framing.md). RE how-to: [docs/re/README.md](docs/re/README.md). Terrain status: [docs/status/terrain.md](docs/status/terrain.md).

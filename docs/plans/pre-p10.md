# Plan: before P10 (U1-U3, B1, S1)

Steps U1, U2, U3, B1 and S1 of [../PLAN.md](../PLAN.md), asked by the user on 2026-11-05. Each step is one Opus thread; at its end the thread commits, updates PLAN.md and this file, and launches the next step's thread (`t3_thread_launch`, workspace root, Opus 5.5) with the chain instruction below.

## U1, U2, U3: UI review loops
One loop per UI: U1 the launcher (`modules/launcher`, Svelte frontend `src/` and the Tauri commands it calls), U2 the web admin (`modules/web-admin`, served by `poe-web-api`), U3 the DLL overlay (`modules/client-hook`, `poe-hook-core` overlay pages).

1. The thread's main agent (Opus) starts a reviewer sub-agent: `Agent`, `model: "opus"`, `run_in_background: false`. Its brief: review the whole UI (every page and dialog: layout, consistency, wording, empty/error/loading states, accessibility, keyboard use, responsiveness, obvious bugs), give a score out of 10 with the reasons, and a prioritised list of concrete fixes (file and component). It reports only; it does not edit.
2. The main agent makes the fixes, builds and runs the UI's tests.
3. A fresh reviewer sub-agent (same brief, plus the previous score and list) reviews again. Repeat until a reviewer scores **9/10 or higher**. Record each round's score in this file.

Seeing the UI: read the source; screenshots only headless (no visible window, never the user's browser, Spectacle or SendInput). U1/U2: a headless browser render of the built frontend (web admin against a dev server; launcher frontend with its Tauri calls mocked) is fine if it runs invisibly. U3: in-game screenshots through the hidden game test `overlay-pages` (one screenshot per page, `runtime/game-test/`). Game tests run hidden (`cargo xtask game-test <scenario>`, no `--display desktop`).

Done when: a reviewer scores 9/10, the UI's checks pass (launcher `cargo test` + `cargo fmt --check` + frontend build; web admin build and `poe-web-api` tests, `cargo xtask openapi --check`; client-hook `cargo xtask build-dll`, `cargo test -p poe-hook-shared`, `cargo fmt --check`, game test `overlay-pages`), docs describe the result. No release unless the user asks.

Scores: U1 9/10 (rounds 7, 8, 8.5, 8.5, 8.5, 8.5, 9; launcher 1466f55..a67c392 and the final commit), U2 9/10 (rounds 6.5, 7.5, 8.5, 9; web-admin eb9efe1..2e9bfdf, server fec98ee: `class_name` and `GET /admin/data/areas`), U3 -.

## B1: Riverbank spawn facing and first-move teleport
A new character on the Riverbank (`G1_1`, washed-up intro, `[spawn.start_tiles.G1_1]`) can spawn facing the wrong direction, and on its first move it teleports to the zombie intro position instead of walking from where it stands. Find why (Opus RE where needed: the client's intro sequence, the facing the server sends in the player blob/`Positioned`, the washed-up flag, the first movement reply and the cell the server simulates from), fix it in the server, add a test (unit or replay) and a hidden game test of a fresh character's first move on the Riverbank.

## S1: suggestions before P10
An Opus agent reads the project (PLAN.md, backlog, docs/status, code layout, tests, tools) and writes a long, concrete list of what could be done before P10 (missing features that need no C2 capture, debug and admin tools, test coverage, tooling, docs, robustness, hosting), each with value, size and model. The list goes to the user through AskUserQuestion (recommended first); the chosen items become PLAN.md steps with specs. S1 is the end of this chain: it launches no further thread.

## Chain instruction (copy into every launch message)
Read CLAUDE.md first, then docs/PLAN.md and docs/plans/pre-p10.md. Do the next open step of the chain (U1, U2, U3, B1, S1 in that order) and only that. Model: Opus 5.5. At the end: commit (submodules first, then the hub; push), record the result in pre-p10.md and PLAN.md, then launch the next step's thread with `t3_thread_launch` (workspace root, Opus 5.5) whose message is this chain instruction plus the state, tell the user its link and stop. At 300k context with the step unfinished: commit WIP marked NOT GATED, launch a thread for the same step with the state. S1 launches nothing.

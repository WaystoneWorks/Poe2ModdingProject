#!/usr/bin/env python3
"""Claude Code PostToolUse hook: warns when a session's context passes the project limit.

Reads the hook's JSON on stdin, takes the context size from the last assistant usage in the
transcript and prints one reminder per threshold crossed (state in runtime/context-guard/).
Never blocks a tool call; any error exits quietly.
"""
import json
import os
import sys
from pathlib import Path

WARN = 250_000
LIMIT = 300_000
TAIL_BYTES = 2_000_000


def context_tokens(transcript):
    with open(transcript, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - TAIL_BYTES))
        lines = f.read().splitlines()
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        usage = (entry.get("message") or {}).get("usage") if entry.get("type") == "assistant" else None
        if usage:
            return sum(usage.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return 0


def main():
    hook = json.load(sys.stdin)
    tokens = context_tokens(hook["transcript_path"])
    level = 2 if tokens >= LIMIT else 1 if tokens >= WARN else 0
    if not level:
        return
    state = Path(__file__).resolve().parent.parent / "runtime/context-guard" / str(hook["session_id"])
    if state.exists() and int(state.read_text() or 0) >= level:
        return
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(str(level))
    text = (
        f"Context is {tokens // 1000}k: over the 300k session limit. At the next safe point: commit, update "
        "docs/PLAN.md and, if the task is unfinished, hand off to a new thread with t3_thread_launch as CLAUDE.md "
        "'Session rules' says (the handoff is the thread's first message); then stop."
        if level == 2
        else f"Context is {tokens // 1000}k of the 300k session limit. Plan to finish this task or stop at a safe point soon."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass

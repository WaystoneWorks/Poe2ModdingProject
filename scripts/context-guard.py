#!/usr/bin/env python3
"""Claude Code PostToolUse hook: tells the agent once when its context reaches the 300k limit.

Reads the hook's JSON on stdin, takes the context size from the last assistant usage in the
transcript and prints one reminder (state in runtime/context-guard/). There is deliberately no
earlier warning: agents stopped early on it (user decision 2026-11-02).
Never blocks a tool call; any error exits quietly.
"""
import json
import os
import sys
from pathlib import Path

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
    if tokens < LIMIT:
        return
    state = Path(__file__).resolve().parent.parent / "runtime/context-guard" / str(hook["session_id"])
    if state.exists():
        return
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("1")
    text = (
        f"Context is {tokens // 1000}k: over the 300k session limit. At the next safe point: commit, update "
        "docs/PLAN.md and, if the task is unfinished, hand off to a new thread with t3_thread_launch as CLAUDE.md "
        "'Session rules' says (the handoff is the thread's first message); then stop."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass

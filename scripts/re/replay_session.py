#!/usr/bin/env python3
"""Turn a window of a recorded DLL session (WASD mode) into a game-test scenario that plays the
same input into a hidden client, on the original timeline (T1 step 5, docs/plans/sync-tools.md).

The session logs no raw keys or mouse events, so the input is rebuilt from what the client sent:
  0x63 vector          -> WASD keys held (nearest of 8 directions; W = (127,127), D = (127,-127))
  0x2e6 held / released -> Space down / up (roll, sprint)
  0x62 aim (mode 2)     -> cursor moved to that cell's screen point (inmove)
  0x1a5 with an entity  -> left button pressed at the cursor, released with the next 0x1ac
  0x356 WarpRequest     -> `tp` to the arrival cell (the World panel's click cannot be replayed)
Screen points come from the original player's position (movement log `frame #` lines) and the
game test's fixed projection (2560 x 1440, xtask game_test.rs `screen_of_cell`). Entries carry
`at:<ms>` from --from, so the DLL plays them as a timeline.

Usage: replay_session.py <session dir> --from HH:MM:SS[.mmm] --to HH:MM:SS[.mmm] --area G1_2
         --seed 1 --out <scenario.toml>
The day is the session's. Writes the scenario and prints what it holds."""
import argparse
import bisect
import datetime
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import movement_fixtures as mf  # noqa: E402
import movement_sequences as ms  # noqa: E402

CELL = 250 / 23
# The 8 key sets by direction index round(angle / 45) (angle of the 0x63 vector).
KEYS = [(0x57, 0x44), (0x57,), (0x57, 0x41), (0x41,), (0x53, 0x41), (0x53,), (0x53, 0x44), (0x44,)]
# The vector reaches the wire about 11 ms after the key (game test snap-known).
KEY_LEAD_MS = 11
LIFT = 80  # px: a click on an object's model, not its ground cell (b4 tests)
FRAME = re.compile(r'^(\d+\.\d+) .*frame #\d+ .*world \((-?[\d.]+), (-?[\d.]+)\)')


def screen_of_cell(dx, dy):
    return 1280.0 + 9.67 * (dx - dy), 647.0 - 8.0 * (dx + dy)


def parse_time(day, s):
    t = datetime.datetime.strptime(s, "%H:%M:%S.%f" if "." in s else "%H:%M:%S").time()
    return datetime.datetime.combine(day, t).timestamp() * 1000


def main():
    a = argparse.ArgumentParser()
    a.add_argument("session")
    a.add_argument("--from", dest="start", required=True)
    a.add_argument("--to", dest="end", required=True)
    a.add_argument("--area", required=True)
    a.add_argument("--seed", required=True)
    a.add_argument("--out", required=True)
    o = a.parse_args()

    msgs = ms.load(ms.resolve(o.session))
    day = datetime.datetime.fromtimestamp(msgs[0].t / 1000).date()
    t0, t1 = parse_time(day, o.start), parse_time(day, o.end)

    frames = []  # (ms, cell x, cell y) of the original client
    with open(os.path.join(o.session, "poe-hook.log"), encoding="utf-8", errors="replace") as f:
        for line in f:
            m = FRAME.match(line)
            if m:
                frames.append((float(m[1]) * 1000, float(m[2]) / CELL, float(m[3]) / CELL))
    ft = [x[0] for x in frames]

    def player(t):
        i = bisect.bisect_right(ft, t) - 1
        return frames[max(i, 0)][1:]

    start_cell = tuple(round(v) for v in player(t0))
    out, held, space, cursor, pressed = [], set(), False, None, False
    counts = {}

    def emit(t, entries, kind):
        out.append((max(0, round(t - t0)), entries))
        counts[kind] = counts.get(kind, 0) + 1

    me = None
    for n, m in enumerate(msgs):
        if m.dir == "in" and m.op == 0x64 and m.d and me is None and t0 <= m.t:
            me = m.d["ent"]
        if m.dir != "out" or not (t0 <= m.t <= t1):
            continue
        k = mf.to_input(m)
        if m.op == 0x356:
            arrive = next((q for q in msgs[n:] if q.dir == "in" and q.op == 0x64 and q.d
                           and (q.d["dx"], q.d["dy"]) != (0, 0) and q.t - m.t < 500), None)
            if arrive:
                emit(m.t, [f"cmd:tp {arrive.d['gx']} {arrive.d['gy']}"], "warp")
            continue
        if m.op == 0x5B:
            sys.exit(f"a waypoint travel at {m.t}: the window must stay in one area")
        if not k:
            continue
        if k["op"] == "wasd" and not k.get("cursor"):
            want = set()
            if (k["x"], k["y"]) != (0, 0):
                want = set(KEYS[round(math.degrees(math.atan2(k["y"], k["x"])) / 45) % 8])
            e = [f"inup:{v:#x}" for v in sorted(held - want)] + [f"indown:{v:#x}" for v in sorted(want - held)]
            if e:
                emit(m.t - KEY_LEAD_MS, e, "keys")
            held = want
        elif k["op"] == "sprint":
            if k["held"] != space:
                emit(m.t - KEY_LEAD_MS, ["indown:0x20", "down:0x20"] if k["held"] else ["up:0x20", "inup:0x20"], "space")
                space = k["held"]
        elif k["op"] == "aim":
            px, py = player(m.t)
            sx, sy = screen_of_cell(k["x"] - px, k["y"] - py)
            pos = (min(max(int(sx), 0), 2559), min(max(int(sy), 0), 1439))
            if pos != cursor and not pressed:
                emit(m.t, [f"inmove:{pos[0]},{pos[1]}"], "aim")
                cursor = pos
        elif k["op"] == "use_skill" and "entity" in k:
            if cursor is None:
                px, py = player(m.t)
                sx, sy = screen_of_cell(k["x"] - px, k["y"] - py)
                cursor = (int(sx), int(sy - LIFT))
            emit(m.t - KEY_LEAD_MS, [f"inpress:{cursor[0]},{cursor[1]}"], "click")
            pressed = True
        elif k["op"] == "input_end" and pressed:
            emit(m.t + 30, [f"inrelease:{cursor[0]},{cursor[1]}"], "release")
            pressed = False
    end = [f"inup:{v:#x}" for v in sorted(held)] + (["up:0x20", "inup:0x20"] if space else [])
    if pressed:
        end.append(f"inrelease:{cursor[0]},{cursor[1]}")
    out.append((round(t1 - t0) + 500, end))
    out.sort(key=lambda e: e[0])
    # One line per entry time; a `cmd:` takes its whole line in the DLL (auto_keys.rs).
    lines = []
    for at, e in out:
        plain = [x for x in e if not x.startswith("cmd:")]
        lines.append(" ".join([f"at:{at}"] + plain))
        lines += [x for x in e if x.startswith("cmd:")]
    timeline = "\\n".join(lines)

    name = os.path.basename(os.path.normpath(o.session))
    scen = f'''# Generated by scripts/re/replay_session.py from {name} {o.start} to {o.end}: the user's
# input replayed on its original timeline (T1 step 5). `after` lists the snaps and compares the
# replay's positions with the original's (replay_compare.py).
description = "replay of {name} {o.start}-{o.end}"
input_mode = "wasd"
after = ["python3 scripts/re/snaps.py {{session}} --expect", "python3 scripts/re/replay_compare.py {o.session} {{session}} --from {o.start} --to {o.end}"]

[client_env]
POE_HOOK_MOVEMENT_LOG = "1"

[server]
"dev.drift_check" = true
"dev.drift_interval_ms" = 100

[[step]]
name = "transfer to {o.area} seed {o.seed}"
cmd = "transfer {o.area} {o.seed}"

[[step]]
name = "in the new instance"
expect_log = "player entered the world"
since = "action"
timeout_s = 60

[[step]]
name = "in {o.area}"
expect_state = {{ area = "{o.area}" }}
timeout_s = 60

[[step]]
name = "settled"
wait_ms = 3000

[[step]]
name = "to the start cell"
cmd = "tp {start_cell[0]} {start_cell[1]}"

[[step]]
name = "there"
expect_state = {{ near = [{start_cell[0]}, {start_cell[1]}, 2] }}

[[step]]
name = "settle"
wait_ms = 800

[[step]]
name = "replay {round((t1 - t0) / 1000, 1)} s"
keys = "{timeline}"

[[step]]
name = "after"
wait_ms = 1500
'''
    with open(o.out, "w") as f:
        f.write(scen)
    print(f"{o.out}: start cell {start_cell}, {round((t1 - t0) / 1000, 1)} s, entries {counts}")


if __name__ == "__main__":
    main()

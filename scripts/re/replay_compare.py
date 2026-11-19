#!/usr/bin/env python3
"""Where a replayed session (replay_session.py) left the original: the client's position in both
on one clock (original from --from, replay from the DLL's `timeline start` line), every 0.5 s,
the first time they stay more than 2 cells apart for 0.5 s, and the world jumps (a frame step
over 3 cells that is not part of a roll: a snap or a teleport) of each, side by side.

Usage: replay_compare.py <original session dir> <replay session dir> --from HH:MM:SS[.mmm]
         --to HH:MM:SS[.mmm]
Always exits 0 (a report)."""
import argparse
import bisect
import datetime
import os
import re

CELL = 250 / 23
FRAME = re.compile(r'^(\d+\.\d+) .*frame #(\d+) .*world \((-?[\d.]+), (-?[\d.]+)\)')
START = re.compile(r'^(\d+\.\d+) .*poe-hook.keys: timeline start')
JUMP = 3.0
APART = 2.0


def frames(session):
    out, start = [], None
    with open(os.path.join(session, "poe-hook.log"), encoding="utf-8", errors="replace") as f:
        for line in f:
            m = FRAME.match(line)
            if m:
                out.append((float(m[1]) * 1000, int(m[2]), float(m[3]) / CELL, float(m[4]) / CELL))
            elif start is None and (s := START.match(line)):
                start = float(s[1]) * 1000
    return out, start


def parse_time(day, s):
    t = datetime.datetime.strptime(s, "%H:%M:%S.%f" if "." in s else "%H:%M:%S").time()
    return datetime.datetime.combine(day, t).timestamp() * 1000


def step(a, b):
    return ((b[2] - a[2]) ** 2 + (b[3] - a[3]) ** 2) ** 0.5


def jumps(fr, t0, dur):
    """Frame steps over JUMP cells, without rolls (a run: the next step is nearly as long)."""
    out = []
    for a, b, c in zip(fr, fr[1:], fr[2:] + [fr[-1]]):
        d = step(a, b)
        if d > JUMP and step(b, c) < 0.8 * d and 0 <= b[0] - t0 <= dur:
            out.append((b[0] - t0, b[1], d, (round(a[2]), round(a[3])), (round(b[2]), round(b[3]))))
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument("original")
    a.add_argument("replay")
    a.add_argument("--from", dest="start", required=True)
    a.add_argument("--to", dest="end", required=True)
    o = a.parse_args()
    orig, _ = frames(o.original)
    rep, rstart = frames(o.replay)
    if not orig or not rep or rstart is None:
        print("no frames or no timeline start line; nothing to compare")
        return
    day = datetime.datetime.fromtimestamp(orig[0][0] / 1000).date()
    t0, t1 = parse_time(day, o.start), parse_time(day, o.end)
    dur = t1 - t0
    ot, rt = [x[0] for x in orig], [x[0] for x in rep]

    def at(fr, ts, t):
        i = max(bisect.bisect_right(ts, t) - 1, 0)
        return fr[i]

    first_apart, run = None, 0
    print("   t s  original (cell)    replay (cell)   apart")
    t = 0.0
    while t <= dur:
        a_, b_ = at(orig, ot, t0 + t), at(rep, rt, rstart + t)
        d = ((a_[2] - b_[2]) ** 2 + (a_[3] - b_[3]) ** 2) ** 0.5
        run = run + 1 if d > APART else 0
        if first_apart is None and run == 5:
            first_apart = (t - 400, d)
        if t % 500 == 0:
            print(f"{t / 1000:6.1f}  ({a_[2]:6.1f},{a_[3]:6.1f})  ({b_[2]:6.1f},{b_[3]:6.1f})  {d:5.1f}")
        t += 100
    for name, fr, start in (("original", orig, t0), ("replay", rep, rstart)):
        js = jumps(fr, start, dur)
        print(f"{name} jumps over {JUMP} cells: {len(js)}")
        for j in js[:30]:
            print(f"  t {j[0] / 1000:6.2f} s frame {j[1]} {j[2]:5.1f} cells {j[3]} -> {j[4]}")
    if first_apart:
        print(f"first apart (> {APART} cells for 0.5 s): t {first_apart[0] / 1000:.1f} s, {first_apart[1]:.1f} cells")
    else:
        print(f"never more than {APART} cells apart")


if __name__ == "__main__":
    main()

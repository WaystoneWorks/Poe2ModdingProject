#!/usr/bin/env python3
"""Every sprint end of an official session, with the client's coast (R3, problem 5).

For each sprint of the local player (per area: `movement_fixtures.player_by_area`) prints:
  - roll t0, sprint on/off frames relative to t0, the end's cause: `release` (the client's
    `0x2e6 held=0` answered by `0x2e7` in the off batch), `t0+35` (an earlier release),
    `attack` (a `0x1c8` of another skill in the off batch), `other` (wall, stun, ...);
  - whether a `MoveAck` stream ran (`0x64` of length 549-551 before the end), the WASD vector
    held at the end (last `0x63`), `must_sprint` off frame;
  - the player's `0x64` in off..off+3 (vector, cell, `unscaled` when not 550 long);
  - the client (poe-hook.log `movement_log`): steps from the off frame on, the coast length
    (frames until the step falls under 0.05 cells or a Move starts), its distance, and the
    `action start slot 1: Move` frame relative to the off batch.

Usage: sprint_ends.py <session> [--verbose]
Analysis only; keep the output in runtime/.
"""
import argparse
import bisect
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import movement_fixtures as mf  # noqa: E402
import movement_sequences as ms  # noqa: E402

CELL = mf.WORLD_PER_CELL


def stat_dict(m):
    return {mf.stat_name(k): v for k, v in m.d["stats"]}


def client_log(session, msgs):
    """frame -> step length (cells), and frames of `action start slot 1: Move` / any start, in
    capture frames. The DLL's frame counter restarts with every area, so each run of the log
    is shifted by the median difference between the capture frame received by the line's time
    and the logged frame."""
    path = os.path.join(os.path.dirname(ms.resolve(session)), "poe-hook.log")
    times = [(m.t, m.frame) for m in msgs]
    tkeys = [t for t, _ in times]
    pat = re.compile(r"^(\d+\.\d+) .*frame #(\d+) dt=[\d.]+ world \((-?[\d.]+), (-?[\d.]+)\) step \((-?[\d.]+), (-?[\d.]+)\)")
    act = re.compile(r"^(\d+\.\d+) .*action (start|end) slot (\d): (\S+) .*frame (\d+)\)")
    runs, cur, last = [], [], -1
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = pat.search(line)
            if m:
                fr = int(m[2])
                if fr < last:
                    runs.append(cur)
                    cur = []
                last = fr
                cur.append(("pos", float(m[1]), fr, math.hypot(float(m[5]), float(m[6])) / CELL))
                continue
            a = act.search(line)
            if a:
                fr = int(a[5])
                if fr < last - 5:
                    runs.append(cur)
                    cur = []
                    last = fr
                cur.append(("act", float(a[1]), fr, (a[2], int(a[3]), a[4])))
    runs.append(cur)
    pos, moves, acts = {}, [], []
    for run in runs:
        diffs = []
        for kind, t, fr, _ in run:
            i = bisect.bisect_right(tkeys, t * 1000) - 1
            if i >= 0:
                diffs.append(times[i][1] - fr)
        if not diffs:
            continue
        off = sorted(diffs)[len(diffs) // 2]
        for kind, t, fr, v in run:
            if kind == "pos":
                pos[fr + off] = v
            else:
                acts.append((fr + off, v[0], v[1], v[2]))
                if v[0] == "start" and v[2] == "Move":
                    moves.append(fr + off)
    return pos, moves, acts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    msgs = ms.load(ms.resolve(a.session))
    entries = mf.area_entries(msgs)
    players = mf.player_by_area(msgs, entries)
    bounds = [b for b, _ in players]

    def player_at(f):
        return players[bisect.bisect_right(bounds, f) - 1][1]

    steps, moves, acts = client_log(a.session, msgs)
    by_frame = {}
    for m in msgs:
        by_frame.setdefault(m.frame, []).append(m)
    ons, n = [], 0
    for m in msgs:
        if m.dir == "in" and m.op == 0x1D3 and m.d and m.d.get("ent") == player_at(m.frame):
            st = stat_dict(m)
            if st.get("is_sprinting") == 1:
                ons.append(m)
            elif st.get("is_sprinting") == 0 and ons:
                on = ons.pop()
                ons.clear()
                n += 1
                report(n, on, m, msgs, by_frame, player_at, steps, moves, acts, a.verbose)
    print(f"sprint-ends: {n} sprints")


def report(n, on, off, msgs, by_frame, player_at, steps, moves, acts, verbose):
    pe = player_at(off.frame)
    f0, f1 = on.frame, off.frame
    rolls = [m for m in msgs if m.dir == "in" and m.op == 0x1C8 and m.d and m.d.get("ent") == pe
             and f0 - 40 <= m.frame <= f0 and (m.d["skill"] & 0xFFFFFF00) == 0x80000000]
    t0 = rolls[-1].frame if rolls else None
    batch = by_frame.get(f1, [])
    release = any(q.dir == "in" and q.op == 0x2E7 and q.d and q.d.get("ent") == pe
                  and q.d.get("held") == 0 for q in batch)
    attack = any(q.dir == "in" and q.op == 0x1C8 and q.d and q.d.get("ent") == pe
                 and (q.d["skill"] & 0xFFFFFF00) != 0x80000000 for q in batch)
    rel_frames = [q.frame for q in msgs if q.dir == "out" and q.op == 0x2E6 and q.d
                  and q.d.get("held") == 0 and f0 - 20 <= q.frame <= f1]
    cause = "attack" if attack else "release" if release else \
        ("t0+35" if rel_frames and t0 is not None and f1 - t0 in (34, 35, 36) else "other")
    acks = [q for q in msgs if q.dir == "in" and q.op == 0x64 and q.d and q.d.get("ent") == pe
            and f0 <= q.frame < f1]
    stream = [q for q in acks if 545 <= math.hypot(q.d["dx"], q.d["dy"]) <= 555]
    wasd = [q for q in msgs if q.dir == "out" and q.op == 0x63 and q.d and q.frame <= f1
            and q.frame >= (t0 or f0) - 60]
    held = (wasd[-1].d["x"], wasd[-1].d["y"]) if wasd else None
    must = [q.frame for q in msgs if q.dir == "in" and q.op == 0x1D3 and q.d and q.d.get("ent") == pe
            and f0 <= q.frame <= f1 and stat_dict(q).get("must_sprint") == 0]
    after = []
    for q in msgs:
        if q.dir == "in" and q.op == 0x64 and q.d and q.d.get("ent") == pe and f1 <= q.frame <= f1 + 3:
            ln = math.hypot(q.d["dx"], q.d["dy"])
            tag = "" if 545 <= ln <= 555 else " unscaled"
            after.append(f"f+{q.frame - f1} ({q.d['dx']},{q.d['dy']}) @({q.d['gx']},{q.d['gy']}){tag}")
    last_cell = (acks[-1].d["gx"], acks[-1].d["gy"]) if acks else None
    # Client coast: steps from f1 on until under 0.05 or a Move starts.
    mv = next((f for f in moves if f > f1 - 1), None)
    coast, dist, first = 0, 0.0, []
    for f in range(f1, f1 + 45):
        s = steps.get(f, 0.0)
        if mv is not None and f >= mv + 1:
            break
        if f > f1 + 1 and s < 0.05:
            break
        coast += 1
        dist += s
        if len(first) < 4:
            first.append(round(s, 2))
    end_acts = [f"{x[3]}@{x[0] - f1:+d}" for x in acts if f1 - 2 <= x[0] <= f1 + 3 and x[1] == "start"]
    print(f"sprint {n}: f{f1} ent {pe} t0={'f%d' % t0 if t0 else '?'} on t0+{f0 - t0 if t0 else '?'} "
          f"off t0+{f1 - t0 if t0 else '?'} cause {cause} (releases {[r - (t0 or 0) for r in rel_frames]}) "
          f"must_sprint off {[x - (t0 or 0) for x in must]}; stream {len(stream)} "
          f"(first {'t0+%d' % (stream[0].frame - t0) if stream and t0 else '-'}); wasd {held}; "
          f"last 0x64 cell {last_cell}")
    print(f"   after: {', '.join(after) or 'no 0x64'}; client: coast {coast} frames {dist:.1f} cells "
          f"first {first}; Move start {('off%+d' % (mv - f1)) if mv is not None and mv - f1 < 60 else '-'}; "
          f"starts near off {end_acts}")
    if verbose:
        print("   steps:", [round(steps.get(f, 0.0), 2) for f in range(f1 - 2, f1 + 32)])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reduces an official capture to what the movement port is checked against offline: per client
frame the server's movement messages for the local player and the client's logged state.
Log frames restart per area; each segment's offset to the packet frames is found from the `0x64`
cells (they equal the logged grid). See docs/re/wasd-movement.md, Port design.

Usage: movement_replay_trace.py <session dir> <out dir>
Writes <out dir>/seg<N>.tsv, lines: `<frame> <component> <seq> <kind> <args...>`, the message's
place in the frame's drain (-1: header order key 0, before all entities; 99: logged state):
  M dx dy gx gy (0x64) | A move|roll|other sx sy tx ty (0x1c8) | S stat value (0x1d3) | K held (0x2e7)
  G gx gy (logged grid) | L sx sy cx cy ex ey (LINE, unswapped) | P gx gy sx sy x,y... (PATHPLAN, goal first) | I dx dy (0x63)
"""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import movement_sequences as ms

STATS = {22342: "is_sprinting", 22426: "must_sprint", 236: "permyriad", 174: "sprint_pct"}
MOVE, ROLLS = 0x20002909, (0x80000040, 0x80000041)
FR = re.compile(r"frame #(\d+) dt=[\d.]+ world \(\S+, \S+\) step \(\S+, \S+\) grid \((\d+), (\d+)\)")
LI = re.compile(r"LINE frame=(\d+) s=(-?\d+),(-?\d+) .*?e=(-?\d+),(-?\d+) cur=(-?\d+),(-?\d+) flag=\d swap=(\d)")
PP = re.compile(r"PATHPLAN #\d+ frame=(\d+) goal=(-?\d+),(-?\d+) start=(-?\d+),(-?\d+).*? path=(.*)$")

def main(sess, out):
    msgs = ms.load(os.path.join(sess, "packets.jsonl"))
    segs, last = [], -1
    for line in open(os.path.join(sess, "poe-hook.log"), errors="replace"):
        rows = None
        m = FR.search(line)
        if m:
            f = int(m[1])
            if f < last or not segs:
                segs.append([])
            last = f
            segs[-1].append((f, 99, 2, "G", m[2], m[3]))
            continue
        if not segs:
            continue
        m = LI.search(line)
        if m:
            c, e = (m[6], m[7]), (m[4], m[5])
            if m[8] == "1":
                c, e = c[::-1], e[::-1]
            segs[-1].append((int(m[1]), 99, 1, "L", m[2], m[3], *c, *e))
            continue
        m = PP.search(line)
        if m:
            segs[-1].append((int(m[1]), 99, 0, "P", m[2], m[3], m[4], m[5], *m[6].split()))
    os.makedirs(out, exist_ok=True)
    m64 = [m for m in msgs if m.op == 0x64 and m.dir == "in" and m.d
           and (m.d["dx"], m.d["dy"]) != (0, 0)]
    prev_hi = -1
    for n, seg in enumerate(segs):
        grid = {r[0]: (int(r[4]), int(r[5])) for r in seg if r[3] == "G"}
        c = collections.Counter()
        for m in m64:
            g = (m.d["gx"], m.d["gy"])
            for f, v in grid.items():
                if v == g:
                    c[f - m.frame] += 1
        off, hits = c.most_common(1)[0] if c else (None, 0)
        if off is None or hits < 50:
            print(f"seg{n}: {len(grid)} frames, no offset ({hits} hits), skipped")
            continue
        lo, hi = min(grid) - off - 1, max(grid) - off + 1
        # The player's entity id changes per area: the one the server acknowledges skills for.
        me = collections.Counter(m.d["ent"] for m in m64 if lo <= m.frame <= hi).most_common(1)[0][0]
        rows = list(seg)
        for m in msgs:
            if not lo <= m.frame <= hi or not m.d:
                continue
            f = m.frame + off
            if m.dir == "out" and m.op == 0x63 and "dx" in m.d:
                rows.append((f, 98, 0, "I", m.d["dx"], m.d["dy"]))
            if m.dir != "in" or m.d.get("ent") != me:
                continue
            d = m.d
            pos = (-1 if d.get("u14") == 0 else d.get("u18"), d.get("u1a"))
            if m.op == 0x64:
                rows.append((f, *pos, "M", d["dx"], d["dy"], d["gx"], d["gy"]))
            elif m.op == 0x1C8:
                k = "move" if d["skill"] == MOVE else "roll" if d["skill"] in ROLLS else "other"
                rows.append((f, *pos, "A", k, d["gx"], d["gy"], d["tx"], d["ty"]))
            elif m.op == 0x1D3:
                for key, v in d["stats"]:
                    if key in STATS:
                        rows.append((f, *pos, "S", STATS[key], v))
            elif m.op == 0x2E7:
                rows.append((f, *pos, "K", int(d["held"])))
        rows.sort(key=lambda r: r[:3])
        path = os.path.join(out, f"seg{n}.tsv")
        with open(path, "w") as f:
            for r in rows:
                f.write(" ".join(map(str, r)) + "\n")
        print(f"seg{n}: offset {off}, {hits}/{len(m64)} 0x64 cells on the logged grid, {len(rows)} rows -> {path}")

main(sys.argv[1], sys.argv[2])

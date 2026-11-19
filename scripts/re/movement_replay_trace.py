#!/usr/bin/env python3
"""Reduces an official capture to what the movement port is checked against offline: per client
frame the server's movement messages for the local player and the client's logged state.
Log frames restart per area; each segment's offset to the packet frames is found from the `0x64`
cells (they equal the logged grid). See docs/re/wasd-movement.md, Port design.

Usage: movement_replay_trace.py <session dir> <out dir> [--skills MOVE,INTERACT,ROLL[,ROLL2]]
Writes <out dir>/seg<N>.meta (`0x<area HASH16> <seed> <offset>`) and <out dir>/seg<N>.tsv, lines: `<frame> <component> <seq> <kind> <args...>`, the message's
place in the frame's drain (-1: header order key 0, before all entities; 99: logged state):
  M dx dy gx gy (0x64) | A move|roll|interact|other sx sy tx ty (0x1c8) | S stat value (0x1d3) | K held (0x2e7) | T x y (0x1af)
  G gx gy (logged grid) | L sx sy cx cy ex ey px py len acc (LINE, unswapped) | P gx gy sx sy x,y... (PATHPLAN, goal first) | I dx dy (0x63)
"""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import movement_sequences as ms

STATS = {22342: "is_sprinting", 22426: "must_sprint", 236: "permyriad", 174: "sprint_pct"}
MOVE, ROLLS = 0x20002909, (0x80000040, 0x80000041)
FR = re.compile(r"frame #(\d+) dt=[\d.]+ world \(\S+, \S+\) step \(\S+, \S+\) grid \((\d+), (\d+)\)")
LI = re.compile(r"LINE frame=(\d+) s=(-?\d+),(-?\d+) p=(-?[\d.]+),(-?[\d.]+) .*?e=(-?\d+),(-?\d+) cur=(-?\d+),(-?\d+) flag=\d swap=(\d).*? len=([\d.]+) .*? acc=(-?[\d.]+)")
# The snap detector's applies (DLL feature snap_log): the exact log frame of each 0x64 and 0x1c8.
CHK = re.compile(r"SNAPCHK frame=(\d+) op=(0x[0-9a-f]+) cell=\((-?\d+),(-?\d+)\)")
PP = re.compile(r"PATHPLAN #\d+ frame=(\d+) goal=(-?\d+),(-?\d+) start=(-?\d+),(-?\d+).*? path=(.*)$")

def main(sess, out, skills=None):
    # `--skills MOVE,INTERACT,ROLL[,ROLL2]`: a private session's ids (replay_terrain prints them).
    move, interact, rolls = MOVE, None, ROLLS
    if skills:
        v = [int(x, 0) for x in skills.split(",")]
        move, interact, rolls = v[0], v[1], tuple(v[2:])
    msgs = ms.load(os.path.join(sess, "packets.jsonl"))
    segs, last = [], -1
    for line in open(os.path.join(sess, "poe-hook.log"), errors="replace"):
        rows = None
        m = FR.search(line)
        if m:
            f = int(m[1])
            # Frame #1 starts an area (an area left at once logs only its frame #1).
            if f < last or f == 1 or not segs:
                segs.append([])
            last = f
            segs[-1].append((f, 99, 2, "G", m[2], m[3]))
            continue
        if not segs:
            continue
        m = CHK.search(line)
        if m:
            segs[-1].append((int(m[1]), 99, 3, "C", m[2], m[3], m[4]))
            continue
        m = LI.search(line)
        if m:
            c, e, q = (m[8], m[9]), (m[6], m[7]), (m[4], m[5])
            if m[10] == "1":
                c, e, q = c[::-1], e[::-1], q[::-1]
            segs[-1].append((int(m[1]), 99, 1, "L", m[2], m[3], *c, *e, *q, m[11], m[12]))
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
        # With the snap detector's lines the offset is exact: each 0x64 apply against the sent 0x64.
        chk = [(r[0], (int(r[5]), int(r[6]))) for r in seg if r[3] == "C" and r[4] == "0x64"]
        if chk:
            c2 = collections.Counter()
            sent = [m for m in msgs if m.op == 0x64 and m.dir == "in" and m.d]
            for f, cell in chk:
                for m in sent:
                    if (m.d["gx"], m.d["gy"]) == cell:
                        c2[f - m.frame] += 1
            if c2:
                off, hits = c2.most_common(1)[0]
                if hits * 2 >= len(chk):
                    hits = max(hits, 50)
        if off is None or hits < 50:
            print(f"seg{n}: {len(grid)} frames, no offset ({hits} hits), skipped")
            continue
        lo, hi = min(grid) - off - 1, max(grid) - off + 1
        # The player's entity id changes per area: the one the server acknowledges skills for.
        me = collections.Counter(m.d["ent"] for m in msgs if m.op == 0x64 and m.dir == "in" and m.d
                                 and lo <= m.frame <= hi).most_common(1)[0][0]
        rows = [r for r in seg if r[3] != "C"]
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
                k = "move" if d["skill"] == move else "roll" if d["skill"] in rolls else "interact" if d["skill"] == interact else "other"
                rows.append((f, *pos, "A", k, d["gx"], d["gy"], d["tx"], d["ty"]))
            elif m.op == 0x1AF:
                rows.append((f, *pos, "T", d["x"], d["y"]))
            elif m.op == 0x1D3:
                for key, v in d["stats"]:
                    if key in STATS:
                        rows.append((f, *pos, "S", STATS[key], v))
            elif m.op == 0x2E7:
                rows.append((f, *pos, "K", int(d["held"])))
        rows.sort(key=lambda r: r[:3])
        # The segment's area: the last AreaInfo (0x1e: u8, u32 instance, u16 HASH16, u16 length +
        # league, u32 seed) before the segment.
        ai = [m for m in msgs if m.op == 0x1E and m.dir == "in" and m.frame <= lo + 1]
        if ai:
            b = bytes.fromhex(ai[-1].hex)
            n_ = int.from_bytes(b[9:11], "big")
            with open(os.path.join(out, f"seg{n}.meta"), "w") as f:
                f.write(f"0x{b[7:9].hex()} {int.from_bytes(b[11 + n_:15 + n_], 'big')} {off}\n")
        path = os.path.join(out, f"seg{n}.tsv")
        with open(path, "w") as f:
            for r in rows:
                f.write(" ".join(map(str, r)) + "\n")
        print(f"seg{n}: offset {off}, {hits}/{len(m64)} 0x64 cells on the logged grid, {len(rows)} rows -> {path}")

a = [x for x in sys.argv[1:] if not x.startswith("--")]
main(a[0], a[1], sys.argv[sys.argv.index("--skills") + 1] if "--skills" in sys.argv else None)

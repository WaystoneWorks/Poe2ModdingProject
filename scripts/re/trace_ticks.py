#!/usr/bin/env python3
"""Per-tick table of a movement trace: server position and modelled grid, the 0x64 sent,
the client's report for the same frame, and whether the client snapped.

A snap = the client's report sits exactly on the centre of the cell the tick's non-zero
0x64 carried while the server's own position is elsewhere in that cell (or another cell).

Usage: scripts/re/trace_ticks.py TRACE [--from T] [--to T] [--snaps] [--summary]
"""
import argparse
import math


def load(path):
    seg = []
    for line in open(path):
        if line.startswith("#"):
            seg = []
            continue
        p = line.rstrip("\n").split("\t")
        seg.append((float(p[0]), p[2], p[3:]))
    ticks = {}
    cur = None
    inputs = []
    for ms, k, f in seg:
        if k == "tick":
            cur = int(f[0])
            ticks[cur] = {"t": cur, "out": [], "in": inputs}
            inputs = []
        elif k == "pos" and cur is not None:
            ticks[cur]["pos"] = (float(f[0]), float(f[1]))
            ticks[cur]["grid"] = (int(f[2]), int(f[3]))
        elif k == "report":
            n = int(f[0])
            ticks.setdefault(n, {"t": n, "out": [], "in": []})["rep"] = (float(f[1]), float(f[2]), f[3], f[4])
        elif k.startswith("out-") and cur is not None:
            ticks[cur]["out"].append((k[4:], f))
        elif k.startswith("in-"):
            inputs.append((k[3:], " ".join(f)))
    return ticks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--to", dest="hi", type=int, default=10**9)
    ap.add_argument("--snaps", action="store_true", help="only rows with a non-zero 0x64")
    args = ap.parse_args()
    ticks = load(args.trace)
    snaps = dirs = 0
    for n in sorted(ticks):
        if n < args.lo or n > args.hi:
            continue
        t = ticks[n]
        rep = t.get("rep")
        pos = t.get("pos")
        dirs_here = [f for k, f in t["out"] if k == "dir"]
        snap = ""
        for f in dirs_here:
            vx, vy, cx, cy = map(int, f[:4])
            if (vx, vy) == (0, 0):
                continue
            dirs += 1
            if rep and abs(rep[0] - (cx + 0.5)) < 1e-3 and abs(rep[1] - (cy + 0.5)) < 1e-3:
                if not (pos and abs(pos[0] - rep[0]) < 1e-3 and abs(pos[1] - rep[1]) < 1e-3):
                    snap = "SNAP"
                    snaps += 1
        if args.snaps and not dirs_here:
            continue
        step = ""
        if rep and n - 1 in ticks and ticks[n - 1].get("rep"):
            pr = ticks[n - 1]["rep"]
            step = f"{math.hypot(rep[0]-pr[0], rep[1]-pr[1]):5.2f}"
        d = ""
        if rep and pos:
            d = f"{math.hypot(rep[0]-pos[0], rep[1]-pos[1]):6.2f}"
        outs = " ".join(k + ":" + ",".join(f) for k, f in t["out"] if k not in ("target", "aim"))
        ins = " ".join(k + ":" + v for k, v in t["in"] if k not in ("AimTarget", "UpdateSkillTarget"))
        ps = f"{pos[0]:8.2f},{pos[1]:8.2f} g{t['grid'][0]},{t['grid'][1]}" if pos else "-"
        rs = f"{rep[0]:8.2f},{rep[1]:8.2f} {rep[3]}" if rep else "-"
        print(f"{n:5d} srv {ps:30s} cli {rs:26s} d{d} st{step} {snap:4s} {outs} | {ins}")
    print(f"# non-zero 0x64: {dirs}, snaps: {snaps}")


if __name__ == "__main__":
    main()

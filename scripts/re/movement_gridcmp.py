#!/usr/bin/env python3
# movement_gridcmp.py TRACE POE_HOOK_LOG [PORT] [--show N] [--window LO HI]: the client's own grid (poe-hook movement_log
# "frame #n ... grid (x, y)", the same frame counter as the position reports) against the server:
# each non-zero 0x64 cell sent at tick t against the client's grid at frame t (and t-1, t+1), and
# the server's modelled grid (pos line) against the client's grid per frame.
# The last player entity's frames (the last "frame #1" block) belong to the trace's last session.
import sys, re, collections
argv = sys.argv[1:]
show = 30
if "--show" in argv:
    i = argv.index("--show"); show = int(argv[i + 1]); del argv[i:i + 2]
if "--window" in argv:
    i = argv.index("--window"); del argv[i:i + 3]
a = argv
trace, hook = a[0], a[1]
ports = collections.Counter()
for line in open(trace):
    f = line.split("\t")
    if len(f) > 2 and f[2] == "tick": ports[f[1]] += 1
port = a[2] if len(a) > 2 else list(ports)[-1]  # default: the last session
tick = 0; acks = {}; model = {}; outs = collections.defaultdict(list)
for line in open(trace):
    f = line.rstrip("\n").split("\t")
    if len(f) < 3 or f[1] != port: continue
    k = f[2]
    if k == "tick": tick = int(f[3])
    elif k == "pos": model[tick] = (int(f[5]), int(f[6]))
    elif k == "out-dir": acks[tick] = ((int(f[3]), int(f[4])), (int(f[5]), int(f[6])))
    if k.startswith("out-") and k not in ("out-aim", "out-target"): outs[tick].append(k[4:] + " " + " ".join(f[3:7]))
    if k.startswith("in-") and k not in ("in-AimTarget", "in-UpdateSkillTarget"): outs[tick].append("IN " + k[3:] + " " + " ".join(f[3:])[:30])
grid = {}; world = {}
pat = re.compile(r"frame #(\d+) dt=\S+ world \(([-\d.]+), ([-\d.]+)\) step \(([-\d.]+), ([-\d.]+)\) grid \((-?\d+), (-?\d+)\)")
for line in open(hook, errors="replace"):
    m = pat.search(line)
    if not m: continue
    n = int(m[1])
    if n == 1: grid = {}; world = {}
    grid[n] = (int(m[6]), int(m[7])); world[n] = (float(m[2]) / (250 / 23), float(m[3]) / (250 / 23))
# Frames without a line kept the last grid (the log writes only when the position changes).
last = None
for n in range(1, max(grid) + 1 if grid else 1):
    if n in grid: last = grid[n]
    elif last: grid[n] = last
print(f"port {port}: {len(model)} ticks, {len(acks)} 0x64, client frames {len(grid)}")
c = collections.Counter(); shown = 0
for t, (d, cell) in sorted(acks.items()):
    if d == (0, 0) or t not in grid: continue
    hit = [k for k in (-1, 0, 1) if grid.get(t + k) == cell]
    c["same frame" if 0 in hit else f"frame {hit}" if hit else "none"] += 1
    if 0 not in hit and shown < show:
        shown += 1
        print(f"t{t} 0x64 {d} {cell}: client grid t-1 {grid.get(t-1)} t {grid.get(t)} t+1 {grid.get(t+1)}; model {model.get(t)} | {'; '.join(outs.get(t, []))[:140]}")
print("0x64 cell vs client grid:", dict(c))
m = collections.Counter(k for t in model if t in grid for k in ["same" if model[t] == grid[t] else "differ"])
print("model grid vs client grid per frame:", dict(m))
runs = []
for t in sorted(model):
    if t in grid and model[t] != grid[t]:
        if runs and runs[-1][1] == t - 1: runs[-1][1] = t
        else: runs.append([t, t])
for r in runs[:show]:
    t = r[0]
    print(f"  differ f{r[0]}-{r[1]}: model {model[t]} client {grid[t]} | {'; '.join(x for k in range(t - 3, t + 1) for x in outs.get(k, []))[:160]}")
if "--window" in sys.argv:
    i = sys.argv.index("--window"); lo, hi = int(sys.argv[i + 1]), int(sys.argv[i + 2])
    for t in range(lo, hi + 1):
        w = world.get(t)
        print(f"{t} client {grid.get(t)} {'(%.2f,%.2f)' % w if w else '-'} model {model.get(t)} {'*' if grid.get(t) != model.get(t) else ''} | {'; '.join(outs.get(t, []))[:150]}")

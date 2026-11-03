#!/usr/bin/env python3
"""Checks the port of the client's grid line (`GridLine` in poe-game movement.rs) against a
client log with `movement_log` and `path_log` (poe-hook.log): per moving frame, the predicted
grid cell against the logged Positioned grid (+0x444/+0x448), and the cell of the position.

Usage: scripts/re/grid_line_check.py <poe-hook.log>
"""
import re, math, sys, collections
U = 250/23
def floor(v): return math.floor(v)
class Line:
    def __init__(s, S, E, P=None):
        sf = (float(S[0]), float(S[1])); ef = (float(E[0]), float(E[1]))
        p = sf
        if P is not None and P != ef and (sf[0]-P[0])**2 + (sf[1]-P[1])**2 < 4.0: p = P
        d = (ef[0]-p[0], ef[1]-p[1])
        if p == sf: q = S
        else:
            l2 = d[0]**2 + d[1]**2
            t = ((sf[0]-p[0])*d[0] + (sf[1]-p[1])*d[1])/l2 if l2 > 0 else 0
            q = (floor(d[0]*t+p[0]+.5), floor(d[1]*t+p[1]+.5))
        ix, iy = abs(E[0]-q[0]), abs(E[1]-q[1])
        s.ym = ix < iy or (p != sf and ix == iy and abs(d[0]) < abs(d[1]))
        s.S, s.q, s.E = S, q, E
        if s.ym: pm, pn, en, qm, em = p[1], p[0], ef[0], q[1], E[1]
        else: pm, pn, en, qm, em = p[0], p[1], ef[1], q[0], E[0]
        df = abs(em - pm)
        s.dead = df <= 0
        if s.dead: return
        s.slope = (en - pn)/df
        off = abs(em - qm) - df
        s.m0 = pn - s.slope*off + (0.49 if s.slope > 0 else 0.5)
    def cell(s, pos):
        if s.dead: return s.E
        if s.q == s.E: return s.E if s.S == s.E else s.S
        pm, qm, em = (pos[1], s.q[1], s.E[1]) if s.ym else (pos[0], s.q[0], s.E[0])
        tot = abs(em-qm); rem = abs(em-pm)
        k = max(0, min(tot, floor(tot - rem + 1e-4)))
        if k == 0: return s.S
        maj = qm + k*(1 if em > qm else -1); mn = floor(s.m0 + k*s.slope)
        return (mn, maj) if s.ym else (maj, mn)
    def done(s, pos):
        return s.dead or s.cell(pos) == s.E

fr = re.compile(r"frame #(\d+) dt=[\d.]+ world \((-?[\d.]+), (-?[\d.]+)\) step \((-?[\d.]+), (-?[\d.]+)\) grid \((\d+), (\d+)\)")
pp = re.compile(r"PATHPLAN #\d+ frame=(\d+) goal=(-?\d+),(-?\d+) start=(-?\d+),(-?\d+).*path=([-\d, ]+)")
mode = "prev"
line = None; wps = []; prev = None; prev2 = None
c = collections.Counter(); bad = []
for raw in open(sys.argv[1], errors="replace"):
    m = pp.search(raw)
    if m:
        S = (int(m[4]), int(m[5]))
        cells = [tuple(map(int, x.split(','))) for x in m[6].strip().split()]
        cells = cells[::-1][1:]
        if not cells: line = Line(S, S); wps = []; continue
        P = None
        if prev is not None and prev[3] > 0.01 and (prev[4]) == S:
            P = (prev[0]-.5, prev[1]-.5)
        line = Line(S, cells[0], P if mode != "none" else None); wps = cells[1:]
        continue
    m = fr.search(raw)
    if not m: continue
    x, y = float(m[2])/U, float(m[3])/U
    st = math.hypot(float(m[4]), float(m[5]))/U
    g = (int(m[6]), int(m[7]))
    pos = (x-.5, y-.5)
    if line is not None and st > 0.01:
        # advance through finished lines
        while line.done(pos) and wps:
            e = line.E; line = Line(e, wps[0]); wps = wps[1:]
        pred = line.cell(pos)
        fl = (floor(x), floor(y))
        c['n'] += 1; c['model'] += pred == g; c['floor'] += fl == g
        if pred != g and len(bad) < 15: bad.append((m[1], round(x,2), round(y,2), 'grid', g, 'pred', pred, 'line', line.S, line.q, line.E))
    prev = (x, y, None, st, g)
print(c)
for b in bad: print(b)

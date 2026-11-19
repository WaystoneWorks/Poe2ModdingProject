"""Snaps of the local player in a DLL session, from the snap detector's lines (feature
`snap_log`, modules/client-hook/poe-hook-core/src/snap_log.rs; on by default).

A snap is exact: a non-zero 0x64 or a 0x1c8 applied while its cell differs from the client's
grid (docs/re/server-code.md, section 1). A `teleport` (0x64 with a vector, then a zero 0x64 at
the same cell in the same or next frame) is intended and listed apart.

Usage: snaps.py <session dir or poe-hook.log> [--quiet] [--expect]
Prints the applies per opcode, each snap (frame, opcode, cell, grid, distance in cells, world
jump, the FORCED setter call it caused) and the forced sets from other callers. Exit 1 when a
snap is left (teleports excluded), with --expect when none is; the last line is the summary."""
import os
import re
import sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
quiet = '--quiet' in sys.argv
if len(args) != 1:
    print(__doc__)
    sys.exit(2)
path = args[0]
if os.path.isdir(path):
    path = os.path.join(path, 'poe-hook.log')

# Return addresses after the two snap call sites (0x14215941c in the Actor handler,
# 0x141e50144 in Actor_InstallQueuedMove).
CALLERS = {0x142159421: '0x64', 0x141e50149: '0x1c8'}

CHK = re.compile(r'SNAPCHK frame=(\d+) op=(0x[0-9a-f]+) cell=\((-?\d+),(-?\d+)\)(.*)')
SNAP = re.compile(r'SNAP frame=(\d+) op=(0x[0-9a-f]+) cell=\((-?\d+),(-?\d+)\) '
                  r'grid=\((-?\d+),(-?\d+)\) d=([\d.]+) jump=([\d.]+)')
FORCED = re.compile(r'FORCED frame=(\d+) caller=(0x[0-9a-f]+) grid=\((-?\d+),(-?\d+)\) '
                    r'-> cell=\((-?\d+),(-?\d+)\)')
TIME = re.compile(r'^(\d+\.\d+) ')

checks = []   # (line no, frame, op, cell, zero vector)
snaps = []    # dict
forced = []   # (line no, frame, caller, grid, cell)
for no, line in enumerate(open(path, errors='replace')):
    t = TIME.match(line)
    t = float(t[1]) if t else None
    if m := SNAP.search(line):
        snaps.append(dict(no=no, t=t, frame=int(m[1]), op=m[2], cell=(int(m[3]), int(m[4])),
                          grid=(int(m[5]), int(m[6])), d=float(m[7]), jump=float(m[8])))
    elif m := CHK.search(line):
        checks.append((no, int(m[1]), m[2], (int(m[3]), int(m[4])), 'nocheck' in m[5]))
    elif m := FORCED.search(line):
        forced.append((no, int(m[1]), int(m[2], 16), (int(m[3]), int(m[4])),
                       (int(m[5]), int(m[6]))))

if not checks and not forced:
    print('no SNAPCHK lines (snap_log off, or no move applied)')
    sys.exit(1)

# Teleports: a snapping 0x64 followed by a zero-vector 0x64 at the same cell within a frame.
zeros = {(f, c) for _, f, op, c, z in checks if z}
for s in snaps:
    s['teleport'] = s['op'] == '0x64' and any((s['frame'] + k, s['cell']) in zeros for k in (0, 1))

real = [s for s in snaps if not s['teleport']]
by_op = {}
for _, _, op, _, z in checks:
    if not z:
        by_op[op] = by_op.get(op, 0) + 1
print('applies: ' + ', '.join(f'{op} {n}' for op, n in sorted(by_op.items())) +
      f'; zero-vector 0x64 {len(zeros)}')
if not quiet:
    for s in snaps:
        kind = 'teleport' if s['teleport'] else 'SNAP'
        print(f"{kind} frame={s['frame']} op={s['op']} cell={s['cell']} grid={s['grid']} "
              f"d={s['d']:.2f} cells jump={s['jump']:.1f} world"
              + (f" t={s['t']:.3f}" if s['t'] else ''))
    other = [f for f in forced if f[2] not in CALLERS]
    for no, frame, caller, grid, cell in other:
        print(f'forced by {caller:#x} frame={frame} grid={grid} -> cell={cell}')
worst = max((s['d'] for s in real), default=0.0)
print(f'snaps {len(real)} (worst {worst:.2f} cells), teleports {len(snaps) - len(real)}, '
      f'forced sets by other callers {sum(f[2] not in CALLERS for f in forced)}')
sys.exit(int(bool(real) != ('--expect' in sys.argv)))

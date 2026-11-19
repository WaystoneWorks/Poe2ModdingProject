"""Client world jumps (snaps) in a DLL session with the movement log (POE_HOOK_MOVEMENT_LOG=1),
leaving out teleports. A jump is a frame step over 25 world units (2.3 cells) and over 3 times
both neighbouring steps. A teleport is a 0x64 pair at one cell with direction (0,0) last
(`teleport` command); a jump that lands within 2 cells of one within 0.3 s is that teleport.
Usage: world_jumps.py <session dir>. Exit 1 when a jump is left; the last line is the summary.
Times: poe-hook.log has epoch seconds, packets.txt local wall time (both from this machine)."""
import datetime as dt
import re
import sys

S = sys.argv[1]
frames = []  # (epoch, frame number, step length, grid)
for l in open(S + '/poe-hook.log', errors='replace'):
    m = re.match(r'(\d+\.\d+) .*frame #(\d+) dt=\S+ world \(([-\d.]+), ([-\d.]+)\) '
                 r'step \(([-\d.]+), ([-\d.]+)\) grid \((\d+), (\d+)\)', l)
    if m:
        frames.append((float(m[1]), int(m[2]), (float(m[5]) ** 2 + float(m[6]) ** 2) ** .5,
                       (int(m[7]), int(m[8]))))
if not frames:
    print('no movement log frames (POE_HOOK_MOVEMENT_LOG=1 not set?)')
    sys.exit(1)
day = dt.datetime.fromtimestamp(frames[0][0]).date()


def varints(b, i, n):
    out = []
    for _ in range(n):
        if b[i] & 0x80:
            v = ((b[i] & 0x7f) << 8) | b[i + 1]
            if v & 0x2000:
                v -= 0x4000
            i += 2
        else:
            v = b[i]
            if v & 0x40:
                v -= 0x80
            i += 1
        out.append(v)
    return out


def epoch(hms):
    h, mi, s = hms.split(':')
    t = dt.datetime(day.year, day.month, day.day, int(h), int(mi)) + dt.timedelta(seconds=float(s))
    return t.timestamp()


teleports = []  # (epoch, cell)
for l in open(S + '/packets.txt', errors='replace'):
    p = l.split()
    if len(p) < 6 or p[1] != 'in' or p[2] != 'instance' or p[3] != '0x0064':
        continue
    b = bytes.fromhex(l[l.index(' B ') + 3:].strip().replace(' ', ''))
    dx, dy, cx, cy = varints(b, 13, 4)
    if (dx, dy) == (0, 0):
        teleports.append((epoch(p[0]), (cx, cy)))

left = 0
for a, b, c in zip(frames, frames[1:], frames[2:]):
    if b[1] != a[1] + 1 or b[1] <= 2:
        continue  # new area or log gap
    if not (b[2] > 25 and b[2] > 3 * max(a[2], c[2])):
        continue
    tp = any(abs(t - b[0]) < 0.3 and max(abs(cell[0] - b[3][0]), abs(cell[1] - b[3][1])) <= 2
             for t, cell in teleports)
    when = dt.datetime.fromtimestamp(b[0]).time()
    print(f'{"teleport" if tp else "JUMP"} frame {b[1]} {when} step {b[2] / 10.87:.1f} cells grid {a[3]}->{b[3]}')
    left += not tp
print(f'world jumps outside teleports: {left}')
sys.exit(1 if left else 0)

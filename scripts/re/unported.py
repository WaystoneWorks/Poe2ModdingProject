"""Unported client movement code a DLL session ran for the local player, from the
`UNPORTED` lines of the DLL feature `unported_log`
(modules/client-hook/poe-hook-core/src/unported_log.rs; on by default). The list of sites is in
docs/re/movement-coverage.md.

Usage: unported.py <session dir or poe-hook.log> [--expect fn[,fn...]] [--quiet]
Prints, per site, the frames hit (one line per site and frame), the first and last frame, the
callers, and the first few lines. With --expect, exit 1 unless every named site was hit;
without, exit 0. The last line is the summary."""
import collections
import os
import re
import sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
expect = []
if '--expect' in sys.argv:
    i = sys.argv.index('--expect')
    expect = sys.argv[i + 1].split(',') if i + 1 < len(sys.argv) else []
    args = [a for a in args if a != sys.argv[i + 1]]
quiet = '--quiet' in sys.argv
if len(args) != 1:
    print(__doc__)
    sys.exit(2)
path = args[0]
if os.path.isdir(path):
    path = os.path.join(path, 'poe-hook.log')

LINE = re.compile(r'UNPORTED frame=(\d+) fn=(\w+) caller=(0x[0-9a-f]+) (.*)')
hits = collections.defaultdict(list)  # fn -> [(frame, caller, rest)]
for line in open(path, errors='replace'):
    if m := LINE.search(line):
        hits[m[2]].append((int(m[1]), m[3], m[4].strip()))

for fn, hs in sorted(hits.items()):
    frames = [h[0] for h in hs]
    callers = collections.Counter(h[1] for h in hs)
    print('%-20s %5d frames  first %d  last %d  callers %s' % (
        fn, len(hs), min(frames), max(frames),
        ' '.join('%s x%d' % c for c in callers.most_common(4))))
    if not quiet:
        for f, c, rest in hs[:5]:
            print('    frame %d %s %s' % (f, c, rest))

missing = [e for e in expect if e not in hits]
summary = ', '.join('%s %d' % (fn, len(hs)) for fn, hs in sorted(hits.items())) or 'none'
print('unported: %s%s' % (summary, ('; MISSING ' + ','.join(missing)) if missing else ''))
sys.exit(1 if missing else 0)

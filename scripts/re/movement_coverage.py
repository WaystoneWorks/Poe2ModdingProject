"""Generate docs/re/movement-coverage.md: one row per client function named in the movement RE
docs (docs/re/movement-*.md, pathfinding.md and the "Clicking an object" section of
world-travel.md) or logged by the DLL feature `unported_log`, with the server files that cite
it and the `UNPORTED` hits per session.

Usage: movement_coverage.py [--session label=<session dir or poe-hook.log> ...] [--check]
                            [--contexts <file>]
  --check     exit 1 if the doc on disk differs from what would be written (nothing is written).
  --contexts  also write the doc text around each function that still has no name.

Function ranges come from dumps/0.5.5h/addr_map.tsv (new_va, new_size), falling back to the
exe's .pdata. An address inside a function counts for that function. Addresses outside .text
(globals, vtables) are skipped. Names are the backticked identifier written next to the address
in the docs (`Name` `0x...` or `0x...` (`Name`)), else the dump's Ghidra name; the hand-written
names in scripts/re/movement_coverage_names.tsv (address<TAB>name) win over both.
A function is cited when any .rs file under modules/server/crates names an address inside it."""
import bisect
import collections
import glob
import json
import os
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'docs/re/movement-coverage.md')
EXE = os.path.join(ROOT, 'GameFiles/PathOfExileSteam.exe')
NAMES = os.path.join(ROOT, 'scripts/re/movement_coverage_names.tsv')
ADDR = re.compile(r'0x14[0-9a-f]{7}\b')
IDENT = r'`\**([A-Za-z_][A-Za-z0-9_:]*)\**`'
BEFORE = re.compile(IDENT + r'\s*\**`?\s*(?:\(|at\s+)?\**`?(0x14[0-9a-f]{7})')
AFTER = re.compile(r'(0x14[0-9a-f]{7})`?\**\s*\(\s*' + IDENT)
# unported_log site -> function entry (unported_log.rs).
UNPORTED = {
    'astar_fallback': 0x141edc7d0,
    'push_test': 0x141dee9e0,
    'can_push': 0x141df03c0,
    'step_entity_hit': 0x141dfdb80,
    'move_event_clipped': 0x141f70e30,
}
SHORT = {'movement-click': 'click', 'movement-positioned': 'positioned', 'movement-roll': 'roll',
         'movement-sprint': 'sprint', 'movement-capture-index': 'index', 'pathfinding': 'path',
         'world-travel': 'travel'}


def sources():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'docs/re/movement-*.md'))):
        if f != OUT:
            out.append((os.path.basename(f)[:-3], open(f).read()))
    out.append(('pathfinding', open(os.path.join(ROOT, 'docs/re/pathfinding.md')).read()))
    wt = open(os.path.join(ROOT, 'docs/re/world-travel.md')).read()
    m = re.search(r'\n## Clicking an object.*?(?=\n## |\Z)', wt, re.S)
    out.append(('world-travel', m.group(0)))
    return out


def text_range():
    d = open(EXE, 'rb').read(4096)
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]
    o = pe + 24 + struct.unpack_from('<H', d, pe + 20)[0]
    secs = {}
    for i in range(n):
        name, vs, va, rs, rp = struct.unpack_from('<8sIIII', d, o + 40 * i)
        secs[name.rstrip(b'\0').decode()] = (va, vs, rp)
    return secs


def functions(secs):
    fn = {}
    for line in open(os.path.join(ROOT, 'dumps/0.5.5h/addr_map.tsv')).read().splitlines()[1:]:
        p = line.split('\t')
        if len(p) > 3 and p[1].startswith('0x') and p[3].isdigit():
            fn[int(p[1], 16)] = int(p[3])
    va, vs, rp = secs['.pdata']
    with open(EXE, 'rb') as f:
        f.seek(rp)
        pdata = f.read(vs)
    for i in range(0, len(pdata) - 11, 12):
        b, e, _ = struct.unpack_from('<III', pdata, i)
        if b and 0x140000000 + b not in fn:
            fn[0x140000000 + b] = e - b
    starts = sorted(fn)
    return starts, fn


def containing(a, starts, fn):
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0 and a < starts[i] + fn[starts[i]]:
        return starts[i]
    return a  # unknown range: the address is its own row


def ghidra_names():
    p = os.path.join(ROOT, 'dumps/0.5.5h/ghidra/ghidra_named_functions_p1.json')
    if not os.path.exists(p):
        return {}
    return {int(r['address'], 16): r['name'] for r in json.load(open(p))['results']}


def server_cites():
    cites = collections.defaultdict(set)
    for f in glob.glob(os.path.join(ROOT, 'modules/server/crates/**/*.rs'), recursive=True):
        rel = os.path.relpath(f, os.path.join(ROOT, 'modules/server/crates'))
        for a in ADDR.findall(open(f, errors='replace').read()):
            cites[int(a, 16)].add(rel)
    return cites


def session_hits(path):
    if os.path.isdir(path):
        path = os.path.join(path, 'poe-hook.log')
    hits = collections.Counter()
    seen = set()
    for line in open(path, errors='replace'):
        if m := re.search(r'UNPORTED frame=(\d+) fn=(\w+)', line):
            if (m[1], m[2]) not in seen:
                seen.add((m[1], m[2]))
                hits[m[2]] += 1
    return hits


def main():
    argv = sys.argv[1:]
    check = '--check' in argv
    sessions = []
    for i, a in enumerate(argv):
        if a == '--session':
            label, path = argv[i + 1].split('=', 1)
            sessions.append((label, session_hits(path)))
    secs = text_range()
    tva, tvs, _ = secs['.text']
    lo, hi = 0x140000000 + tva, 0x140000000 + tva + tvs
    starts, fn = functions(secs)
    gnames = ghidra_names()
    curated = {}
    if os.path.exists(NAMES):
        for line in open(NAMES):
            if line.strip() and not line.startswith('#'):
                a, n = line.rstrip('\n').split('\t', 1)
                curated[int(a, 16)] = n.strip()
    rows = {}  # entry -> {'docs': set, 'names': Counter, 'sites': set}
    skipped = set()
    for doc, text in sources():
        named = {}
        for m in BEFORE.finditer(text):
            named.setdefault(int(m[2], 16), collections.Counter())[m[1]] += 1
        for m in AFTER.finditer(text):
            named.setdefault(int(m[1], 16), collections.Counter())[m[2]] += 1
        for a in set(int(x, 16) for x in ADDR.findall(text)):
            if not lo <= a < hi:
                skipped.add(a)
                continue
            e = containing(a, starts, fn)
            r = rows.setdefault(e, {'docs': set(), 'names': collections.Counter(), 'sites': set()})
            r['docs'].add(SHORT.get(doc, doc))
            if a == e:
                r['names'].update(named.get(a, {}))
            else:
                r['sites'].add(a)
    for site, e in UNPORTED.items():
        r = rows.setdefault(e, {'docs': set(), 'names': collections.Counter(), 'sites': set()})
        r['docs'].add('unported_log')
    by_fn = {e: s for s, e in UNPORTED.items()}
    cites = server_cites()
    cite_fn = collections.defaultdict(set)
    for a, files in cites.items():
        if lo <= a < hi:
            cite_fn[containing(a, starts, fn)] |= files

    lines = []
    counts = collections.Counter()
    for e in sorted(rows):
        r = rows[e]
        names = [n for n, _ in r['names'].most_common()
                 if not n.startswith(('FUN_', 'LAB_')) and n != 'this'
                 and (n != n.lower() or '_' in n)]
        name = curated.get(e) or (names[0] if names else gnames.get(e, ''))
        if name.startswith(('FUN_', 'switchD', 'caseD')):
            name = ''
        files = sorted(cite_fn.get(e, ()))
        flagged = by_fn.get(e)
        if files and flagged:
            status = 'partial (`%s`)' % flagged
        elif files:
            status = 'cited'
        elif flagged:
            status = 'no (`%s`)' % flagged
        else:
            status = ''
        counts[status.split(' ')[0] or 'none'] += 1
        server = ', '.join('`%s`' % f.replace('poe-game/src/', '') for f in files)
        hits = []
        for _, h in sessions:
            hits.append(str(h.get(flagged, 0)) if flagged else '')
        cells = ['`%x`' % e, '`%s`' % name if name else '', ' '.join(sorted(r['docs'])),
                 status, server] + hits
        lines.append('| ' + ' | '.join(cells) + ' |')

    if '--contexts' in argv:
        texts = sources()
        with open(argv[argv.index('--contexts') + 1], 'w') as out:
            for e in sorted(rows):
                if e in curated or any(l.startswith('| `%x` | `' % e) for l in lines):
                    continue
                out.write('== 0x%x (sites %s)\n' % (e, ' '.join('0x%x' % x for x in sorted(rows[e]['sites']))))
                for a in [e] + sorted(rows[e]['sites']):
                    for doc, t in texts:
                        for m in list(re.finditer('0x%x' % a, t))[:2]:
                            out.write('  [%s] %s\n' % (doc, t[max(0, m.start() - 160):m.end() + 100].replace('\n', ' ')))
    head = ['Address', 'Name', 'Docs', 'Status', 'Server'] + [s for s, _ in sessions]
    doc = HEADER.format(n=len(rows), cited=counts['cited'], partial=counts['partial'],
                        no=counts['no'], none=counts['none'], skipped=len(skipped))
    doc += '| ' + ' | '.join(head) + ' |\n|' + '---|' * len(head) + '\n' + '\n'.join(lines) + '\n'
    if check:
        same = os.path.exists(OUT) and open(OUT).read() == doc
        print('movement-coverage.md', 'up to date' if same else 'OUT OF DATE')
        sys.exit(0 if same else 1)
    open(OUT, 'w').write(doc)
    print('%d functions: cited %d, partial %d, no %d, not cited %d; %d non-code addresses skipped'
          % (len(rows), counts['cited'], counts['partial'], counts['no'], counts['none'],
             len(skipped)))


HEADER = """# Movement coverage

Which client movement functions the server's copy (`modules/server/crates/poe-game/src/clientsim.rs`, `clientpath.rs`) ports, generated by `scripts/re/movement_coverage.py` (do not edit by hand; rerun it after a doc or port changes, with the same `--session` arguments as below). Tools: [movement.md](../protocol/movement.md#test-tooling).

One row per client function (0.5.5h) named in [movement-click](movement-click.md), [movement-positioned](movement-positioned.md), [movement-roll](movement-roll.md), [movement-sprint](movement-sprint.md), [movement-capture-index](movement-capture-index.md), [pathfinding](pathfinding.md), the "Clicking an object" section of [world-travel](world-travel.md#clicking-an-object), or logged by the DLL feature `unported_log` ([client-dll.md](../architecture/client-dll.md)). An address inside a function counts for that function. {skipped} addresses outside `.text` (globals, vtables) are not listed.

Status:
- `cited`: a server source file names an address in the function (usually its port).
- `partial`: cited, and `unported_log` flags a part the server lacks (its site name in brackets).
- `no`: flagged by `unported_log`, not cited.
- empty: not cited. Many of these are not movement rules (input, rendering, network, containers) and need no port.

Session columns: player frames with an `UNPORTED` line for the function (`scripts/re/unported.py`). `snap-known` is `runtime/game-test/snap-known-20261119-174004` (warp onto a checkpoint, walk out), `walk` is `runtime/game-test/walk-20261119-174920` (open ground, a wall stop, a roll: no hits).

Totals: {n} functions; cited {cited}, partial {partial}, no {no}, not cited {none}.

"""

if __name__ == '__main__':
    main()

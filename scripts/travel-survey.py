#!/usr/bin/env python3
"""Offline check of every transition in acts 1-4 and the interludes (P9).

Runs `area_objects --survey <seed>` (modules/server/crates/poe-world/examples/area_objects.rs)
over every area reachable from the campaign towns, then reports:
  - areas, gates by rule (docs/re/world-travel.md), waypoints, checkpoints;
  - areas the generator cannot build (not covered);
  - connections of an area that no gate leads to (towns travel to the next act by NPC);
  - area links with no gate back.
Fails (exit 1) when a gate has no target, a gate leads to an area that is not one of its area's
connections, or the object stage errors.

Usage, from the hub root: python3 scripts/travel-survey.py [--seed N ...] [--tsv FILE]
Output TSV: dumps/<version>/travel/survey-<seed>.tsv (git-ignored).
"""
import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path

VERSION = "0.5.5e.hotfix1"
ROOT = Path(__file__).resolve().parent.parent
AREA = re.compile(r'Area \{ area: "([^"]+)"')


def run_survey(seed: int) -> Path:
    out = ROOT / "dumps" / VERSION / "travel" / f"survey-{seed}.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["cargo", "run", "-q", "--release", "--manifest-path", "modules/server/Cargo.toml",
           "-p", "poe-world", "--example", "area_objects", "--", "--survey", str(seed), str(out)]
    subprocess.run(cmd, cwd=ROOT, check=True, stderr=subprocess.DEVNULL)
    return out


def check(tsv: Path) -> int:
    rows = [l.rstrip("\n").split("\t") for l in tsv.open()]
    conns, gates, others, gen_errors, obj_errors = {}, [], [], [], []
    for r in rows:
        conns.setdefault(r[0], [c for c in r[4].split(",") if c])
        kind = r[5]
        if kind == "GATE":
            gates.append(r)
        elif kind == "OTHER":
            others.append(r)
        elif kind == "ERROR":
            gen_errors.append((r[0], r[6][:80]))
        elif kind == "OBJERROR":
            obj_errors.append((r[0], r[6][:80]))
    targets = collections.defaultdict(set)
    bad = []
    for g in gates:
        target = g[9]
        m = AREA.match(target)
        if m:
            targets[g[0]].add(m[1])
            if m[1] not in conns[g[0]]:
                bad.append(f"{g[0]} gate ({g[6]},{g[7]}) leads to {m[1]}, not a connection")
        elif not target.startswith("Teleport"):
            bad.append(f"{g[0]} gate ({g[6]},{g[7]}) has no target ({target})")
    print(f"{tsv.name}: {len(conns)} areas, {len(gates)} gates, {len(others)} waypoints/checkpoints/wells")
    print("  gate rules:", dict(collections.Counter(g[8] for g in gates).most_common()))
    print("  gate targets:", dict(collections.Counter(g[9].split(" ")[0] for g in gates)))
    print("  others:", dict(collections.Counter(o[8].split(" ")[0] for o in others)))
    print(f"  not covered (generator fails): {gen_errors}")
    built = [a for a in conns if a not in {e[0] for e in gen_errors}]
    unreached = [(a, c) for a in built for c in sorted(set(conns[a])) if c not in targets[a]]
    print(f"  connections no gate leads to ({len(unreached)}): {unreached}")
    links = [(a, t) for a in targets for t in targets[a]]
    no_back = [(a, t) for a, t in links if t in targets and a not in targets[t]]
    print(f"  area links {len(links)}, with a gate back {len(links) - len(no_back)}, without: {no_back}")
    for e in obj_errors:
        bad.append(f"object stage error in {e[0]}: {e[1]}")
    for b in bad:
        print("  FAIL", b)
    return 1 if bad else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, action="append", help="seed(s) to survey (default 1)")
    p.add_argument("--tsv", type=Path, action="append", help="check an existing survey TSV instead")
    a = p.parse_args()
    files = a.tsv or [run_survey(s) for s in (a.seed or [1])]
    return max(check(f) for f in files)


if __name__ == "__main__":
    sys.exit(main())

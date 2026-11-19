#!/usr/bin/env python3
"""First divergence of a private session (T1 step 2, docs/plans/sync-tools.md): replays the
client's inputs into our server's movement (Locomotion) and its messages into a client model
(ClientSim), area by area, and prints the first frame where anything differs: the client model
against the client's logged grid, the replayed messages against the ones the server sent, or the
server's model against the client model. Built on scripts/re/movement_replay_trace.py,
movement_own_inputs.py and the examples own_replay (poe-game) and replay_terrain (instance-server).

Usage: first_divergence.py <session dir> [--out DIR] [--config server.toml] [--seg N] [--hints] [--all]
  --out     work dir (default runtime/first-divergence/<session name>)
  --config  the server config the session ran with (default modules/server/config/server.toml;
            a game-test run dir has its own server.toml)
  --seg N   only segment N (an area visit)
  --hints   let the replay use the client's logged plans (hides path search differences)
  --all     no --first: the whole segment's counts and the first --show differences
  --no-fail exit 0 also when a segment diverges (a game test's `after` report)
Terrain dumps are cached in dumps/<version>/replay/. Exit 1 when a segment diverges."""
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVER = os.path.join(ROOT, "modules", "server")
EX = os.path.join(SERVER, "target", "release", "examples")
VERSION = "0.5.5h"


def opt(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    args = [a for i, a in enumerate(sys.argv[1:], 1)
            if not a.startswith("--") and sys.argv[i - 1] not in ("--out", "--config", "--seg")]
    if len(args) != 1:
        print(__doc__)
        return 2
    sess = os.path.abspath(args[0])
    name = os.path.basename(sess.rstrip("/"))
    out = os.path.abspath(opt("--out", os.path.join(ROOT, "runtime", "first-divergence", name)))
    config = os.path.abspath(opt("--config", os.path.join(SERVER, "config", "server.toml")))
    dumps = os.path.join(ROOT, "dumps", VERSION, "replay")
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if re.fullmatch(r"seg\d+\..*|inputs\.json", f):
            os.remove(os.path.join(out, f))
    b = run(["cargo", "build", "--release", "-q", "-p", "poe-game", "--example", "own_replay",
             "-p", "instance-server", "--example", "replay_terrain"], cwd=SERVER)
    if b.returncode:
        print(b.stderr[-3000:])
        return 2
    # The skill ids come with the first area's terrain; the trace needs them to name 0x1c8 kinds.
    t = run([sys.executable, os.path.join(ROOT, "scripts/re/movement_replay_trace.py"), sess, out])
    metas = sorted(f for f in os.listdir(out) if re.fullmatch(r"seg\d+\.meta", f))
    if not metas:
        print(t.stdout + t.stderr)
        print("no segment with an area: nothing to replay")
        return 2
    terrains, skills = {}, None
    for m in metas:
        h, seed, _ = open(os.path.join(out, m)).read().split()
        if (h, seed) in terrains:
            continue
        r = run([os.path.join(EX, "replay_terrain"), h, seed, dumps, "--config", config], cwd=ROOT)
        if r.returncode:
            print(f"{m}: no terrain for area {h} seed {seed}: {r.stderr.strip()[-300:]}")
            terrains[(h, seed)] = None
            continue
        area, *ids = r.stdout.split()
        ids = dict(i.split("=") for i in ids)
        skills = skills or ",".join([ids["move"], ids["interact"], *ids["roll"].split(",")])
        terrains[(h, seed)] = os.path.join(dumps, f"{area}_{seed}")
    t = run([sys.executable, os.path.join(ROOT, "scripts/re/movement_replay_trace.py"), sess, out, "--skills", skills])
    segs = {}
    for line in t.stdout.splitlines():
        if mm := re.match(r"seg(\d+): (.*)", line):
            segs[int(mm[1])] = mm[2]
    i = run([sys.executable, os.path.join(ROOT, "scripts/re/movement_own_inputs.py"), sess, os.path.join(out, "inputs.json")])
    if i.returncode:
        print(i.stderr[-2000:])
        return 2
    print(f"session {name}: {len(segs)} segments, skills {skills}; work dir {out}")
    diverged = False
    only = opt("--seg")
    for n, desc in sorted(segs.items()):
        if only is not None and n != int(only):
            continue
        meta = os.path.join(out, f"seg{n}.meta")
        if not os.path.exists(meta):
            print(f"== seg{n}: {desc}")
            continue
        h, seed, off = open(meta).read().split()
        base = terrains.get((h, seed))
        print(f"== seg{n}: area {os.path.basename(base) if base else h} seed {seed}, log offset {off}")
        if not base:
            continue
        cmd = [os.path.join(EX, "own_replay"), os.path.join(out, "inputs.json"), os.path.join(out, f"seg{n}.tsv"),
               base + ".pwg", off, "--skills", skills, "--objects", base + ".objects"]
        if "--hints" not in sys.argv:
            cmd.append("--no-hints")
        if "--all" not in sys.argv:
            cmd.append("--first")
        r = run(cmd, cwd=ROOT)
        text = r.stdout + (r.stderr[-2000:] if r.returncode else "")
        open(os.path.join(out, f"seg{n}.report.txt"), "w").write(text)
        lines = text.splitlines()
        print("\n".join(lines[:60]))
        if len(lines) > 60:
            print(f"  ... {len(lines) - 60} more lines in {out}/seg{n}.report.txt")
        diverged |= "FIRST DIVERGENCE" in text or r.returncode != 0
    return 1 if diverged and "--no-fail" not in sys.argv else 0


sys.exit(main())

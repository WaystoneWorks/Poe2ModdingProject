#!/usr/bin/env python3
"""Turns one private session (our server's movement trace and the client's poe-hook.log with
`POE_HOOK_MOVEMENT_LOG=1`) into the two files `own_replay` reads, so a user's game test replays
offline like an official capture (docs/protocol/movement.md, Movement trace).

Usage: movement_session_replay.py TRACE PORT POE_HOOK_LOG OUT_DIR
Writes OUT_DIR/inputs.json (the client's inputs, each at the tick that handled it: the first `tick`
line logged strictly later, or for a direction the tick of the server's 0x64 that answered it) and OUT_DIR/seg.tsv (the client's logged grid, LINE and PATHPLAN per frame,
and what our server sent as the "official" M and A rows; log frame = server tick, offset 0). Use the log's last `frame #1` block (one session).
Then: own_replay OUT_DIR/inputs.json OUT_DIR/seg.tsv GRIDS 0 --roll-skill 1
"""
import json, os, re, sys

FR = re.compile(r"frame #(\d+) dt=[\d.]+ world \(\S+, \S+\) step \(\S+, \S+\) grid \((\d+), (\d+)\)")
LI = re.compile(r"LINE frame=(\d+) s=(-?\d+),(-?\d+) p=(-?[\d.]+),(-?[\d.]+) .*?e=(-?\d+),(-?\d+) cur=(-?\d+),(-?\d+) flag=\d swap=(\d).*? len=([\d.]+) .*? acc=(-?[\d.]+)")
PP = re.compile(r"PATHPLAN #\d+ frame=(\d+) goal=(-?\d+),(-?\d+) start=(-?\d+),(-?\d+).*? path=(.*)$")
NUM = lambda s, k: int(re.search(rf"\b{k}: (-?\d+)", s)[1])


def inputs(trace, port):
    out, pending = [], []
    for line in open(trace):
        f = line.rstrip("\n").split("\t")
        if len(f) < 4 or f[1] != port:
            continue
        k, body, at, ms = f[2], f[3], None, float(f[0])
        if k == "tick":
            for v in pending:
                if v["f"] < ms:
                    v["f"] = int(body)
            pending = [v for v in pending if isinstance(v["f"], float)]
            continue
        n = len(out)
        if False:
            pass
        elif k == "in-MoveDirection":
            op = "wasd"
            out.append({"f": at, "op": op, "x": NUM(body, "x"), "y": NUM(body, "y"),
                        **({"cursor": True} if body.startswith("CursorDirection") else {})})
        elif k == "in-UseSkill":
            v = {"f": at, "op": "use_skill"}
            for key in ("skill", "flags", "unk", "target_flags", "x", "y"):
                v[key] = NUM(body, key)
            m = re.search(r"entity: Some\((\d+)\)", body)
            if m:
                v["entity"] = int(m[1])
            out.append(v)
        elif k == "in-UpdateSkillTarget":
            out.append({"f": at, "op": "update_target", "x": NUM(body, "x"), "y": NUM(body, "y"), "skill": NUM(body, "skill")})
        elif k == "in-SkillInputEnd":
            out.append({"f": at, "op": "input_end"})
        elif k == "in-SprintInput":
            out.append({"f": at, "op": "sprint", "held": "held: true" in body})
        elif k == "in-SkillReleased":
            out.append({"f": at, "op": "released", "skill": NUM(body, "skill"), "flag": NUM(body, "flag")})
        elif k == "in-AimTarget" and body.startswith("AimMode"):
            out.append({"f": at, "op": "aim_mode", "mode": NUM(body, "mode")})
        elif k == "in-StanceRequest":
            out.append({"f": at, "op": "stance_request", "value": NUM(body, "value")})
        if len(out) > n:
            out[-1]["f"] = ms
            pending.append(out[-1])
    out = [v for v in out if isinstance(v["f"], int)]
    # The arrival time does not decide the tick (an input logged just before a tick line can still
    # miss it): a direction the server answered with a 0x64 the same way within 2 ticks, before the
    # next direction, was handled at that 0x64's tick.
    rows = server_rows(trace, port)
    sign = lambda v: (v > 0) - (v < 0)
    acks = sorted((r[0], sign(int(r[4])), sign(int(r[5]))) for r in rows if r[3] == "M")
    # An admin teleport (our server's 0x64 (1,0) then (0,0) on one cell in one tick) is replayed
    # as one, at its tick.
    for r, n in zip(rows, rows[1:]):
        if r[3] == n[3] == "M" and r[0] == n[0] and r[4:6] == ("1", "0") and n[4:6] == ("0", "0"):
            out.append({"f": r[0], "op": "teleport", "x": int(r[6]), "y": int(r[7])})
    dirs = [v for v in out if v["op"] == "wasd"]
    for v, nxt in zip(dirs, dirs[1:] + [None]):
        want = (sign(v["x"]), sign(v["y"]))
        t = next((a for a, *d in acks if v["f"] <= a <= v["f"] + 2 and tuple(d) == want), None)
        if t is not None and (nxt is None or t <= nxt["f"]):
            v["f"] = t
    return sorted(out, key=lambda v: v["f"])


def server_rows(trace, port):
    """What our server sent in the session: `0x64` as M, action starts as A (all rolls: skill 1)."""
    rows, tick = [], 0
    for line in open(trace):
        f = line.rstrip("\n").split("\t")
        if len(f) < 4 or f[1] != port:
            continue
        if f[2] == "tick":
            tick = int(f[3])
        elif f[2] == "out-dir":
            rows.append((tick, 9, 0, "M", *f[3:7]))
        elif f[2] == "out-start":
            rows.append((tick, -1, 0, "A", "roll" if f[7] == "0x1" else "other", *f[3:7]))
    return rows


def log_rows(log):
    blocks = []
    for line in open(log, errors="replace"):
        m = FR.search(line)
        if m:
            if m[1] == "1" or not blocks:
                blocks.append([])
            blocks[-1].append((int(m[1]), 99, 2, "G", m[2], m[3]))
            continue
        if not blocks:
            continue
        m = LI.search(line)
        if m:
            c, e, q = (m[8], m[9]), (m[6], m[7]), (m[4], m[5])
            if m[10] == "1":
                c, e, q = c[::-1], e[::-1], q[::-1]
            blocks[-1].append((int(m[1]), 99, 1, "L", m[2], m[3], *c, *e, *q, m[11], m[12]))
            continue
        m = PP.search(line)
        if m:
            blocks[-1].append((int(m[1]), 99, 0, "P", m[2], m[3], m[4], m[5], *m[6].split()))
    return sorted(blocks[-1], key=lambda r: r[:3])


def main(trace, port, log, out):
    os.makedirs(out, exist_ok=True)
    ins = inputs(trace, port)
    with open(os.path.join(out, "inputs.json"), "w") as f:
        json.dump(ins, f)
    rows = sorted(log_rows(log) + server_rows(trace, port), key=lambda r: r[:3])
    with open(os.path.join(out, "seg.tsv"), "w") as f:
        for r in rows:
            f.write(" ".join(map(str, r)) + "\n")
    print(f"{len(ins)} inputs, {len(rows)} log rows (frames {rows[0][0]}..{rows[-1][0]}) -> {out}")


main(*sys.argv[1:5])

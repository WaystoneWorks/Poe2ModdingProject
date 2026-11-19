#!/usr/bin/env python3
"""The client's inputs of an official capture, each with the frame the official server answered it
in, for the end-to-end check: examples/own_replay feeds them to our server and our messages to a
client model. An input is answered in the batch of its first reply; one without a reply (a stop the
server does not answer) in the frame it was sent.
A private session also gets our server's teleports of the player (`op: teleport`).
Usage: movement_own_inputs.py <session dir> <out.json>"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import movement_fixtures as mf
import movement_sequences as ms

msgs = ms.load(ms.resolve(sys.argv[1]))
replies = [q for q in msgs if q.dir == "in" and q.d and q.op in mf.REPLY_OPS]
out, used, unanswered = [], set(), 0
for m in msgs:
    k = mf.key_input(m)
    # Cursor aims too (key episodes drop them): their echo 0x1dc turns the player (the facing a roll
    # starts with).
    if k is None and m.dir == "out" and m.op == 0x62 and m.d and m.d.get("mode") == 2:
        k = mf.to_input(m)
    if not k or k["op"] in ("pause", "unsupported"):
        continue
    frame = None
    for q in replies:
        if q.i <= m.i or q.i in used or q.op not in mf.PAIR.get(m.op, ()):
            continue
        if q.frame > m.frame + 3:
            break
        if m.op == 0x63:
            want = (m.d["x"], m.d["y"])
            ln = (want[0] ** 2 + want[1] ** 2) ** 0.5 or 1.0
            if (q.d["dx"], q.d["dy"]) not in (want, (int(want[0] * 550 / 180), int(want[1] * 550 / 180)),
                                              (int(want[0] * 550 / ln), int(want[1] * 550 / ln))):
                continue
        frame = q.frame
        used.add(q.i)
        break
    unanswered += frame is None
    out.append(dict(f=frame if frame is not None else m.frame, sent=m.frame, **k))
    if frame is None and k["op"] == "wasd" and (k["x"], k["y"]) != (0, 0):
        out[-1]["late"] = True
# A vector the official server did not answer was replaced by the next one before it ran.
for n, r in enumerate(out):
    if r.pop("late", False):
        nxt = next((o for o in out[n + 1:] if o["op"] == "wasd" and not o.get("late")), None)
        if nxt and nxt["f"] <= r["f"] + 3:
            r["f"] = nxt["f"]
# A zero vector sent with the key's release arrives with it: the sprint's end answers it a frame
# late (seg2 f689).
released = {r["sent"]: r["f"] for r in out if r["op"] == "sprint" and not r["held"]}
for r in out:
    if r["op"] == "wasd" and (r["x"], r["y"]) == (0, 0) and r["sent"] in released:
        r["f"] = released[r["sent"]]
    del r["sent"]
# A private session: our server's teleports (warps, respawns, admin teleports) of the player, a
# 0x64 with a vector then a zero one on the same cell in the same or next frame (as scripts/re/snaps.py).
acks = [q for q in msgs if q.dir == "in" and q.op == 0x64 and q.d]
if acks:
    me = collections.Counter(q.d["ent"] for q in acks).most_common(1)[0][0]
    acks = [q for q in acks if q.d["ent"] == me]
    for q, z in zip(acks, acks[1:]):
        if (q.d["dx"], q.d["dy"]) != (0, 0) and (z.d["dx"], z.d["dy"]) == (0, 0) \
                and (q.d["gx"], q.d["gy"]) == (z.d["gx"], z.d["gy"]) and z.frame - q.frame <= 1:
            out.append(dict(f=q.frame, op="teleport", x=q.d["gx"], y=q.d["gy"]))
out.sort(key=lambda r: r["f"])
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "inputs,", unanswered, "unanswered")

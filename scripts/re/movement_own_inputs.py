#!/usr/bin/env python3
"""The client's inputs of an official capture, each with the frame the official server answered it
in, for the end-to-end check: examples/own_replay feeds them to our server and our messages to a
client model. An input is answered in the batch of its first reply; one without a reply (a stop the
server does not answer) in the frame it was sent.
Usage: movement_own_inputs.py <session dir> <out.json>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import movement_fixtures as mf
import movement_sequences as ms

msgs = ms.load(ms.resolve(sys.argv[1]))
replies = [q for q in msgs if q.dir == "in" and q.d and q.op in mf.REPLY_OPS]
out, used, unanswered = [], set(), 0
for m in msgs:
    k = mf.key_input(m)
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
    out.append(dict(f=frame if frame is not None else m.frame, **k))
    if frame is None and k["op"] == "wasd" and (k["x"], k["y"]) != (0, 0):
        out[-1]["late"] = True
# A vector the official server did not answer was replaced by the next one before it ran.
for n, r in enumerate(out):
    if r.pop("late", False):
        nxt = next((o for o in out[n + 1:] if o["op"] == "wasd" and not o.get("late")), None)
        if nxt and nxt["f"] <= r["f"] + 3:
            r["f"] = nxt["f"]
out.sort(key=lambda r: r["f"])
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "inputs,", unanswered, "unanswered")

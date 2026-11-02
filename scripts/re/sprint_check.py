#!/usr/bin/env python3
"""Checks the server's sprint replies in a DLL session against the stream rules.

Rules (docs/protocol/movement.md "Sprint stream", "End of sprint", "Coasting after a sprint"):
  - no `0x64` between the sprint start (`is_sprinting=1`) and the reply to the first `0x63` sent
    from 3 frames before it on;
  - from that reply on, one `0x64` per frame, vector length 549-550, until the frame before the
    sprint-off batch;
  - a new `0x63` direction shows in a `0x64` within `--slack` frames (unless a newer `0x63` came);
  - the sprint-off batch (`is_sprinting=0`) at roll + 35 frames at the earliest (a note, not a
    failure: one official no-stream sprint ended at + 34);
  - what follows the sprint-off batch is printed (unscaled `0x64`, `(0, 0)`).
Frames are counted from the ticks the client received, so official sessions (network latency)
need `--slack 3`; a local server answers in the next frame (default 1).

Usage: sprint_check.py <session folder | packets.jsonl> [--slack N] [--verbose]
Prints one block per sprint and `sprint-check: N sprints, M rule failures`. Analysis only.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import movement_sequences as ms  # noqa: E402


def angle(a, b):
    """Angle in degrees between two vectors."""
    d = math.degrees(math.atan2(a[1], a[0]) - math.atan2(b[1], b[0]))
    return abs((d + 180) % 360 - 180)


def main():
    argv = sys.argv[1:]
    slack = 1
    if "--slack" in argv:
        i = argv.index("--slack")
        slack = int(argv[i + 1])
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    verbose = "--verbose" in argv
    path = args[0]
    if os.path.isdir(path):
        path = os.path.join(path, "packets.jsonl")
    msgs = ms.load(path)
    pe = ms.player_entity(msgs)
    k = ms.K_SPRINTING

    def stat(m, v):
        return m.dir == "in" and m.op == 0x1D3 and m.d and m.d.get("ent") == pe and dict(m.d["stats"]).get(k) == v

    ons = [m for m in msgs if stat(m, 1)]
    offs = [m for m in msgs if stat(m, 0)]
    fails = 0
    for n, s in enumerate(ons, 1):
        e = next((x for x in offs if x.i > s.i), None)
        if e is None:
            print(f"sprint {n}: on f{s.frame}, no sprint-off")
            fails += 1
            continue
        # The roll's Move/roll 0x1c8 before the sprint (t0).
        roll = next((x for x in reversed(msgs[:s.i]) if x.dir == "in" and x.op == 0x1C8 and x.d and x.d.get("ent") == pe), None)
        t0 = roll.frame if roll else None
        window = [x for x in msgs[s.i:e.i + 40] if x.frame <= e.frame + 3]
        before = [x for x in msgs[max(0, s.i - 80):s.i] if x.frame >= s.frame - 3]
        ins = [x for x in before + window if x.dir == "out" and x.op == 0x63]
        mv = [x for x in window if x.dir == "in" and x.op == 0x64 and x.d.get("ent") == pe]
        keys_up = [x for x in msgs[s.i - 40:e.i + 40] if x.dir == "out" and x.op in (0x2E6,)]
        bad = []
        first63 = ins[0] if ins else None
        stream = [x for x in mv if x.frame <= e.frame]
        if first63 is None:
            if stream:
                bad.append(f"0x64 without a 0x63 after the start (f{stream[0].frame})")
        else:
            early = [x for x in stream if x.frame < first63.frame]
            if early:
                bad.append(f"0x64 before the reply to the first 0x63 (f{early[0].frame}, 0x63 in f{first63.frame})")
            per = {}
            for x in stream:
                per.setdefault(x.frame, []).append(x)
            if stream:
                f_from = stream[0].frame
                gaps = [f for f in range(f_from, e.frame + 1) if f not in per]
                dup = [f for f, v in per.items() if len(v) > 1]
                if gaps:
                    bad.append(f"frames without a 0x64: {gaps[:10]}")
                if dup:
                    bad.append(f"frames with two 0x64: {dup[:10]}")
                lens = sorted({round(math.hypot(x.d["dx"], x.d["dy"])) for x in stream if x.frame < e.frame})
                if any(abs(v - 550) > 1 for v in lens):
                    bad.append(f"stream vector lengths {lens}")
            else:
                bad.append("a 0x63 after the start but no stream")
            # Each 0x63 sets the direction of the next frame's 0x64.
            for c in ins:
                if c.frame >= e.frame or (c.d["x"], c.d["y"]) == (0, 0):
                    continue
                nxt = [x for x in stream if c.frame < x.frame <= c.frame + slack]
                newer = next((y for y in ins if y.i > c.i), None)
                if newer is not None:
                    nxt = [x for x in nxt if x.i < newer.i or x.frame <= newer.frame]
                if nxt and not any(angle((c.d["x"], c.d["y"]), (x.d["dx"], x.d["dy"])) <= 1.0 for x in nxt):
                    if newer is None or newer.frame > c.frame + slack:
                        got = " ".join(f"({x.d['dx']},{x.d['dy']})" for x in nxt)
                        bad.append(f"0x63 ({c.d['x']},{c.d['y']}) f{c.frame} not followed within {slack}: {got}")
        if t0 is not None and e.frame - t0 < 35:
            print(f"    note: sprint off at t0+{e.frame - t0} (< 35)")
        after = [x for x in mv if x.frame > e.frame]
        unscaled = [x for x in after if 0 < math.hypot(x.d["dx"], x.d["dy"]) < 540]
        print(f"sprint {n}: roll t0=f{t0}, on t0+{s.frame - t0 if t0 is not None else '?'}, off t0+{e.frame - t0 if t0 is not None else '?'}; "
              f"0x63 after the start: {len(ins)} (first f{first63.frame if first63 else '-'}), stream {len(stream)} "
              f"from f{stream[0].frame if stream else '-'}; after off: "
              + ", ".join(f"f+{x.frame - e.frame} ({x.d['dx']},{x.d['dy']})" for x in after[:4]))
        if verbose:
            for x in sorted(ins + [x for x in keys_up if s.frame - 30 <= x.frame <= e.frame + 3], key=lambda m: m.i):
                print(f"    f{x.frame - (t0 or 0):+d} {ms.fmt(x)[:120]}")
        if stream and unscaled and unscaled[0].frame != e.frame + 1:
            print(f"    note: first unscaled 0x64 at off+{unscaled[0].frame - e.frame}")
        for b in bad:
            print(f"    FAIL {b}")
        fails += len(bad)
    print(f"sprint-check: {len(ons)} sprints, {fails} rule failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

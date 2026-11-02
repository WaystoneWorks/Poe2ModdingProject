#!/usr/bin/env python3
"""Official 0x2f4 tick timing: body sizes, rate, spacing, 0x2f5 count and stall catch-up.

Usage: python3 scripts/re/tick_timing.py [packets.jsonl ...]
Default: every dumps/0.5.5e.hotfix1/captures/official/*/packets.jsonl.
Times are the DLL's receive times (ms). Lag = (t - t0) - 33 * i within one area
(segments split at gaps > 2 s). A stall line is (gap ms, ticks in the burst right after,
lag before, lag 40 ticks later): equal lags mean the server sent every missed frame.
"""
import collections
import glob
import json
import statistics
import sys

FRAME_MS = 33


def ticks(path):
    ts, lens, f5 = [], collections.Counter(), 0
    for line in open(path, encoding="utf-8"):
        try:
            p = json.loads(line)
        except ValueError:
            continue
        if p.get("chan") != "instance" or p.get("dir") != "in":
            continue
        op = p["op"].lower()
        if op == "0x02f4":
            ts.append(p["t"])
            lens[p["len"]] += 1
        elif op == "0x02f5":
            f5 += 1
    return ts, lens, f5


def main():
    paths = sys.argv[1:] or sorted(glob.glob("dumps/0.5.5e.hotfix1/captures/official/*/packets.jsonl"))
    for path in paths:
        name = path.split("/")[-2]
        ts, lens, f5 = ticks(path)
        if len(ts) < 2:
            print(f"{name}: no ticks")
            continue
        gaps = sorted(b - a for a, b in zip(ts, ts[1:]))
        rate = (len(ts) - 1) / ((ts[-1] - ts[0]) / 1000)
        print(f"{name}: ticks {len(ts)} body sizes {dict(lens)} 0x2f5 {f5} rate {rate:.3f}/s "
              f"gap median {statistics.median(gaps)} p5 {gaps[len(gaps)//20]} p95 {gaps[19*len(gaps)//20]}")
        segs = [[ts[0]]]
        for a, b in zip(ts, ts[1:]):
            if b - a > 2000:
                segs.append([])
            segs[-1].append(b)
        for s in segs:
            if len(s) < 300:
                continue
            lag = [(t - s[0]) - FRAME_MS * i for i, t in enumerate(s)]
            stalls = []
            for i in range(1, len(s)):
                if s[i] - s[i - 1] >= 100:
                    j = i
                    while j + 1 < len(s) and s[j + 1] - s[j] <= 3:
                        j += 1
                    stalls.append((s[i] - s[i - 1], j - i + 1, lag[i - 1], lag[min(len(s) - 1, i + 40)]))
            print(f"  area: ticks {len(s)} mean {(s[-1]-s[0])/(len(s)-1):.4f} ms "
                  f"lag end {lag[-1]} stalls {stalls[:8]}")


if __name__ == "__main__":
    main()

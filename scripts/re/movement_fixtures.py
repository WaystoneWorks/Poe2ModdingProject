#!/usr/bin/env python3
"""Builds the replay fixtures of `modules/server/crates/poe-game/tests/fixtures/` from official captures (WP2.2).

A fixture is a short window of one capture, reduced to *movement* messages of the local player:
the client inputs and the server replies, as semantic events (the names of
`poe_game::movement::MoveEvent`), with frame numbers relative to the first input. No account
names, chat or other entities' messages are kept. Captures stay in `dumps/` (git-ignored); only
these derived files are committed.

Frame model (docs/protocol/movement.md): a message that arrives after `n` ticks is in frame `n`.
The server processes an input in the tick that emits the batch with the first reply, so an input
`arrives` one frame before its first reply: `arrive = first_reply_frame - 1`, never before the
previous input. The replay submits inputs at `arrive` and expects each reply at its own frame.

Usage:
  movement_fixtures.py show  <session> --from F --to F [--track] [--drop-aim]
                                                            print the window as fixture JSON
  movement_fixtures.py build [--out DIR]                    write all PRESETS (needs the dumps)

Needs `GameFiles/poe-hook-data/stats.tsv` (cargo xtask dll-data) to name stats; analysis only.

Notes (WP2.1b): `action_start` carries the 1c8 flags (the 0x1a5 flags plus 0x10 for a start an
input caused; a server-issued restart has the last request's flags without it). Sprint replies
of `0x63` are matched with the vector normalised to length 550 and truncated (and with the
older x 550/180).
"""

import argparse
import bisect
import collections
import json
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import movement_sequences as ms  # noqa: E402

OUT_DEFAULT = os.path.join(ms.ROOT, "modules", "server", "crates", "poe-game", "tests", "fixtures")

NEW = "2026-10-20_18-41-14_336"

# name -> (session, first frame, last frame, description[, drop aim inputs[, options]]). Frames
# are the capture's own. Options: `shift` {capture frame of an input: frames to arrive later}.
PRESETS = {
    "wasd_start_turn_stop": (
        "2026-10-14_22-23-02_336", 1352, 1373,
        "WASD start, two turns and stop, with one aim input per frame echoed (all 16)"),
    "tap_roll_while_walking": (
        "2026-10-14_22-23-02_336", 1081, 1106,
        "walk, tap-roll (Space released 4 frames in), steering by 0x1a8, WASD during the roll, "
        "roll end at t0+16; aims during the roll are not echoed"),
    "tap_rolls_chained": (
        "2026-10-14_22-23-02_336", 1081, 1135,
        "two tap rolls, the second 30 frames after the first started"),
    "sprint_hold_release": (
        "2026-10-17_15-28-54_340", 1098, 1200,
        "roll with Space held: sprint at t0+15, roll end t0+30, must_sprint off t0+35, a 0x64 per "
        "frame from the first WASD vector after the sprint start, scaled; Space released"),
    "sprint_ended_by_attack": (
        "2026-10-14_22-23-02_336", 2340, 2382,
        "a short sprint ended by an attack in the same frame as the key release "
        "(aim inputs dropped: aims are mostly not echoed while an attack runs)", True),
    # ---- 2026-10-20 session (gap-targeted, WP2.1b) -------------------------------------------
    "standing_tap_roll": (
        NEW, 510, 550,
        "roll from standing (no WASD), Space released 7 frames after the press: the roll batch "
        "is the same as when walking, steering by 0x1a8, end at t0+16, no 0x64 at any time",
        False, {"track": True}),
    "standing_hold_sprint_cursor_follow": (
        NEW, 1128, 1175,
        "roll from standing with Space held: sprint at t0+15, then the client sends a 0x63 per "
        "frame towards the cursor (no WASD) and the server streams 0x64 scaled to length 550; "
        "roll end t0+30, must_sprint off t0+35"),
    "chained_rolls_during_a_roll": (
        NEW, 1568, 1650,
        "roll (press and release in one frame, after a pause), a roll asked for 9 frames later "
        "(tap, dropped), one at 28 frames (tap, starts at t0+30), one at 31 frames (starts at once)"),
    "walk_tap_roll_then_turn": (
        NEW, 2452, 2500,
        "WASD walk, tap roll (7 frames), WASD turn at t0+15 answered at once, stop; the 0x64 "
        "after the roll"),
    "sprint_wasd_released_then_space_up": (
        NEW, 1720, 1832,
        "roll with Space held while walking; WASD vectors during and after the roll; WASD keys "
        "released while Space is still down (the client then sends the cursor direction, not "
        "(0, 0)); Space released, 0x64 scaled then unscaled, (0, 0) after; the client's walk "
        "has ended with the sprint and it coasts 30 frames, about 18 cells, along the last "
        "direction ('track', compared from the sprint-off frame on)",
        False, {"track": True, "track_from": 73}),
    "attack_during_a_tap_roll": (
        NEW, 1930, 1998,
        "tap roll followed by an attack asked for 11 frames in: acked at once, the attack "
        "starts at t0+24, the earlier acks of the repeated attack carry no start",
        True),
    "attack_waits_for_sprint_end": (
        NEW, 4018, 4060,
        "roll with Space held; an attack asked for during the roll is acked at once and starts "
        "with the end of the sprint at t0+35 (must_sprint off, MoveAck, StartAction, sprint "
        "off); cursor-follow 0x63 vectors in between",
        True),
    "attack_while_click_walking": (
        NEW, 3990, 4020,
        "held click walk (repeats every 2 frames) with an attack at f4005: the walk goes on and "
        "the client's step falls to 0.3 of walking 7 frames in, rising again from frame 13 "
        "('track': the action speed factor)",
        True, {"track": True}),
    "attack_ends_sprint_then_walk": (
        NEW, 2322, 2416,
        "walk, roll with Space held into a sprint along the keys, sprint ended by an attack at f2393: the unscaled 0x64 restarts the walk, which "
        "the attack slows to 0.3 from 7 frames in ('track' from the attack on)",
        True, {"track": True, "track_from": 72}),
    # ---- click-to-move mode standing rolls (WP C1, gap #12): 'track' is the client's own path ----
    "click_mode_roll_south": (
        NEW, 3644, 3678,
        "click-to-move mode, standing tap roll (Space 3 frames) with the cursor to the south: the "
        "roll heads where the cursor is at the roll and follows its offsets with the usual lag; "
        "the client's positions ('track') stay within 3 cells of ours",
        True, {"track": True}),
    "click_mode_roll_east": (
        NEW, 3678, 3711,
        "click-to-move mode, standing tap roll (Space 3 frames) with the cursor to the east",
        True, {"track": True}),
    "click_mode_roll_west": (
        NEW, 4177, 4212,
        "click-to-move mode, standing roll (Space 14 frames) with the cursor to the west-north-west "
        "and moving further round",
        True, {"track": True}),
    "click_single": (
        NEW, 3372, 3382,
        "click-to-move: press and release 2 frames later: StartAction Move + UseSkillAck in the "
        "next batch, SkillReleasedAck one batch after the release"),
    "click_held_reaim": (
        NEW, 3322, 3372,
        "held click for 41 frames with the cursor sweeping: a UseSkill repeat (target flags "
        "0x10) every 2 frames, each acked and answered with a StartAction Move; a periodic "
        "StartAction every 15 frames; SkillReleasedAck on release",
        True),
    "held_click_with_rolls": (
        NEW, 3525, 3700,
        "mouse mode: a click held for 4 s; a roll with Space released at t0+19 (sprint cut short, "
        "its end at t0+35), then a tap roll; repeats are acked during the rolls and the walk "
        "resumes with a StartAction at the end of the roll",
        True),
    "stance_to_mouse_mode": (
        NEW, 3284, 3290,
        "input mode toggled to click-to-move: AimMode(0) and the stance request in one frame, "
        "stance 0 one frame later", False, {"stance": True}),
    "stance_to_combat_mode": (
        NEW, 4660, 4666,
        "input mode toggled back to WASD: AimMode(1) and the stance request in one frame, "
        "stance 1 one frame later", False, {"stance": False}),
    # ---- stance at the first skill use in mouse mode (the intro wake-up click; its skill
    # messages are left out with `stance_only`) and at entry --------------------------------
    "stance_first_skill_in_mouse_mode": (
        "2026-10-14_22-13-22_336", 600, 606,
        "first skill use in mouse mode: 0x200 value 4 and AimMode(1) with the click; 0x2a6 0.05 "
        "and stance 1 with the value in the next batch", False,
        {"stance": False, "stance_only": True}),
    "stance_first_skill_merged": (
        "2026-10-14_22-23-02_336", 391, 396,
        "as stance_first_skill_in_mouse_mode; the official delta also carries flag words "
        "(mask 0x1402), the stance and value are the same", False,
        {"stance": False, "stance_only": True}),
    "stance_entry_with_request": (
        "2026-10-14_22-23-02_336", 0, 12,
        "entry: AimMode(1), the stance request value 1 and AimMode(0) at f1; stance 1 with 0x2a6 "
        "0.05 nine frames later, then stance 0 with the value and 0x2a6 0.2 one frame after",
        False, {"stance_only": True}),
    "stance_entry": (
        "2026-10-15_23-03-45_340", 0, 12,
        "entry: AimMode(1) at f1, stance 1 with 0x2a6 0.05 nine frames later", False,
        {"stance_only": True}),
}


def stat_name(k):
    return ms.STAT_NAMES.get(k, f"stat_{k}")


def struct_f32(u):
    return struct.unpack(">f", struct.pack(">I", u))[0]


def to_input(m):
    d = m.d
    if m.op == 0x63:
        return {"op": "wasd", "x": d["x"], "y": d["y"]}
    if m.op == 0x1A5:
        o = {"op": "use_skill", "skill": d["skill"], "flags": d["flags"], "unk": d["u13"],
             "target_flags": d["tf"], "x": d["x"], "y": d["y"]}
        if "target" in d:
            o["entity"] = d["target"]
        return o
    if m.op == 0x1A8:
        return {"op": "update_target", "x": d["x"], "y": d["y"], "skill": d["skill"]}
    if m.op == 0x1AC:
        return {"op": "input_end"}
    if m.op == 0x2E6:
        return {"op": "sprint", "held": bool(d["held"])}
    if m.op == 0x1AD:
        return {"op": "released", "skill": d["skill"], "flag": d["u"]}
    if m.op == 0x62 and d["mode"] == 2:
        return {"op": "aim", "x": d["x"], "y": d["y"]}
    if m.op == 0x62 and d["mode"] in (0, 1):
        return {"op": "aim_mode", "mode": d["mode"]}
    if m.op == 0x200:
        return {"op": "stance_request", "value": d["value"]}
    return None


def player_delta(hexstr):
    """The Player component delta (`poe_proto::entity::PlayerDelta`): mask, then experience
    (`0x1`), flag words (`0x2`), stance (`0x400`) and the `0x1000` byte in this order."""
    b = bytes.fromhex(hexstr)
    if len(b) < 2:
        return {}
    mask, i, out = b[0] | b[1] << 8, 2, {}
    if mask & 0x1:
        i += 4
    if mask & 0x2:
        n = b[i] | b[i + 1] << 8
        i += 2 + 9 * n
    if mask & 0x400:
        out["combat"] = bool(b[i])
        i += 1
    if mask & 0x1000 and i < len(b):
        out["request"] = b[i]
    return out


def to_event(m, buff_base):
    d = m.d
    if m.op == 0x64:
        return {"ev": "move_ack", "dir": [d["dx"], d["dy"]], "cell": [d["gx"], d["gy"]]}
    if m.op == 0x1C8:
        o = {"ev": "action_start", "skill": d["skill"], "flags": d["flags"],
             "cell": [d["gx"], d["gy"]], "target": [d["tx"], d["ty"]]}
        return o
    if m.op == 0x1AE:
        o = {"ev": "skill_ack", "skill": d["skill"], "flags": d["flags"], "unk": d["u13"],
             "target_flags": d["tf"] & ~4, "x": d["x"], "y": d["y"]}
        if "target" in d:
            o["entity"] = d["target"]
        return o
    if m.op == 0x1AF:
        return {"ev": "target_ack", "skill": d["skill"], "x": d["x"], "y": d["y"]}
    if m.op == 0x1B1:
        return {"ev": "input_end_ack"}
    if m.op == 0x1B2:
        return {"ev": "released_ack", "skill": d["skill"], "flag": d["flag"]}
    if m.op == 0x2F9:
        if d.get("comp") != 6:
            return None
        pd = player_delta(d["delta"])
        if not pd:
            return None
        return {"ev": "stance", **pd}
    if m.op == 0x2A6:
        return {"ev": "orientation_lerp", "value": round(d["f32"], 3)}
    if m.op == 0x1CA:
        return {"ev": "action_event"}
    if m.op == 0x1D3:
        return {"ev": "stats", "stats": [[stat_name(k), v] for k, v in d["stats"]]}
    if m.op == 0x1EB:
        o = {"ev": "buff_added", "index": d["index"] - buff_base, "row": d["buff"]}
        if d["flags"] & 2:
            o["fade"] = round(struct_f32(d["f2"]), 3)
        return o
    if m.op == 0x1EC:
        return {"ev": "buff_removed", "index": d["index"] - buff_base}
    if m.op == 0x2E7:
        return {"ev": "sprint", "held": bool(d["held"])}
    if m.op == 0x1DC:
        return {"ev": "aim_echo", "kind": d["kind"], "x": d["x"], "y": d["y"]}
    return None


PAIR = {0x63: (0x64,), 0x1A5: (0x1AE,), 0x1A8: (0x1AF,), 0x1AC: (0x1B1,), 0x2E6: (0x2E7,),
        0x62: (0x1DC,), 0x1AD: (0x1B2,), 0x200: (0x2A6,)}
REPLY_OPS = (0x64, 0x1C8, 0x1AE, 0x1AF, 0x1B1, 0x1B2, 0x1CA, 0x1D3, 0x1EB, 0x1EC, 0x2E7, 0x1DC,
             0x2F9, 0x2A6)
# Option `stance_only`: only the stance messages of a window (the intro wake-up click that
# comes with the first stance request in mouse mode is not a movement sequence).
STANCE_IN, STANCE_OUT = (0x200, 0x62), (0x2A6, 0x2F9)


# Cells per world unit of the client's position log (a cell is 250 / 23 world units).
WORLD_PER_CELL = 250 / 23


def client_track(session, base, lo, hi):
    """The client's own position per frame from the session's `poe-hook.log` (`movement_log`):
    `[frame relative to the first input, x, y]` in cells (cell centre = integer + 0.5), for the
    capture frames `lo..hi` the log has. Frames in which the entity did not move are not logged."""
    path = os.path.join(os.path.dirname(ms.resolve(session)), "poe-hook.log")
    pat = re.compile(r"frame #(\d+) dt=[\d.]+ world \((-?[\d.]+), (-?[\d.]+)\)")
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = pat.search(line)
            if m and lo <= int(m[1]) <= hi:
                out.append([int(m[1]) - base,
                            round(float(m[2]) / WORLD_PER_CELL, 2),
                            round(float(m[3]) / WORLD_PER_CELL, 2)])
    return out


def window(session, lo, hi, name="", desc="", drop_aim=False, opts=None):
    opts = opts or {}
    shift = opts.get("shift", {})
    msgs = ms.load(ms.resolve(session))
    pe = ms.player_entity(msgs)
    only = opts.get("stance_only")
    ins = [m for m in msgs if m.dir == "out" and lo <= m.frame <= hi and to_input(m)
           and not (drop_aim and m.op == 0x62)
           and not (only and (m.op not in STANCE_IN or m.op == 0x62 and m.d["mode"] > 1))]
    outs = [m for m in msgs if m.dir == "in" and lo <= m.frame <= hi + 3 and m.d
            and m.d.get("ent") == pe and m.op in REPLY_OPS and not (drop_aim and m.op == 0x1DC)
            and not (only and m.op not in STANCE_OUT)]
    used, arrive, prev = set(), {}, lo
    for m in ins:
        kinds = PAIR.get(m.op, ())
        if m.op == 0x62 and m.d["mode"] != 2:
            kinds = (0x2F9,)
        want = (m.d.get("x"), m.d.get("y"))
        r = None
        for q in outs:
            if q.i <= m.i or q.i in used or q.op not in kinds or q.frame > m.frame + 3:
                continue
            if m.op == 0x63:
                ln = math.hypot(*want) or 1.0
                sc = (int(want[0] * 550 / 180), int(want[1] * 550 / 180))  # the older rule
                nm = (int(want[0] * 550 / ln), int(want[1] * 550 / ln))  # normalised, truncated
                if (q.d["dx"], q.d["dy"]) not in (want, sc, nm):
                    continue
            if m.op == 0x62 and m.d["mode"] == 2 and (q.d["x"], q.d["y"]) != want:
                continue
            if m.op == 0x62 and m.d["mode"] != 2 and q.op != 0x2F9:
                continue
            r = q
            break
        if r is not None:
            used.add(r.i)
            a = max(prev, r.frame - 1)
        else:
            a = max(prev, m.frame)
        a += shift.get(m.frame, 0)
        arrive[m.i] = a
        prev = a
    base = arrive[ins[0].i] if ins else lo
    buffs = [q.d["index"] for q in outs if q.op == 0x1EB]
    buff_base = min(buffs) if buffs else 0
    inputs = [dict(f=arrive[m.i] - base, **to_input(m)) for m in ins]
    events, first_cell = [], None
    for q in outs:
        e = to_event(q, buff_base)
        if e is None or q.frame - base < 1 or q.frame > hi:
            continue
        events.append(dict(f=q.frame - base, **e))
        if first_cell is None and "cell" in e:
            first_cell = e["cell"]
    extra = {"combat_stance": opts["stance"]} if "stance" in opts else {}
    if opts.get("track"):
        # `base` is the capture frame of fixture frame 0 (the frame the first input arrived in).
        extra["track"] = client_track(session, base, lo, hi)
        if "track_from" in opts:
            # Compare from this fixture frame on, relative to the position there (the terrain
            # of the capture is not in the fixture: a walk that bent around an obstacle before
            # that frame is not part of the check).
            extra["track_from"] = opts["track_from"]
    return {
        **extra,
        "name": name,
        "description": desc,
        "source": os.path.basename(os.path.dirname(ms.resolve(session))),
        "capture_frames": [lo, hi],
        "start_cell": first_cell or [50, 50],
        "inputs": inputs,
        "expect": events,
    }


# ---- episodes: every input sequence of every official session ---------------------------------

EPISODES_DIR = os.path.join(OUT_DEFAULT, "episodes")
# Stats and buff rows the movement simulation sends (`poe_game::locomotion::MoveStat`, the three
# sprint buffs); the captures' other stats and buffs (hits, energy shield, skills) are not part of
# a movement episode.
MOVE_STATS = {
    "is_dodge_rolling", "stun_threshold_+%_final_while_performing_action",
    "virtual_heavy_stun_threshold_+%_final", "virtual_light_stun_threshold_+%_final",
    "sprint_blend_time_override_ms", "is_sprinting", "must_sprint", "all_hits_stun_you",
    "virtual_skill_ignore_namelocking_dynamically", "base_move_speed_+%_from_sprint",
    "movement_velocity_+permyriad",
}
SPRINT_BUFFS = {2758, 2737, 2853}
# Frames without a key input (aims do not count) that end an episode when nothing is held, and
# frames kept after its last input for the replies (sprint end t0+35, roll end t0+30).
EPISODE_GAP, EPISODE_TAIL = 45, 40


def pause_input(m):
    """`0x1ff` PauseRequest (`u8, u8 paused`), not decoded by movement_sequences."""
    if m.dir == "out" and m.op == 0x1FF:
        b = bytes.fromhex(m.hex)
        return {"op": "pause", "paused": bool(b[3])}
    return None


def key_input(m):
    """A client input of an episode: everything `to_input` knows except cursor aims, plus the
    pause request; `0x1aa` (entity target) is kept as `unsupported`."""
    if m.dir != "out":
        return None
    if m.op == 0x1AA:
        return {"op": "unsupported", "opcode": "0x1aa"}
    if m.op == 0x62:
        if m.d and m.d.get("mode") in (0, 1):
            return to_input(m)
        return None
    return pause_input(m) or to_input(m)


def episode_events(outs, base, buff_base):
    events, added = [], set()
    for q in outs:
        e = to_event(q, buff_base)
        if e is None or q.op == 0x1DC:
            continue
        if e["ev"] == "stats":
            e["stats"] = [s for s in e["stats"] if s[0] in MOVE_STATS]
            if not e["stats"]:
                continue
        if e["ev"] == "buff_added":
            if e["row"] not in SPRINT_BUFFS:
                continue
            added.add(e["index"])
        # A buff the episode did not add (the entry buff removed with the first action, buffs
        # of hits and skills) is not a movement message.
        if e["ev"] == "buff_removed" and e["index"] not in added:
            continue
        events.append(dict(f=q.frame - base, **e))
    return events


def area_entries(msgs):
    """Frames where the client entered an area: `0x62` mode 0 and mode 1 in one frame (sent
    after every area load; a toggle sends one mode with `0x200`)."""
    modes = collections.defaultdict(set)
    for m in msgs:
        if m.dir == "out" and m.op == 0x62 and m.d and m.d.get("mode") in (0, 1):
            modes[m.frame].add(m.d["mode"])
    return sorted(f for f, s in modes.items() if s == {0, 1})


def player_by_area(msgs, entries):
    """The local player's entity per area (its id changes with every area): the entity of the
    replies that match the client's own inputs (other players and monsters get `0x64`, `0x1ae`
    and Player deltas too). Returns [(first frame, entity)]."""
    bounds = [msgs[0].frame] + entries
    votes = [collections.Counter() for _ in bounds]
    ins = [m for m in msgs if m.dir == "out" and m.d and m.op in (0x63, 0x1A5)]
    outs = collections.defaultdict(list)
    for q in msgs:
        if q.dir == "in" and q.d and q.op in (0x64, 0x1AE) and "ent" in q.d:
            outs[q.frame].append(q)
    for m in ins:
        want = (m.d.get("x"), m.d.get("y"))
        for f in range(m.frame, m.frame + 3):
            hit = None
            for q in outs.get(f, ()):
                if m.op == 0x63 and q.op == 0x64:
                    ln = math.hypot(*want) or 1.0
                    ok = (q.d["dx"], q.d["dy"]) in (
                        want, (int(want[0] * 550 / 180), int(want[1] * 550 / 180)),
                        (int(want[0] * 550 / ln), int(want[1] * 550 / ln)))
                elif m.op == 0x1A5 and q.op == 0x1AE:
                    ok = q.d.get("skill") == m.d.get("skill") and (q.d.get("x"), q.d.get("y")) == want
                else:
                    ok = False
                if ok:
                    hit = q.d["ent"]
                    break
            if hit is not None:
                votes[bisect.bisect_right(bounds, m.frame) - 1][hit] += 1
                break
    # Areas with no matched input: the entity of the first Player delta after the entry.
    out = []
    for i, b in enumerate(bounds):
        if votes[i]:
            out.append((b, votes[i].most_common(1)[0][0]))
            continue
        nxt = bounds[i + 1] if i + 1 < len(bounds) else 1 << 60
        d = next((q.d["ent"] for q in msgs if b <= q.frame < nxt and q.dir == "in" and q.d
                  and q.op == 0x2F9 and q.d.get("comp") == 6), None)
        out.append((b, d if d is not None else ms.player_entity(msgs)))
    return out


def session_episodes(session):
    msgs = ms.load(ms.resolve(session))
    keys = [(m, key_input(m)) for m in msgs]
    # Inputs in the capture's last frames have no recorded reply.
    end = msgs[-1].frame - 3
    keys = [(m, k) for m, k in keys if k and m.frame <= end]
    # Held state while scanning: an episode does not end while a key, Space or a click is held.
    eps, cur = [], None
    wasd, space, click_until = (0, 0), False, -1
    entries = area_entries(msgs)
    players = player_by_area(msgs, entries)
    entry_set = set(entries)

    def player_at(f):
        return players[bisect.bisect_right([b for b, _ in players], f) - 1][1]

    for m, k in keys:
        # An area entry starts a new episode (new entity, new place; held keys are reset).
        if cur and m.frame in entry_set and cur["lo"] != m.frame:
            eps.append(cur)
            cur = None
            wasd, space, click_until = (0, 0), False, -1
        if cur and m.frame - cur["last"] > EPISODE_GAP and wasd == (0, 0) and not space \
                and m.frame > click_until + EPISODE_GAP:
            eps.append(cur)
            cur = None
        if cur is None:
            cur = {"lo": m.frame, "last": m.frame, "msgs": []}
        cur["msgs"].append((m, k))
        cur["last"] = m.frame
        if k["op"] == "wasd":
            wasd = (k["x"], k["y"])
        elif k["op"] == "sprint":
            space = k["held"]
        elif k["op"] == "use_skill" and k["skill"] == ms.MOVE_SKILL:
            click_until = m.frame + 6
    if cur:
        eps.append(cur)
    # Stance state from the Player deltas, per frame (episodes after the entry start with it).
    stance = []
    for m in msgs:
        if m.dir == "in" and m.op == 0x2F9 and m.d and m.d.get("comp") == 6:
            pd = player_delta(m.d["delta"])
            if "combat" in pd and m.d.get("ent") == player_at(m.frame):
                stance.append((m.frame, pd["combat"]))
    out = []
    for ep in eps:
        lo, hi = ep["lo"], ep["last"] + EPISODE_TAIL
        # Not into the next area.
        hi = min([hi] + [e - 1 for e in entries if e > lo])
        entry = lo in entry_set
        ins = [m for m, _ in ep["msgs"]]
        pe = player_at(lo)
        outs = [q for q in msgs if q.dir == "in" and lo <= q.frame <= hi and q.d
                and q.d.get("ent") == pe and q.op in REPLY_OPS]
        # Arrival frames as in `window`: one frame before the first matching reply (which can
        # be in the input's own frame, f+0).
        used, arrive, prev = set(), {}, lo - 1
        for m, k in ep["msgs"]:
            kinds = PAIR.get(m.op, ())
            if m.op == 0x62:
                kinds = (0x2F9,)
            r = None
            if k["op"] not in ("pause", "unsupported", "aim_mode"):
                want = (m.d.get("x"), m.d.get("y"))
                for q in outs:
                    if q.i <= m.i or q.i in used or q.op not in kinds or q.frame > m.frame + 3:
                        continue
                    if m.op == 0x63:
                        ln = math.hypot(*want) or 1.0
                        sc = (int(want[0] * 550 / 180), int(want[1] * 550 / 180))
                        nm = (int(want[0] * 550 / ln), int(want[1] * 550 / ln))
                        if (q.d["dx"], q.d["dy"]) not in (want, sc, nm):
                            continue
                    r = q
                    break
            if r is not None:
                used.add(r.i)
                a = max(prev, r.frame - 1)
            else:
                a = max(prev, m.frame)
            arrive[m.i] = a
            prev = a
        base = arrive[ins[0].i]
        buffs = [q.d["index"] for q in outs if q.op == 0x1EB and q.d.get("buff") in SPRINT_BUFFS]
        events = episode_events(outs, base, min(buffs) if buffs else 0)
        events = [e for e in events if e["f"] >= 1]
        before = [c for f, c in stance if f < lo and player_at(f) == pe]
        if entry:
            before = []
        elif not before and lo > msgs[0].frame + EPISODE_GAP:
            # Nothing seen yet (the capture started inside an area): a stance request answered
            # in the episode changed the stance, so it was the other one before.
            first = next((m for m in msgs if lo <= m.frame <= hi and m.dir == "in" and m.op == 0x2F9
                          and m.d and m.d.get("comp") == 6
                          and "request" in player_delta(m.d["delta"])), None)
            if first is not None:
                before = [not player_delta(first.d["delta"])["combat"]]
        cell = next((e["cell"] for e in events if "cell" in e), [50, 50])
        # Login (the first episode) or area change: the official entry stance's frame.
        entry_stance = next((e["f"] for e in events if e["ev"] == "stance"), None) \
            if entry or ep is eps[0] else None
        out.append({
            "name": f"{lo}",
            "capture_frames": [lo, hi],
            **({"combat_stance": before[-1]} if before else {}),
            **({"entry_stance_frame": entry_stance} if entry_stance else {}),
            "start_cell": cell,
            "frames": hi - base,
            "inputs": [dict(f=arrive[m.i] - base, **k) for m, k in ep["msgs"]],
            "expect": events,
        })
    return out


def cmd_episodes(a):
    os.makedirs(a.out, exist_ok=True)
    sessions = sorted(os.listdir(os.path.join(ms.CAPS, "official")))
    for session in sessions:
        eps = session_episodes(session)
        path = os.path.join(a.out, session + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"source": session, "episodes": eps}, f, separators=(",", ":"))
            f.write("\n")
        print(f"{session}: {len(eps)} episodes, {sum(len(e['inputs']) for e in eps)} inputs, "
              f"{sum(len(e['expect']) for e in eps)} events, {os.path.getsize(path)} bytes")


def cmd_show(a):
    print(json.dumps(window(a.session, a.start, a.end, drop_aim=a.drop_aim,
                            opts={"track": a.track}), indent=None, separators=(",", ":")).replace("},{", "},\n{"))


def cmd_build(a):
    os.makedirs(a.out, exist_ok=True)
    for name, (session, lo, hi, desc, *opts) in PRESETS.items():
        w = window(session, lo, hi, name, desc, drop_aim=bool(opts and opts[0]),
                   opts=opts[1] if len(opts) > 1 else None)
        path = os.path.join(a.out, name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(w, f, separators=(",", ":"))
            f.write("\n")
        print(f"{path}: {len(w['inputs'])} inputs, {len(w['expect'])} events")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("show")
    p.add_argument("session")
    p.add_argument("--from", dest="start", type=int, required=True)
    p.add_argument("--to", dest="end", type=int, required=True)
    p.add_argument("--track", action="store_true", help="add the client's positions (poe-hook.log)")
    p.add_argument("--drop-aim", action="store_true", help="leave out the aim inputs and echoes")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("episodes", help="write every input sequence of every official session")
    p.add_argument("--out", default=EPISODES_DIR)
    p.set_defaults(fn=cmd_episodes)
    p = sub.add_parser("build")
    p.add_argument("--out", default=OUT_DEFAULT)
    p.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

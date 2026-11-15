"""Find functions whose body changed between two builds although their size did not.

Usage: body_diff.py <old exe> <new exe> <addr_map.tsv> [--names <tsv>] [--out <tsv>]

addr_map.py pairs functions by size, so a patched constant or a changed branch inside an
equal-size function stays `same`. This disassembles every `same` pair and compares the
instructions: mnemonics, registers and immediates must match; a branch or call target inside
the function must sit at the same offset; one into another function must be that function's
mapped address; RIP-relative and image-relative (RVA displacement) data references are not
compared (data moves by section). Output: one row per changed function (old_va, new_va, size, first
differing instruction); `--names` (a TSV `va<TAB>name`) adds names to the console summary.
"""
import argparse
import bisect
import sys

import capstone
from capstone import x86

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pe import Image


def load_map(path):
    rows = []
    for line in open(path):
        f = line.rstrip("\n").split("\t")
        if f[0] == "old_va" or f[1] == "-":
            continue
        rows.append((int(f[0], 16), int(f[1], 16), int(f[2]), int(f[3]), f[4]))
    rows.sort()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("map")
    ap.add_argument("--names")
    ap.add_argument("--out")
    a = ap.parse_args()
    old, new = Image(a.old), Image(a.new)
    rows = load_map(a.map)
    starts = [r[0] for r in rows]
    names = {}
    if a.names:
        for line in open(a.names):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2:
                names[int(f[0], 16)] = f[1]

    def mapped(va):
        i = bisect.bisect_right(starts, va) - 1
        if i < 0:
            return None
        o, n, osz, _, kind = rows[i]
        if va >= o + osz or kind != "same":
            return None
        return n + (va - o)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    lo, hi = old.base, old.base + old.pe.OPTIONAL_HEADER.SizeOfImage

    def ops(ins, fstart, fsize, side):
        out = []
        for op in ins.operands:
            if op.type == x86.X86_OP_IMM:
                v = op.imm
                if lo <= v < hi + 0x1000000:
                    if fstart <= v < fstart + fsize:
                        out.append(("in", v - fstart))
                    else:
                        out.append(("ext", v, side))
                else:
                    out.append(("imm", v))
            elif op.type == x86.X86_OP_REG:
                out.append(("reg", op.reg))
            elif op.type == x86.X86_OP_MEM:
                m = op.mem
                if m.base == x86.X86_REG_RIP or 0x100000 <= m.disp < hi - lo:
                    # RIP-relative, or an image-relative table (RVA + a register holding the base)
                    out.append(("rip",))
                else:
                    out.append(("mem", m.base, m.index, m.scale, m.disp, op.size))
        return out

    def data_start(ins, fstart, fsize, base):
        """Offset of the first switch table inside the function (else its size)."""
        first = fsize
        for x in ins:
            for op in x.operands:
                if op.type != x86.X86_OP_MEM:
                    continue
                m = op.mem
                if m.base == x86.X86_REG_RIP:
                    t = x.address + x.size + m.disp
                elif m.index != 0 and 0x100000 <= m.disp < hi - lo:
                    t = base + m.disp
                else:
                    continue
                if fstart < t < fstart + fsize:
                    first = min(first, t - fstart)
        return first

    changed = []
    n_same = 0
    for o, n, osz, nsz, kind in rows:
        if kind != "same":
            continue
        n_same += 1
        ob, nb = old.read(o, osz), new.read(n, nsz)
        if ob == nb and o == n:
            continue
        oi = list(md.disasm(ob, o))
        ni = list(md.disasm(nb, n))
        # Switch tables inside the function (MSVC puts them after the code): the code is compared
        # up to the first one, the tables as dwords that moved with the function or as equal bytes.
        ds = data_start(oi, o, osz, old.base)
        oi = [x for x in oi if x.address + x.size - o <= ds]
        ni = [y for y in ni if y.address + y.size - n <= ds]
        diff = None
        if len(oi) != len(ni):
            diff = f"instruction count {len(oi)} -> {len(ni)} (code before +{ds:#x})"
        else:
            for x, y in zip(oi, ni):
                if x.mnemonic != y.mnemonic or x.size != y.size:
                    diff = f"+{x.address - o:#x} {x.mnemonic} {x.op_str} -> {y.mnemonic} {y.op_str}"
                    break
                xo, yo = ops(x, o, osz, 0), ops(y, n, nsz, 1)
                if len(xo) != len(yo):
                    diff = f"+{x.address - o:#x} operands"
                    break
                bad = False
                for p, q in zip(xo, yo):
                    if p[0] == "ext" and q[0] == "ext":
                        t = mapped(p[1])
                        if t is not None and t != q[1]:
                            bad = True
                    elif p != q:
                        bad = True
                    if bad:
                        break
                if bad:
                    diff = f"+{x.address - o:#x} {x.mnemonic} {x.op_str} -> {y.mnemonic} {y.op_str}"
                    break
        if not diff and ds < osz:
            delta = n - o
            for k in range(ds, osz - 3, 4):
                a4, b4 = ob[k : k + 4], nb[k : k + 4]
                if a4 != b4 and int.from_bytes(b4, "little") - int.from_bytes(a4, "little") != delta:
                    diff = f"+{k:#x} switch table {a4.hex()} -> {b4.hex()}"
                    break
        if diff:
            changed.append((o, n, osz, diff))
    print(f"{n_same} same-size pairs, {len(changed)} with a changed body")
    for o, n, sz, d in changed[:200]:
        print(f"{o:#x} -> {n:#x} size {sz} {names.get(o, '')}: {d}")
    if a.out:
        with open(a.out, "w") as f:
            f.write("old_va\tnew_va\tsize\tdiff\n")
            for o, n, sz, d in changed:
                f.write(f"{o:#x}\t{n:#x}\t{sz}\t{d}\n")


if __name__ == "__main__":
    main()

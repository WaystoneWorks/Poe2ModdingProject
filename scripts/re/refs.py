"""Direct calls and RIP-relative data references (with the string there) in a range:
refs.py <start_va> <end_va>."""
import sys

import capstone
from capstone import x86

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pe import Image

img = Image()
a, b = int(sys.argv[1], 16), int(sys.argv[2], 16)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True


def text_at(va):
    raw = bytes(img.read(va, 160))
    if len(raw) > 3 and raw[1] == 0 and 32 <= raw[0] < 127:
        t = raw.decode("utf-16le", "ignore").split("\0")[0]
        return "w:" + t if len(t) >= 3 else ""
    t = raw.split(b"\0")[0]
    return "a:" + t.decode("latin1") if len(t) >= 4 and all(32 <= c < 127 for c in t) else ""


for i in md.disasm(bytes(img.read(a, b - a)), a):
    if i.mnemonic == "call" and i.operands[0].type == x86.X86_OP_IMM:
        print(f"{i.address:x} call {i.operands[0].imm:x}")
    for op in i.operands:
        if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
            t = i.address + i.size + op.mem.disp
            print(f"{i.address:x} {i.mnemonic} ref {t:x} {text_at(t)[:70]}")

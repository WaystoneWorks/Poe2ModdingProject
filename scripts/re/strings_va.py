"""Dump every ASCII and UTF-16LE string (4+ chars) outside code sections with its VA:
strings_va.py [out.tsv]  (default runtime/strings.tsv). Lines: va<TAB>a|w<TAB>text."""
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pe import Image

img = Image()
out = open(sys.argv[1] if len(sys.argv) > 1 else "runtime/strings.tsv", "w")
for name, s in img.sections.items():
    if s.Characteristics & 0x20000000:  # executable
        continue
    start, data = img.section(name)
    data = bytes(data)
    for m in re.finditer(rb"[\x20-\x7e]{4,}", data):
        out.write(f"{img.va(start + m.start()):x}\ta\t{m.group().decode()}\n")
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){4,}", data):
        out.write(f"{img.va(start + m.start()):x}\tw\t{m.group().decode('utf-16le')}\n")

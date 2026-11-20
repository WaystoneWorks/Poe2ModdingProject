"""Collect the client function names the docs and the DLL already give, for G1ImportNames.java.

known_names.py [out.tsv]  (default runtime/ghidra-naming/known_names.tsv)

Sources: docs/re/**/*.md, docs/protocol/*.md, and the DLL's ghidra_labels.tsv of every
GameFiles/logs/poe-hook/<session>/ whose poe-hook.log is for the current client build
(version.py). A doc address gets a name only when an identifier in the project's style (contains
`_` or `::`, e.g. `TerrainGen_Construct`) stands right next to it: `Name` (`0x14...`), `Name` 0x14...,
`0x14...` `Name`, or a table row `| 0x14... | Name ...` with one address in its first cell; it
starts upper case (snake_case names are the server's Rust ports). Lines: address<TAB>name<TAB>
sources, one per address and name; G1ImportNames.java resolves sites inside a function and
reports conflicts."""
import glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from version import current_version  # noqa: E402

VERSION = current_version()

IDENT = r"[A-Z][A-Za-z0-9]*(?:(?:_|::)[A-Za-z0-9]+)+"  # client names start upper case; snake_case is our Rust
ADDR = r"(?:0x)?(14[0-9a-f]{7})"
BEFORE = re.compile(r"`(" + IDENT + r")(?:\(\))?`\s*(?:\(|=|at|:)?\s*`?" + ADDR + r"\b")
BEFORE_BARE = re.compile(r"(?<![\w`])(" + IDENT + r")\s*\(\s*`?" + ADDR + r"\b")
AFTER = re.compile(r"\b" + ADDR + r"`?\s*(?:=|is|\(|:)?\s*`(" + IDENT + r")[`(]")
ROW = re.compile(r"^\|\s*`?" + ADDR + r"`?\s*\|\s*`(" + IDENT + r")[`(]")
SKIP = re.compile(r"^(FUN|DAT|LAB|PTR|SUB|thunk_FUN|switchD|caseD)_", re.I)


def doc_names(root):
    out = []
    files = sorted(glob.glob(f"{root}/docs/re/**/*.md", recursive=True) + glob.glob(f"{root}/docs/protocol/*.md"))
    for f in files:
        rel = os.path.relpath(f, root)
        for n, line in enumerate(open(f, encoding="utf-8"), 1):
            found = set()
            m = ROW.match(line)
            if m:
                first_cell = line.split("|")[1]
                if len(re.findall(ADDR, first_cell)) == 1:
                    found.add((m.group(1), m.group(2)))
            for m in BEFORE.finditer(line):
                found.add((m.group(2), m.group(1)))
            for m in BEFORE_BARE.finditer(line):
                found.add((m.group(2), m.group(1)))
            for m in AFTER.finditer(line):
                found.add((m.group(1), m.group(2)))
            for a, name in found:
                if not SKIP.match(name):
                    out.append((a, name, f"{rel}:{n}"))
    return out


def dll_names(root):
    out = []
    for d in sorted(glob.glob(f"{root}/GameFiles/logs/poe-hook/*/")):
        lab, log = os.path.join(d, "ghidra_labels.tsv"), os.path.join(d, "poe-hook.log")
        if not os.path.exists(lab) or not os.path.exists(log):
            continue
        with open(log, encoding="utf-8", errors="replace") as fh:
            head = fh.read(20000)
        if VERSION not in head:
            continue
        for line in open(lab, encoding="utf-8"):
            if line.startswith("#") or "\t" not in line:
                continue
            a, name = line.rstrip("\n").split("\t", 1)
            out.append((a.lower().removeprefix("0x"), name, "dll:" + os.path.basename(d.rstrip("/"))))
    return out


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "runtime/ghidra-naming/known_names.tsv")
    rows = doc_names(root) + dll_names(root)
    by_pair = defaultdict(set)
    for a, name, src in rows:
        by_pair[(a, name)].add("dll" if src.startswith("dll:") else src)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for (a, name), srcs in sorted(by_pair.items()):
            fh.write(f"{a}\t{name}\t{','.join(sorted(srcs))}\n")
    ndoc = sum(1 for r in rows if not r[2].startswith("dll:"))
    print(f"mentions: docs {ndoc}, dll {len(rows) - ndoc}; address-name pairs {len(by_pair)}; addresses {len({a for a, _ in by_pair})} -> {path}")


if __name__ == "__main__":
    main()

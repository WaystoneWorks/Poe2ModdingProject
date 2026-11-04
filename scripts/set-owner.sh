#!/usr/bin/env bash
# Rewrites the GitHub owner of the project's repositories everywhere it is written down, in the
# hub and in every submodule checkout (nested ones too). Shows the diff first; changes nothing
# without --apply.
#
#   scripts/set-owner.sh OWNER            # dry run: list and diff
#   scripts/set-owner.sh OWNER --apply    # write the files (commit them per repository yourself)
#
# What changes (only tracked files, never GameFiles/, runtime/, dumps/ or third_party/):
#   - URLs github.com/<old>/..., raw.githubusercontent.com/<old>/..., api.github.com/repos/<old>/...
#   - repository paths <old>/Poe2...  (docs, comments, launcher texts, mod.toml, templates)
#   - the compiled-in default owner of the launcher (source.rs default_owner!, Settings page,
#     UI mock)
#   - .gitmodules (hub and nested), git dependency URLs (modules/server, modules/mod-sdk, and
#     the Cargo.lock sources), the two JSON schemas' $id, issue-template links, READMEs.
# What stays: licence/copyright lines and mod authors ("<old> and contributors"), the name in
# prose. The script lists what is left so you can decide.
#
# <old> is read from the launcher's default (modules/launcher/src-tauri/src/source.rs).
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
exec python3 -I - "$root" "$@" <<'PY'
import difflib, re, subprocess, sys
from pathlib import Path

root = Path(sys.argv[1])
args = sys.argv[2:]
apply = "--apply" in args
args = [a for a in args if a != "--apply"]
if len(args) != 1 or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", args[0]):
    sys.exit("usage: scripts/set-owner.sh OWNER [--apply]   (OWNER: a GitHub user or organisation name)")
new = args[0]

src = root / "modules/launcher/src-tauri/src/source.rs"
m = re.search(r'macro_rules! default_owner \{\s*\(\) => \{\s*"([^"]+)"', src.read_text()) if src.exists() else None
if not m:
    sys.exit("cannot read the current owner from modules/launcher/src-tauri/src/source.rs (launcher not checked out?)")
old = m.group(1)
if old == new:
    sys.exit(f"the owner is already {new}")

o = re.escape(old)
rules = [
    # URLs
    (re.compile(rf"((?:github\.com|raw\.githubusercontent\.com|api\.github\.com/repos)/){o}(?![A-Za-z0-9_-])"), rf"\g<1>{new}"),
    # repository paths: WaystoneWorks/Poe2Server, git@github.com:WaystoneWorks/Poe2X
    (re.compile(rf"(?<![A-Za-z0-9_-]){o}/(Poe2[A-Za-z]+)"), rf"{new}/\g<1>"),
]
# The one literal that is the default itself.
literal = {
    "modules/launcher/src-tauri/src/source.rs": (re.compile(rf'("){o}(")'), rf"\g<1>{new}\g<2>"),
    "modules/launcher/src/pages/Settings.svelte": (re.compile(rf"(owner: '){o}(')"), rf"\g<1>{new}\g<2>"),
    "modules/launcher/src/lib/mock.ts": (re.compile(rf"(owner: '){o}(')"), rf"\g<1>{new}\g<2>"),
}
skip = ("GameFiles/", "runtime/", "dumps/", "third_party/")

out = subprocess.run(["git", "ls-files", "--recurse-submodules", "-z"], capture_output=True, check=True).stdout
files = [f for f in out.decode().split("\0") if f and not f.startswith(skip)]

changed = []
left = []
for rel in files:
    p = root / rel
    try:
        data = p.read_bytes()
    except OSError:
        continue
    if b"\0" in data or old.encode() not in data:
        continue
    text = data.decode("utf-8", "replace")
    edited = text
    for rx, rep in rules:
        edited = rx.sub(rep, edited)
    if rel in literal:
        rx, rep = literal[rel]
        edited = rx.sub(rep, edited)
    if edited != text:
        changed.append((rel, text, edited))
    for i, line in enumerate(edited.splitlines(), 1):
        if old in line:
            left.append((rel, i, line.strip()[:110]))

total = 0
for rel, a, b in changed:
    n = sum(1 for x, y in zip(a.splitlines(), b.splitlines()) if x != y)
    total += n
    if not apply:
        sys.stdout.writelines(difflib.unified_diff(a.splitlines(True), b.splitlines(True), f"a/{rel}", f"b/{rel}", n=0))
    else:
        (root / rel).write_text(b, newline="")
repos = sorted({("/".join(r.split("/")[:2]) if r.startswith("modules/") else ".") for r, _, _ in changed})
print(f"\n{'changed' if apply else 'would change'} {total} lines in {len(changed)} files: {old} -> {new}")
print("repositories touched (commit in each, submodules first):", ", ".join(repos))
if left:
    print(f"\nstill mentions {old} ({len(left)} lines, left on purpose: licence/author lines and prose):")
    for rel, i, line in left[:40]:
        print(f"  {rel}:{i}: {line}")
    if len(left) > 40:
        print(f"  ... and {len(left) - 40} more")
if not apply:
    print("\nDry run. Add --apply to write.")
PY

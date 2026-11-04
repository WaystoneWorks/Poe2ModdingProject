#!/usr/bin/env python3
"""After the overlay-pages game test: pairs the tour's pages (hook log, `overlay tour: <Page>`)
with the snapshot screenshots of the session, in order, and copies them to
runtime/game-test/overlay-pages/<Page>.png. Fails when a page has no screenshot."""
import pathlib, re, shutil, sys

run, session = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
log = (run / "poe-hook.log").read_text(errors="replace")
pages = re.findall(r"overlay tour: (\w+)", log)
pages = [p for p in pages if p != "done"]
shots = sorted(session.glob("snapshots/*/*.png"), key=lambda p: p.parent.name)
if not pages or len(shots) < len(pages):
    sys.exit(f"{len(pages)} pages in the tour, {len(shots)} screenshots")
out = pathlib.Path("runtime/game-test/overlay-pages")
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)
for page, shot in zip(pages, shots):
    shutil.copy(shot, out / f"{page}.png")
print(f"{len(pages)} pages: " + " ".join(pages))

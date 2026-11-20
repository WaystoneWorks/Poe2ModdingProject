# G1: automated Ghidra naming pass (user, 2026-11-19)

A one-time pass over `/0.5.5h/PathOfExileSteam.exe` so later RE sessions find functions faster. Done by Ghidra scripts (`scripts/re/ghidra/G1*.java`, run through the MCP), never by reading functions one by one. **A name comes only from a reliable source** (RTTI, a unique Function ID match, the docs, the DLL); anything weaker is a tag or a plate comment marked as a hint. Raw output goes to `runtime/ghidra-naming/`; the program is saved after each step; each step reports the function count and how many are still `FUN_` before and after.

1. **RTTI.** From the MSVC RTTI (complete object locators, type descriptors, class hierarchy descriptors): label every vtable with its class, and name each slot function that has no name yet `Class::vf_XX` (existing names are kept). A function shared by unrelated classes stays unnamed.
2. **Libraries.** Statically linked library code (MSVC CRT/STL, compression, crypto, ...) by Function ID and by library-only strings and RTTI namespaces: renamed only on a single-name match, otherwise tagged `lib` and `lib:<name>` so searches can skip it. Counts per library.
3. **Strings.** A function that is the only user of a debug, error or log string gets that string as a `str:` plate-comment hint and the tag `str`; no rename.
4. **Known names.** Every address named in `docs/re/`, `docs/protocol/` and the DLL's `ghidra_labels.tsv` (0.5.5h sessions) is imported as a name. Conflicts (two names for one address, a doc name against an existing Ghidra name) are reported, not overwritten.
5. **Ongoing rule** in [../re/README.md](../re/README.md): every function read during a task is renamed and commented in Ghidra at once, and the project is saved.

Done when steps 1 to 4 are applied and saved, the scripts and results are in [../re/README.md](../re/README.md), and G1 is marked done in [../PLAN.md](../PLAN.md) and `tracker/status.toml`; then this spec is deleted.

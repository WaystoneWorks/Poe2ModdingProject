# Plan: passive tree, ascendancies, weapon-set points, class changer

Step P15 of [../PLAN.md](../PLAN.md). Needs the stat calculator, items and weapon sets ([items-stats.md](items-stats.md)).

## User decisions (2026-11-04)
- The passive tree and ascendancies with **basic stats only** (the same implemented set as items). For a node with a line that is not implemented (Chaos Inoculation-style keystones and the like), the server sends a chat line on allocation, once per line: `The passive you allocated: <passive> has a line that is not implemented: <line>`. Also once at login for nodes already allocated.
- **Ascendancy points come only from the debug command and overlay** for now; trials come later. Choosing an ascendancy goes through the class changer.
- **Refunds are free.**
- **Weapon-set passive points and allocations** are included, with weapon swap (the active set's allocations apply).
- Web admin character page: **editable passive tree for admins**.
- Class changer: keeps level, XP, items and gold; resets the tree, ascendancy and weapon-set allocations and refunds the points; leaves and rejoins the same instance automatically.

## Steps
1. **Data** (`poe-data`): `PassiveSkills.dat` (node id, name, stats and values, keystone, notable, ascendancy, class start, weapon-set flag if any), the tree graph (`Metadata/PassiveSkillGraph.psg`: groups, orbits, connections), `Ascendancy.dat` (class, name, start node). Cross-check the node count and connections against PoB2's tree export for the same version.
2. **RE (Opus)** from C2 and the client: the allocate, refund and reset requests (and their batch "apply" flow if the client queues allocations), the server's reply, how allocations and unspent points are sent at login (the player's passive data), weapon-set allocation messages and the swap's effect, ascendancy choice and how the client shows ascendancy points. Results go to `docs/protocol/passives.md` (new).
3. **Server rules** (`poe-game::passives`): allocations must stay connected to the class start (or the ascendancy start for ascendancy nodes); unspent points per pool (passive, weapon set, ascendancy); free refund of any node that leaves the tree connected; the weapon-set pool's allocations tagged set 1 or set 2 and only the active set's apply in the calculator; point sources: level-ups (P9), and `points` commands until quests exist. The official number of weapon-set points and their source is researched (PoB2's tree data and community sources) and configured, not hardcoded.
4. **Calculator**: node stats into the ModDB through `map.rs` ([stats.md](../architecture/stats.md)); unmapped lines produce the chat line. `stats-check` fixtures with trees included.
   - Switchable nodes (78 in PoB2's 0_5 tree) have other stats per class than `PassiveSkills` says; `stats-check` does not walk them, so this step takes the per-class stats ([stats.md](../architecture/stats.md#rules-the-comparison-needs)).
5. **Class changer** (`class set <class> [ascendancy]`, `ascendancy set <name>`): updates the character's class and ascendancy, clears allocations, refunds points, saves, then transfers the player out and back into the same instance at the same cell (the class is part of the player's AddObject blob, so a fresh entry is needed). Overlay Debug > Character ([overlay.md](overlay.md)).
6. **Commands**: `tree reset [--weaponset 1|2] [--ascendancy]`, `tree allocate <node>` (by name or id, connecting path optional `--path`), `points passive|weaponset|ascendancy add|set <n>`.
7. **Web admin** (admins): Character page **Passives** tab: a canvas of the tree (nodes from the data endpoint `GET /api/v1/data/passive-tree`, allocated nodes highlighted, weapon-set allocations in two colours, ascendancy panel), click to allocate or refund with the same rules, point counters with set fields, `[Reset tree]`. Changes to an online character are applied live. API: `GET/PATCH /api/v1/admin/characters/{id}/passives`.
- Done when: an agent game test allocates nodes through the client's tree UI, refunds one, sees stats change (client = server in the Stats page), allocates weapon-set nodes and swaps sets, picks an ascendancy through `class set`, gets the not-implemented line for a keystone; the web admin edits the tree of an online character; `stats-check` agrees with PoB2 for tree fixtures.

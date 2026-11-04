# Plan: loot drops, ground items, gold, parties and loot allocation

Step P18 of [../PLAN.md](../PLAN.md). Needs monsters ([monsters.md](monsters.md)), items and the mod rolling engine ([items-stats.md](items-stats.md)). Parties were deferred in the old plan "until items exist" and need the G-PARTY capture (a friend answers a party invite and a trade request).

## User decisions (2026-11-04)
- Drops from **game data plus configurable tables**, with defaults from **research**: game data and poe2db for item and mod weights (Mods.dat spawn weights are exact), **community drop-rate studies** for currency and rarity rates, **PoB2's data** for cross-checks. Every number that is not from game data is cited in `docs/research/loot.md` (new).
- Ownership is **official-like**. The game has an in-game loot allocation setting; **the party leader's setting is the party's allocation**.
- **Basic parties** are part of this plan: invite, accept, leave, kick, leader, allocation, shared instances.

## Steps
1. **Research (Sonnet with web search, then Opus to check)**: `docs/research/loot.md` with sources: drops per monster rarity, quantity and rarity scaling (`item_found_quantity`/`rarity` stats), currency drop rates per area level from community datasets, base type drop levels (`BaseItemTypes` DropLevel), rarity chances of dropped equipment, unique drop weighting, gold amounts per area level, uncut gem drop rates and levels. Where sources disagree, list both and pick one with the reason.
2. **Drop tables** in config, data-mod friendly: `config/loot.toml` (loaded with `server.toml`'s data mod layering): per monster rarity the item count, the share of currency, gold, gems and equipment; currency weights; IIQ/IIR application. Defaults from step 1.
3. **Generation**: item level = area level (monster level), base chosen by drop level and weights, rarity rolled with IIR, mods from the P10 rolling engine, uniques by their weights where known; currency by weight; gold amount by level.
4. **RE (Opus)** from C2: the ground item object (AddObject of a world item, its label data), pickup (click and the client's request), the reply and the inventory update, gold pickup, the allocation display (the allocated player's name on the label) and the allocation setting messages; from G-PARTY: party invite, accept, decline, leave, kick, leader change, party member list, the allocation setting sync. Results go to `docs/protocol/items.md` and `docs/protocol/entities.md` (party section).
5. **Ground items**: spawn on kill around the corpse (official scatter pattern; the client's loot filter shows or hides labels on its own), pickup with free inventory space checks, despawn timer, and the item creator's `--ground` and `item random --ground` (P11).
6. **Allocation**: modes as the game's setting offers (free for all, short allocation, permanent allocation; names and timers from the client), read from the party leader's setting; solo players use their own; allocated items can be picked only by their owner until the timer ends.
7. **Parties**: invite, accept and decline, leave, kick, promote; the member list; shared instances (members joining an area go to the party's instance of it); XP split by the official formula (research: PoB2 or community sources) for kills in range.
8. **Commands**: `loot roll`, `party` debug views; overlay Debug > Items (loot roll form) and Players (party state).
- Done when: in agent game tests monsters drop items and gold with rates near the configured tables over 1,000 kills (`loot roll` statistics), items and gold can be picked up, a two-client test (`scripts/test-mp.sh`) forms a party, the leader's allocation setting decides who may pick up, and both members share an instance.

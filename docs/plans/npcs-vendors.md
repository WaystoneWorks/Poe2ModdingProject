# Plan: NPCs and vendors

Step P19 of [../PLAN.md](../PLAN.md). Needs the R4 object stage (NPC objects in towns, [world-travel.md](../re/world-travel.md)), items and gold ([items-stats.md](items-stats.md)). Added by the user on 2026-11-04 next to experience from kills ([monsters.md](monsters.md)) and checkpoints and wells (R4).

## Steps
1. **Data**: `NPCs`, `NPCTalk`, `NPCTextAudio`, `NPCShop`-style tables in 0.5.5e (found with `poe-data`), the town NPCs' object paths and placement from the area's object data.
2. **RE (Opus)** from C2: interacting with an NPC (click, the dialogue window, options), the vendor window (open, the vendor's inventory as an AddInventory-like message, buy, sell, the sell window's confirm), the gold change, and how quest-state-dependent dialogue is chosen (StateMachine and quest states: only what is needed to show the default dialogue now; quests are later). Results go to `docs/protocol/npcs.md` (new).
3. **NPC objects**: spawn town NPCs at their placements (with R4's AddObject), idle state as the data says, click to open dialogue with the default text and the "Purchase items" and "Sell items" options.
4. **Vendors**: stock generated per vendor by level (bases and rarities the vendor sells, from data and documented community rules), refreshed on level-up or by `vendor refresh`; buy prices and sell prices (research the official price rules and cite them in `docs/research/loot.md`); gold and currency payment; selling gives gold.
5. **Commands**: `npc list`, `vendor refresh`; overlay Debug > World.
- Done when: in an agent game test the player talks to a town NPC, opens the vendor, buys an item with gold and sells one back, and the gold and inventory update.

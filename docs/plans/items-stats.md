# Plan: items, inventory, equipment, currency

Steps P10 (items, inventory, equipment, levels) and P11 (currency) of [../PLAN.md](../PLAN.md). The stat calculator (P8) is done: [../architecture/stats.md](../architecture/stats.md). What exists: `poe-game/src/stats.rs` (class template and the speed stats the movement port needs, the admin command `speed`); empty inventories sent on instance entry (`0x00df` AddInventory, one per `Inventories.dat` row, sizes in `[inventories]`, [../protocol/instance.md](../protocol/instance.md)); the DLL Stats page reads the client's stat sets ([../architecture/client-dll.md](../architecture/client-dll.md)).

## User decisions (2026-11-04)
- **Accuracy: use Path of Building 2** (PathOfBuilding-PoE2, MIT). Its latest version targets 0.5.5e, and Hotfix 1 only fixed the minimap, so the latest PoB2 is the reference as is.
- **Port PoB2's calculation rules to Rust**, and test against PoB2 itself run headless.
- **The server computes every stat and sends them** (authoritative), as official servers do.
- "Basic" stats (implemented in the first pass): defences, attributes, life and mana (flat, increased and more life, mana, ES, armour, evasion; Str, Dex, Int; resistances and max resistances; regeneration; spirit); offence basics (weapon physical and elemental damage, added damage, increased and more damage, attack and cast speed, crit chance and multiplier, accuracy); speed and utility (movement speed, rarity and quantity, light radius, stun and ailment thresholds, flask stats); skill-level stats (+N to skill or gem levels).
- Anything else on an item (Mageblood's or Mage's Legacy-style effects, keystone-like lines) is **not implemented**. On **every equip**, once per such stat, the server sends a chat line: `The item you equipped: <item name> has a stat that is not implemented: <stat text>`. Also once at login for items already worn.
- Storage: **inventory and equipment only** (both weapon sets, flask and charm slots); **no stash** in this plan.
- Currency in the first pass: **basic orbs and quality currency** (Transmutation, Augmentation, Regal, Alchemy, Exalted, Chaos, Annulment, Divine, Vaal, their Greater and Perfect tiers; Whetstone, Armourer's Scrap, Glassblower's Bauble, Gemcutter's Prism, Arcanist's Etcher).
- New characters start **empty** (no starting gear).
- Web admin character page: **editable for admins** (inventory here, passive tree in [passives.md](passives.md)).
- Sign-off by agent tests ([../decisions.md](../decisions.md)).

## P10: items, inventory, equipment, weapon sets, levels (Opus for the RE, Sonnet for storage and web admin)
1. **RE (Opus, re-tracer) before code**, from capture C2 ([../re/captures.md](../re/captures.md)) and the client:
   - The item blob inside AddInventory's item list (reader `0x1425bab20`, serializer `0x1425ba860`) and in any separate item messages: base item (BaseItemTypes key or hash), rarity, item level, quality, name words, mods (Mods row and values), implicits, enchants, socketables, corruption, identified, stack size, flags, unique id.
   - Client to server messages: pick up to cursor, place, swap with cursor, equip and unequip, split a stack, weapon set swap, destroy, drop on the ground; and the server's replies (add, remove, move, inventory update).
   - Where the player's equipment appears in the player's AddObject blob (other players' visuals; the "remote equipment visuals" item of the old plan).
   - Results go to `docs/protocol/items.md` (new protocol doc, one owner).
2. **Item model** (`poe-game::items`, shared by inventory, currency, loot and the creator):
   ```rust
   struct Item { uid: u64, base: BaseItemId, rarity: Rarity, ilvl: u8, quality: u8,
                 name: Option<(WordId, WordId)>, unique: Option<UniqueId>,
                 implicits: Vec<RolledMod>, explicits: Vec<RolledMod>, enchants: Vec<RolledMod>,
                 sockets: u8, socketed: Vec<Item>, corrupted: bool, identified: bool,
                 stack: u32, illegal: bool /* made by the creator outside the rules */ }
   struct RolledMod { modr: ModId, values: Vec<i32> }
   ```
3. **Storage** (`poe-store`, new migration): `items` (uid, owner character, JSON or columns of the model), `item_slots` (character, inventory row, x, y, uid). Writes in one transaction per change. Gold stored per character (needed by P11/P18/P19).
4. **Inventory logic**: grid placement and collision (item sizes from BaseItemTypes), stack merge and split, equipment slot rules (ItemClasses and Inventories), requirements (level, Str, Dex, Int) checked as in the client, two weapon sets with the active set stored, flask and charm slot counts (charm slots from the belt, [life-flasks.md](life-flasks.md)).
5. **Send** the real inventories at instance entry (AddInventory with items) and the change messages from the RE.
6. **Stats pipeline**: one `CharacterStats::recalc` (class, level, equipped items of the active set, passive tree, buffs, debug modifiers) on every change; diff against the last sent set; send the stat updates; feed movement speed to the movement port. Feed the calculator output through `character_defaults`' `derive` with items. Send the geared stat list found from C2 (armour, evasion, resistance pairs, per-item counters) and the stat sets 0x40/0x41/0x80/0x81 in the local blob ([stats.md](../architecture/stats.md#what-the-server-sends)).
7. **Not implemented lines**: on equip and at login, for each mod stat of the item not in `map.rs`, a `<Server>` chat line with the formatter's text and the item's name (unique name, rare name or base name).
8. **Levels and XP** (needed by P10's commands; kills come in P17): XP per level from `ExperienceLevels.dat`; level-up gives passive points as the game does (1 per level; quest points come when quests exist: until then via `!points`); the level-up effect and stat recalc. Death XP penalty is in [life-flasks.md](life-flasks.md).
9. **Commands** ([commands.md](commands.md)): `level`, `xp`, `points passive`, `stat ...` (the debug modifier layer: stored per character in `debug_mods(character, stat, kind, value)`, shown as its own source in the breakdown), `inv clear`, `save`, `inspect`. Overlay tabs Character and Stats; the Stats page shows client value, server value and a red mark when they differ (it needs the server's numbers over the debug channel).
10. **Web admin** character page (admins): an **Inventory** tab showing the equipment paper doll and the inventory grid with HTML tooltips (art from `GET /api/v1/art/{path}`, [leagues.md](../architecture/web-api.md)); admin actions: delete, move between slots, change stack size, give a saved template. Changes to an online character are applied live through the instance server. API: `GET/PATCH /api/v1/admin/characters/{id}/inventory`, `POST .../inventory/{uid}/delete`, `POST .../inventory/give-template`.
- Done when: an agent game test gives items by command, equips and unequips them by clicking, swaps weapon sets, and the overlay Stats page shows client = server for every stat; `stats-check` matches PoB2 for the same character; the not-implemented line appears for a unique with an unmapped stat; items survive relog and server restart.

## P11: currency (Opus for the rules, Sonnet for tests)
1. **Mod rolling engine** (`poe-game::crafting`), shared with loot ([loot-parties.md](loot-parties.md)): eligible mods by domain (item), generation type (prefix, suffix, implicit, corrupted), required level ≤ item level (and the Greater and Perfect currencies' minimum mod level), spawn weights by the base's tags (`BaseItemTypes` + `ItemClasses` tags) in order, mod groups and families exclusive, affix limits by rarity (magic 1 prefix + 1 suffix, rare 3 + 3), value ranges rolled uniformly per stat. Weights from `Mods.dat` (exact), cross-checked against PoB2's mod data and poe2db.
2. **Orbs**: Transmutation (normal to magic, 1 mod), Augmentation (add a mod to a magic item), Regal (magic to rare, add a mod), Alchemy (normal to rare with 4 mods), Exalted (add a mod to a rare), Chaos (remove a random mod and add one), Annulment (remove a random mod), Divine (reroll the values of explicit mods), Vaal (corrupt: the official outcome table; research the current 0.5 outcomes from community sources and the client's text, cite them), Greater and Perfect tiers (minimum modifier level from the currency's data). Quality: Whetstone (weapons), Armourer's Scrap (armour), Glassblower's Bauble (flasks), Gemcutter's Prism (gems), Arcanist's Etcher (wands, staves, and what the item text says). Quality caps and steps by rarity as in game.
3. **Interaction**: right-click a currency item, left-click the target: the client's "use item on item" message (from C2 RE); the server checks, applies, decrements the stack and sends the updated items. Invalid uses get the client's own refusal message if one exists.
4. **Stacks and gold**: stack sizes from data; `currency <orb> [n]` and `gold` commands.
- Done when: every listed orb works in game on a test item (agent game test), distribution tests over 100,000 rolls match the spawn weights within 1%, and illegal uses are refused.

## Not in this plan
Stash tabs, Artificer's Orbs and other socket currency, runes, soul cores and essences, Omens, catalysts and the rest; starting gear.

# Plan: item creator and spawner

Step P12 of [../PLAN.md](../PLAN.md), after items (P10) and the mod rolling engine (P11) of [items-stats.md](items-stats.md). Overlay tab: Debug > Items ([overlay.md](overlay.md#debug-help--console--character--stats--items--world--monsters--life--players)). Commands: `item ...` in [commands.md](commands.md).

## User decisions (2026-11-04)
- Lets an admin **search any item and change anything**: any base, rarity, item level, quality, sockets, corrupted state, any mod at any tier and value, including mods and values that cannot normally roll on that base (marked "illegal").
- Output: **directly into the inventory, or dropped on the ground** at the player's feet.
- The overlay shows a **game-style tooltip with the item's art**, updated live while editing.
- Extras: **paste** an item's text (Ctrl+C in game or a PoB2 item), **templates and favourites**, **bulk/random spawn**, **edit an item already in the inventory or equipped**.
- **Overlay and commands only**; no creator in the web admin.
- Admin only.

## Server side: one item builder
1. `poe-game::items::builder`: `ItemSpec` (base or unique, rarity, ilvl, quality, sockets, corrupted, name, implicits, explicits, enchants, socketed, stack) to `Item`, with `validate(&ItemSpec) -> Vec<Issue>` (illegal mod for the base, value out of range, too many affixes, wrong generation type, duplicate group). Issues never block: they set `Item::illegal` and come back to the overlay as tags.
2. Uniques: `UniqueStashLayout`/`Words` and the unique's mod list from game data (`UniqueItems`-style tables in 0.5.5e, found with `poe-data`); a unique starts with its real mods rolled, every mod editable.
3. Rare names: two random `Words.dat` entries of the right type, or free text (free text sets `illegal`).
4. **Paste**: a parser of the game's item text (Ctrl+C format: `Item Class:`, `Rarity:`, name lines, `--------` sections, `Item Level:`, `Quality:`, requirements, `(implicit)`, `(enchant)`, `(rune)`, `Corrupted`) and of PoB2's item text format. Mod lines are matched back to mods through the stat-description formatter (reverse lookup over the base's eligible mods first, then all mods). Unmatched lines are listed for the user and skipped.
5. **Templates**: `item_templates(account, name, spec JSON, favourite)` in `poe-store`, per account. Commands `item template save|give|list|delete`.
6. **Random**: `item random <class|base> [--rarity] [--ilvl] [--count n]` uses the P11 rolling engine, legal only.
7. **Edit in place**: `item edit <slot>` (equipment slot name, or `inv <x> <y>`) loads an existing item's spec; saving replaces it with the same uid and sends the update.
8. **Ground drop**: uses the ground item support of [loot-parties.md](loot-parties.md) (P18). Until P18, `--ground` answers "ground items come with loot (P18)".
9. Debug link: `itemspec` request and reply (the spec as JSON with issues), `complete itembase|unique|mod <prefix>` with filters (item class, mod generation type, tags, tier), and `mods_for <base>` (eligible mods by group with tiers, weights and ranges).

## Item art for the overlay
- The server converts game images to PNG: `GET /api/v1/art/{path}` (DDS decode from the server's own game files, cached on disk under the server's data dir, nothing committed; first user is the league banner picker in [leagues.md](../architecture/web-api.md)). The art path comes from the base's `ItemVisualIdentity` (the 2D inventory art `Art/2DItems/...`).
- The DLL fetches it over HTTP from the server's web API (address known from the connection and the deploy config), decodes the PNG on the overlay thread and registers it as an ImGui texture through the `dear-imgui-ash` backend (the overlay thread owns all overlay Vulkan objects). A small LRU cache (64 textures).
- Without the web API (or an error), the tooltip shows without art.

## The overlay tab
Layout and mockup: [overlay.md](overlay.md#debug-help--console--character--stats--items--world--monsters--life--players). Details:
- **Left**: search box over bases and uniques, grouped by item class; a Templates section (favourites first); `[Paste item text]` (reads the clipboard).
- **Middle**: the editor. Base, rarity, ilvl, quality, sockets, corrupted, identified, stack, name. Mod sections (Implicit, Prefix, Suffix, Enchant, Socketed): each row is a mod picker (search, filter "legal only / all", shows tier `T1..Tn`, weight, required level), value sliders per stat within the tier range, and a free number field to go outside it. `[+ add]` per section, drag to reorder, remove buttons. `[Reroll values]` per row, `[Reroll all legal]`.
- **Right**: the tooltip, drawn in the game's layout: name lines coloured by rarity (normal white, magic blue, rare yellow, unique orange), separators, properties (quality, armour, evasion, ES, damage, crit, speed with the computed values), requirements, sockets and socketed items, implicits, enchants, explicits (blue, the game's text from the formatter), `Corrupted` in red. Illegal parts get an orange `ILLEGAL` tag with the reason on hover. Art above the name.
- **Bottom**: `[Give to inventory]`, `[Drop at feet]`, count `[1]`, `[Save template]` (name), `[Random x N]`, and when editing an existing item `[Save changes]`.

## Done when
- In an agent game test: create a rare ring with chosen mods, give it, equip it, see its stats applied; create an illegal item and see the tags; paste an in-game item text and get the same item; spawn 20 random items on the ground (after P18); edit an equipped item in place.
- Parser tests for game and PoB2 item text; builder validation tests.

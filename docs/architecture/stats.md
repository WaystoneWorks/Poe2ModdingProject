# Stats (`poe-stats`)

Owner of the stat calculator: what it ports, the tools that check it, what it does not cover and which stats the server sends. Step P8 is done; the geared stat list and items come with P10 ([plans/items-stats.md](../plans/items-stats.md)).

## Crate
`modules/server/crates/poe-stats` is a port of the PathOfBuilding-PoE2 rules (MIT, notice in `crates/poe-stats/LICENSE-PathOfBuilding.md`; the reference commit is pinned in `third_party/fetch-tools.sh`). No I/O. Files:

| File | Content |
|---|---|
| `moddb.rs` | ModDB, tags, Sum / More / Flag / Override with PoB rounding |
| `items.rs` | item local mods (calcLocal) |
| `calc.rs` | initEnv base mods, attributes, `calculate` |
| `defence.rs`, `offence.rs` | defence and offence outputs |
| `map.rs` | generated table: stat ids to mods, 396 groups; a stat absent from it is "not implemented" |
| `network.rs` | `own_stats`: calculator output to game stats |

The stat text formatter is `poe_data::stat_desc` (files `data/statdescriptions/*.csd`).

## Tools
- `cargo xtask stats-map` (15 s) writes `dumps/<version>/stats/stat_map.tsv`; `scripts/pob/gen_map.py <tsv> modules/server/crates/poe-stats/src/map.rs` regenerates `map.rs`.
- `scripts/pob/run.sh <driver.lua>` runs a driver in headless PoB2. Drivers read `pob_args`, because PoB opens `arg` as a build; always give stdin from `/dev/null`.
- `cargo xtask stats-check [--write] [--verbose] [--sweep]` compares with PoB2.
  - Default: the corpus, 72 fixtures, 8 classes, levels 1-90, real item mods and real passive nodes, about 20 s.
  - `--write` stores `poe-stats/tests/fixtures.json`, the regression test that needs no game files or PoB2.
  - `--sweep`: every row of `map.rs` alone on 3 gear sets (rows with flags or tags on every weapon type too), with a ring supplying attributes, capped resists, regeneration, spirit, ward and all damage types: 2913 fixtures, about 5 min. Run it when `map.rs` changes.
  - Report: `dumps/<version>/stats/stats_check.txt`; rows where no compared output moved are in `stat_sweep_blind.txt`.
- `cargo xtask stats-sent` writes `dumps/<version>/stats/stats_sent.tsv` from official captures (159 stats over 10 sessions, 23 local entries).

## Result
Corpus and sweep agree with PoB2 on every compared output: 0 differences in 75,618 comparisons. Tolerances: exact for integers; LifeRegen, ManaRegen, EnergyShieldRecharge 0.1; AverageHit, Speed, CritChance, CritMultiplier 0.01; MovementSpeedMod 0.001; StunThreshold, AilmentThreshold 0.5.

`stats-check` fails when an allocated node's text differs from PoB2's tree text, or when PoB2 does not allocate a requested node.

## Rules the comparison needs
Each exists because the comparison was wrong without it.
- Base names with several `BaseItemTypes` rows are skipped: PoB2 keys bases by name and keeps one (Golden Blade, Runeforged and Runemastered bases).
- Switchable tree nodes (78 in PoB2's 0_5 tree) have other stats per class than `PassiveSkills` says, so they are not walked. P15 needs the per-class stats ([plans/passives.md](../plans/passives.md)).
- Enemy physical reduction clamps to [-100, `maximum_physical_damage_reduction_%` of `Metadata/Monsters/Monster.ot`, 75]; the player's cap is 90 from `Character.ot`.
- Crossbow bolt count is per skill level (`SkillProfile.base_bolts`, 7 for Crossbow Shot in the fixtures), the same for `skill_multiplier`. The fixtures read them from PoB2 until P16 takes them from game data.
- A row granting a skill (Thorns) makes PoB2 select it, so hit outputs are not compared there.

## Not ported, not checked
- Dual wielding (`DualWielding` rows are never active), damage conversion, ailments and DoT.
- Temporal chains and the action speed floor: `defence.rs` uses a simplified action speed. The attack speed cap `ServerTickRate` is not ported.
- Most of the damage-taken pipeline: only `armour_reduction` and `hit_taken`; P13 extends it.
- Base spirit of sceptres and the belt charm limit (fixtures use none).
- Default-attack skill flags are a small table in `SkillProfile::default_attack`.
- `per_minute` stats in the fixtures are rounded to multiples of 6, because PoB reads rounded text.
- The sweep cannot see 151 rows: spell, cast, trap, mine, totem, thorns and Vaal rows (no such skill yet, P16), flask and charm rows, gem levels (rows named `GemLevel:<key>`), loot, light radius, weapon range, maximum block. Spear rows (no spear base has an implicit in the table) and Wand rows (no wand class in the sweep) are not seen either. `Ward` INC rows move nothing in either calculator. Resistance rows are blind in the sweep because the ring caps them; the corpus checks them.

## What the server sends
The official entry list for a character without gear, values fitted (Ranger 7/15/7): level 1 `maximum_life` 42, `maximum_mana` 48, `total_mana_recovery_per_minute_from_regeneration` 115, `ailment_threshold` 21, `accuracy` 90; level 2: 54, 52, 125, 27, 96. ES 33 gives `energy_shield_recharge_rate_per_minute` 248.

`poe_stats::network::own_stats` sends: `strength`, `dexterity`, `intelligence`, `total_attributes`, `starting_attribute_*`, `virtual_*_for_requirements`, `virtual_*_for_gem_requirements`, `virtual_gem_requirements_can_be_satisfied_by_highest_attribute_value`, `maximum_life`, `life_unreserved`, `maximum_mana`, `mana_unreserved`, `maximum_energy_shield`, `total_mana_recovery_per_minute_from_regeneration`, `mana_recovery_per_minute`, `energy_shield_recharge_rate_per_minute`, `ailment_threshold`, `virtual_stun_threshold`, `base_movement_velocity_+%`, `combined_movement_velocity_+%_final`. It is used through `poe_game::stats::character_defaults` at login.

Other categories seen on official servers:
- State stats (`on_full_*`, `is_in_town`, `cannot_die`, `using_flask`, `is_dodge_rolling` ...): existing code or P13/P14.
- Weapon and accuracy stats only in stat sets 0x40/0x41/0x80/0x81 (`main_hand_accuracy_rating`, `generic_accuracy_rating`, `main_hand_*_physical_damage`, `display_*`); our local blob sends no sets.
- Per-item counters (`number_of_equipped_*`, `base_helmet_maximum_energy_shield`, `base_boots_maximum_energy_shield`, `base_maximum_energy_shield_on_equipped_armour_items`).
- Resist uncapped/capped pairs (`uncapped_cold_damage_resistance_%` and `cold_damage_resistance_%`, `base_cold_damage_resistance_%`).

The captures hold only a low-level character with a few items, so the geared list (armour, evasion, etc.) is not known: that needs capture C2 ([re/captures.md](../re/captures.md)), taken by P10.

## Movement
The calculator's increased and final numbers reach `speed_stats` through `base_movement_velocity_+%` and `combined_movement_velocity_+%_final` (`Output.movement_inc_percent`, `movement_final_percent`). Both are 0 without gear, so movement is unchanged (replay 27 passed, game test `walk` passes, max drift 0.71 cells). The admin command `speed` stays as the debug override until P10's debug-mod layer.

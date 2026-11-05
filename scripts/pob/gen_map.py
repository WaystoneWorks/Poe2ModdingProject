#!/usr/bin/env python3
"""Generates modules/server/crates/poe-stats/src/map.rs from dumps/<version>/stats/stat_map.tsv.

Keeps the stats whose PoB2 mods are all in the implemented "basic" set (docs/plans or
docs/architecture/stats.md) and need no state the server does not track yet. Every other stat is
"not implemented". Rerun after `cargo xtask stats-map`, then review the diff of map.rs.
"""
import re, sys
from fractions import Fraction

BASIC = re.compile(r"""^(
    Life|Mana|Spirit|EnergyShield|Armour|Evasion|Ward|ArmourAndEvasion|ArmourAndEnergyShield|EvasionAndEnergyShield|Defences|
    Str|Dex|Int|StrDex|StrInt|DexInt|All|
    (Fire|Cold|Lightning|Chaos|Elemental)Resist(Max)?|
    LifeRegen|LifeRegenPercent|ManaRegen|ManaRegenPercent|EnergyShieldRecharge|LifeRecoveryRate|ManaRecoveryRate|
    (Physical|Fire|Cold|Lightning|Chaos)(Min|Max)|
    (Physical|Fire|Cold|Lightning|Chaos|Elemental)?Damage|Local(Fire|Cold|Lightning|Chaos|Elemental)Damage|
    Speed|CritChance|CritMultiplier|Accuracy|
    MovementSpeed|ActionSpeed|LootRarity|LootQuantity|LightRadius|StunThreshold|AilmentThreshold|
    BlockChance|BlockChanceMax|WeaponRange|Quality|
    Flask\w*|CharmLimit|Charm\w*
)$""", re.X)
# Tags whose state the calculator computes itself.
OK_TAG = re.compile(r"^\{(.*type=(PerStat|Condition|Multiplier).*)\}$")
PER_STATS = {"Str", "Dex", "Int"}
COND_OK = re.compile(r"^(Using(Shield|Focus|Bow|Staff|Wand|Sceptre|Spear|Crossbow|Flail|Dagger|Claw|Mace|Axe|Sword|OneHandedWeapon|TwoHandedWeapon|MeleeWeapon)|DualWielding|Unarmed)$")
SCALES = [Fraction(1), Fraction(-1), Fraction(1, 60), Fraction(-1, 60), Fraction(1, 100), Fraction(-1, 100), Fraction(1, 1000), Fraction(-1, 1000), Fraction(2), Fraction(-2)]

RUNTIME = """
fn index() -> &'static HashMap<&'static str, usize> {
    static INDEX: OnceLock<HashMap<&'static str, usize>> = OnceLock::new();
    INDEX.get_or_init(|| {
        let mut map = HashMap::new();
        for (row, (stats, _)) in STAT_MAP.iter().enumerate() {
            for s in *stats {
                map.insert(*s, row);
            }
        }
        map
    })
}

/// Whether the calculator knows this stat.
pub fn is_implemented(stat: &str) -> bool {
    index().contains_key(stat)
}

/// The mods of a stat list, and the stats with no entry. Stats of one description share a row; a
/// missing one counts as 0, values of one stat add up.
pub fn mods_for_stats(stats: &[(&str, i64)]) -> (Vec<Mod>, Vec<String>) {
    let mut totals: HashMap<&str, i64> = HashMap::new();
    let mut order: Vec<usize> = Vec::new();
    let mut unknown = Vec::new();
    for (stat, value) in stats {
        *totals.entry(*stat).or_default() += *value;
        match index().get(*stat) {
            Some(&row) if !order.contains(&row) => order.push(row),
            Some(_) => {}
            None => {
                if !unknown.iter().any(|u| u == stat) {
                    unknown.push((*stat).to_owned());
                }
            }
        }
    }
    let mut mods = Vec::new();
    for row in order {
        let (ids, row_mods) = STAT_MAP[row];
        for &(name, kind, idx, num, den, flags, keyword_flags, tags) in row_mods {
            let v = totals.get(ids[usize::from(idx)]).copied().unwrap_or(0) as f64;
            let mut m = Mod::new(name, kind, v * f64::from(num) / f64::from(den));
            m.flags = flags;
            m.keyword_flags = keyword_flags;
            m.tags = tags();
            mods.push(m);
        }
    }
    (mods, unknown)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_and_unknown_stats() {
        let (mods, unknown) = mods_for_stats(&[("base_maximum_life", 40), ("not_a_stat", 1)]);
        assert_eq!(mods.len(), 1);
        assert_eq!((mods[0].name.as_str(), mods[0].kind, mods[0].value), ("Life", Kind::Base, 40.0));
        assert_eq!(unknown, ["not_a_stat"]);
    }

    #[test]
    fn min_max_stats_share_a_row() {
        let (mods, unknown) = mods_for_stats(&[("attack_minimum_added_fire_damage", 3), ("attack_maximum_added_fire_damage", 7)]);
        assert!(unknown.is_empty());
        let by_name: Vec<(&str, f64)> = mods.iter().map(|m| (m.name.as_str(), m.value)).collect();
        assert_eq!(by_name, [("FireMin", 3.0), ("FireMax", 7.0)]);
    }

    #[test]
    fn per_minute_stats_are_per_second() {
        let (mods, _) = mods_for_stats(&[("life_regeneration_rate_per_minute_%", 120)]);
        assert_eq!(mods[0].value, 2.0);
    }
}
"""

def parse_tag(t):
    m = OK_TAG.match(t)
    if not m:
        return None
    kv = dict(p.split("=", 1) for p in m.group(1).split(","))
    if kv["type"] == "PerStat" and kv.get("stat") in PER_STATS and "limit" not in kv:
        return f'Tag::per_stat("{kv["stat"]}", {float(kv.get("div", 1))})'
    if kv["type"] == "Multiplier" and kv.get("var") == "Level" and "limit" not in kv and "base" not in kv:
        return f'Tag::per_level({float(kv.get("div", 1))})'
    if kv["type"] == "Condition" and COND_OK.match(kv.get("var", "")) and "neg" not in kv:
        return f'Tag::condition("{kv["var"]}")'
    return None

def scale_for(value, sample):
    for s in SCALES:
        if abs(float(s) * sample - value) < max(0.0051, abs(value) * 0.03):
            return s
    return None

def convert(ids, samples, mods):
    out = []
    for m in mods:
        parts = m.split(":")
        name, kind, val = parts[0], parts[1], parts[2]
        flags, kw, tags = 0, 0, []
        for p in parts[3:]:
            if p.startswith("flags="):
                flags = int(p[6:])
            elif p.startswith("kw="):
                kw = int(p[3:])
            else:
                tags.append(parse_tag(p))
        if not BASIC.match(name) or None in tags or kind not in ("BASE", "INC", "MORE"):
            return None
        try:
            v = float(val)
        except ValueError:
            return None
        hit = None
        for i, s in enumerate(samples):
            sc = scale_for(v, s)
            if sc is not None:
                hit = (i, sc)
                break
        if hit is None:
            return None
        out.append((name, kind, hit[0], hit[1], flags, kw, tags))
    return out

def main(tsv, rs):
    rows = []
    for line in open(tsv, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) < 5 or f[2] != "ok" or not f[4]:
            continue
        # "+N to Level of all X Skills": kept per stat for the gem levels of P16.
        level = re.match(r"^(\w+)_skill_gem_level_\+$", f[0])
        if level and "GemProperty" in f[4]:
            rows.append(([f[0]], f[3], [(f"GemLevel:{level.group(1)}", "BASE", 0, Fraction(1), 0, 0, [])]))
            continue
        conv = convert(f[0].split(","), [int(x) for x in f[1].split(",")], f[4].split(" ; "))
        if conv:
            rows.append((f[0].split(","), f[3], conv))
    rows.sort(key=lambda r: r[0])
    w = ["//! Stat id to mod table: what each implemented game stat means to the calculator.",
         "//! Generated by `scripts/pob/gen_map.py` from `cargo xtask stats-map` (PoB2's ModParser on the",
         "//! game's stat text), then reviewed. A stat not listed here is \"not implemented\".",
         "//! Rows: `(stats of the description, mods)`; a mod reads one value of the group, scaled.",
         "#![allow(clippy::type_complexity)]", "",
         "use std::{collections::HashMap, sync::OnceLock};", "",
         "use crate::moddb::{Kind, Mod, Tag};", "",
         "/// One mod of a stat group: `(name, kind, value index, numerator, denominator, flags, keyword flags, tags)`.",
         "pub type MapMod = (&'static str, Kind, u8, i32, i32, u64, u32, fn() -> Vec<Tag>);", "",
         "fn no_tags() -> Vec<Tag> {", "    Vec::new()", "}", "",
         "pub const STAT_MAP: &[(&[&str], &[MapMod])] = &["]
    kinds = {"BASE": "Kind::Base", "INC": "Kind::Inc", "MORE": "Kind::More"}
    for ids, text, conv in rows:
        w.append(f"    // {text.replace(chr(92)+'n', ' / ')}")
        w.append(f"    (&[{', '.join(chr(34)+i+chr(34) for i in ids)}], &[")
        for name, kind, idx, sc, flags, kw, tags in conv:
            t = "no_tags" if not tags else f"|| vec![{', '.join(tags)}]"
            w.append(f'        ("{name}", {kinds[kind]}, {idx}, {sc.numerator}, {sc.denominator}, {flags}, {kw}, {t}),')
        w.append("    ]),")
    w.append("];")
    w.append(RUNTIME)
    open(rs, "w", encoding="utf-8").write("\n".join(w) + "\n")
    print(f"{len(rows)} stat groups")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

//! `cargo xtask stats-check`: compares `poe-stats` with PoB2 headless on a corpus of fixture
//! characters built from game data (every class, levels 1-90, real item mods, real passives).
//! `--write` stores the corpus with PoB2's numbers in `poe-stats/tests/fixtures.json`, the
//! regression test that runs without game files. Docs: docs/architecture/stats.md.

use std::{
    collections::{BTreeMap, HashMap, HashSet, VecDeque},
    fmt::Write as _,
    path::Path,
    process::{Command, Stdio},
};

use anyhow::{Context, Result, bail};
use poe_data::{GameData, Row, stat_desc::StatDescriptions, template::ObjectTemplate};
use poe_stats::{
    CharacterBase, Constants, Enemy, Input, ItemBase, ItemInput, SkillProfile, Slot, WeaponBase, WeaponType, calculate,
    map,
};
use serde_json::{Value, json};

/// Outputs that must match exactly; the others within PoB2's display rounding.
const INTEGER_OUTPUTS: &[&str] = &[
    "Life", "Mana", "Spirit", "EnergyShield", "Armour", "Evasion", "Ward", "FireResist", "ColdResist", "LightningResist",
    "ChaosResist", "BlockChance", "Str", "Dex", "Int", "Accuracy",
];
const DECIMAL_OUTPUTS: &[(&str, f64)] = &[
    ("LifeRegen", 0.1),
    ("ManaRegen", 0.1),
    ("EnergyShieldRecharge", 0.1),
    ("AverageHit", 0.01),
    ("Speed", 0.01),
    ("CritChance", 0.01),
    ("CritMultiplier", 0.01),
    ("MovementSpeedMod", 0.001),
    ("StunThreshold", 0.5),
    ("AilmentThreshold", 0.5),
];

fn output_value(o: &poe_stats::Output, key: &str) -> f64 {
    match key {
        "Life" => o.life,
        "Mana" => o.mana,
        "Spirit" => o.spirit,
        "EnergyShield" => o.energy_shield,
        "Armour" => o.armour,
        "Evasion" => o.evasion,
        "Ward" => o.ward,
        "FireResist" => o.fire_resist,
        "ColdResist" => o.cold_resist,
        "LightningResist" => o.lightning_resist,
        "ChaosResist" => o.chaos_resist,
        "BlockChance" => o.block_chance,
        "Str" => o.str,
        "Dex" => o.dex,
        "Int" => o.int,
        "Accuracy" => o.accuracy,
        "LifeRegen" => o.life_regen,
        "ManaRegen" => o.mana_regen,
        "EnergyShieldRecharge" => o.es_recharge,
        "AverageHit" => o.average_hit,
        "Speed" => o.speed,
        "CritChance" => o.crit_chance,
        "CritMultiplier" => o.crit_multiplier,
        "MovementSpeedMod" => o.movement_speed_mod,
        "StunThreshold" => o.stun_threshold,
        "AilmentThreshold" => o.ailment_threshold,
        _ => f64::NAN,
    }
}

/// xorshift64, so the corpus is the same on every run.
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }

    fn below(&mut self, n: usize) -> usize {
        (self.next() % n.max(1) as u64) as usize
    }
}

fn stat_ids(data: &GameData) -> Result<Vec<String>> {
    let t = data.table("Stats")?;
    t.rows().map(|r| Ok(r.str("Id")?)).collect()
}

fn int_or_first(row: &Row, column: &str) -> Result<i64> {
    let v = row.get(column)?;
    if let Some(i) = v.as_int() {
        return Ok(i);
    }
    Ok(v.as_list().and_then(|l| l.first()).and_then(|x| x.as_int()).unwrap_or(0))
}

/// The stats of a `Mods` row, each at its lowest roll. `per_minute` stats are rounded to what the
/// text can show, because PoB2 reads the text.
fn mod_stats(row: &Row, ids: &[String]) -> Result<Vec<(String, i64)>> {
    let mut out = Vec::new();
    for i in 1..=8 {
        if let Some(s) = row.row_ref(&format!("Stat{i}"))? {
            let mut v = int_or_first(row, &format!("Stat{i}Value"))?;
            if ids[s].contains("per_minute") {
                v = (v / 6).max(1) * 6;
            }
            out.push((ids[s].clone(), v));
        }
    }
    Ok(out)
}

#[derive(Clone)]
struct Base {
    name: String,
    class: String,
    item: ItemBase,
    implicits: Vec<(String, i64)>,
    /// Eligible mods: their stats.
    mods: Vec<Vec<(String, i64)>>,
}

/// The base table's numbers per class (`ArmourTypes`, `WeaponTypes`, `ShieldTypes`).
fn load_bases(data: &GameData, ids: &[String], pob: &HashSet<String>, desc: &StatDescriptions) -> Result<Vec<Base>> {
    let weapon_kinds: HashMap<&str, WeaponType> = HashMap::from([
        ("Bow", WeaponType::Bow),
        ("Crossbow", WeaponType::Crossbow),
        ("One Hand Mace", WeaponType::OneHandMace),
        ("Two Hand Mace", WeaponType::TwoHandMace),
        ("Spear", WeaponType::Spear),
        ("Warstaff", WeaponType::Staff),
        ("Claw", WeaponType::Claw),
        ("Dagger", WeaponType::Dagger),
        ("Flail", WeaponType::Flail),
        ("One Hand Sword", WeaponType::OneHandSword),
        ("One Hand Axe", WeaponType::OneHandAxe),
        ("Two Hand Sword", WeaponType::TwoHandSword),
        ("Two Hand Axe", WeaponType::TwoHandAxe),
    ]);
    let classes = data.table("ItemClasses")?;
    let mut armour = HashMap::new();
    for r in data.table("ArmourTypes")?.rows() {
        if let Some(b) = r.row_ref("BaseItemType")? {
            armour.insert(b, (r.int("Armour")?, r.int("Evasion")?, r.int("EnergyShield")?, r.int("Ward")?, r.int("IncreasedMovementSpeed")?));
        }
    }
    let mut weapons = HashMap::new();
    for r in data.table("WeaponTypes")?.rows() {
        if let Some(b) = r.row_ref("BaseItemType")? {
            weapons.insert(b, (r.int("DamageMin")?, r.int("DamageMax")?, r.int("Speed")?, r.int("CritChance")?, r.int("ReloadTime")?));
        }
    }
    let mut shields = HashMap::new();
    for r in data.table("ShieldTypes")?.rows() {
        if let Some(b) = r.row_ref("BaseItemType")? {
            shields.insert(b, r.int("Block")?);
        }
    }
    let mods_table = data.table("Mods")?;
    // Mods the calculator fully understands and the game can show, with their spawn weights.
    let mut candidates = Vec::new();
    for r in mods_table.rows() {
        let gen_type = r.row_ref("GenerationType")?;
        if r.row_ref("Domain")? != Some(1) || !(gen_type == Some(1) || gen_type == Some(2)) {
            continue;
        }
        let stats = mod_stats(&r, ids)?;
        if stats.is_empty() || !stats.iter().all(|(s, _)| map::is_implemented(s)) {
            continue;
        }
        let refs: Vec<(&str, i64)> = stats.iter().map(|(s, v)| (s.as_str(), *v)).collect();
        if desc.format(&refs).is_empty() {
            continue;
        }
        let tags: Vec<usize> = r.get("SpawnWeight_Tags")?.as_list().unwrap_or(&[]).iter().filter_map(|v| v.as_row()).collect();
        let weights: Vec<i64> = r.get("SpawnWeight_Values")?.as_list().unwrap_or(&[]).iter().filter_map(|v| v.as_int()).collect();
        candidates.push((stats, tags, weights));
    }
    let base_table = data.table("BaseItemTypes")?;
    let mut out = Vec::new();
    for r in base_table.rows() {
        let name = r.str("Name")?;
        if !pob.contains(&name) {
            continue;
        }
        let Some(class_row) = r.row_ref("ItemClass")?.and_then(|i| classes.row(i)) else { continue };
        let class = class_row.str("Id")?;
        let i = r.index();
        let item = if let Some(&kind) = weapon_kinds.get(class.as_str()) {
            let Some(&(min, max, speed, crit, reload)) = weapons.get(&i) else { continue };
            ItemBase::Weapon(WeaponBase {
                kind,
                physical_min: min as f64,
                physical_max: max as f64,
                attack_rate: poe_stats::round_to(1000.0 / speed as f64, 2),
                crit_chance: crit as f64 / 100.0,
                reload_time: reload as f64 / 1000.0,
            })
        } else if matches!(class.as_str(), "Helmet" | "Body Armour" | "Gloves" | "Boots" | "Shield" | "Focus") {
            let Some(&(a, e, s, w, ms)) = armour.get(&i) else { continue };
            ItemBase::Armour {
                armour: a as f64,
                evasion: e as f64,
                energy_shield: s as f64,
                ward: w as f64,
                block: shields.get(&i).map(|b| *b as f64),
                movement_penalty: -(ms as f64) / 10000.0,
                shield: class == "Shield",
                focus: class == "Focus",
            }
        } else if matches!(class.as_str(), "Ring" | "Amulet" | "Belt") {
            ItemBase::Other { spirit: None, charm_limit: None }
        } else {
            continue;
        };
        let mut implicits = Vec::new();
        for m in r.get("Implicit_Mods")?.as_list().unwrap_or(&[]).iter().filter_map(|v| v.as_row()) {
            if let Some(row) = mods_table.row(m) {
                implicits.extend(mod_stats(&row, ids)?);
            }
        }
        // A base with an implicit outside the table would only test "not implemented".
        if !implicits.iter().all(|(s, _)| map::is_implemented(s)) {
            continue;
        }
        let base_tags: HashSet<usize> = r.get("Tags")?.as_list().unwrap_or(&[]).iter().filter_map(|v| v.as_row()).collect();
        let mods = candidates
            .iter()
            .filter(|(_, tags, weights)| {
                tags.iter().zip(weights).find(|(t, _)| base_tags.contains(t)).is_some_and(|(_, w)| *w > 0)
            })
            .map(|(stats, _, _)| stats.clone())
            .collect();
        out.push(Base { name, class, item, implicits, mods });
    }
    Ok(out)
}

struct Fixture {
    name: String,
    class_name: String,
    input: Input,
    items: Vec<(Slot, Base, Vec<(String, i64)>)>,
    nodes: Vec<u32>,
    enemy: Enemy,
}

fn xml_escape(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;").replace('"', "&quot;")
}

fn item_text(base: &Base, quality: f64, explicits: &[(String, i64)], desc: &StatDescriptions) -> String {
    let lines = |stats: &[(String, i64)]| -> Vec<String> {
        let refs: Vec<(&str, i64)> = stats.iter().map(|(s, v)| (s.as_str(), *v)).collect();
        desc.format(&refs).into_iter().flat_map(|l| l.text.split('\n').map(str::to_owned).collect::<Vec<_>>()).collect()
    };
    let implicit = lines(&base.implicits);
    let mut t = format!("Rarity: RARE\nFixture Item\n{}\nQuality: {quality}\nImplicits: {}\n", base.name, implicit.len());
    for l in implicit {
        t.push_str(&l);
        t.push('\n');
    }
    for l in lines(explicits) {
        t.push_str(&l);
        t.push('\n');
    }
    t
}

fn build_xml(fx: &Fixture, class_id: u64, penalty: f64, desc: &StatDescriptions) -> String {
    let mut items = String::new();
    let mut slots = String::new();
    for (i, (slot, base, explicits)) in fx.items.iter().enumerate() {
        let id = i + 1;
        let quality = fx.input.items[i].quality;
        write!(items, "<Item id=\"{id}\">{}</Item>", xml_escape(&item_text(base, quality, explicits, desc))).unwrap();
        write!(slots, "<Slot name=\"{}\" itemId=\"{id}\"/>", slot.pob_name()).unwrap();
    }
    let nodes: Vec<String> = fx.nodes.iter().map(u32::to_string).collect();
    let e = &fx.enemy;
    format!(
        "<?xml version=\"1.0\"?><PathOfBuilding2><Build level=\"{}\" targetVersion=\"0_1\" className=\"{}\" ascendClassName=\"None\" mainSocketGroup=\"1\" viewMode=\"ITEMS\"/>\
<Tree activeSpec=\"1\"><Spec treeVersion=\"0_5\" classId=\"{class_id}\" ascendClassId=\"0\" nodes=\"{}\"/></Tree>\
<Items activeItemSet=\"1\">{items}<ItemSet id=\"1\">{slots}</ItemSet></Items><Skills activeSkillSet=\"1\"><SkillSet id=\"1\"/></Skills>\
<Config><Input name=\"resistancePenalty\" number=\"{penalty}\"/><Input name=\"enemyIsBoss\" string=\"None\"/><Input name=\"enemyEvasion\" number=\"{}\"/><Input name=\"enemyArmour\" number=\"{}\"/><Input name=\"enemyPhysicalDamageReduction\" number=\"{}\"/><Input name=\"enemyLightningResist\" number=\"{}\"/><Input name=\"enemyColdResist\" number=\"{}\"/><Input name=\"enemyFireResist\" number=\"{}\"/><Input name=\"enemyChaosResist\" number=\"{}\"/><!--QUESTS--></Config></PathOfBuilding2>",
        fx.input.level,
        fx.class_name,
        nodes.join(","),
        e.evasion,
        e.armour,
        e.physical_reduction,
        e.resist[0],
        e.resist[1],
        e.resist[2],
        e.resist[3],
    )
}

fn run_driver(root: &Path, args: &[&str]) -> Result<()> {
    let status = Command::new(root.join("scripts/pob/run.sh"))
        .arg(root.join("scripts/pob/stats_check.lua"))
        .args(args)
        .stdin(Stdio::null())
        .status()
        .context("running PoB2 (third_party/fetch-tools.sh fetches it)")?;
    if !status.success() {
        bail!("PoB2 driver failed: {status}");
    }
    Ok(())
}

fn fixture_json(fx: &Fixture, pob: &Value) -> Value {
    let c = &fx.input.constants;
    let class = &fx.input.class;
    let items: Vec<Value> = fx
        .input
        .items
        .iter()
        .map(|it| {
            let base = match &it.base {
                ItemBase::Armour { armour, evasion, energy_shield, ward, block, movement_penalty, shield, focus } => {
                    json!({"armour": [armour, evasion, energy_shield, ward, block, movement_penalty, shield, focus]})
                }
                ItemBase::Weapon(w) => json!({"weapon": [format!("{:?}", w.kind), w.physical_min, w.physical_max, w.attack_rate, w.crit_chance, w.reload_time]}),
                ItemBase::Other { .. } => json!({"other": []}),
            };
            json!({"slot": format!("{:?}", it.slot), "base": base, "quality": it.quality, "stats": it.stats})
        })
        .collect();
    let mut expected = serde_json::Map::new();
    for k in INTEGER_OUTPUTS.iter().copied().chain(DECIMAL_OUTPUTS.iter().map(|d| d.0)) {
        expected.insert(k.to_owned(), pob.get(k).cloned().unwrap_or(Value::Null));
    }
    json!({
        "name": fx.name,
        "level": fx.input.level,
        "constants": [c.life_per_level, c.mana_per_level, c.accuracy_per_level, c.base_evasion, c.base_crit_bonus, c.max_resistance, c.max_block, c.mana_regen_per_minute, c.es_recharge_per_minute, c.base_life, c.base_mana],
        "class": [class.strength, class.dexterity, class.intelligence, class.unarmed.physical_min, class.unarmed.physical_max, class.unarmed.attack_rate, class.unarmed.crit_chance],
        "items": items,
        "passives": fx.input.passives,
        "resist_penalty": fx.input.resist_penalty,
        "skill_multiplier": fx.input.skill.base_multiplier,
        "enemy": [fx.enemy.evasion, fx.enemy.armour, fx.enemy.physical_reduction, fx.enemy.resist[0], fx.enemy.resist[1], fx.enemy.resist[2], fx.enemy.resist[3]],
        "expected": expected,
    })
}

pub fn run(root: &Path, version: &str, write: bool, verbose: bool) -> Result<()> {
    let data = GameData::open(&root.join("GameFiles"), &root.join("third_party/dat-schema/schema-poe2.min.json"))?;
    let desc = StatDescriptions::load(data.files(), "data/statdescriptions/stat_descriptions.csd")?;
    let ids = stat_ids(&data)?;
    let dir = root.join("dumps").join(version).join("stats");
    std::fs::create_dir_all(&dir)?;

    // What PoB2 knows: item base names, classes, tree links.
    let query_path = dir.join("pob_query.json");
    run_driver(root, &["query", query_path.to_str().context("path")?])?;
    let query: Value = serde_json::from_slice(&std::fs::read(&query_path)?)?;
    let pob_bases: HashSet<String> = query["bases"].as_array().context("bases")?.iter().filter_map(|v| v.as_str().map(str::to_owned)).collect();
    let bases = load_bases(&data, &ids, &pob_bases, &desc)?;
    let by_class = |classes: &[&str]| -> Vec<Base> { bases.iter().filter(|b| classes.contains(&b.class.as_str())).cloned().collect() };

    // Constants from the Character template.
    let template = ObjectTemplate::load(&data, "Metadata/Characters/Character")?;
    let t: HashMap<&str, f64> = template.component("Stats").iter().filter_map(|(k, v)| Some((k.as_str(), v.parse().ok()?))).collect();
    let get = |k: &str| t.get(k).copied().with_context(|| format!("{k} not in Character.ot"));
    let unarmed_crit = get("unarmed_base_critical_strike_chance")? / 100.0;
    let constants = Constants {
        life_per_level: get("life_per_level")?,
        mana_per_level: get("mana_per_level")?,
        accuracy_per_level: get("accuracy_rating_per_level")?,
        base_evasion: get("base_evasion_rating")?,
        base_crit_bonus: get("base_critical_hit_damage_bonus")?,
        max_resistance: get("base_maximum_all_resistances_%")?,
        max_block: get("object_inherent_base_maximum_block_%_from_ot")?,
        mana_regen_per_minute: get("character_inherent_mana_regeneration_rate_per_minute_%")?,
        es_recharge_per_minute: get("energy_shield_recharge_rate_per_minute_%")?,
        base_life: 16.0,
        base_mana: 30.0,
    };

    // Classes.
    let characters = data.table("Characters")?;
    let mut classes = Vec::new();
    let class_ids = query["classes"].as_object().context("classes")?;
    for r in characters.rows() {
        let name = r.str("Name")?;
        let Some(class_id) = class_ids.get(&name).and_then(Value::as_u64) else { continue };
        if classes.iter().any(|(n, _, _)| *n == name) {
            continue;
        }
        let speed = r.int("WeaponSpeed")? as f64;
        classes.push((
            name,
            class_id,
            CharacterBase {
                strength: r.int("BaseStrength")? as f64,
                dexterity: r.int("BaseDexterity")? as f64,
                intelligence: r.int("BaseIntelligence")? as f64,
                unarmed: WeaponBase {
                    kind: WeaponType::Unarmed,
                    physical_min: r.int("MinDamage")? as f64,
                    physical_max: r.int("MaxDamage")? as f64,
                    attack_rate: poe_stats::round_to(1000.0 / speed, 2),
                    crit_chance: unarmed_crit,
                    reload_time: 0.0,
                },
            },
        ));
    }

    // Passive nodes whose stats are all implemented; attribute nodes only walk.
    let passive_table = data.table("PassiveSkills")?;
    let mut node_stats: HashMap<u32, Vec<(String, i64)>> = HashMap::new();
    let mut walkable: HashSet<u32> = HashSet::new();
    for r in passive_table.rows() {
        let id = r.int("PassiveSkillGraphId")? as u32;
        let excluded = r.bool("IsKeystone")? || r.bool("IsJewelSocket")? || r.row_ref("Ascendancy")?.is_some() || r.bool("IsMultipleChoice")? || r.bool("IsMultipleChoiceOption")?;
        if excluded {
            continue;
        }
        if r.bool("IsAttribute")? {
            walkable.insert(id);
            continue;
        }
        let stats: Vec<(String, i64)> = r
            .get("Stats")?
            .as_list()
            .unwrap_or(&[])
            .iter()
            .filter_map(|v| v.as_row())
            .enumerate()
            .filter_map(|(i, s)| Some((ids.get(s)?.clone(), r.int(&format!("Stat{}Value", i + 1)).ok()?)))
            .collect();
        if !stats.is_empty() && stats.iter().all(|(s, _)| map::is_implemented(s) && !s.contains("per_minute")) {
            walkable.insert(id);
            node_stats.insert(id, stats);
        }
    }
    let links: HashMap<u32, Vec<u32>> = query["links"]
        .as_object()
        .context("links")?
        .iter()
        .filter_map(|(k, v)| Some((k.parse().ok()?, v.as_array()?.iter().filter_map(|x| x.as_u64().map(|n| n as u32)).collect())))
        .collect();
    let reachable = |class: &str, limit: usize| -> Vec<u32> {
        let Some(start) = query["starts"].get(class).and_then(Value::as_u64) else { return Vec::new() };
        let mut seen = HashSet::from([start as u32]);
        let mut q = VecDeque::from([start as u32]);
        let mut out = Vec::new();
        while let Some(n) = q.pop_front() {
            for &next in links.get(&n).map_or(&[][..], Vec::as_slice) {
                if walkable.contains(&next) && seen.insert(next) {
                    out.push(next);
                    q.push_back(next);
                }
            }
            if out.len() >= limit {
                break;
            }
        }
        out.truncate(limit);
        out
    };

    let armour_slots: [(Slot, &[&str]); 8] = [
        (Slot::Helmet, &["Helmet"]),
        (Slot::BodyArmour, &["Body Armour"]),
        (Slot::Gloves, &["Gloves"]),
        (Slot::Boots, &["Boots"]),
        (Slot::Amulet, &["Amulet"]),
        (Slot::Ring1, &["Ring"]),
        (Slot::Ring2, &["Ring"]),
        (Slot::Belt, &["Belt"]),
    ];
    let weapon_classes: [&[&str]; 13] = [
        &["Bow"], &["Crossbow"], &["One Hand Mace"], &["Two Hand Mace"], &["Spear"], &["Warstaff"], &["Claw"], &["Dagger"], &["Flail"],
        &["One Hand Sword"], &["One Hand Axe"], &["Two Hand Sword"], &["Two Hand Axe"],
    ];
    let levels = [1u32, 5, 12, 20, 33, 45, 60, 75, 90];
    let penalties = [0.0, -10.0, -20.0, -30.0, -40.0, -50.0, -60.0];
    let enemies = [
        Enemy::default(),
        Enemy { evasion: 500.0, ..Enemy::default() },
        Enemy { evasion: 2000.0, armour: 500.0, physical_reduction: 0.0, resist: [20.0, 20.0, 20.0, 10.0] },
    ];
    let mut rng = Rng(0x9E37_79B9_7F4A_7C15);
    let mut fixtures = Vec::new();
    let make = |rng: &mut Rng, name: String, class_idx: usize, level: u32, gear: usize, weapon: Option<usize>, nodes_wanted: usize, mods_per_item: usize, penalty: f64, enemy: Enemy| -> Fixture {
        let (class_name, _, class) = &classes[class_idx];
        let mut items = Vec::new();
        let mut inputs = Vec::new();
        let mut add = |rng: &mut Rng, slot: Slot, pool: &[Base], items: &mut Vec<(Slot, Base, Vec<(String, i64)>)>, inputs: &mut Vec<ItemInput>| {
            if pool.is_empty() {
                return;
            }
            let base = pool[rng.below(pool.len())].clone();
            let mut explicits: Vec<(String, i64)> = Vec::new();
            if !base.mods.is_empty() {
                for _ in 0..mods_per_item {
                    for (s, v) in &base.mods[rng.below(base.mods.len())] {
                        if !explicits.iter().any(|(x, _)| x == s) {
                            explicits.push((s.clone(), *v));
                        }
                    }
                }
            }
            let quality = [0.0, 5.0, 10.0, 20.0][rng.below(4)];
            let mut stats = base.implicits.clone();
            stats.extend(explicits.iter().cloned());
            inputs.push(ItemInput { slot, base: base.item.clone(), quality, stats });
            items.push((slot, base, explicits));
        };
        let mut kind = WeaponType::Unarmed;
        if let Some(w) = weapon {
            let pool = by_class(weapon_classes[w]);
            add(rng, Slot::MainHand, &pool, &mut items, &mut inputs);
            if let Some(ItemBase::Weapon(b)) = inputs.last().map(|i| &i.base) {
                kind = b.kind;
            }
            if kind != WeaponType::Unarmed && kind.info().2 && gear > 2 {
                let pool = by_class(if gear % 2 == 0 { &["Shield"] } else { &["Focus"] });
                add(rng, Slot::OffHand, &pool, &mut items, &mut inputs);
            }
        }
        for (slot, cls) in armour_slots.iter().take(gear) {
            let pool = by_class(cls);
            add(rng, *slot, &pool, &mut items, &mut inputs);
        }
        let nodes = reachable(class_name, nodes_wanted);
        let passives = nodes.iter().filter_map(|n| node_stats.get(n).cloned()).collect();
        Fixture {
            name,
            class_name: class_name.clone(),
            input: Input {
                constants,
                class: *class,
                level,
                items: inputs,
                passives,
                extra_mods: Vec::new(),
                resist_penalty: penalty,
                skill: SkillProfile::default_attack(kind, 1.0),
                enemy,
                conditions: Vec::new(),
            },
            items,
            nodes,
            enemy,
        }
    };
    for (i, (class, _, _)) in classes.iter().enumerate() {
        // Bare characters over the level range.
        for (l, level) in [1u32, 45, 90].into_iter().enumerate() {
            fixtures.push(make(&mut rng, format!("{class}-bare-{level}"), i, level, 0, None, 0, 0, penalties[l * 2], enemies[0]));
        }
        // Passives only.
        fixtures.push(make(&mut rng, format!("{class}-passives"), i, 60, 0, None, 25, 0, 0.0, enemies[1]));
        // Gear combinations.
        for g in 0..5 {
            let n = fixtures.len();
            let level = levels[n % levels.len()];
            let weapon = rng.below(weapon_classes.len());
            let gear = [1, 3, 5, 6, 8][g];
            let mods = [0, 1, 2, 3, 4][g];
            let nodes = [0, 5, 10, 20, 40][g];
            fixtures.push(make(&mut rng, format!("{class}-gear-{g}"), i, level, gear, Some(weapon), nodes, mods, penalties[n % penalties.len()], enemies[n % enemies.len()]));
        }
    }

    // PoB2.
    let eval_in = dir.join("stats_check_in.jsonl");
    let eval_out = dir.join("stats_check_out.jsonl");
    let class_id = |name: &str| classes.iter().find(|c| c.0 == name).map_or(0, |c| c.1);
    let mut text = String::new();
    for fx in &fixtures {
        let xml = build_xml(fx, class_id(&fx.class_name), fx.input.resist_penalty, &desc);
        writeln!(text, "{}", json!({"name": fx.name, "xml": xml}))?;
    }
    std::fs::write(&eval_in, text)?;
    run_driver(root, &["eval", eval_in.to_str().context("path")?, eval_out.to_str().context("path")?])?;
    let results: Vec<Value> = std::fs::read_to_string(&eval_out)?.lines().map(serde_json::from_str).collect::<Result<_, _>>()?;
    if results.len() != fixtures.len() {
        bail!("PoB2 returned {} results for {} fixtures", results.len(), fixtures.len());
    }

    // Compare.
    let (mut failed, mut checks) = (0, 0);
    let mut per_output: BTreeMap<String, usize> = BTreeMap::new();
    let mut lines = String::new();
    let mut stored = Vec::new();
    for (fx, pob) in fixtures.iter_mut().zip(&results) {
        if let Some(e) = pob.get("error") {
            bail!("{}: PoB2 error: {e}", fx.name);
        }
        fx.input.skill.base_multiplier = pob["skill_multiplier"].as_f64().unwrap_or(1.0);
        let got = calculate(&fx.input);
        let mut bad = Vec::new();
        for (k, tol) in INTEGER_OUTPUTS.iter().map(|k| (*k, 0.0)).chain(DECIMAL_OUTPUTS.iter().copied()) {
            let Some(want) = pob.get(k).and_then(Value::as_f64) else { continue };
            checks += 1;
            let have = output_value(&got, k);
            if (have - want).abs() > tol + 1e-9 {
                bad.push(format!("{k}: {have} vs PoB2 {want}"));
                *per_output.entry(k.to_owned()).or_default() += 1;
            }
        }
        if !bad.is_empty() {
            failed += 1;
            writeln!(lines, "{} [{}]: {}", fx.name, pob["skill"], bad.join(", "))?;
        }
        stored.push(fixture_json(fx, pob));
    }
    let report = dir.join("stats_check.txt");
    std::fs::write(&report, &lines)?;
    println!("{} fixtures, {checks} comparisons, {failed} fixtures differ; report {}", fixtures.len(), report.display());
    for (k, n) in &per_output {
        println!("  {k}: {n}");
    }
    if verbose {
        print!("{lines}");
    }
    if write {
        let path = root.join("modules/server/crates/poe-stats/tests/fixtures.json");
        std::fs::write(&path, serde_json::to_string_pretty(&stored)?)?;
        println!("wrote {}", path.display());
    }
    if failed > 0 {
        bail!("poe-stats differs from PoB2");
    }
    Ok(())
}

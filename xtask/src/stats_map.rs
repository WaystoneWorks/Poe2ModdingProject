//! `cargo xtask stats-map`: which PoB2 mods each game stat produces. Renders every stat used by
//! `Mods`, `PassiveSkills` and the gem stat sets with the game's own stat descriptions, feeds the
//! text to PoB2's ModParser (headless) and writes `dumps/<version>/stats/stat_map.tsv`. The table
//! `poe-stats/src/map.rs` is reviewed against this file. Docs: docs/architecture/stats.md.

use std::{
    collections::BTreeSet,
    fmt::Write as _,
    path::Path,
    process::Command,
};

use anyhow::{Context, Result, bail};
use poe_data::{GameData, stat_desc::StatDescriptions};

/// Stat ids used by the mod, passive and gem tables.
fn used_stats(data: &GameData) -> Result<BTreeSet<String>> {
    let stats = data.table("Stats")?;
    let mut rows = BTreeSet::new();
    let mods = data.table("Mods")?;
    for row in mods.rows() {
        for i in 1..=8 {
            if let Some(s) = row.row_ref(&format!("Stat{i}"))? {
                rows.insert(s);
            }
        }
    }
    for (table, column) in [
        ("PassiveSkills", "Stats"),
        ("GrantedEffectStatSets", "ImplicitStats"),
        ("GrantedEffectStatSets", "ConstantStats"),
    ] {
        let t = data.table(table)?;
        for row in t.rows() {
            if let Some(list) = row.get(column)?.as_list() {
                rows.extend(list.iter().filter_map(|v| v.as_row()));
            }
        }
    }
    let mut out = BTreeSet::new();
    for r in rows {
        if let Some(row) = stats.row(r) {
            out.insert(row.str("Id")?);
        }
    }
    Ok(out)
}

/// A stat group rendered with sample values, so the mods tell which stat they read. Pairs of
/// minimum and maximum get different values; in other groups a later stat is often a switch that
/// changes the wording, so the first stat alone is tried first. A description can show nothing for
/// 10 (`1|1` only), hence the other samples.
fn render(desc: &StatDescriptions, group: &[String]) -> Option<(Vec<i64>, String)> {
    let pair = group.len() > 1 && group[0].contains("minimum") && group[1].contains("maximum");
    let spread = |s: i64| -> Vec<i64> { (0..group.len() as i64).map(|i| s * (1 + 2 * i)).collect() };
    let first = |s: i64| -> Vec<i64> { (0..group.len()).map(|i| if i == 0 { s } else { 0 }).collect() };
    for sample in [10, 1, 2, 100, 1000, -10] {
        for values in if pair { vec![spread(sample)] } else { vec![first(sample), spread(sample)] } {
            let stats: Vec<(&str, i64)> = group.iter().map(String::as_str).zip(values.iter().copied()).collect();
            let lines = desc.format(&stats);
            if !lines.is_empty() {
                let text: Vec<String> = lines.into_iter().map(|l| l.text.replace('\n', "\\n")).collect();
                return Some((values, text.join("\\n")));
            }
        }
    }
    None
}

pub fn run(root: &Path, version: &str) -> Result<()> {
    let data = GameData::open(&root.join("GameFiles"), &root.join("third_party/dat-schema/schema-poe2.min.json"))?;
    let stats = used_stats(&data)?;
    let mut desc = StatDescriptions::load(data.files(), "data/statdescriptions/passive_skill_stat_descriptions.csd")?;
    desc.merge(StatDescriptions::load(data.files(), "data/statdescriptions/stat_descriptions.csd")?);

    let dir = root.join("dumps").join(version).join("stats");
    std::fs::create_dir_all(&dir)?;
    let input = dir.join("stat_text.tsv");
    let output = dir.join("stat_map.tsv");

    let (mut seen, mut text, mut hidden, mut missing) = (BTreeSet::new(), String::new(), String::new(), 0);
    for stat in &stats {
        if seen.contains(stat) {
            continue;
        }
        let Some(group) = desc.group(stat) else {
            let why = if desc.is_hidden(stat) { "hidden" } else { "no_description" };
            missing += 1;
            writeln!(hidden, "{stat}\t\t{why}\t\t")?;
            continue;
        };
        seen.extend(group.iter().cloned());
        match render(&desc, group) {
            Some((values, t)) => {
                let v: Vec<String> = values.iter().map(i64::to_string).collect();
                writeln!(text, "{}\t{}\t{t}", group.join(","), v.join(","))?;
            }
            None => writeln!(hidden, "{}\t\tno_variant\t\t", group.join(","))?,
        }
    }
    std::fs::write(&input, text)?;

    let status = Command::new(root.join("scripts/pob/run.sh"))
        .arg(root.join("scripts/pob/stats_map.lua"))
        .arg(&input)
        .arg(&output)
        .stdin(std::process::Stdio::null())
        .status()
        .context("running PoB2 (third_party/fetch-tools.sh fetches it)")?;
    if !status.success() {
        bail!("PoB2 driver failed: {status}");
    }

    let mut map = std::fs::read_to_string(&output)?;
    map.push_str(&hidden);
    std::fs::write(&output, &map)?;

    let mut counts = std::collections::BTreeMap::<&str, usize>::new();
    for line in map.lines() {
        *counts.entry(line.split('\t').nth(2).unwrap_or("")).or_default() += 1;
    }
    println!("{} stats, {missing} without a description; {}", stats.len(), output.display());
    for (k, v) in counts {
        println!("  {k}: {v}");
    }
    Ok(())
}

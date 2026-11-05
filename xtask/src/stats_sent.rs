//! `cargo xtask stats-sent`: which stats the official server sends for the local player, from the
//! official captures: the entry blob's base list and stat sets, and `StatsUpdate`. Writes
//! `dumps/<version>/stats/stats_sent.tsv`. Docs: docs/architecture/stats.md.

use std::{
    collections::{BTreeMap, BTreeSet},
    fmt::Write as _,
    path::Path,
};

use anyhow::{Context, Result};
use poe_data::GameData;
use poe_net::Reader;
use poe_proto::{
    Message,
    instance::{AddObject, PlayerEntity, StatsUpdate},
    player_blob::PlayerBlob,
};
use serde_json::Value;

#[derive(Default)]
struct Seen {
    entry_sessions: BTreeSet<String>,
    entry_values: BTreeSet<i32>,
    set_ids: BTreeSet<u8>,
    updates: usize,
    update_values: BTreeSet<i32>,
}

fn hex(s: &str) -> Vec<u8> {
    (0..s.len() / 2).filter_map(|i| u8::from_str_radix(&s[i * 2..i * 2 + 2], 16).ok()).collect()
}

fn sample(values: &BTreeSet<i32>) -> String {
    let mut v: Vec<String> = values.iter().take(6).map(i32::to_string).collect();
    if values.len() > 6 {
        v.push("...".to_owned());
    }
    v.join(",")
}

pub fn run(root: &Path, version: &str) -> Result<()> {
    let data = GameData::open(&root.join("GameFiles"), &root.join("third_party/dat-schema/schema-poe2.min.json"))?;
    let names: Vec<String> = data.table("Stats")?.rows().map(|r| Ok(r.str("Id")?)).collect::<Result<_>>()?;
    let captures = root.join("dumps").join(version).join("captures/official");
    let mut seen: BTreeMap<u32, Seen> = BTreeMap::new();
    let mut sessions = 0;
    let mut entries = 0;
    let mut entries_dir: Vec<_> = std::fs::read_dir(&captures)?.filter_map(|e| Some(e.ok()?.path())).collect();
    entries_dir.sort();
    for dir in entries_dir {
        let Ok(text) = std::fs::read_to_string(dir.join("packets.jsonl")) else { continue };
        let session = dir.file_name().context("name")?.to_string_lossy().into_owned();
        sessions += 1;
        let mut me = None;
        for line in text.lines() {
            let Ok(m) = serde_json::from_str::<Value>(line) else { continue };
            if m["dir"] != "in" || m["chan"] != "instance" {
                continue;
            }
            let Some(bytes) = m["hex"].as_str().map(hex) else { continue };
            let Some(body) = bytes.get(2..) else { continue };
            let mut r = Reader::new(body);
            match m["name"].as_str() {
                Some("PlayerEntity") => me = PlayerEntity::decode(&mut r).ok().map(|p| p.entity_id),
                Some("AddObject") => {
                    let Ok(add) = AddObject::decode(&mut r) else { continue };
                    if Some(add.header.entity_id) != me {
                        continue;
                    }
                    let Ok(blob) = PlayerBlob::decode(&add.blob) else { continue };
                    entries += 1;
                    for &(key, value) in &blob.stats.base {
                        let s = seen.entry(key).or_default();
                        s.entry_sessions.insert(session.clone());
                        s.entry_values.insert(value);
                    }
                    for set in &blob.stats.sets {
                        for &(key, value) in &set.stats {
                            let s = seen.entry(key).or_default();
                            s.set_ids.insert(set.id);
                            s.entry_values.insert(value);
                        }
                    }
                }
                Some("StatsUpdate") => {
                    let Ok(update) = StatsUpdate::decode(&mut r) else { continue };
                    if Some(update.header.entity_id) != me {
                        continue;
                    }
                    for &(key, value) in &update.stats {
                        let s = seen.entry(key).or_default();
                        s.updates += 1;
                        s.update_values.insert(value);
                    }
                }
                _ => {}
            }
        }
    }
    let mut out = String::from("key\tstat\tentry_sessions\tsets\tentry_values\tupdates\tupdate_values\n");
    for (key, s) in &seen {
        let name = names.get(*key as usize - 1).map_or("?", String::as_str);
        let sets: Vec<String> = s.set_ids.iter().map(|i| format!("{i:#x}")).collect();
        writeln!(out, "{key}\t{name}\t{}\t{}\t{}\t{}\t{}", s.entry_sessions.len(), sets.join(","), sample(&s.entry_values), s.updates, sample(&s.update_values))?;
    }
    let path = root.join("dumps").join(version).join("stats/stats_sent.tsv");
    std::fs::write(&path, out)?;
    println!("{sessions} sessions, {entries} entries of the local player, {} stats; {}", seen.len(), path.display());
    Ok(())
}

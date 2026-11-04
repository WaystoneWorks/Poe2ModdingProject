//! `cargo xtask tracker gen | check | build | edit`: the progress tracker site (docs/guides/tracker.md).
//!
//! - `gen` reads the game data and writes `tracker/rows.json` (names only) and the `[auto]` table
//!   of `tracker/status.toml`.
//! - `check` needs no game data: every id in `status.toml` must be a row of `rows.json` or of a
//!   section of `sections.toml`, and every status must be a known one.
//! - `build` makes the static site in `runtime/tracker-site/` (Vite app in `tracker/site/`, data
//!   in `data.js`, recent changes from `git log -p tracker/status.toml`).
//! - `edit` serves the same site on 127.0.0.1 with status dropdowns that write `status.toml`.

use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    io::{BufRead, BufReader, Read, Write},
    net::{TcpListener, TcpStream},
    path::Path,
    process::Command,
};

use anyhow::{Context, Result, bail};
use clap::Subcommand;
use poe_config::Config;
use serde::{Deserialize, Serialize};

const ROWS: &str = "tracker/rows.json";
const STATUS: &str = "tracker/status.toml";
const SECTIONS: &str = "tracker/sections.toml";
const SITE_DIR: &str = "tracker/site";
const OUT_DIR: &str = "runtime/tracker-site";
/// Source file of the server commands (`cmd:` rows and their automatic status).
const COMMANDS_RS: &str = "modules/server/servers/instance-server/src/commands.rs";
const TOKENS: &str = "modules/web-admin/src/tokens.css";
/// How many status changes the page lists.
const RECENT: usize = 50;

#[derive(Subcommand)]
pub enum Cmd {
    /// Make tracker/rows.json from the game data and refresh the `[auto]` table of status.toml.
    Gen,
    /// Check status.toml against rows.json and sections.toml (no game data needed).
    Check,
    /// Build the static site into runtime/tracker-site/.
    Build {
        /// Only rewrite data.js (the site was built before).
        #[arg(long)]
        data_only: bool,
    },
    /// Serve the site on 127.0.0.1 with editable statuses (writes tracker/status.toml).
    Edit {
        #[arg(long, default_value_t = 8787)]
        port: u16,
        /// Do not rebuild the site first.
        #[arg(long)]
        no_build: bool,
    },
}

pub fn run(root: &Path, config_path: &Path, cmd: Cmd) -> Result<()> {
    match cmd {
        Cmd::Gen => generate(root, config_path),
        Cmd::Check => check(root),
        Cmd::Build { data_only } => build(root, data_only),
        Cmd::Edit { port, no_build } => edit(root, port, no_build),
    }
}

// ---------------------------------------------------------------------------------------------
// Files

/// The statuses, in the order the page shows them.
const STATUSES: &[&str] = &[
    "unknown",
    "not_implemented",
    "partial",
    "implemented",
    "fully_functional",
    "not_planned",
];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
struct Row {
    id: String,
    section: String,
    group: String,
    name: String,
}

#[derive(Debug, Deserialize)]
struct SectionsFile {
    section: Vec<Section>,
}

#[derive(Debug, Deserialize)]
struct Section {
    id: String,
    title: String,
    #[serde(default)]
    description: String,
    /// `project` sections list their rows in `rows`; the others are filled by `gen`.
    #[serde(default)]
    generator: String,
    #[serde(default)]
    rows: Vec<StaticRow>,
}

#[derive(Debug, Deserialize)]
struct StaticRow {
    id: String,
    group: String,
    name: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct Entry {
    status: String,
    note: String,
    link: String,
}

/// `status.toml`: `[auto]` (written by `gen`, wins over hand edits) and `[status]` (hand edited).
#[derive(Debug, Default)]
struct StatusFile {
    auto: BTreeMap<String, Entry>,
    hand: BTreeMap<String, Entry>,
}

fn load_sections(root: &Path) -> Result<Vec<Section>> {
    let text = std::fs::read_to_string(root.join(SECTIONS)).context("reading sections.toml")?;
    Ok(toml::from_str::<SectionsFile>(&text).context("parsing sections.toml")?.section)
}

fn load_rows(root: &Path) -> Result<Vec<Row>> {
    let text = std::fs::read_to_string(root.join(ROWS))
        .context("reading tracker/rows.json (run `cargo xtask tracker gen`)")?;
    serde_json::from_str(&text).context("parsing rows.json")
}

fn load_status(root: &Path) -> Result<StatusFile> {
    let path = root.join(STATUS);
    if !path.exists() {
        return Ok(StatusFile::default());
    }
    let table: toml::Table =
        toml::from_str(&std::fs::read_to_string(&path)?).context("parsing status.toml")?;
    let mut out = StatusFile::default();
    for (key, target) in [("auto", &mut out.auto), ("status", &mut out.hand)] {
        let Some(t) = table.get(key).and_then(|v| v.as_table()) else { continue };
        for (id, v) in t {
            let get = |k: &str| v.get(k).and_then(|x| x.as_str()).unwrap_or_default().to_owned();
            target.insert(
                id.clone(),
                Entry { status: get("status"), note: get("note"), link: get("link") },
            );
        }
    }
    Ok(out)
}

fn toml_str(s: &str) -> String {
    // JSON string escapes are valid TOML basic-string escapes.
    serde_json::to_string(s).unwrap()
}

fn entry_line(id: &str, e: &Entry) -> String {
    let mut s = format!("{} = {{ status = {}", toml_str(id), toml_str(&e.status));
    if !e.note.is_empty() {
        s.push_str(&format!(", note = {}", toml_str(&e.note)));
    }
    if !e.link.is_empty() {
        s.push_str(&format!(", link = {}", toml_str(&e.link)));
    }
    s.push_str(" }\n");
    s
}

fn save_status(root: &Path, f: &StatusFile) -> Result<()> {
    let mut out = String::from(
        "# Row statuses of the progress tracker (docs/guides/tracker.md). A row that is not here is\n\
         # unknown. Edit [status] by hand or with `cargo xtask tracker edit`; [auto] is written by\n\
         # `cargo xtask tracker gen` and wins over [status]. Statuses: unknown, not_implemented,\n\
         # partial, implemented, fully_functional, not_planned.\n\n[auto]\n",
    );
    for (id, e) in &f.auto {
        out.push_str(&entry_line(id, e));
    }
    out.push_str("\n[status]\n");
    for (id, e) in &f.hand {
        out.push_str(&entry_line(id, e));
    }
    std::fs::write(root.join(STATUS), out)?;
    Ok(())
}

// ---------------------------------------------------------------------------------------------
// gen

/// Sort key that orders "Act 2" before "Act 10".
fn natural_key(s: &str) -> Vec<(u8, String, u64)> {
    let mut out = Vec::new();
    let mut digits = String::new();
    let mut text = String::new();
    let flush_text = |out: &mut Vec<(u8, String, u64)>, text: &mut String| {
        if !text.is_empty() {
            out.push((0, text.to_lowercase(), 0));
            text.clear();
        }
    };
    for c in s.chars() {
        if c.is_ascii_digit() {
            flush_text(&mut out, &mut text);
            digits.push(c);
        } else {
            if !digits.is_empty() {
                out.push((1, String::new(), digits.parse().unwrap_or(u64::MAX)));
                digits.clear();
            }
            text.push(c);
        }
    }
    flush_text(&mut out, &mut text);
    if !digits.is_empty() {
        out.push((1, String::new(), digits.parse().unwrap_or(u64::MAX)));
    }
    out
}

type Gen = Vec<(String, String, String)>; // id, group, name

fn generate(root: &Path, config_path: &Path) -> Result<()> {
    let config = Config::load(config_path).context("loading the server config")?;
    let gd = poe_data::GameData::open(&config.game.game_dir, &config.game.schema)
        .context("opening the game data")?;
    let sections = load_sections(root)?;
    let classes = ItemClasses::load(&gd)?;
    let mut rows: Vec<Row> = Vec::new();
    for s in &sections {
        let mut found: Gen = match s.generator.as_str() {
            "" => continue,
            "classes" => gen_classes(&gd)?,
            "gems" => gen_gems(&gd, false)?,
            "supports" => gen_gems(&gd, true)?,
            "passives" => gen_passives(&gd)?,
            "uniques" => gen_uniques(&gd)?,
            "base" => gen_base(&gd, &classes, ClassKind::Base)?,
            "currency" => gen_base(&gd, &classes, ClassKind::Currency)?,
            "flasks" => gen_base(&gd, &classes, ClassKind::Flask)?,
            "stats" => gen_stats(&gd)?,
            "monsters" => gen_monsters(&gd)?,
            "areas" => gen_areas(&gd)?,
            "commands" => gen_commands(root)?,
            other => bail!("sections.toml: section {}: unknown generator {other:?}", s.id),
        };
        found.sort_by(|a, b| {
            natural_key(&a.1).cmp(&natural_key(&b.1)).then_with(|| {
                natural_key(&a.2).cmp(&natural_key(&b.2)).then_with(|| a.0.cmp(&b.0))
            })
        });
        let mut seen = BTreeSet::new();
        let before = found.len();
        for (id, group, name) in found {
            // Developer placeholders ("[DNT] ...", "[DNT-UNUSED] ...") are not content.
            if name.starts_with("[DNT") || name.starts_with("[UNUSED") {
                continue;
            }
            if seen.insert(id.clone()) {
                rows.push(Row { id, section: s.id.clone(), group, name });
            }
        }
        println!("{:<12} {:>6} rows ({} placeholders or duplicates dropped)", s.id, seen.len(), before - seen.len());
    }
    let mut out = String::from("[\n");
    for (i, r) in rows.iter().enumerate() {
        out.push_str(&format!(
            "{}{}\n",
            serde_json::to_string(r)?,
            if i + 1 == rows.len() { "" } else { "," }
        ));
    }
    out.push_str("]\n");
    std::fs::write(root.join(ROWS), out)?;

    // [auto]: the server commands that exist are implemented.
    let mut status = load_status(root)?;
    status.auto.clear();
    for r in rows.iter().filter(|r| r.id.starts_with("cmd:")) {
        status.auto.insert(
            r.id.clone(),
            Entry { status: "implemented".into(), ..Default::default() },
        );
    }
    save_status(root, &status)?;
    check(root)
}

/// Item classes: id and name by row index, and which section a class belongs to.
struct ItemClasses {
    ids: Vec<String>,
    names: Vec<String>,
}

#[derive(PartialEq, Clone, Copy)]
enum ClassKind {
    Base,
    Currency,
    Flask,
    /// Covered by the gem sections.
    Gem,
}

impl ItemClasses {
    fn load(gd: &poe_data::GameData) -> Result<Self> {
        let t = gd.table("ItemClasses")?;
        let mut ids = Vec::new();
        let mut names = Vec::new();
        for r in t.rows() {
            ids.push(r.str("Id")?);
            names.push(r.str("Name")?);
        }
        Ok(Self { ids, names })
    }

    fn kind(&self, class: usize) -> ClassKind {
        let id = self.ids.get(class).map(String::as_str).unwrap_or_default();
        let lower = id.to_ascii_lowercase();
        if lower.contains("gem") {
            ClassKind::Gem
        } else if lower.contains("flask") || lower.contains("charm") {
            ClassKind::Flask
        } else if lower.contains("currency") {
            ClassKind::Currency
        } else {
            ClassKind::Base
        }
    }
}

fn row_str(gd: &poe_data::GameData, table: &str, index: usize, col: &str) -> Result<String> {
    Ok(gd.table(table)?.row(index).map(|r| r.str(col)).transpose()?.unwrap_or_default())
}

fn list_rows(v: poe_data::Value) -> Vec<usize> {
    v.as_list().map(|l| l.iter().filter_map(|x| x.as_row()).collect()).unwrap_or_default()
}

fn gen_classes(gd: &poe_data::GameData) -> Result<Gen> {
    let mut out = Gen::new();
    let chars = gd.table("Characters")?;
    for r in chars.rows() {
        let (id, name) = (r.str("Id")?, r.str("Name")?);
        if !id.is_empty() && !name.is_empty() {
            out.push((format!("class:{id}"), "Classes".into(), name));
        }
    }
    for r in gd.table("Ascendancy")?.rows() {
        let (id, name) = (r.str("Id")?, r.str("Name")?);
        if id.is_empty() || name.is_empty() || r.bool("Disabled")? {
            continue;
        }
        let class = match r.row_ref("Character")? {
            Some(i) => row_str(gd, "Characters", i, "Name")?,
            None => String::new(),
        };
        let group = if class.is_empty() { "Ascendancies".to_owned() } else { class };
        out.push((format!("asc:{id}"), format!("{group} ascendancies"), name));
    }
    Ok(out)
}

fn gen_gems(gd: &poe_data::GameData, supports: bool) -> Result<Gen> {
    let mut out = Gen::new();
    for r in gd.table("SkillGems")?.rows() {
        if r.bool("IsVaalVariant")? {
            continue;
        }
        let Some(base) = r.row_ref("BaseItemType")? else { continue };
        let (id, name) = (
            row_str(gd, "BaseItemTypes", base, "Id")?,
            row_str(gd, "BaseItemTypes", base, "Name")?,
        );
        if id.is_empty() || name.is_empty() {
            continue;
        }
        let is_support = id.contains("SupportGem");
        if is_support != supports {
            continue;
        }
        let (s, d, i) = (
            r.int("StrengthRequirementPercent")?,
            r.int("DexterityRequirementPercent")?,
            r.int("IntelligenceRequirementPercent")?,
        );
        let group = if s == 0 && d == 0 && i == 0 {
            "No attribute"
        } else if s >= d && s >= i {
            "Strength"
        } else if d >= i {
            "Dexterity"
        } else {
            "Intelligence"
        };
        out.push((format!("gem:{}", short_id(&id)), group.into(), name));
    }
    Ok(out)
}

fn gen_passives(gd: &poe_data::GameData) -> Result<Gen> {
    let mut out = Gen::new();
    // Small passives are grouped by their first stat instead of one row each.
    let mut small: BTreeMap<String, String> = BTreeMap::new();
    for r in gd.table("PassiveSkills")?.rows() {
        let (id, name) = (r.str("Id")?, r.str("Name")?);
        if id.is_empty() || name.is_empty() || r.bool("IsJewelSocket")? || r.bool("IsProxyPassive")? {
            continue;
        }
        let group_ascendancy = match r.row_ref("Ascendancy")? {
            Some(i) => row_str(gd, "Ascendancy", i, "Name")?,
            None => String::new(),
        };
        if r.bool("IsKeystone")? {
            out.push((format!("passive:{id}"), "Keystones".into(), name));
        } else if r.bool("IsNotable")? {
            let group = if group_ascendancy.is_empty() {
                "Notables".to_owned()
            } else {
                format!("{group_ascendancy} notables")
            };
            out.push((format!("passive:{id}"), group, name));
        } else if group_ascendancy.is_empty() {
            let stats = list_rows(r.get("Stats")?);
            if let Some(first) = stats.first() {
                let stat = row_str(gd, "Stats", *first, "Id")?;
                if !stat.is_empty() {
                    small.entry(stat).or_insert(name);
                }
            }
        }
    }
    for (stat, name) in small {
        out.push((format!("passive:stat:{stat}"), "Small passives (by stat)".into(), name));
    }
    Ok(out)
}

/// Item ids without the common `Metadata/Items/` prefix.
fn short_id(id: &str) -> &str {
    id.strip_prefix("Metadata/Items/").unwrap_or(id)
}

/// "Act 1" to "Act 4", the interludes (act 6 in the data) and the endgame (act 10).
fn act_label(act: i64) -> String {
    match act {
        6 => "Act 6 (interludes)".into(),
        10 => "Act 10 (endgame)".into(),
        n => format!("Act {n}"),
    }
}

fn slug(s: &str) -> String {
    let mut out = String::new();
    for c in s.chars() {
        if c.is_ascii_alphanumeric() {
            out.push(c.to_ascii_lowercase());
        } else if !out.ends_with('_') && !out.is_empty() {
            out.push('_');
        }
    }
    out.trim_end_matches('_').to_owned()
}

fn gen_uniques(gd: &poe_data::GameData) -> Result<Gen> {
    let mut out = Gen::new();
    for r in gd.table("UniqueStashLayout")?.rows() {
        if r.bool("IsAlternateArt")? {
            continue;
        }
        let Some(w) = r.row_ref("WordsKey")? else { continue };
        let name = row_str(gd, "Words", w, "Text")?;
        if name.is_empty() {
            continue;
        }
        let group = match r.row_ref("UniqueStashTypesKey")? {
            Some(i) => row_str(gd, "UniqueStashTypes", i, "Name")?,
            None => String::new(),
        };
        let group = if group.is_empty() { "Other".to_owned() } else { group };
        out.push((format!("unique:{}", slug(&name)), group, name));
    }
    Ok(out)
}

fn gen_base(gd: &poe_data::GameData, classes: &ItemClasses, kind: ClassKind) -> Result<Gen> {
    let mut out = Gen::new();
    for r in gd.table("BaseItemTypes")?.rows() {
        let (id, name) = (r.str("Id")?, r.str("Name")?);
        let Some(class) = r.row_ref("ItemClass")? else { continue };
        if id.is_empty() || name.is_empty() || classes.kind(class) != kind {
            continue;
        }
        let class_id = classes.ids.get(class).map(String::as_str).unwrap_or_default();
        if class_id.contains("Hidden") || class_id.contains("InstanceLocal") {
            continue;
        }
        let group = classes.names.get(class).cloned().unwrap_or_default();
        let group = if group.is_empty() { "Other".to_owned() } else { group };
        let prefix = if kind == ClassKind::Currency { "currency" } else { "base" };
        out.push((format!("{prefix}:{}", short_id(&id)), group, name));
    }
    Ok(out)
}

fn gen_stats(gd: &poe_data::GameData) -> Result<Gen> {
    let mut used: BTreeSet<usize> = BTreeSet::new();
    for r in gd.table("Mods")?.rows() {
        for col in ["Stat1", "Stat2", "Stat3", "Stat4", "Stat5"] {
            if let Some(i) = r.row_ref(col)? {
                used.insert(i);
            }
        }
    }
    for r in gd.table("PassiveSkills")?.rows() {
        used.extend(list_rows(r.get("Stats")?));
    }
    let stats = gd.table("Stats")?;
    let mut out = Gen::new();
    for i in used {
        let Some(r) = stats.row(i) else { continue };
        let id = r.str("Id")?;
        if id.is_empty() {
            continue;
        }
        let first = id.split('_').next().unwrap_or("other");
        let group = match first {
            "base" | "local" | "additional" | "number" | "maximum" | "minimum" => "Base and local",
            "virtual" => "Virtual",
            "active" | "skill" | "support" => "Skills and supports",
            "physical" | "fire" | "cold" | "lightning" | "chaos" | "elemental" => "Damage types",
            "monster" | "map" => "Monsters and areas",
            _ if id.contains("passive") => "Passives",
            _ => "Other",
        };
        out.push((format!("stat:{id}"), group.into(), id));
    }
    Ok(out)
}

fn gen_monsters(gd: &poe_data::GameData) -> Result<Gen> {
    // The first campaign act a monster appears in, and whether it is a boss there.
    let mut place: HashMap<usize, (i64, bool)> = HashMap::new();
    for r in gd.table("WorldAreas")?.rows() {
        if r.bool("IsMapArea")? || r.str("Id")?.is_empty() {
            continue;
        }
        let act = r.int("Act")?;
        for (col, boss) in [("Bosses_MonsterVarietiesKeys", true), ("Monsters_MonsterVarietiesKeys", false)] {
            for m in list_rows(r.get(col)?) {
                let e = place.entry(m).or_insert((act, boss));
                if act < e.0 || (act == e.0 && boss) {
                    *e = (act, boss);
                }
            }
        }
    }
    let mut out = Gen::new();
    for r in gd.table("MonsterVarieties")?.rows() {
        let (id, name) = (r.str("Id")?, r.str("Name")?);
        if id.is_empty() || name.is_empty() {
            continue;
        }
        let group = match place.get(&r.index()) {
            Some((act, true)) => format!("{} bosses", act_label(*act)),
            Some((act, false)) => format!("{} monsters", act_label(*act)),
            None => "Other (not in a campaign area)".into(),
        };
        out.push((format!("monster:{id}"), group, name));
    }
    Ok(out)
}

fn gen_areas(gd: &poe_data::GameData) -> Result<Gen> {
    let mut out = Gen::new();
    for r in gd.table("WorldAreas")?.rows() {
        let (id, name) = (r.str("Id")?, r.str("Name")?);
        if id.is_empty() || name.is_empty() {
            continue;
        }
        let group = if r.bool("IsMapArea")? {
            "Endgame maps".to_owned()
        } else {
            act_label(r.int("Act")?)
        };
        out.push((format!("area:{id}"), group, name));
    }
    Ok(out)
}

/// `cmd:` rows from the server's command table (`Spec { name: "...", group: "..." }`).
fn gen_commands(root: &Path) -> Result<Gen> {
    let text = std::fs::read_to_string(root.join(COMMANDS_RS)).context("reading commands.rs")?;
    let re = regex::Regex::new(r#"Spec \{ name: "(\w+)", group: "(\w+)""#).unwrap();
    Ok(re
        .captures_iter(&text)
        .map(|c| (format!("cmd:{}", &c[1]), c[2].to_owned(), c[1].to_owned()))
        .collect())
}

// ---------------------------------------------------------------------------------------------
// check

/// All row ids: generated and the static rows of the project sections.
fn all_rows(root: &Path) -> Result<Vec<Row>> {
    let mut rows = load_rows(root)?;
    for s in load_sections(root)? {
        for r in s.rows {
            rows.push(Row { id: r.id, section: s.id.clone(), group: r.group, name: r.name });
        }
    }
    Ok(rows)
}

fn check(root: &Path) -> Result<()> {
    let rows = all_rows(root)?;
    let ids: BTreeSet<&str> = rows.iter().map(|r| r.id.as_str()).collect();
    if ids.len() != rows.len() {
        bail!("duplicate row ids in rows.json / sections.toml");
    }
    let status = load_status(root)?;
    let mut bad = Vec::new();
    for (table, map) in [("auto", &status.auto), ("status", &status.hand)] {
        for (id, e) in map {
            if !ids.contains(id.as_str()) {
                bad.push(format!("[{table}] {id}: no such row"));
            }
            if !STATUSES.contains(&e.status.as_str()) {
                bad.push(format!("[{table}] {id}: unknown status {:?}", e.status));
            }
        }
    }
    for id in status.hand.keys() {
        if status.auto.contains_key(id) {
            bad.push(format!("[status] {id}: also in [auto] (the automatic status wins; delete it)"));
        }
    }
    if !bad.is_empty() {
        for b in &bad {
            eprintln!("tracker: {b}");
        }
        bail!("tracker: {} problem(s) in status.toml", bad.len());
    }
    println!(
        "tracker: {} rows, {} automatic and {} hand-set statuses, all ids exist",
        rows.len(),
        status.auto.len(),
        status.hand.len()
    );
    Ok(())
}

// ---------------------------------------------------------------------------------------------
// build

fn git(root: &Path, args: &[&str]) -> Option<String> {
    let out = Command::new("git").args(args).current_dir(root).output().ok()?;
    out.status.success().then(|| String::from_utf8_lossy(&out.stdout).into_owned())
}

/// `https://github.com/owner/repo` from the `origin` remote, if it is a GitHub one.
fn repo_url(root: &Path) -> Option<String> {
    let url = git(root, &["remote", "get-url", "origin"])?.trim().to_owned();
    let path = url
        .strip_prefix("git@github.com:")
        .or_else(|| url.strip_prefix("https://github.com/"))?;
    Some(format!("https://github.com/{}", path.trim_end_matches(".git")))
}

#[derive(Serialize)]
struct Change {
    id: String,
    name: String,
    old: String,
    new: String,
    date: String,
    commit: String,
}

/// The last status changes from `git log -p tracker/status.toml`.
fn recent_changes(root: &Path, names: &HashMap<&str, &str>) -> Vec<Change> {
    let Some(log) = git(
        root,
        &["log", "-n", "300", "-p", "-U0", "--no-color", "--format=@@C %h %cs", "--", STATUS],
    ) else {
        return Vec::new();
    };
    let line_re = regex::Regex::new(r#"^([+-])("(?:[^"\\]|\\.)*") = \{ status = "(\w+)""#).unwrap();
    let mut out = Vec::new();
    let mut commit = (String::new(), String::new());
    let mut old: BTreeMap<String, String> = BTreeMap::new();
    let mut new: BTreeMap<String, String> = BTreeMap::new();
    let flush = |commit: &(String, String),
                     old: &mut BTreeMap<String, String>,
                     new: &mut BTreeMap<String, String>,
                     out: &mut Vec<Change>| {
        let ids: BTreeSet<String> = old.keys().chain(new.keys()).cloned().collect();
        for id in ids {
            let o = old.get(&id).cloned().unwrap_or_else(|| "unknown".into());
            let n = new.get(&id).cloned().unwrap_or_else(|| "unknown".into());
            if o != n {
                let name = names.get(id.as_str()).copied().unwrap_or(id.as_str()).to_owned();
                out.push(Change { id, name, old: o, new: n, date: commit.1.clone(), commit: commit.0.clone() });
            }
        }
        old.clear();
        new.clear();
    };
    for line in log.lines() {
        if let Some(rest) = line.strip_prefix("@@C ") {
            flush(&commit, &mut old, &mut new, &mut out);
            let mut p = rest.split(' ');
            commit = (p.next().unwrap_or_default().into(), p.next().unwrap_or_default().into());
            if out.len() >= RECENT {
                break;
            }
        } else if let Some(c) = line_re.captures(line) {
            let id: String = serde_json::from_str(&c[2]).unwrap_or_default();
            let map = if &c[1] == "+" { &mut new } else { &mut old };
            map.insert(id, c[3].to_owned());
        }
    }
    flush(&commit, &mut old, &mut new, &mut out);
    out.truncate(RECENT);
    out
}

/// The text of `data.js`: everything the page shows.
fn data_js(root: &Path, edit: bool) -> Result<String> {
    let rows = all_rows(root)?;
    let sections = load_sections(root)?;
    let status = load_status(root)?;
    let names: HashMap<&str, &str> = rows.iter().map(|r| (r.id.as_str(), r.name.as_str())).collect();
    let mut by_section: HashMap<&str, Vec<&Row>> = HashMap::new();
    for r in &rows {
        by_section.entry(r.section.as_str()).or_default().push(r);
    }
    let mut secs = Vec::new();
    for s in &sections {
        let mut list = Vec::new();
        for r in by_section.get(s.id.as_str()).map(Vec::as_slice).unwrap_or_default() {
            // The automatic status wins over a hand set one.
            let e = status.auto.get(&r.id).or_else(|| status.hand.get(&r.id));
            let (st, note, link) = match e {
                Some(e) => (e.status.as_str(), e.note.as_str(), e.link.as_str()),
                None => ("unknown", "", ""),
            };
            let auto = status.auto.contains_key(&r.id);
            list.push(serde_json::json!([r.id, r.group, r.name, st, note, link, auto]));
        }
        secs.push(serde_json::json!({
            "id": s.id, "title": s.title, "description": s.description, "rows": list,
        }));
    }
    let data = serde_json::json!({
        "edit": edit,
        "commit": git(root, &["rev-parse", "--short", "HEAD"]).unwrap_or_default().trim(),
        "repo": repo_url(root),
        "statuses": STATUSES,
        "sections": secs,
        "recent": recent_changes(root, &names),
    });
    Ok(format!("window.TRACKER_DATA = {};\n", serde_json::to_string(&data)?))
}

fn build(root: &Path, data_only: bool) -> Result<()> {
    check(root)?;
    let out = root.join(OUT_DIR);
    if !data_only {
        let site = root.join(SITE_DIR);
        std::fs::copy(root.join(TOKENS), site.join("src/tokens.css"))
            .context("copying tokens.css from the web admin")?;
        if !site.join("node_modules").exists() {
            run_cmd(Command::new("npm").args(["ci"]).current_dir(&site), "npm ci")?;
        }
        run_cmd(
            Command::new("npm").args(["run", "build"]).env("TRACKER_OUT", &out).current_dir(&site),
            "npm run build",
        )?;
    }
    std::fs::write(out.join("data.js"), data_js(root, false)?)?;
    println!("tracker: site in {}", out.display());
    Ok(())
}

fn run_cmd(cmd: &mut Command, what: &str) -> Result<()> {
    let status = cmd.status().with_context(|| format!("starting {what}"))?;
    if !status.success() {
        bail!("{what} failed ({status})");
    }
    Ok(())
}

// ---------------------------------------------------------------------------------------------
// edit

#[derive(Deserialize)]
struct SetRequest {
    id: String,
    status: String,
    #[serde(default)]
    note: String,
    #[serde(default)]
    link: String,
}

/// Applies one edit to `[status]`; `unknown` without a note or link removes the row.
fn apply_edit(root: &Path, req: SetRequest) -> Result<()> {
    if !STATUSES.contains(&req.status.as_str()) {
        bail!("unknown status {:?}", req.status);
    }
    let ids: BTreeSet<String> = all_rows(root)?.into_iter().map(|r| r.id).collect();
    if !ids.contains(&req.id) {
        bail!("no such row {:?}", req.id);
    }
    let mut status = load_status(root)?;
    if status.auto.contains_key(&req.id) {
        bail!("{} has an automatic status", req.id);
    }
    let (note, link) = (req.note.trim().to_owned(), req.link.trim().to_owned());
    if req.status == "unknown" && note.is_empty() && link.is_empty() {
        status.hand.remove(&req.id);
    } else {
        status.hand.insert(req.id, Entry { status: req.status, note, link });
    }
    save_status(root, &status)
}

fn content_type(path: &Path) -> &'static str {
    match path.extension().and_then(|e| e.to_str()) {
        Some("html") => "text/html; charset=utf-8",
        Some("js") => "text/javascript; charset=utf-8",
        Some("css") => "text/css; charset=utf-8",
        Some("svg") => "image/svg+xml",
        Some("json") => "application/json",
        _ => "application/octet-stream",
    }
}

fn respond(stream: &mut TcpStream, code: &str, ctype: &str, body: &[u8]) {
    let head = format!(
        "HTTP/1.1 {code}\r\nContent-Type: {ctype}\r\nContent-Length: {}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n",
        body.len()
    );
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(body);
}

fn handle(root: &Path, out: &Path, stream: TcpStream) -> Result<()> {
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut stream = stream;
    let mut request = String::new();
    reader.read_line(&mut request)?;
    let mut parts = request.split_whitespace();
    let (method, target) = (parts.next().unwrap_or_default(), parts.next().unwrap_or("/"));
    let mut length = 0usize;
    let (mut host_ok, mut json) = (false, false);
    loop {
        let mut line = String::new();
        reader.read_line(&mut line)?;
        let line = line.trim_end();
        if line.is_empty() {
            break;
        }
        let Some((k, v)) = line.split_once(':') else { continue };
        let (k, v) = (k.to_ascii_lowercase(), v.trim());
        match k.as_str() {
            "content-length" => length = v.parse().unwrap_or(0),
            // Not a name an attacker's page can point at 127.0.0.1 (DNS rebinding).
            "host" => host_ok = v.starts_with("127.0.0.1") || v.starts_with("localhost"),
            "content-type" => json = v.starts_with("application/json"),
            _ => {}
        }
    }
    if !host_ok {
        respond(&mut stream, "403 Forbidden", "text/plain", b"bad host");
        return Ok(());
    }
    if method == "POST" && target == "/api/set" {
        // application/json forces a CORS preflight that this server never answers.
        if !json || length > 1 << 20 {
            respond(&mut stream, "400 Bad Request", "text/plain", b"json only");
            return Ok(());
        }
        let mut body = vec![0u8; length];
        reader.read_exact(&mut body)?;
        let result = serde_json::from_slice::<SetRequest>(&body)
            .map_err(anyhow::Error::from)
            .and_then(|req| apply_edit(root, req));
        match result {
            Ok(()) => respond(&mut stream, "200 OK", "application/json", b"{\"ok\":true}"),
            Err(e) => {
                let msg = serde_json::json!({ "ok": false, "error": format!("{e:#}") });
                respond(&mut stream, "400 Bad Request", "application/json", msg.to_string().as_bytes());
            }
        }
        return Ok(());
    }
    if method != "GET" {
        respond(&mut stream, "405 Method Not Allowed", "text/plain", b"");
        return Ok(());
    }
    let path = target.split(['?', '#']).next().unwrap_or("/");
    if path == "/data.js" {
        match data_js(root, true) {
            Ok(js) => respond(&mut stream, "200 OK", "text/javascript; charset=utf-8", js.as_bytes()),
            Err(e) => respond(&mut stream, "500 Internal Server Error", "text/plain", format!("{e:#}").as_bytes()),
        }
        return Ok(());
    }
    let rel = if path == "/" { "index.html" } else { path.trim_start_matches('/') };
    if rel.split('/').any(|c| c == ".." || c.is_empty()) {
        respond(&mut stream, "404 Not Found", "text/plain", b"");
        return Ok(());
    }
    let file = out.join(rel);
    match std::fs::read(&file) {
        Ok(bytes) => respond(&mut stream, "200 OK", content_type(&file), &bytes),
        Err(_) => respond(&mut stream, "404 Not Found", "text/plain", b"not found"),
    }
    Ok(())
}

fn edit(root: &Path, port: u16, no_build: bool) -> Result<()> {
    if !no_build || !root.join(OUT_DIR).join("index.html").exists() {
        build(root, false)?;
    }
    let out = root.join(OUT_DIR);
    let listener = TcpListener::bind(("127.0.0.1", port)).with_context(|| format!("binding 127.0.0.1:{port}"))?;
    println!("tracker editor: http://127.0.0.1:{port}/ (writes {STATUS}; nothing is committed; Ctrl-C to stop)");
    for stream in listener.incoming() {
        let Ok(stream) = stream else { continue };
        if let Err(e) = handle(root, &out, stream) {
            eprintln!("tracker: request failed: {e:#}");
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn natural_order() {
        let mut v = vec!["Act 10", "Act 2", "Act 1 bosses", "Act 1"];
        v.sort_by_key(|s| natural_key(s));
        assert_eq!(v, vec!["Act 1", "Act 1 bosses", "Act 2", "Act 10"]);
    }

    #[test]
    fn entry_lines_round_trip() {
        let e = Entry { status: "partial".into(), note: "a \"b\"".into(), link: String::new() };
        let line = entry_line("proj:x", &e);
        let t: toml::Table = toml::from_str(&line).unwrap();
        assert_eq!(t["proj:x"]["status"].as_str(), Some("partial"));
        assert_eq!(t["proj:x"]["note"].as_str(), Some("a \"b\""));
    }

    #[test]
    fn edits_write_sorted_lines_and_unknown_removes() {
        let dir = std::env::temp_dir().join(format!("tracker-test-{}", std::process::id()));
        std::fs::create_dir_all(dir.join("tracker")).unwrap();
        std::fs::write(
            dir.join(ROWS),
            r#"[{"id":"a:1","section":"s","group":"g","name":"A"},{"id":"a:0","section":"s","group":"g","name":"B"}]"#,
        )
        .unwrap();
        std::fs::write(dir.join(SECTIONS), "section = []\n").unwrap();
        let set = |id: &str, status: &str, note: &str| SetRequest {
            id: id.into(),
            status: status.into(),
            note: note.into(),
            link: String::new(),
        };
        apply_edit(&dir, set("a:1", "partial", "n")).unwrap();
        apply_edit(&dir, set("a:0", "implemented", "")).unwrap();
        let text = std::fs::read_to_string(dir.join(STATUS)).unwrap();
        let (a0, a1) = (text.find("\"a:0\"").unwrap(), text.find("\"a:1\"").unwrap());
        assert!(a0 < a1, "sorted by id");
        assert!(apply_edit(&dir, set("a:2", "partial", "")).is_err());
        assert!(apply_edit(&dir, set("a:1", "bogus", "")).is_err());
        apply_edit(&dir, set("a:1", "unknown", "")).unwrap();
        assert!(!std::fs::read_to_string(dir.join(STATUS)).unwrap().contains("a:1"));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn slugs() {
        assert_eq!(slug("Headhunter's Ring!"), "headhunter_s_ring");
    }
}

//! Checks on the client DLL's live state file (`GameFiles/poe-hook-state.json`, written by
//! poe-hook-core `state_export.rs`) for `expect_state` steps of `cargo xtask game-test`.
//! Format of the file and of the checks: docs/guides/setup.md, "Live state file".

use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Result, bail};
use serde_json::Value;

/// Older states than this are stale (the DLL writes every 250 ms by default).
pub const MAX_AGE_MS: u64 = 3000;

/// Parses the state file and refuses a stale one.
pub fn parse(text: &str) -> Result<Value> {
    let v: Value = serde_json::from_str(text)?;
    let t = v.get("t").and_then(Value::as_u64).unwrap_or(0);
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis() as u64;
    if now.saturating_sub(t) > MAX_AGE_MS {
        bail!("state is {} ms old", now.saturating_sub(t));
    }
    Ok(v)
}

/// `Ok(summary)` when every check holds, else the first one that does not, with what was found.
/// What checks compare against besides the state.
#[derive(Default)]
pub struct Ctx {
    /// Names for `@<vtable>` path segments of `panels` (`scripts/game-test/panels.toml`).
    pub aliases: toml::Table,
    /// The player's grid cell when the previous step started (`moved`).
    pub before: Option<(f64, f64)>,
}

pub fn check(state: &Value, checks: &toml::Table, ctx: &Ctx) -> Result<String, String> {
    let mut seen = Vec::new();
    for (key, want) in checks {
        let got = one(state, key, want, ctx)?;
        seen.push(format!("{key}={got}"));
    }
    Ok(seen.join(" "))
}

fn one(state: &Value, key: &str, want: &toml::Value, ctx: &Ctx) -> Result<String, String> {
    let aliases = &ctx.aliases;
    match key {
        // `area = "G1_1"`: the area id, a whole-id regex (`"G1_.*"`).
        "area" => {
            let id = path(state, "area.id").and_then(Value::as_str).unwrap_or("");
            let w = want.as_str().ok_or("area: want a string")?;
            let re = regex::Regex::new(&format!("^(?:{w})$")).map_err(|e| format!("area: {e}"))?;
            if re.is_match(id) { Ok(id.into()) } else { Err(format!("area is {id:?}, want {w:?}")) }
        }
        // `near = [x, y, r]`: the player's grid cell within r cells of (x, y).
        "near" => {
            let a = want.as_array().filter(|a| a.len() == 3).ok_or("near: want [x, y, r]")?;
            let f = |v: &toml::Value| v.as_float().or(v.as_integer().map(|i| i as f64));
            let (Some(x), Some(y), Some(r)) = (f(&a[0]), f(&a[1]), f(&a[2])) else {
                return Err("near: want numbers".into());
            };
            let (px, py) = grid(state).ok_or("no player")?;
            let d = ((px - x).powi(2) + (py - y).powi(2)).sqrt();
            if d <= r {
                Ok(format!("({px},{py})"))
            } else {
                Err(format!("player at ({px},{py}), {d:.1} cells from ({x},{y}), want <= {r}"))
            }
        }
        // `moved = 10`: at least that many cells from where the player was when the previous
        // step started (the step that walked).
        // `moved_max = 3`: at most that many (a roll or walk into a wall stopped short).
        "moved" | "moved_max" => {
            let n = want.as_float().or(want.as_integer().map(|i| i as f64)).ok_or("moved: want a number")?;
            let (bx, by) = ctx.before.ok_or("moved: no position before the previous step")?;
            let (px, py) = grid(state).ok_or("no player")?;
            let d = ((px - bx).powi(2) + (py - by).powi(2)).sqrt();
            let (ok, op) = if key == "moved" { (d >= n, ">=") } else { (d <= n, "<=") };
            if ok {
                Ok(format!("({bx},{by})->({px},{py}) {d:.1}"))
            } else {
                Err(format!("moved {d:.1} cells ({bx},{by})->({px},{py}), want {op} {n}"))
            }
        }
        // `panel = "inventory"`: a visible UI panel path contains the text; `no_panel`: none does.
        "panel" | "no_panel" => {
            let w = want.as_str().ok_or("panel: want a string")?;
            let panels: Vec<String> = state
                .get("panels")
                .and_then(Value::as_array)
                .map(|a| a.iter().filter_map(Value::as_str).map(|p| named(p, aliases)).collect())
                .unwrap_or_default();
            let hit = panels.iter().find(|p| p.contains(w));
            match (key, hit) {
                ("panel", Some(p)) => Ok(p.clone()),
                ("panel", None) => Err(format!("no visible panel matches {w:?} ({} visible)", panels.len())),
                (_, None) => Ok("none".into()),
                (_, Some(p)) => Err(format!("panel {p:?} is visible")),
            }
        }
        // Any other key: a dotted path into the file (`"player.life.current" = ">= 1"`).
        _ => {
            let got = path(state, key).ok_or_else(|| format!("{key}: not in the state"))?;
            compare(key, got, want).map(|()| short(got))
        }
    }
}

/// A panel path with its `@<vtable>` segments named by `aliases`.
fn named(path: &str, aliases: &toml::Table) -> String {
    path.split('/')
        .map(|seg| aliases.get(seg).and_then(toml::Value::as_str).unwrap_or(seg))
        .collect::<Vec<_>>()
        .join("/")
}

pub fn grid(state: &Value) -> Option<(f64, f64)> {
    let g = path(state, "player.grid")?.as_array()?;
    Some((g.first()?.as_f64()?, g.get(1)?.as_f64()?))
}

fn path<'a>(v: &'a Value, dotted: &str) -> Option<&'a Value> {
    dotted.split('.').try_fold(v, |v, part| match part.parse::<usize>() {
        Ok(i) if v.is_array() => v.get(i),
        _ => v.get(part),
    })
}

fn short(v: &Value) -> String {
    let s = v.to_string();
    if s.len() > 60 { format!("{}...", &s[..60]) } else { s }
}

/// A string starting with `>=`, `<=`, `>`, `<`, `==` or `!=` compares numbers; anything else is
/// equality (strings exact, numbers numerically, booleans).
fn compare(key: &str, got: &Value, want: &toml::Value) -> Result<(), String> {
    let fail = || Err(format!("{key} is {}, want {want}", short(got)));
    match want {
        toml::Value::String(s) => {
            for op in [">=", "<=", "==", "!=", ">", "<"] {
                if let Some(rest) = s.strip_prefix(op)
                    && let Ok(n) = rest.trim().parse::<f64>()
                {
                    let Some(g) = got.as_f64() else { return fail() };
                    let ok = match op {
                        ">=" => g >= n,
                        "<=" => g <= n,
                        "==" => g == n,
                        "!=" => g != n,
                        ">" => g > n,
                        _ => g < n,
                    };
                    return if ok { Ok(()) } else { fail() };
                }
            }
            if got.as_str() == Some(s.as_str()) { Ok(()) } else { fail() }
        }
        toml::Value::Integer(i) if got.as_f64() == Some(*i as f64) => Ok(()),
        toml::Value::Float(f) if got.as_f64() == Some(*f) => Ok(()),
        toml::Value::Boolean(b) if got.as_bool() == Some(*b) => Ok(()),
        _ => fail(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state() -> Value {
        serde_json::json!({
            "t": 0, "area": {"id": "G1_town", "name": "Clearfell Encampment"},
            "player": {"grid": [100, 200], "life": {"current": 28, "max": 28}, "action": ""},
            "panels": ["escape_menu", "root/@1/@2/label_title"],
        })
    }

    fn t(s: &str) -> toml::Table {
        toml::from_str(s).unwrap()
    }

    #[test]
    fn checks() {
        let s = state();
        let ctx = Ctx { aliases: t(r#""@2" = "inventory""#), before: Some((100.0, 190.0)) };
        let check = |s: &Value, c: &toml::Table| super::check(s, c, &ctx);
        assert!(check(&s, &t("moved = 10")).is_ok());
        assert!(check(&s, &t("moved = 10.5")).is_err());
        assert!(check(&s, &t("moved_max = 10")).is_ok());
        assert!(check(&s, &t("moved_max = 9.5")).is_err());
        assert!(check(&s, &t(r#"area = "G1_town""#)).is_ok());
        assert!(check(&s, &t(r#"area = "G1_1""#)).is_err());
        assert!(check(&s, &t(r#"area = "G1_.*""#)).is_ok());
        assert!(check(&s, &t(r#"area = "G1""#)).is_err());
        assert!(check(&s, &t("near = [103, 204, 5]")).is_ok());
        assert!(check(&s, &t("near = [103, 204, 4.9]")).is_err());
        assert!(check(&s, &t(r#""player.life.current" = ">= 1""#)).is_ok());
        assert!(check(&s, &t(r#""player.life.current" = "< 28""#)).is_err());
        assert!(check(&s, &t(r#""player.life.max" = 28"#)).is_ok());
        assert!(check(&s, &t(r#""player.grid.0" = 100"#)).is_ok());
        assert!(check(&s, &t(r#"panel = "inventory""#)).is_ok());
        assert!(check(&s, &t(r#"no_panel = "inventory""#)).is_err());
        assert!(check(&s, &t(r#"no_panel = "social""#)).is_ok());
        assert!(check(&s, &t(r#""player.missing" = 1"#)).is_err());
    }

    #[test]
    fn stale() {
        assert!(parse(r#"{"t": 1}"#).is_err());
    }
}

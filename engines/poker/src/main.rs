//! Command-line front end used by the hub's API (it runs this binary and reads JSON).
//!
//!   poker-engine equity --hands AhKh,random,QsQd [--board Td9s2c] [--trials 200000]
//!   poker-engine preflop-table [--trials 200000] [--max-opponents 9]
//!   poker-engine eval AhKhQhJhTh2c3d

mod cards;
mod equity;
mod eval;

use std::collections::HashMap;
use std::process::ExitCode;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use cards::{card, parse_cards, Card, RANKS};
use equity::{run, Spec};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let result = match args.first().map(String::as_str) {
        Some("equity") => cmd_equity(&flags(&args[1..])),
        Some("preflop-table") => cmd_preflop(&flags(&args[1..])),
        Some("eval") if args.len() == 2 => cmd_eval(&args[1]),
        _ => Err("usage: poker-engine equity|preflop-table|eval ...".to_string()),
    };
    match result {
        Ok(json) => {
            println!("{json}");
            ExitCode::SUCCESS
        }
        Err(msg) => {
            eprintln!("{msg}");
            ExitCode::from(2)
        }
    }
}

fn flags(args: &[String]) -> HashMap<String, String> {
    args.chunks(2)
        .filter(|c| c.len() == 2 && c[0].starts_with("--"))
        .map(|c| (c[0].trim_start_matches("--").to_string(), c[1].clone()))
        .collect()
}

fn num<T: std::str::FromStr>(
    f: &HashMap<String, String>,
    key: &str,
    default: T,
) -> Result<T, String> {
    match f.get(key) {
        None => Ok(default),
        Some(v) => v.parse().map_err(|_| format!("--{key} must be a number")),
    }
}

fn threads() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(1)
}

fn seed() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(1)
}

fn cmd_equity(f: &HashMap<String, String>) -> Result<String, String> {
    let hands_arg = f.get("hands").ok_or("--hands is required")?;
    let mut hands = Vec::new();
    for h in hands_arg.split(',') {
        let h = h.trim();
        if h.is_empty() || h.eq_ignore_ascii_case("random") {
            hands.push(None);
        } else {
            let c = parse_cards(h)?;
            if c.len() != 2 {
                return Err(format!("a hand is two cards, got {h:?}"));
            }
            hands.push(Some([c[0], c[1]]));
        }
    }
    let board = parse_cards(f.get("board").map(String::as_str).unwrap_or(""))?;
    let trials: u64 = num(f, "trials", 200_000)?;
    if !(1_000..=5_000_000).contains(&trials) {
        return Err("--trials must be between 1,000 and 5,000,000".into());
    }
    let spec = Spec {
        hands,
        board,
        trials,
        threads: threads(),
        seed: num(f, "seed", seed())?,
    };
    let start = Instant::now();
    let out = run(&spec)?;
    let n = out.tally.samples as f64;
    let players: Vec<String> = (0..spec.hands.len())
        .map(|i| {
            format!(
                r#"{{"win":{:.6},"tie":{:.6},"equity":{:.6}}}"#,
                out.tally.wins[i] / n,
                out.tally.ties[i] / n,
                out.tally.equity[i] / n
            )
        })
        .collect();
    Ok(format!(
        r#"{{"exact":{},"samples":{},"millis":{},"players":[{}]}}"#,
        out.exact,
        out.tally.samples,
        start.elapsed().as_millis(),
        players.join(",")
    ))
}

/// The 169 distinct starting hands, strongest-looking first: pairs, then suited, then offsuit.
fn starting_hands() -> Vec<(String, [Card; 2])> {
    let mut out = Vec::new();
    for hi in (0..13u8).rev() {
        for lo in (0..=hi).rev() {
            let (h, l) = (RANKS[hi as usize] as char, RANKS[lo as usize] as char);
            if hi == lo {
                out.push((format!("{h}{l}"), [card(hi, 0), card(lo, 1)]));
            } else {
                out.push((format!("{h}{l}s"), [card(hi, 0), card(lo, 0)]));
                out.push((format!("{h}{l}o"), [card(hi, 0), card(lo, 1)]));
            }
        }
    }
    out
}

fn cmd_preflop(f: &HashMap<String, String>) -> Result<String, String> {
    let trials: u64 = num(f, "trials", 200_000)?;
    let max_opp: usize = num(f, "max-opponents", 9)?;
    if !(1..=9).contains(&max_opp) {
        return Err("--max-opponents must be 1 to 9".into());
    }
    let base_seed: u64 = num(f, "seed", 1)?;
    let mut rows = Vec::new();
    for (i, (name, hand)) in starting_hands().into_iter().enumerate() {
        let mut eqs = Vec::new();
        for opp in 1..=max_opp {
            let mut hands = vec![Some(hand)];
            hands.extend(std::iter::repeat_n(None, opp));
            let spec = Spec {
                hands,
                board: vec![],
                trials,
                threads: threads(),
                seed: base_seed
                    .wrapping_mul(1_000_003)
                    .wrapping_add((i * 10 + opp) as u64),
            };
            let out = run(&spec)?;
            eqs.push(format!(
                "{:.4}",
                out.tally.equity[0] / out.tally.samples as f64
            ));
        }
        rows.push(format!(
            r#"{{"hand":"{name}","equity":[{}]}}"#,
            eqs.join(",")
        ));
        eprintln!("{name} done");
    }
    Ok(format!(
        r#"{{"trials":{trials},"hands":[{}]}}"#,
        rows.join(",\n")
    ))
}

fn cmd_eval(text: &str) -> Result<String, String> {
    let c = parse_cards(text)?;
    if !(5..=7).contains(&c.len()) {
        return Err("give 5 to 7 cards".into());
    }
    let v = eval::evaluate(&c);
    Ok(format!(
        r#"{{"value":{v},"category":"{}"}}"#,
        eval::CATEGORY_NAMES[eval::category(v) as usize]
    ))
}

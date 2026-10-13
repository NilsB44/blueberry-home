//! Equity: each player's share of the pot when all cards are dealt out.
//! Exact enumeration when every hand is known and the boards are few enough,
//! otherwise Monte Carlo across all CPU cores.

use std::thread;

use crate::cards::Card;
use crate::eval::evaluate;

/// Enumerate exactly when there are at most this many boards (C(48,5) is 1.7M).
const EXACT_LIMIT: u64 = 2_000_000;

#[derive(Clone, Debug)]
pub struct Spec {
    /// One entry per player; `None` is a random hand.
    pub hands: Vec<Option<[Card; 2]>>,
    pub board: Vec<Card>,
    pub trials: u64,
    pub threads: usize,
    pub seed: u64,
}

#[derive(Clone, Debug, Default)]
pub struct Tally {
    pub wins: Vec<f64>,
    pub ties: Vec<f64>,
    pub equity: Vec<f64>,
    pub samples: u64,
}

impl Tally {
    fn new(players: usize) -> Self {
        Tally {
            wins: vec![0.0; players],
            ties: vec![0.0; players],
            equity: vec![0.0; players],
            samples: 0,
        }
    }

    fn merge(&mut self, other: &Tally) {
        for i in 0..self.wins.len() {
            self.wins[i] += other.wins[i];
            self.ties[i] += other.ties[i];
            self.equity[i] += other.equity[i];
        }
        self.samples += other.samples;
    }

    /// Score one showdown given each player's 7-card value.
    fn record(&mut self, values: &[u32]) {
        let best = *values.iter().max().unwrap();
        let winners = values.iter().filter(|&&v| v == best).count();
        for (i, &v) in values.iter().enumerate() {
            if v == best {
                if winners == 1 {
                    self.wins[i] += 1.0;
                } else {
                    self.ties[i] += 1.0;
                }
                self.equity[i] += 1.0 / winners as f64;
            }
        }
        self.samples += 1;
    }
}

#[derive(Debug)]
pub struct Outcome {
    pub tally: Tally,
    pub exact: bool,
}

pub fn validate(spec: &Spec) -> Result<(), String> {
    if !(2..=10).contains(&spec.hands.len()) {
        return Err("need 2 to 10 players".into());
    }
    if spec.board.len() > 5 {
        return Err("a board has at most 5 cards".into());
    }
    let mut seen = [false; 52];
    for &c in spec
        .hands
        .iter()
        .flatten()
        .flatten()
        .chain(spec.board.iter())
    {
        if seen[c as usize] {
            return Err(format!("{} is used twice", crate::cards::name(c)));
        }
        seen[c as usize] = true;
    }
    Ok(())
}

fn remaining_deck(spec: &Spec) -> Vec<Card> {
    let mut used = [false; 52];
    for &c in spec
        .hands
        .iter()
        .flatten()
        .flatten()
        .chain(spec.board.iter())
    {
        used[c as usize] = true;
    }
    (0..52u8).filter(|&c| !used[c as usize]).collect()
}

fn choose(n: u64, k: u64) -> u64 {
    if k > n {
        return 0;
    }
    (0..k).fold(1u64, |acc, i| acc * (n - i) / (i + 1))
}

pub fn run(spec: &Spec) -> Result<Outcome, String> {
    validate(spec)?;
    let deck = remaining_deck(spec);
    let missing = 5 - spec.board.len();
    let all_known = spec.hands.iter().all(Option::is_some);
    if all_known && choose(deck.len() as u64, missing as u64) <= EXACT_LIMIT {
        Ok(Outcome {
            tally: enumerate(spec, &deck, missing),
            exact: true,
        })
    } else {
        Ok(Outcome {
            tally: monte_carlo(spec, &deck, missing),
            exact: false,
        })
    }
}

fn showdown(hands: &[[Card; 2]], board: &[Card; 5], values: &mut Vec<u32>) {
    values.clear();
    let mut seven = [0u8; 7];
    seven[2..].copy_from_slice(board);
    for h in hands {
        seven[0] = h[0];
        seven[1] = h[1];
        values.push(evaluate(&seven));
    }
}

fn enumerate(spec: &Spec, deck: &[Card], missing: usize) -> Tally {
    let hands: Vec<[Card; 2]> = spec.hands.iter().map(|h| h.unwrap()).collect();
    let mut board = [0u8; 5];
    board[..spec.board.len()].copy_from_slice(&spec.board);
    let known = spec.board.len();
    let mut tally = Tally::new(hands.len());
    if missing == 0 {
        let mut values = Vec::new();
        showdown(&hands, &board, &mut values);
        tally.record(&values);
        return tally;
    }

    // Split on the first missing card so each thread gets a slice of the boards.
    let threads = spec.threads.max(1);
    let firsts: Vec<usize> = (0..deck.len()).collect();
    let chunks: Vec<Vec<usize>> = (0..threads)
        .map(|t| {
            firsts
                .iter()
                .copied()
                .filter(|i| i % threads == t)
                .collect()
        })
        .collect();
    thread::scope(|s| {
        let handles: Vec<_> = chunks
            .into_iter()
            .map(|chunk| {
                let hands = &hands;
                s.spawn(move || {
                    let mut local = Tally::new(hands.len());
                    let mut values = Vec::with_capacity(hands.len());
                    let mut b = board;
                    let mut idx = vec![0usize; missing];
                    for first in chunk {
                        idx[0] = first;
                        combos(deck, &mut idx, 1, missing, known, &mut b, &mut |b| {
                            showdown(hands, b, &mut values);
                            local.record(&values);
                        });
                    }
                    local
                })
            })
            .collect();
        for h in handles {
            tally.merge(&h.join().unwrap());
        }
    });
    tally
}

/// Visit every way to fill board slots known.. with increasing deck indexes (idx[0] fixed).
fn combos(
    deck: &[Card],
    idx: &mut Vec<usize>,
    depth: usize,
    missing: usize,
    known: usize,
    board: &mut [Card; 5],
    visit: &mut dyn FnMut(&[Card; 5]),
) {
    if depth == missing {
        for (k, &i) in idx.iter().enumerate() {
            board[known + k] = deck[i];
        }
        visit(board);
        return;
    }
    for i in idx[depth - 1] + 1..deck.len() {
        idx[depth] = i;
        combos(deck, idx, depth + 1, missing, known, board, visit);
    }
}

/// xorshift64*: tiny, fast, and good enough for dealing cards.
pub struct Rng(u64);

impl Rng {
    pub fn new(seed: u64) -> Self {
        Rng(seed.max(1))
    }

    pub fn next(&mut self) -> u64 {
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        self.0.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    pub fn below(&mut self, n: usize) -> usize {
        (((self.next() >> 32) * n as u64) >> 32) as usize
    }
}

fn monte_carlo(spec: &Spec, deck: &[Card], missing: usize) -> Tally {
    let threads = spec.threads.max(1);
    let per_thread = spec.trials.div_ceil(threads as u64);
    let mut tally = Tally::new(spec.hands.len());
    thread::scope(|s| {
        let handles: Vec<_> = (0..threads)
            .map(|t| {
                s.spawn(move || {
                    let mut rng = Rng::new(
                        spec.seed
                            .wrapping_add(0x9E37_79B9_7F4A_7C15 * (t as u64 + 1)),
                    );
                    let mut local = Tally::new(spec.hands.len());
                    let mut cards = deck.to_vec();
                    let mut hands: Vec<[Card; 2]> = vec![[0, 0]; spec.hands.len()];
                    let mut board = [0u8; 5];
                    board[..spec.board.len()].copy_from_slice(&spec.board);
                    let mut values = Vec::with_capacity(spec.hands.len());
                    for _ in 0..per_thread {
                        // Partial Fisher-Yates: draw only the cards this trial needs.
                        let mut drawn = 0;
                        let mut draw = |cards: &mut Vec<Card>, rng: &mut Rng| {
                            let j = drawn + rng.below(cards.len() - drawn);
                            cards.swap(drawn, j);
                            drawn += 1;
                            cards[drawn - 1]
                        };
                        for (p, h) in spec.hands.iter().enumerate() {
                            hands[p] = match h {
                                Some(h) => *h,
                                None => [draw(&mut cards, &mut rng), draw(&mut cards, &mut rng)],
                            };
                        }
                        for k in 0..missing {
                            board[spec.board.len() + k] = draw(&mut cards, &mut rng);
                        }
                        showdown(&hands, &board, &mut values);
                        local.record(&values);
                    }
                    local
                })
            })
            .collect();
        for h in handles {
            tally.merge(&h.join().unwrap());
        }
    });
    tally
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cards::parse_cards;

    fn hand(s: &str) -> Option<[Card; 2]> {
        let c = parse_cards(s).unwrap();
        Some([c[0], c[1]])
    }

    fn spec(hands: Vec<Option<[Card; 2]>>, board: &str, trials: u64) -> Spec {
        Spec {
            hands,
            board: parse_cards(board).unwrap(),
            trials,
            threads: 4,
            seed: 7,
        }
    }

    #[test]
    fn aces_vs_kings_exact() {
        let out = run(&spec(vec![hand("AsAh"), hand("KsKh")], "", 0)).unwrap();
        assert!(out.exact);
        assert_eq!(out.tally.samples, 1_712_304);
        let eq = out.tally.equity[0] / out.tally.samples as f64;
        // Well-known figure: about 82.4% (suit overlap varies it slightly).
        assert!((eq - 0.8236).abs() < 0.003, "{eq}");
    }

    #[test]
    fn river_is_deterministic() {
        let out = run(&spec(vec![hand("AsKs"), hand("QdQc")], "Kd7d2c9hTh", 0)).unwrap();
        assert_eq!(out.tally.samples, 1);
        assert_eq!(out.tally.equity, vec![1.0, 0.0]);
    }

    #[test]
    fn split_pot_on_board() {
        let out = run(&spec(vec![hand("2c3d"), hand("2h3s")], "AhKdQcJsTh", 0)).unwrap();
        assert_eq!(out.tally.equity, vec![0.5, 0.5]);
        assert_eq!(out.tally.ties, vec![1.0, 1.0]);
    }

    #[test]
    fn aces_vs_random_monte_carlo() {
        let out = run(&spec(vec![hand("AsAh"), None], "", 400_000)).unwrap();
        assert!(!out.exact);
        let eq = out.tally.equity[0] / out.tally.samples as f64;
        assert!((eq - 0.852).abs() < 0.005, "{eq}");
    }

    #[test]
    fn rejects_duplicates() {
        assert!(run(&spec(vec![hand("AsAh"), hand("AsKd")], "", 0)).is_err());
    }

    #[test]
    fn rng_covers_range() {
        let mut rng = Rng::new(1);
        let mut seen = [false; 10];
        for _ in 0..1000 {
            seen[rng.below(10)] = true;
        }
        assert!(seen.iter().all(|&s| s));
    }
}

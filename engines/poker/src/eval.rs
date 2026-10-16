//! Seven-card hand evaluation. Returns a `u32` where a bigger number is a better hand:
//! the category sits in bits 20+, and up to five tie-breaking ranks follow, four bits each.

use crate::cards::{rank, suit, Card};

pub const HIGH_CARD: u32 = 0;
pub const PAIR: u32 = 1;
pub const TWO_PAIR: u32 = 2;
pub const TRIPS: u32 = 3;
pub const STRAIGHT: u32 = 4;
pub const FLUSH: u32 = 5;
pub const FULL_HOUSE: u32 = 6;
pub const QUADS: u32 = 7;
pub const STRAIGHT_FLUSH: u32 = 8;

pub const CATEGORY_NAMES: [&str; 9] = [
    "high card",
    "pair",
    "two pair",
    "three of a kind",
    "straight",
    "flush",
    "full house",
    "four of a kind",
    "straight flush",
];

pub fn category(value: u32) -> u32 {
    value >> 20
}

fn make(cat: u32, ranks: &[u8]) -> u32 {
    let mut v = cat << 20;
    for (i, &r) in ranks.iter().enumerate() {
        v |= (r as u32) << (16 - 4 * i);
    }
    v
}

/// Highest rank of a five-in-a-row in `mask` (bit = rank), counting A-2-3-4-5 as 5-high.
fn straight_high(mask: u16) -> Option<u8> {
    for hi in (4..=12u8).rev() {
        if (mask >> (hi - 4)) & 0x1F == 0x1F {
            return Some(hi);
        }
    }
    const WHEEL: u16 = (1 << 12) | 0b1111;
    (mask & WHEEL == WHEEL).then_some(3)
}

fn top_ranks(mask: u16, n: usize) -> Vec<u8> {
    (0..13u8)
        .rev()
        .filter(|r| mask & (1 << r) != 0)
        .take(n)
        .collect()
}

pub fn evaluate(cards: &[Card]) -> u32 {
    let mut suit_masks = [0u16; 4];
    let mut counts = [0u8; 13];
    for &c in cards {
        suit_masks[suit(c) as usize] |= 1 << rank(c);
        counts[rank(c) as usize] += 1;
    }

    for &m in &suit_masks {
        if m.count_ones() >= 5 {
            // Five suited cards leave at most two others, too few for quads or a full house,
            // so a flush (or straight flush) is the best hand here.
            if let Some(hi) = straight_high(m) {
                return make(STRAIGHT_FLUSH, &[hi]);
            }
            return make(FLUSH, &top_ranks(m, 5));
        }
    }

    let (mut quad, mut trips, mut pairs) = (None, Vec::new(), Vec::new());
    for r in (0..13u8).rev() {
        match counts[r as usize] {
            4 => quad = Some(r),
            3 => trips.push(r),
            2 => pairs.push(r),
            _ => {}
        }
    }
    let rank_mask = suit_masks.iter().fold(0u16, |a, m| a | m);
    let kickers = |exclude: &[u8], n: usize| -> Vec<u8> {
        (0..13u8)
            .rev()
            .filter(|r| counts[*r as usize] > 0 && !exclude.contains(r))
            .take(n)
            .collect()
    };

    if let Some(q) = quad {
        return make(QUADS, &[q, kickers(&[q], 1)[0]]);
    }
    if !trips.is_empty() && (trips.len() >= 2 || !pairs.is_empty()) {
        let t = trips[0];
        let p = match (trips.get(1), pairs.first()) {
            (Some(&a), Some(&b)) => a.max(b),
            (Some(&a), None) => a,
            (None, Some(&b)) => b,
            (None, None) => unreachable!(),
        };
        return make(FULL_HOUSE, &[t, p]);
    }
    if let Some(hi) = straight_high(rank_mask) {
        return make(STRAIGHT, &[hi]);
    }
    if let Some(&t) = trips.first() {
        let k = kickers(&[t], 2);
        return make(TRIPS, &[t, k[0], k[1]]);
    }
    if pairs.len() >= 2 {
        let (p1, p2) = (pairs[0], pairs[1]);
        return make(TWO_PAIR, &[p1, p2, kickers(&[p1, p2], 1)[0]]);
    }
    if let Some(&p) = pairs.first() {
        let k = kickers(&[p], 3);
        return make(PAIR, &[p, k[0], k[1], k[2]]);
    }
    make(HIGH_CARD, &top_ranks(rank_mask, 5))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cards::parse_cards;

    fn ev(s: &str) -> u32 {
        evaluate(&parse_cards(s).unwrap())
    }

    fn cat(s: &str) -> u32 {
        category(ev(s))
    }

    #[test]
    fn categories() {
        assert_eq!(cat("AhKhQhJhTh2c3d"), STRAIGHT_FLUSH);
        assert_eq!(cat("Ah2h3h4h5h9c9d"), STRAIGHT_FLUSH);
        assert_eq!(cat("9c9d9h9sKh2c3d"), QUADS);
        assert_eq!(cat("9c9d9hKsKh2c3d"), FULL_HOUSE);
        assert_eq!(cat("9c9d9hKsKhKc3d"), FULL_HOUSE);
        assert_eq!(cat("Ah9h7h4h2h9c9d"), FLUSH);
        assert_eq!(cat("Ah2c3d4s5h9c9d"), STRAIGHT);
        assert_eq!(cat("9c9d9hKs2h4c7d"), TRIPS);
        assert_eq!(cat("9c9dKhKs2h2c7d"), TWO_PAIR);
        assert_eq!(cat("9c9dKhQs2h3c7d"), PAIR);
        assert_eq!(cat("AcJd9h7s5h3c2d"), HIGH_CARD);
    }

    #[test]
    fn tie_breaks() {
        // Wheel loses to 6-high straight.
        assert!(ev("Ah2c3d4s5h") < ev("2c3d4s5h6d"));
        // Better kicker wins.
        assert!(ev("AhAdKc7s2h") > ev("AhAdQc7s2h"));
        // Two pair kicker uses the best remaining card, even from a third pair.
        assert_eq!(ev("KhKd9c9s5h5dAc"), ev("KhKd9c9sAc2d3h"));
        // Boat: trips over the higher of a second trips or pair.
        assert_eq!(ev("9c9d9hKsKhKc3d"), ev("KsKhKc9c9d2h3d"));
        // Board plays: identical values.
        assert_eq!(ev("AhKdQcJsTh2c3d"), ev("AhKdQcJsTh4c5d"));
        // Flush compares all five cards.
        assert!(ev("Ah9h7h4h3h") > ev("Ah9h7h4h2h"));
    }
}

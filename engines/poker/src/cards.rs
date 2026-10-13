//! Cards are a `u8` in 0..52: rank * 4 + suit, with rank 0 = deuce .. 12 = ace.

pub type Card = u8;

pub const RANKS: &[u8; 13] = b"23456789TJQKA";
pub const SUITS: &[u8; 4] = b"cdhs";

pub fn rank(c: Card) -> u8 {
    c / 4
}

pub fn suit(c: Card) -> u8 {
    c % 4
}

pub fn card(rank: u8, suit: u8) -> Card {
    rank * 4 + suit
}

pub fn name(c: Card) -> String {
    format!(
        "{}{}",
        RANKS[rank(c) as usize] as char,
        SUITS[suit(c) as usize] as char
    )
}

fn parse_rank(ch: char) -> Option<u8> {
    RANKS
        .iter()
        .position(|&r| r as char == ch.to_ascii_uppercase())
        .map(|p| p as u8)
}

fn parse_suit(ch: char) -> Option<u8> {
    SUITS
        .iter()
        .position(|&s| s as char == ch.to_ascii_lowercase())
        .map(|p| p as u8)
}

/// Parse a run of cards like "AhKd" or "Td 9s 2c" (also accepts "10h").
pub fn parse_cards(text: &str) -> Result<Vec<Card>, String> {
    let cleaned: String = text
        .replace("10", "T")
        .chars()
        .filter(|c| !c.is_whitespace())
        .collect();
    let chars: Vec<char> = cleaned.chars().collect();
    if !chars.len().is_multiple_of(2) {
        return Err(format!("can't read cards from {text:?}"));
    }
    chars
        .chunks(2)
        .map(|pair| match (parse_rank(pair[0]), parse_suit(pair[1])) {
            (Some(r), Some(s)) => Ok(card(r, s)),
            _ => Err(format!("unknown card {}{}", pair[0], pair[1])),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips() {
        for c in 0..52 {
            assert_eq!(parse_cards(&name(c)).unwrap(), vec![c]);
        }
    }

    #[test]
    fn parses_variants() {
        assert_eq!(parse_cards("ah 10d").unwrap(), parse_cards("AhTd").unwrap());
        assert!(parse_cards("Ax").is_err());
        assert!(parse_cards("A").is_err());
    }
}

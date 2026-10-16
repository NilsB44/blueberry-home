import { combos, RANKS } from './cards.ts';

/**
 * Standard pre-flop ranges, simplified from common solver charts. "Open" spots are raise-first-in:
 * everyone before you folded, so you raise (to about 2.5 big blinds) or fold.
 */

export type GameType = 'hu' | '6max' | '9max';
export type Spot = { id: string; label: string; kind: 'open' | 'defend'; note: string; range: string };
export type Game = { label: string; seats: string[]; spots: Spot[] };

// Shared late-position ranges: the same in 6-max and full ring once the early seats have folded.
const HJ = '44+, A2s+, K8s+, Q9s+, J9s+, T8s+, 97s+, 87s, 76s, 65s, ATo+, KJo+, QJo';
const CO = '22+, A2s+, K5s+, Q8s+, J8s+, T8s+, 97s+, 86s+, 75s+, 65s, 54s, A8o+, KTo+, QTo+, JTo';
const BTN = '22+, A2s+, K2s+, Q4s+, J6s+, T6s+, 96s+, 85s+, 74s+, 64s+, 53s+, 43s, A2o+, K8o+, Q9o+, J9o+, T9o, 98o';
const SB = '22+, A2s+, K3s+, Q5s+, J7s+, T7s+, 97s+, 86s+, 75s+, 64s+, 54s, A2o+, K9o+, Q9o+, J9o+, T9o';

const open = (id: string, range: string, note = ''): Spot => ({ id, label: id, kind: 'open', note, range });

export const GAMES: Record<GameType, Game> = {
	hu: {
		label: 'Heads-up',
		seats: ['BTN', 'BB'],
		spots: [
			open('BTN', '22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 92s+, 82s+, 73s+, 62s+, 52s+, 42s+, 32s, A2o+, K2o+, Q2o+, J2o+, T5o+, 95o+, 85o+, 75o+, 64o+, 54o', 'The button is the small blind and acts first pre-flop.'),
			{
				id: 'BB',
				label: 'BB defend',
				kind: 'defend',
				note: 'Facing a 2.5× raise from the button: continue (call or re-raise) with these, fold the rest.',
				range: '22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 92s+, 82s+, 72s+, 62s+, 52s+, 42s+, 32s, A2o+, K2o+, Q2o+, J4o+, T6o+, 96o+, 86o+, 75o+, 65o, 54o'
			}
		]
	},
	'6max': {
		label: '6-max',
		seats: ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
		spots: [open('UTG', '55+, A2s+, K9s+, Q9s+, J9s+, T9s, 98s, 87s, 76s, ATo+, KJo+'), open('HJ', HJ), open('CO', CO), open('BTN', BTN), open('SB', SB, 'Raise or fold against the big blind; no limping.')]
	},
	'9max': {
		label: 'Full ring',
		seats: ['UTG', 'UTG+1', 'MP', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
		spots: [
			open('UTG', '77+, ATs+, KTs+, QTs+, JTs, AQo+'),
			open('UTG+1', '66+, A9s+, KTs+, QTs+, JTs, T9s, AJo+, KQo'),
			open('MP', '55+, A7s+, K9s+, Q9s+, J9s+, T9s, 98s, AJo+, KQo'),
			open('LJ', '55+, A2s+, K9s+, Q9s+, J9s+, T9s, 98s, 87s, ATo+, KJo+'),
			open('HJ', HJ),
			open('CO', CO),
			open('BTN', BTN),
			open('SB', SB, 'Raise or fold against the big blind; no limping.')
		]
	}
};

/** Who continues against your open in the practice game: tight from the field, wide from the blinds. */
export const CONTINUE = {
	field: '22+, A9s+, KTs+, QTs+, JTs, T9s, 98s, ATo+, KJo+',
	SB: '22+, A2s+, K9s+, Q9s+, J9s+, T9s, 98s, 87s, A9o+, KTo+, QJo'
};

const rank = (r: string) => RANKS.indexOf(r); // 0 = A, 12 = 2

/** Expand range notation ("22+, A2s+, KTo+, T9s") into the set of chart hands it covers. */
export function parseRange(text: string): Set<string> {
	const out = new Set<string>();
	for (const raw of text.split(',')) {
		const part = raw.trim();
		if (!part) continue;
		const m = /^([AKQJT2-9])([AKQJT2-9])([so]?)(\+?)$/.exec(part);
		if (!m) throw new Error(`bad range part ${part}`);
		const [, a, b, suit, plus] = m;
		if (a === b) {
			// Pairs: "55+" is 55 up to AA.
			for (let i = rank(a); i >= (plus ? 0 : rank(a)); i--) out.add(RANKS[i] + RANKS[i]);
			continue;
		}
		const hi = rank(a);
		// Non-pairs: "K9s+" raises the kicker up to one below the top card (K9s..KQs).
		for (let k = rank(b); k > (plus ? hi : rank(b) - 1); k--) out.add(`${a}${RANKS[k]}${suit}`);
	}
	return out;
}

const cache = new Map<string, Set<string>>();
export function rangeSet(text: string): Set<string> {
	let s = cache.get(text);
	if (!s) cache.set(text, (s = parseRange(text)));
	return s;
}

/** Share of all 1,326 starting combos a range covers. */
export const rangeShare = (set: Set<string>) => [...set].reduce((n, h) => n + combos(h), 0) / 1326;

/** Chart hand ("AKs", "T9o", "77") for two concrete cards like "Ah", "Kh". */
export function handOf(c1: string, c2: string): string {
	const [hi, lo] = rank(c1[0]) <= rank(c2[0]) ? [c1, c2] : [c2, c1];
	if (hi[0] === lo[0]) return hi[0] + lo[0];
	return `${hi[0]}${lo[0]}${hi[1] === lo[1] ? 's' : 'o'}`;
}

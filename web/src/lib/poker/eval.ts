import { RANKS, SUITS, type Card } from './cards.ts';

/** A small 7-card evaluator for the practice game. Higher score wins; equal scores split. */

export const CATEGORY = ['High card', 'Pair', 'Two pair', 'Three of a kind', 'Straight', 'Flush', 'Full house', 'Four of a kind', 'Straight flush'];

const value = (c: Card) => 14 - RANKS.indexOf(c[0]); // A = 14 … 2 = 2

function score5(cards: Card[]): number {
	const vals = cards.map(value).sort((a, b) => b - a);
	const flush = cards.every((c) => c[1] === cards[0][1]);
	const uniq = [...new Set(vals)];
	let top = 0;
	if (uniq.length === 5) {
		if (vals[0] - vals[4] === 4) top = vals[0];
		else if (vals[0] === 14 && vals[1] === 5) top = 5; // the wheel, A-2-3-4-5
	}
	const counts = new Map<number, number>();
	for (const v of vals) counts.set(v, (counts.get(v) ?? 0) + 1);
	// Tie-break order: bigger groups first, then higher ranks.
	const groups = [...counts].sort((a, b) => b[1] - a[1] || b[0] - a[0]);
	const shape = groups.map((g) => g[1]).join('');

	let cat: number;
	let kickers = groups.map((g) => g[0]);
	if (top && flush) [cat, kickers] = [8, [top]];
	else if (shape === '41') cat = 7;
	else if (shape === '32') cat = 6;
	else if (flush) cat = 5;
	else if (top) [cat, kickers] = [4, [top]];
	else if (shape === '311') cat = 3;
	else if (shape === '221') cat = 2;
	else if (shape === '2111') cat = 1;
	else cat = 0;
	return kickers.reduce((s, k, i) => s + k * 15 ** (4 - i), cat * 15 ** 5);
}

/** Best five-card score out of 5–7 cards. */
export function score(cards: Card[]): number {
	if (cards.length === 5) return score5(cards);
	let best = 0;
	for (let i = 0; i < cards.length; i++) best = Math.max(best, score(cards.filter((_, j) => j !== i)));
	return best;
}

export const categoryOf = (s: number) => CATEGORY[Math.floor(s / 15 ** 5)];

export const DECK: Card[] = RANKS.flatMap((r) => SUITS.map((s) => r + s));

/** Draw n cards not in `used`, uniformly at random. */
export function draw(n: number, used: Iterable<Card>, rand = Math.random): Card[] {
	const taken = new Set(used);
	const left = DECK.filter((c) => !taken.has(c));
	for (let i = 0; i < n; i++) {
		const j = i + Math.floor(rand() * (left.length - i));
		[left[i], left[j]] = [left[j], left[i]];
	}
	return left.slice(0, n);
}

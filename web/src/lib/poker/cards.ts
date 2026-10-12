export const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
export const SUITS = ['s', 'h', 'd', 'c'] as const;
export const SUIT_SYMBOL: Record<string, string> = { s: '♠', h: '♥', d: '♦', c: '♣' };

export type Card = string; // e.g. "Ah"

export const isRed = (c: Card) => c[1] === 'h' || c[1] === 'd';
export const label = (c: Card) => `${c[0] === 'T' ? '10' : c[0]}${SUIT_SYMBOL[c[1]]}`;

/** Hand name for the 13×13 chart cell at (row, col): pairs on the diagonal, suited above. */
export function chartHand(row: number, col: number): string {
	if (row === col) return RANKS[row] + RANKS[col];
	return row < col ? `${RANKS[row]}${RANKS[col]}s` : `${RANKS[col]}${RANKS[row]}o`;
}

/** How many two-card combos a chart hand stands for: pairs 6, suited 4, offsuit 12. */
export const combos = (hand: string) => (hand.length === 2 ? 6 : hand.endsWith('s') ? 4 : 12);

export function money(minor: number, currency: string): string {
	return new Intl.NumberFormat(undefined, {
		style: 'currency',
		currency,
		maximumFractionDigits: minor % 100 === 0 ? 0 : 2
	}).format(minor / 100);
}

export const toMinor = (value: string | number) => Math.round(Number(value) * 100);

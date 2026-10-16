import type { Card } from './cards.ts';
import { categoryOf, draw, score } from './eval.ts';
import { CONTINUE, GAMES, handOf, rangeSet, type GameType, type Spot } from './ranges.ts';

/**
 * The pre-flop practice game: folded to you, raise or fold. Blinds are $0.50/$1 and an open is
 * $2.50. Anyone who calls checks it down to a showdown, so only the pre-flop decision matters.
 * Money is in cents.
 */

export const SB = 50;
export const BB = 100;
export const OPEN = 250;
export const START = 10_000;

export type Deal = { game: GameType; spot: Spot; hands: Record<string, Card[]> };
export type Opponent = { pos: string; cards: Card[]; called: boolean; category?: string; won?: boolean };
export type Outcome = {
	action: 'fold' | 'raise';
	shouldRaise: boolean;
	net: number;
	pot: number;
	opponents: Opponent[];
	board: Card[];
	heroCategory?: string;
	heroWon?: boolean;
	split?: boolean;
};

export function deal(game: GameType, rand = Math.random): Deal {
	const g = GAMES[game];
	const opens = g.spots.filter((s) => s.kind === 'open');
	const spot = opens[Math.floor(rand() * opens.length)];
	const cards = draw(g.seats.length * 2, [], rand);
	const hands = Object.fromEntries(g.seats.map((pos, i) => [pos, cards.slice(i * 2, i * 2 + 2)]));
	return { game, spot, hands };
}

/** What a seat posts before anyone acts. Heads-up the button is the small blind. */
function blind(game: GameType, pos: string): number {
	if (pos === 'BB') return BB;
	return pos === 'SB' || (game === 'hu' && pos === 'BTN') ? SB : 0;
}

/** The range a seat behind you continues with against your open. */
function callRange(pos: string): string {
	if (pos === 'SB') return CONTINUE.SB;
	// The big blind already has a bet in, so it defends wide, like heads-up.
	if (pos === 'BB') return GAMES.hu.spots.find((s) => s.id === 'BB')!.range;
	return CONTINUE.field;
}

export const heroHand = (d: Deal) => handOf(d.hands[d.spot.id][0], d.hands[d.spot.id][1]);

export function resolve(d: Deal, action: 'fold' | 'raise', rand = Math.random): Outcome {
	const hero = d.spot.id;
	const seats = GAMES[d.game].seats;
	const shouldRaise = rangeSet(d.spot.range).has(heroHand(d));
	const behind = seats.slice(seats.indexOf(hero) + 1);
	const base = { action, shouldRaise, board: [] as Card[] };

	if (action === 'fold') {
		const opponents = behind.map((pos) => ({ pos, cards: d.hands[pos], called: false }));
		return { ...base, net: -blind(d.game, hero), pot: 0, opponents };
	}

	const opponents: Opponent[] = behind.map((pos) => ({
		pos,
		cards: d.hands[pos],
		called: rangeSet(callRange(pos)).has(handOf(d.hands[pos][0], d.hands[pos][1]))
	}));
	const pot = OPEN + opponents.reduce((s, o) => s + (o.called ? OPEN : blind(d.game, o.pos)), 0);
	const callers = opponents.filter((o) => o.called);
	if (!callers.length) return { ...base, net: pot - OPEN, pot, opponents, heroWon: true };

	const board = draw(5, Object.values(d.hands).flat(), rand);
	const heroScore = score([...d.hands[hero], ...board]);
	const scores = callers.map((o) => score([...o.cards, ...board]));
	const best = Math.max(heroScore, ...scores);
	const winners = (heroScore === best ? 1 : 0) + scores.filter((s) => s === best).length;
	callers.forEach((o, i) => {
		o.category = categoryOf(scores[i]);
		o.won = scores[i] === best;
	});
	const heroWon = heroScore === best;
	const share = heroWon ? Math.floor(pot / winners) + (pot % winners) : 0;
	return {
		...base,
		net: share - OPEN,
		pot,
		opponents,
		board,
		heroCategory: categoryOf(heroScore),
		heroWon,
		split: heroWon && winners > 1
	};
}

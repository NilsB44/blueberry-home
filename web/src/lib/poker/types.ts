export type Entry = { id: number; player: string; buy_in: number; buy_ins: number; cash_out: number | null; net: number | null };
export type Transfer = { payer: string; payee: string; amount: number };
export type Game = {
	id: number;
	name: string;
	currency: string;
	default_buy_in: number;
	created_at: string;
	settled_at: string | null;
	entries: Entry[];
	total_in: number;
	total_out: number;
	difference: number | null;
	transfers: Transfer[] | null;
};
export type GameSummary = { id: number; name: string; currency: string; created_at: string; settled_at: string | null; players: number; pot: number };
export type LedgerRow = { player: string; currency: string; games: number; buy_in: number; net: number; best: number; worst: number };

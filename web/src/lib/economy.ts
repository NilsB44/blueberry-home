/** The owner's economy page. The API only stores this; every sum and rule is worked out here. */

export type AccountKind = 'cash' | 'investment' | 'pension' | 'property' | 'loan' | 'other';
export type Account = { name: string; kind: AccountKind; balance: number };
export type Subscription = { name: string; price: number; period: 'month' | 'year' };
export type Rules = {
	wait_days: number;
	big_price: number;
	big_wait_days: number;
	max_net_worth_pct: number;
	monthly_expenses: number;
	emergency_months: number;
	hourly_pay: number;
	max_work_hours: number;
	max_cost_per_use: number;
};
export type WishItem = { name: string; price: number; added: string; uses: number; checks: Record<string, boolean> };
export type Economy = { accounts: Account[]; subscriptions: Subscription[]; rules: Rules; wishlist: WishItem[] };

export const KINDS: { id: AccountKind; label: string }[] = [
	{ id: 'cash', label: 'Cash & savings' },
	{ id: 'investment', label: 'Investments' },
	{ id: 'pension', label: 'Pension' },
	{ id: 'property', label: 'Property' },
	{ id: 'other', label: 'Other' },
	{ id: 'loan', label: 'Loans' }
];

const signed = (a: Account) => (a.kind === 'loan' ? -a.balance : a.balance);

export const netWorth = (accounts: Account[]) => accounts.reduce((s, a) => s + signed(a), 0);

export const totalOf = (accounts: Account[], kind: AccountKind) =>
	accounts.filter((a) => a.kind === kind).reduce((s, a) => s + a.balance, 0);

export const monthly = (s: Subscription) => (s.period === 'month' ? s.price : s.price / 12);

export const subscriptionsPerMonth = (subs: Subscription[]) => subs.reduce((s, x) => s + monthly(x), 0);

/** Yes/no questions to answer honestly before buying; a "yes" passes. */
export const QUESTIONS: { id: string; text: string }[] = [
	{ id: 'need', text: 'It replaces something broken or fills a real need, not just a want' },
	{ id: 'none_owned', text: "I don't already own something that does the job" },
	{ id: 'compared', text: 'I compared prices and looked for used or refurbished' },
	{ id: 'cash', text: 'I can pay in full now, with no credit or instalments' },
	{ id: 'full_price', text: 'I would still want it at full price, not only because it is on sale' },
	{ id: 'year', text: 'I will still use it a year from now' },
	{ id: 'space', text: 'I have a place for it (or something leaves when it arrives)' }
];

// question: the id of a yes/no question, answered by ticking it.
export type Verdict = { label: string; pass: boolean | null; detail: string; question?: string };

const DAY = 86_400_000;

export function daysSince(added: string, today = new Date()) {
	return Math.floor((today.getTime() - new Date(added + 'T00:00:00').getTime()) / DAY);
}

/** Every rule for one wishlist item. pass is null when a rule can't be judged yet (a setting is 0). */
export function judge(item: WishItem, e: Economy, today = new Date()): Verdict[] {
	const r = e.rules;
	const nw = netWorth(e.accounts);
	const cash = totalOf(e.accounts, 'cash');
	const big = item.price >= r.big_price;
	const wait = big ? r.big_wait_days : r.wait_days;
	const waited = daysSince(item.added, today);
	const out: Verdict[] = [
		{
			label: `${wait}-day rule${big ? ' (big purchase)' : ''}`,
			pass: waited >= wait,
			detail: waited >= wait ? `Waited ${waited} days` : `${wait - waited} more days to wait`
		},
		{
			label: `At most ${r.max_net_worth_pct}% of net worth`,
			pass: nw > 0 && item.price <= (nw * r.max_net_worth_pct) / 100,
			detail: nw > 0 ? `${pct(item.price, nw)} of ${sek(nw)}` : 'Net worth is not above zero'
		},
		r.monthly_expenses > 0
			? {
					label: `Leaves a ${r.emergency_months}-month buffer`,
					pass: cash - item.price >= r.emergency_months * r.monthly_expenses,
					detail: `${sek(cash - item.price)} cash left, buffer is ${sek(r.emergency_months * r.monthly_expenses)}`
				}
			: { label: 'Leaves an emergency buffer', pass: null, detail: 'Set your monthly expenses under Rules' },
		r.hourly_pay > 0
			? {
					label: `At most ${r.max_work_hours} hours of work`,
					pass: item.price / r.hourly_pay <= r.max_work_hours,
					detail: `${round(item.price / r.hourly_pay)} hours at ${sek(r.hourly_pay)}/h`
				}
			: { label: 'Hours of work', pass: null, detail: 'Set your hourly pay under Rules' },
		item.uses > 0
			? {
					label: `At most ${sek(r.max_cost_per_use)} per use`,
					pass: item.price / item.uses <= r.max_cost_per_use,
					detail: `${sek(item.price / item.uses)} over ${item.uses} uses`
				}
			: { label: 'Cost per use', pass: null, detail: 'Estimate how many times you will use it' }
	];
	for (const q of QUESTIONS) out.push({ label: q.text, pass: item.checks[q.id] ?? false, detail: '', question: q.id });
	return out;
}

const round = (n: number) => Math.round(n * 10) / 10;
const pct = (part: number, whole: number) => `${round((part / whole) * 100)}%`;

const fmt = new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', maximumFractionDigits: 0 });
export const sek = (n: number) => fmt.format(n);

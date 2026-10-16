<script lang="ts">
	import { api } from '#lib/api.ts';
	import { chartHand, combos, RANKS } from '#lib/poker/cards.ts';
	import PokerNav from '#lib/poker/PokerNav.svelte';

	type Table = { trials: number; hands: { hand: string; equity: number[] }[] };

	let table = $state<Table | null>(null);
	let opponents = $state(1);
	let selected = $state('AKs');
	let error = $state('');

	$effect(() => {
		api<Table>('/poker/preflop')
			.then((t) => (table = t))
			.catch((e) => (error = e.message));
	});

	const equity = $derived(new Map(table?.hands.map((h) => [h.hand, h.equity]) ?? []));

	// Strength percentile by combos: "AKs is in the top 2% of hands" against this many opponents.
	const percentile = $derived.by(() => {
		const out = new Map<string, number>();
		if (!table) return out;
		const sorted = [...table.hands].sort((a, b) => b.equity[opponents - 1] - a.equity[opponents - 1]);
		let seen = 0;
		for (const h of sorted) {
			seen += combos(h.hand);
			out.set(h.hand, seen / 1326);
		}
		return out;
	});

	const range = $derived.by(() => {
		const vals = table?.hands.map((h) => h.equity[opponents - 1]) ?? [0, 1];
		return [Math.min(...vals), Math.max(...vals)];
	});

	function strength(hand: string): number {
		const e = equity.get(hand)?.[opponents - 1] ?? 0;
		return (e - range[0]) / (range[1] - range[0] || 1);
	}

	const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
	const fair = $derived(1 / (opponents + 1));
</script>

<section>
	<PokerNav />
	<h1>Pre-flop equity</h1>
	<p class="muted">
		Each hand's share of the pot if everyone goes to showdown against random hands. A fair share
		against {opponents} opponent{opponents === 1 ? '' : 's'} is {pct(fair)}.
	</p>
	{#if error}<p class="error">{error}</p>{/if}

	<div class="opps">
		<span class="muted">Opponents</span>
		{#each [1, 2, 3, 4, 5, 6, 7, 8, 9] as n}
			<button class:on={opponents === n} class="ghost" onclick={() => (opponents = n)}>{n}</button>
		{/each}
	</div>

	{#if table}
		<div class="grid" role="grid">
			{#each RANKS as _, row}
				{#each RANKS as _, col}
					{@const hand = chartHand(row, col)}
					{@const e = equity.get(hand)?.[opponents - 1] ?? 0}
					<button
						class="cell"
						class:sel={selected === hand}
						class:above={e > fair}
						style:--s={strength(hand)}
						onclick={() => (selected = hand)}
						aria-label={`${hand} ${pct(e)}`}
					>
						<span class="h">{hand}</span>
						<span class="e">{Math.round(e * 100)}</span>
					</button>
				{/each}
			{/each}
		</div>
		<p class="muted small">Suited hands above the diagonal, offsuit below. Bold: better than a fair share.</p>

		{#if equity.get(selected)}
			{@const eqs = equity.get(selected) ?? []}
			<div class="card detail">
				<h2>{selected}</h2>
				<p>
					{pct(eqs[opponents - 1])} against {opponents}. Top {pct(percentile.get(selected) ?? 0)} of starting hands
					({combos(selected)} of 1,326 combos).
				</p>
				<table>
					<thead><tr><th>Opponents</th>{#each eqs as _, i}<th>{i + 1}</th>{/each}</tr></thead>
					<tbody>
						<tr><td>Equity</td>{#each eqs as e, i}<td class:above={e > 1 / (i + 2)}>{Math.round(e * 100)}%</td>{/each}</tr>
						<tr class="muted"><td>Fair share</td>{#each eqs as _, i}<td>{Math.round(100 / (i + 2))}%</td>{/each}</tr>
					</tbody>
				</table>
				<a href={`/poker/calculator?hand=${selected}`}>Try it in the calculator →</a>
			</div>
		{/if}
		<p class="muted small">Monte Carlo, {table.trials.toLocaleString()} deals per hand and table size.</p>
	{/if}
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 760px;
		margin: 0 auto;
	}
	.opps {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		flex-wrap: wrap;
		margin-bottom: 0.75rem;
	}
	.opps button {
		padding: 0.3rem 0.65rem;
	}
	.opps .on {
		background: var(--accent);
		color: var(--accent-text);
		border-color: var(--accent);
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(13, 1fr);
		gap: 2px;
	}
	.cell {
		aspect-ratio: 1;
		padding: 0;
		border-radius: 3px;
		display: grid;
		place-content: center;
		line-height: 1.05;
		font-weight: 400;
		color: var(--text);
		background: color-mix(in oklab, var(--hot) calc(var(--s) * 100%), var(--cold));
		border: 0;
	}
	.cell.above .h {
		font-weight: 700;
	}
	.cell.sel {
		outline: 2px solid var(--text);
		outline-offset: -1px;
	}
	.h {
		font-size: clamp(0.5rem, 2.3vw, 0.8rem);
	}
	.e {
		font-size: clamp(0.45rem, 1.8vw, 0.65rem);
		opacity: 0.75;
	}
	.detail {
		margin-top: 1rem;
		overflow-x: auto;
	}
	.detail h2 {
		margin: 0;
	}
	table {
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
		margin: 0.5rem 0;
	}
	th,
	td {
		padding: 0.2rem 0.4rem;
		text-align: right;
	}
	td.above {
		font-weight: 700;
	}
	.small {
		font-size: 0.85rem;
	}
	section {
		--cold: #eef1f6;
		--hot: #f4a3b8;
	}
	@media (prefers-color-scheme: dark) {
		section {
			--cold: #23262d;
			--hot: #8c2a4a;
		}
	}
</style>

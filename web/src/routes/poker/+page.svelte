<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import { chartHand, combos, RANKS } from '#lib/poker/cards.ts';
	import PokerNav from '#lib/poker/PokerNav.svelte';
	import { GAMES, rangeSet, rangeShare, type GameType } from '#lib/poker/ranges.ts';

	type Table = { trials: number; hands: { hand: string; equity: number[] }[] };

	let table = $state<Table | null>(null);
	let mode = $state<'ranges' | 'equity'>('ranges');
	let gameType = $state<GameType>('6max');
	let spotId = $state('CO'); // a spot id, or 'all'
	let opponents = $state(1);
	let selected = $state('AKs');
	let error = $state('');

	$effect(() => {
		const g = page.url.searchParams.get('game');
		const pos = page.url.searchParams.get('pos');
		if (g && g in GAMES) gameType = g as GameType;
		if (pos && GAMES[gameType].spots.some((s) => s.id === pos)) spotId = pos;
	});

	$effect(() => {
		api<Table>('/poker/preflop')
			.then((t) => (table = t))
			.catch((e) => (error = e.message));
	});

	const game = $derived(GAMES[gameType]);
	const spot = $derived(game.spots.find((s) => s.id === spotId));
	const spotSets = $derived(game.spots.map((s) => ({ spot: s, set: rangeSet(s.range) })));

	function setGame(g: GameType) {
		gameType = g;
		if (spotId !== 'all' && !GAMES[g].spots.some((s) => s.id === spotId)) spotId = GAMES[g].spots[0].id;
	}

	const equity = $derived(new Map(table?.hands.map((h) => [h.hand, h.equity]) ?? []));
	const fair = $derived(1 / (opponents + 1));

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

	const span = $derived.by(() => {
		const vals = table?.hands.map((h) => h.equity[opponents - 1]) ?? [0, 1];
		return [Math.min(...vals), Math.max(...vals)];
	});

	function strength(hand: string): number {
		const e = equity.get(hand)?.[opponents - 1] ?? 0;
		return (e - span[0]) / (span[1] - span[0] || 1);
	}

	/** Index of the tightest spot that plays this hand, or -1. Spots are ordered tight to loose. */
	function firstSpot(hand: string): number {
		return spotSets.findIndex((s) => s.spot.kind === 'open' && s.set.has(hand));
	}

	/** Whether a hand is "in" for the current view: the outlined area of the chart. */
	function inside(hand: string): boolean {
		if (mode === 'equity') return (equity.get(hand)?.[opponents - 1] ?? 0) > fair;
		if (spotId === 'all') return firstSpot(hand) >= 0;
		return !!spot && rangeSet(spot.range).has(hand);
	}

	// A thick line around the playable area: draw each cell edge whose neighbour is outside.
	function edges(row: number, col: number): string {
		if (!inside(chartHand(row, col))) return '';
		const out = (r: number, c: number) => r < 0 || c < 0 || r > 12 || c > 12 || !inside(chartHand(r, c));
		const w = '3px';
		return [
			out(row - 1, col) && `inset 0 ${w} 0 var(--line)`,
			out(row, col + 1) && `inset -${w} 0 0 var(--line)`,
			out(row + 1, col) && `inset 0 -${w} 0 var(--line)`,
			out(row, col - 1) && `inset ${w} 0 0 var(--line)`
		]
			.filter(Boolean)
			.join(', ');
	}

	const share = $derived(spot && spotId !== 'all' ? rangeShare(rangeSet(spot.range)) : 0);
	const opens = $derived(spotSets.filter((s) => s.spot.kind === 'open'));

	const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
</script>

<section>
	<PokerNav />
	<h1>Pre-flop chart</h1>

	<div class="chips">
		<button class:on={mode === 'ranges'} class="ghost" onclick={() => (mode = 'ranges')}>What to play</button>
		<button class:on={mode === 'equity'} class="ghost" onclick={() => (mode = 'equity')}>Raw equity</button>
	</div>

	{#if mode === 'ranges'}
		<div class="chips">
			<span class="muted">Game</span>
			{#each Object.entries(GAMES) as [id, g]}
				<button class:on={gameType === id} class="ghost" onclick={() => setGame(id as GameType)}>{g.label}</button>
			{/each}
		</div>
		<div class="chips">
			<span class="muted">Seat</span>
			{#each game.spots as s}
				<button class:on={spotId === s.id} class="ghost" onclick={() => (spotId = s.id)}>{s.label}</button>
			{/each}
			{#if opens.length > 1}
				<button class:on={spotId === 'all'} class="ghost" onclick={() => (spotId = 'all')}>All seats</button>
			{/if}
		</div>
		{#if spotId === 'all'}
			<p class="muted">Each hand shows the earliest seat you can raise it from. Later seats raise everything earlier seats do, plus more.</p>
		{:else if spot}
			<p>
				<strong>{spot.kind === 'open' ? 'Raise' : 'Continue with'}</strong> the highlighted hands, <strong>fold</strong> the rest:
				{pct(share)} of hands.
				<span class="muted">{spot.kind === 'open' ? 'Everyone before you folded.' : ''} {spot.note}</span>
			</p>
		{/if}
	{:else}
		<p class="muted">
			Each hand's share of the pot if everyone goes to showdown against random hands. The outlined hands beat a fair
			share ({pct(fair)}) against {opponents} opponent{opponents === 1 ? '' : 's'}.
		</p>
		<div class="chips">
			<span class="muted">Opponents</span>
			{#each [1, 2, 3, 4, 5, 6, 7, 8, 9] as n}
				<button class:on={opponents === n} class="ghost" onclick={() => (opponents = n)}>{n}</button>
			{/each}
		</div>
	{/if}
	{#if error}<p class="error">{error}</p>{/if}

	<div class="grid" class:ranges={mode === 'ranges'} class:solid={spotId !== 'all'} role="grid">
		{#each RANKS as _, row}
			{#each RANKS as _, col}
				{@const hand = chartHand(row, col)}
				{@const e = equity.get(hand)?.[opponents - 1] ?? 0}
				{@const first = firstSpot(hand)}
				{@const isIn = inside(hand)}
				<button
					class="cell"
					class:sel={selected === hand}
					class:in={isIn}
					class:deep={spotId === 'all' && first >= 0 && first / opens.length < 0.5}
					style:--s={mode === 'equity' ? strength(hand) : spotId === 'all' && first >= 0 ? 1 - first / opens.length : 1}
					style:box-shadow={edges(row, col)}
					onclick={() => (selected = hand)}
					aria-label={`${hand}: ${isIn ? (mode === 'equity' ? 'above fair share' : 'play') : 'fold'}`}
				>
					<span class="h">{hand}</span>
					{#if mode === 'ranges' && spotId === 'all'}
						<span class="e">{first >= 0 ? opens[first].spot.label : ''}</span>
					{:else if table}
						<span class="e">{Math.round(e * 100)}</span>
					{/if}
				</button>
			{/each}
		{/each}
	</div>
	<p class="muted small">
		Suited hands above the diagonal, offsuit below.
		{#if mode === 'ranges'}Small numbers are equity against one random hand.{/if}
	</p>
	{#if mode === 'ranges' && spotId === 'all'}
		<div class="legend">
			{#each opens as s, i}
				<span class="key" class:deep={i / opens.length < 0.5} style:--s={1 - i / opens.length}>{s.spot.label}</span>
			{/each}
		</div>
	{/if}

	<div class="card detail">
		<h2>{selected}</h2>
		{#if mode === 'ranges'}
			{@const plays = spotSets.filter((s) => s.set.has(selected)).map((s) => s.spot.label)}
			{@const folds = spotSets.filter((s) => !s.set.has(selected)).map((s) => s.spot.label)}
			<p>
				{game.label}:
				{#if plays.length}play from <strong>{plays.join(', ')}</strong>{/if}{#if plays.length && folds.length};
				{/if}{#if folds.length}fold from <strong>{folds.join(', ')}</strong>{/if}.
			</p>
		{/if}
		{#if equity.get(selected)}
			{@const eqs = equity.get(selected) ?? []}
			<p>
				{pct(eqs[opponents - 1])} equity against {opponents} random hand{opponents === 1 ? '' : 's'}. Top {pct(
					percentile.get(selected) ?? 0
				)} of starting hands ({combos(selected)} of 1,326 combos).
			</p>
			<div class="scroll">
				<table>
					<thead><tr><th>Opponents</th>{#each eqs as _, i}<th>{i + 1}</th>{/each}</tr></thead>
					<tbody>
						<tr><td>Equity</td>{#each eqs as e, i}<td class:above={e > 1 / (i + 2)}>{Math.round(e * 100)}%</td>{/each}</tr>
						<tr class="muted"><td>Fair share</td>{#each eqs as _, i}<td>{Math.round(100 / (i + 2))}%</td>{/each}</tr>
					</tbody>
				</table>
			</div>
		{/if}
		<p class="links">
			<a href={`/poker/calculator?hand=${selected}`}>Try it in the calculator →</a>
			<a href={`/poker/practice?game=${gameType}`}>Practice these ranges →</a>
		</p>
	</div>
	{#if table}
		<p class="muted small">Equity: Monte Carlo, {table.trials.toLocaleString()} deals per hand and table size. Ranges: simplified from common solver charts for 100-big-blind cash games.</p>
	{/if}
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 760px;
		margin: 0 auto;
	}
	.chips {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		flex-wrap: wrap;
		margin-bottom: 0.6rem;
	}
	.chips button {
		padding: 0.3rem 0.65rem;
	}
	.chips .on {
		background: var(--accent);
		color: var(--accent-text);
		border-color: var(--accent);
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(13, 1fr);
		gap: 1px;
		margin-top: 0.5rem;
	}
	.cell {
		aspect-ratio: 1;
		padding: 0;
		border-radius: 2px;
		display: grid;
		place-content: center;
		line-height: 1.05;
		font-weight: 400;
		color: var(--text);
		background: color-mix(in oklab, var(--hot) calc(var(--s) * 100%), var(--cold));
		border: 0;
	}
	.cell.in .h {
		font-weight: 700;
	}
	.ranges .cell {
		background: var(--cold);
		color: var(--muted);
	}
	.ranges .cell.in {
		background: color-mix(in oklab, var(--play) calc(25% + var(--s) * 75%), var(--cold));
		color: var(--text);
	}
	.ranges.solid .cell.in,
	.ranges .cell.deep,
	.key.deep {
		color: var(--play-text);
	}
	.cell.sel {
		outline: 2px solid var(--text);
		outline-offset: -1px;
		position: relative;
		z-index: 1;
	}
	.h {
		font-size: clamp(0.5rem, 2.3vw, 0.8rem);
	}
	.e {
		font-size: clamp(0.45rem, 1.8vw, 0.65rem);
		opacity: 0.8;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
	.key {
		padding: 0.15rem 0.5rem;
		border-radius: 4px;
		font-size: 0.8rem;
		background: color-mix(in oklab, var(--play) calc(25% + var(--s) * 75%), var(--cold));
	}
	.detail {
		margin-top: 1rem;
	}
	.detail h2 {
		margin: 0;
	}
	.scroll {
		overflow-x: auto;
	}
	.links {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
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
		--play: #2e7d32;
		--play-text: #ffffff;
		--line: #15181d;
	}
	:global(:root[data-theme='dark']) section {
		--cold: #23262d;
		--hot: #8c2a4a;
		--play: #4caf50;
		--play-text: #0d1a0e;
		--line: #e9ecf1;
	}
	@media (prefers-color-scheme: dark) {
		:global(:root:not([data-theme='light'])) section {
			--cold: #23262d;
			--hot: #8c2a4a;
			--play: #4caf50;
			--play-text: #0d1a0e;
			--line: #e9ecf1;
		}
	}
</style>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '#lib/api.ts';
	import { money, toMinor } from '#lib/poker/cards.ts';
	import PokerNav from '#lib/poker/PokerNav.svelte';
	import type { Game, GameSummary, LedgerRow } from '#lib/poker/types.ts';

	let games = $state<GameSummary[]>([]);
	let ledger = $state<LedgerRow[]>([]);
	let name = $state(`Home game ${new Date().toLocaleDateString()}`);
	let currency = $state('SEK');
	let buyIn = $state('200');
	let error = $state('');

	$effect(() => {
		Promise.all([api<GameSummary[]>('/poker/games'), api<LedgerRow[]>('/poker/ledger')])
			.then(([g, l]) => {
				games = g;
				ledger = l;
			})
			.catch((e) => (error = e.message));
	});

	async function create(e: SubmitEvent) {
		e.preventDefault();
		try {
			const game = await api<Game>('/poker/games', {
				method: 'POST',
				json: { name, currency: currency.toUpperCase(), default_buy_in: toMinor(buyIn) }
			});
			goto(`/poker/games/${game.id}`);
		} catch (err) {
			error = (err as Error).message;
		}
	}
</script>

<section>
	<PokerNav />
	<h1>Home games</h1>
	<p class="muted">Track buy-ins and rebuys, enter final stacks, and get the fewest transfers to settle up.</p>

	<form class="card new" onsubmit={create}>
		<label>Name <input bind:value={name} required maxlength="80" /></label>
		<div class="row">
			<label>Buy-in <input type="number" bind:value={buyIn} min="0" step="any" inputmode="decimal" /></label>
			<label>Currency <input bind:value={currency} maxlength="3" pattern={'[A-Za-z]{3}'} /></label>
		</div>
		<button>Start a game</button>
	</form>
	{#if error}<p class="error">{error}</p>{/if}

	{#if games.length}
		<h2>Games</h2>
		<ul class="list">
			{#each games as g}
				<li>
					<a class="card game" href={`/poker/games/${g.id}`}>
						<span><strong>{g.name}</strong><span class="muted small">{g.players} players · pot {money(g.pot, g.currency)}</span></span>
						<span class="tag" class:open={!g.settled_at}>{g.settled_at ? 'Settled' : 'Open'}</span>
					</a>
				</li>
			{/each}
		</ul>
	{/if}

	{#if ledger.length}
		<h2>Lifetime results</h2>
		<div class="card table-wrap">
			<table>
				<thead><tr><th>Player</th><th>Games</th><th>Net</th><th>Best</th><th>Worst</th></tr></thead>
				<tbody>
					{#each ledger as r}
						<tr>
							<td>{r.player}</td>
							<td>{r.games}</td>
							<td class:pos={r.net > 0} class:neg={r.net < 0}>{money(r.net, r.currency)}</td>
							<td>{money(r.best, r.currency)}</td>
							<td>{money(r.worst, r.currency)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 640px;
		margin: 0 auto;
	}
	.new {
		display: grid;
		gap: 0.6rem;
	}
	.new label {
		display: grid;
		gap: 0.2rem;
		font-size: 0.9rem;
	}
	.row {
		display: grid;
		grid-template-columns: 2fr 1fr;
		gap: 0.5rem;
	}
	.list {
		list-style: none;
		padding: 0;
		display: grid;
		gap: 0.5rem;
	}
	.game {
		display: flex;
		justify-content: space-between;
		align-items: center;
		text-decoration: none;
	}
	.game > span:first-child {
		display: grid;
	}
	.tag {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.tag.open {
		color: var(--accent);
		font-weight: 600;
	}
	.small {
		font-size: 0.85rem;
	}
	.table-wrap {
		overflow-x: auto;
		padding: 0.5rem;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
	}
	th,
	td {
		padding: 0.35rem 0.5rem;
		text-align: right;
	}
	th:first-child,
	td:first-child {
		text-align: left;
	}
	.pos {
		color: var(--good);
	}
	.neg {
		color: var(--danger);
	}
</style>

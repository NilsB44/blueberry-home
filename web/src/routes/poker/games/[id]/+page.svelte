<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import { money, toMinor } from '#lib/poker/cards.ts';
	import PokerNav from '#lib/poker/PokerNav.svelte';
	import type { Game } from '#lib/poker/types.ts';

	const id = $derived(page.params.id);
	let game = $state<Game | null>(null);
	let newPlayer = $state('');
	let newBuyIn = $state('');
	let stacks = $state<Record<number, string>>({});
	let error = $state('');

	$effect(() => {
		api<Game>(`/poker/games/${id}`).then(load).catch((e) => (error = e.message));
	});

	function load(g: Game) {
		game = g;
		newBuyIn ||= String(g.default_buy_in / 100);
		for (const e of g.entries) stacks[e.id] ??= e.cash_out === null ? '' : String(e.cash_out / 100);
	}

	async function act(path: string, method: string, json?: unknown) {
		error = '';
		try {
			load(await api<Game>(`/poker/games/${id}${path}`, { method, json }));
			return true;
		} catch (e) {
			error = (e as Error).message;
			return false;
		}
	}

	async function addPlayer(e: SubmitEvent) {
		e.preventDefault();
		if (await act('/players', 'POST', { player: newPlayer, buy_in: toMinor(newBuyIn || 0) })) newPlayer = '';
	}

	function saveStack(entryId: number) {
		const v = stacks[entryId];
		if (v === '' || v === undefined) return;
		act(`/players/${entryId}/cash-out`, 'PUT', { amount: toMinor(v) });
	}

	async function remove() {
		if (!confirm('Delete this game?')) return;
		await api(`/poker/games/${id}`, { method: 'DELETE' });
		goto('/poker/games');
	}

	const m = (v: number) => money(v, game?.currency ?? 'SEK');
	const open = $derived(game !== null && game.settled_at === null);
</script>

<section>
	<PokerNav />
	{#if error}<p class="error">{error}</p>{/if}
	{#if game}
		<h1>{game.name}</h1>
		<p class="muted">
			Pot {m(game.total_in)} · {game.entries.length} players{#if game.settled_at} · settled{/if}
		</p>

		<div class="entries">
			{#each game.entries as e (e.id)}
				<div class="card entry">
					<div class="who">
						<strong>{e.player}</strong>
						<span class="muted small">{m(e.buy_in)} in · {e.buy_ins} buy-in{e.buy_ins === 1 ? '' : 's'}</span>
					</div>
					{#if open}
						<button class="ghost" onclick={() => act(`/players/${e.id}/buy-in`, 'POST', { amount: game!.default_buy_in || toMinor(newBuyIn) })}>
							+ Rebuy
						</button>
						<label class="stack">
							<span class="muted small">Final stack</span>
							<input
								type="number"
								inputmode="decimal"
								min="0"
								step="any"
								bind:value={stacks[e.id]}
								onchange={() => saveStack(e.id)}
							/>
						</label>
					{:else}
						<span class="net" class:pos={(e.net ?? 0) > 0} class:neg={(e.net ?? 0) < 0}>{m(e.net ?? 0)}</span>
					{/if}
				</div>
			{/each}
		</div>

		{#if open}
			<form class="add" onsubmit={addPlayer}>
				<input placeholder="Player name" bind:value={newPlayer} required maxlength="40" />
				<input type="number" inputmode="decimal" min="0" step="any" bind:value={newBuyIn} aria-label="Buy-in" />
				<button>Add</button>
			</form>
		{/if}

		{#if game.difference !== null && game.difference !== 0}
			<p class="card warn">
				Final stacks add up to {m(game.total_out)}, but {m(game.total_in)} was paid in
				({game.difference > 0 ? '+' : ''}{m(game.difference)}). Recount the chips.
			</p>
		{/if}

		{#if game.transfers}
			<h2>Settle up</h2>
			{#if game.transfers.length === 0}
				<p>Everyone is square.</p>
			{:else}
				<ul class="card transfers">
					{#each game.transfers as t}
						<li><strong>{t.payer}</strong> pays <strong>{t.payee}</strong> <span class="amt">{m(t.amount)}</span></li>
					{/each}
				</ul>
			{/if}
			{#if open}
				<button onclick={() => act('/settle', 'POST')}>Mark as settled</button>
				<p class="muted small">Settling locks the game and adds it to lifetime results.</p>
			{/if}
		{:else if open && game.entries.length}
			<p class="muted small">Enter every final stack to see who pays whom.</p>
		{/if}

		<p><button class="ghost danger" onclick={remove}>Delete game</button></p>
	{/if}
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 640px;
		margin: 0 auto;
	}
	.entries {
		display: grid;
		gap: 0.5rem;
	}
	.entry {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.6rem 0.75rem;
	}
	.who {
		display: grid;
		flex: 1;
	}
	.stack {
		display: grid;
		width: 6.5rem;
	}
	.stack input {
		padding: 0.35rem 0.5rem;
	}
	.add {
		display: grid;
		grid-template-columns: 1fr 6rem auto;
		gap: 0.5rem;
		margin-top: 0.75rem;
	}
	.warn {
		border-color: var(--near);
		color: var(--near);
	}
	.transfers {
		list-style: none;
		display: grid;
		gap: 0.4rem;
	}
	.amt {
		float: right;
		font-variant-numeric: tabular-nums;
	}
	.net {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
	.pos {
		color: var(--good);
	}
	.neg {
		color: var(--danger);
	}
	.small {
		font-size: 0.85rem;
	}
	.danger {
		color: var(--danger);
	}
</style>

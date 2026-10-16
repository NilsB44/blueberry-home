<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import { draw } from '#lib/poker/eval.ts';
	import CardPicker from '#lib/poker/CardPicker.svelte';
	import PlayingCard from '#lib/poker/PlayingCard.svelte';
	import PokerNav from '#lib/poker/PokerNav.svelte';

	type Result = { exact: boolean; samples: number; millis: number; players: { win: number; tie: number; equity: number }[] };
	// Slots: players' hole cards are p<i>-0 / p<i>-1, the board is b-0..b-4.
	let players = $state<(string | null)[][]>([
		[null, null],
		[null, null]
	]);
	let board = $state<(string | null)[]>([null, null, null, null, null]);
	let picking = $state<{ kind: 'p' | 'b'; i: number; j: number } | null>(null);
	let result = $state<Result | null>(null);
	let busy = $state(false);
	let error = $state('');
	// Simulation: opponents dealt at random, optionally face down until you reveal them.
	let dealt = $state<number[]>([]);
	let boardDealt = $state(false);
	let hide = $state(true);
	let revealed = $state(false);
	const masked = $derived(hide && !revealed && dealt.length > 0);

	$effect(() => {
		const hand = page.url.searchParams.get('hand');
		if (hand && /^[AKQJT2-9]{2}[so]?$/.test(hand)) {
			const second = hand.length === 2 || hand.endsWith('o') ? 'h' : 's';
			players[0] = [hand[0] + 's', hand[1] + second];
		}
	});

	const used = $derived(new Set([...players.flat(), ...board].filter((c): c is string => !!c)));

	function slots(): { kind: 'p' | 'b'; i: number; j: number }[] {
		return [
			...players.flatMap((_, i) => [0, 1].map((j) => ({ kind: 'p' as const, i, j }))),
			...board.map((_, j) => ({ kind: 'b' as const, i: 0, j }))
		];
	}

	function get(s: { kind: 'p' | 'b'; i: number; j: number }) {
		return s.kind === 'p' ? players[s.i][s.j] : board[s.j];
	}

	function set(s: { kind: 'p' | 'b'; i: number; j: number }, c: string | null) {
		if (s.kind === 'p') {
			players[s.i][s.j] = c;
			dealt = dealt.filter((i) => i !== s.i);
		} else board[s.j] = c;
		result = null;
	}

	function tap(s: { kind: 'p' | 'b'; i: number; j: number }) {
		if (s.kind === 'p' && masked && dealt.includes(s.i)) revealed = true;
		else if (get(s)) set(s, null);
		else picking = s;
	}

	function pick(c: string) {
		if (!picking) return;
		set(picking, c);
		const all = slots();
		const at = all.findIndex((s) => s.kind === picking!.kind && s.i === picking!.i && s.j === picking!.j);
		const cur = picking;
		// Keep going through a hand's two cards or the three flop cards; turn and river are one each.
		const keepGoing = cur.kind === 'p' || cur.j < 2;
		const next = keepGoing
			? all.slice(at + 1).find((s) => s.kind === cur.kind && (s.kind === 'b' ? s.j <= 2 : s.i === cur.i) && !get(s))
			: undefined;
		picking = next ?? null;
	}

	const boardCount = $derived(board.filter(Boolean).length);
	const problem = $derived.by(() => {
		if (players.some((p) => p.filter(Boolean).length === 1)) return 'Pick both cards for a hand, or none for a random hand.';
		if (boardCount === 1 || boardCount === 2) return 'The board needs 0, 3, 4 or 5 cards.';
		return '';
	});

	function removePlayer(i: number) {
		players.splice(i, 1);
		dealt = dealt.filter((d) => d !== i).map((d) => (d > i ? d - 1 : d));
		result = null;
	}

	/** Deal random cards to every opponent you haven't picked cards for, then calculate. */
	function dealOpponents() {
		const redeal = new Set(dealt);
		if (boardDealt) board = [null, null, null, null, null];
		boardDealt = false;
		const targets = players.map((p, i) => i).filter((i) => i > 0 && (redeal.has(i) || (!players[i][0] && !players[i][1])));
		const keep = players.flatMap((p, i) => (targets.includes(i) ? [] : p)).concat(board).filter((c): c is string => !!c);
		const cards = draw(targets.length * 2, keep);
		targets.forEach((i, k) => (players[i] = [cards[k * 2], cards[k * 2 + 1]]));
		dealt = targets;
		revealed = false;
		calculate();
	}

	const nextStreet = $derived(boardCount === 0 ? 'flop' : boardCount === 3 ? 'turn' : boardCount === 4 ? 'river' : '');

	/** Run the board out one street at a time: flop, turn, river. */
	function dealStreet() {
		const n = boardCount === 0 ? 3 : 1;
		const cards = draw(n, used);
		let k = 0;
		board = board.map((c) => c ?? (k < n ? cards[k++] : null));
		boardDealt = true;
		calculate();
	}

	async function calculate() {
		busy = true;
		error = '';
		try {
			result = await api<Result>('/poker/equity', {
				method: 'POST',
				json: {
					hands: players.map((p) => (p[0] && p[1] ? p[0] + p[1] : '')),
					board: board.filter(Boolean).join('')
				}
			});
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	function reset() {
		players = [
			[null, null],
			[null, null]
		];
		board = [null, null, null, null, null];
		result = null;
		dealt = [];
		boardDealt = false;
	}

	const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
</script>

<section>
	<PokerNav />
	<h1>Equity calculator</h1>
	<p class="muted">
		Tap a slot to pick a card. Leave a hand empty for a random hand, or pick yours and deal the others to play a hand
		out.
	</p>

	<div class="players">
		{#each players as p, i}
			<div class="card player">
				<span class="name">P{i + 1}</span>
				<span class="cards">
					{#each [0, 1] as j}
						<PlayingCard
							card={p[j]}
							hidden={masked && dealt.includes(i)}
							active={picking?.kind === 'p' && picking.i === i && picking.j === j}
							onclick={() => tap({ kind: 'p', i, j })}
						/>
					{/each}
				</span>
				{#if result && masked}
					<span class="muted small">{i === 0 ? 'your equity is hidden' : 'face down'}</span>
				{:else if result}
					{@const r = result.players[i]}
					<span class="res">
						<strong>{pct(r.equity)}</strong>
						<span class="muted small">win {pct(r.win)} · tie {pct(r.tie)}</span>
						<span class="bar"><span style:width={pct(r.equity)}></span></span>
					</span>
				{:else if !p[0] && !p[1]}
					<span class="muted small">random</span>
				{/if}
				{#if players.length > 2}
					<button class="ghost x" aria-label="Remove player" onclick={() => removePlayer(i)}>✕</button>
				{/if}
			</div>
		{/each}
	</div>
	{#if players.length < 9}
		<button class="ghost" onclick={() => { players.push([null, null]); result = null; }}>+ Add player</button>
	{/if}

	<h2>Board</h2>
	<div class="board">
		{#each board as c, j}
			<PlayingCard card={c} active={picking?.kind === 'b' && picking.j === j} onclick={() => tap({ kind: 'b', i: 0, j })} />
		{/each}
	</div>

	{#if problem}<p class="muted">{problem}</p>{/if}
	{#if error}<p class="error">{error}</p>{/if}
	<div class="actions">
		<button disabled={busy || !!problem} onclick={calculate}>{busy ? 'Calculating…' : 'Calculate'}</button>
		<button class="ghost" onclick={reset}>Clear</button>
	</div>

	<div class="card sim">
		<h2>Simulate a hand</h2>
		<p class="muted small">Pick your two cards as P1, then deal random hands to the other players and run out the board.</p>
		<div class="actions">
			<button disabled={busy || !players[0][0] || !players[0][1]} onclick={dealOpponents}>
				{dealt.length ? 'Deal new hands' : 'Deal opponents'}
			</button>
			{#if dealt.length && nextStreet}
				<button class="ghost" disabled={busy} onclick={dealStreet}>Deal the {nextStreet}</button>
			{/if}
			{#if masked}
				<button class="ghost" onclick={() => (revealed = true)}>Reveal</button>
			{/if}
		</div>
		<label class="toggle">
			<input type="checkbox" bind:checked={hide} />
			Deal face down, so you can guess your equity before revealing it
		</label>
	</div>
	{#if result}
		<p class="muted small">
			{result.exact ? `Exact: all ${result.samples.toLocaleString()} boards` : `${result.samples.toLocaleString()} random deals`}
			in {result.millis} ms.
		</p>
	{/if}
</section>

{#if picking}
	<CardPicker {used} onPick={pick} onClose={() => (picking = null)} />
{/if}

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 640px;
		margin: 0 auto;
	}
	.players {
		display: grid;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.player {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.6rem 0.75rem;
	}
	.name {
		font-weight: 700;
		width: 1.8rem;
	}
	.cards,
	.board {
		display: flex;
		gap: 0.3rem;
	}
	.res {
		flex: 1;
		display: grid;
		gap: 0.1rem;
	}
	.bar {
		height: 6px;
		background: var(--border);
		border-radius: 3px;
		overflow: hidden;
	}
	.bar span {
		display: block;
		height: 100%;
		background: var(--accent);
	}
	.x {
		margin-left: auto;
		padding: 0.2rem 0.5rem;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 1rem;
	}
	.small {
		font-size: 0.85rem;
	}
	.sim {
		margin-top: 1.25rem;
	}
	.sim h2 {
		margin: 0;
	}
	.sim .actions {
		flex-wrap: wrap;
		margin-top: 0.5rem;
	}
	.toggle {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.75rem;
		font-size: 0.9rem;
	}
	.toggle input {
		width: auto;
	}
</style>

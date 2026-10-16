<script lang="ts">
	import { page } from '$app/state';
	import { money } from '#lib/poker/cards.ts';
	import PlayingCard from '#lib/poker/PlayingCard.svelte';
	import PokerNav from '#lib/poker/PokerNav.svelte';
	import { deal, heroHand, OPEN, resolve, START, type Deal, type Outcome } from '#lib/poker/practice.ts';
	import { GAMES, type GameType } from '#lib/poker/ranges.ts';

	type Stats = { bankroll: number; hands: number; right: number; best: number };
	const KEY = 'poker-practice';
	const fresh = (): Stats => ({ bankroll: START, hands: 0, right: 0, best: START });

	function loadStats(): Stats {
		try {
			return { ...fresh(), ...JSON.parse(localStorage.getItem(KEY) ?? '{}') };
		} catch {
			return fresh();
		}
	}

	let stats = $state<Stats>(loadStats());
	let gameType = $state<GameType>('6max');
	let hand = $state<Deal | null>(null);
	let outcome = $state<Outcome | null>(null);

	$effect(() => {
		const g = page.url.searchParams.get('game');
		if (g && g in GAMES) gameType = g as GameType;
	});

	$effect(() => {
		try {
			localStorage.setItem(KEY, JSON.stringify(stats));
		} catch {
			// Private mode: the session still works, it just won't be remembered.
		}
	});

	const busted = $derived(stats.bankroll < OPEN);
	const usd = (cents: number) => money(cents, 'USD');
	const signed = (cents: number) => (cents > 0 ? '+' : cents < 0 ? '−' : '') + usd(Math.abs(cents));

	function next() {
		outcome = null;
		hand = deal(gameType);
	}

	function act(action: 'fold' | 'raise') {
		if (!hand || outcome) return;
		const o = resolve(hand, action);
		outcome = o;
		stats.hands += 1;
		if ((action === 'raise') === o.shouldRaise) stats.right += 1;
		stats.bankroll += o.net;
		stats.best = Math.max(stats.best, stats.bankroll);
	}

	function setGame(g: GameType) {
		gameType = g;
		next();
	}

	function restart() {
		stats = fresh();
		next();
	}

	$effect(() => {
		if (!hand) next();
	});

	const seats = $derived(hand ? GAMES[hand.game].seats : []);
	const heroAt = $derived(hand ? seats.indexOf(hand.spot.id) : -1);
	const name = $derived(hand ? heroHand(hand) : '');
	const accuracy = $derived(stats.hands ? Math.round((stats.right / stats.hands) * 100) : 0);
</script>

<section>
	<PokerNav />
	<h1>Pre-flop practice</h1>
	<p class="muted">
		Play money. Everyone before you folded: raise to {usd(OPEN)} or fold. Blinds are $0.50/$1. Anyone who calls checks it
		down to the river, so only your pre-flop choice counts.
	</p>

	<div class="chips">
		{#each Object.entries(GAMES) as [id, g]}
			<button class:on={gameType === id} class="ghost" onclick={() => setGame(id as GameType)}>{g.label}</button>
		{/each}
	</div>

	<div class="stats">
		<div><span class="muted small">Bankroll</span><strong class:up={stats.bankroll > START} class:down={stats.bankroll < START}>{usd(stats.bankroll)}</strong></div>
		<div><span class="muted small">Hands</span><strong>{stats.hands}</strong></div>
		<div><span class="muted small">Matched the chart</span><strong>{stats.hands ? `${accuracy}%` : '–'}</strong></div>
	</div>

	{#if busted}
		<div class="card">
			<p>You're out of chips. Your best was {usd(stats.best)} after {stats.hands} hands.</p>
			<button onclick={restart}>Start again with {usd(START)}</button>
		</div>
	{:else if hand}
		<div class="table">
			{#each seats as pos, i}
				{@const opp = outcome?.opponents.find((o) => o.pos === pos)}
				<div class="seat" class:hero={i === heroAt} class:gone={i < heroAt || (opp && !opp.called)}>
					<span class="pos">{pos}</span>
					{#if i === heroAt}
						<span class="muted small">you</span>
					{:else if i < heroAt}
						<span class="muted small">folded</span>
					{:else if opp}
						<span class="small">{opp.called ? 'calls' : 'folds'}</span>
					{:else}
						<span class="muted small">{pos === 'BB' ? '$1' : pos === 'SB' || (hand.game === 'hu' && pos === 'BTN') ? '$0.50' : '…'}</span>
					{/if}
				</div>
			{/each}
		</div>

		<div class="card spot">
			<div class="hole">
				{#each hand.hands[hand.spot.id] as c}<PlayingCard card={c} />{/each}
			</div>
			<p>You're on the <strong>{hand.spot.id}</strong> with <strong>{name}</strong>. {hand.spot.note}</p>
			{#if !outcome}
				<div class="actions">
					<button class="ghost" onclick={() => act('fold')}>Fold</button>
					<button onclick={() => act('raise')}>Raise to {usd(OPEN)}</button>
				</div>
			{/if}
		</div>

		{#if outcome}
			{@const right = (outcome.action === 'raise') === outcome.shouldRaise}
			<div class="card verdict" class:right class:wrong={!right}>
				<p>
					<strong>{right ? '✓' : '✗'}</strong>
					The {GAMES[hand.game].label} {hand.spot.id} chart <strong>{outcome.shouldRaise ? 'raises' : 'folds'}</strong> {name}.
					<a href={`/poker?game=${hand.game}&pos=${hand.spot.id}`}>See the chart</a>
				</p>
			</div>

			<div class="card result">
				{#if outcome.action === 'fold'}
					<p>You folded{outcome.net ? `, losing your ${usd(-outcome.net)} blind` : ''}.</p>
				{:else if !outcome.board.length}
					<p>Everyone folded. You win the blinds: <strong>{signed(outcome.net)}</strong>.</p>
				{:else}
					<div class="board">
						{#each outcome.board as c}<PlayingCard card={c} small />{/each}
					</div>
					<ul class="showdown">
						<li class:won={outcome.heroWon}>
							<span class="who">You</span>
							<span class="cards">{#each hand.hands[hand.spot.id] as c}<PlayingCard card={c} small />{/each}</span>
							<span class="small">{outcome.heroCategory}</span>
						</li>
						{#each outcome.opponents.filter((o) => o.called) as o}
							<li class:won={o.won}>
								<span class="who">{o.pos}</span>
								<span class="cards">{#each o.cards as c}<PlayingCard card={c} small />{/each}</span>
								<span class="small">{o.category}</span>
							</li>
						{/each}
					</ul>
					<p>
						Pot {usd(outcome.pot)}.
						{outcome.split ? 'You split it' : outcome.heroWon ? 'You win' : 'You lose'}:
						<strong class:up={outcome.net > 0} class:down={outcome.net < 0}>{signed(outcome.net)}</strong>.
					</p>
				{/if}
				{#if outcome.opponents.some((o) => !o.called)}
					<details>
						<summary class="muted small">What the folders had</summary>
						<ul class="showdown">
							{#each outcome.opponents.filter((o) => !o.called) as o}
								<li>
									<span class="who">{o.pos}</span>
									<span class="cards">{#each o.cards as c}<PlayingCard card={c} small />{/each}</span>
								</li>
							{/each}
						</ul>
					</details>
				{/if}
				<button onclick={next}>Next hand</button>
			</div>
		{/if}
	{/if}

	<p class="muted small">
		Your bankroll stays on this device. <button class="link" onclick={restart}>Reset to {usd(START)}</button>
	</p>
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 640px;
		margin: 0 auto;
	}
	.chips {
		display: flex;
		gap: 0.3rem;
		flex-wrap: wrap;
		margin-bottom: 0.75rem;
	}
	.chips button {
		padding: 0.3rem 0.65rem;
	}
	.chips .on {
		background: var(--accent);
		color: var(--accent-text);
		border-color: var(--accent);
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.stats div {
		display: grid;
	}
	.stats strong {
		font-size: 1.2rem;
		font-variant-numeric: tabular-nums;
	}
	.table {
		display: flex;
		gap: 0.3rem;
		flex-wrap: wrap;
		margin-bottom: 0.5rem;
	}
	.seat {
		display: grid;
		justify-items: center;
		min-width: 3.4rem;
		padding: 0.3rem 0.4rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--surface);
	}
	.seat.hero {
		border: 2px solid var(--accent);
	}
	.seat.gone {
		opacity: 0.5;
	}
	.pos {
		font-weight: 700;
		font-size: 0.85rem;
	}
	.spot,
	.verdict,
	.result {
		margin-bottom: 0.75rem;
	}
	.hole,
	.board,
	.cards {
		display: flex;
		gap: 0.3rem;
	}
	.actions {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
	}
	.verdict p {
		margin: 0;
	}
	.verdict.right {
		background: var(--good-bg);
		border-color: var(--good);
	}
	.verdict.wrong {
		background: var(--bad-bg);
		border-color: var(--danger);
	}
	.showdown {
		list-style: none;
		padding: 0;
		display: grid;
		gap: 0.35rem;
	}
	.showdown li {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.2rem 0.4rem;
		border-radius: 6px;
	}
	.showdown li.won {
		background: var(--good-bg);
	}
	.who {
		font-weight: 700;
		width: 3.2rem;
	}
	.small {
		font-size: 0.85rem;
	}
	.up {
		color: var(--good);
	}
	.down {
		color: var(--danger);
	}
	.link {
		background: none;
		border: 0;
		padding: 0;
		color: inherit;
		text-decoration: underline;
		font-weight: 400;
	}
</style>

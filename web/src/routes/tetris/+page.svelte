<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '#lib/api.ts';
	import { POWERS } from '#lib/tetris/game.ts';

	type Room = { code: string; host: string | null; players: string[]; started: boolean; full: boolean };
	type Scores = { top: { name: string; score: number; lines: number; level: number; mine: boolean }[]; best: number | null };

	let rooms = $state<Room[]>([]);
	let scores = $state<Scores | null>(null);
	let code = $state('');
	let error = $state('');
	let creating = $state(false);

	$effect(() => {
		const load = () =>
			api<Room[]>('/tetris/rooms')
				.then((r) => (rooms = r))
				.catch((e) => (error = e.message));
		load();
		const timer = setInterval(load, 3000);
		api<Scores>('/tetris/scores').then((s) => (scores = s));
		return () => clearInterval(timer);
	});

	async function create() {
		creating = true;
		try {
			const room = await api<Room>('/tetris/rooms', { method: 'POST' });
			goto(`/tetris/room/${room.code}`);
		} catch (e) {
			error = (e as Error).message;
			creating = false;
		}
	}

	function join(e: SubmitEvent) {
		e.preventDefault();
		const c = code.trim().toUpperCase();
		if (c) goto(`/tetris/room/${c}`);
	}
</script>

<section>
	<h1>🧱 Tetris</h1>
	{#if error}<p class="error">{error}</p>{/if}

	<div class="modes">
		<a class="card mode" href="/tetris/solo">
			<strong>Solo</strong>
			<span class="muted">Clear lines, climb levels, beat the household high score.</span>
			{#if scores?.best}<span class="best">Your best: {scores.best.toLocaleString()}</span>{/if}
		</a>
		<div class="card mode">
			<strong>Multiplayer</strong>
			<span class="muted">2–4 players on the Wi-Fi. Clearing 2+ lines sends garbage to an opponent. Last one standing wins.</span>
			<button onclick={create} disabled={creating}>Create a room</button>
			<form onsubmit={join}>
				<input bind:value={code} placeholder="Room code" maxlength="4" autocapitalize="characters" aria-label="Room code" />
				<button class="ghost" disabled={!code.trim()}>Join</button>
			</form>
		</div>
	</div>

	{#if rooms.length}
		<h2>Open rooms</h2>
		<ul class="rooms">
			{#each rooms as r (r.code)}
				<li class="card">
					<div>
						<strong class="code">{r.code}</strong>
						<span class="muted">{r.players.join(', ') || 'Empty'}</span>
					</div>
					{#if r.full}
						<span class="muted">Full</span>
					{:else}
						<a class="join" href="/tetris/room/{r.code}">{r.started ? 'Watch' : 'Join'}</a>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}

	<h2>Power-ups</h2>
	<p class="muted">
		Some pieces carry a ✦ star. Clear the row it's in to collect a power-up (you can keep two), then
		press ✦ or E to use it.
	</p>
	<ul class="powers">
		{#each Object.entries(POWERS) as [id, p] (id)}
			<li>
				<span class="icon">{p.icon}</span>
				<span><strong>{p.name}</strong>{id === 'shield' || id === 'rush' ? ' (multiplayer)' : ''}: {p.text}</span>
			</li>
		{/each}
	</ul>

	{#if scores?.top.length}
		<h2>High scores</h2>
		<ol class="scores">
			{#each scores.top as s, i (i)}
				<li class:mine={s.mine}>
					<span>{s.name}</span>
					<span class="muted">{s.lines} lines · level {s.level}</span>
					<strong>{s.score.toLocaleString()}</strong>
				</li>
			{/each}
		</ol>
	{/if}
</section>

<style>
	section {
		padding: 1.5rem 16px;
		max-width: 760px;
		margin: 0 auto;
	}
	h1 {
		margin-top: 0;
	}
	h2 {
		font-size: 1.1rem;
		margin: 1.75rem 0 0.5rem;
	}
	.modes {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 1rem;
	}
	.mode {
		display: grid;
		gap: 0.5rem;
		align-content: start;
		text-decoration: none;
	}
	a.mode:hover {
		border-color: var(--accent);
	}
	.mode strong {
		font-size: 1.15rem;
	}
	.best {
		font-weight: 600;
	}
	form {
		display: flex;
		gap: 0.5rem;
	}
	form input {
		text-transform: uppercase;
		letter-spacing: 0.15em;
	}
	ul,
	ol {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.rooms {
		display: grid;
		gap: 0.5rem;
	}
	.rooms li {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 1rem;
	}
	.rooms div {
		display: grid;
	}
	.code {
		letter-spacing: 0.15em;
	}
	.join {
		font-weight: 600;
		color: var(--accent);
		text-decoration: none;
	}
	.powers {
		display: grid;
		gap: 0.4rem;
	}
	.powers li {
		display: flex;
		gap: 0.6rem;
		align-items: baseline;
	}
	.icon {
		width: 1.5rem;
		text-align: center;
	}
	.scores {
		display: grid;
		gap: 0.25rem;
		counter-reset: rank;
	}
	.scores li {
		display: grid;
		grid-template-columns: 1.5rem 1fr auto auto;
		gap: 0.75rem;
		padding: 0.4rem 0.6rem;
		border-radius: 8px;
		counter-increment: rank;
	}
	.scores li::before {
		content: counter(rank);
		color: var(--muted);
	}
	.scores li.mine {
		background: var(--surface);
		border: 1px solid var(--border);
	}
	@media (max-width: 480px) {
		.scores li {
			grid-template-columns: 1.5rem 1fr auto;
		}
		.scores li .muted {
			display: none;
		}
	}
</style>

<script lang="ts">
	import { api } from '#lib/api.ts';
	import Tetris from '#lib/tetris/Tetris.svelte';

	type Scores = { top: { name: string; score: number; mine: boolean }[]; best: number | null };

	let seed = $state(newSeed());
	let result = $state<{ score: number; lines: number; level: number } | null>(null);
	let scores = $state<Scores | null>(null);
	let previousBest = $state<number | null>(null);

	function newSeed() {
		return Math.floor(Math.random() * 2 ** 31);
	}

	$effect(() => {
		api<Scores>('/tetris/scores').then((s) => (previousBest = s.best));
	});

	async function over(r: { score: number; lines: number; level: number }) {
		result = r;
		scores = await api<Scores>('/tetris/scores', { method: 'POST', json: r });
	}

	function again() {
		previousBest = scores?.best ?? previousBest;
		result = null;
		scores = null;
		seed = newSeed();
	}
</script>

<div class="page">
	<nav><a href="/tetris" class="muted">← Tetris</a></nav>
	<div class="game">
		{#key seed}
			<Tetris {seed} onover={over} />
		{/key}
		{#if result}
			<div class="overlay">
				<div class="card summary">
					<h2>Game over</h2>
					<p class="big">{result.score.toLocaleString()}</p>
					<p class="muted">{result.lines} lines · level {result.level}</p>
					{#if result.score > 0 && (previousBest === null || result.score > previousBest)}
						<p class="record">🎉 Your new best!</p>
					{/if}
					{#if scores && scores.top.length}
						{@const rank = scores.top.findIndex((s) => s.mine && s.score === result?.score)}
						{#if rank >= 0}<p>#{rank + 1} on the household high scores</p>{/if}
					{/if}
					<div class="actions">
						<button onclick={again}>Play again</button>
						<a href="/tetris" class="muted">Back</a>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.page {
		height: calc(100dvh - 52px);
		display: flex;
		flex-direction: column;
		padding: 0.5rem 16px 0;
	}
	nav {
		padding-bottom: 0.5rem;
	}
	nav a {
		text-decoration: none;
	}
	.game {
		position: relative;
		flex: 1;
		min-height: 0;
	}
	.overlay {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		background: color-mix(in srgb, var(--bg) 60%, transparent);
	}
	.summary {
		text-align: center;
		min-width: 240px;
	}
	h2 {
		margin: 0;
	}
	.big {
		font-size: 2.25rem;
		font-weight: 800;
		margin: 0.25rem 0 0;
	}
	.record {
		font-weight: 600;
	}
	.actions {
		display: flex;
		gap: 1rem;
		justify-content: center;
		align-items: center;
		margin-top: 1rem;
	}
</style>

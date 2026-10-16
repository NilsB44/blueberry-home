<script lang="ts">
	import { drawMini, fit } from './draw.ts';
	import { COLS, HIDDEN, ROWS } from './game.ts';

	let {
		name,
		board,
		score,
		out = false,
		cell = 6
	}: { name: string; board: string; score: number; out?: boolean; cell?: number } = $props();

	let canvas: HTMLCanvasElement;

	$effect(() => {
		drawMini(fit(canvas, COLS * cell, (ROWS - HIDDEN) * cell), board, cell, out);
	});
</script>

<figure class:out>
	<canvas bind:this={canvas}></canvas>
	<figcaption>
		<strong>{name}</strong>
		<span class="muted">{out ? 'Out' : score.toLocaleString()}</span>
	</figcaption>
</figure>

<style>
	figure {
		margin: 0;
		display: grid;
		justify-items: center;
		gap: 2px;
		font-size: 0.75rem;
	}
	canvas {
		border-radius: 4px;
	}
	figcaption {
		display: grid;
		justify-items: center;
		line-height: 1.2;
		max-width: 80px;
	}
	strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 100%;
	}
</style>

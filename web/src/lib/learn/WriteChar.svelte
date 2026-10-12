<script lang="ts">
	// Draw a character stroke by stroke. Hanzi Writer checks each stroke against the
	// stroke-order data the API serves, so this works offline on the Pi.
	import HanziWriter from 'hanzi-writer';
	import { onMount } from 'svelte';
	import { api } from '../api.ts';
	import SpeakButton from './SpeakButton.svelte';

	let {
		courseId,
		char,
		reading,
		en,
		onDone
	}: { courseId: string; char: string; reading: string; en: string; onDone: (mistakes: number) => void } = $props();

	let box = $state<HTMLDivElement | null>(null);
	let writer: HanziWriter | null = null;
	let outline = $state(true);
	let finished = $state(false);
	let error = $state('');

	onMount(() => {
		if (!box) return;
		const size = Math.min(280, box.clientWidth || 280);
		// Follow the theme so strokes stay visible in dark mode.
		const css = getComputedStyle(box);
		const color = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
		writer = HanziWriter.create(box, char, {
			width: size,
			height: size,
			padding: 10,
			showCharacter: false,
			showOutline: true,
			showHintAfterMisses: 2,
			highlightOnComplete: true,
			drawingWidth: 24,
			strokeColor: color('--accent', '#2563eb'),
			outlineColor: color('--border', '#d4d4d8'),
			drawingColor: color('--text', '#3f3f46'),
			charDataLoader: (c, onLoad, onError) => {
				api(`/learn/${courseId}/strokes/${encodeURIComponent(c)}`)
					.then((data) => onLoad(data as Parameters<typeof onLoad>[0]))
					.catch((e) => {
						error = 'No stroke data for this character.';
						onError(e);
					});
			}
		});
		start();
		return () => writer?.cancelQuiz();
	});

	function start() {
		writer?.quiz({
			onComplete: ({ totalMistakes }) => {
				finished = true;
				onDone(totalMistakes);
			}
		});
	}

	function toggleOutline() {
		outline = !outline;
		if (outline) writer?.showOutline();
		else writer?.hideOutline();
	}

	function demo() {
		writer?.cancelQuiz();
		writer?.hideCharacter();
		writer?.animateCharacter({ onComplete: () => {
			writer?.hideCharacter();
			start();
		} });
	}
</script>

<h2 class="muted small">Write the character</h2>
<p class="prompt"><strong>{reading}</strong> · {en} <SpeakButton text={char} /></p>
<div class="box" bind:this={box}>
	<svg class="grid" viewBox="0 0 100 100" aria-hidden="true">
		<line x1="0" y1="0" x2="100" y2="100" /><line x1="100" y1="0" x2="0" y2="100" />
		<line x1="50" y1="0" x2="50" y2="100" /><line x1="0" y1="50" x2="100" y2="50" />
	</svg>
</div>
{#if error}<p class="error">{error}</p>{/if}
{#if !finished}
	<div class="tools">
		<button type="button" class="ghost" onclick={demo}>Show me</button>
		<button type="button" class="ghost" onclick={toggleOutline}>{outline ? 'Hide' : 'Show'} outline</button>
	</div>
	<p class="muted small">Draw each stroke in order. After two misses the next stroke is highlighted.</p>
{/if}

<style>
	h2.small {
		font-size: 0.95rem;
		font-weight: 500;
		margin: 0;
	}
	.prompt {
		font-size: 1.35rem;
		margin: 0;
	}
	.box {
		position: relative;
		width: min(280px, 100%);
		aspect-ratio: 1;
		margin: 0 auto;
		border: 2px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		touch-action: none;
	}
	.box :global(svg:not(.grid)) {
		position: relative;
	}
	.grid {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		stroke: var(--border);
		stroke-dasharray: 2 2;
		stroke-width: 0.4;
	}
	.tools {
		display: flex;
		gap: 0.5rem;
		justify-content: center;
	}
	p.small {
		font-size: 0.85rem;
		text-align: center;
		margin: 0;
	}
</style>

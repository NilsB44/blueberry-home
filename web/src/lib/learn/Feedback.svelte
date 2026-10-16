<script lang="ts">
	import { course } from './course.svelte.ts';
	import type { CheckResult } from './types.ts';

	let { result, onContinue }: { result: CheckResult; onContinue: () => void } = $props();

	const TITLES = $derived({
		correct: 'Correct!',
		accent: course.chinese ? 'Correct, but check the tones:' : 'Correct, mind the accents and apostrophes:',
		typo: 'Correct, with a typo',
		wrong: 'Correct answer:'
	});
</script>

<div class="feedback {result.correct ? (result.verdict === 'correct' ? 'good' : 'near') : 'bad'}">
	<div>
		<strong>{TITLES[result.verdict]}</strong>
		{#if result.verdict !== 'correct'}<div class="expected">{result.expected}</div>{/if}
	</div>
	<!-- svelte-ignore a11y_autofocus -->
	<button autofocus onclick={onContinue}>Continue</button>
</div>

<style>
	.feedback {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem;
		border-radius: var(--radius);
	}
	.good {
		background: var(--good-bg);
		color: var(--good);
	}
	.near {
		background: var(--near-bg);
		color: var(--near);
	}
	.bad {
		background: var(--bad-bg);
		color: var(--danger);
	}
	.expected {
		color: var(--text);
		font-size: 1.05rem;
	}
</style>

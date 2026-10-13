<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import AccentKeys from '#lib/learn/AccentKeys.svelte';
	import Feedback from '#lib/learn/Feedback.svelte';
	import SpeakButton from '#lib/learn/SpeakButton.svelte';
	import { speak } from '#lib/learn/speech.ts';
	import type { CheckResult, ReviewItem } from '#lib/learn/types.ts';

	const courseId = $derived(page.params.course ?? '');

	let items = $state<ReviewItem[] | null>(null);
	let index = $state(0);
	let text = $state('');
	let input = $state<HTMLInputElement | null>(null);
	let result = $state<CheckResult | null>(null);
	let correct = $state(0);
	let error = $state('');

	$effect(() => {
		api<ReviewItem[]>(`/learn/${courseId}/review?limit=20`)
			.then((r) => (items = r))
			.catch((e) => (error = e.message));
	});

	const item = $derived(items?.[index]);

	$effect(() => {
		if (item && item.mode === 'listen') speak(item.prompt);
	});

	$effect(() => {
		if (item && !result) input?.focus();
	});

	const INSTRUCTIONS = {
		fr_en: 'Write this in English',
		en_fr: 'Write this in French',
		listen: 'Type what you hear'
	};

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!item || !text.trim() || result) return;
		try {
			result = await api<CheckResult>(`/learn/${courseId}/review/${item.id}`, {
				method: 'POST',
				json: { mode: item.mode, answer: text }
			});
			if (result.correct) correct++;
			if (item.mode === 'en_fr') speak(result.expected);
		} catch (err) {
			error = (err as Error).message;
		}
	}

	function next() {
		result = null;
		text = '';
		index++;
	}
</script>

<section>
	<div class="top">
		<a href={`/learn/${courseId}`} class="close" aria-label="Quit review">✕</a>
		<progress max={items?.length ?? 1} value={index}></progress>
	</div>
	{#if error}<p class="error">{error}</p>{/if}

	{#if items && items.length === 0}
		<p class="card">Nothing to review right now. Finish a lesson or come back later.</p>
		<a href={`/learn/${courseId}`}>Back to the course</a>
	{:else if items && !item}
		<div class="done">
			<h1>Révision terminée !</h1>
			<p class="big">{correct}/{items.length}</p>
			<p class="muted">Words you missed will come back soon; the rest are scheduled further out.</p>
			<a href={`/learn/${courseId}`}>Back to the course</a>
		</div>
	{:else if item}
		<form onsubmit={submit}>
			<h2 class="muted">{INSTRUCTIONS[item.mode]}</h2>
			{#if item.mode === 'listen'}
				<p class="center"><SpeakButton text={item.prompt} big /></p>
			{:else}
				<p class="prompt">{item.prompt} {#if item.mode === 'fr_en'}<SpeakButton text={item.prompt} />{/if}</p>
			{/if}
			<input bind:this={input} bind:value={text} disabled={result !== null} autocomplete="off" autocapitalize="off" spellcheck="false" />
			{#if item.mode !== 'fr_en' && !result}
				<AccentKeys target={input} onInsert={(v) => (text = v)} />
			{/if}
			{#if !result}<button disabled={!text.trim()}>Check</button>{/if}
		</form>
		{#if result}<Feedback {result} onContinue={next} />{/if}
	{/if}
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 640px;
		margin: 0 auto;
		display: grid;
		gap: 1.25rem;
	}
	form {
		display: grid;
		gap: 1rem;
	}
	h2 {
		font-size: 0.95rem;
		font-weight: 500;
		margin: 0;
	}
	.prompt {
		font-size: 1.5rem;
		margin: 0;
	}
	.center,
	.done {
		text-align: center;
	}
	.top {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	.close {
		text-decoration: none;
		color: var(--muted);
		font-size: 1.2rem;
	}
	progress {
		flex: 1;
		height: 0.9rem;
		accent-color: var(--accent);
	}
	.big {
		font-size: 2rem;
		font-weight: 700;
		color: var(--accent);
	}
</style>

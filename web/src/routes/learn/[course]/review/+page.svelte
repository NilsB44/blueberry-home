<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import AccentKeys from '#lib/learn/AccentKeys.svelte';
	import { course, loadCourse, spoken } from '#lib/learn/course.svelte.ts';
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
		Promise.all([api<ReviewItem[]>(`/learn/${courseId}/review?limit=20`), loadCourse(courseId)])
			.then(([r]) => (items = r))
			.catch((e) => (error = e.message));
	});

	const item = $derived(items?.[index]);

	$effect(() => {
		if (item && item.mode === 'listen') speak(item.prompt);
	});

	$effect(() => {
		if (item && !result) input?.focus();
	});

	const INSTRUCTIONS = $derived({
		to_en: 'Write this in English',
		from_en: `Write this in ${course.meta?.name ?? 'French'}`,
		listen: 'Type what you hear'
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!item || !text.trim() || result) return;
		try {
			result = await api<CheckResult>(`/learn/${courseId}/review/${item.id}`, {
				method: 'POST',
				json: { mode: item.mode, answer: text }
			});
			if (result.correct) correct++;
			if (item.mode === 'from_en') speak(spoken(result.expected));
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
			<h1>Review done!</h1>
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
				<p class="prompt">{item.prompt} {#if item.mode === 'to_en'}<SpeakButton text={item.prompt} />{/if}</p>
				{#if item.reading}<p class="reading">{item.reading}</p>{/if}
			{/if}
			<input bind:this={input} bind:value={text} disabled={result !== null} autocomplete="off" autocapitalize="off" spellcheck="false" />
			{#if item.mode !== 'to_en' && !result}
				{#if course.chinese}
					{#if course.meta?.answer_hint}<p class="muted hint">{course.meta.answer_hint}</p>{/if}
				{:else}
					<AccentKeys target={input} onInsert={(v) => (text = v)} />
				{/if}
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
	.reading {
		margin: -0.6rem 0 0;
		color: var(--muted);
		font-size: 1.1rem;
	}
	.hint {
		font-size: 0.85rem;
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

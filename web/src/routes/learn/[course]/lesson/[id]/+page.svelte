<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import ExerciseView from '#lib/learn/ExerciseView.svelte';
	import Feedback from '#lib/learn/Feedback.svelte';
	import SpeakButton from '#lib/learn/SpeakButton.svelte';
	import type { CheckResult, Lesson, Stats } from '#lib/learn/types.ts';

	const courseId = $derived(page.params.course ?? '');
	const lessonId = $derived(page.params.id ?? '');

	let lesson = $state<Lesson | null>(null);
	let started = $state(false);
	// Exercises answered wrong go to the back of the queue, like Duolingo.
	let queue = $state<number[]>([]);
	let step = $state(0); // bumps on every attempt so the exercise view resets
	let solved = $state(0);
	let mistakes = $state(0);
	let result = $state<CheckResult | null>(null);
	let finished = $state<{ xp: number; new_words: number; stats: Stats } | null>(null);
	let error = $state('');

	$effect(() => {
		api<Lesson>(`/learn/${courseId}/lessons/${lessonId}`)
			.then((l) => {
				lesson = l;
				queue = l.exercises.map((_, i) => i);
				if (!l.intro && l.vocab.length === 0) started = true;
			})
			.catch((e) => (error = e.message));
	});

	const current = $derived(queue[0]);
	const total = $derived(lesson?.exercises.length ?? 1);

	async function submit(answer: string) {
		try {
			result = await api<CheckResult>(`/learn/${courseId}/lessons/${lessonId}/check`, {
				method: 'POST',
				json: { index: current, answer }
			});
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function matchDone(m: number) {
		mistakes += m;
		result = { verdict: 'correct', correct: true, expected: '' };
	}

	async function next() {
		if (!result) return;
		const [head, ...rest] = queue;
		if (result.correct) {
			solved++;
			queue = rest;
		} else {
			mistakes++;
			queue = [...rest, head];
		}
		result = null;
		step++;
		if (queue.length === 0) {
			finished = await api(`/learn/${courseId}/lessons/${lessonId}/complete`, {
				method: 'POST',
				json: { mistakes }
			});
		}
	}
</script>

<section>
	<div class="top">
		<a href={`/learn/${courseId}`} class="close" aria-label="Quit lesson">✕</a>
		<progress max={total} value={solved}></progress>
	</div>
	{#if error}<p class="error">{error}</p>{/if}

	{#if finished}
		<div class="done">
			<h1>Leçon terminée ! 🎉</h1>
			<p class="big">+{finished.xp} XP</p>
			<p>{mistakes === 0 ? 'Perfect lesson, no mistakes.' : `${mistakes} mistake${mistakes === 1 ? '' : 's'}.`}</p>
			{#if finished.new_words}<p class="muted">{finished.new_words} new words added to your reviews.</p>{/if}
			<p>🔥 {finished.stats.streak} day streak · {finished.stats.xp_today}/{finished.stats.daily_goal} XP today</p>
			<a class="button" href={`/learn/${courseId}`}>Continue</a>
		</div>
	{:else if lesson && !started}
		<h1>{lesson.title}</h1>
		{#if lesson.intro}<p class="card">{lesson.intro}</p>{/if}
		{#if lesson.vocab.length}
			<h2>New words</h2>
			<ul class="vocab">
				{#each lesson.vocab as v}
					<li><SpeakButton text={v.fr} /> <strong>{v.fr}</strong> <span class="muted">{v.en}</span></li>
				{/each}
			</ul>
		{/if}
		<button class="wide" onclick={() => (started = true)}>Start lesson</button>
	{:else if lesson && current !== undefined}
		{#key step}
			<ExerciseView ex={lesson.exercises[current]} locked={result !== null} onSubmit={submit} onMatchDone={matchDone} />
		{/key}
		{#if result}
			<Feedback {result} onContinue={next} />
		{/if}
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
	.vocab {
		list-style: none;
		padding: 0;
		display: grid;
		gap: 0.35rem;
	}
	.wide,
	.button {
		width: 100%;
		padding: 0.8rem;
		text-align: center;
	}
	.button {
		display: block;
		background: var(--accent);
		color: var(--accent-text);
		border-radius: 8px;
		font-weight: 600;
		text-decoration: none;
	}
	.done {
		text-align: center;
	}
	.big {
		font-size: 2rem;
		font-weight: 700;
		color: var(--accent);
		margin: 0;
	}
</style>

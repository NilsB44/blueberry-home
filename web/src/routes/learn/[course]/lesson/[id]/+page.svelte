<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import ExerciseView from '#lib/learn/ExerciseView.svelte';
	import { loadCourse, prefs } from '#lib/learn/course.svelte.ts';
	import Feedback from '#lib/learn/Feedback.svelte';
	import LearnCards from '#lib/learn/LearnCards.svelte';
	import SpeakButton from '#lib/learn/SpeakButton.svelte';
	import type { CheckResult, Lesson, Stats } from '#lib/learn/types.ts';

	const courseId = $derived(page.params.course ?? '');
	const lessonId = $derived(page.params.id ?? '');

	let lesson = $state<Lesson | null>(null);
	// intro → learn the new words → exercises
	let phase = $state<'intro' | 'learn' | 'practice'>('intro');
	let showWords = $state(false);
	// Exercises answered wrong go to the back of the queue, like Duolingo.
	let queue = $state<number[]>([]);
	let step = $state(0); // bumps on every attempt so the exercise view resets
	let solved = $state(0);
	let mistakes = $state(0);
	let result = $state<CheckResult | null>(null);
	let finished = $state<{ xp: number; new_words: number; stats: Stats } | null>(null);
	let error = $state('');
	let total = $state(1);

	$effect(() => {
		Promise.all([api<Lesson>(`/learn/${courseId}/lessons/${lessonId}`), loadCourse(courseId)])
			.then(([l]) => {
				lesson = l;
				const all = l.exercises.map((_, i) => i);
				const kept = prefs.writing ? all : all.filter((i) => l.exercises[i].type !== 'write');
				queue = kept.length ? kept : all;
				total = queue.length;
				if (!l.intro && l.vocab.length === 0) phase = 'practice';
			})
			.catch((e) => (error = e.message));
	});

	const current = $derived(queue[0]);

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

	function localDone(m: number) {
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
		{#if lesson?.vocab.length && phase === 'practice' && !finished}
			<button type="button" class="ghost" aria-expanded={showWords} onclick={() => (showWords = !showWords)}>📖 Words</button>
		{/if}
	</div>
	{#if showWords && lesson && phase === 'practice' && !finished}
		<ul class="card vocab">
			{#each lesson.vocab as v}
				<li>
					<SpeakButton text={v.word} /> <strong>{v.word}</strong>
					{#if v.reading}<span class="reading">{v.reading}</span>{/if}
					<span class="muted">{v.en}</span>
					{#if v.note}<div class="muted note">{v.note}</div>{/if}
				</li>
			{/each}
		</ul>
	{/if}
	{#if error}<p class="error">{error}</p>{/if}

	{#if finished}
		<div class="done">
			<h1>Lesson complete! 🎉</h1>
			<p class="big">+{finished.xp} XP</p>
			<p>{mistakes === 0 ? 'Perfect lesson, no mistakes.' : `${mistakes} mistake${mistakes === 1 ? '' : 's'}.`}</p>
			{#if finished.new_words}<p class="muted">{finished.new_words} new words added to your reviews.</p>{/if}
			<p>🔥 {finished.stats.streak} day streak · {finished.stats.xp_today}/{finished.stats.daily_goal} XP today</p>
			<a class="button" href={`/learn/${courseId}`}>Continue</a>
		</div>
	{:else if lesson && phase === 'intro'}
		<h1>{lesson.title}</h1>
		{#if lesson.intro}<p class="card">{lesson.intro}</p>{/if}
		{#if lesson.vocab.length}
			<p class="muted">This lesson has {lesson.vocab.length} new words. Learn them first, then practise.</p>
			<button class="wide" onclick={() => (phase = 'learn')}>Learn the new words</button>
			<button class="wide secondary" onclick={() => (phase = 'practice')}>Skip to the exercises</button>
		{:else}
			<button class="wide" onclick={() => (phase = 'practice')}>Start lesson</button>
		{/if}
	{:else if lesson && phase === 'learn'}
		<LearnCards vocab={lesson.vocab} onDone={() => (phase = 'practice')} />
	{:else if lesson && current !== undefined}
		{#key step}
			<ExerciseView ex={lesson.exercises[current]} locked={result !== null} onSubmit={submit} onLocalDone={localDone} />
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
		margin: 0;
		display: grid;
		gap: 0.35rem;
	}
	.reading {
		color: var(--accent);
	}
	.note {
		font-size: 0.85rem;
		margin-left: 2.6rem;
	}
	.wide,
	.button {
		width: 100%;
		padding: 0.8rem;
		text-align: center;
	}
	.secondary {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
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

<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import { course, prefs, savePrefs, setCourse } from '#lib/learn/course.svelte.ts';
	import type { CourseOverview, Stats } from '#lib/learn/types.ts';

	const courseId = $derived(page.params.course ?? '');
	let overview = $state<CourseOverview | null>(null);
	const meta = $derived(overview?.meta ?? { name: '', flag: '' });
	let stats = $state<Stats | null>(null);
	let error = $state('');

	$effect(() => {
		Promise.all([
			api<CourseOverview>(`/learn/${courseId}/course`),
			api<Stats>(`/learn/${courseId}/stats`)
		])
			.then(([o, s]) => {
				setCourse(o);
				overview = o;
				stats = s;
			})
			.catch((e) => (error = e.message));
	});
</script>

<section>
	<h1>{meta.flag} {meta.name}</h1>
	{#if error}<p class="error">{error}</p>{/if}

	{#if stats}
		<div class="stats">
			<div class="card stat"><span class="big">🔥 {stats.streak}</span><span class="muted">day streak</span></div>
			<div class="card stat">
				<span class="big">{stats.xp_today}/{stats.daily_goal}</span><span class="muted">XP today</span>
				<progress max={stats.daily_goal} value={Math.min(stats.xp_today, stats.daily_goal)}></progress>
			</div>
			<div class="card stat"><span class="big">{stats.words}</span><span class="muted">words learned</span></div>
		</div>

		<a class="card review" class:empty={stats.due === 0} href={`/learn/${courseId}/review`}>
			<strong>Review</strong>
			<span class="muted">{stats.due === 0 ? 'Nothing due. Come back later.' : `${stats.due} words due`}</span>
		</a>
	{/if}

	{#if overview && course.chinese}
		<details class="card prefs">
			<summary>Can't read characters yet?</summary>
			<p class="muted small">
				You don't need to. Learn the sounds first with pinyin printed above every character, and
				answer by typing pinyin. The characters will start to look familiar on their own.
			</p>
			<label><input type="checkbox" bind:checked={prefs.pinyin} onchange={savePrefs} /> Show pinyin above characters</label>
			<label><input type="checkbox" bind:checked={prefs.writing} onchange={savePrefs} /> Include character-writing exercises</label>
		</details>
	{/if}

	{#if overview}
		{#each overview.units as unit}
			<h2>{unit.title} <span class="muted level">{unit.cefr}</span></h2>
			<p class="muted">{unit.description}</p>
			<ol class="lessons">
				{#each unit.lessons as lesson}
					<li>
						<a
							class="card lesson"
							class:done={lesson.completed}
							class:next={lesson.id === overview.next_lesson}
							href={`/learn/${courseId}/lesson/${lesson.id}`}
						>
							<span class="mark">{lesson.completed ? (lesson.best_mistakes === 0 ? '⭐' : '✓') : '○'}</span>
							<span>
								<strong>{lesson.title}</strong>
								<span class="muted small">{lesson.exercises} exercises</span>
							</span>
							{#if lesson.id === overview.next_lesson}<span class="go">Start</span>{/if}
						</a>
					</li>
				{/each}
			</ol>
		{/each}
	{/if}
</section>

<style>
	section {
		padding: 1.5rem 16px;
		max-width: 640px;
		margin: 0 auto;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.5rem;
	}
	.stat {
		display: grid;
		gap: 0.15rem;
		padding: 0.75rem;
		text-align: center;
	}
	.big {
		font-size: 1.3rem;
		font-weight: 700;
	}
	progress {
		width: 100%;
		accent-color: var(--accent);
	}
	.review {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 0.75rem;
		text-decoration: none;
		border-color: var(--accent);
	}
	.review.empty {
		border-color: var(--border);
	}
	.level {
		font-size: 0.8rem;
		font-weight: 500;
	}
	.lessons {
		list-style: none;
		padding: 0;
		display: grid;
		gap: 0.5rem;
	}
	.lesson {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		text-decoration: none;
	}
	.lesson > span:nth-child(2) {
		display: grid;
		flex: 1;
	}
	.lesson.next {
		border-color: var(--accent);
	}
	.mark {
		font-size: 1.2rem;
		width: 1.5rem;
		text-align: center;
	}
	.small {
		font-size: 0.85rem;
	}
	.prefs {
		margin-top: 0.75rem;
		display: grid;
		gap: 0.4rem;
	}
	.prefs summary {
		cursor: pointer;
		font-weight: 600;
	}
	.prefs label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.prefs input {
		width: auto;
	}
	.prefs p {
		margin: 0.25rem 0;
	}
	.go {
		color: var(--accent);
		font-weight: 600;
	}
</style>

<script lang="ts">
	import AccentKeys from './AccentKeys.svelte';
	import { course, prefs } from './course.svelte.ts';
	import Hanzi from './Hanzi.svelte';
	import SpeakButton from './SpeakButton.svelte';
	import { speak } from './speech.ts';
	import type { Exercise } from './types.ts';
	import WriteChar from './WriteChar.svelte';

	let {
		ex,
		locked,
		onSubmit,
		onLocalDone
	}: {
		ex: Exercise;
		locked: boolean;
		onSubmit: (answer: string) => void;
		/** Match and write exercises are checked in the browser. */
		onLocalDone: (mistakes: number) => void;
	} = $props();

	const language = $derived(course.meta?.name ?? 'French');
	const lang = $derived(course.meta?.lang ?? 'fr-FR');

	let text = $state('');
	let choice = $state<string | null>(null);
	let picked = $state<number[]>([]); // word bank: indexes into tiles
	let input = $state<HTMLInputElement | null>(null);

	// Match state
	let left = $state<string | null>(null);
	let done = $state<string[]>([]);
	let wrongFlash = $state<string | null>(null);
	let matchMistakes = 0;

	const rights = $derived(ex.type === 'match' ? shuffle(ex.pairs.map((p) => p[1])) : []);
	const lefts = $derived(ex.type === 'match' ? shuffle(ex.pairs.map((p) => p[0])) : []);

	$effect(() => {
		if (ex.type === 'listen') speak(ex.text);
		if (ex.type === 'choice' && ex.speak) speak(ex.speak);
	});

	function shuffle<T>(xs: T[]): T[] {
		const a = [...xs];
		for (let i = a.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[a[i], a[j]] = [a[j], a[i]];
		}
		return a;
	}

	const answer = $derived.by(() => {
		switch (ex.type) {
			case 'choice':
				return choice ?? '';
			case 'word_bank':
				return picked.map((i) => ex.tiles[i]).join(' ');
			case 'gap':
				return ex.options.length ? (choice ?? '') : text;
			default:
				return text;
		}
	});

	// Free-text answers in the language being learned get accent keys (French) or a pinyin hint.
	const typesTarget = $derived(
		(ex.type === 'translate' && ex.source === 'en') || ex.type === 'listen' || (ex.type === 'gap' && !ex.options.length)
	);

	function submit(e?: Event) {
		e?.preventDefault();
		if (!locked && answer.trim()) onSubmit(answer);
	}

	function pickRight(r: string) {
		if (ex.type !== 'match' || !left) return;
		const pair = ex.pairs.find((p) => p[0] === left);
		if (pair && pair[1] === r) {
			done = [...done, left];
			speak(left);
			left = null;
			if (done.length === ex.pairs.length) onLocalDone(matchMistakes);
		} else {
			matchMistakes++;
			wrongFlash = r;
			setTimeout(() => (wrongFlash = null), 400);
		}
	}

	const doneRights = $derived(
		ex.type === 'match' ? ex.pairs.filter((p) => done.includes(p[0])).map((p) => p[1]) : []
	);
</script>

<form class="exercise" onsubmit={submit}>
	{#if ex.type === 'choice'}
		<h2><Hanzi text={ex.prompt} /> {#if ex.speak}<SpeakButton text={ex.speak} />{/if}</h2>
		<div class="options">
			{#each ex.options as o}
				<button type="button" class="option" class:selected={choice === o} disabled={locked} onclick={() => (choice = o)}><Hanzi text={o} /></button>
			{/each}
		</div>
	{:else if ex.type === 'translate'}
		<h2 class="muted small">Write this in {ex.source === 'target' ? 'English' : language}</h2>
		<p class="prompt"><Hanzi text={ex.prompt} /> {#if ex.source === 'target'}<SpeakButton text={ex.prompt} />{/if}</p>
		{#if ex.prompt_reading && !(course.chinese && prefs.pinyin)}<p class="reading">{ex.prompt_reading}</p>{/if}
		<input bind:this={input} bind:value={text} disabled={locked} autocomplete="off" autocapitalize="off" spellcheck="false" lang={ex.source === 'target' ? 'en' : lang} />
	{:else if ex.type === 'word_bank'}
		<h2 class="muted small">Translate this sentence</h2>
		<p class="prompt">{ex.prompt}</p>
		<div class="built">
			{#each picked as i, pos (i)}
				<button type="button" class="word-tile" disabled={locked} onclick={() => picked.splice(pos, 1)}><Hanzi text={ex.tiles[i]} /></button>
			{/each}
		</div>
		<div class="pool">
			{#each ex.tiles as t, i}
				<button type="button" class="word-tile" class:used={picked.includes(i)} disabled={locked || picked.includes(i)} onclick={() => picked.push(i)}><Hanzi text={t} /></button>
			{/each}
		</div>
	{:else if ex.type === 'listen'}
		<h2 class="muted small">Type what you hear</h2>
		<p class="center"><SpeakButton text={ex.text} big /></p>
		<input bind:this={input} bind:value={text} disabled={locked} autocomplete="off" autocapitalize="off" spellcheck="false" {lang} />
	{:else if ex.type === 'gap'}
		<h2 class="muted small">Fill in the blank</h2>
		<p class="prompt">
			{#each ex.prompt.split('___') as part, i}
				<Hanzi text={part} />{#if i === 0}<span class="blank"><Hanzi text={(ex.options.length ? choice : text) || '  '} /></span>{/if}
			{/each}
		</p>
		{#if ex.hint}<p class="muted">{ex.hint}</p>{/if}
		{#if ex.options.length}
			<div class="pool">
				{#each ex.options as o}
					<button type="button" class="word-tile" class:chosen={choice === o} disabled={locked} onclick={() => (choice = o)}><Hanzi text={o} /></button>
				{/each}
			</div>
		{:else}
			<input bind:this={input} bind:value={text} disabled={locked} autocomplete="off" autocapitalize="off" spellcheck="false" {lang} />
		{/if}
	{:else if ex.type === 'match'}
		<h2 class="muted small">Tap the matching pairs</h2>
		<div class="match">
			<div class="col">
				{#each lefts as l}
					<button type="button" class="word-tile" class:chosen={left === l} disabled={done.includes(l)} onclick={() => { left = l; speak(l); }}><Hanzi text={l} /></button>
				{/each}
			</div>
			<div class="col">
				{#each rights as r}
					<button type="button" class="word-tile" class:wrong={wrongFlash === r} disabled={doneRights.includes(r)} onclick={() => pickRight(r)}>{r}</button>
				{/each}
			</div>
		</div>
	{:else if ex.type === 'write'}
		<WriteChar courseId={course.id} char={ex.char} reading={ex.reading} en={ex.en} onDone={onLocalDone} />
	{/if}

	{#if typesTarget && !locked}
		{#if course.chinese}
			{#if course.meta?.answer_hint}<p class="muted hint">{course.meta.answer_hint}</p>{/if}
		{:else}
			<AccentKeys target={input} onInsert={(v) => (text = v)} />
		{/if}
	{/if}

	{#if ex.type !== 'match' && ex.type !== 'write' && !locked}
		<button class="check" disabled={!answer.trim()}>Check</button>
	{/if}
</form>

<style>
	.exercise {
		display: grid;
		gap: 1rem;
	}
	h2 {
		font-size: 1.3rem;
		margin: 0;
	}
	h2.small {
		font-size: 0.95rem;
		font-weight: 500;
	}
	.prompt {
		font-size: 1.35rem;
		margin: 0;
	}
	.center {
		text-align: center;
	}
	.reading {
		margin: -0.6rem 0 0;
		color: var(--muted);
		font-size: 1.05rem;
	}
	.hint {
		font-size: 0.85rem;
		margin: 0;
	}
	.options {
		display: grid;
		gap: 0.5rem;
	}
	.built {
		min-height: 3rem;
		border-bottom: 2px solid var(--border);
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		padding-bottom: 0.5rem;
	}
	.pool {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.used {
		visibility: hidden;
	}
	.chosen {
		border-color: var(--accent);
	}
	.wrong {
		border-color: var(--danger);
		animation: shake 0.3s;
	}
	.blank {
		display: inline-block;
		min-width: 3rem;
		border-bottom: 2px solid var(--accent);
		text-align: center;
	}
	.match {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	.col {
		display: grid;
		gap: 0.5rem;
		align-content: start;
	}
	.match button:disabled {
		opacity: 0.35;
	}
	.check {
		width: 100%;
		padding: 0.8rem;
	}
	@keyframes shake {
		25% {
			transform: translateX(-4px);
		}
		75% {
			transform: translateX(4px);
		}
	}
</style>

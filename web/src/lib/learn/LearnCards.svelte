<script lang="ts">
	// Teaches a lesson's new words before any exercise asks for them: a card per word, then a
	// quick "which one means…?" round after every few words. Nothing here is graded.
	import Hanzi from './Hanzi.svelte';
	import SpeakButton from './SpeakButton.svelte';
	import { speak } from './speech.ts';
	import type { Vocab } from './types.ts';

	let { vocab, onDone }: { vocab: Vocab[]; onDone: () => void } = $props();

	const GROUP = 4;
	const groups = $derived(
		Array.from({ length: Math.ceil(vocab.length / GROUP) }, (_, i) => vocab.slice(i * GROUP, (i + 1) * GROUP))
	);

	let group = $state(0);
	let card = $state(0); // index in the group while showing cards
	let quiz = $state<Vocab[] | null>(null); // words still to recognise in this group
	let options = $state<Vocab[]>([]);
	let picked = $state<Vocab | null>(null);
	let seen = $state(0);

	const words = $derived(groups[group] ?? []);
	const current = $derived(quiz ? quiz[0] : words[card]);

	function meaning(v: Vocab) {
		return v.en.split(' / ')[0];
	}

	function shuffle<T>(xs: T[]): T[] {
		const a = [...xs];
		for (let i = a.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[a[i], a[j]] = [a[j], a[i]];
		}
		return a;
	}

	function optionsFor(v: Vocab): Vocab[] {
		// Other words from this group first, topped up from the rest of the lesson.
		const others = shuffle(words.filter((w) => w !== v));
		const rest = shuffle(vocab.filter((w) => w !== v && !words.includes(w)));
		return shuffle([v, ...[...others, ...rest].slice(0, 3)]);
	}

	$effect(() => {
		if (!quiz && current) speak(current.word);
	});

	function nextCard() {
		seen++;
		if (card < words.length - 1) {
			card++;
		} else if (vocab.length > 1) {
			quiz = shuffle(words);
			options = optionsFor(quiz[0]);
		} else {
			onDone();
		}
	}

	function pick(v: Vocab) {
		if (picked || !quiz) return;
		picked = v;
		speak(quiz[0].word);
	}

	function nextQuestion() {
		if (!quiz || !picked) return;
		const [head, ...rest] = quiz;
		// Missed words come back at the end of the round.
		quiz = picked === head ? rest : [...rest, head];
		picked = null;
		if (quiz.length) {
			options = optionsFor(quiz[0]);
		} else if (group < groups.length - 1) {
			quiz = null;
			group++;
			card = 0;
		} else {
			onDone();
		}
	}
</script>

<div class="learn">
	<p class="muted small">New words · {quiz ? seen : Math.min(seen + 1, vocab.length)} of {vocab.length}</p>
	{#if quiz && current}
		<h2>Which one means “{meaning(current)}”?</h2>
		<div class="options">
			{#each options as o}
				<button
					type="button"
					class="option"
					class:right={picked && o === current}
					class:wrong={picked === o && o !== current}
					disabled={picked !== null}
					onclick={() => pick(o)}><Hanzi text={o.word} /></button
				>
			{/each}
		</div>
		{#if picked}
			<p class="muted">
				<strong>{current.word}</strong>{#if current.reading}&nbsp;· {current.reading}{/if} means {current.en}
			</p>
			<!-- svelte-ignore a11y_autofocus -->
			<button class="wide" autofocus onclick={nextQuestion}>Continue</button>
		{/if}
	{:else if current}
		<div class="card word">
			<p class="big">{current.word}</p>
			{#if current.reading}<p class="reading">{current.reading}</p>{/if}
			<p><SpeakButton text={current.word} big /></p>
			<p class="en">{current.en}</p>
			{#if current.note}<p class="muted">{current.note}</p>{/if}
		</div>
		<!-- svelte-ignore a11y_autofocus -->
		<button class="wide" autofocus onclick={nextCard}>Got it</button>
	{/if}
	<button type="button" class="link" onclick={onDone}>I know these, skip to the exercises</button>
</div>

<style>
	.learn {
		display: grid;
		gap: 1rem;
	}
	.small {
		font-size: 0.85rem;
		margin: 0;
	}
	h2 {
		font-size: 1.3rem;
		margin: 0;
	}
	.word {
		text-align: center;
		display: grid;
		gap: 0.25rem;
	}
	.word p {
		margin: 0;
	}
	.big {
		font-size: 2.4rem;
		font-weight: 700;
	}
	.reading {
		font-size: 1.3rem;
		color: var(--accent);
	}
	.en {
		font-size: 1.15rem;
	}
	.options {
		display: grid;
		gap: 0.5rem;
	}
	.option {
		font-size: 1.2rem;
	}
	.option:disabled {
		opacity: 1;
	}
	.right {
		border-color: var(--good);
		background: var(--good-bg);
	}
	.wrong {
		border-color: var(--danger);
		background: var(--bad-bg);
	}
	.wide {
		width: 100%;
		padding: 0.8rem;
	}
	.link {
		background: none;
		border: none;
		color: var(--muted);
		text-decoration: underline;
		font-weight: 400;
	}
</style>

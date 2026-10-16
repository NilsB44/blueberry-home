<script lang="ts">
	// Prints pinyin above Chinese characters when the learner wants it; plain text otherwise.
	import { annotate, course, prefs } from './course.svelte.ts';

	let { text }: { text: string } = $props();

	// "谢谢 (xièxie)": the pinyin in brackets is redundant once it's printed above.
	const BRACKETED_PINYIN = /\s*\([^()]*[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ][^()]*\)/g;

	const segments = $derived(
		course.chinese && prefs.pinyin ? annotate(text.replace(BRACKETED_PINYIN, '')) : [{ text }]
	);
</script>

{#each segments as s}{#if s.reading}<ruby>{s.text}<rt>{s.reading}</rt></ruby>{:else}{s.text}{/if}{/each}

<style>
	ruby {
		ruby-position: over;
	}
	rt {
		font-size: 0.6em;
		color: var(--accent);
		font-weight: 400;
	}
</style>

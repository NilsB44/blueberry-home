<script lang="ts">
	import { speak } from './speech.ts';

	let { text, lang = 'fr-FR', big = false }: { text: string; lang?: string; big?: boolean } = $props();
</script>

<span class="speak" class:big>
	<button type="button" class="ghost" aria-label="Play audio" onclick={() => speak(text, { lang })}>🔊</button>
	{#if big}
		<button type="button" class="ghost" aria-label="Play slowly" onclick={() => speak(text, { lang, slow: true })}>🐢</button>
	{/if}
</span>

<style>
	.speak {
		display: inline-flex;
		gap: 0.4rem;
		vertical-align: middle;
	}
	.speak button {
		padding: 0.25rem 0.5rem;
	}
	.big button {
		font-size: 1.6rem;
		padding: 0.6rem 1rem;
	}
</style>

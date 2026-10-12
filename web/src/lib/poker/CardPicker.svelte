<script lang="ts">
	import { RANKS, SUITS } from './cards.ts';
	import PlayingCard from './PlayingCard.svelte';

	let { used, onPick, onClose }: { used: Set<string>; onPick: (c: string) => void; onClose: () => void } = $props();
</script>

<div class="backdrop" role="presentation" onclick={onClose}>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div class="sheet card" role="dialog" aria-label="Pick a card" tabindex="-1" onclick={(e) => e.stopPropagation()}>
		{#each SUITS as s}
			<div class="row">
				{#each RANKS as r}
					{@const c = r + s}
					{#if used.has(c)}
						<span class="gone"></span>
					{:else}
						<PlayingCard card={c} small onclick={() => onPick(c)} />
					{/if}
				{/each}
			</div>
		{/each}
		<button class="ghost" onclick={onClose}>Close</button>
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		background: rgb(0 0 0 / 0.45);
		display: flex;
		align-items: flex-end;
		justify-content: center;
		z-index: 10;
	}
	.sheet {
		width: 100%;
		max-width: 640px;
		display: grid;
		gap: 0.35rem;
		border-radius: var(--radius) var(--radius) 0 0;
		overflow-x: auto;
	}
	.row {
		display: grid;
		grid-template-columns: repeat(13, minmax(1.6rem, 1fr));
		gap: 0.2rem;
	}
	.row :global(.pc) {
		width: 100%;
		min-width: 0;
		font-size: 0.75rem;
	}
	.gone {
		height: 2.8rem;
	}
</style>

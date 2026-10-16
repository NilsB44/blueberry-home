<script lang="ts">
	import { isRed, label } from './cards.ts';

	let { card, onclick, small = false, active = false }: { card: string | null; onclick?: () => void; small?: boolean; active?: boolean } = $props();
</script>

<button type="button" class="pc" class:red={card && isRed(card)} class:empty={!card} class:small class:active {onclick}>
	{card ? label(card) : '?'}
</button>

<style>
	.pc {
		width: 2.6rem;
		height: 3.6rem;
		padding: 0;
		border-radius: 6px;
		background: #fff;
		color: #1a1a1a;
		border: 1px solid #c9ccd2;
		font-weight: 700;
		font-size: 1rem;
	}
	.pc.red {
		color: #c62828;
	}
	.pc.empty {
		background: transparent;
		color: var(--muted);
		border: 2px dashed var(--border);
	}
	.pc.active {
		outline: 3px solid var(--accent);
		outline-offset: 1px;
	}
	.pc.small {
		width: 2.2rem;
		height: 2.8rem;
		font-size: 0.85rem;
	}
</style>

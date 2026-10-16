<script lang="ts">
	import { isRed, label } from './cards.ts';

	let {
		card,
		onclick,
		small = false,
		active = false,
		hidden = false
	}: { card: string | null; onclick?: () => void; small?: boolean; active?: boolean; hidden?: boolean } = $props();
</script>

<button
	type="button"
	class="pc"
	class:red={card && isRed(card) && !hidden}
	class:empty={!card}
	class:back={card && hidden}
	class:small
	class:active
	{onclick}
	aria-label={card && hidden ? 'Face-down card' : undefined}
>
	{card ? (hidden ? '' : label(card)) : '?'}
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
	.pc.back {
		background: repeating-linear-gradient(45deg, #b0003a 0 4px, #d81b60 4px 8px);
		border: 2px solid #fff;
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

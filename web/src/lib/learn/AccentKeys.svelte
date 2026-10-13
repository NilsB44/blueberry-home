<script lang="ts">
	// Phone keyboards can long-press for accents, but laptops can't, so offer buttons.
	let { target, onInsert }: { target: HTMLInputElement | null; onInsert: (value: string) => void } = $props();
	const KEYS = ['é', 'è', 'ê', 'à', 'â', 'ç', 'ô', 'î', 'û', 'ù', 'ë', 'ï', 'œ'];

	function insert(ch: string) {
		if (!target) return;
		const start = target.selectionStart ?? target.value.length;
		const end = target.selectionEnd ?? start;
		const value = target.value.slice(0, start) + ch + target.value.slice(end);
		onInsert(value);
		requestAnimationFrame(() => {
			target.focus();
			target.setSelectionRange(start + 1, start + 1);
		});
	}
</script>

<div class="keys">
	{#each KEYS as k}
		<button type="button" class="key" onmousedown={(e) => e.preventDefault()} onclick={() => insert(k)}>{k}</button>
	{/each}
</div>

<style>
	.keys {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
	.key {
		padding: 0.25rem 0.55rem;
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		font-weight: 500;
	}
</style>

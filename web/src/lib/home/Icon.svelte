<script lang="ts">
	import type { ModuleInfo } from '#lib/api.ts';

	/** An app's rounded-square icon, or a folder's showing the first few apps inside it. */
	let {
		app,
		folder,
		small = false
	}: { app?: ModuleInfo; folder?: ModuleInfo[]; small?: boolean } = $props();

	// A steady hue per app so every icon gets its own soft colour.
	function hue(id: string) {
		let h = 0;
		for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 360;
		return h;
	}
</script>

{#if folder}
	<span class="squircle folder" class:small aria-hidden="true">
		{#each folder.slice(0, 4) as m (m.id)}
			<span class="mini" style:--h={hue(m.id)}>{m.icon}</span>
		{/each}
	</span>
{:else if app}
	<span class="squircle" class:small style:--h={hue(app.id)} aria-hidden="true">{app.icon}</span>
{/if}

<style>
	.squircle {
		--size: 4rem;
		width: var(--size);
		height: var(--size);
		border-radius: 28%;
		display: grid;
		place-items: center;
		font-size: calc(var(--size) * 0.5);
		line-height: 1;
		background: linear-gradient(145deg, hsl(var(--h) 85% 93%), hsl(calc(var(--h) + 25) 75% 84%));
		box-shadow:
			inset 0 0 0 1px rgb(255 255 255 / 0.35),
			0 2px 6px rgb(20 22 28 / 0.12);
		flex: none;
		user-select: none;
	}
	.small {
		--size: 2.75rem;
	}
	.folder {
		grid-template-columns: 1fr 1fr;
		grid-template-rows: 1fr 1fr;
		gap: 12%;
		padding: 16%;
		background: var(--surface-2);
		box-shadow:
			inset 0 0 0 1px var(--border),
			0 2px 6px rgb(20 22 28 / 0.1);
	}
	.mini {
		width: 100%;
		height: 100%;
		border-radius: 28%;
		display: grid;
		place-items: center;
		font-size: calc(var(--size) * 0.19);
		background: hsl(var(--h) 80% 88%);
	}
	:global(:root[data-theme='dark']) .squircle:not(.folder),
	:global(:root[data-theme='dark']) .mini {
		background: linear-gradient(145deg, hsl(var(--h) 35% 26%), hsl(calc(var(--h) + 25) 40% 18%));
		box-shadow:
			inset 0 0 0 1px rgb(255 255 255 / 0.06),
			0 2px 6px rgb(0 0 0 / 0.3);
	}
	@media (prefers-color-scheme: dark) {
		:global(:root:not([data-theme='light'])) .squircle:not(.folder),
		:global(:root:not([data-theme='light'])) .mini {
			background: linear-gradient(145deg, hsl(var(--h) 35% 26%), hsl(calc(var(--h) + 25) 40% 18%));
			box-shadow:
				inset 0 0 0 1px rgb(255 255 255 / 0.06),
				0 2px 6px rgb(0 0 0 / 0.3);
		}
	}
	@media (min-width: 720px) {
		.squircle:not(.small) {
			--size: 4.75rem;
		}
	}
</style>

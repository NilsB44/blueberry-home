<script lang="ts">
	import { page } from '$app/state';

	const TABS = [
		{ href: '/poker', label: 'Chart' },
		{ href: '/poker/calculator', label: 'Calculator' },
		{ href: '/poker/practice', label: 'Practice' },
		{ href: '/poker/games', label: 'Home games' }
	];
	const current = $derived(
		TABS.slice()
			.reverse()
			.find((t) => page.url.pathname === t.href || page.url.pathname.startsWith(t.href + '/'))?.href
	);
</script>

<nav>
	{#each TABS as t}
		<a href={t.href} class:on={current === t.href}>{t.label}</a>
	{/each}
</nav>

<style>
	nav {
		display: flex;
		gap: 0.25rem;
		border-bottom: 1px solid var(--border);
		margin-bottom: 1rem;
		overflow-x: auto;
	}
	a {
		padding: 0.6rem 0.8rem;
		text-decoration: none;
		color: var(--muted);
		border-bottom: 2px solid transparent;
		white-space: nowrap;
	}
	a.on {
		color: var(--text);
		border-color: var(--accent);
		font-weight: 600;
	}
</style>

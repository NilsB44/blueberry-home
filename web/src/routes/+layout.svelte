<script lang="ts">
	import '../app.css';
	import { loadSession, session } from '#lib/session.svelte.ts';
	import { isDark, toggleTheme } from '#lib/theme.svelte.ts';

	let { children } = $props();
	let loadError = $state('');
	const dark = $derived(isDark());

	$effect(() => {
		if (!session.loaded) loadSession().catch((e) => (loadError = `Can't reach the hub: ${e.message}`));
	});
</script>

{#if loadError}
	<p class="auth error">{loadError}</p>
{:else if session.loaded}
	{#if session.user}
		<header>
			<a href="/" class="brand"><img src="/icon.svg" alt="" width="28" height="28" />Blueberry Home</a>
			<nav>
				<a href="/people" class="link">People</a>
				<button
					class="round"
					onclick={toggleTheme}
					aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
					title={dark ? 'Light mode' : 'Dark mode'}
				>
					{#if dark}
						<svg viewBox="0 0 24 24" aria-hidden="true"
							><circle cx="12" cy="12" r="4.5" /><path
								d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"
							/></svg
						>
					{:else}
						<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" /></svg>
					{/if}
				</button>
				<a href="/me" class="round avatar" title="{session.user.display_name}: change your name">
					{session.user.display_name.slice(0, 1).toUpperCase()}
				</a>
			</nav>
		</header>
	{/if}
	<main>{@render children()}</main>
{/if}

<style>
	header {
		position: sticky;
		top: 0;
		z-index: 10;
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: calc(0.6rem + env(safe-area-inset-top)) 16px 0.6rem;
		background: color-mix(in srgb, var(--bg) 80%, transparent);
		backdrop-filter: saturate(1.4) blur(14px);
		-webkit-backdrop-filter: saturate(1.4) blur(14px);
		border-bottom: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		font-weight: 700;
		letter-spacing: -0.01em;
		text-decoration: none;
		margin-right: auto;
	}
	.brand img {
		border-radius: 8px;
	}
	nav {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.link {
		color: var(--muted);
		text-decoration: none;
		font-weight: 500;
		padding: 0.4rem 0.6rem;
		border-radius: 999px;
	}
	.link:hover {
		color: var(--text);
		background: var(--surface-2);
	}
	.round {
		width: 2.25rem;
		height: 2.25rem;
		padding: 0;
		border-radius: 50%;
		display: grid;
		place-items: center;
		background: var(--surface-2);
		color: var(--text);
		text-decoration: none;
		font-weight: 700;
		font-size: 0.95rem;
	}
	.round svg {
		width: 1.15rem;
		height: 1.15rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.8;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.avatar {
		background: var(--accent);
		color: var(--accent-text);
	}
	main {
		max-width: 1100px;
		margin: 0 auto;
	}
</style>

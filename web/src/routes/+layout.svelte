<script lang="ts">
	import '../app.css';
	import { loadSession, session } from '#lib/session.svelte.ts';

	let { children } = $props();
	let loadError = $state('');

	$effect(() => {
		if (!session.loaded) loadSession().catch((e) => (loadError = `Can't reach the hub: ${e.message}`));
	});
</script>

{#if loadError}
	<p class="auth error">{loadError}</p>
{:else if session.loaded}
	{#if session.user}
		<header>
			<a href="/" class="brand">Blueberry Home</a>
			<a href="/people" class="muted">People</a>
			<a href="/me" class="muted" title="Change your name">{session.user.display_name}</a>
		</header>
	{/if}
	<main>{@render children()}</main>
{/if}

<style>
	header {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 16px;
		border-bottom: 1px solid var(--border);
		background: var(--surface);
	}
	.brand {
		font-weight: 700;
		text-decoration: none;
		margin-right: auto;
	}
	main {
		max-width: 1100px;
		margin: 0 auto;
	}
</style>

<script lang="ts">
	import '../app.css';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { loadSession, logout, session } from '#lib/session.svelte.ts';

	let { children } = $props();
	let loadError = $state('');

	const PUBLIC = ['/login', '/setup'];

	$effect(() => {
		if (!session.loaded) {
			loadSession().catch((e) => (loadError = `Can't reach the hub API: ${e.message}`));
			return;
		}
		const path = page.url.pathname;
		if (session.needsSetup && path !== '/setup') goto('/setup');
		else if (!session.needsSetup && !session.user && !PUBLIC.includes(path)) goto('/login');
	});

	async function signOut() {
		await logout();
		goto('/login');
	}
</script>

{#if loadError}
	<p class="auth error">{loadError}</p>
{:else if session.loaded}
	{#if session.user}
		<header>
			<a href="/" class="brand">Blueberry Home</a>
			<span class="muted">{session.user.display_name}</span>
			<button class="ghost" onclick={signOut}>Sign out</button>
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

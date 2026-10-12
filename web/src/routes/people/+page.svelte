<script lang="ts">
	import { api, type User } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';

	let users = $state<User[]>([]);
	let username = $state('');
	let displayName = $state('');
	let password = $state('');
	let isAdmin = $state(false);
	let error = $state('');
	let added = $state('');

	function load() {
		api<User[]>('/users')
			.then((u) => (users = u))
			.catch((e) => (error = e.message));
	}

	$effect(() => {
		if (session.user?.is_admin) load();
	});

	async function add(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		try {
			const u = await api<User>('/users', {
				method: 'POST',
				json: { username, display_name: displayName || username, password, is_admin: isAdmin }
			});
			added = `${u.display_name} can now sign in as "${u.username}".`;
			username = displayName = password = '';
			isAdmin = false;
			load();
		} catch (err) {
			error = (err as Error).message;
		}
	}
</script>

<section>
	<h1>People</h1>
	{#if !session.user?.is_admin}
		<p class="muted">Only the hub's admin can add people.</p>
	{:else}
		<p class="muted">Everyone gets their own login, progress, poker history and private files.</p>
		<ul class="card list">
			{#each users as u (u.id)}
				<li><strong>{u.display_name}</strong> <span class="muted">@{u.username}{u.is_admin ? ' · admin' : ''}</span></li>
			{/each}
		</ul>

		<h2>Add someone</h2>
		<form class="card" onsubmit={add}>
			<label>Username <input bind:value={username} required autocapitalize="off" autocomplete="off" /></label>
			<label>Name <input bind:value={displayName} placeholder="Shown in the app" /></label>
			<label>Password <input type="password" bind:value={password} required minlength="10" autocomplete="new-password" /></label>
			<label class="check"><input type="checkbox" bind:checked={isAdmin} /> Admin (can add people)</label>
			<button>Add</button>
		</form>
		{#if added}<p>{added}</p>{/if}
	{/if}
	{#if error}<p class="error">{error}</p>{/if}
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 520px;
		margin: 0 auto;
		display: grid;
		gap: 0.75rem;
	}
	h1,
	h2,
	p {
		margin: 0;
	}
	.list {
		list-style: none;
		display: grid;
		gap: 0.4rem;
	}
	form {
		display: grid;
		gap: 0.75rem;
	}
	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.9rem;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.check input {
		width: auto;
	}
</style>

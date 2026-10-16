<script lang="ts">
	import { api, type User } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';

	let users = $state<User[]>([]);
	let error = $state('');

	$effect(() => {
		if (session.user) {
			api<User[]>('/users')
				.then((u) => (users = u))
				.catch((e) => (error = e.message));
		}
	});
</script>

<section>
	<h1>People</h1>
	<p class="muted">
		Everyone on your home Wi-Fi gets their own name, progress, poker history and private files the
		first time they open the hub. To add someone, just have them open it.
	</p>
	<ul class="card list">
		{#each users as u (u.id)}
			<li>
				<strong>{u.display_name}</strong>
				<span class="muted">
					@{u.username}{u.device ? ` · ${u.device}` : ''}{u.is_owner ? ' · owner' : u.is_admin ? ' · admin' : ''}{u.id === session.user?.id ? ' · you' : ''}
				</span>
			</li>
		{/each}
	</ul>
	<a href="/me">Change your name</a>
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
	p {
		margin: 0;
	}
	.list {
		list-style: none;
		display: grid;
		gap: 0.4rem;
	}
</style>

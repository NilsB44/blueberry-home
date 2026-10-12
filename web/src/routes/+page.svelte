<script lang="ts">
	import { api, type ModuleInfo } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';

	let modules = $state<ModuleInfo[]>([]);
	let error = $state('');

	$effect(() => {
		if (session.user) {
			api<ModuleInfo[]>('/modules')
				.then((m) => (modules = m))
				.catch((e) => (error = e.message));
		}
	});
</script>

<section>
	<h1>Hi {session.user?.display_name ?? ''}</h1>
	{#if error}<p class="error">{error}</p>{/if}
	<div class="grid">
		{#each modules as m (m.id)}
			{#if m.status === 'ready'}
				<a class="card tile" href={m.path}>
					<span class="icon">{m.icon}</span>
					<strong>{m.name}</strong>
					<span class="muted">{m.description}</span>
				</a>
			{:else}
				<div class="card tile planned" aria-disabled="true">
					<span class="icon">{m.icon}</span>
					<strong>{m.name}</strong>
					<span class="muted">{m.description}</span>
					<span class="badge">Phase {m.phase}</span>
				</div>
			{/if}
		{/each}
	</div>
</section>

<style>
	section {
		padding: 1.5rem 16px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 1rem;
	}
	.tile {
		display: grid;
		gap: 0.35rem;
		text-decoration: none;
		position: relative;
		transition: border-color 0.15s;
	}
	a.tile:hover {
		border-color: var(--accent);
	}
	.planned {
		opacity: 0.55;
	}
	.icon {
		font-size: 1.75rem;
	}
	.badge {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		font-size: 0.75rem;
		color: var(--muted);
	}
</style>

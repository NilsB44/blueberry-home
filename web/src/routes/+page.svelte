<script lang="ts">
	import { api, type ModuleInfo } from '#lib/api.ts';
	import type { Overview } from '#lib/network.ts';
	import { STATUS_LABEL, type Schedule } from '#lib/security.ts';
	import { session } from '#lib/session.svelte.ts';

	let modules = $state<ModuleInfo[]>([]);
	let error = $state('');
	let security = $state<Schedule | null>(null);
	let newDevices = $state(0);

	$effect(() => {
		if (session.user) {
			api<ModuleInfo[]>('/modules')
				.then((m) => (modules = m))
				.catch((e) => (error = e.message));
		}
		if (session.user?.is_admin) {
			api<Schedule>('/security/schedule')
				.then((s) => (security = s))
				.catch(() => {});
			api<Overview>('/network/overview')
				.then((o) => (newDevices = o.scan.new_devices ?? 0))
				.catch(() => {});
		}
	});

	const alert = $derived.by(() => {
		const latest = security?.latest;
		if (!latest || (latest.status !== 'fail' && latest.status !== 'warn')) return null;
		const n = latest.checks.filter((c) => c.status !== 'ok').length;
		return { status: latest.status, n };
	});
</script>

<section>
	<h1>Hi {session.user?.display_name ?? ''}</h1>
	{#if error}<p class="error">{error}</p>{/if}
	{#if alert}
		<a class="card alert {alert.status}" href="/security">
			🔒 {STATUS_LABEL[alert.status]}: the security check flagged {alert.n}
			{alert.n === 1 ? 'thing' : 'things'}.
		</a>
	{/if}
	{#if newDevices}
		<a class="card alert warn" href="/network">
			📶 {newDevices} new device{newDevices === 1 ? '' : 's'} joined the Wi-Fi. Check you recognise
			{newDevices === 1 ? 'it' : 'them'}.
		</a>
	{/if}
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
	.alert {
		display: block;
		margin-bottom: 1rem;
		text-decoration: none;
		padding: 0.75rem 1rem;
	}
	.alert.warn {
		background: var(--near-bg);
		color: var(--near);
		border-color: transparent;
	}
	.alert.fail {
		background: var(--bad-bg);
		color: var(--danger);
		border-color: transparent;
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

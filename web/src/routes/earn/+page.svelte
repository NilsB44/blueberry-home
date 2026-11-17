<script lang="ts">
	import { api } from '#lib/api.ts';
	import { bytes } from '#lib/network.ts';
	import { when } from '#lib/security.ts';
	import { session } from '#lib/session.svelte.ts';

	type App = {
		installed: boolean;
		running: boolean;
		state: string;
		problem: string;
		today_bytes: number | null;
		total_bytes: number | null;
		counted_since: string | null;
		log: string[];
	};
	type Status = { generated_at: string | null; stale: boolean; apps: Record<string, App>; error: string };

	const APPS = [
		{ id: 'earnapp', name: 'EarnApp', dashboard: 'https://earnapp.com/dashboard' },
		{ id: 'pawns', name: 'Pawns.app', dashboard: 'https://dashboard.pawns.app' }
	];
	const README = 'https://github.com/NilsB44/blueberry-home/blob/main/bandwidth-sharing/README.md';

	let status = $state<Status | null>(null);
	let error = $state('');

	async function load() {
		try {
			status = await api<Status>('/earn');
		} catch (e) {
			error = (e as Error).message;
		}
	}

	$effect(() => {
		if (!session.user?.is_owner) return;
		load();
		// The Pi reports every 5 minutes.
		const timer = setInterval(load, 60_000);
		return () => clearInterval(timer);
	});

	function pill(app: App | undefined): [string, string] {
		if (!app?.installed) return ['', 'Not installed'];
		if (app.problem) return ['warn', 'Not working'];
		return app.running ? ['ok', 'Running'] : ['fail', 'Stopped'];
	}
</script>

<section>
	<h1>Earn apps</h1>
	{#if !session.user?.is_owner}
		<p class="muted">Only the hub's owner can see this page.</p>
	{:else}
		{#if error}<p class="error">{error}</p>{/if}
		{#if status?.error}<p class="error">{status.error}</p>{/if}
		{#if status && !status.generated_at}
			<div class="card stack">
				<h2>Not set up yet</h2>
				<p>
					Make the EarnApp and Pawns.app accounts first, then run the setup on the Pi. It installs both
					apps and the 5-minute status report this page reads.
				</p>
				<code>~/hub/bandwidth-sharing/setup.sh</code>
				<a href={README} target="_blank" rel="noopener noreferrer">Setup guide</a>
			</div>
		{:else if status}
			<p class="muted small">
				Updated {when(status.generated_at!)}. The Pi checks every 5 minutes, so this can be a few
				minutes behind.
				{#if status.stale}
					<span class="warn">That's over 20 minutes ago: is the Pi's status timer running?
						(<code>systemctl status hub-earn-status.timer</code>)</span>
				{/if}
			</p>
		{/if}

		{#if status?.generated_at}
			{#each APPS as a (a.id)}
				{@const app = status.apps[a.id]}
				{@const [cls, label] = pill(app)}
				<div class="card stack">
					<div class="row">
						<h2>{a.name}</h2>
						<span class="pill {cls}">{label}</span>
					</div>
					{#if app?.problem}
						<p class="warn">
							{app.problem}
							<a href={`${README}#when-somethings-off`} target="_blank" rel="noopener noreferrer">What to do</a>
						</p>
					{/if}
					{#if app?.installed}
						{#if app.total_bytes !== null && app.counted_since}
							<div class="stats">
								<div><span class="muted small">Traffic today</span><strong>{bytes(app.today_bytes ?? 0)}</strong></div>
								<div><span class="muted small">Total</span><strong>{bytes(app.total_bytes)}</strong></div>
							</div>
							<p class="muted small">Up and down together, counted on the Pi since {app.counted_since}.</p>
						{:else}
							<p class="muted small">No traffic counted yet.</p>
						{/if}
						{#if !app.running}<p class="muted small">State: {app.state}</p>{/if}
						<details>
							<summary class="muted">Latest log lines</summary>
							{#if app.log.length}
								<pre>{app.log.join('\n')}</pre>
							{:else}
								<p class="muted small">Nothing logged.</p>
							{/if}
						</details>
					{:else}
						<p class="muted small">Not on the Pi yet: run <code>~/hub/bandwidth-sharing/setup.sh</code>.</p>
					{/if}
					<a href={a.dashboard} target="_blank" rel="noopener noreferrer">Earnings and requests on the {a.name} dashboard</a>
				</div>
			{/each}
		{/if}
		<p class="muted small">
			Earnings and how many requests each app handled are only on the apps' own dashboards: they
			don't share them with the Pi, so the hub can't show them here.
		</p>
	{/if}
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 720px;
		margin: 0 auto;
		display: grid;
		gap: 1rem;
	}
	h1,
	h2,
	p {
		margin: 0;
	}
	h2 {
		font-size: 1.15rem;
	}
	.stack {
		display: grid;
		gap: 0.6rem;
		justify-items: start;
	}
	.stack > * {
		max-width: 100%;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
	}
	.stats {
		display: flex;
		gap: 1.5rem;
	}
	.stats > div {
		display: grid;
	}
	.small {
		font-size: 0.85rem;
	}
	.warn {
		color: var(--near);
	}
	pre {
		margin: 0.4rem 0 0;
		font-size: 0.75rem;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
	.pill {
		font-size: 0.8rem;
		font-weight: 600;
		padding: 0.1rem 0.6rem;
		border-radius: 999px;
		background: var(--bg);
		border: 1px solid var(--border);
	}
	.pill.warn {
		color: var(--near);
		background: var(--near-bg);
		border-color: transparent;
	}
	.pill.ok {
		color: var(--good);
		background: var(--good-bg);
		border-color: transparent;
	}
	.pill.fail {
		color: var(--danger);
		background: var(--bad-bg);
		border-color: transparent;
	}
</style>

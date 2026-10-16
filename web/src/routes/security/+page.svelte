<script lang="ts">
	import { api } from '#lib/api.ts';
	import {
		STATUS_LABEL,
		when,
		type Attempt,
		type AwayAccess,
		type Check,
		type Report,
		type ReportSummary,
		type Schedule
	} from '#lib/security.ts';
	import { session } from '#lib/session.svelte.ts';

	let away = $state<AwayAccess | null>(null);
	let schedule = $state<Schedule | null>(null);
	let report = $state<Report | null>(null);
	let history = $state<ReportSummary[]>([]);
	let attempts = $state<Attempt[]>([]);
	let error = $state('');
	let busy = $state(false);
	let running = $state(false);

	const KIND_LABEL: Record<Attempt['kind'], string> = {
		blocked: 'Refused',
		login: 'Wrong password',
		away: 'Away visit'
	};

	async function load() {
		try {
			[away, schedule, history, attempts] = await Promise.all([
				api<AwayAccess>('/security/away'),
				api<Schedule>('/security/schedule'),
				api<ReportSummary[]>('/security/reports'),
				api<Attempt[]>('/security/attempts')
			]);
			report = schedule.latest;
		} catch (e) {
			error = (e as Error).message;
		}
	}

	$effect(() => {
		if (session.user?.is_admin) load();
	});

	async function setAway(enabled: boolean) {
		busy = true;
		error = '';
		try {
			away = await api<AwayAccess>('/security/away', { method: 'PUT', json: { enabled } });
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function runNow() {
		running = true;
		error = '';
		try {
			report = await api<Report>('/security/reports', { method: 'POST' });
			history = await api<ReportSummary[]>('/security/reports');
		} catch (e) {
			error = (e as Error).message;
		} finally {
			running = false;
		}
	}

	async function show(id: number) {
		try {
			report = await api<Report>(`/security/reports/${id}`);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const groups = $derived.by(() => {
		const checks = report?.checks ?? [];
		return [
			{ name: 'The hub', checks: checks.filter((c: Check) => c.group === 'hub') },
			{ name: 'The Pi', checks: checks.filter((c: Check) => c.group === 'pi') }
		];
	});
</script>

<section>
	<h1>Security</h1>
	{#if !session.user?.is_admin}
		<p class="muted">Only admins can see this page.</p>
	{:else}
		{#if error}<p class="error">{error}</p>{/if}

		{#if away}
			<div class="card stack">
				<div class="row">
					<h2>Away access</h2>
					<span class="pill" class:on={away.enabled}>{away.enabled ? 'On' : 'Off'}</span>
				</div>
				{#if away.enabled}
					<p>
						Your own devices on your Tailscale VPN can reach the hub from anywhere, but only ones that
						already joined here on the Wi-Fi. New devices can't join from outside.
					</p>
					{#if away.changed_at}
						<p class="muted">Turned on {when(away.changed_at)}{away.changed_by ? ` by ${away.changed_by}` : ''}.</p>
					{/if}
					<button class="ghost" disabled={busy} onclick={() => setAway(false)}>Turn off</button>
				{:else}
					<p>
						Only devices on your home Wi-Fi can reach the hub. Turn this on before a trip to check on
						things through Tailscale. Nothing is opened on your router either way.
					</p>
					{#if away.can_enable}
						<button disabled={busy} onclick={() => setAway(true)}>Turn on</button>
					{:else}
						<p class="muted">You can only turn this on at home.</p>
					{/if}
				{/if}
			</div>
		{/if}

		<div class="card stack">
			<div class="row">
				<h2>Weekly check</h2>
				{#if report}<span class="pill {report.status}">{STATUS_LABEL[report.status]}</span>{/if}
			</div>
			{#if report}
				<p class="muted">
					{report.trigger === 'manual' ? 'Run by hand' : 'Ran'}
					{when(report.started_at)}.
					{#if schedule}Next one {when(schedule.next_run_at)}.{/if}
				</p>
				{#each groups as g (g.name)}
					{#if g.checks.length}
						<h3>{g.name}</h3>
						<ul class="checks">
							{#each g.checks as c (c.id)}
								<li>
									<span class="dot {c.status}" title={STATUS_LABEL[c.status]}></span>
									<div>
										<strong>{c.title}</strong>
										<p>{c.summary}</p>
										{#if c.details.length}
											<details>
												<summary class="muted">Details</summary>
												<ul class="muted">
													{#each c.details as d, i (i)}<li>{d}</li>{/each}
												</ul>
											</details>
										{/if}
									</div>
								</li>
							{/each}
						</ul>
					{/if}
				{/each}
			{:else}
				<p class="muted">No check has run yet.</p>
			{/if}
			<p class="muted small">
				The Pi's own part refreshes every Sunday night. Running the check now re-reads its latest
				report.
			</p>
			<button disabled={running} onclick={runNow}>{running ? 'Checking…' : 'Run the check now'}</button>
		</div>

		<div class="card stack">
			<h2>Who knocked</h2>
			{#if attempts.length}
				<div class="table">
					<table>
						<thead><tr><th>Last seen</th><th>What</th><th>From</th><th>Times</th></tr></thead>
						<tbody>
							{#each attempts as a (`${a.kind}${a.ip}${a.day}`)}
								<tr class:internet={a.from_internet}>
									<td>{when(a.last_seen)}</td>
									<td>{KIND_LABEL[a.kind]}{a.kind === 'login' ? ` as @${a.detail}` : ''}</td>
									<td>{a.ip}{a.from_internet ? ' (internet)' : ''}</td>
									<td>{a.count}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<p class="muted">Nobody was refused, and no wrong passwords, in the last 30 days.</p>
			{/if}
		</div>

		{#if history.length > 1}
			<div class="card stack">
				<h2>Earlier checks</h2>
				<ul class="history">
					{#each history as h (h.id)}
						<li>
							<button class="link" onclick={() => show(h.id)}>
								<span class="dot {h.status}"></span>
								{when(h.started_at)}
								<span class="muted">· {STATUS_LABEL[h.status]}{h.trigger === 'manual' ? ' · by hand' : ''}</span>
							</button>
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<p class="muted small">
			How this is set up, and what to do if something shows red: <code>docs/security.md</code> in the
			hub's code.
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
	h3,
	p {
		margin: 0;
	}
	h2 {
		font-size: 1.15rem;
	}
	h3 {
		font-size: 0.95rem;
		margin-top: 0.5rem;
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
	.small {
		font-size: 0.85rem;
	}
	.pill {
		font-size: 0.8rem;
		font-weight: 600;
		padding: 0.1rem 0.6rem;
		border-radius: 999px;
		background: var(--bg);
		border: 1px solid var(--border);
	}
	.pill.on,
	.pill.ok {
		color: var(--good);
		background: var(--good-bg);
		border-color: transparent;
	}
	.pill.warn,
	.pill.unknown {
		color: var(--near);
		background: var(--near-bg);
		border-color: transparent;
	}
	.pill.fail {
		color: var(--danger);
		background: var(--bad-bg);
		border-color: transparent;
	}
	.checks {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.75rem;
		width: 100%;
	}
	.checks > li {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.6rem;
		align-items: start;
	}
	.checks p {
		overflow-wrap: anywhere;
	}
	.checks details ul {
		margin: 0.25rem 0 0;
		padding-left: 1.1rem;
		font-size: 0.9rem;
		overflow-wrap: anywhere;
	}
	.dot {
		display: inline-block;
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 50%;
		margin-top: 0.45rem;
		background: var(--muted);
	}
	.dot.ok {
		background: var(--good);
	}
	.dot.warn,
	.dot.unknown {
		background: var(--near);
	}
	.dot.fail {
		background: var(--danger);
	}
	.table {
		width: 100%;
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	th,
	td {
		text-align: left;
		padding: 0.35rem 0.5rem 0.35rem 0;
		border-bottom: 1px solid var(--border);
		white-space: nowrap;
	}
	tr.internet td {
		color: var(--danger);
	}
	.history {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.25rem;
	}
	button.link {
		background: none;
		color: var(--text);
		padding: 0.2rem 0;
		font-weight: 400;
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	button.link .dot {
		margin-top: 0;
	}
</style>

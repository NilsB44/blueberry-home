<script lang="ts">
	import { api } from '#lib/api.ts';
	import { when } from '#lib/security.ts';
	import { session } from '#lib/session.svelte.ts';
	import { num, type Alert, type Level, type TradingSettings, type TradingStatus } from '#lib/trading.ts';

	let status = $state<TradingStatus | null>(null);
	let settings = $state<TradingSettings | null>(null);
	let levels = $state<Level[]>([]);
	let alerts = $state<Alert[]>([]);
	let error = $state('');
	let busy = $state(false);

	let form = $state({
		instrument: '',
		entry_low: '',
		entry_high: '',
		stop_points: ''
	});

	async function load() {
		try {
			[status, settings, levels, alerts] = await Promise.all([
				api<TradingStatus>('/trading/status'),
				api<TradingSettings>('/trading/settings'),
				api<Level[]>('/trading/levels'),
				api<Alert[]>('/trading/alerts')
			]);
			if (!form.instrument && settings.instruments.length) form.instrument = settings.instruments[0].name;
		} catch (e) {
			error = (e as Error).message;
		}
	}

	$effect(() => {
		if (!session.user?.is_owner) return;
		load();
		// Keep prices and alerts fresh while the page is open.
		const timer = setInterval(load, 30_000);
		return () => clearInterval(timer);
	});

	async function act(fn: () => Promise<unknown>) {
		busy = true;
		error = '';
		try {
			await fn();
			await load();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	const checkNow = () => act(() => api('/trading/check', { method: 'POST' }));

	function addLevel(e: SubmitEvent) {
		e.preventDefault();
		act(async () => {
			await api('/trading/levels', {
				method: 'POST',
				json: {
					instrument: form.instrument,
					entry_low: Number(form.entry_low),
					entry_high: form.entry_high === '' ? null : Number(form.entry_high),
					stop_points: Number(form.stop_points) || 0
				}
			});
			form = { ...form, entry_low: '', entry_high: '', stop_points: '' };
		});
	}

	const setActive = (l: Level, active: boolean) =>
		act(() => api(`/trading/levels/${l.id}`, { method: 'PATCH', json: { active } }));

	function remove(l: Level) {
		if (confirm(`Delete the ${l.instrument} ${zone(l)} level?`)) act(() => api(`/trading/levels/${l.id}`, { method: 'DELETE' }));
	}

	const zone = (l: Level) => (l.entry_low === l.entry_high ? num(l.entry_low) : `${num(l.entry_low)}–${num(l.entry_high)}`);
</script>

<section>
	<div class="row">
		<h1>Trading</h1>
		<a href="/trading/settings" class="settings">Settings</a>
	</div>
	{#if !session.user?.is_owner}
		<p class="muted">Only the hub's owner can see this page.</p>
	{:else}
		{#if error}<p class="error">{error}</p>{/if}

		{#if status}
			<div class="card stack">
				<div class="row">
					<h2>Prices</h2>
					<span class="pill" class:on={status.enabled}>{status.enabled ? 'Watching' : 'Paused'}</span>
					{#if status.ig_demo}<span class="pill">IG demo</span>{/if}
				</div>
				{#if !status.ig_configured}
					<p class="muted">Add your IG API key, username and password to the Pi's .env to see prices.</p>
				{/if}
				{#if status.prices.length}
					<div class="table">
						<table>
							<thead><tr><th>Market</th><th>Bid</th><th>Offer</th><th></th></tr></thead>
							<tbody>
								{#each status.prices as p (p.name)}
									<tr>
										<td>{p.name}</td>
										<td>{num(p.bid)}</td>
										<td>{num(p.offer)}</td>
										<td class="muted">{p.status === 'TRADEABLE' ? 'Open' : 'Closed'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
				{#if status.price_error}<p class="error">{status.price_error}</p>{/if}
				{#if status.feed_error}<p class="error">{status.feed_error}</p>{/if}
				<div class="row wrap">
					<button class="ghost" disabled={busy} onclick={checkNow}>Check now</button>
					{#if status.price_checked_at}<span class="muted small">Checked {when(status.price_checked_at)}</span>{/if}
				</div>
			</div>
		{/if}

		{#if settings}
			<form class="card stack" onsubmit={addLevel}>
				<h2>Add a level</h2>
				<div class="grid">
					<label>
						Market
						<select bind:value={form.instrument} required>
							{#each settings.instruments as i (i.name)}<option value={i.name}>{i.name}</option>{/each}
						</select>
					</label>
					<label>Lower level <input type="number" step="any" inputmode="decimal" bind:value={form.entry_low} required /></label>
					<label>Upper level <input type="number" step="any" inputmode="decimal" bind:value={form.entry_high} required /></label>
					<label>
						Stop, points beyond
						<input type="number" min="0" step="any" inputmode="decimal" bind:value={form.stop_points} placeholder="optional" />
					</label>
				</div>
				<p class="muted small">
					Long or short is decided when the price gets there: coming up from below is a short, coming down from above is a
					long. Levels stay until you delete them. With a stop, alerts also show the position size.
				</p>
				<button disabled={busy}>Add</button>
			</form>
		{/if}

		<div class="card stack">
			<h2>Levels</h2>
			{#if levels.length}
				<ul class="list">
					{#each levels as l (l.id)}
						<li class:paused={!l.active}>
							<div>
								<strong>{l.instrument}</strong>
								{zone(l)}{l.stop_points ? `, stop ${num(l.stop_points)} pts beyond` : ''}
								{#if l.targets}<span class="muted">· targets {l.targets}</span>{/if}
								<div class="muted small">
									{#if l.distance != null}{l.distance === 0 ? 'Price is in the zone' : `${num(l.distance)} pts away`} ·{/if}
									{#if l.bias}now {l.bias}{l.stop ? `, stop ${num(l.stop)}` : ''}{l.contracts ? `, ${num(l.contracts)} contracts` : ''} ·{/if}
									{#if l.valid_until}until {l.valid_until} ·{/if}
									{#if l.last_alert_at}alerted {when(l.last_alert_at)}{:else}no alert yet{/if}
								</div>
								{#if l.note}<div class="muted small">{l.note}</div>{/if}
							</div>
							<div class="actions">
								<button class="ghost" disabled={busy} onclick={() => setActive(l, !l.active)}>{l.active ? 'Pause' : 'Resume'}</button>
								<button class="ghost" disabled={busy} onclick={() => remove(l)}>Delete</button>
							</div>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="muted">No levels yet. Add the ones from this week's analysis above.</p>
			{/if}
		</div>

		<div class="card stack">
			<h2>Alerts</h2>
			{#if alerts.length}
				<ul class="list">
					{#each alerts as a (a.id)}
						<li>
							<div>
								<strong>{a.title}</strong>
								<span class="muted small">{when(a.at)}{a.delivered ? '' : ' · not pushed'}</span>
								<p class="message">{a.message}</p>
								{#if a.link}<a href={a.link} target="_blank" rel="noopener noreferrer" class="small">Open</a>{/if}
								{#if a.error}<div class="muted small">{a.error}</div>{/if}
							</div>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="muted">No alerts yet.</p>
			{/if}
		</div>
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
	.wrap {
		flex-wrap: wrap;
	}
	.settings {
		margin-left: auto;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 0.6rem;
		width: 100%;
	}
	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.9rem;
	}
	select {
		font: inherit;
		color: inherit;
		padding: 0.6rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--surface);
	}
	.list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.75rem;
		width: 100%;
	}
	.list > li {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.4rem 0.75rem;
		overflow-wrap: anywhere;
	}
	.paused {
		opacity: 0.55;
	}
	.actions {
		flex-shrink: 0;
		display: flex;
		gap: 0.4rem;
		align-items: start;
	}
	.message {
		white-space: pre-line;
		font-size: 0.9rem;
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
	.pill.on {
		color: var(--good);
		background: var(--good-bg);
		border-color: transparent;
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
</style>

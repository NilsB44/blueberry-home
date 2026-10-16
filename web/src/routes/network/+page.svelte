<script lang="ts">
	import { api } from '#lib/api.ts';
	import {
		bytes,
		deviceName,
		duration,
		percent,
		type Device,
		type History,
		type Overview,
		type SpeedTest
	} from '#lib/network.ts';
	import { when } from '#lib/security.ts';
	import { session } from '#lib/session.svelte.ts';

	const STRIP_HOURS = 48;

	let overview = $state<Overview | null>(null);
	let history = $state<History | null>(null);
	let devices = $state<Device[]>([]);
	let error = $state('');
	let testing = $state(false);
	let editing = $state<string | null>(null);
	let draft = $state('');
	let showOffline = $state(false);

	const admin = $derived(session.user?.is_admin ?? false);

	async function load() {
		try {
			[overview, history] = await Promise.all([
				api<Overview>('/network/overview'),
				api<History>(`/network/history?days=7`)
			]);
			if (admin) devices = await api<Device[]>('/network/devices');
		} catch (e) {
			error = (e as Error).message;
		}
	}

	$effect(() => {
		if (!session.user) return;
		load();
		const timer = setInterval(load, 60_000);
		return () => clearInterval(timer);
	});

	async function speedtest() {
		testing = true;
		error = '';
		try {
			await api<SpeedTest>('/network/speedtest', { method: 'POST' });
			await load();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			testing = false;
		}
	}

	async function change(d: Device, body: { name?: string; known?: boolean }) {
		error = '';
		try {
			const updated = await api<Device>(`/network/devices/${d.mac}`, { method: 'PATCH', json: body });
			devices = devices.map((x) => (x.mac === d.mac ? updated : x));
			if (overview?.scan.new_devices != null) {
				overview.scan.new_devices = devices.filter((x) => !x.known).length;
			}
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function acknowledgeAll() {
		try {
			await api('/network/devices/acknowledge', { method: 'POST' });
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function forget(d: Device) {
		if (!confirm(`Forget ${deviceName(d)}? If it comes back it shows as new.`)) return;
		try {
			await api(`/network/devices/${d.mac}`, { method: 'DELETE' });
			devices = devices.filter((x) => x.mac !== d.mac);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function startRename(d: Device) {
		editing = d.mac;
		draft = d.name || d.hostname;
	}

	async function saveRename(d: Device) {
		await change(d, { name: draft });
		editing = null;
	}

	/** One slot per hour for the last two days, oldest first; null where there's no data. */
	const strip = $derived.by(() => {
		const byHour = new Map(
			(history?.hours ?? []).map((h) => [new Date(/[zZ]|[+-]\d\d:\d\d$/.test(h.hour) ? h.hour : `${h.hour}Z`).getTime(), h])
		);
		const now = new Date();
		now.setMinutes(0, 0, 0);
		return Array.from({ length: STRIP_HOURS }, (_, i) => {
			const t = now.getTime() - (STRIP_HOURS - 1 - i) * 3_600_000;
			return { t, h: byHour.get(t) ?? null };
		});
	});

	function slotClass(uptime: number | null | undefined): string {
		if (uptime == null) return 'none';
		if (uptime >= 0.999) return 'ok';
		if (uptime >= 0.95) return 'warn';
		return 'fail';
	}

	function slotTitle(t: number, h: History['hours'][number] | null): string {
		const label = new Date(t).toLocaleString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' });
		if (!h) return `${label}: not checked`;
		const latency = h.latency_ms != null ? `, ${h.latency_ms.toFixed(0)} ms` : '';
		return `${label}: ${percent(h.uptime)} up${latency}`;
	}

	const online = $derived(devices.filter((d) => d.online || !d.known));
	const offline = $derived(devices.filter((d) => !d.online && d.known));
	const memoryUsed = $derived.by(() => {
		const h = overview?.health;
		if (!h?.memory_total_bytes || h.memory_available_bytes == null) return null;
		return 1 - h.memory_available_bytes / h.memory_total_bytes;
	});
</script>

{#snippet deviceRow(d: Device)}
	<li class:new={!d.known}>
		<span class="dot" class:ok={d.online} title={d.online ? 'Online' : `Last seen ${when(d.last_seen)}`}></span>
		<div class="device">
			{#if editing === d.mac}
				<form class="rename" onsubmit={(e) => (e.preventDefault(), saveRename(d))}>
					<input bind:value={draft} maxlength="64" aria-label="Name" />
					<button>Save</button>
					<button type="button" class="ghost" onclick={() => (editing = null)}>Cancel</button>
				</form>
			{:else}
				<span class="name">
					<strong>{deviceName(d)}</strong>
					{#if !d.known}<span class="pill warn">New</span>{/if}
				</span>
			{/if}
			<p class="muted small">
				{d.ip} · <code>{d.mac}</code>{d.private_mac ? ' · private address' : ''}
				{#if d.name && d.hostname} · calls itself {d.hostname}{/if}
			</p>
			<p class="muted small">
				{d.online ? 'Online now' : `Last seen ${when(d.last_seen)}`} · first seen {when(d.first_seen)}
			</p>
			{#if editing !== d.mac}
				<div class="actions">
					{#if !d.known}
						<button class="small-btn" onclick={() => change(d, { known: true })}>I know this one</button>
					{/if}
					<button class="ghost small-btn" onclick={() => startRename(d)}>Rename</button>
					{#if !d.is_pi}
						<button class="ghost small-btn" onclick={() => forget(d)}>Forget</button>
					{/if}
				</div>
			{/if}
		</div>
	</li>
{/snippet}

<section>
	<h1>Network</h1>
	{#if error}<p class="error">{error}</p>{/if}

	{#if overview}
		{@const net = overview.internet}
		<div class="card stack">
			<div class="row">
				<h2>Internet</h2>
				{#if net.up === null}
					<span class="pill">Checking…</span>
				{:else if net.up}
					<span class="pill ok">Online</span>
				{:else}
					<span class="pill fail">Down</span>
				{/if}
			</div>
			{#if net.up === false && net.down_since}
				<p>The connection has been down since {when(net.down_since)}. The hub keeps working on the Wi-Fi.</p>
			{/if}
			<div class="stats">
				<div><span class="big">{net.latency_ms != null ? `${net.latency_ms.toFixed(0)} ms` : '–'}</span><span class="muted">Response time</span></div>
				<div><span class="big">{percent(net.uptime_24h)}</span><span class="muted">Up, last 24 h</span></div>
				<div><span class="big">{percent(net.uptime_7d)}</span><span class="muted">Up, last 7 days</span></div>
				<div><span class="big">{net.outages_7d}</span><span class="muted">Outage{net.outages_7d === 1 ? '' : 's'} this week</span></div>
			</div>
			<div class="strip" aria-label="Uptime per hour, last 48 hours">
				{#each strip as s (s.t)}
					<span class="slot {slotClass(s.h?.uptime)}" title={slotTitle(s.t, s.h)}></span>
				{/each}
			</div>
			<p class="muted small">Last 48 hours, one bar per hour. Checked once a minute.</p>
			{#if history?.outages.length}
				<details>
					<summary class="muted">Outages</summary>
					<ul class="muted small">
						{#each history.outages as o (o.started_at)}
							<li>{when(o.started_at)}: {o.ended_at ? `${o.minutes.toFixed(0)} min` : 'still down'}</li>
						{/each}
					</ul>
				</details>
			{/if}
		</div>

		<div class="card stack">
			<div class="row">
				<h2>Speed</h2>
				{#if overview.speed}<span class="muted small">{when(overview.speed.at)}</span>{/if}
			</div>
			{#if overview.speed?.error}
				<p class="error">{overview.speed.error}</p>
			{:else if overview.speed}
				<div class="stats">
					<div><span class="big">{overview.speed.down_mbps?.toFixed(0)}</span><span class="muted">Mbit/s down</span></div>
					<div><span class="big">{overview.speed.up_mbps?.toFixed(0)}</span><span class="muted">Mbit/s up</span></div>
					<div><span class="big">{overview.speed.ping_ms?.toFixed(0)} ms</span><span class="muted">Ping</span></div>
				</div>
			{:else}
				<p class="muted">No speed test yet. One runs every few hours.</p>
			{/if}
			{#if history && history.speedtests.length > 1}
				<details>
					<summary class="muted">This week</summary>
					<div class="table">
						<table>
							<thead><tr><th>When</th><th>Down</th><th>Up</th><th>Ping</th></tr></thead>
							<tbody>
								{#each history.speedtests as t (t.at)}
									<tr>
										<td>{when(t.at)}</td>
										{#if t.error}
											<td colspan="3" class="muted">failed</td>
										{:else}
											<td>{t.down_mbps?.toFixed(0)}</td>
											<td>{t.up_mbps?.toFixed(0)}</td>
											<td>{t.ping_ms?.toFixed(0)} ms</td>
										{/if}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</details>
			{/if}
			{#if admin}
				<button disabled={testing} onclick={speedtest}>{testing ? 'Testing… (about 20 s)' : 'Test now'}</button>
			{/if}
			<p class="muted small">
				Measured from the Pi, so a Wi-Fi phone may see less. Each test uses about 35 MB.
			</p>
		</div>

		{@const h = overview.health}
		<div class="card stack">
			<div class="row">
				<h2>The Pi</h2>
				<span class="pill {h.status}">{h.status === 'ok' ? 'Healthy' : h.status === 'warn' ? 'Worth a look' : 'Needs attention'}</span>
			</div>
			{#each h.notes as note (note)}<p>{note}</p>{/each}
			<div class="stats">
				<div><span class="big">{h.temperature_c != null ? `${h.temperature_c.toFixed(0)} °C` : '–'}</span><span class="muted">CPU temperature</span></div>
				<div>
					<span class="big">{h.load ? `${Math.round((h.load[0] / h.cpus) * 100)}%` : '–'}</span>
					<span class="muted">CPU busy</span>
				</div>
				<div><span class="big">{h.uptime_seconds != null ? duration(h.uptime_seconds) : '–'}</span><span class="muted">Since restart</span></div>
			</div>
			{#if memoryUsed !== null && h.memory_total_bytes}
				<div class="meter-row">
					<span>Memory</span>
					<meter min="0" max="1" low="0.75" high="0.9" optimum="0" value={memoryUsed}></meter>
					<span class="muted small">{bytes(h.memory_total_bytes - (h.memory_available_bytes ?? 0))} of {bytes(h.memory_total_bytes)}</span>
				</div>
			{/if}
			{#each h.disks as d (d.label)}
				<div class="meter-row">
					<span>{d.label}</span>
					<meter min="0" max="1" low="0.75" high="0.9" optimum="0" value={1 - d.free_bytes / d.total_bytes}></meter>
					<span class="muted small">{bytes(d.free_bytes)} free of {bytes(d.total_bytes)}</span>
				</div>
			{/each}
			{#if h.throttled_since_boot.length && !h.throttled_now.length}
				<p class="muted small">Since it started: {h.throttled_since_boot.join(', ')}.</p>
			{/if}
		</div>

		<div class="card stack">
			<div class="row">
				<h2>On the Wi-Fi</h2>
				{#if !overview.scan.stale}<span class="pill ok">{overview.scan.online} online</span>{/if}
			</div>
			{#if overview.scan.at === null}
				<p>
					The Pi hasn't listed the devices yet. It needs a small scan installed once on the Pi itself:
				</p>
				<pre><code>sudo scripts/install-network-scan.sh</code></pre>
				<p class="muted small">Run it in the hub's folder. It checks every 5 minutes. See docs/network.md.</p>
			{:else if overview.scan.stale}
				<p class="muted">The last scan was {when(overview.scan.at)}, so who's online is unknown. Is the scan timer running on the Pi?</p>
			{/if}

			{#if admin}
				{#if overview.scan.new_devices}
					<div class="alert">
						<p>
							<strong>{overview.scan.new_devices} new device{overview.scan.new_devices === 1 ? '' : 's'}</strong>
							joined the Wi-Fi. If you don't recognise one, change the Wi-Fi password on the router.
						</p>
						<button class="small-btn" onclick={acknowledgeAll}>I recognise them all</button>
					</div>
				{/if}
				{#if online.length}
					<ul class="devices">
						{#each online as d (d.mac)}{@render deviceRow(d)}{/each}
					</ul>
				{/if}
				{#if offline.length}
					<button class="link" onclick={() => (showOffline = !showOffline)}>
						{showOffline ? 'Hide' : 'Show'} {offline.length} offline device{offline.length === 1 ? '' : 's'}
					</button>
					{#if showOffline}
						<ul class="devices">
							{#each offline as d (d.mac)}{@render deviceRow(d)}{/each}
						</ul>
					{/if}
				{/if}
				{#if overview.scan.network}
					<p class="muted small">
						Network {overview.scan.network}, router {overview.scan.gateway}, last scan {when(overview.scan.at ?? '')}.
						Phones use a private address per network, so one phone can show up twice after a reset.
					</p>
				{/if}
			{:else if !overview.scan.stale}
				<p class="muted">Admins can see and name each device.</p>
			{/if}
		</div>

		{#if overview.refused_7d}
			<a class="card refused" href="/security">
				🔒 {overview.refused_7d} visit{overview.refused_7d === 1 ? ' was' : 's were'} refused this week. See who on the Security page.
			</a>
		{/if}
	{:else if !error}
		<p class="muted">Loading…</p>
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
		flex-wrap: wrap;
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
	.pill.ok {
		color: var(--good);
		background: var(--good-bg);
		border-color: transparent;
	}
	.pill.warn {
		color: var(--near);
		background: var(--near-bg);
		border-color: transparent;
	}
	.pill.fail {
		color: var(--danger);
		background: var(--bad-bg);
		border-color: transparent;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
		gap: 0.75rem;
		width: 100%;
	}
	.stats > div {
		display: grid;
	}
	.stats .muted {
		font-size: 0.85rem;
	}
	.big {
		font-size: 1.5rem;
		font-weight: 650;
		font-variant-numeric: tabular-nums;
	}
	.strip {
		display: grid;
		grid-template-columns: repeat(48, 1fr);
		gap: 2px;
		width: 100%;
		height: 1.6rem;
	}
	.slot {
		border-radius: 2px;
		background: var(--border);
	}
	.slot.ok {
		background: var(--good);
	}
	.slot.warn {
		background: var(--near);
	}
	.slot.fail {
		background: var(--danger);
	}
	.meter-row {
		display: grid;
		grid-template-columns: 7rem 1fr;
		gap: 0 0.75rem;
		align-items: center;
		width: 100%;
	}
	.meter-row meter {
		width: 100%;
		height: 0.9rem;
	}
	.meter-row .small {
		grid-column: 2;
	}
	pre {
		margin: 0;
		padding: 0.5rem 0.75rem;
		background: var(--bg);
		border-radius: 8px;
		overflow-x: auto;
		max-width: 100%;
	}
	.alert {
		display: grid;
		gap: 0.5rem;
		justify-items: start;
		padding: 0.75rem 1rem;
		border-radius: 8px;
		background: var(--near-bg);
		color: var(--near);
		width: 100%;
	}
	.devices {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.75rem;
		width: 100%;
	}
	.devices > li {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.6rem;
		align-items: start;
	}
	.devices > li.new strong {
		color: var(--near);
	}
	.device {
		display: grid;
		gap: 0.15rem;
		min-width: 0;
	}
	.device p {
		overflow-wrap: anywhere;
	}
	.name {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 0.25rem;
	}
	.small-btn {
		padding: 0.3rem 0.7rem;
		font-size: 0.85rem;
	}
	.rename {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}
	.rename input {
		flex: 1 1 12rem;
		padding: 0.35rem 0.6rem;
	}
	.rename button {
		padding: 0.35rem 0.8rem;
	}
	.dot {
		display: inline-block;
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 50%;
		margin-top: 0.45rem;
		background: var(--muted);
		opacity: 0.5;
	}
	.dot.ok {
		background: var(--good);
		opacity: 1;
	}
	button.link {
		background: none;
		color: var(--accent);
		padding: 0.2rem 0;
		font-weight: 500;
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
	details ul {
		margin: 0.25rem 0 0;
		padding-left: 1.1rem;
	}
	.refused {
		display: block;
		text-decoration: none;
		padding: 0.75rem 1rem;
	}
</style>

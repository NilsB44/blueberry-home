<script lang="ts">
	import { api } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';
	import { num, type Alert, type Market, type TradingSettings } from '#lib/trading.ts';

	let s = $state<TradingSettings | null>(null);
	let error = $state('');
	let notice = $state('');
	let busy = $state(false);
	// The instrument row being searched, its search words and what IG found.
	let searching = $state<number | null>(null);
	let term = $state('');
	let found = $state<Market[]>([]);

	// IG's names for the usual markets, as a starting point for the search.
	const IG_NAMES: Record<string, string> = {
		DAX: 'Germany 40',
		OMXS30: 'Sweden 30',
		'Nasdaq 100': 'US Tech 100',
		'S&P 500': 'US 500',
		Gold: 'Spot Gold'
	};

	$effect(() => {
		if (session.user?.is_owner)
			api<TradingSettings>('/trading/settings')
				.then((r) => (s = r))
				.catch((e) => (error = e.message));
	});

	async function run(fn: () => Promise<void>) {
		busy = true;
		error = '';
		notice = '';
		try {
			await fn();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	function save(e: SubmitEvent) {
		e.preventDefault();
		run(async () => {
			s = await api<TradingSettings>('/trading/settings', { method: 'PUT', json: s });
			notice = 'Saved.';
		});
	}

	const testAlert = () =>
		run(async () => {
			const a = await api<Alert>('/trading/test-alert', { method: 'POST' });
			notice = a.delivered ? 'Sent: check your phone.' : a.error;
		});

	function startSearch(i: number) {
		searching = i;
		found = [];
		term = IG_NAMES[s!.instruments[i].name] ?? s!.instruments[i].name;
		search();
	}

	const search = () =>
		run(async () => {
			found = await api<Market[]>(`/trading/markets?q=${encodeURIComponent(term)}`);
			if (!found.length) notice = 'IG found nothing by that name.';
		});

	function pick(m: Market) {
		if (s && searching !== null) s.instruments[searching].epic = m.epic;
		searching = null;
		found = [];
	}
</script>

<section>
	<div class="row">
		<h1>Trading settings</h1>
		<a href="/trading" class="back">Back</a>
	</div>
	{#if !session.user?.is_owner}
		<p class="muted">Only the hub's owner can see this page.</p>
	{:else if s}
		<form class="stack" onsubmit={save}>
			<div class="card stack">
				<h2>Watcher</h2>
				<label class="inline"><input type="checkbox" bind:checked={s.enabled} /> Watch prices and the feed</label>
				<div class="grid">
					<label>
						Check prices every (seconds)
						<input type="number" min="15" max="3600" bind:value={s.price_check_seconds} required />
					</label>
					<label>
						Alert within (points)
						<input type="number" min="0.1" step="any" bind:value={s.near_points} required />
					</label>
					<label>
						Quiet after an alert (minutes)
						<input type="number" min="1" max="10080" bind:value={s.cooldown_minutes} required />
					</label>
				</div>
				<p class="muted small">IG allows 30 price requests a minute; each check is one.</p>
			</div>

			<div class="card stack">
				<h2>Risk</h2>
				<div class="grid">
					<label>Account equity <input type="number" min="1" step="any" bind:value={s.equity} required /></label>
					<label>Risk per trade (%) <input type="number" min="0.01" max="10" step="any" bind:value={s.risk_pct} required /></label>
				</div>
				<p class="muted small">
					Risking {num((s.equity * s.risk_pct) / 100)} a trade. Sizes are in contracts, using each market's point value below.
				</p>
			</div>

			<div class="card stack">
				<h2>Alerts to your phone</h2>
				<label class="wide">
					ntfy topic URL
					<input type="url" bind:value={s.ntfy_url} placeholder="https://ntfy.sh/a-long-random-name" maxlength="200" />
				</label>
				<p class="muted small">
					Install the ntfy app, subscribe to a topic with a long random name, and paste its URL here. Anyone who knows
					the name can read it. Empty: alerts only show on the trading page.
				</p>
				<button type="button" class="ghost" disabled={busy} onclick={testAlert}>Send a test alert</button>
			</div>

			<div class="card stack">
				<h2>New analyses</h2>
				<label class="inline"><input type="checkbox" bind:checked={s.feed_enabled} /> Ping me when a new post appears</label>
				<div class="grid">
					<label>Feed URL <input type="url" bind:value={s.feed_url} maxlength="200" /></label>
					<label>
						Check every (minutes)
						<input type="number" min="5" max="1440" bind:value={s.feed_check_minutes} required />
					</label>
				</div>
			</div>

			<div class="card stack">
				<h2>Markets</h2>
				<p class="muted small">
					Each market needs IG's id for it (its epic): Find picks it from IG's search. "1 point =" is what one point is worth
					per contract in the equity's currency, from the market's info page on IG (Tyskland 40 Micro: SEK 10.96).
				</p>
				<ul class="markets">
					{#each s.instruments as inst, i (i)}
						<li>
							<div class="market">
								<input bind:value={inst.name} maxlength="20" aria-label="Name" required />
								<input bind:value={inst.epic} maxlength="40" placeholder="IG epic" aria-label="IG epic" />
								<button type="button" class="ghost" disabled={busy} onclick={() => startSearch(i)}>Find</button>
								<button type="button" class="ghost" onclick={() => s!.instruments.splice(i, 1)} aria-label="Remove">✕</button>
							</div>
							<label class="inline small">
								1 point =
								<input class="point" type="number" min="0.0001" step="any" bind:value={inst.point_value} required />
								per contract
							</label>
							{#if searching === i}
								<div class="row">
									<input bind:value={term} aria-label="Search IG" />
									<button type="button" class="ghost" disabled={busy} onclick={search}>Search</button>
								</div>
								{#each found as m (m.epic)}
									<button type="button" class="option" onclick={() => pick(m)}>
										{m.name} <span class="muted small">{m.epic} · {m.type} · {m.expiry} · {num(m.bid)}</span>
									</button>
								{/each}
							{/if}
						</li>
					{/each}
				</ul>
				<button type="button" class="ghost" onclick={() => s!.instruments.push({ name: '', epic: '', point_value: 1 })}>Add a market</button>
			</div>

			{#if error}<p class="error">{error}</p>{/if}
			{#if notice}<p class="muted">{notice}</p>{/if}
			<button disabled={busy}>Save</button>
		</form>
	{:else if error}
		<p class="error">{error}</p>
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
	form.stack {
		gap: 1rem;
		justify-items: stretch;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
	}
	.back {
		margin-left: auto;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.6rem;
		width: 100%;
	}
	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.9rem;
	}
	label.wide {
		width: 100%;
	}
	.inline {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.inline input {
		width: auto;
	}
	.markets {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.6rem;
		width: 100%;
	}
	.markets li {
		display: grid;
		gap: 0.4rem;
	}
	.market {
		display: grid;
		grid-template-columns: 1fr 1.4fr auto auto;
		gap: 0.4rem;
	}
	.markets input.point {
		width: 7rem;
	}
	.markets input,
	.market button {
		min-width: 0;
		padding-inline: 0.5rem;
	}
	.option {
		overflow-wrap: anywhere;
	}
	.small {
		font-size: 0.85rem;
	}
</style>

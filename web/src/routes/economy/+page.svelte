<script lang="ts">
	import { api } from '#lib/api.ts';
	import {
		judge,
		KINDS,
		monthly,
		netWorth,
		sek,
		subscriptionsPerMonth,
		totalOf,
		type Economy
	} from '#lib/economy.ts';
	import { session } from '#lib/session.svelte.ts';

	const TABS = ['Overview', 'Subscriptions', 'Purchases'] as const;
	let tab = $state<(typeof TABS)[number]>('Overview');
	let e = $state<Economy | null>(null);
	let error = $state('');
	let saved = $state('');
	let open = $state<number | null>(null);

	$effect(() => {
		if (session.user?.is_owner)
			api<Economy>('/economy')
				.then((r) => (e = r))
				.catch((err) => (error = err.message));
	});

	// Save a moment after the last change, so typing doesn't send a request per key.
	let last = '';
	$effect(() => {
		if (!e) return;
		const json = JSON.stringify(e);
		if (!last) {
			last = json;
			return;
		}
		if (json === last) return;
		const t = setTimeout(async () => {
			try {
				await api('/economy', { method: 'PUT', body: json, headers: { 'content-type': 'application/json' } });
				last = json;
				error = '';
				saved = 'Saved';
			} catch (err) {
				error = (err as Error).message;
				saved = '';
			}
		}, 600);
		return () => clearTimeout(t);
	});

	const today = () => new Date().toISOString().slice(0, 10);
</script>

<section>
	<div class="row">
		<h1>Economy</h1>
		<span class="muted small saved">{saved}</span>
	</div>
	{#if !session.user?.is_owner}
		<p class="muted">Only the hub's owner can see this page.</p>
	{:else if e}
		<nav>
			{#each TABS as t}
				<button type="button" class="tab" class:on={tab === t} onclick={() => (tab = t)}>{t}</button>
			{/each}
		</nav>
		{#if error}<p class="error">{error}</p>{/if}

		{#if tab === 'Overview'}
			<div class="card stack">
				<p class="muted small">Net worth</p>
				<p class="big">{sek(netWorth(e.accounts))}</p>
				<div class="totals">
					{#each KINDS as k}
						{@const sum = totalOf(e.accounts, k.id)}
						{#if sum}
							<span>{k.label}</span><span class="num">{k.id === 'loan' ? '−' : ''}{sek(sum)}</span>
						{/if}
					{/each}
				</div>
			</div>
			<div class="card stack">
				<h2>Accounts and loans</h2>
				<p class="muted small">Today's balance for each. Enter a loan, like the mortgage, as what you owe.</p>
				{#each e.accounts as a, i (i)}
					<div class="line">
						<input bind:value={a.name} maxlength="60" placeholder="Name" aria-label="Name" />
						<select bind:value={a.kind} aria-label="Kind">
							{#each KINDS as k}<option value={k.id}>{k.label}</option>{/each}
						</select>
						<input type="number" step="any" bind:value={a.balance} aria-label="Balance" />
						<button type="button" class="ghost" onclick={() => e!.accounts.splice(i, 1)} aria-label="Remove">✕</button>
					</div>
				{/each}
				<button type="button" class="ghost" onclick={() => e!.accounts.push({ name: 'Account', kind: 'cash', balance: 0 })}>
					Add an account or loan
				</button>
			</div>
		{:else if tab === 'Subscriptions'}
			<div class="card stack">
				<p class="muted small">Subscriptions cost</p>
				<p class="big">{sek(subscriptionsPerMonth(e.subscriptions))} <span class="muted small">a month</span></p>
				<p class="muted">{sek(subscriptionsPerMonth(e.subscriptions) * 12)} a year</p>
			</div>
			<div class="card stack">
				{#each e.subscriptions as s, i (i)}
					<div class="line">
						<input bind:value={s.name} maxlength="60" placeholder="Name" aria-label="Name" />
						<input type="number" min="0" step="any" bind:value={s.price} aria-label="Price" />
						<select bind:value={s.period} aria-label="Per">
							<option value="month">a month</option>
							<option value="year">a year</option>
						</select>
						<button type="button" class="ghost" onclick={() => e!.subscriptions.splice(i, 1)} aria-label="Remove">✕</button>
					</div>
					{#if s.period === 'year'}<p class="muted small">{sek(monthly(s))} a month</p>{/if}
				{/each}
				<button type="button" class="ghost" onclick={() => e!.subscriptions.push({ name: '', price: 0, period: 'month' })}>
					Add a subscription
				</button>
			</div>
		{:else}
			<div class="card stack">
				<h2>Thinking of buying</h2>
				<p class="muted small">Add it the day you want it. It gets a green light when every rule passes.</p>
				{#each e.wishlist as w, i (i)}
					{@const verdicts = judge(w, e)}
					{@const failed = verdicts.filter((v) => v.pass === false).length}
					<div class="wish">
						<button type="button" class="option head" onclick={() => (open = open === i ? null : i)}>
							<span>{w.name || 'Unnamed'} · {sek(w.price)}</span>
							<span class:ok={!failed} class:no={failed}>{failed ? `${failed} not passed` : 'Go'}</span>
						</button>
						{#if open === i}
							<div class="line">
								<input bind:value={w.name} maxlength="60" placeholder="What" aria-label="What" />
								<input type="number" min="0" step="any" bind:value={w.price} aria-label="Price" />
								<label class="inline small">
									Uses <input class="short" type="number" min="0" bind:value={w.uses} aria-label="Expected uses" />
								</label>
								<button type="button" class="ghost" onclick={() => ((open = null), e!.wishlist.splice(i, 1))}>Remove</button>
							</div>
							<ul class="rules">
								{#each verdicts as v}
									<li>
										{#if v.question}
											<label class="inline">
												<input type="checkbox" bind:checked={w.checks[v.question]} />
												{v.label}
											</label>
										{:else}
											<span class="mark" class:ok={v.pass} class:no={v.pass === false}>
												{v.pass === null ? '–' : v.pass ? '✓' : '✕'}
											</span>
											<span>{v.label} <span class="muted small">{v.detail}</span></span>
										{/if}
									</li>
								{/each}
							</ul>
						{/if}
					</div>
				{/each}
				<button
					type="button"
					class="ghost"
					onclick={() => {
						e!.wishlist.push({ name: '', price: 0, added: today(), uses: 0, checks: {} });
						open = e!.wishlist.length - 1;
					}}
				>
					Add something
				</button>
			</div>
			<div class="card stack">
				<h2>Rules</h2>
				<div class="grid">
					<label>Wait (days) <input type="number" min="0" max="365" bind:value={e.rules.wait_days} /></label>
					<label>Big purchase from (SEK) <input type="number" min="0" bind:value={e.rules.big_price} /></label>
					<label>Wait for big ones (days) <input type="number" min="0" max="365" bind:value={e.rules.big_wait_days} /></label>
					<label>Max % of net worth <input type="number" min="0" max="100" step="any" bind:value={e.rules.max_net_worth_pct} /></label>
					<label>Monthly expenses (SEK) <input type="number" min="0" bind:value={e.rules.monthly_expenses} /></label>
					<label>Buffer (months) <input type="number" min="0" max="60" step="any" bind:value={e.rules.emergency_months} /></label>
					<label>Hourly pay after tax <input type="number" min="0" bind:value={e.rules.hourly_pay} /></label>
					<label>Max hours of work <input type="number" min="0" step="any" bind:value={e.rules.max_work_hours} /></label>
					<label>Max cost per use (SEK) <input type="number" min="0" bind:value={e.rules.max_cost_per_use} /></label>
				</div>
				<p class="muted small">The buffer counts only Cash &amp; savings accounts. A rule set to 0 is skipped.</p>
			</div>
		{/if}
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
	.row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.saved {
		margin-left: auto;
	}
	nav {
		display: flex;
		gap: 0.25rem;
		border-bottom: 1px solid var(--border);
		overflow-x: auto;
	}
	.tab {
		background: none;
		color: var(--muted);
		border: 0;
		border-bottom: 2px solid transparent;
		border-radius: 0;
		padding: 0.6rem 0.8rem;
	}
	.tab.on {
		color: var(--text);
		border-color: var(--accent);
		font-weight: 600;
	}
	.stack {
		display: grid;
		gap: 0.6rem;
	}
	.big {
		font-size: 2rem;
		font-weight: 700;
	}
	.totals {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.25rem 1rem;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.line {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
		gap: 0.4rem;
		align-items: center;
	}
	/* The name gets its own row so the fields stay usable on a phone. */
	.line > :first-child {
		grid-column: 1 / -1;
	}
	.line select {
		font: inherit;
		color: inherit;
		padding: 0.6rem 0.5rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--surface);
		min-width: 0;
		width: 100%;
	}
	input[type='checkbox'] {
		width: auto;
		flex: none;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.6rem;
	}
	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.9rem;
	}
	.inline {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.short {
		width: 5rem;
	}
	.small {
		font-size: 0.85rem;
	}
	.wish {
		display: grid;
		gap: 0.5rem;
	}
	.head {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		width: 100%;
	}
	.rules {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.4rem;
	}
	.rules li {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
	}
	.mark {
		width: 1.2rem;
		text-align: center;
		flex: none;
	}
	.ok {
		color: var(--good);
	}
	.no {
		color: var(--danger);
	}
</style>

<script lang="ts">
	import { api } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';

	type Day = { day: string; input: number; output: number; cache_read: number; cache_write: number; tokens: number; cost_usd: number };
	type Share = { name: string; tokens: number; cost_usd: number | null; replies: number };
	type Usage = {
		plan_usage_url: string;
		code: {
			found: boolean;
			days: Day[];
			models: Share[];
			projects: Share[];
			today_tokens: number;
			avg_tokens_7d: number;
			avg_tokens_30d: number;
			tokens_30d: number;
			cost_30d: number;
			avg_cost_7d: number;
			month_estimate: number;
			sessions_30d: number;
			cache_hit_rate: number | null;
			unpriced_models: string[];
		};
		api: { configured: boolean; error: string | null; days: Day[]; models: Share[]; cost_30d: number; avg_cost_7d: number };
	};

	let usage = $state<Usage | null>(null);
	let error = $state('');
	let hovered = $state<Day | null>(null);

	$effect(() => {
		if (session.user?.is_owner)
			api<Usage>('/claude/usage')
				.then((u) => (usage = u))
				.catch((e) => (error = e.message));
	});

	const fmt = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 });
	const usd = new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' });
	const tokens = (n: number) => fmt.format(n);
	const dayLabel = (iso: string) =>
		new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
	const short = (model: string) => model.replace(/^claude-/, '').replace(/-(\d)-(\d)$/, ' $1.$2').replace(/-(\d)$/, ' $1');

	const max = $derived(Math.max(1, ...(usage?.code.days.map((d) => d.tokens) ?? [1])));
</script>

<section>
	<h1>Claude</h1>
	{#if !session.user?.is_owner}
		<p class="muted">Only the hub's owner can see this page.</p>
	{:else if error}
		<p class="error">{error}</p>
	{:else if usage}
		<div class="card plan">
			<div>
				<strong>Your plan's limits</strong>
				<p class="muted">
					How much of your Claude plan is left, and when it resets, is only shown on claude.ai. Anthropic
					doesn't offer it to other apps.
				</p>
			</div>
			<a class="button" href={usage.plan_usage_url} target="_blank" rel="noopener noreferrer">Open usage on claude.ai</a>
		</div>

		<h2>Claude Code on the Pi</h2>
		{#if !usage.code.found}
			<p class="card muted">
				No Claude Code logs found yet. Once Claude Code runs on the Pi, point <code>HUB_CLAUDE_LOGS</code> in
				<code>.env</code> at its <code>~/.claude/projects</code> folder (see docs/claude-usage.md).
			</p>
		{:else}
			<div class="tiles">
				<div class="card tile">
					<span class="muted">Today</span>
					<strong>{tokens(usage.code.today_tokens)}</strong>
					<span class="muted small">tokens</span>
				</div>
				<div class="card tile">
					<span class="muted">Average per day</span>
					<strong>{tokens(usage.code.avg_tokens_7d)}</strong>
					<span class="muted small">last 7 days · {tokens(usage.code.avg_tokens_30d)} over 30</span>
				</div>
				<div class="card tile">
					<span class="muted">At API prices</span>
					<strong>{usd.format(usage.code.avg_cost_7d)}<span class="unit">/day</span></strong>
					<span class="muted small">≈ {usd.format(usage.code.month_estimate)} a month at this pace</span>
				</div>
				<div class="card tile">
					<span class="muted">Last 30 days</span>
					<strong>{tokens(usage.code.tokens_30d)}</strong>
					<span class="muted small">
						{usage.code.sessions_30d} sessions{usage.code.cache_hit_rate !== null
							? ` · ${Math.round(usage.code.cache_hit_rate * 100)}% from cache`
							: ''}
					</span>
				</div>
			</div>

			<div class="card">
				<div class="chart-head">
					<strong>Tokens per day</strong>
					<span class="muted small" aria-live="polite">
						{#if hovered}
							{dayLabel(hovered.day)}: {tokens(hovered.tokens)} tokens · {usd.format(hovered.cost_usd)}
						{:else}
							Last 30 days · hover or tap a day
						{/if}
					</span>
				</div>
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="bars" onmouseleave={() => (hovered = null)}>
					{#each usage.code.days as d (d.day)}
						<button
							class="bar-slot"
							aria-label="{dayLabel(d.day)}: {d.tokens} tokens"
							onmouseenter={() => (hovered = d)}
							onfocus={() => (hovered = d)}
							onclick={() => (hovered = d)}
						>
							<span class="bar" class:active={hovered?.day === d.day} style="height: {(d.tokens / max) * 100}%"></span>
						</button>
					{/each}
				</div>
				<div class="axis muted small">
					<span>{dayLabel(usage.code.days[0].day)}</span>
					<span>Today</span>
				</div>
			</div>

			<div class="grid2">
				<div class="card">
					<strong>By model</strong>
					<table>
						<thead><tr><th>Model</th><th>Tokens</th><th>At API prices</th></tr></thead>
						<tbody>
							{#each usage.code.models as m (m.name)}
								<tr>
									<td>{short(m.name)}</td>
									<td>{tokens(m.tokens)}</td>
									<td>{m.cost_usd === null ? '–' : usd.format(m.cost_usd)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<div class="card">
					<strong>By project</strong>
					<table>
						<thead><tr><th>Folder</th><th>Tokens</th><th>Replies</th></tr></thead>
						<tbody>
							{#each usage.code.projects as p (p.name)}
								<tr><td>{p.name}</td><td>{tokens(p.tokens)}</td><td>{p.replies}</td></tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
			<p class="muted small">
				"At API prices" is what the same use would cost on Anthropic's API, cache discounts included. On a plan
				you don't pay this; it's for comparing days.
			</p>
		{/if}

		<h2>API keys</h2>
		{#if !usage.api.configured}
			<p class="card muted">
				Not connected. If you use Anthropic API keys (console.anthropic.com, an organisation account), add an Admin
				API key as <code>HUB_ANTHROPIC_ADMIN_KEY</code> in <code>.env</code> to see their spend here.
			</p>
		{:else if usage.api.error}
			<p class="card error">{usage.api.error}</p>
		{:else}
			<div class="tiles">
				<div class="card tile">
					<span class="muted">Spent, last 30 days</span>
					<strong>{usd.format(usage.api.cost_30d)}</strong>
				</div>
				<div class="card tile">
					<span class="muted">Average per day</span>
					<strong>{usd.format(usage.api.avg_cost_7d)}</strong>
					<span class="muted small">last 7 days</span>
				</div>
			</div>
			{#if usage.api.models.length}
				<div class="card">
					<table>
						<thead><tr><th>Model</th><th>Tokens, 30 days</th></tr></thead>
						<tbody>
							{#each usage.api.models as m (m.name)}
								<tr><td>{short(m.name)}</td><td>{tokens(m.tokens)}</td></tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		{/if}
	{/if}
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 900px;
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
		margin-top: 0.5rem;
	}
	.small {
		font-size: 0.85rem;
	}
	.plan {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}
	.plan p {
		margin-top: 0.2rem;
	}
	.button {
		padding: 0.6rem 1rem;
		border-radius: 8px;
		background: var(--accent);
		color: var(--accent-text);
		font-weight: 600;
		text-decoration: none;
	}
	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
		gap: 0.75rem;
	}
	.tile {
		display: grid;
		gap: 0.15rem;
		padding: 1rem;
	}
	.tile strong {
		font-size: 1.6rem;
		line-height: 1.2;
	}
	.unit {
		font-size: 0.9rem;
		font-weight: 500;
		color: var(--muted);
	}
	.chart-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.bars {
		display: grid;
		grid-template-columns: repeat(30, 1fr);
		align-items: end;
		height: 160px;
		border-bottom: 1px solid var(--border);
	}
	.bar-slot {
		height: 100%;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		background: none;
		padding: 0 1px;
		border-radius: 0;
		cursor: pointer;
	}
	.bar {
		width: 100%;
		max-width: 18px;
		min-height: 1px;
		background: var(--accent);
		opacity: 0.75;
		border-radius: 4px 4px 0 0;
	}
	.bar.active,
	.bar-slot:hover .bar {
		opacity: 1;
	}
	.axis {
		display: flex;
		justify-content: space-between;
		margin-top: 0.35rem;
	}
	.grid2 {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 0.75rem;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		margin-top: 0.5rem;
		font-size: 0.9rem;
	}
	th,
	td {
		text-align: left;
		padding: 0.35rem 0.5rem 0.35rem 0;
		border-bottom: 1px solid var(--border);
	}
	th {
		color: var(--muted);
		font-weight: 500;
	}
	td:not(:first-child),
	th:not(:first-child) {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
</style>

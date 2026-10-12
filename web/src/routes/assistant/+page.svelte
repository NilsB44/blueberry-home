<script lang="ts">
	import { api, streamText } from '#lib/api.ts';

	type Msg = { role: 'user' | 'assistant'; content: string };
	type Status = { online: boolean; default_model: string; models: string[] };

	let status = $state<Status | null>(null);
	let model = $state('');
	let messages = $state<Msg[]>([]);
	let draft = $state('');
	let busy = $state(false);
	let error = $state('');
	let controller: AbortController | null = null;

	$effect(() => {
		api<Status>('/assistant/status').then((s) => {
			status = s;
			model = s.models.includes(s.default_model) ? s.default_model : (s.models[0] ?? s.default_model);
		});
	});

	async function send(e: SubmitEvent) {
		e.preventDefault();
		const text = draft.trim();
		if (!text || busy) return;
		draft = '';
		error = '';
		messages.push({ role: 'user', content: text });
		const history = $state.snapshot(messages);
		messages.push({ role: 'assistant', content: '' });
		const reply = messages[messages.length - 1];
		busy = true;
		controller = new AbortController();
		try {
			for await (const chunk of streamText('/assistant/chat', { messages: history, model }, controller.signal)) {
				reply.content += chunk;
			}
		} catch (err) {
			if ((err as Error).name !== 'AbortError') error = (err as Error).message;
			if (!reply.content) messages.pop();
		} finally {
			busy = false;
			controller = null;
		}
	}
</script>

<section>
	<div class="head">
		<h1>Assistant</h1>
		{#if status?.online && status.models.length}
			<select bind:value={model}>
				{#each status.models as m}<option>{m}</option>{/each}
			</select>
		{/if}
	</div>

	{#if status && !status.online}
		<p class="card muted">
			The model server isn't running. Start it on the Pi with
			<code>docker compose --profile llm up -d</code>, then pull a model with
			<code>docker compose exec ollama ollama pull {status.default_model}</code>.
		</p>
	{:else if status && status.models.length === 0}
		<p class="card muted">
			No models yet. Pull one with <code>docker compose exec ollama ollama pull {status.default_model}</code>.
		</p>
	{/if}

	<div class="log">
		{#each messages as m, i (i)}
			<div class="msg {m.role}">{m.content || '…'}</div>
		{/each}
	</div>
	{#if error}<p class="error">{error}</p>{/if}

	<form onsubmit={send}>
		<textarea
			bind:value={draft}
			rows="2"
			placeholder="Ask something, e.g. explain the passé composé"
			onkeydown={(e) => {
				if (e.key === 'Enter' && !e.shiftKey) {
					e.preventDefault();
					e.currentTarget.form?.requestSubmit();
				}
			}}
		></textarea>
		{#if busy}
			<button type="button" class="ghost" onclick={() => controller?.abort()}>Stop</button>
		{:else}
			<button disabled={!status?.online || !draft.trim()}>Send</button>
		{/if}
	</form>
</section>

<style>
	section {
		padding: 1.5rem 16px;
		display: grid;
		gap: 1rem;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	select {
		padding: 0.4rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
	}
	.log {
		display: grid;
		gap: 0.5rem;
	}
	.msg {
		white-space: pre-wrap;
		padding: 0.6rem 0.9rem;
		border-radius: var(--radius);
		max-width: 85%;
	}
	.user {
		justify-self: end;
		background: var(--accent);
		color: var(--accent-text);
	}
	.assistant {
		justify-self: start;
		background: var(--surface);
		border: 1px solid var(--border);
	}
	form {
		display: flex;
		gap: 0.5rem;
		align-items: end;
	}
	code {
		font-size: 0.85em;
	}
</style>

<script lang="ts">
	import { api, type User } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';
	import { setTheme, theme, type ThemePref } from '#lib/theme.svelte.ts';

	const THEMES: { value: ThemePref; label: string }[] = [
		{ value: 'system', label: 'Same as device' },
		{ value: 'light', label: 'Light' },
		{ value: 'dark', label: 'Dark' }
	];

	let displayName = $state(session.user?.display_name ?? '');
	let username = $state(session.user?.username ?? '');
	let error = $state('');
	let saved = $state(false);
	let busy = $state(false);

	async function save(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		saved = false;
		try {
			session.user = await api<User>('/auth/me', {
				method: 'PATCH',
				json: { display_name: displayName, username: username.toLowerCase() }
			});
			saved = true;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<section>
	<h1>You</h1>
	<p class="muted">
		Anyone on your home Wi-Fi can use the hub without a password. This {session.user?.device ?? 'device'}
		remembers who you are, so pick a name people will recognise.
	</p>
	<form class="card" onsubmit={save}>
		<label>Name <input bind:value={displayName} required maxlength="64" /></label>
		<label>
			Username
			<input
				bind:value={username}
				required
				minlength="3"
				maxlength="32"
				pattern="[a-zA-Z0-9_.\-]+"
				autocapitalize="off"
				autocomplete="off"
			/>
		</label>
		{#if error}<p class="error">{error}</p>{/if}
		{#if saved}<p>Saved.</p>{/if}
		<button disabled={busy}>Save</button>
	</form>
	<div class="card">
		<h2>Look</h2>
		<div class="segmented" role="radiogroup" aria-label="Colour theme on this device">
			{#each THEMES as t (t.value)}
				<button
					role="radio"
					aria-checked={theme.pref === t.value}
					class:on={theme.pref === t.value}
					onclick={() => setTheme(t.value)}>{t.label}</button
				>
			{/each}
		</div>
	</div>
	<p class="muted">
		Clearing this browser's data makes it a new person. Already have an account with a password?
		<a href="/login">Use it on this device</a>.
	</p>
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 520px;
		margin: 0 auto;
		display: grid;
		gap: 0.75rem;
	}
	h1,
	p {
		margin: 0;
	}
	form {
		display: grid;
		gap: 0.75rem;
	}
	h2 {
		font-size: 1rem;
		margin: 0 0 0.75rem;
	}
	.segmented {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.25rem;
		padding: 0.25rem;
		border-radius: 12px;
		background: var(--surface-2);
	}
	.segmented button {
		background: transparent;
		color: var(--muted);
		padding: 0.5rem 0.25rem;
		font-size: 0.9rem;
	}
	.segmented button.on {
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow);
	}
	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.9rem;
	}
</style>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, type User } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			session.user = await api<User>('/auth/login', { method: 'POST', json: { username, password } });
			goto('/');
		} catch (err) {
			error = (err as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<div class="auth">
	<h1>Use an existing account</h1>
	<p class="muted">
		Only for accounts made with a password. This device will remember it, so you won't be asked again.
	</p>
	<form onsubmit={submit}>
		<label>Username <input bind:value={username} autocomplete="username" required /></label>
		<label>
			Password <input type="password" bind:value={password} autocomplete="current-password" required />
		</label>
		{#if error}<p class="error">{error}</p>{/if}
		<button disabled={busy}>Use on this device</button>
		<a href="/me" class="muted">Back</a>
	</form>
</div>

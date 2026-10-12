<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, type User } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';

	let username = $state('');
	let display_name = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			session.user = await api<User>('/auth/setup', {
				method: 'POST',
				json: { username: username.toLowerCase(), display_name, password }
			});
			session.needsSetup = false;
			goto('/');
		} catch (err) {
			error = (err as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<div class="auth">
	<h1>Set up your hub</h1>
	<p class="muted">Create the admin account. You can add guest accounts later.</p>
	<form onsubmit={submit}>
		<label>Your name <input bind:value={display_name} required /></label>
		<label>
			Username <input bind:value={username} autocomplete="username" pattern="[a-zA-Z0-9_.\-]+" minlength="3" required />
		</label>
		<label>
			Password (10+ characters)
			<input type="password" bind:value={password} autocomplete="new-password" minlength="10" required />
		</label>
		{#if error}<p class="error">{error}</p>{/if}
		<button disabled={busy}>Create account</button>
	</form>
</div>

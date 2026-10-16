<script lang="ts">
	import { api, type User } from '#lib/api.ts';
	import { session } from '#lib/session.svelte.ts';

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
	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.9rem;
	}
</style>

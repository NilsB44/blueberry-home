import { api, ApiError, type User } from './api.ts';

export const session = $state<{ user: User | null; loaded: boolean; needsSetup: boolean }>({
	user: null,
	loaded: false,
	needsSetup: false
});

export async function loadSession() {
	try {
		const setup = await api<{ needs_setup: boolean }>('/auth/setup');
		session.needsSetup = setup.needs_setup;
		session.user = setup.needs_setup ? null : await api<User>('/auth/me');
	} catch (e) {
		if (!(e instanceof ApiError && e.status === 401)) throw e;
		session.user = null;
	} finally {
		session.loaded = true;
	}
}

export async function logout() {
	await api('/auth/logout', { method: 'POST' });
	session.user = null;
}

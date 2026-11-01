import { api, type ModuleInfo } from '#lib/api.ts';
import { reconcile, type Layout } from './layout.ts';

/** Each person's arrangement lives on the hub, so it's the same on every visit; a copy on the
 * device lets the home screen draw straight away before the hub answers. */

const cacheKey = (userId: number) => `blueberry.layout.${userId}`;

export function cachedLayout(userId: number, modules: ModuleInfo[]): Layout | null {
	try {
		const raw = localStorage.getItem(cacheKey(userId));
		return raw ? reconcile(JSON.parse(raw) as Layout, modules) : null;
	} catch {
		return null;
	}
}

function cache(userId: number, layout: Layout | null) {
	try {
		if (layout) localStorage.setItem(cacheKey(userId), JSON.stringify(layout));
		else localStorage.removeItem(cacheKey(userId));
	} catch {
		// storage blocked: the hub still has it
	}
}

export async function loadLayout(userId: number, modules: ModuleInfo[]): Promise<Layout> {
	const saved = await api<Layout | null>('/home/layout');
	cache(userId, saved);
	return reconcile(saved, modules);
}

export async function saveLayout(userId: number, layout: Layout) {
	cache(userId, layout);
	await api('/home/layout', { method: 'PUT', json: layout });
}

export async function resetLayout(userId: number) {
	cache(userId, null);
	await api('/home/layout', { method: 'DELETE' });
}

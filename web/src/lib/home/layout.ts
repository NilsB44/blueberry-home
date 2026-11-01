import type { ModuleInfo } from '#lib/api.ts';

/** A home screen is a row of items: an app on its own, or a folder of apps. Folders hold apps only. */
export type LayoutApp = { type: 'app'; id: string };
export type LayoutFolder = { type: 'folder'; id: string; name: string; apps: string[] };
export type LayoutItem = LayoutApp | LayoutFolder;
export type Layout = { items: LayoutItem[] };

/** The folders every module starts in (the API gives each module one of these ids). */
export const DEFAULT_FOLDERS: { id: ModuleInfo['folder']; name: string }[] = [
	{ id: 'games', name: 'Games' },
	{ id: 'learning', name: 'Learning' },
	{ id: 'nerd', name: 'Nerd stuff' },
	{ id: 'life', name: 'Home & life' }
];

export function defaultLayout(modules: ModuleInfo[]): Layout {
	return {
		items: DEFAULT_FOLDERS.map((f) => ({
			type: 'folder',
			id: f.id,
			name: f.name,
			apps: modules.filter((m) => m.folder === f.id).map((m) => m.id)
		}))
	};
}

/** Fit a saved layout to the apps this person can see today: forget apps that are gone, and put new
 * ones in their usual folder (or on the home screen if that folder was removed). */
export function reconcile(saved: Layout | null, modules: ModuleInfo[]): Layout {
	if (!saved) return defaultLayout(modules);
	const known = new Set(modules.map((m) => m.id));
	const seen = new Set<string>();
	const keep = (id: string) => known.has(id) && !seen.has(id) && (seen.add(id), true);

	const items: LayoutItem[] = [];
	const folderIds = new Set<string>();
	for (const item of saved.items) {
		if (item.type === 'app') {
			if (keep(item.id)) items.push({ type: 'app', id: item.id });
		} else if (!folderIds.has(item.id)) {
			folderIds.add(item.id);
			items.push({ ...item, apps: item.apps.filter(keep) });
		}
	}
	for (const m of modules) {
		if (seen.has(m.id)) continue;
		const folder = items.find((i): i is LayoutFolder => i.type === 'folder' && i.id === m.folder);
		if (folder) folder.apps.push(m.id);
		else items.push({ type: 'app', id: m.id });
	}
	return { items };
}

/** Where a dragged app or folder is right now: on the home screen, or inside a folder. */
export type Place = { container: 'home' } | { container: 'folder'; folder: string };

export function findApp(layout: Layout, id: string): { place: Place; index: number } | null {
	for (const [i, item] of layout.items.entries()) {
		if (item.type === 'app' && item.id === id) return { place: { container: 'home' }, index: i };
		if (item.type === 'folder') {
			const j = item.apps.indexOf(id);
			if (j >= 0) return { place: { container: 'folder', folder: item.id }, index: j };
		}
	}
	return null;
}

export function folderById(layout: Layout, id: string): LayoutFolder | undefined {
	return layout.items.find((i): i is LayoutFolder => i.type === 'folder' && i.id === id);
}

function move<T>(list: T[], from: number, to: number) {
	const [x] = list.splice(from, 1);
	list.splice(Math.max(0, Math.min(to, list.length)), 0, x);
}

/** Move a home-screen item (app or folder) to another spot on the home screen. */
export function moveOnHome(layout: Layout, from: number, to: number) {
	move(layout.items, from, to);
}

/** Move an app to another spot within its folder. */
export function moveInFolder(layout: Layout, folder: string, from: number, to: number) {
	const f = folderById(layout, folder);
	if (f) move(f.apps, from, to);
}

function takeApp(layout: Layout, id: string) {
	const at = findApp(layout, id);
	if (!at) return;
	if (at.place.container === 'home') layout.items.splice(at.index, 1);
	else folderById(layout, at.place.folder)?.apps.splice(at.index, 1);
}

/** Take an app out of wherever it is and put it in a folder (at the end unless told where). */
export function putInFolder(layout: Layout, app: string, folder: string, index?: number) {
	takeApp(layout, app);
	const f = folderById(layout, folder);
	if (!f) return;
	f.apps.splice(index ?? f.apps.length, 0, app);
}

/** Take an app out of its folder and put it on the home screen. */
export function putOnHome(layout: Layout, app: string, index: number) {
	takeApp(layout, app);
	layout.items.splice(Math.min(index, layout.items.length), 0, { type: 'app', id: app });
}

function newFolderId(layout: Layout) {
	let n = 1;
	while (folderById(layout, `folder-${n}`)) n++;
	return `folder-${n}`;
}

/** Drop one home-screen app onto another: both go into a new folder where the target was. */
export function mergeIntoFolder(layout: Layout, dragged: string, target: string, name = 'New folder') {
	const id = newFolderId(layout);
	takeApp(layout, dragged);
	const at = layout.items.findIndex((i) => i.type === 'app' && i.id === target);
	if (at < 0) return null;
	layout.items[at] = { type: 'folder', id, name, apps: [target, dragged] };
	return id;
}

export function addFolder(layout: Layout, name = 'New folder') {
	const id = newFolderId(layout);
	layout.items.push({ type: 'folder', id, name, apps: [] });
	return id;
}

/** Remove a folder; its apps stay, on the home screen where the folder was. */
export function removeFolder(layout: Layout, id: string) {
	const at = layout.items.findIndex((i) => i.type === 'folder' && i.id === id);
	if (at < 0) return;
	const f = layout.items[at] as LayoutFolder;
	layout.items.splice(at, 1, ...f.apps.map((a): LayoutApp => ({ type: 'app', id: a })));
}

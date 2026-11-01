/** Light, dark or follow the device. The choice is kept on this device; app.html applies it before
 * the first paint so there's no flash, and this module keeps it in sync afterwards. */

export type ThemePref = 'system' | 'light' | 'dark';

const KEY = 'blueberry.theme';
const media = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;

function stored(): ThemePref {
	try {
		const v = localStorage.getItem(KEY);
		if (v === 'light' || v === 'dark') return v;
	} catch {
		// storage blocked (private mode): follow the device
	}
	return 'system';
}

export const theme = $state<{ pref: ThemePref; systemDark: boolean }>({
	pref: stored(),
	systemDark: media?.matches ?? false
});

media?.addEventListener('change', (e) => {
	theme.systemDark = e.matches;
	apply();
});

/** Is the page showing dark colours right now? For canvases that can't read CSS variables. */
export function isDark(): boolean {
	return theme.pref === 'dark' || (theme.pref === 'system' && theme.systemDark);
}

function apply() {
	const root = document.documentElement;
	if (theme.pref === 'system') delete root.dataset.theme;
	else root.dataset.theme = theme.pref;
	document.querySelector('meta[name="theme-color"]')?.setAttribute('content', isDark() ? '#0f1116' : '#f4f5f8');
}

export function setTheme(pref: ThemePref) {
	theme.pref = pref;
	try {
		if (pref === 'system') localStorage.removeItem(KEY);
		else localStorage.setItem(KEY, pref);
	} catch {
		// not remembered, still applied for this visit
	}
	apply();
}

/** The header button: flips between light and dark, starting from whatever is showing now. */
export function toggleTheme() {
	setTheme(isDark() ? 'light' : 'dark');
}

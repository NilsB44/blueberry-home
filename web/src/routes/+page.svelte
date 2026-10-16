<script lang="ts">
	import { flip } from 'svelte/animate';
	import { fade, fly } from 'svelte/transition';
	import { api, type ModuleInfo } from '#lib/api.ts';
	import Icon from '#lib/home/Icon.svelte';
	import {
		addFolder,
		folderById,
		mergeIntoFolder,
		moveInFolder,
		moveOnHome,
		putInFolder,
		putOnHome,
		reconcile,
		removeFolder,
		type Layout,
		type LayoutFolder
	} from '#lib/home/layout.ts';
	import { cachedLayout, loadLayout, resetLayout, saveLayout } from '#lib/home/store.ts';
	import { STATUS_LABEL, type Schedule } from '#lib/security.ts';
	import { session } from '#lib/session.svelte.ts';

	let modules = $state<ModuleInfo[]>([]);
	let layout = $state<Layout>({ items: [] });
	let error = $state('');
	let saveError = $state('');
	let security = $state<Schedule | null>(null);

	let editing = $state(false);
	let openFolder = $state<string | null>(null);
	let renaming = $state(false);

	$effect(() => {
		const user = session.user;
		if (!user) return;
		api<ModuleInfo[]>('/modules')
			.then((m) => {
				modules = m;
				layout = cachedLayout(user.id, m) ?? reconcile(null, m);
				return loadLayout(user.id, m);
			})
			.then((l) => {
				// Don't yank the screen out from under someone already moving things.
				if (!drag && !editing) layout = l;
			})
			.catch((e) => (error = e.message));
		if (user.is_owner) {
			api<Schedule>('/security/schedule')
				.then((s) => (security = s))
				.catch(() => {});
		}
	});

	const byId = $derived(new Map(modules.map((m) => [m.id, m])));
	const appsIn = (f: LayoutFolder) => f.apps.map((id) => byId.get(id)).filter((m) => m !== undefined);
	const folder = $derived(openFolder ? folderById(layout, openFolder) : undefined);

	const alert = $derived.by(() => {
		const latest = security?.latest;
		if (!latest || (latest.status !== 'fail' && latest.status !== 'warn')) return null;
		const n = latest.checks.filter((c) => c.status !== 'ok').length;
		return { status: latest.status, n };
	});

	const greeting = $derived.by(() => {
		const h = new Date().getHours();
		const part = h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
		return `${part}, ${session.user?.display_name ?? ''}`;
	});

	let saveTimer: ReturnType<typeof setTimeout> | undefined;
	function save() {
		const user = session.user;
		if (!user) return;
		clearTimeout(saveTimer);
		saveTimer = setTimeout(() => {
			saveLayout(user.id, $state.snapshot(layout))
				.then(() => (saveError = ''))
				.catch(() => (saveError = "Couldn't save your layout to the hub. It's kept on this device for now."));
		}, 400);
	}

	async function reset() {
		const user = session.user;
		if (!user) return;
		clearTimeout(saveTimer);
		layout = reconcile(null, modules);
		openFolder = null;
		await resetLayout(user.id).catch(() => {});
	}

	function newFolder() {
		openFolder = addFolder(layout);
		renaming = true;
		save();
	}

	function closeFolder() {
		openFolder = null;
		renaming = false;
	}

	function deleteFolder(id: string) {
		removeFolder(layout, id);
		closeFolder();
		save();
	}

	function done() {
		editing = false;
		renaming = false;
	}

	// --- Press and hold to move -----------------------------------------------------------------
	//
	// Holding any icon for a moment (or just dragging, once in edit mode) picks it up. While it's
	// held: resting on the edge of another icon shuffles it into that spot, dropping an app on a
	// folder puts it inside, and dropping an app on another app makes a new folder of the two.
	// Dragging an app out of an open folder puts it back on the home screen.

	type Grab = { kind: 'app' | 'folder'; id: string };
	type Press = Grab & { pointerId: number; x0: number; y0: number; timer?: ReturnType<typeof setTimeout> };
	type Drag = Grab & { x: number; y: number };
	type Hover = { into: string } | { merge: string } | null;

	const HOLD_MS = 450;
	const SLOP = 10;

	let press: Press | null = null;
	let drag = $state<Drag | null>(null);
	let hover = $state<Hover>(null);
	let swallowClick = false;
	let dwell: { key: string; timer: ReturnType<typeof setTimeout> } | null = null;
	// The icon we just swapped with. It slides away under the finger, so ignore it until the finger
	// moves onto something else; otherwise the two would swap straight back.
	let swappedWith = '';
	let leaveTimer: ReturnType<typeof setTimeout> | undefined;
	let sheet = $state<HTMLElement | null>(null);

	const dragged = $derived(drag?.kind === 'app' ? byId.get(drag.id) : undefined);
	const draggedFolder = $derived(drag?.kind === 'folder' ? folderById(layout, drag.id) : undefined);

	function onPointerDown(e: PointerEvent, grab: Grab) {
		swallowClick = false;
		if (e.button !== 0 || drag) return;
		press = { ...grab, pointerId: e.pointerId, x0: e.clientX, y0: e.clientY };
		// Outside edit mode a short press is a tap; only a held press picks the icon up.
		if (!editing) press.timer = setTimeout(() => press && pickUp(press, e.clientX, e.clientY), HOLD_MS);
	}

	function pickUp(p: Press, x: number, y: number) {
		clearTimeout(p.timer);
		press = null;
		editing = true;
		swallowClick = true;
		drag = { kind: p.kind, id: p.id, x, y };
		navigator.vibrate?.(12);
	}

	function onPointerMove(e: PointerEvent) {
		if (press && e.pointerId === press.pointerId) {
			const moved = Math.hypot(e.clientX - press.x0, e.clientY - press.y0) > SLOP;
			if (moved && editing) pickUp(press, e.clientX, e.clientY);
			else if (moved) {
				// It's a scroll, not a hold.
				clearTimeout(press.timer);
				press = null;
			}
		}
		if (!drag) return;
		drag.x = e.clientX;
		drag.y = e.clientY;
		track(e.clientX, e.clientY);
	}

	function track(x: number, y: number) {
		if (!drag) return;
		// Leaving an open folder with one of its apps puts the app back on the home screen.
		if (openFolder && sheet) {
			const r = sheet.getBoundingClientRect();
			const outside = x < r.left || x > r.right || y < r.top || y > r.bottom;
			if (outside && drag.kind === 'app' && leaveTimer === undefined) {
				leaveTimer = setTimeout(() => {
					leaveTimer = undefined;
					if (!drag || !openFolder) return;
					putOnHome(layout, drag.id, layout.items.length);
					closeFolder();
				}, 300);
			} else if (!outside && leaveTimer !== undefined) {
				clearTimeout(leaveTimer);
				leaveTimer = undefined;
			}
		}

		const slot = document.elementFromPoint(x, y)?.closest<HTMLElement>('[data-slot]');
		if (!slot || (slot.dataset.kind === drag.kind && slot.dataset.id === drag.id)) {
			hover = null;
			swappedWith = '';
			cancelDwell();
			return;
		}
		const key = `${slot.dataset.kind}:${slot.dataset.id}`;
		if (key !== swappedWith) swappedWith = '';
		const index = Number(slot.dataset.index);

		if (slot.dataset.slot === 'folder') {
			// Inside a folder: the list simply makes room.
			const from = folder?.apps.indexOf(drag.id) ?? -1;
			if (folder && from >= 0 && swappedWith !== key) {
				moveInFolder(layout, folder.id, from, index);
				swappedWith = key;
			}
			return;
		}
		if (openFolder) return;

		// On the home screen: the middle of an icon is "drop in here", the edge is "go here".
		const r = slot.getBoundingClientRect();
		const middle = Math.abs(x - (r.left + r.width / 2)) < r.width * 0.25 && y < r.top + r.height * 0.7;
		if (middle && drag.kind === 'app') {
			cancelDwell();
			hover = slot.dataset.kind === 'folder' ? { into: slot.dataset.id! } : { merge: slot.dataset.id! };
			return;
		}
		hover = null;
		// Wait a beat before shuffling, so sweeping across icons on the way to a folder doesn't.
		if (dwell?.key === key || swappedWith === key) return;
		cancelDwell();
		dwell = {
			key,
			timer: setTimeout(() => {
				dwell = null;
				if (!drag) return;
				const from = layout.items.findIndex((i) => i.type === drag!.kind && i.id === drag!.id);
				if (from >= 0) moveOnHome(layout, from, index);
				swappedWith = key;
			}, 140)
		};
	}

	function cancelDwell() {
		if (dwell) clearTimeout(dwell.timer);
		dwell = null;
	}

	function onPointerUp(e: PointerEvent) {
		if (press && e.pointerId === press.pointerId) {
			clearTimeout(press.timer);
			press = null;
		}
		if (!drag) return;
		cancelDwell();
		clearTimeout(leaveTimer);
		leaveTimer = undefined;
		if (e.type !== 'pointercancel' && hover && drag.kind === 'app') {
			if ('into' in hover) putInFolder(layout, drag.id, hover.into);
			else {
				const id = mergeIntoFolder(layout, drag.id, hover.merge);
				if (id) {
					openFolder = id;
					renaming = true;
				}
			}
		}
		drag = null;
		hover = null;
		save();
		// Swallow the click that some browsers send after a hold, but not the next real one.
		setTimeout(() => (swallowClick = false), 150);
	}

	// Once something is picked up, the finger moves it instead of scrolling the page. (Added by hand
	// because Svelte makes touchmove listeners passive, and a passive one can't stop the scroll.)
	$effect(() => {
		const stop = (e: TouchEvent) => drag && e.cancelable && e.preventDefault();
		document.addEventListener('touchmove', stop, { passive: false });
		return () => document.removeEventListener('touchmove', stop);
	});

	function onClick(e: MouseEvent) {
		if (swallowClick) {
			e.preventDefault();
			e.stopPropagation();
			swallowClick = false;
		}
	}

	function onKey(e: KeyboardEvent) {
		if (e.key !== 'Escape') return;
		if (openFolder) closeFolder();
		else if (editing) done();
	}

	/** Keyboard moving in edit mode: arrow keys shift the focused icon along the row. */
	function nudge(e: KeyboardEvent, list: 'home' | string, index: number) {
		if (!editing || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight' && e.key !== 'ArrowUp' && e.key !== 'ArrowDown'))
			return;
		e.preventDefault();
		const step = e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 1;
		const target = e.currentTarget as HTMLElement;
		if (list === 'home') moveOnHome(layout, index, index + step);
		else moveInFolder(layout, list, index, index + step);
		save();
		requestAnimationFrame(() => target.focus());
	}

	function preventMenu(e: Event) {
		e.preventDefault();
	}
</script>

<svelte:window
	onpointermove={onPointerMove}
	onpointerup={onPointerUp}
	onpointercancel={onPointerUp}
	onkeydown={onKey}
	onclickcapture={onClick}
/>

<section class:editing>
	<div class="intro">
		<h1>{greeting}</h1>
		<p class="muted hint">
			{#if editing}
				Drag to move. Drop an app on a folder to put it inside, or on another app to make a new folder.
			{:else}
				Press and hold any icon to rearrange.
			{/if}
		</p>
	</div>

	{#if error}<p class="error">{error}</p>{/if}
	{#if alert}
		<a class="card alert {alert.status}" href="/security">
			🔒 {STATUS_LABEL[alert.status]}: the security check flagged {alert.n}
			{alert.n === 1 ? 'thing' : 'things'}.
		</a>
	{/if}

	<div class="grid" role="list">
		{#each layout.items as item, i (`${item.type}:${item.id}`)}
			{@const isDragged = drag?.kind === item.type && drag.id === item.id}
			{@const isTarget =
				hover && (('into' in hover && hover.into === item.id) || ('merge' in hover && hover.merge === item.id))}
			<div
				class="slot"
				class:ghosted={isDragged}
				class:target={isTarget}
				role="listitem"
				data-slot="home"
				data-kind={item.type}
				data-id={item.id}
				data-index={i}
				animate:flip={{ duration: 220 }}
			>
				{#if item.type === 'folder'}
					{@const apps = appsIn(item)}
					<button
						class="tile"
						onpointerdown={(e) => onPointerDown(e, { kind: 'folder', id: item.id })}
						oncontextmenu={preventMenu}
						onclick={() => (openFolder = item.id)}
						onkeydown={(e) => nudge(e, 'home', i)}
						aria-label="{item.name} folder, {apps.length} apps"
					>
						<Icon folder={apps} />
						<span class="label">{item.name}</span>
					</button>
				{:else}
					{@const m = byId.get(item.id)}
					{#if m}
						{#if m.status === 'ready'}
							<a
								class="tile"
								href={m.path}
								title={m.description}
								draggable="false"
								onpointerdown={(e) => onPointerDown(e, { kind: 'app', id: m.id })}
								oncontextmenu={preventMenu}
								onclick={(e) => editing && e.preventDefault()}
								onkeydown={(e) => nudge(e, 'home', i)}
							>
								<Icon app={m} />
								<span class="label">{m.name}</span>
							</a>
						{:else}
							<button
								class="tile planned"
								title="{m.description} Coming soon."
								onpointerdown={(e) => onPointerDown(e, { kind: 'app', id: m.id })}
								oncontextmenu={preventMenu}
								onkeydown={(e) => nudge(e, 'home', i)}
							>
								<Icon app={m} />
								<span class="label">{m.name}</span>
								<span class="soon">Soon</span>
							</button>
						{/if}
					{/if}
				{/if}
			</div>
		{/each}
	</div>

	{#if saveError}<p class="error small">{saveError}</p>{/if}
</section>

{#if editing}
	<div class="editbar" transition:fly={{ y: 40, duration: 180 }}>
		<button class="ghost" onclick={newFolder}>New folder</button>
		<button class="ghost" onclick={reset}>Reset</button>
		<button onclick={done}>Done</button>
	</div>
{/if}

{#if folder}
	<div class="backdrop" transition:fade={{ duration: 150 }} onclick={closeFolder} aria-hidden="true"></div>
	<div
		class="sheet"
		class:editing
		bind:this={sheet}
		role="dialog"
		aria-modal="true"
		aria-label="{folder.name} folder"
		transition:fly={{ y: 30, duration: 200 }}
	>
		<header>
			{#if editing && renaming}
				<!-- svelte-ignore a11y_autofocus -->
				<input
					class="rename"
					value={folder.name}
					maxlength="40"
					autofocus
					onfocus={(e) => e.currentTarget.select()}
					onchange={(e) => {
						const name = e.currentTarget.value.trim();
						if (folder && name) folder.name = name;
						save();
					}}
					onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
					onblur={() => (renaming = false)}
					aria-label="Folder name"
				/>
			{:else}
				<h2>
					{#if editing}
						<button class="name" onclick={() => (renaming = true)} title="Rename">{folder.name} ✎</button>
					{:else}
						{folder.name}
					{/if}
				</h2>
			{/if}
			<button class="close" onclick={closeFolder} aria-label="Close folder">✕</button>
		</header>

		{#if folder.apps.length === 0}
			<p class="muted empty">This folder is empty. Drop an app on it from the home screen to add one.</p>
		{/if}
		<ul class="rows">
			{#each appsIn(folder) as m, i (m.id)}
				<li
					class="row-slot"
					class:ghosted={drag?.kind === 'app' && drag.id === m.id}
					data-slot="folder"
					data-kind="app"
					data-id={m.id}
					data-index={i}
					animate:flip={{ duration: 200 }}
				>
					<svelte:element
						this={m.status === 'ready' ? 'a' : 'div'}
						class="row"
						class:planned={m.status !== 'ready'}
						href={m.status === 'ready' ? m.path : undefined}
						role={m.status === 'ready' ? undefined : 'button'}
						tabindex="0"
						draggable="false"
						onpointerdown={(e: PointerEvent) => onPointerDown(e, { kind: 'app', id: m.id })}
						oncontextmenu={preventMenu}
						onclick={(e: MouseEvent) => editing && e.preventDefault()}
						onkeydown={(e: KeyboardEvent) => folder && nudge(e, folder.id, i)}
					>
						<Icon app={m} small />
						<span class="text">
							<strong>{m.name}</strong>
							<span class="muted">{m.description}</span>
						</span>
						{#if m.status !== 'ready'}<span class="soon inline">Soon</span>{/if}
					</svelte:element>
				</li>
			{/each}
		</ul>

		{#if editing}
			<button class="ghost remove" onclick={() => folder && deleteFolder(folder.id)}>
				Remove folder (its apps stay)
			</button>
		{/if}
	</div>
{/if}

{#if drag}
	<div class="drag" style:left="{drag.x}px" style:top="{drag.y}px" aria-hidden="true">
		{#if dragged}<Icon app={dragged} />{:else if draggedFolder}<Icon folder={appsIn(draggedFolder)} />{/if}
	</div>
{/if}

<style>
	section {
		padding: 1.25rem 16px 7rem;
	}
	.intro h1 {
		font-size: clamp(1.6rem, 5vw, 2.2rem);
		margin: 0.5rem 0 0.15rem;
	}
	.hint {
		margin: 0 0 1.5rem;
		font-size: 0.9rem;
		min-height: 1.5em;
	}
	.small {
		font-size: 0.85rem;
	}
	.alert {
		display: block;
		margin-bottom: 1.5rem;
		text-decoration: none;
		padding: 0.75rem 1rem;
		box-shadow: none;
	}
	.alert.warn {
		background: var(--near-bg);
		color: var(--near);
		border-color: transparent;
	}
	.alert.fail {
		background: var(--bad-bg);
		color: var(--danger);
		border-color: transparent;
	}

	/* --- home grid --- */
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(4.75rem, 1fr));
		gap: 1.5rem 0.5rem;
		max-width: 52rem;
	}
	@media (min-width: 720px) {
		.grid {
			grid-template-columns: repeat(auto-fill, minmax(7rem, 1fr));
			gap: 2rem 1rem;
		}
	}
	.slot {
		display: grid;
		justify-items: center;
		border-radius: 18px;
		transition: background-color 0.15s;
	}
	.tile {
		position: relative;
		display: grid;
		justify-items: center;
		gap: 0.45rem;
		padding: 0.25rem;
		background: none;
		border: 0;
		color: var(--text);
		font-weight: 500;
		text-decoration: none;
		cursor: pointer;
		/* Holding shouldn't select text or pop up the phone's link menu. */
		user-select: none;
		-webkit-user-select: none;
		-webkit-touch-callout: none;
		transition: transform 0.15s;
	}
	.tile:active {
		transform: scale(0.94);
	}
	.tile:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 4px;
		border-radius: 18px;
	}
	.label {
		font-size: 0.8rem;
		line-height: 1.2;
		text-align: center;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	@media (min-width: 720px) {
		.label {
			font-size: 0.9rem;
		}
	}
	.planned {
		opacity: 0.5;
		cursor: default;
	}
	.soon {
		position: absolute;
		top: -0.2rem;
		right: -0.2rem;
		font-size: 0.65rem;
		font-weight: 700;
		padding: 0.05rem 0.4rem;
		border-radius: 999px;
		background: var(--surface);
		border: 1px solid var(--border);
		color: var(--muted);
	}
	.soon.inline {
		position: static;
		flex: none;
	}
	.ghosted {
		opacity: 0.25;
	}
	.target {
		background: var(--accent-soft);
	}
	.target :global(.squircle) {
		transform: scale(1.08);
		transition: transform 0.15s;
	}

	/* In edit mode the icons wiggle, like a phone's home screen, and can be dragged right away. */
	.editing .tile {
		touch-action: none;
		animation: wiggle 0.3s ease-in-out infinite alternate;
	}
	.editing .slot:nth-child(2n) .tile {
		animation-delay: -0.15s;
	}
	@keyframes wiggle {
		from {
			transform: rotate(-1.6deg);
		}
		to {
			transform: rotate(1.6deg);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.editing .tile {
			animation: none;
		}
	}

	.editbar {
		position: fixed;
		left: 50%;
		bottom: calc(1rem + env(safe-area-inset-bottom));
		transform: translateX(-50%);
		display: flex;
		gap: 0.5rem;
		padding: 0.5rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--surface) 85%, transparent);
		backdrop-filter: blur(14px);
		-webkit-backdrop-filter: blur(14px);
		border: 1px solid var(--border);
		box-shadow: var(--shadow);
		z-index: 20;
	}
	.editbar button {
		border-radius: 999px;
		white-space: nowrap;
	}
	.editbar .ghost {
		background: var(--surface-2);
		color: var(--text);
		border-color: transparent;
	}

	/* --- open folder --- */
	.backdrop {
		position: fixed;
		inset: 0;
		background: rgb(10 12 16 / 0.45);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		z-index: 30;
	}
	.sheet {
		position: fixed;
		z-index: 31;
		left: 50%;
		top: 50%;
		transform: translate(-50%, -50%);
		width: min(34rem, calc(100vw - 32px));
		max-height: min(80dvh, 44rem);
		overflow: auto;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 24px;
		box-shadow: 0 24px 64px rgb(0 0 0 / 0.3);
		padding: 1rem 1rem 1.25rem;
	}
	/* On a phone the folder comes up from the bottom, within reach of the thumb. */
	@media (max-width: 599px) {
		.sheet {
			top: auto;
			bottom: 0;
			transform: translateX(-50%);
			width: 100vw;
			border-radius: 24px 24px 0 0;
			border-bottom: 0;
			padding-bottom: calc(1.25rem + env(safe-area-inset-bottom));
		}
	}
	.sheet header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.sheet h2 {
		margin: 0;
		font-size: 1.3rem;
		flex: 1;
		min-width: 0;
	}
	.name {
		background: none;
		color: inherit;
		font: inherit;
		padding: 0;
	}
	.rename {
		flex: 1;
		font-size: 1.15rem;
		font-weight: 700;
	}
	.close {
		flex: none;
		width: 2.25rem;
		height: 2.25rem;
		padding: 0;
		border-radius: 50%;
		background: var(--surface-2);
		color: var(--muted);
	}
	.empty {
		margin: 0.5rem 0 1rem;
	}
	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.25rem;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		padding: 0.6rem;
		border-radius: 16px;
		text-decoration: none;
		cursor: pointer;
		user-select: none;
		-webkit-user-select: none;
		-webkit-touch-callout: none;
		transition: background-color 0.15s;
	}
	.row:hover,
	.row:focus-visible {
		background: var(--surface-2);
		outline: none;
	}
	.row.planned {
		cursor: default;
	}
	.sheet.editing .row {
		touch-action: none;
	}
	.text {
		display: grid;
		min-width: 0;
		flex: 1;
	}
	.text .muted {
		font-size: 0.85rem;
		line-height: 1.35;
	}
	.remove {
		margin-top: 1rem;
		width: 100%;
	}

	.drag {
		position: fixed;
		z-index: 50;
		pointer-events: none;
		transform: translate(-50%, -50%) scale(1.12);
		filter: drop-shadow(0 12px 20px rgb(0 0 0 / 0.25));
	}
</style>

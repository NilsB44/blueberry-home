<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api.ts';
	import {
		ICONS,
		SPACES,
		bytes,
		join,
		rawUrl,
		uploadFile,
		type Entry,
		type Listing,
		type Space,
		type Upload,
		type Usage
	} from '#lib/files/files.ts';

	const space = $derived<Space>(page.url.searchParams.get('space') === 'home' ? 'home' : 'shared');
	const dir = $derived(page.url.searchParams.get('path') ?? '');
	const crumbs = $derived(dir ? dir.split('/') : []);

	let listing = $state<Listing | null>(null);
	let usage = $state<Usage | null>(null);
	let uploads = $state<Upload[]>([]);
	let error = $state('');
	let menu = $state<string | null>(null); // name of the entry whose actions are open
	let preview = $state<Entry | null>(null);
	let dragging = $state(false);
	let picker = $state<HTMLInputElement | null>(null);
	let nextId = 0;

	const images = $derived(listing?.entries.filter((e) => e.kind === 'image') ?? []);

	function load() {
		const s = space;
		const p = dir;
		error = '';
		// Drop the old folder's entries right away so its thumbnails aren't requested under the new path.
		if (listing && (listing.space !== s || listing.path !== p)) listing = null;
		Promise.all([
			api<Listing>(`/files/${s}/list?${new URLSearchParams({ path: p })}`),
			api<Usage>('/files/usage')
		])
			.then(([l, u]) => {
				listing = l;
				usage = u;
			})
			.catch((e) => (error = e.message));
	}

	$effect(load);

	function open(s: Space, path: string) {
		const q = new URLSearchParams({ space: s });
		if (path) q.set('path', path);
		menu = null;
		goto(`/files?${q}`);
	}

	function activate(e: Entry) {
		if (e.kind === 'dir') open(space, join(dir, e.name));
		else if (e.kind === 'image' || e.kind === 'video' || e.kind === 'audio') preview = e;
		else if (e.kind === 'pdf' || e.kind === 'text') window.open(rawUrl(space, join(dir, e.name)), '_blank');
		else location.href = rawUrl(space, join(dir, e.name), true);
	}

	async function send(files: FileList | File[]) {
		const s = space;
		const d = dir;
		const list = [...files];
		if (usage) {
			const tooBig = list.filter((f) => f.size > usage!.max_upload);
			if (tooBig.length) error = `Too large to upload: ${tooBig.map((f) => f.name).join(', ')}`;
		}
		for (const file of list) {
			if (usage && file.size > usage.max_upload) continue;
			const u: Upload = { id: nextId++, name: file.name, size: file.size, sent: 0, error: '', done: false };
			uploads.push(u);
			const item = uploads[uploads.length - 1];
			try {
				await uploadFile(s, d, file, (sent) => (item.sent = sent));
				item.done = true;
				item.sent = file.size;
			} catch (e) {
				item.error = (e as Error).message;
			}
			if (s === space && d === dir) load();
		}
		// Clear finished uploads after a moment; keep failures visible.
		setTimeout(() => (uploads = uploads.filter((x) => !x.done)), 2500);
	}

	function onPick(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		if (input.files?.length) send(input.files);
		input.value = '';
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		if (e.dataTransfer?.files.length) send(e.dataTransfer.files);
	}

	async function act(fn: () => Promise<unknown>) {
		menu = null;
		try {
			await fn();
			load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function newFolder() {
		const name = prompt('Folder name');
		if (name) act(() => api(`/files/${space}/folder`, { method: 'POST', json: { path: dir, name } }));
	}

	function rename(e: Entry) {
		const name = prompt('New name', e.name);
		if (name && name !== e.name)
			act(() => api(`/files/${space}/rename`, { method: 'POST', json: { path: join(dir, e.name), name } }));
	}

	function moveAcross(e: Entry) {
		const to = space === 'shared' ? 'home' : 'shared';
		act(() =>
			api(`/files/${space}/move`, { method: 'POST', json: { path: join(dir, e.name), to_space: to, to_dir: '' } })
		);
	}

	function remove(e: Entry) {
		const what = e.kind === 'dir' ? `the folder "${e.name}" and everything in it` : `"${e.name}"`;
		if (confirm(`Delete ${what}? This can't be undone.`))
			act(() => api(`/files/${space}?${new URLSearchParams({ path: join(dir, e.name) })}`, { method: 'DELETE' }));
	}

	function step(delta: number) {
		if (!preview) return;
		const i = images.findIndex((e) => e.name === preview!.name);
		if (i >= 0) preview = images[(i + delta + images.length) % images.length];
	}

	function onKey(e: KeyboardEvent) {
		if (!preview) return;
		if (e.key === 'Escape') preview = null;
		if (e.key === 'ArrowRight') step(1);
		if (e.key === 'ArrowLeft') step(-1);
	}
</script>

<svelte:window onkeydown={onKey} />

<section
	class:dragging
	aria-label="Files"
	ondragover={(e) => {
		e.preventDefault();
		dragging = true;
	}}
	ondragleave={(e) => {
		if (e.currentTarget === e.target) dragging = false;
	}}
	ondrop={onDrop}
>
	<h1>Files</h1>
	<nav class="tabs">
		{#each Object.entries(SPACES) as [s, label]}
			<a href={`/files?space=${s}`} class:active={space === s}>{label}</a>
		{/each}
	</nav>
	<p class="muted small">
		{space === 'shared' ? 'Everyone on the hub can see these.' : 'Only you can see these.'}
	</p>

	<div class="bar">
		<nav class="crumbs" aria-label="Folder">
			<button class="link" onclick={() => open(space, '')}>{SPACES[space]}</button>
			{#each crumbs as c, i}
				<span class="muted">/</span>
				<button class="link" onclick={() => open(space, crumbs.slice(0, i + 1).join('/'))}>{c}</button>
			{/each}
		</nav>
		<div class="actions">
			<button class="ghost" onclick={newFolder}>New folder</button>
			<button onclick={() => picker?.click()}>Upload</button>
			<input bind:this={picker} type="file" multiple hidden onchange={onPick} />
		</div>
	</div>

	{#if error}<p class="error">{error}</p>{/if}

	{#if uploads.length}
		<ul class="uploads card">
			{#each uploads as u (u.id)}
				<li>
					<span class="name">{u.name}</span>
					{#if u.error}
						<span class="error small">{u.error}</span>
					{:else}
						<progress max={u.size || 1} value={u.sent}></progress>
						<span class="muted small">{u.done ? 'Done' : `${Math.floor((100 * u.sent) / (u.size || 1))}%`}</span>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}

	{#if listing}
		{#if listing.entries.length === 0}
			<div class="empty card">
				<p>This folder is empty.</p>
				<p class="muted small">Tap Upload, or drop files here from your laptop.</p>
			</div>
		{:else}
			<ul class="entries card">
				{#each listing.entries as e (e.name)}
					<li>
						<button class="entry" onclick={() => activate(e)}>
							{#if e.kind === 'image'}
								<img class="thumb" src={rawUrl(space, join(dir, e.name))} alt="" loading="lazy" />
							{:else}
								<span class="icon">{ICONS[e.kind]}</span>
							{/if}
							<span class="meta">
								<span class="name">{e.name}</span>
								<span class="muted small">
									{e.kind === 'dir' ? 'Folder' : bytes(e.size)} · {new Date(e.modified).toLocaleDateString()}
								</span>
							</span>
						</button>
						<button class="ghost more" aria-label={`Actions for ${e.name}`} onclick={() => (menu = menu === e.name ? null : e.name)}>⋯</button>
						{#if menu === e.name}
							<div class="menu card">
								{#if e.kind !== 'dir'}<a href={rawUrl(space, join(dir, e.name), true)} onclick={() => (menu = null)}>Download</a>{/if}
								<button class="link" onclick={() => rename(e)}>Rename</button>
								<button class="link" onclick={() => moveAcross(e)}>Move to {space === 'shared' ? 'My files' : 'Shared'}</button>
								<button class="link danger" onclick={() => remove(e)}>Delete</button>
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	{/if}

	{#if usage}
		<p class="muted small usage">{bytes(usage.free)} free of {bytes(usage.total)}</p>
	{/if}
</section>

{#if preview}
	{@const url = rawUrl(space, join(dir, preview.name))}
	<div class="viewer" role="dialog" aria-label={preview.name}>
		<div class="viewer-bar">
			<span class="name">{preview.name}</span>
			<a class="button ghost" href={rawUrl(space, join(dir, preview.name), true)}>Download</a>
			<button class="ghost" onclick={() => (preview = null)} aria-label="Close">✕</button>
		</div>
		<div class="viewer-body">
			{#if preview.kind === 'image'}
				{#if images.length > 1}<button class="nav prev ghost" onclick={() => step(-1)} aria-label="Previous">‹</button>{/if}
				<img src={url} alt={preview.name} />
				{#if images.length > 1}<button class="nav next ghost" onclick={() => step(1)} aria-label="Next">›</button>{/if}
			{:else if preview.kind === 'video'}
				<!-- svelte-ignore a11y_media_has_caption -->
				<video src={url} controls autoplay playsinline></video>
			{:else if preview.kind === 'audio'}
				<audio src={url} controls autoplay></audio>
			{/if}
		</div>
	</div>
{/if}

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 820px;
		margin: 0 auto;
		display: grid;
		gap: 0.75rem;
		min-height: 70vh;
	}
	section.dragging {
		outline: 3px dashed var(--accent);
		outline-offset: -8px;
		border-radius: var(--radius);
	}
	h1 {
		margin: 0;
	}
	.small {
		font-size: 0.85rem;
	}
	p {
		margin: 0;
	}
	.tabs {
		display: flex;
		gap: 0.5rem;
	}
	.tabs a {
		padding: 0.4rem 0.9rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		text-decoration: none;
		color: var(--muted);
	}
	.tabs a.active {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--accent-text);
	}
	.bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.crumbs {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem;
		min-width: 0;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
	}
	button.link {
		background: none;
		border: 0;
		padding: 0.2rem 0.3rem;
		color: var(--text);
		font-weight: 500;
		text-align: left;
	}
	.danger {
		color: var(--danger) !important;
	}
	ul {
		list-style: none;
		margin: 0;
	}
	.entries {
		padding: 0.25rem 0;
	}
	.entries li {
		position: relative;
		display: flex;
		align-items: center;
		border-bottom: 1px solid var(--border);
	}
	.entries li:last-child {
		border-bottom: 0;
	}
	.entry {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-width: 0;
		background: none;
		color: var(--text);
		padding: 0.6rem 0.75rem;
		font-weight: 400;
		text-align: left;
	}
	.icon,
	.thumb {
		width: 2.5rem;
		height: 2.5rem;
		flex: none;
		display: grid;
		place-items: center;
		font-size: 1.5rem;
		border-radius: 6px;
		object-fit: cover;
	}
	.meta {
		display: grid;
		min-width: 0;
	}
	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.more {
		margin-right: 0.5rem;
		padding: 0.3rem 0.7rem;
	}
	.menu {
		position: absolute;
		right: 0.5rem;
		top: 100%;
		z-index: 5;
		display: grid;
		gap: 0.25rem;
		padding: 0.5rem;
		min-width: 12rem;
		box-shadow: 0 6px 20px rgb(0 0 0 / 0.15);
	}
	.menu a {
		padding: 0.2rem 0.3rem;
		text-decoration: none;
		font-weight: 500;
	}
	.uploads {
		display: grid;
		gap: 0.4rem;
		padding: 0.75rem;
	}
	.uploads li {
		display: grid;
		grid-template-columns: 1fr 6rem 3rem;
		gap: 0.5rem;
		align-items: center;
	}
	.uploads progress {
		width: 100%;
		accent-color: var(--accent);
	}
	.empty {
		text-align: center;
	}
	.usage {
		text-align: right;
	}
	.viewer {
		position: fixed;
		inset: 0;
		z-index: 20;
		display: grid;
		grid-template-rows: auto 1fr;
		background: rgb(0 0 0 / 0.92);
		color: #fff;
	}
	.viewer-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 16px;
	}
	.viewer-bar .name {
		flex: 1;
	}
	.viewer-bar .ghost,
	.viewer .nav {
		color: #fff;
		border-color: rgb(255 255 255 / 0.3);
	}
	.button {
		padding: 0.6rem 1rem;
		border-radius: 8px;
		text-decoration: none;
		border: 1px solid;
	}
	.viewer-body {
		position: relative;
		display: grid;
		place-items: center;
		min-height: 0;
		padding: 0 16px 16px;
	}
	.viewer-body img,
	.viewer-body video {
		max-width: 100%;
		max-height: 100%;
		object-fit: contain;
	}
	.nav {
		position: absolute;
		top: 50%;
		transform: translateY(-50%);
		font-size: 1.6rem;
		background: rgb(0 0 0 / 0.4);
	}
	.prev {
		left: 16px;
	}
	.next {
		right: 16px;
	}
</style>

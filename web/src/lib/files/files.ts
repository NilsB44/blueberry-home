export type Space = 'shared' | 'home';
export type Kind = 'dir' | 'image' | 'video' | 'audio' | 'pdf' | 'text' | 'other';
export type Entry = { name: string; kind: Kind; size: number; modified: string };
export type Listing = { space: Space; path: string; entries: Entry[] };
export type Usage = { total: number; used: number; free: number; max_upload: number };

export const SPACES: Record<Space, string> = { shared: 'Shared', home: 'My files' };

export const ICONS: Record<Kind, string> = {
	dir: '📁',
	image: '🖼️',
	video: '🎬',
	audio: '🎵',
	pdf: '📄',
	text: '📝',
	other: '📦'
};

export function join(dir: string, name: string): string {
	return dir ? `${dir}/${name}` : name;
}

export function rawUrl(space: Space, path: string, download = false): string {
	const q = new URLSearchParams({ path });
	if (download) q.set('download', 'true');
	return `/api/files/${space}/raw?${q}`;
}

export function bytes(n: number): string {
	if (n < 1024) return `${n} B`;
	const units = ['KB', 'MB', 'GB', 'TB'];
	let v = n / 1024;
	let i = 0;
	while (v >= 1024 && i < units.length - 1) {
		v /= 1024;
		i++;
	}
	return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
}

export type Upload = { id: number; name: string; size: number; sent: number; error: string; done: boolean };

/** PUT one file with progress. fetch() can't report upload progress, XHR can. */
export function uploadFile(
	space: Space,
	dir: string,
	file: File,
	onProgress: (sent: number) => void
): Promise<void> {
	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest();
		const q = new URLSearchParams({ name: file.name, path: dir });
		xhr.open('PUT', `/api/files/${space}/upload?${q}`);
		xhr.withCredentials = true;
		xhr.upload.onprogress = (e) => onProgress(e.loaded);
		xhr.onload = () => {
			if (xhr.status >= 200 && xhr.status < 300) return resolve();
			let message = xhr.statusText || `Upload failed (${xhr.status})`;
			try {
				message = JSON.parse(xhr.responseText).detail ?? message;
			} catch {
				// keep statusText
			}
			reject(new Error(message));
		};
		xhr.onerror = () => reject(new Error('Network error'));
		xhr.send(file);
	});
}

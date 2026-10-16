export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

async function errorFrom(res: Response): Promise<ApiError> {
	let message = res.statusText;
	try {
		const body = await res.json();
		if (typeof body.detail === 'string') message = body.detail;
		else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ');
	} catch {
		// not JSON; keep statusText
	}
	return new ApiError(res.status, message);
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
	const { json, ...rest } = init;
	const res = await fetch(`/api${path}`, {
		...rest,
		credentials: 'same-origin',
		headers: json === undefined ? rest.headers : { 'content-type': 'application/json', ...rest.headers },
		body: json === undefined ? rest.body : JSON.stringify(json)
	});
	if (!res.ok) throw await errorFrom(res);
	if (res.status === 204) return undefined as T;
	return res.json() as Promise<T>;
}

/** POST and yield the response body as text chunks while it streams in. */
export async function* streamText(path: string, json: unknown, signal?: AbortSignal) {
	const res = await fetch(`/api${path}`, {
		method: 'POST',
		credentials: 'same-origin',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(json),
		signal
	});
	if (!res.ok || !res.body) throw await errorFrom(res);
	const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
	while (true) {
		const { done, value } = await reader.read();
		if (done) return;
		yield value;
	}
}

export type User = {
	id: number;
	username: string;
	display_name: string;
	is_admin: boolean;
	device: string | null;
	has_password: boolean;
};

export type ModuleInfo = {
	id: string;
	name: string;
	description: string;
	icon: string;
	path: string;
	status: 'ready' | 'planned';
	phase: number;
};

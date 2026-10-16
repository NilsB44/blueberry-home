export type Internet = {
	up: boolean | null;
	latency_ms: number | null;
	checked_at: string | null;
	down_since: string | null;
	uptime_24h: number | null;
	uptime_7d: number | null;
	outages_7d: number;
};

export type SpeedTest = {
	at: string;
	trigger: 'scheduled' | 'manual';
	ping_ms: number | null;
	down_mbps: number | null;
	up_mbps: number | null;
	error: string;
};

export type Health = {
	status: 'ok' | 'warn' | 'fail';
	notes: string[];
	uptime_seconds: number | null;
	temperature_c: number | null;
	load: number[] | null;
	cpus: number;
	memory_total_bytes: number | null;
	memory_available_bytes: number | null;
	disks: { label: string; total_bytes: number; free_bytes: number }[];
	throttled_now: string[];
	throttled_since_boot: string[];
};

export type ScanInfo = {
	at: string | null;
	network: string;
	gateway: string;
	stale: boolean;
	online: number;
	new_devices: number | null;
};

export type Overview = {
	internet: Internet;
	speed: SpeedTest | null;
	health: Health;
	scan: ScanInfo;
	refused_7d: number | null;
};

export type Hour = {
	hour: string;
	uptime: number | null;
	latency_ms: number | null;
	latency_ms_max: number | null;
};

export type Outage = { started_at: string; ended_at: string | null; minutes: number };

export type History = { hours: Hour[]; outages: Outage[]; speedtests: SpeedTest[] };

export type Device = {
	mac: string;
	ip: string;
	hostname: string;
	name: string;
	first_seen: string;
	last_seen: string;
	known: boolean;
	online: boolean;
	is_pi: boolean;
	is_gateway: boolean;
	private_mac: boolean;
};

export function deviceName(d: Device): string {
	if (d.name) return d.name;
	if (d.is_pi) return 'This Pi (the hub)';
	if (d.is_gateway) return d.hostname ? `Router (${d.hostname})` : 'Router';
	return d.hostname || 'Unnamed device';
}

export function bytes(n: number): string {
	const units = ['B', 'KB', 'MB', 'GB', 'TB'];
	let i = 0;
	while (n >= 1000 && i < units.length - 1) {
		n /= 1000;
		i++;
	}
	return `${n >= 100 || i === 0 ? n.toFixed(0) : n.toFixed(1)} ${units[i]}`;
}

export function duration(seconds: number): string {
	const d = Math.floor(seconds / 86400);
	const h = Math.floor((seconds % 86400) / 3600);
	const m = Math.floor((seconds % 3600) / 60);
	if (d) return `${d} d ${h} h`;
	if (h) return `${h} h ${m} min`;
	return `${m} min`;
}

export function percent(x: number | null): string {
	if (x === null) return '–';
	return x === 1 ? '100%' : `${(x * 100).toFixed(x > 0.99 ? 2 : 1)}%`;
}

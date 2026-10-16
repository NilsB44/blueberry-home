export type CheckStatus = 'ok' | 'warn' | 'fail' | 'unknown';

export type Check = {
	id: string;
	group: 'hub' | 'pi';
	title: string;
	status: CheckStatus;
	summary: string;
	details: string[];
};

export type Report = {
	id: number;
	started_at: string;
	finished_at: string | null;
	trigger: 'scheduled' | 'manual';
	status: CheckStatus;
	checks: Check[];
};

export type ReportSummary = {
	id: number;
	started_at: string;
	trigger: string;
	status: CheckStatus;
	counts: Partial<Record<CheckStatus, number>>;
};

export type Schedule = { next_run_at: string; latest: Report | null };

export type AwayAccess = {
	enabled: boolean;
	networks: string[];
	changed_at: string | null;
	changed_by: string | null;
	expires_at: string | null;
	durations: number[];
	can_enable: boolean;
};

export type SecurityEvent = {
	at: string;
	action: string;
	detail: string;
	who: string | null;
	ip: string | null;
};

export type DeviceSession = {
	id: string;
	user: string;
	username: string;
	device: string | null;
	is_owner: boolean;
	signed_in_at: string;
	last_seen_at: string | null;
	last_ip: string | null;
	this_device: boolean;
};

export const EVENT_LABEL: Record<string, string> = {
	'away-on': 'Away access turned on',
	'away-off': 'Away access turned off',
	'away-expired': 'Away access ran out',
	'signed-out': 'Device signed out',
	lockout: 'Logins paused',
	owner: 'Owner changed',
	check: 'Check run'
};

export function duration(hours: number): string {
	if (hours < 24) return `${hours} hours`;
	const days = hours / 24;
	return days === 1 ? '1 day' : `${days} days`;
}

export type Attempt = {
	kind: 'blocked' | 'login' | 'away';
	ip: string;
	day: string;
	count: number;
	detail: string;
	last_seen: string;
	from_internet: boolean;
};

export const STATUS_LABEL: Record<CheckStatus, string> = {
	ok: 'All good',
	warn: 'Worth a look',
	fail: 'Needs fixing',
	unknown: "Couldn't check"
};

/** The API sends UTC timestamps; SQLite may drop the zone, so add it back before parsing. */
export function when(iso: string): string {
	const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
	return d.toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

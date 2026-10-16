// Tetris rules, independent of the screen: the 7-bag randomiser, SRS rotation with wall kicks,
// hold, ghost, lock delay, garbage lines and power-ups. Everything random comes from seeded
// generators, so every player in a room gets the same pieces.

export const COLS = 10;
export const ROWS = 22; // the top two rows are hidden above the board
export const HIDDEN = 2;
export const GARBAGE = 8;
const POWER_BIT = 16;

export type Kind = 'I' | 'J' | 'L' | 'O' | 'S' | 'T' | 'Z';
export const KINDS: Kind[] = ['I', 'J', 'L', 'O', 'S', 'T', 'Z'];
export const COLOR_INDEX: Record<Kind, number> = { I: 1, J: 2, L: 3, O: 4, S: 5, T: 6, Z: 7 };

export type Power = 'bomb' | 'slow' | 'line' | 'shield' | 'rush';
export const POWERS: Record<Power, { icon: string; name: string; text: string }> = {
	bomb: { icon: '💣', name: 'Bomb', text: 'Clears your bottom two rows' },
	slow: { icon: '🐢', name: 'Slow-mo', text: 'Your pieces fall at half speed for 15 seconds' },
	line: { icon: '📏', name: 'Long bar', text: 'Your next piece is a long bar' },
	shield: { icon: '🛡️', name: 'Shield', text: 'Blocks the next garbage sent your way' },
	rush: { icon: '⚡', name: 'Rush', text: "Everyone else's pieces fall twice as fast for 10 seconds" }
};
const SOLO_POWERS: Power[] = ['bomb', 'slow', 'line'];
const MULTI_POWERS: Power[] = ['bomb', 'slow', 'line', 'shield', 'rush'];
export const MAX_POWERS = 2;
// About one piece in eight carries a power-up star; clear its row to collect it.
const POWER_CHANCE = 1 / 8;
const SLOW_MS = 15_000;
const RUSH_MS = 10_000;

const LOCK_DELAY = 500;
const MAX_LOCK_RESETS = 15;

// Spawn shapes, in an n×n box; rotating the box gives the SRS rotation states.
const SHAPES: Record<Kind, string[]> = {
	I: ['....', 'IIII', '....', '....'],
	J: ['J..', 'JJJ', '...'],
	L: ['..L', 'LLL', '...'],
	O: ['OO', 'OO'],
	S: ['.SS', 'SS.', '...'],
	T: ['.T.', 'TTT', '...'],
	Z: ['ZZ.', '.ZZ', '...']
};

type Cell = [number, number];

function rotations(kind: Kind): Cell[][] {
	const rows = SHAPES[kind];
	const n = rows.length;
	let cells: Cell[] = [];
	rows.forEach((row, y) => [...row].forEach((c, x) => c !== '.' && cells.push([x, y])));
	const out: Cell[][] = [];
	for (let r = 0; r < 4; r++) {
		out.push(cells);
		cells = cells.map(([x, y]) => [n - 1 - y, x]); // clockwise
	}
	return out;
}
const CELLS = Object.fromEntries(KINDS.map((k) => [k, rotations(k)])) as Record<Kind, Cell[][]>;

// SRS wall kicks, written y-up as in the guideline; they're flipped to y-down when used.
const KICKS: Record<string, Cell[]> = {
	'01': [[0, 0], [-1, 0], [-1, 1], [0, -2], [-1, -2]],
	'10': [[0, 0], [1, 0], [1, -1], [0, 2], [1, 2]],
	'12': [[0, 0], [1, 0], [1, -1], [0, 2], [1, 2]],
	'21': [[0, 0], [-1, 0], [-1, 1], [0, -2], [-1, -2]],
	'23': [[0, 0], [1, 0], [1, 1], [0, -2], [1, -2]],
	'32': [[0, 0], [-1, 0], [-1, -1], [0, 2], [-1, 2]],
	'30': [[0, 0], [-1, 0], [-1, -1], [0, 2], [-1, 2]],
	'03': [[0, 0], [1, 0], [1, 1], [0, -2], [1, -2]]
};
const I_KICKS: Record<string, Cell[]> = {
	'01': [[0, 0], [-2, 0], [1, 0], [-2, -1], [1, 2]],
	'10': [[0, 0], [2, 0], [-1, 0], [2, 1], [-1, -2]],
	'12': [[0, 0], [-1, 0], [2, 0], [-1, 2], [2, -1]],
	'21': [[0, 0], [1, 0], [-2, 0], [1, -2], [-2, 1]],
	'23': [[0, 0], [2, 0], [-1, 0], [2, 1], [-1, -2]],
	'32': [[0, 0], [-2, 0], [1, 0], [-2, -1], [1, 2]],
	'30': [[0, 0], [1, 0], [-2, 0], [1, -2], [-2, 1]],
	'03': [[0, 0], [-1, 0], [2, 0], [-1, 2], [2, -1]]
};

/** mulberry32: small, fast and good enough for shuffling pieces. */
export function rng(seed: number) {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

export type Piece = { kind: Kind; rot: number; x: number; y: number; power: number };

export type Events = {
	/** Lines cleared by a lock; `sent` is how many garbage lines that attack is worth. */
	clear?: (lines: number, sent: number) => void;
	power?: (power: Power) => void;
	over?: () => void;
};

const LINE_SCORES = [0, 100, 300, 500, 800];
const LINE_ATTACK = [0, 0, 1, 2, 4];

export class Game {
	board = new Uint8Array(COLS * ROWS);
	piece: Piece | null = null;
	queue: Kind[] = [];
	hold: Kind | null = null;
	holdUsed = false;
	score = 0;
	lines = 0;
	combo = -1;
	backToBack = false;
	powers: Power[] = [];
	incoming: number[] = []; // garbage waiting to rise, oldest first
	shield = false;
	slowUntil = 0;
	rushUntil = 0;
	over = false;
	softDrop = false;
	clock = 0; // ms of play
	/** Bumped whenever something visible changes, so the screen knows to redraw. */
	version = 0;

	private bag: () => number;
	private luck: () => number;
	private bagLeft: Kind[] = [];
	private fall = 0;
	private lockTimer = 0;
	private lockResets = 0;
	private lowest = 0;
	private powerPool: Power[];
	private events: Events;
	readonly multiplayer: boolean;

	constructor(seed: number, multiplayer = false, events: Events = {}) {
		this.multiplayer = multiplayer;
		this.events = events;
		this.bag = rng(seed);
		this.luck = rng(seed ^ 0x5bd1e995);
		this.powerPool = multiplayer ? MULTI_POWERS : SOLO_POWERS;
		this.fillQueue();
		this.spawn();
	}

	get level() {
		return Math.min(20, 1 + Math.floor(this.lines / 10));
	}

	/** Seconds per row at the current level (the guideline curve), with power-ups applied. */
	get fallInterval() {
		let s = Math.pow(0.8 - (this.level - 1) * 0.007, this.level - 1);
		if (this.clock < this.slowUntil) s *= 2;
		if (this.clock < this.rushUntil) s /= 2;
		if (this.softDrop) s = Math.min(s / 20, 0.05);
		return s * 1000;
	}

	cell(x: number, y: number) {
		return this.board[y * COLS + x];
	}

	cells(p: Piece = this.piece!): Cell[] {
		return CELLS[p.kind][p.rot].map(([x, y]) => [x + p.x, y + p.y]);
	}

	fits(p: Piece) {
		return this.cells(p).every(
			([x, y]) => x >= 0 && x < COLS && y >= 0 && y < ROWS && this.cell(x, y) === 0
		);
	}

	ghost(): Piece | null {
		if (!this.piece) return null;
		const g = { ...this.piece };
		while (this.fits({ ...g, y: g.y + 1 })) g.y++;
		return g;
	}

	// --- player actions --------------------------------------------------------------------

	move(dx: number) {
		if (!this.piece || this.over) return false;
		const next = { ...this.piece, x: this.piece.x + dx };
		if (!this.fits(next)) return false;
		this.piece = next;
		this.moved();
		return true;
	}

	rotate(dir: 1 | -1) {
		if (!this.piece || this.over || this.piece.kind === 'O') return false;
		const from = this.piece.rot;
		const to = (from + dir + 4) % 4;
		const kicks = (this.piece.kind === 'I' ? I_KICKS : KICKS)[`${from}${to}`];
		for (const [kx, ky] of kicks) {
			const next = { ...this.piece, rot: to, x: this.piece.x + kx, y: this.piece.y - ky };
			if (this.fits(next)) {
				this.piece = next;
				this.moved();
				return true;
			}
		}
		return false;
	}

	/** Move down one row; true if it moved. */
	drop() {
		if (!this.piece || this.over) return false;
		const next = { ...this.piece, y: this.piece.y + 1 };
		if (!this.fits(next)) return false;
		this.piece = next;
		this.fall = 0;
		if (next.y > this.lowest) {
			this.lowest = next.y;
			this.lockResets = 0;
			this.lockTimer = 0;
		}
		this.version++;
		return true;
	}

	hardDrop() {
		if (!this.piece || this.over) return;
		let rows = 0;
		while (this.drop()) rows++;
		this.score += rows * 2;
		this.lock();
	}

	holdPiece() {
		if (!this.piece || this.over || this.holdUsed) return;
		const current = this.piece.kind;
		if (this.hold) this.queue.unshift(this.hold);
		this.hold = current;
		this.holdUsed = true;
		this.spawn();
	}

	usePower(): Power | null {
		if (this.over || this.powers.length === 0) return null;
		const power = this.powers.shift()!;
		if (power === 'bomb') {
			// Drop the bottom two rows; if an overhang lands on the falling piece, lift it clear.
			this.board.copyWithin(2 * COLS, 0, (ROWS - 2) * COLS);
			this.board.fill(0, 0, 2 * COLS);
			while (this.piece && !this.fits(this.piece) && this.piece.y > 0) this.piece.y--;
		} else if (power === 'slow') {
			this.slowUntil = this.clock + SLOW_MS;
		} else if (power === 'line') {
			this.queue.unshift('I');
		} else if (power === 'shield') {
			this.shield = true;
		}
		// 'rush' only affects the others; the room passes it on.
		this.version++;
		return power;
	}

	// --- things that happen to the player -----------------------------------------------------

	/** Garbage from an opponent; it rises after your next piece locks unless you clear lines first. */
	addGarbage(lines: number) {
		if (this.over || lines <= 0) return false;
		if (this.shield) {
			this.shield = false;
			this.version++;
			return false;
		}
		this.incoming.push(lines);
		this.version++;
		return true;
	}

	rush() {
		this.rushUntil = this.clock + RUSH_MS;
	}

	/** Advance time by `dt` ms: gravity and lock delay. */
	tick(dt: number) {
		if (this.over || !this.piece) return;
		this.clock += dt;
		const grounded = !this.fits({ ...this.piece, y: this.piece.y + 1 });
		if (grounded) {
			this.lockTimer += dt;
			if (this.lockTimer >= LOCK_DELAY) this.lock();
			return;
		}
		this.fall += dt;
		const interval = this.fallInterval;
		while (this.fall >= interval && this.piece) {
			this.fall -= interval;
			if (!this.drop()) break;
			if (this.softDrop) this.score += 1;
		}
	}

	/** The visible board with the falling piece, one digit per cell, for opponents' screens. */
	snapshot() {
		const out = Array.from(this.board.subarray(HIDDEN * COLS), (v) => v & 15);
		if (this.piece) {
			for (const [x, y] of this.cells()) {
				if (y >= HIDDEN) out[(y - HIDDEN) * COLS + x] = COLOR_INDEX[this.piece.kind];
			}
		}
		return out.join('');
	}

	// --- internals ---------------------------------------------------------------------------

	private moved() {
		this.version++;
		if (this.piece && !this.fits({ ...this.piece, y: this.piece.y + 1 })) {
			if (this.lockResets < MAX_LOCK_RESETS) {
				this.lockResets++;
				this.lockTimer = 0;
			}
		}
	}

	private fillQueue() {
		while (this.queue.length < 6) {
			if (this.bagLeft.length === 0) {
				this.bagLeft = [...KINDS];
				for (let i = this.bagLeft.length - 1; i > 0; i--) {
					const j = Math.floor(this.bag() * (i + 1));
					[this.bagLeft[i], this.bagLeft[j]] = [this.bagLeft[j], this.bagLeft[i]];
				}
			}
			this.queue.push(this.bagLeft.shift()!);
		}
	}

	private spawn() {
		const kind = this.queue.shift()!;
		this.fillQueue();
		const width = SHAPES[kind].length;
		const power = this.luck() < POWER_CHANCE ? Math.floor(this.luck() * 4) : -1;
		// Every shape's lowest row starts on the top visible row.
		const piece: Piece = { kind, rot: 0, x: Math.floor((COLS - width) / 2), y: 1, power };
		this.fall = 0;
		this.lockTimer = 0;
		this.lockResets = 0;
		this.lowest = piece.y;
		if (!this.fits(piece)) {
			this.piece = piece;
			this.end();
			return;
		}
		this.piece = piece;
		this.version++;
	}

	private lock() {
		const p = this.piece!;
		const cells = this.cells(p);
		cells.forEach(([x, y], i) => {
			this.board[y * COLS + x] = COLOR_INDEX[p.kind] | (i === p.power ? POWER_BIT : 0);
		});
		this.piece = null;
		this.holdUsed = false;

		// Locked entirely above the board: topped out.
		if (cells.every(([, y]) => y < HIDDEN)) {
			this.end();
			return;
		}

		const full: number[] = [];
		for (let y = 0; y < ROWS; y++) {
			let filled = true;
			for (let x = 0; x < COLS; x++) if (this.cell(x, y) === 0) filled = false;
			if (filled) full.push(y);
		}
		const cleared = full.length;
		if (cleared) {
			let found = 0;
			for (const y of full) {
				for (let x = 0; x < COLS; x++) if (this.cell(x, y) & POWER_BIT) found++;
				this.board.copyWithin(COLS, 0, y * COLS);
				this.board.fill(0, 0, COLS);
			}
			this.combo++;
			const tetris = cleared === 4;
			const bonus = tetris && this.backToBack ? 1.5 : 1;
			this.score += Math.round(LINE_SCORES[cleared] * this.level * bonus) + 50 * this.combo * this.level;
			this.lines += cleared;
			let sent = LINE_ATTACK[cleared] + (tetris && this.backToBack ? 1 : 0) + Math.floor(this.combo / 2);
			this.backToBack = tetris;
			// Your own clears cancel garbage that's on its way before any goes out.
			while (sent > 0 && this.incoming.length) {
				const use = Math.min(sent, this.incoming[0]);
				sent -= use;
				this.incoming[0] -= use;
				if (this.incoming[0] === 0) this.incoming.shift();
			}
			for (let i = 0; i < found; i++) this.grantPower();
			this.events.clear?.(cleared, sent);
		} else {
			this.combo = -1;
			this.riseGarbage();
		}
		this.version++;
		if (!this.over) this.spawn();
	}

	private grantPower() {
		if (this.powers.length >= MAX_POWERS) {
			this.score += 100 * this.level;
			return;
		}
		const power = this.powerPool[Math.floor(this.luck() * this.powerPool.length)];
		this.powers.push(power);
		this.events.power?.(power);
	}

	private riseGarbage() {
		let total = 0;
		while (this.incoming.length && total < 8) total += this.incoming.shift()!;
		total = Math.min(total, ROWS);
		if (!total) return;
		// Garbage arrives as rows with one gap, in the same column for each attack.
		const hole = Math.floor(Math.random() * COLS);
		for (let y = 0; y < total; y++) {
			if (this.board.subarray(y * COLS, (y + 1) * COLS).some((v) => v !== 0)) {
				this.end();
				return;
			}
		}
		this.board.copyWithin(0, total * COLS);
		for (let y = ROWS - total; y < ROWS; y++) {
			for (let x = 0; x < COLS; x++) this.board[y * COLS + x] = x === hole ? 0 : GARBAGE;
		}
	}

	private end() {
		this.over = true;
		this.version++;
		this.events.over?.();
	}

	isPower(x: number, y: number) {
		return (this.cell(x, y) & POWER_BIT) !== 0;
	}
}

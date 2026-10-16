import { COLOR_INDEX, COLS, HIDDEN, ROWS, type Game, type Kind } from './game.ts';

// Index 0 is empty, 1–7 the pieces (I J L O S T Z), 8 garbage.
export const COLORS = ['', '#2ec4e6', '#3d6fe0', '#f08c2e', '#f2c94c', '#45c46a', '#a45bd9', '#e5484d', '#7c828c'];
const VISIBLE = ROWS - HIDDEN;

/** Size a canvas for crisp drawing on high-density screens; returns its 2D context. */
export function fit(canvas: HTMLCanvasElement, width: number, height: number) {
	const dpr = window.devicePixelRatio || 1;
	canvas.width = Math.round(width * dpr);
	canvas.height = Math.round(height * dpr);
	canvas.style.width = `${width}px`;
	canvas.style.height = `${height}px`;
	const ctx = canvas.getContext('2d')!;
	ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
	return ctx;
}

function block(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, color: string) {
	const gap = size > 10 ? 1 : 0.5;
	ctx.fillStyle = color;
	ctx.fillRect(x + gap, y + gap, size - 2 * gap, size - 2 * gap);
	if (size > 10) {
		// A soft highlight on the top edge so blocks read as blocks.
		ctx.fillStyle = 'rgba(255,255,255,0.22)';
		ctx.fillRect(x + gap, y + gap, size - 2 * gap, Math.max(2, size * 0.14));
	}
}

function star(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, t: number) {
	const cx = x + size / 2;
	const cy = y + size / 2;
	const r = size * (0.3 + 0.05 * Math.sin(t / 150));
	ctx.save();
	ctx.fillStyle = '#fff';
	ctx.shadowColor = '#fff6a8';
	ctx.shadowBlur = size * 0.5;
	ctx.beginPath();
	for (let i = 0; i < 8; i++) {
		const a = (i * Math.PI) / 4 - Math.PI / 2;
		const rr = i % 2 === 0 ? r : r * 0.4;
		ctx.lineTo(cx + rr * Math.cos(a), cy + rr * Math.sin(a));
	}
	ctx.closePath();
	ctx.fill();
	ctx.restore();
}

export function drawBoard(ctx: CanvasRenderingContext2D, game: Game, cell: number, dark: boolean, now: number) {
	const w = COLS * cell;
	const h = VISIBLE * cell;
	ctx.clearRect(0, 0, w, h);
	ctx.fillStyle = dark ? '#0f1115' : '#1b1f27';
	ctx.fillRect(0, 0, w, h);
	ctx.strokeStyle = 'rgba(255,255,255,0.05)';
	ctx.lineWidth = 1;
	ctx.beginPath();
	for (let x = 1; x < COLS; x++) {
		ctx.moveTo(x * cell + 0.5, 0);
		ctx.lineTo(x * cell + 0.5, h);
	}
	for (let y = 1; y < VISIBLE; y++) {
		ctx.moveTo(0, y * cell + 0.5);
		ctx.lineTo(w, y * cell + 0.5);
	}
	ctx.stroke();

	for (let y = HIDDEN; y < ROWS; y++) {
		for (let x = 0; x < COLS; x++) {
			const v = game.cell(x, y) & 15;
			if (!v) continue;
			block(ctx, x * cell, (y - HIDDEN) * cell, cell, COLORS[v]);
			if (game.isPower(x, y)) star(ctx, x * cell, (y - HIDDEN) * cell, cell, now);
		}
	}

	const piece = game.piece;
	if (piece && !game.over) {
		const color = COLORS[COLOR_INDEX[piece.kind]];
		const ghost = game.ghost();
		if (ghost && ghost.y !== piece.y) {
			ctx.globalAlpha = 0.25;
			for (const [x, y] of game.cells(ghost)) {
				if (y >= HIDDEN) block(ctx, x * cell, (y - HIDDEN) * cell, cell, color);
			}
			ctx.globalAlpha = 1;
		}
		game.cells(piece).forEach(([x, y], i) => {
			if (y < HIDDEN) return;
			block(ctx, x * cell, (y - HIDDEN) * cell, cell, color);
			if (i === piece.power) star(ctx, x * cell, (y - HIDDEN) * cell, cell, now);
		});
	}

	if (game.over) {
		ctx.fillStyle = 'rgba(0,0,0,0.55)';
		ctx.fillRect(0, 0, w, h);
	}
}

/** An opponent's board from the digits they send. */
export function drawMini(ctx: CanvasRenderingContext2D, board: string, cell: number, out: boolean) {
	const w = COLS * cell;
	const h = VISIBLE * cell;
	ctx.clearRect(0, 0, w, h);
	ctx.fillStyle = '#1b1f27';
	ctx.fillRect(0, 0, w, h);
	for (let i = 0; i < board.length && i < COLS * VISIBLE; i++) {
		const v = board.charCodeAt(i) - 48;
		if (v > 0 && v < COLORS.length) block(ctx, (i % COLS) * cell, Math.floor(i / COLS) * cell, cell, COLORS[v]);
	}
	if (out) {
		ctx.fillStyle = 'rgba(0,0,0,0.6)';
		ctx.fillRect(0, 0, w, h);
	}
}

const PREVIEW: Record<Kind, [number, number][]> = {
	I: [[0, 0], [1, 0], [2, 0], [3, 0]],
	J: [[0, 0], [0, 1], [1, 1], [2, 1]],
	L: [[2, 0], [0, 1], [1, 1], [2, 1]],
	O: [[0, 0], [1, 0], [0, 1], [1, 1]],
	S: [[1, 0], [2, 0], [0, 1], [1, 1]],
	T: [[1, 0], [0, 1], [1, 1], [2, 1]],
	Z: [[0, 0], [1, 0], [1, 1], [2, 1]]
};

/** A piece centred in a 4×2-cell box, for hold and next. */
export function drawPreview(ctx: CanvasRenderingContext2D, kind: Kind | null, cell: number, dim = false) {
	ctx.clearRect(0, 0, 4 * cell, 2 * cell);
	if (!kind) return;
	const cells = PREVIEW[kind];
	const width = Math.max(...cells.map(([x]) => x)) + 1;
	const height = Math.max(...cells.map(([, y]) => y)) + 1;
	const ox = ((4 - width) * cell) / 2;
	const oy = ((2 - height) * cell) / 2;
	ctx.globalAlpha = dim ? 0.35 : 1;
	for (const [x, y] of cells) block(ctx, ox + x * cell, oy + y * cell, cell, COLORS[COLOR_INDEX[kind]]);
	ctx.globalAlpha = 1;
}

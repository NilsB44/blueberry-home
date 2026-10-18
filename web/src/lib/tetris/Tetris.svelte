<script lang="ts">
	import { onMount } from 'svelte';
	import { drawBoard, drawPreview, fit } from './draw.ts';
	import { COLS, Game, HIDDEN, MAX_POWERS, POWERS, ROWS, type Power } from './game.ts';
	import { isDark } from '#lib/theme.svelte.ts';

	type Result = { score: number; lines: number; level: number };

	let {
		seed,
		multiplayer = false,
		running = true,
		onstate,
		onattack,
		onpower,
		onover
	}: {
		seed: number;
		multiplayer?: boolean;
		/** False before the countdown ends; the board shows but nothing moves. */
		running?: boolean;
		onstate?: (board: string, score: number, lines: number) => void;
		onattack?: (lines: number) => void;
		onpower?: (power: Power) => void;
		onover?: (result: Result) => void;
	} = $props();

	const DAS = 160; // ms before a held direction starts repeating
	const ARR = 45; // ms between repeats

	// svelte-ignore state_referenced_locally
	const game = new Game(seed, multiplayer, {
		clear: (_, sent) => {
			if (sent > 0) onattack?.(sent);
		},
		power: (p) => toast(`${POWERS[p].icon} ${POWERS[p].name}! Tap ✦ to use it`),
		over: () => onover?.({ score: game.score, lines: game.lines, level: game.level })
	});

	let ui = $state(read());
	let paused = $state(false);
	let notices = $state<{ id: number; text: string }[]>([]);
	let cell = $state(24);
	let play: HTMLDivElement;
	let board: HTMLCanvasElement;
	let holdCanvas: HTMLCanvasElement;
	let nextCanvases: HTMLCanvasElement[] = $state([]);

	function read() {
		return {
			score: game.score,
			lines: game.lines,
			level: game.level,
			hold: game.hold,
			holdUsed: game.holdUsed,
			next: game.queue.slice(0, 3),
			powers: [...game.powers],
			incoming: game.incoming.reduce((a, b) => a + b, 0),
			shield: game.shield,
			slow: game.clock < game.slowUntil,
			rush: game.clock < game.rushUntil,
			over: game.over
		};
	}

	let noticeId = 0;
	function toast(text: string) {
		const id = ++noticeId;
		notices = [...notices.slice(-2), { id, text }];
		setTimeout(() => (notices = notices.filter((n) => n.id !== id)), 2600);
	}

	/** Garbage lines from an opponent. */
	export function garbage(lines: number, from: string) {
		if (game.addGarbage(lines)) toast(`${from} sent ${lines} line${lines > 1 ? 's' : ''}`);
		else if (!game.over) toast(`🛡️ Your shield blocked ${from}'s ${lines} line${lines > 1 ? 's' : ''}`);
	}

	/** A power-up an opponent used on you. */
	export function power(kind: Power, from: string) {
		if (kind === 'rush' && !game.over) {
			game.rush();
			toast(`⚡ ${from} rushed you!`);
		}
	}

	function usePower() {
		const p = game.usePower();
		if (!p) return;
		toast(`${POWERS[p].icon} ${POWERS[p].text}`);
		onpower?.(p);
	}

	const active = () => running && !paused && !game.over;

	// --- keyboard and buttons ----------------------------------------------------------------

	let dir = 0; // -1 left, 1 right, 0 none
	let dirHeld = 0;
	let dirRepeat = 0;

	function startMove(d: -1 | 1) {
		if (!active()) return;
		dir = d;
		dirHeld = 0;
		dirRepeat = 0;
		game.move(d);
	}
	function stopMove(d: -1 | 1) {
		if (dir === d) dir = 0;
	}

	type Action = 'left' | 'right' | 'soft' | 'hard' | 'cw' | 'ccw' | 'hold' | 'power';

	function press(a: Action) {
		if (!active()) return;
		if (a === 'left') startMove(-1);
		else if (a === 'right') startMove(1);
		else if (a === 'soft') game.softDrop = true;
		else if (a === 'hard') game.hardDrop();
		else if (a === 'cw') game.rotate(1);
		else if (a === 'ccw') game.rotate(-1);
		else if (a === 'hold') game.holdPiece();
		else if (a === 'power') usePower();
	}
	function release(a: Action) {
		if (a === 'left') stopMove(-1);
		else if (a === 'right') stopMove(1);
		else if (a === 'soft') game.softDrop = false;
	}

	const KEYS: Record<string, Action> = {
		ArrowLeft: 'left',
		ArrowRight: 'right',
		ArrowDown: 'soft',
		' ': 'hard',
		ArrowUp: 'cw',
		x: 'cw',
		X: 'cw',
		z: 'ccw',
		Z: 'ccw',
		Control: 'ccw',
		c: 'hold',
		C: 'hold',
		Shift: 'hold',
		e: 'power',
		E: 'power'
	};

	function keydown(e: KeyboardEvent) {
		if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
		if ((e.key === 'p' || e.key === 'P' || e.key === 'Escape') && !multiplayer) {
			paused = !paused;
			e.preventDefault();
			return;
		}
		const a = KEYS[e.key];
		if (!a) return;
		e.preventDefault();
		if (e.repeat) return; // we do our own repeating
		press(a);
	}
	function keyup(e: KeyboardEvent) {
		const a = KEYS[e.key];
		if (a) release(a);
	}

	// --- touch gestures on the board: drag to move, tap to rotate, flick down to drop ---------

	let gesture: { id: number; x0: number; y0: number; x: number; y: number; t0: number; moved: boolean } | null =
		null;

	function pointerdown(e: PointerEvent) {
		if (e.pointerType === 'mouse' || !active()) return;
		board.setPointerCapture(e.pointerId);
		gesture = { id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, t0: performance.now(), moved: false };
	}
	function pointermove(e: PointerEvent) {
		if (!gesture || e.pointerId !== gesture.id || !active()) return;
		const step = cell * 0.9;
		while (e.clientX - gesture.x >= step) {
			game.move(1);
			gesture.x += step;
			gesture.moved = true;
		}
		while (gesture.x - e.clientX >= step) {
			game.move(-1);
			gesture.x -= step;
			gesture.moved = true;
		}
		// A slow drag down is a soft drop, row by row.
		while (e.clientY - gesture.y >= step && performance.now() - gesture.t0 > 200) {
			if (game.drop()) game.score += 1;
			gesture.y += step;
			gesture.moved = true;
		}
	}
	function pointerup(e: PointerEvent) {
		if (!gesture || e.pointerId !== gesture.id) return;
		const dt = performance.now() - gesture.t0;
		const dy = e.clientY - gesture.y0;
		const dx = e.clientX - gesture.x0;
		if (active()) {
			if (dy > cell * 2.5 && dt < 300 && Math.abs(dy) > Math.abs(dx)) game.hardDrop();
			else if (dy < -cell * 2 && dt < 300) game.holdPiece();
			else if (!gesture.moved && Math.hypot(dx, dy) < 12 && dt < 300) {
				const rect = board.getBoundingClientRect();
				game.rotate(e.clientX < rect.left + rect.width / 2 ? -1 : 1);
			}
		}
		gesture = null;
	}

	/** A pad button that repeats while held, like a key. */
	function hold(node: HTMLElement, a: Action) {
		const down = (e: PointerEvent) => {
			e.preventDefault();
			node.setPointerCapture(e.pointerId);
			node.classList.add('down');
			press(a);
		};
		const up = () => {
			node.classList.remove('down');
			release(a);
		};
		node.addEventListener('pointerdown', down);
		node.addEventListener('pointerup', up);
		node.addEventListener('pointercancel', up);
		node.addEventListener('contextmenu', (e) => e.preventDefault());
		return {
			destroy() {
				node.removeEventListener('pointerdown', down);
				node.removeEventListener('pointerup', up);
				node.removeEventListener('pointercancel', up);
			}
		};
	}

	// --- the loop -----------------------------------------------------------------------------

	onMount(() => {
		const dark = isDark();
		let ctx = fit(board, COLS * cell, (ROWS - HIDDEN) * cell);
		let drawnCell = cell;
		let last = performance.now();
		let seen = -1;
		let sentVersion = -1;
		let sentAt = 0;
		let frame = 0;

		const observer = new ResizeObserver(() => {
			const rect = play.getBoundingClientRect();
			// The board is 10 cells wide; the side panels take about 2.6 cells each.
			const byWidth = (rect.width - 24) / 15.2;
			const byHeight = rect.height / (ROWS - HIDDEN);
			cell = Math.max(12, Math.min(36, Math.floor(Math.min(byWidth, byHeight))));
		});
		observer.observe(play);

		const visibility = () => {
			if (document.hidden && !multiplayer && running && !game.over) paused = true;
		};
		document.addEventListener('visibilitychange', visibility);

		const loop = (now: number) => {
			const dt = Math.min(100, now - last);
			last = now;
			if (active()) {
				if (dir !== 0) {
					dirHeld += dt;
					if (dirHeld >= DAS) {
						dirRepeat += dt;
						while (dirRepeat >= ARR) {
							dirRepeat -= ARR;
							if (!game.move(dir)) break;
						}
					}
				}
				game.tick(dt);
			}
			if (drawnCell !== cell) {
				ctx = fit(board, COLS * cell, (ROWS - HIDDEN) * cell);
				drawnCell = cell;
				seen = -1;
			}
			// Power-up stars twinkle, so keep drawing while one is on screen.
			const sparkle = game.piece?.power !== -1 || game.board.some((v) => v & 16);
			if (game.version !== seen || sparkle) {
				drawBoard(ctx, game, cell, dark, now);
			}
			if (game.version !== seen || frame % 15 === 0) {
				seen = game.version;
				ui = read();
			}
			if (onstate && game.version !== sentVersion && now - sentAt > 120) {
				sentVersion = game.version;
				sentAt = now;
				onstate(game.snapshot(), game.score, game.lines);
			}
			frame++;
			raf = requestAnimationFrame(loop);
		};
		let raf = requestAnimationFrame(loop);

		return () => {
			cancelAnimationFrame(raf);
			observer.disconnect();
			document.removeEventListener('visibilitychange', visibility);
		};
	});

	// Previews redraw when what they show changes.
	$effect(() => {
		const size = Math.round(cell * 0.6);
		if (holdCanvas) drawPreview(fit(holdCanvas, 4 * size, 2 * size), ui.hold, size, ui.holdUsed);
		ui.next.forEach((kind, i) => {
			const c = nextCanvases[i];
			if (c) drawPreview(fit(c, 4 * size, 2 * size), kind, size);
		});
	});
</script>

<svelte:window onkeydown={keydown} onkeyup={keyup} onblur={() => ((dir = 0), (game.softDrop = false))} />

<div class="tetris" style="--cell: {cell}px">
	<div class="play" bind:this={play}>
		<aside class="side left">
			<div class="box">
				<span class="label">Hold</span>
				<canvas bind:this={holdCanvas}></canvas>
			</div>
			<div class="box">
				<span class="label">Power</span>
				<div class="powers">
					{#each Array(MAX_POWERS) as _, i}
						<span class="slot" class:full={ui.powers[i]} title={ui.powers[i] ? POWERS[ui.powers[i]].text : ''}>
							{ui.powers[i] ? POWERS[ui.powers[i]].icon : ''}
						</span>
					{/each}
				</div>
			</div>
			<div class="effects">
				{#if ui.shield}<span title="Shield up">🛡️</span>{/if}
				{#if ui.slow}<span title="Slow-mo">🐢</span>{/if}
				{#if ui.rush}<span title="Rushed">⚡</span>{/if}
			</div>
		</aside>

		<div class="well">
			{#if multiplayer}
				<div class="incoming" style="height: {Math.min(20, ui.incoming) * cell}px" title="Garbage on its way"></div>
			{/if}
			<canvas
				bind:this={board}
				class="board"
				onpointerdown={pointerdown}
				onpointermove={pointermove}
				onpointerup={pointerup}
				onpointercancel={() => (gesture = null)}
			></canvas>
			<div class="notices" aria-live="polite">
				{#each notices as n (n.id)}<div class="notice">{n.text}</div>{/each}
			</div>
			{#if paused}
				<div class="overlay">
					<strong>Paused</strong>
					<button onclick={() => (paused = false)}>Resume</button>
				</div>
			{/if}
		</div>

		<aside class="side right">
			<div class="box">
				<span class="label">Next</span>
				{#each ui.next as _, i}<canvas bind:this={nextCanvases[i]}></canvas>{/each}
			</div>
			<dl>
				<dt>Score</dt>
				<dd>{ui.score.toLocaleString()}</dd>
				<dt>Lines</dt>
				<dd>{ui.lines}</dd>
				<dt>Level</dt>
				<dd>{ui.level}</dd>
			</dl>
			{#if !multiplayer && !ui.over}
				<button class="ghost small" onclick={() => (paused = !paused)}>{paused ? 'Resume' : 'Pause'}</button>
			{/if}
		</aside>
	</div>

	<div class="pad" aria-label="Controls">
		<button class="ghost" use:hold={'hold'} aria-label="Hold">Hold</button>
		<button class="ghost" use:hold={'ccw'} aria-label="Rotate left">⟲</button>
		<button class="ghost" use:hold={'cw'} aria-label="Rotate right">⟳</button>
		<button class="ghost power" use:hold={'power'} aria-label="Use power-up" disabled={!ui.powers.length}>
			{ui.powers[0] ? POWERS[ui.powers[0]].icon : '✦'}
		</button>
		<button class="ghost" use:hold={'left'} aria-label="Left">◀</button>
		<button class="ghost" use:hold={'soft'} aria-label="Soft drop">▼</button>
		<button class="ghost" use:hold={'right'} aria-label="Right">▶</button>
		<button use:hold={'hard'} aria-label="Hard drop">⤓</button>
	</div>
	<p class="keys muted">
		← → move · ↑ or X rotate · Z rotate back · ↓ soft drop · Space drop · C hold · E power-up{multiplayer ? '' : ' · P pause'}
	</p>
</div>

<style>
	.tetris {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		user-select: none;
		-webkit-user-select: none;
		-webkit-touch-callout: none;
	}
	.play {
		flex: 1;
		min-height: 0;
		display: flex;
		justify-content: center;
		align-items: flex-start;
		gap: 8px;
	}
	.side {
		width: calc(var(--cell) * 2.6);
		display: flex;
		flex-direction: column;
		gap: 8px;
		font-size: clamp(0.7rem, calc(var(--cell) * 0.5), 0.95rem);
	}
	.box {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		padding: 6px 0;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	.label {
		font-size: 0.75em;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--muted);
	}
	.powers {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.slot {
		width: calc(var(--cell) * 1.4);
		height: calc(var(--cell) * 1.4);
		display: grid;
		place-items: center;
		border: 1px dashed var(--border);
		border-radius: 6px;
		font-size: calc(var(--cell) * 0.8);
	}
	.slot.full {
		border-style: solid;
		border-color: var(--accent);
	}
	.effects {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 2px;
		font-size: calc(var(--cell) * 0.8);
	}
	dl {
		margin: 0;
		display: grid;
		gap: 0;
	}
	dt {
		font-size: 0.75em;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--muted);
	}
	dd {
		margin: 0 0 4px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.small {
		padding: 0.3rem 0.4rem;
		font-size: 0.85em;
	}
	.well {
		position: relative;
		display: flex;
		align-items: flex-end;
	}
	.board {
		display: block;
		border-radius: 6px;
		touch-action: none;
		box-shadow: 0 0 0 1px var(--border);
	}
	.incoming {
		position: absolute;
		left: -7px;
		bottom: 0;
		width: 4px;
		border-radius: 2px;
		background: var(--danger);
		transition: height 0.2s;
	}
	.notices {
		position: absolute;
		top: 8px;
		left: 0;
		right: 0;
		display: grid;
		gap: 4px;
		justify-items: center;
		pointer-events: none;
	}
	.notice {
		max-width: 90%;
		padding: 4px 10px;
		border-radius: 999px;
		background: rgba(0, 0, 0, 0.75);
		color: #fff;
		font-size: 0.85rem;
		text-align: center;
		animation: pop 0.2s ease-out;
	}
	@keyframes pop {
		from {
			transform: scale(0.8);
			opacity: 0;
		}
	}
	.overlay {
		position: absolute;
		inset: 0;
		display: grid;
		place-content: center;
		gap: 0.75rem;
		text-align: center;
		color: #fff;
		background: rgba(0, 0, 0, 0.6);
		border-radius: 6px;
		font-size: 1.25rem;
	}
	.pad {
		display: none;
		grid-template-columns: repeat(4, 1fr);
		gap: 8px;
		padding: 10px 0 max(10px, env(safe-area-inset-bottom));
		max-width: 420px;
		width: 100%;
		margin: 0 auto;
		touch-action: none;
	}
	.pad button {
		height: 52px;
		font-size: 1.3rem;
		padding: 0;
		touch-action: none;
		background: var(--surface);
		color: var(--text);
	}
	.pad button:last-child {
		background: var(--accent);
		color: var(--accent-text);
	}
	.pad button.power:not(:disabled) {
		border-color: var(--accent);
	}
	.pad :global(button.down) {
		filter: brightness(0.85);
		transform: scale(0.96);
	}
	.keys {
		font-size: 0.8rem;
		text-align: center;
		margin: 0.5rem 0 0;
	}
	@media (pointer: coarse) {
		.pad {
			display: grid;
		}
		.keys {
			display: none;
		}
	}
</style>

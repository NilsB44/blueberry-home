<script lang="ts">
	import { page } from '$app/state';
	import type { Power } from '#lib/tetris/game.ts';
	import MiniBoard from '#lib/tetris/MiniBoard.svelte';
	import Tetris from '#lib/tetris/Tetris.svelte';

	type Player = {
		id: number;
		name: string;
		playing: boolean;
		alive: boolean;
		score: number;
		lines: number;
		place: number | null;
		wins: number;
	};
	type Lobby = { code: string; host: number | null; started: boolean; round: number; winner: string | null; players: Player[] };

	const code = $derived(page.params.code!.toUpperCase());

	let ws: WebSocket | null = null;
	let me = $state<number | null>(null);
	let lobby = $state<Lobby | null>(null);
	let phase = $state<'connecting' | 'lobby' | 'countdown' | 'playing' | 'watching' | 'closed'>('connecting');
	let seed = $state(0);
	let round = $state(0);
	let count = $state(3);
	let boards = $state<Record<number, { board: string; score: number }>>({});
	let outcome = $state<{ winner: string | null; id: number | null } | null>(null);
	let error = $state('');
	let game = $state<Tetris | null>(null);
	let iAmOut = $state(false);
	let narrow = $state(false);

	const isHost = $derived(lobby?.host === me);
	const others = $derived(lobby?.players.filter((p) => p.id !== me && (p.playing || phase === 'watching')) ?? []);

	function send(msg: object) {
		if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
	}

	function connect() {
		error = '';
		phase = 'connecting';
		const proto = location.protocol === 'https:' ? 'wss' : 'ws';
		const socket = new WebSocket(`${proto}://${location.host}/api/tetris/rooms/${code}/ws`);
		ws = socket;
		socket.onmessage = (e) => handle(JSON.parse(e.data));
		socket.onclose = () => {
			if (ws !== socket) return;
			ws = null;
			phase = 'closed';
			if (!error) error = 'Lost the connection to the room';
		};
	}

	let countdown: ReturnType<typeof setInterval> | undefined;

	function handle(msg: any) {
		switch (msg.t) {
			case 'hello':
				me = msg.you;
				break;
			case 'lobby':
				lobby = msg;
				if (phase === 'connecting') phase = 'lobby';
				break;
			case 'start':
				seed = msg.seed;
				round = msg.round;
				boards = {};
				outcome = null;
				iAmOut = false;
				phase = 'countdown';
				count = 3;
				clearInterval(countdown);
				countdown = setInterval(() => {
					count--;
					if (count <= 0) {
						clearInterval(countdown);
						if (phase === 'countdown') phase = 'playing';
					}
				}, 800);
				break;
			case 'watch':
				// Joined while a round is on: watch it, play the next one.
				phase = 'watching';
				break;
			case 'state':
				boards[msg.id] = { board: msg.board, score: msg.score };
				break;
			case 'garbage':
				game?.garbage(msg.lines, msg.from);
				break;
			case 'power':
				game?.power(msg.kind, msg.from);
				break;
			case 'end':
				outcome = { winner: msg.winner, id: msg.id };
				if (phase === 'watching') phase = 'lobby';
				break;
			case 'error':
				error = msg.message;
				break;
		}
	}

	$effect(() => {
		connect();
		const resize = () => (narrow = innerWidth < 600);
		resize();
		addEventListener('resize', resize);
		return () => {
			const socket = ws;
			ws = null;
			socket?.close();
			clearInterval(countdown);
			removeEventListener('resize', resize);
		};
	});

	function backToLobby() {
		outcome = null;
		phase = 'lobby';
	}

	const inGame = $derived(phase === 'countdown' || phase === 'playing' || (outcome !== null && round > 0));
</script>

<div class="page" class:game={inGame}>
	<nav>
		<a href="/tetris" class="muted">← Tetris</a>
		<span>Room <strong class="code">{code}</strong></span>
	</nav>

	{#if error}<p class="error">{error}</p>{/if}

	{#if phase === 'closed'}
		<div class="card center">
			<p>{error || 'Disconnected.'}</p>
			<button onclick={connect}>Rejoin</button>
		</div>
	{:else if phase === 'connecting'}
		<p class="muted">Joining…</p>
	{:else if inGame}
		{#if others.length}
			<div class="opponents">
				{#each others as p (p.id)}
					<MiniBoard
						name={p.name}
						board={boards[p.id]?.board ?? ''}
						score={boards[p.id]?.score ?? 0}
						out={round > 0 && p.playing && !p.alive && !outcome}
						cell={narrow ? 4 : 7}
					/>
				{/each}
			</div>
		{/if}
		<div class="play">
			{#key round}
				<Tetris
					bind:this={game}
					{seed}
					multiplayer
					running={phase === 'playing' && !outcome}
					onstate={(board, score, lines) => send({ t: 'state', board, score, lines })}
					onattack={(lines) => send({ t: 'attack', lines })}
					onpower={(kind: Power) => send({ t: 'power', kind })}
					onover={() => {
						iAmOut = true;
						send({ t: 'over' });
					}}
				/>
			{/key}
			{#if phase === 'countdown'}
				<div class="overlay"><span class="count">{count}</span></div>
			{:else if outcome}
				<div class="overlay">
					<div class="card center">
						<h2>
							{#if outcome.winner === null}Nobody wins
							{:else if outcome.id === me}🏆 You win!
							{:else}{outcome.winner} wins{/if}
						</h2>
						<button onclick={backToLobby}>Back to the room</button>
					</div>
				</div>
			{:else if iAmOut}
				<div class="overlay soft"><div class="card center">You're out. Watch the others finish.</div></div>
			{/if}
		</div>
	{:else if lobby}
		<div class="lobby">
			{#if phase === 'watching'}
				<p class="muted">A round is on. You'll play in the next one.</p>
				<div class="opponents">
					{#each lobby.players.filter((p) => p.playing) as p (p.id)}
						<MiniBoard name={p.name} board={boards[p.id]?.board ?? ''} score={boards[p.id]?.score ?? 0} out={!p.alive} cell={narrow ? 6 : 9} />
					{/each}
				</div>
			{/if}
			<div class="card">
				<p class="muted share">Others on the Wi-Fi can join from the Tetris page with code <strong class="code">{code}</strong>.</p>
				<ul class="players">
					{#each lobby.players as p (p.id)}
						<li>
							<span>{p.name}{p.id === me ? ' (you)' : ''}</span>
							{#if p.id === lobby.host}<span class="tag">host</span>{/if}
							<span class="wins muted">{p.wins} {p.wins === 1 ? 'win' : 'wins'}</span>
						</li>
					{/each}
				</ul>
				{#if phase !== 'watching'}
					{#if isHost}
						<button onclick={() => send({ t: 'start' })} disabled={lobby.players.length < 2}>
							{lobby.round ? 'Play again' : 'Start'}
						</button>
						{#if lobby.players.length < 2}<p class="muted">Waiting for someone to join…</p>{/if}
					{:else}
						<p class="muted">Waiting for {lobby.players.find((p) => p.id === lobby?.host)?.name ?? 'the host'} to start.</p>
					{/if}
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.page {
		padding: 0.5rem 16px 0;
		max-width: 760px;
		margin: 0 auto;
	}
	.page.game {
		max-width: none;
		height: calc(100dvh - 52px);
		display: flex;
		flex-direction: column;
	}
	nav {
		display: flex;
		justify-content: space-between;
		padding-bottom: 0.5rem;
	}
	nav a {
		text-decoration: none;
	}
	.code {
		letter-spacing: 0.15em;
	}
	.opponents {
		display: flex;
		justify-content: center;
		gap: 12px;
		padding-bottom: 8px;
		flex-wrap: wrap;
	}
	.play {
		position: relative;
		flex: 1;
		min-height: 0;
	}
	.overlay {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		background: color-mix(in srgb, var(--bg) 55%, transparent);
	}
	.overlay.soft {
		background: none;
		place-items: start center;
		padding-top: 30%;
		pointer-events: none;
	}
	.count {
		font-size: 5rem;
		font-weight: 800;
	}
	.center {
		text-align: center;
		display: grid;
		gap: 0.75rem;
		justify-items: center;
	}
	h2 {
		margin: 0;
	}
	.lobby {
		display: grid;
		gap: 1rem;
	}
	.share {
		margin-top: 0;
	}
	.players {
		list-style: none;
		padding: 0;
		margin: 0 0 1rem;
		display: grid;
		gap: 0.4rem;
	}
	.players li {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.tag {
		font-size: 0.7rem;
		padding: 0 0.4rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		color: var(--accent);
	}
	.wins {
		margin-left: auto;
	}
</style>

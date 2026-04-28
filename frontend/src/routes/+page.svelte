<script lang="ts">
	import { onMount } from 'svelte';
	import PokerTable from '$lib/components/PokerTable.svelte';
	import Leaderboard from '$lib/components/Leaderboard.svelte';
	import { store } from '$lib/store.svelte';

	onMount(() => {
		const env = import.meta.env.VITE_WS_URL as string | undefined;
		const wsUrl =
			env ??
			`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.hostname}:8000/ws`;
		store.connect(wsUrl);
	});

	const statusLine = $derived.by(() => {
		const s = store.state;
		if (!s.connected) return 'connecting…';
		if (s.hand_id === null) return 'waiting for next hand…';
		const actor = s.current_actor !== null ? s.seats[s.current_actor] : null;
		if (actor) return `Hand #${s.hand_id} · ${actor.bot_name} to act`;
		return `Hand #${s.hand_id}`;
	});
</script>

<svelte:head>
	<title>Deep Poker Lab</title>
</svelte:head>

<div class="bg-glow"></div>

<header>
	<h1>Deep Poker <span class="accent">Lab</span></h1>
	<p class="status">
		<span class="dot" class:on={store.state.connected}></span>
		<span class="status-text">{statusLine}</span>
	</p>
</header>

<main>
	<PokerTable state={store.state} />
	<Leaderboard entries={store.state.leaderboard} />
</main>

<style>
	:global(:root) {
		--bg-0: #07040d;
		--bg-1: #14082a;
		--bg-2: #1f0f3d;
		--purple-1: #6d28d9;
		--purple-2: #a855f7;
		--purple-3: #d946ef;
		--ink-0: #f5f3ff;
		--ink-1: #c4b5fd;
		--ink-2: #8b7eb8;
		--felt-0: #0a3a23;
		--felt-1: #117a4a;
		--felt-2: #1aa365;
		--win: #34d399;
		--loss: #f87171;
	}
	:global(html), :global(body) {
		margin: 0;
		min-height: 100%;
	}
	:global(body) {
		font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
		background: radial-gradient(ellipse at top, #1f0f3d 0%, #0c0419 45%, #07040d 100%);
		background-attachment: fixed;
		color: var(--ink-0);
		-webkit-font-smoothing: antialiased;
		min-height: 100vh;
	}
	.bg-glow {
		position: fixed;
		inset: 0;
		pointer-events: none;
		background:
			radial-gradient(circle at 15% 20%, rgba(168, 85, 247, 0.18), transparent 45%),
			radial-gradient(circle at 85% 30%, rgba(217, 70, 239, 0.12), transparent 50%),
			radial-gradient(circle at 50% 100%, rgba(109, 40, 217, 0.18), transparent 60%);
		z-index: 0;
	}
	header {
		position: relative;
		z-index: 1;
		text-align: center;
		padding: 28px 16px 12px;
	}
	header h1 {
		margin: 0;
		font-size: 2.1em;
		font-weight: 800;
		letter-spacing: -0.02em;
		background: linear-gradient(90deg, #f5f3ff 0%, #c4b5fd 60%, #d946ef 100%);
		background-clip: text;
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
	}
	header h1 .accent {
		font-weight: 800;
	}
	.status {
		margin: 8px 0 0;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 5px 14px;
		font-size: 0.85em;
		color: var(--ink-1);
		background: rgba(255, 255, 255, 0.04);
		border: 1px solid rgba(168, 85, 247, 0.25);
		border-radius: 999px;
		backdrop-filter: blur(6px);
	}
	.status-text {
		font-variant-numeric: tabular-nums;
	}
	.dot {
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--loss);
		box-shadow: 0 0 8px var(--loss);
	}
	.dot.on {
		background: var(--win);
		box-shadow: 0 0 10px var(--win);
	}
	main {
		position: relative;
		z-index: 1;
		padding: 16px 24px 48px;
	}
</style>

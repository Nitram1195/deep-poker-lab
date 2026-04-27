<script lang="ts">
	import { onMount } from 'svelte';
	import PokerTable from '$lib/components/PokerTable.svelte';
	import Leaderboard from '$lib/components/Leaderboard.svelte';
	import { store } from '$lib/store.svelte';

	onMount(() => {
		// Default backend URL; can be overridden via Vite env var.
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

<header>
	<h1>Deep Poker Lab</h1>
	<p class="status">
		<span class="dot" class:on={store.state.connected}></span>
		{statusLine}
	</p>
</header>

<main>
	<PokerTable state={store.state} />
	<Leaderboard entries={store.state.leaderboard} />
</main>

<style>
	:global(body) {
		margin: 0;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
		background: #f4f4f5;
		color: #222;
	}
	header {
		text-align: center;
		padding: 16px;
	}
	header h1 {
		margin: 0;
		font-size: 1.6em;
		font-weight: 600;
	}
	.status {
		margin: 4px 0 0;
		color: #555;
		font-size: 0.9em;
	}
	.dot {
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #c33;
		margin-right: 4px;
	}
	.dot.on {
		background: #2c7;
	}
	main {
		padding: 0 16px 32px;
	}
</style>

<script lang="ts">
	import type { LeaderboardEntry } from '$lib/types';

	let { entries }: { entries: LeaderboardEntry[] } = $props();

	const sorted = $derived([...entries].sort((a, b) => b.net_chips - a.net_chips));
</script>

<div class="leaderboard">
	<h2>Leaderboard</h2>
	{#if sorted.length === 0}
		<p class="empty">No hands played yet</p>
	{:else}
		<table>
			<thead>
				<tr>
					<th>Bot</th>
					<th>Hands</th>
					<th>Net chips</th>
					<th>bb / hand</th>
				</tr>
			</thead>
			<tbody>
				{#each sorted as e (e.bot_name)}
					<tr>
						<td class="name">{e.bot_name}</td>
						<td class="num">{e.hands_played}</td>
						<td class="num" class:positive={e.net_chips > 0} class:negative={e.net_chips < 0}>
							{e.net_chips > 0 ? '+' : ''}{e.net_chips}
						</td>
						<td class="num">
							{e.hands_played > 0 ? (e.net_chips / 2 / e.hands_played).toFixed(2) : '0.00'}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</div>

<style>
	.leaderboard {
		background: #fff;
		padding: 16px 20px;
		border-radius: 8px;
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
		max-width: 480px;
		margin: 16px auto 0;
	}
	h2 {
		margin: 0 0 8px;
		font-size: 1.05em;
	}
	.empty {
		color: #777;
		font-style: italic;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.92em;
	}
	th,
	td {
		padding: 4px 8px;
		text-align: left;
	}
	th {
		font-weight: 600;
		color: #555;
		border-bottom: 1px solid #eee;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.positive {
		color: #1e8a4a;
	}
	.negative {
		color: #b03a2e;
	}
	.name {
		font-weight: 500;
	}
</style>

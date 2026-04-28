<script lang="ts">
	import type { LeaderboardEntry } from '$lib/types';

	let { entries }: { entries: LeaderboardEntry[] } = $props();

	const sorted = $derived([...entries].sort((a, b) => b.net_chips - a.net_chips));
</script>

<div class="leaderboard">
	<div class="header">
		<h2>Leaderboard</h2>
		<span class="subtitle">net chips by bot</span>
	</div>
	{#if sorted.length === 0}
		<p class="empty">No hands played yet</p>
	{:else}
		<table>
			<thead>
				<tr>
					<th>#</th>
					<th>Bot</th>
					<th class="num">Hands</th>
					<th class="num">Net chips</th>
					<th class="num">bb / hand</th>
				</tr>
			</thead>
			<tbody>
				{#each sorted as e, i (e.bot_name)}
					<tr class:top={i === 0}>
						<td class="rank">{i + 1}</td>
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
		max-width: 560px;
		margin: 32px auto 0;
		padding: 18px 22px 14px;
		background: linear-gradient(160deg, rgba(45, 27, 78, 0.6) 0%, rgba(20, 8, 42, 0.7) 100%);
		border: 1px solid rgba(168, 85, 247, 0.3);
		border-radius: 14px;
		backdrop-filter: blur(10px);
		box-shadow:
			0 12px 40px rgba(0, 0, 0, 0.5),
			inset 0 1px 0 rgba(255, 255, 255, 0.05);
	}
	.header {
		display: flex;
		align-items: baseline;
		gap: 12px;
		margin-bottom: 10px;
	}
	h2 {
		margin: 0;
		font-size: 1em;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-0);
	}
	.subtitle {
		font-size: 0.78em;
		color: var(--ink-2);
		letter-spacing: 0.04em;
	}
	.empty {
		color: var(--ink-2);
		font-style: italic;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9em;
	}
	th, td {
		padding: 7px 10px;
		text-align: left;
	}
	th {
		font-weight: 600;
		color: var(--ink-2);
		border-bottom: 1px solid rgba(168, 85, 247, 0.2);
		font-size: 0.78em;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	tbody tr {
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		transition: background 0.15s;
	}
	tbody tr:last-child {
		border-bottom: none;
	}
	tbody tr:hover {
		background: rgba(168, 85, 247, 0.06);
	}
	tbody tr.top {
		background: linear-gradient(90deg, rgba(217, 70, 239, 0.12), rgba(168, 85, 247, 0.04));
	}
	tbody tr.top:hover {
		background: linear-gradient(90deg, rgba(217, 70, 239, 0.18), rgba(168, 85, 247, 0.08));
	}
	.rank {
		color: var(--ink-2);
		font-variant-numeric: tabular-nums;
		width: 1.5em;
	}
	tr.top .rank {
		color: #fde047;
		font-weight: 700;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
		color: var(--ink-1);
	}
	.positive {
		color: var(--win);
		font-weight: 600;
	}
	.negative {
		color: var(--loss);
		font-weight: 600;
	}
	.name {
		font-weight: 600;
		color: var(--ink-0);
	}
</style>

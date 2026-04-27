<script lang="ts">
	import type { SeatState } from '$lib/types';
	import Card from './Card.svelte';

	let {
		seat,
		isButton,
		isActor
	}: { seat: SeatState; isButton: boolean; isActor: boolean } = $props();

	const actionLabel = $derived(formatAction(seat.last_action));

	function formatAction(a: SeatState['last_action']) {
		if (!a) return '';
		if (a.kind === 'fold') return 'fold';
		if (a.kind === 'check_call') return seat.bet > 0 ? `call ${seat.bet}` : 'check';
		return `raise to ${a.amount}`;
	}
</script>

<div class="seat" class:folded={seat.folded} class:actor={isActor}>
	<div class="name-row">
		{#if isActor}<span class="turn-arrow" aria-hidden="true">▶</span>{/if}
		<span class="name">{seat.bot_name}</span>
		{#if isButton}<span class="dealer-btn" title="Dealer button">D</span>{/if}
	</div>
	<div class="cards" class:mucked={seat.folded}>
		{#if seat.hole_cards && seat.hole_cards.length > 0}
			{#each seat.hole_cards as c (c)}<Card card={c} />{/each}
		{:else}
			<Card card={null} /><Card card={null} />
		{/if}
	</div>
	{#if seat.hand_label && !seat.folded}
		<div class="hand-label" data-rank={seat.hand_label.category}>{seat.hand_label.text}</div>
	{/if}
	<div class="info">
		<span class="stack">stack: {seat.stack}</span>
		{#if seat.bet > 0}<span class="bet">bet: {seat.bet}</span>{/if}
	</div>
	<div class="last-action">{actionLabel}</div>
</div>

<style>
	.seat {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 8px 12px;
		background: rgba(255, 255, 255, 0.92);
		border-radius: 8px;
		min-width: 160px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
		transition: outline 0.2s, box-shadow 0.2s, opacity 0.15s, transform 0.2s;
		outline: 3px solid transparent;
	}
	.seat.actor {
		outline: 3px solid #f1c40f;
		box-shadow: 0 0 0 4px rgba(241, 196, 15, 0.35), 0 0 24px rgba(241, 196, 15, 0.7);
		transform: scale(1.04);
		animation: actor-pulse 1.4s ease-in-out infinite;
		z-index: 2;
	}
	@keyframes actor-pulse {
		0%, 100% { box-shadow: 0 0 0 4px rgba(241, 196, 15, 0.35), 0 0 24px rgba(241, 196, 15, 0.7); }
		50%      { box-shadow: 0 0 0 6px rgba(241, 196, 15, 0.55), 0 0 36px rgba(241, 196, 15, 0.95); }
	}
	.turn-arrow {
		color: #d68910;
		font-weight: 700;
		font-size: 1em;
		line-height: 1;
	}
	.seat.folded {
		opacity: 0.45;
	}
	.name-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.name {
		font-weight: 600;
	}
	.dealer-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.4em;
		height: 1.4em;
		border-radius: 50%;
		background: white;
		color: black;
		border: 1px solid #444;
		font-weight: 700;
		font-size: 0.8em;
	}
	.cards {
		display: flex;
		gap: 0;
		transition: filter 0.15s, opacity 0.15s;
	}
	.cards.mucked {
		filter: grayscale(0.7);
		opacity: 0.55;
	}
	.info {
		display: flex;
		justify-content: space-between;
		font-size: 0.9em;
		color: #444;
	}
	.bet {
		color: #2c7;
		font-weight: 600;
	}
	.last-action {
		min-height: 1.2em;
		font-size: 0.85em;
		color: #2c3e50;
		font-style: italic;
	}
	.hand-label {
		font-size: 0.82em;
		font-weight: 600;
		letter-spacing: 0.02em;
		padding: 1px 6px;
		border-radius: 3px;
		align-self: flex-start;
		background: #ecf0f1;
		color: #2c3e50;
	}
	/* color hand-strength tiers from weak (gray) to monster (red) */
	.hand-label[data-rank='High card']         { background: #ecf0f1; color: #555; }
	.hand-label[data-rank='One pair']          { background: #d6eaf8; color: #1b4f72; }
	.hand-label[data-rank='Two pair']          { background: #aed6f1; color: #154360; }
	.hand-label[data-rank='Three of a kind']   { background: #abebc6; color: #145a32; }
	.hand-label[data-rank='Straight']          { background: #f9e79f; color: #7d6608; }
	.hand-label[data-rank='Flush']             { background: #f5cba7; color: #784212; }
	.hand-label[data-rank='Full house']        { background: #f5b7b1; color: #78281f; }
	.hand-label[data-rank='Four of a kind']    { background: #e74c3c; color: white; }
	.hand-label[data-rank='Straight flush']    { background: #c0392b; color: white; }
</style>

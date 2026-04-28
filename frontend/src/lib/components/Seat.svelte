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
		<span class="stack"><span class="info-label">stack</span> {seat.stack}</span>
		{#if seat.bet > 0}<span class="bet"><span class="info-label">bet</span> {seat.bet}</span>{/if}
	</div>
	<div class="last-action">{actionLabel}</div>
</div>

<style>
	.seat {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 10px 14px;
		min-width: 168px;
		background: linear-gradient(160deg, rgba(45, 27, 78, 0.92) 0%, rgba(20, 8, 42, 0.92) 100%);
		border: 1px solid rgba(168, 85, 247, 0.3);
		border-radius: 12px;
		color: var(--ink-0);
		backdrop-filter: blur(8px);
		box-shadow:
			0 8px 24px rgba(0, 0, 0, 0.4),
			inset 0 1px 0 rgba(255, 255, 255, 0.04);
		transition: outline 0.2s, box-shadow 0.2s, border-color 0.2s, opacity 0.15s, transform 0.2s;
		outline: 2px solid transparent;
	}
	.seat.actor {
		border-color: rgba(217, 70, 239, 0.9);
		outline: 2px solid rgba(217, 70, 239, 0.7);
		box-shadow:
			0 0 0 4px rgba(217, 70, 239, 0.18),
			0 0 32px rgba(217, 70, 239, 0.6),
			0 8px 24px rgba(0, 0, 0, 0.4);
		transform: scale(1.05);
		animation: actor-pulse 1.4s ease-in-out infinite;
		z-index: 2;
	}
	@keyframes actor-pulse {
		0%, 100% {
			box-shadow:
				0 0 0 4px rgba(217, 70, 239, 0.18),
				0 0 32px rgba(217, 70, 239, 0.55),
				0 8px 24px rgba(0, 0, 0, 0.4);
		}
		50% {
			box-shadow:
				0 0 0 6px rgba(217, 70, 239, 0.32),
				0 0 48px rgba(217, 70, 239, 0.85),
				0 8px 24px rgba(0, 0, 0, 0.4);
		}
	}
	.turn-arrow {
		color: var(--purple-3);
		font-weight: 700;
		font-size: 0.95em;
		line-height: 1;
		text-shadow: 0 0 6px rgba(217, 70, 239, 0.7);
	}
	.seat.folded {
		opacity: 0.4;
	}
	.name-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.name {
		font-weight: 600;
		font-size: 0.95em;
		color: var(--ink-0);
		letter-spacing: 0.01em;
	}
	.dealer-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		margin-left: auto;
		width: 1.5em;
		height: 1.5em;
		border-radius: 50%;
		background: linear-gradient(145deg, #fef3c7, #f59e0b);
		color: #422006;
		font-weight: 800;
		font-size: 0.72em;
		box-shadow: 0 2px 6px rgba(245, 158, 11, 0.4);
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
		font-size: 0.85em;
		color: var(--ink-1);
		font-variant-numeric: tabular-nums;
	}
	.info-label {
		color: var(--ink-2);
		font-size: 0.85em;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin-right: 2px;
	}
	.bet {
		color: var(--win);
		font-weight: 600;
	}
	.last-action {
		min-height: 1.2em;
		font-size: 0.8em;
		color: var(--ink-1);
		font-style: italic;
		letter-spacing: 0.02em;
	}
	.hand-label {
		font-size: 0.78em;
		font-weight: 700;
		letter-spacing: 0.04em;
		padding: 2px 8px;
		border-radius: 4px;
		align-self: flex-start;
		background: rgba(255, 255, 255, 0.05);
		color: var(--ink-1);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}
	/* hand-strength tiers, dark-theme palette */
	.hand-label[data-rank='High card']         { background: rgba(255, 255, 255, 0.05); color: #b9a8d6; border-color: rgba(255, 255, 255, 0.08); }
	.hand-label[data-rank='One pair']          { background: rgba(59, 130, 246, 0.18); color: #93c5fd; border-color: rgba(59, 130, 246, 0.4); }
	.hand-label[data-rank='Two pair']          { background: rgba(14, 165, 233, 0.22); color: #67e8f9; border-color: rgba(14, 165, 233, 0.45); }
	.hand-label[data-rank='Three of a kind']   { background: rgba(34, 197, 94, 0.22); color: #6ee7b7; border-color: rgba(34, 197, 94, 0.45); }
	.hand-label[data-rank='Straight']          { background: rgba(234, 179, 8, 0.22); color: #fde047; border-color: rgba(234, 179, 8, 0.45); }
	.hand-label[data-rank='Flush']             { background: rgba(249, 115, 22, 0.25); color: #fdba74; border-color: rgba(249, 115, 22, 0.5); }
	.hand-label[data-rank='Full house']        { background: rgba(244, 63, 94, 0.28); color: #fda4af; border-color: rgba(244, 63, 94, 0.55); }
	.hand-label[data-rank='Four of a kind']    {
		background: linear-gradient(135deg, #ef4444, #b91c1c); color: white; border-color: #fecaca;
		box-shadow: 0 0 12px rgba(239, 68, 68, 0.5);
	}
	.hand-label[data-rank='Straight flush']    {
		background: linear-gradient(135deg, #d946ef, #6d28d9); color: white; border-color: #f5d0fe;
		box-shadow: 0 0 16px rgba(217, 70, 239, 0.7);
	}
</style>

<script lang="ts">
	import type { TableState } from '$lib/types';
	import Card from './Card.svelte';
	import Seat from './Seat.svelte';

	let { state }: { state: TableState } = $props();
</script>

<div class="table-wrap">
	<div class="rim">
		<div class="felt">
			<div class="felt-pattern"></div>
			<div class="board">
				{#each state.board as c (c)}
					<Card card={c} />
				{/each}
				{#if state.board.length === 0}
					<span class="placeholder">— preflop —</span>
				{/if}
			</div>
			<div class="pot">
				<span class="pot-label">POT</span>
				<span class="pot-amount">{state.pot}</span>
			</div>
		</div>
	</div>

	<div class="seats">
		{#each state.seats as s (s.seat)}
			<div class="seat-slot" data-seat={s.seat}>
				<Seat
					seat={s}
					isButton={state.button_seat === s.seat}
					isActor={state.current_actor === s.seat}
					legal={state.current_actor === s.seat ? state.legal : null}
				/>
			</div>
		{/each}
	</div>
</div>

<style>
	.table-wrap {
		position: relative;
		width: min(1000px, 100%);
		aspect-ratio: 16 / 10;
		margin: 24px auto 0;
	}
	.rim {
		position: absolute;
		inset: 12% 8%;
		border-radius: 50% / 60%;
		padding: 14px;
		background: linear-gradient(135deg, #3b1d6b 0%, #1a0a3d 50%, #2a0f5e 100%);
		box-shadow:
			0 0 0 1px rgba(168, 85, 247, 0.4),
			0 30px 80px rgba(0, 0, 0, 0.6),
			0 0 60px rgba(168, 85, 247, 0.25);
	}
	.felt {
		position: relative;
		width: 100%;
		height: 100%;
		background:
			radial-gradient(ellipse at center, var(--felt-2) 0%, var(--felt-1) 45%, var(--felt-0) 100%);
		border-radius: 50% / 60%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 14px;
		box-shadow:
			inset 0 0 60px rgba(0, 0, 0, 0.55),
			inset 0 0 0 2px rgba(255, 255, 255, 0.05);
		overflow: hidden;
	}
	.felt-pattern {
		position: absolute;
		inset: 0;
		background-image:
			radial-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px);
		background-size: 14px 14px;
		opacity: 0.6;
		pointer-events: none;
	}
	.board {
		position: relative;
		display: flex;
		min-height: 4.2em;
		align-items: center;
		gap: 2px;
		z-index: 1;
	}
	.pot {
		position: relative;
		z-index: 1;
		display: inline-flex;
		align-items: baseline;
		gap: 8px;
		padding: 6px 18px;
		background: rgba(0, 0, 0, 0.45);
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 999px;
		backdrop-filter: blur(4px);
	}
	.pot-label {
		font-size: 0.7em;
		letter-spacing: 0.18em;
		color: var(--ink-1);
		font-weight: 600;
	}
	.pot-amount {
		color: #fff;
		font-weight: 700;
		font-size: 1.2em;
		font-variant-numeric: tabular-nums;
		letter-spacing: 0.02em;
	}
	.placeholder {
		color: rgba(255, 255, 255, 0.4);
		font-style: italic;
		letter-spacing: 0.1em;
		font-size: 0.9em;
	}
	.seats {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}
	.seat-slot {
		position: absolute;
		pointer-events: auto;
	}
	/* 6-max anchored positions */
	.seat-slot[data-seat='0'] { left: 50%; bottom: 0; transform: translateX(-50%); }
	.seat-slot[data-seat='1'] { left: 0; bottom: 22%; }
	.seat-slot[data-seat='2'] { left: 0; top: 5%; }
	.seat-slot[data-seat='3'] { left: 50%; top: 0; transform: translateX(-50%); }
	.seat-slot[data-seat='4'] { right: 0; top: 5%; }
	.seat-slot[data-seat='5'] { right: 0; bottom: 22%; }
</style>

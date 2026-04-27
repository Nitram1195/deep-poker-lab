<script lang="ts">
	import type { TableState } from '$lib/types';
	import Card from './Card.svelte';
	import Seat from './Seat.svelte';

	let { state }: { state: TableState } = $props();
</script>

<div class="table-wrap">
	<div class="felt">
		<div class="board">
			{#each state.board as c (c)}
				<Card card={c} />
			{/each}
			{#if state.board.length === 0}
				<span class="placeholder">— preflop —</span>
			{/if}
		</div>
		<div class="pot">Pot: {state.pot}</div>
	</div>

	<div class="seats">
		{#each state.seats as s (s.seat)}
			<div class="seat-slot" data-seat={s.seat}>
				<Seat
					seat={s}
					isButton={state.button_seat === s.seat}
					isActor={state.current_actor === s.seat}
				/>
			</div>
		{/each}
	</div>
</div>

<style>
	.table-wrap {
		position: relative;
		width: min(900px, 100%);
		aspect-ratio: 16 / 10;
		margin: 0 auto;
	}
	.felt {
		position: absolute;
		inset: 12% 8%;
		background: radial-gradient(ellipse at center, #1a6b3a, #0e4326);
		border: 8px solid #5a3b1f;
		border-radius: 50% / 60%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 8px;
		box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.5);
	}
	.board {
		display: flex;
		min-height: 3.6em;
		align-items: center;
	}
	.pot {
		color: #fff;
		font-weight: 600;
		letter-spacing: 0.04em;
	}
	.placeholder {
		color: #ccc;
		font-style: italic;
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
	/* 6-max anchored positions; for fewer than 6 we use the first N */
	.seat-slot[data-seat='0'] {
		left: 50%;
		bottom: 0;
		transform: translateX(-50%);
	}
	.seat-slot[data-seat='1'] {
		left: 0;
		bottom: 22%;
	}
	.seat-slot[data-seat='2'] {
		left: 0;
		top: 5%;
	}
	.seat-slot[data-seat='3'] {
		left: 50%;
		top: 0;
		transform: translateX(-50%);
	}
	.seat-slot[data-seat='4'] {
		right: 0;
		top: 5%;
	}
	.seat-slot[data-seat='5'] {
		right: 0;
		bottom: 22%;
	}
</style>

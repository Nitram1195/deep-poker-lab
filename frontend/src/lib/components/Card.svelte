<script lang="ts">
	let { card }: { card: string | null } = $props();

	// card is "Td", "As", "2c", "Tc" etc; null = back of card.
	const suitSymbol: Record<string, string> = {
		s: '♠',
		h: '♥',
		d: '♦',
		c: '♣'
	};
	const suitColor: Record<string, string> = {
		s: 'black',
		c: 'black',
		h: 'red',
		d: 'red'
	};
</script>

{#if card}
	<span class="card" data-color={suitColor[card[1]]}>
		<span class="rank">{card[0] === 'T' ? '10' : card[0]}</span>
		<span class="suit">{suitSymbol[card[1]]}</span>
	</span>
{:else}
	<span class="card back">&nbsp;</span>
{/if}

<style>
	.card {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 1px;
		min-width: 2.4em;
		height: 3.2em;
		padding: 0 0.3em;
		margin: 0 2px;
		background: white;
		border: 1px solid #888;
		border-radius: 4px;
		font-family: ui-monospace, monospace;
		font-weight: 600;
		font-size: 1.05em;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
	}
	.card[data-color='red'] {
		color: #c0392b;
	}
	.card[data-color='black'] {
		color: #222;
	}
	.card.back {
		background: repeating-linear-gradient(45deg, #224, #224 4px, #335 4px, #335 8px);
		border-color: #112;
	}
	.suit {
		font-size: 1.05em;
	}
</style>

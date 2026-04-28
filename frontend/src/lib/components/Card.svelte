<script lang="ts">
	let { card }: { card: string | null } = $props();

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
		min-width: 2.5em;
		height: 3.4em;
		padding: 0 0.35em;
		margin: 0 2px;
		background: linear-gradient(180deg, #ffffff 0%, #ece8f8 100%);
		border: 1px solid rgba(168, 85, 247, 0.25);
		border-radius: 6px;
		font-family: 'SF Mono', ui-monospace, 'Cascadia Code', Consolas, monospace;
		font-weight: 700;
		font-size: 1.05em;
		box-shadow:
			0 4px 8px rgba(0, 0, 0, 0.4),
			inset 0 1px 0 rgba(255, 255, 255, 0.6);
	}
	.card[data-color='red'] {
		color: #dc2626;
	}
	.card[data-color='black'] {
		color: #111827;
	}
	.card.back {
		background:
			linear-gradient(135deg, #4c1d95 0%, #2e1065 50%, #1e0a4a 100%);
		background-size: 100% 100%;
		border: 1px solid rgba(168, 85, 247, 0.5);
		box-shadow:
			0 4px 8px rgba(0, 0, 0, 0.5),
			inset 0 0 0 2px rgba(168, 85, 247, 0.15),
			inset 0 0 0 4px rgba(217, 70, 239, 0.1);
	}
	.card.back::after {
		content: '';
		position: absolute;
	}
	.suit {
		font-size: 1.05em;
	}
</style>

<script lang="ts">
	import type { LegalActions, SeatState } from '$lib/types';
	import Card from './Card.svelte';
	import { store } from '$lib/store.svelte';

	let {
		seat,
		isButton,
		isActor,
		legal
	}: {
		seat: SeatState;
		isButton: boolean;
		isActor: boolean;
		legal: LegalActions | null;
	} = $props();

	const showActions = $derived(seat.is_human && isActor && legal !== null);
	const callLabel = $derived.by(() => {
		if (!legal) return 'check';
		return legal.to_call > 0 ? `call ${legal.to_call}` : 'check';
	});
	const canRaise = $derived(legal !== null && legal.max_raise > 0 && legal.min_raise > 0);

	let raiseAmount = $state(0);
	$effect(() => {
		// Reset the raise input each time it's the human's turn.
		if (showActions && legal) {
			raiseAmount = legal.min_raise;
		}
	});

	function clamp(n: number) {
		if (!legal) return n;
		return Math.max(legal.min_raise, Math.min(legal.max_raise, Math.floor(n)));
	}

	function doFold() {
		store.act(seat.seat, 'fold');
	}
	function doCheckCall() {
		store.act(seat.seat, 'check_call');
	}
	function doRaise() {
		if (!legal) return;
		store.act(seat.seat, 'raise_to', clamp(raiseAmount));
	}

	const isAllIn = $derived(!seat.sitting_out && !seat.folded && seat.stack === 0);
	const actionLabel = $derived(formatAction(seat.last_action));

	function formatAction(a: SeatState['last_action']) {
		if (!a) return '';
		if (a.kind === 'fold') return 'fold';
		const allInSuffix = isAllIn ? ' (all-in)' : '';
		if (a.kind === 'check_call') return (seat.bet > 0 ? `call ${seat.bet}` : 'check') + allInSuffix;
		return `raise to ${a.amount}` + allInSuffix;
	}

	let menuOpen = $state(false);
	let menuX = $state(0);
	let menuY = $state(0);

	function onContextMenu(e: MouseEvent) {
		e.preventDefault();
		// clamp so the menu never spills outside the viewport
		const MENU_W = 200;
		const MENU_H = 96;
		menuX = Math.min(e.clientX, window.innerWidth - MENU_W - 4);
		menuY = Math.min(e.clientY, window.innerHeight - MENU_H - 4);
		menuOpen = true;
	}

	function toggleSitOut() {
		if (seat.sitting_out) store.sitIn(seat.seat);
		else store.sitOut(seat.seat);
		menuOpen = false;
	}

	function onWindowClick() {
		if (menuOpen) menuOpen = false;
	}

	function onWindowKey(e: KeyboardEvent) {
		if (e.key === 'Escape') menuOpen = false;
	}

	// Render the menu outside any transformed ancestor (transformed parents
	// become the containing block for position:fixed children, which is why
	// the menu appears offset when the seat or its slot uses transform).
	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return { destroy: () => node.remove() };
	}
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} oncontextmenu={(e) => menuOpen && e.preventDefault()} />

<div
	class="seat"
	class:folded={seat.folded}
	class:actor={isActor}
	class:sitting-out={seat.sitting_out}
	oncontextmenu={onContextMenu}
	role="group"
	aria-label={`seat ${seat.seat}: ${seat.bot_name}`}
>
	<div class="name-row">
		{#if isActor}<span class="turn-arrow" aria-hidden="true">▶</span>{/if}
		<span class="name">{seat.bot_name}</span>
		{#if isButton && !seat.sitting_out}<span class="dealer-btn" title="Dealer button">D</span>{/if}
	</div>

	{#if seat.sitting_out}
		<div class="sitout-badge">sitting out</div>
		<div class="info">
			<span class="info-label">stack</span> {seat.stack}
		</div>
	{:else}
		<div class="cards" class:mucked={seat.folded}>
			{#if seat.hole_cards && seat.hole_cards.length > 0}
				{#each seat.hole_cards as c (c)}<Card card={c} />{/each}
			{:else}
				<Card card={null} /><Card card={null} />
			{/if}
		</div>
		{#if isAllIn}
			<div class="allin-badge">ALL-IN</div>
		{/if}
		{#if seat.hand_label && !seat.folded}
			<div class="hand-label" data-rank={seat.hand_label.category}>{seat.hand_label.text}</div>
		{/if}
		<div class="info">
			<span class="stack"><span class="info-label">stack</span> {seat.stack}</span>
			{#if seat.bet > 0}<span class="bet"><span class="info-label">bet</span> {seat.bet}</span>{/if}
		</div>
		<div class="last-action">{actionLabel}</div>
		{#if showActions && legal}
			<div class="actions" onclick={(e) => e.stopPropagation()}>
				<div class="action-row">
					<button class="btn fold" onclick={doFold}>Fold</button>
					<button class="btn call" onclick={doCheckCall}>{callLabel}</button>
				</div>
				{#if canRaise}
					<div class="action-row raise-row">
						<input
							type="number"
							min={legal.min_raise}
							max={legal.max_raise}
							step="1"
							bind:value={raiseAmount}
						/>
						<button class="btn raise" onclick={doRaise}>
							Raise to {clamp(raiseAmount)}
						</button>
					</div>
					<div class="raise-hint">min {legal.min_raise} · max {legal.max_raise}</div>
				{/if}
			</div>
		{/if}
	{/if}
</div>

{#if menuOpen}
	<div
		use:portal
		class="menu"
		style="left: {menuX}px; top: {menuY}px"
		onclick={(e) => e.stopPropagation()}
		oncontextmenu={(e) => e.preventDefault()}
		role="menu"
		tabindex="-1"
	>
		<div class="menu-header">{seat.bot_name}</div>
		<button class="menu-item" onclick={toggleSitOut} role="menuitem">
			{seat.sitting_out ? 'Sit in' : 'Sit out'}
		</button>
	</div>
{/if}

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
		cursor: context-menu;
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
	.seat.folded {
		opacity: 0.4;
	}
	.seat.sitting-out {
		opacity: 0.55;
		filter: saturate(0.4);
		border-style: dashed;
	}
	.turn-arrow {
		color: var(--purple-3);
		font-weight: 700;
		font-size: 0.95em;
		line-height: 1;
		text-shadow: 0 0 6px rgba(217, 70, 239, 0.7);
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
	.sitout-badge {
		align-self: flex-start;
		padding: 4px 10px;
		font-size: 0.72em;
		font-weight: 700;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--ink-1);
		background: rgba(168, 85, 247, 0.12);
		border: 1px dashed rgba(168, 85, 247, 0.5);
		border-radius: 4px;
	}
	.allin-badge {
		align-self: flex-start;
		padding: 3px 10px;
		font-size: 0.74em;
		font-weight: 800;
		letter-spacing: 0.18em;
		color: #ffffff;
		background: linear-gradient(135deg, #ef4444, #b91c1c);
		border: 1px solid rgba(254, 202, 202, 0.6);
		border-radius: 4px;
		box-shadow: 0 0 14px rgba(239, 68, 68, 0.55);
		animation: allin-glow 1.6s ease-in-out infinite;
	}
	@keyframes allin-glow {
		0%, 100% { box-shadow: 0 0 10px rgba(239, 68, 68, 0.45); }
		50%      { box-shadow: 0 0 22px rgba(239, 68, 68, 0.85); }
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

	.actions {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin-top: 4px;
		padding-top: 8px;
		border-top: 1px solid rgba(168, 85, 247, 0.2);
	}
	.action-row {
		display: flex;
		gap: 6px;
	}
	.btn {
		flex: 1;
		padding: 6px 10px;
		font: inherit;
		font-size: 0.85em;
		font-weight: 600;
		color: var(--ink-0);
		background: linear-gradient(160deg, rgba(109, 40, 217, 0.6), rgba(45, 27, 78, 0.6));
		border: 1px solid rgba(168, 85, 247, 0.5);
		border-radius: 6px;
		cursor: pointer;
		transition: background 0.1s, transform 0.05s;
	}
	.btn:hover {
		background: linear-gradient(160deg, rgba(168, 85, 247, 0.7), rgba(109, 40, 217, 0.7));
	}
	.btn:active {
		transform: scale(0.98);
	}
	.btn.fold {
		background: linear-gradient(160deg, rgba(127, 29, 29, 0.5), rgba(45, 27, 78, 0.6));
		border-color: rgba(248, 113, 113, 0.45);
	}
	.btn.fold:hover {
		background: linear-gradient(160deg, rgba(220, 38, 38, 0.6), rgba(127, 29, 29, 0.6));
	}
	.btn.raise {
		background: linear-gradient(160deg, rgba(217, 70, 239, 0.6), rgba(109, 40, 217, 0.6));
		border-color: rgba(217, 70, 239, 0.55);
	}
	.btn.raise:hover {
		background: linear-gradient(160deg, rgba(217, 70, 239, 0.8), rgba(168, 85, 247, 0.7));
	}
	.raise-row input {
		width: 70px;
		padding: 6px 8px;
		font: inherit;
		font-size: 0.85em;
		color: var(--ink-0);
		background: rgba(0, 0, 0, 0.35);
		border: 1px solid rgba(168, 85, 247, 0.3);
		border-radius: 6px;
		font-variant-numeric: tabular-nums;
	}
	.raise-row input:focus {
		outline: none;
		border-color: var(--purple-3);
	}
	.raise-hint {
		font-size: 0.7em;
		color: var(--ink-2);
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	/* Right-click context menu */
	.menu {
		position: fixed;
		z-index: 50;
		min-width: 180px;
		padding: 6px;
		background: linear-gradient(160deg, rgba(45, 27, 78, 0.98) 0%, rgba(20, 8, 42, 0.98) 100%);
		border: 1px solid rgba(168, 85, 247, 0.5);
		border-radius: 10px;
		box-shadow:
			0 12px 36px rgba(0, 0, 0, 0.6),
			0 0 24px rgba(168, 85, 247, 0.25),
			inset 0 1px 0 rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(8px);
	}
	.menu-header {
		padding: 6px 10px 8px;
		font-size: 0.72em;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--ink-2);
		border-bottom: 1px solid rgba(168, 85, 247, 0.2);
		margin-bottom: 4px;
	}
	.menu-item {
		display: block;
		width: 100%;
		padding: 8px 12px;
		text-align: left;
		background: transparent;
		border: none;
		color: var(--ink-0);
		font: inherit;
		font-size: 0.9em;
		border-radius: 6px;
		cursor: pointer;
		transition: background 0.1s;
	}
	.menu-item:hover {
		background: rgba(168, 85, 247, 0.18);
	}
	.menu-item:focus-visible {
		outline: 2px solid var(--purple-3);
		outline-offset: -2px;
	}
</style>

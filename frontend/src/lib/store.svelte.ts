// Reactive table state, fed by the WebSocket event stream.
import type {
	ActionEvent,
	HandEnd,
	HandLabel,
	HandReplay,
	HandStart,
	HandSync,
	LeaderboardUpdate,
	SeatState,
	SeatsUpdate,
	ServerEvent,
	Showdown,
	Snapshot,
	StreetDeal,
	TableState
} from './types';

function emptyState(): TableState {
	return {
		connected: false,
		hand_id: null,
		button_seat: null,
		blinds: null,
		seats: [],
		board: [],
		pot: 0,
		current_actor: null,
		legal: null,
		leaderboard: [],
		last_event: ''
	};
}

// Pacing for replay (matches the runner's TURN/ACTION/STREET delays).
// Indexed by the event type that JUST played; we wait this long before the next.
const REPLAY_DELAY_MS: Record<string, number> = {
	hand_start: 200,
	actor_turn: 700,
	action: 1200,
	street_deal: 1500,
	showdown: 1500,
	hand_end: 0
};

class Store {
	liveState: TableState = $state(emptyState());
	replayState: TableState | null = $state(null);
	replayActive: boolean = $state(false);
	replayHandId: number | null = $state(null);
	hasReplayAvailable: boolean = $state(false);

	private ws: WebSocket | null = null;
	private replayCancelled = false;

	get state(): TableState {
		return this.replayState ?? this.liveState;
	}

	private apply(ev: ServerEvent) {
		// Live events always update liveState so it stays current even during replay.
		this.applyTo(this.liveState, ev);
		if (ev.type === 'hand_end') this.hasReplayAvailable = true;
	}

	private applyTo(target: TableState, ev: ServerEvent) {
		target.last_event = ev.type;
		switch (ev.type) {
			case 'snapshot':
				this.applySnapshot(target, ev as Snapshot);
				break;
			case 'hand_start':
				this.applyHandStart(target, ev as HandStart);
				break;
			case 'actor_turn':
				target.current_actor = ev.seat;
				target.legal = {
					to_call: ev.to_call,
					min_raise: ev.min_raise,
					max_raise: ev.max_raise
				};
				break;
			case 'action':
				this.applyAction(target, ev as ActionEvent);
				break;
			case 'street_deal':
				this.applyStreetDeal(target, ev as StreetDeal);
				break;
			case 'showdown':
				this.applyShowdown(target, ev as Showdown);
				break;
			case 'hand_end':
				this.applyHandEnd(target, ev as HandEnd);
				break;
			case 'leaderboard':
				target.leaderboard = (ev as LeaderboardUpdate).entries;
				break;
			case 'seats_update':
				this.applySeatsUpdate(target, ev as SeatsUpdate);
				break;
			case 'hand_sync':
				this.applyHandSync(target, ev as HandSync);
				break;
		}
	}

	private applySnapshot(target: TableState, ev: Snapshot) {
		target.leaderboard = ev.leaderboard;
		const sittingOut = new Set(ev.sitting_out ?? []);
		for (const s of target.seats) s.sitting_out = sittingOut.has(s.seat);
	}

	private applyHandStart(target: TableState, ev: HandStart) {
		target.hand_id = ev.hand_id;
		target.button_seat = ev.button_seat;
		target.blinds = ev.blinds;
		target.board = [];
		target.pot = 0;
		target.current_actor = null;
		target.legal = null;
		target.seats = ev.seats.map<SeatState>((s) => ({
			seat: s.seat,
			bot_name: s.bot_name,
			stack: s.starting_stack,
			bet: 0,
			folded: false,
			hole_cards: s.hole_cards,
			last_action: null,
			hand_label: null,
			sitting_out: !!s.sitting_out,
			is_human: !!s.is_human
		}));
	}

	private applyAction(target: TableState, ev: ActionEvent) {
		target.pot = ev.pot;
		const seat = target.seats[ev.seat];
		if (seat) {
			seat.last_action = ev.action;
			if (ev.action.kind === 'fold') seat.folded = true;
		}
		for (let i = 0; i < target.seats.length; i++) {
			target.seats[i].stack = ev.stacks[i];
			target.seats[i].bet = ev.bets[i];
		}
		target.legal = null;
	}

	private applyStreetDeal(target: TableState, ev: StreetDeal) {
		target.board = ev.board;
		this.applyHandLabels(target, ev.hand_labels);
		for (const s of target.seats) {
			s.bet = 0;
			s.last_action = null;
		}
	}

	private applyHandLabels(target: TableState, labels: Record<number, HandLabel>) {
		for (const s of target.seats) {
			const label = labels[s.seat] ?? labels[String(s.seat) as unknown as number];
			s.hand_label = label ?? (s.folded ? null : s.hand_label);
		}
	}

	private applyShowdown(target: TableState, ev: Showdown) {
		for (const [seatStr, cards] of Object.entries(ev.hole_cards)) {
			const seat = target.seats[Number(seatStr)];
			if (seat) seat.hole_cards = cards;
		}
	}

	private applyHandEnd(target: TableState, ev: HandEnd) {
		target.board = ev.board;
		target.current_actor = null;
		this.applyHandLabels(target, ev.hand_labels);
		for (let i = 0; i < target.seats.length; i++) {
			target.seats[i].stack = ev.final_stacks[i];
		}
	}

	private applySeatsUpdate(target: TableState, ev: SeatsUpdate) {
		const sittingOut = new Set(ev.sitting_out);
		for (const s of target.seats) s.sitting_out = sittingOut.has(s.seat);
	}

	private applyHandSync(target: TableState, ev: HandSync) {
		target.hand_id = ev.hand_id;
		target.button_seat = ev.button_seat;
		target.blinds = ev.blinds;
		target.board = ev.board;
		target.pot = ev.pot;
		target.current_actor = ev.current_actor;
		target.legal = ev.current_actor !== null
			? { to_call: ev.to_call, min_raise: ev.min_raise, max_raise: ev.max_raise }
			: null;
		target.seats = ev.seats.map<SeatState>((s, i) => {
			const label = ev.hand_labels[s.seat] ?? ev.hand_labels[String(s.seat) as unknown as number];
			return {
				seat: s.seat,
				bot_name: s.bot_name,
				stack: ev.stacks[i],
				bet: ev.bets[i],
				folded: ev.folded[i],
				hole_cards: s.hole_cards,
				last_action: null,
				hand_label: label ?? null,
				sitting_out: !!s.sitting_out,
				is_human: !!s.is_human
			};
		});
	}

	private send(payload: object) {
		if (this.ws && this.ws.readyState === WebSocket.OPEN) {
			this.ws.send(JSON.stringify(payload));
		}
	}

	sitOut(seat: number) {
		this.send({ cmd: 'sit_out', seat });
	}

	sitIn(seat: number) {
		this.send({ cmd: 'sit_in', seat });
	}

	act(seat: number, kind: 'fold' | 'check_call' | 'raise_to', amount = 0) {
		this.send({ cmd: 'act', seat, kind, amount });
	}

	requestReplay() {
		if (this.replayActive) return;
		this.send({ cmd: 'replay_last' });
	}

	stopReplay() {
		this.replayCancelled = true;
		this.replayActive = false;
		this.replayState = null;
		this.replayHandId = null;
	}

	private async startReplay(payload: HandReplay) {
		this.replayCancelled = false;
		this.replayActive = true;
		this.replayHandId = payload.hand_id;
		const fresh = emptyState();
		fresh.connected = true;
		// keep the live leaderboard visible during replay
		fresh.leaderboard = this.liveState.leaderboard;
		this.replayState = fresh;
		let prev: string | null = null;
		for (const ev of payload.events) {
			if (this.replayCancelled) return;
			const wait = prev !== null ? REPLAY_DELAY_MS[prev] ?? 0 : 0;
			if (wait > 0) await new Promise((r) => setTimeout(r, wait));
			if (this.replayCancelled || !this.replayState) return;
			this.applyTo(this.replayState, ev);
			prev = ev.type;
		}
		// Stay on the final state — user clicks Stop to return to live.
	}

	connect(url: string) {
		const ws = new WebSocket(url);
		this.ws = ws;
		ws.onopen = () => {
			this.liveState.connected = true;
		};
		ws.onclose = () => {
			this.liveState.connected = false;
			setTimeout(() => this.connect(url), 1500);
		};
		ws.onerror = () => ws.close();
		ws.onmessage = (msg) => {
			try {
				const ev = JSON.parse(msg.data);
				if (ev?.type === 'hand_replay') {
					this.startReplay(ev as HandReplay);
				} else {
					this.apply(ev as ServerEvent);
				}
			} catch (e) {
				console.error('bad ws message', e, msg.data);
			}
		};
	}
}

export const store = new Store();

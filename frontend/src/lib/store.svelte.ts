// Reactive table state, fed by the WebSocket event stream.
import type {
	ActionEvent,
	HandEnd,
	HandLabel,
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

class Store {
	state: TableState = $state(emptyState());
	private ws: WebSocket | null = null;
	private sittingOut: Set<number> = new Set();

	private apply(ev: ServerEvent) {
		this.state.last_event = ev.type;
		switch (ev.type) {
			case 'snapshot':
				this.applySnapshot(ev as Snapshot);
				break;
			case 'hand_start':
				this.applyHandStart(ev as HandStart);
				break;
			case 'actor_turn':
				this.state.current_actor = ev.seat;
				this.state.legal = {
					to_call: ev.to_call,
					min_raise: ev.min_raise,
					max_raise: ev.max_raise
				};
				break;
			case 'action':
				this.applyAction(ev as ActionEvent);
				break;
			case 'street_deal':
				this.applyStreetDeal(ev as StreetDeal);
				break;
			case 'showdown':
				this.applyShowdown(ev as Showdown);
				break;
			case 'hand_end':
				this.applyHandEnd(ev as HandEnd);
				break;
			case 'leaderboard':
				this.state.leaderboard = (ev as LeaderboardUpdate).entries;
				break;
			case 'seats_update':
				this.applySeatsUpdate(ev as SeatsUpdate);
				break;
			case 'hand_sync':
				this.applyHandSync(ev as HandSync);
				break;
		}
	}

	private applyHandSync(ev: HandSync) {
		this.state.hand_id = ev.hand_id;
		this.state.button_seat = ev.button_seat;
		this.state.blinds = ev.blinds;
		this.state.board = ev.board;
		this.state.pot = ev.pot;
		this.state.current_actor = ev.current_actor;
		this.state.legal = ev.current_actor !== null
			? { to_call: ev.to_call, min_raise: ev.min_raise, max_raise: ev.max_raise }
			: null;
		this.sittingOut = new Set(ev.seats.filter((s) => s.sitting_out).map((s) => s.seat));
		this.state.seats = ev.seats.map<SeatState>((s, i) => {
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

	private applySnapshot(ev: Snapshot) {
		this.state.leaderboard = ev.leaderboard;
		this.sittingOut = new Set(ev.sitting_out ?? []);
		// reflect on any seats already rendered
		for (const s of this.state.seats) {
			s.sitting_out = this.sittingOut.has(s.seat);
		}
	}

	private applyHandStart(ev: HandStart) {
		this.state.hand_id = ev.hand_id;
		this.state.button_seat = ev.button_seat;
		this.state.blinds = ev.blinds;
		this.state.board = [];
		this.state.pot = 0;
		this.state.current_actor = null;
		this.sittingOut = new Set(ev.seats.filter((s) => s.sitting_out).map((s) => s.seat));
		this.state.legal = null;
		this.state.seats = ev.seats.map<SeatState>((s) => ({
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

	private applyAction(ev: ActionEvent) {
		this.state.pot = ev.pot;
		const seat = this.state.seats[ev.seat];
		if (seat) {
			seat.stack = ev.stacks[ev.seat];
			seat.bet = ev.bets[ev.seat];
			seat.last_action = ev.action;
			if (ev.action.kind === 'fold') seat.folded = true;
		}
		for (let i = 0; i < this.state.seats.length; i++) {
			this.state.seats[i].stack = ev.stacks[i];
			this.state.seats[i].bet = ev.bets[i];
		}
		// Whoever just acted is no longer to act; the next actor_turn will repopulate.
		this.state.legal = null;
	}

	private applyStreetDeal(ev: StreetDeal) {
		this.state.board = ev.board;
		this.applyHandLabels(ev.hand_labels);
		for (const s of this.state.seats) {
			s.bet = 0;
			s.last_action = null;
		}
	}

	private applyHandLabels(labels: Record<number, HandLabel>) {
		for (const s of this.state.seats) {
			const label = labels[s.seat] ?? labels[String(s.seat) as unknown as number];
			s.hand_label = label ?? (s.folded ? null : s.hand_label);
		}
	}

	private applyShowdown(ev: Showdown) {
		for (const [seatStr, cards] of Object.entries(ev.hole_cards)) {
			const seat = this.state.seats[Number(seatStr)];
			if (seat) seat.hole_cards = cards;
		}
	}

	private applyHandEnd(ev: HandEnd) {
		this.state.board = ev.board;
		this.state.current_actor = null;
		this.applyHandLabels(ev.hand_labels);
		for (let i = 0; i < this.state.seats.length; i++) {
			this.state.seats[i].stack = ev.final_stacks[i];
		}
	}

	private applySeatsUpdate(ev: SeatsUpdate) {
		this.sittingOut = new Set(ev.sitting_out);
		for (const s of this.state.seats) {
			s.sitting_out = this.sittingOut.has(s.seat);
		}
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

	connect(url: string) {
		const ws = new WebSocket(url);
		this.ws = ws;
		ws.onopen = () => {
			this.state.connected = true;
		};
		ws.onclose = () => {
			this.state.connected = false;
			setTimeout(() => this.connect(url), 1500);
		};
		ws.onerror = () => ws.close();
		ws.onmessage = (msg) => {
			try {
				const ev = JSON.parse(msg.data) as ServerEvent;
				this.apply(ev);
			} catch (e) {
				console.error('bad ws message', e, msg.data);
			}
		};
	}
}

export const store = new Store();

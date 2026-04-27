// Reactive table state, fed by the WebSocket event stream.
import type {
	ActionEvent,
	HandEnd,
	HandStart,
	LeaderboardUpdate,
	SeatState,
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
		leaderboard: [],
		last_event: ''
	};
}

class Store {
	state: TableState = $state(emptyState());

	private apply(ev: ServerEvent) {
		this.state.last_event = ev.type;
		switch (ev.type) {
			case 'snapshot':
				this.state.leaderboard = (ev as Snapshot).leaderboard;
				break;
			case 'hand_start':
				this.applyHandStart(ev as HandStart);
				break;
			case 'actor_turn':
				this.state.current_actor = ev.seat;
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
		}
	}

	private applyHandStart(ev: HandStart) {
		this.state.hand_id = ev.hand_id;
		this.state.button_seat = ev.button_seat;
		this.state.blinds = ev.blinds;
		this.state.board = [];
		this.state.pot = 0;
		this.state.current_actor = null;
		this.state.seats = ev.seats.map<SeatState>((s) => ({
			seat: s.seat,
			bot_name: s.bot_name,
			stack: s.starting_stack,
			bet: 0,
			folded: false,
			hole_cards: s.hole_cards,
			last_action: null
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
		// keep all bets/stacks fresh
		for (let i = 0; i < this.state.seats.length; i++) {
			this.state.seats[i].stack = ev.stacks[i];
			this.state.seats[i].bet = ev.bets[i];
		}
		this.state.current_actor = null;
	}

	private applyStreetDeal(ev: StreetDeal) {
		this.state.board = ev.board;
		// new street resets per-street bets and last actions in the UI
		for (const s of this.state.seats) {
			s.bet = 0;
			s.last_action = null;
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
		// stacks at this point are post-pull (after winnings); show those
		for (let i = 0; i < this.state.seats.length; i++) {
			this.state.seats[i].stack = ev.final_stacks[i];
		}
	}

	connect(url: string) {
		const ws = new WebSocket(url);
		ws.onopen = () => {
			this.state.connected = true;
		};
		ws.onclose = () => {
			this.state.connected = false;
			// retry after a short delay so the page survives a backend restart
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

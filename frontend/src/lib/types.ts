// Mirrors backend/events.py — keep in sync if backend schemas change.

export type ActionKind = 'fold' | 'check_call' | 'raise_to';

export interface Action {
	kind: ActionKind;
	amount: number;
}

export interface SeatInfo {
	seat: number;
	bot_name: string;
	starting_stack: number;
	hole_cards: string[];
	sitting_out?: boolean;
	is_human?: boolean;
}

export interface HandLabel {
	text: string;       // 'Pair of 8s', 'Aces full of Ks'
	category: string;   // raw pokerkit category, used for color tier
}

export interface HandStart {
	type: 'hand_start';
	hand_id: number;
	button_seat: number;
	blinds: [number, number];
	seats: SeatInfo[];
}

export interface ActorTurn {
	type: 'actor_turn';
	seat: number;
	to_call: number;
	min_raise: number;
	max_raise: number;
}

export interface ActionEvent {
	type: 'action';
	seat: number;
	bot_name: string;
	action: Action;
	pot: number;
	stacks: number[];
	bets: number[];
}

export interface StreetDeal {
	type: 'street_deal';
	street: 'flop' | 'turn' | 'river';
	board: string[];
	hand_labels: Record<number, HandLabel>;
}

export interface Showdown {
	type: 'showdown';
	hole_cards: Record<number, string[]>;
}

export interface HandEnd {
	type: 'hand_end';
	hand_id: number;
	payoffs: Record<number, number>;
	final_stacks: number[];
	board: string[];
	hand_labels: Record<number, HandLabel>;
}

export interface LeaderboardEntry {
	bot_name: string;
	hands_played: number;
	net_chips: number;
}

export interface LeaderboardUpdate {
	type: 'leaderboard';
	entries: LeaderboardEntry[];
}

export interface SeatsUpdate {
	type: 'seats_update';
	sitting_out: number[];
}

export interface Snapshot {
	type: 'snapshot';
	bots: string[];
	leaderboard: LeaderboardEntry[];
	in_hand: boolean;
	current_hand_id: number | null;
	sitting_out?: number[];
}

export interface HandSync {
	type: 'hand_sync';
	hand_id: number;
	button_seat: number;
	blinds: [number, number];
	seats: SeatInfo[];
	board: string[];
	pot: number;
	stacks: number[];
	bets: number[];
	folded: boolean[];
	hand_labels: Record<number, HandLabel>;
	current_actor: number | null;
	to_call: number;
	min_raise: number;
	max_raise: number;
}

export type ServerEvent =
	| HandStart
	| ActorTurn
	| ActionEvent
	| StreetDeal
	| Showdown
	| HandEnd
	| LeaderboardUpdate
	| SeatsUpdate
	| Snapshot
	| HandSync;

// --- UI state derived from event stream ---

export interface SeatState {
	seat: number;
	bot_name: string;
	stack: number;
	bet: number;
	folded: boolean;
	hole_cards: string[] | null; // null = hidden (other player); [] = mucked
	last_action: Action | null;
	hand_label: HandLabel | null; // null preflop or folded
	sitting_out: boolean;
	is_human: boolean;
}

export interface LegalActions {
	to_call: number;
	min_raise: number;
	max_raise: number;
}

export interface TableState {
	connected: boolean;
	hand_id: number | null;
	button_seat: number | null;
	blinds: [number, number] | null;
	seats: SeatState[];
	board: string[];
	pot: number;
	current_actor: number | null;
	legal: LegalActions | null;
	leaderboard: LeaderboardEntry[];
	last_event: string;
}

# engine.py
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple
from evaluator import best_of_7

Street = Literal["PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN", "HAND_OVER"]

@dataclass
class GameParams:
    starting_stack: int = 10000
    sb: int = 50
    bb: int = 100
    max_hands: int = 2000  # failsafe
    # decision time is enforced by runner, not engine

def _make_deck(rng: random.Random) -> List[str]:
    ranks = "23456789TJQKA"
    suits = "cdhs"
    deck = [r + s for r in ranks for s in suits]
    rng.shuffle(deck)
    return deck

class Hand:
    def __init__(self, params: GameParams, stacks: Dict[int, int], button: int, hand_seed: int):
        self.params = params
        self.rng = random.Random(hand_seed)
        self.deck = _make_deck(self.rng)

        self.stacks = dict(stacks)  # remaining stack
        
        # Get active players (those with chips)
        self.players = sorted([p for p, s in stacks.items() if s > 0])
        self.num_players = len(self.players)
        
        if self.num_players < 2:
            raise ValueError(f"Need at least 2 players, got {self.num_players}")
        
        # Find button position in active players list
        if button not in self.players:
            # Button player eliminated, use first active player
            self.button = self.players[0]
        else:
            self.button = button
        
        button_idx = self.players.index(self.button)
        self.sb_player = self.players[(button_idx + 1) % self.num_players]
        self.bb_player = self.players[(button_idx + 2) % self.num_players]

        # Initialize data structures for all active players
        self.hole: Dict[int, List[str]] = {p: [] for p in self.players}
        self.board: List[str] = []
        self.contrib_total: Dict[int, int] = {p: 0 for p in self.players}
        self.bets_street: Dict[int, int] = {p: 0 for p in self.players}
        
        # Track players who folded (still in hand but can't win)
        self.folded: set[int] = set()

        self.street: Street = "PREFLOP"
        self.current_bet = 0

        # For min-raise rule: track last raise increment on this street
        self.last_raise_inc = self.params.bb

        # Closing player concept: betting round ends when action returns here after no raise.
        # Preflop: BB is last to act, so action closes when it returns to BB
        self.closing_player: int = self.bb_player
        # Preflop: UTG (player after BB) acts first, or SB if only 2 players
        if self.num_players == 2:
            self.to_act: int = self.button  # SB acts first in HU
        else:
            # UTG is 3 positions after button
            self.to_act = self.players[(button_idx + 3) % self.num_players]

        self.action_history: List[dict] = []

        self._post_blinds()
        self._deal_hole()

    def _take_from_stack(self, p: int, amount: int) -> int:
        actual = min(amount, self.stacks[p])
        self.stacks[p] -= actual
        self.contrib_total[p] += actual
        self.bets_street[p] += actual
        return actual
    
    def _next_player(self, current: int) -> int:
        """Get next active player clockwise from current."""
        if current not in self.players:
            return self.players[0]
        idx = self.players.index(current)
        return self.players[(idx + 1) % self.num_players]
    
    def _prev_player(self, current: int) -> int:
        """Get previous active player counter-clockwise."""
        if current not in self.players:
            return self.players[-1]
        idx = self.players.index(current)
        return self.players[(idx - 1) % self.num_players]

    def _post_blinds(self):
        sb_paid = self._take_from_stack(self.sb_player, self.params.sb)
        bb_paid = self._take_from_stack(self.bb_player, self.params.bb)
        self.current_bet = max(self.bets_street.values()) if self.bets_street else 0
        self.last_raise_inc = self.params.bb
        self.action_history.append({"street": "PREFLOP", "actor": self.sb_player, "action": "POST_SB", "amount": sb_paid})
        self.action_history.append({"street": "PREFLOP", "actor": self.bb_player, "action": "POST_BB", "amount": bb_paid})

    def _deal_hole(self):
        for _ in range(2):
            for p in self.players:
                self.hole[p].append(self.deck.pop())

    def pot(self) -> int:
        return sum(self.contrib_total.values())

    def _street_to_deal(self):
        if self.street == "FLOP":
            self.board += [self.deck.pop(), self.deck.pop(), self.deck.pop()]
        elif self.street == "TURN":
            self.board.append(self.deck.pop())
        elif self.street == "RIVER":
            self.board.append(self.deck.pop())
        else:
            raise ValueError("No dealing for this street")

    def _new_street(self, street: Street):
        self.street = street
        self.bets_street = {p: 0 for p in self.players}
        self.current_bet = 0
        self.last_raise_inc = self.params.bb

        # Postflop: first to act is player after button (SB in multiway)
        if street in ("FLOP", "TURN", "RIVER"):
            button_idx = self.players.index(self.button)
            self.to_act = self.sb_player
            self.closing_player = self.button  # Action closes when it returns to button
        else:
            raise ValueError("Invalid new street")

    def _bets_equal_or_allin(self) -> bool:
        """Check if all active (non-folded, non-all-in) players have matched bets."""
        # Get active players (not folded, have chips)
        active = [p for p in self.players if p not in self.folded and self.stacks[p] > 0]
        if not active:
            return True  # All folded or all-in
        
        # All active players must have same bet
        active_bets = [self.bets_street[p] for p in active]
        return len(set(active_bets)) == 1

    def legal_actions(self, p: int) -> Dict[str, dict]:
        if self.street in ("SHOWDOWN", "HAND_OVER"):
            return {}
        if self.stacks[p] == 0:
            return {}  # all-in players don't act

        to_call = self.current_bet - self.bets_street[p]
        acts: Dict[str, dict] = {}

        if to_call > 0:
            acts["FOLD"] = {}
            acts["CALL"] = {"call_amount": min(to_call, self.stacks[p])}
            # raise
            max_raise_to = self.bets_street[p] + to_call + self.stacks[p]
            min_raise_to = None
            # Minimum raise increment based on last_raise_inc
            min_inc = self.last_raise_inc
            # If raising, new current_bet must be at least current_bet + min_inc
            min_raise_to = self.current_bet + min_inc
            if max_raise_to > self.current_bet and max_raise_to >= min_raise_to:
                acts["RAISE"] = {"min_raise_to": min_raise_to, "max_raise_to": max_raise_to}
            elif max_raise_to > self.current_bet:
                # can still go all-in, but may be a non-reopening raise (we allow it)
                acts["RAISE"] = {"min_raise_to": max_raise_to, "max_raise_to": max_raise_to, "note": "all-in only"}
        else:
            acts["CHECK"] = {}
            max_bet_to = self.bets_street[p] + self.stacks[p]  # since to_call=0
            min_bet_to = self.params.bb  # simple: min bet = bb
            if max_bet_to >= min_bet_to and self.stacks[p] > 0:
                acts["RAISE"] = {"min_raise_to": min_bet_to, "max_raise_to": max_bet_to, "note": "this is a BET"}
        return acts

    def apply_action(self, p: int, action: dict) -> Optional[dict]:
        """
        Apply action. Returns a hand_result dict when hand ends, else None.
        action: {"action": "FOLD"/"CALL"/"CHECK"/"RAISE", ...}
        """
        if p != self.to_act:
            raise ValueError("Not this player's turn")
        if self.street in ("SHOWDOWN", "HAND_OVER"):
            raise ValueError("Hand already ended")
        if self.stacks[p] == 0:
            raise ValueError("All-in player cannot act")

        acts = self.legal_actions(p)
        a = action.get("action")
        if a not in acts:
            raise ValueError(f"Illegal action {a} for player {p}")

        to_call = self.current_bet - self.bets_street[p]

        if a == "FOLD":
            self.action_history.append({"street": self.street, "actor": p, "action": "FOLD"})
            self.folded.add(p)
            
            # Check if only one player remains (not folded)
            active = [pl for pl in self.players if pl not in self.folded]
            if len(active) == 1:
                return self._award_fold(active[0])
            
            # Continue betting round
            return self._advance_after_nonraise(p)

        if a == "CHECK":
            self.action_history.append({"street": self.street, "actor": p, "action": "CHECK"})
            return self._advance_after_nonraise(p)

        if a == "CALL":
            pay = min(to_call, self.stacks[p])
            self._take_from_stack(p, pay)
            self.action_history.append({"street": self.street, "actor": p, "action": "CALL", "amount": pay})
            return self._advance_after_nonraise(p)

        if a == "RAISE":
            raise_to = int(action.get("to"))
            info = acts["RAISE"]
            min_to = int(info["min_raise_to"])
            max_to = int(info["max_raise_to"])
            if raise_to < min_to or raise_to > max_to:
                raise ValueError(f"Raise-to out of bounds: {raise_to} not in [{min_to},{max_to}]")

            # need to pay to_call first, then extra
            new_current_bet = raise_to
            inc = new_current_bet - self.current_bet
            # take required chips from stack
            needed = (new_current_bet - self.bets_street[p])
            self._take_from_stack(p, needed)

            # update raise tracking
            if inc > 0:
                self.last_raise_inc = inc  # simplified (all-in non-reopen still changes here, ok for MVP)
            self.current_bet = max(self.bets_street.values()) if self.bets_street else 0
            self.closing_player = p  # action must return to raiser to close
            self.action_history.append({"street": self.street, "actor": p, "action": "RAISE", "to": raise_to})
            
            # Move to next active player
            next_p = self._next_player(p)
            # Skip folded players and all-in players
            while (next_p in self.folded or self.stacks[next_p] == 0) and next_p != p:
                next_p = self._next_player(next_p)
            self.to_act = next_p
            return self._check_auto_runout()

        raise ValueError("Unhandled action")

    def _advance_after_nonraise(self, actor: int) -> Optional[dict]:
        """Move to next active player or close betting round."""
        # Find next active player (not folded, not all-in)
        next_p = self._next_player(actor)
        while (next_p in self.folded or self.stacks[next_p] == 0) and next_p != self.closing_player:
            next_p = self._next_player(next_p)
        
        self.to_act = next_p

        # If we've returned to closing player and bets are equal, close round
        if self.to_act == self.closing_player and self._bets_equal_or_allin():
            return self._close_betting_round()
        return self._check_auto_runout()

    def _close_betting_round(self) -> Optional[dict]:
        # Check if any active player is all-in and bets are matched
        active = [p for p in self.players if p not in self.folded and self.stacks[p] > 0]
        if not active:
            # All players all-in or folded, run out to showdown
            return self._runout_to_showdown()
        
        # Check if any player is all-in
        has_allin = any(self.stacks[p] == 0 for p in self.players if p not in self.folded)
        if has_allin and self._bets_equal_or_allin():
            return self._runout_to_showdown()

        # Advance street normally
        if self.street == "PREFLOP":
            self._new_street("FLOP")
            self._street_to_deal()
            return None
        if self.street == "FLOP":
            self._new_street("TURN")
            self._street_to_deal()
            return None
        if self.street == "TURN":
            self._new_street("RIVER")
            self._street_to_deal()
            return None
        if self.street == "RIVER":
            return self._showdown()
        raise ValueError("Bad street")

    def _check_auto_runout(self) -> Optional[dict]:
        """If all active players are all-in AND bets are equal, run out board."""
        active = [p for p in self.players if p not in self.folded and self.stacks[p] > 0]
        if not active and self._bets_equal_or_allin():
            # All players all-in, run out
            return self._runout_to_showdown()
        return None

    def _runout_to_showdown(self) -> dict:
        # deal remaining streets to river then showdown
        while self.street in ("PREFLOP", "FLOP", "TURN"):
            if self.street == "PREFLOP":
                self._new_street("FLOP")
                self._street_to_deal()
            elif self.street == "FLOP":
                self._new_street("TURN")
                self._street_to_deal()
            elif self.street == "TURN":
                self._new_street("RIVER")
                self._street_to_deal()
        if self.street == "RIVER":
            return self._showdown()
        raise ValueError("Unexpected runout state")

    def _award_fold(self, winner: int) -> dict:
        pot = self.pot()
        self.stacks[winner] += pot
        self.street = "HAND_OVER"
        return {
            "result": "FOLD",
            "winner": winner,
            "pot": pot,
            "final_stacks": dict(self.stacks),
            "board": list(self.board),
            "hole_reveal": {p: list(self.hole[p]) for p in self.players},
        }

    def _showdown(self) -> dict:
        """Handle showdown with multiple players and side pots."""
        # Get players who didn't fold (eligible for showdown)
        eligible = [p for p in self.players if p not in self.folded]
        
        if len(eligible) == 0:
            raise ValueError("No eligible players for showdown")
        if len(eligible) == 1:
            # Only one player, award entire pot
            winner = eligible[0]
            pot = self.pot()
            self.stacks[winner] += pot
            self.street = "HAND_OVER"
            return {
                "result": "SHOWDOWN",
                "winner": winner,
                "pot": pot,
                "final_stacks": dict(self.stacks),
                "board": list(self.board),
                "hole_reveal": {p: list(self.hole[p]) for p in self.players},
            }
        
        # Group players by contribution amount for side pot calculation
        contrib_levels = sorted(set(self.contrib_total[p] for p in eligible), reverse=True)
        
        # Calculate side pots
        pots = []
        for i, level in enumerate(contrib_levels):
            pot_eligible = [p for p in eligible if self.contrib_total[p] >= level]
            if i == 0:
                pot_size = level * len(pot_eligible)
            else:
                prev_level = contrib_levels[i-1]
                pot_size = (level - prev_level) * len(pot_eligible)
            
            if pot_size > 0:
                pots.append({
                    'size': pot_size,
                    'eligible': pot_eligible,
                    'level': level
                })
        
        # Evaluate hands for all eligible players
        hand_ranks = {}
        for p in eligible:
            if len(self.hole[p]) == 2:  # Only if player has cards
                hand_ranks[p] = best_of_7(self.hole[p] + self.board)
        
        # Award pots
        pot_winners = {}
        for pot_info in pots:
            pot_eligible = pot_info['eligible']
            eligible_hands = {p: hand_ranks[p] for p in pot_eligible if p in hand_ranks}
            
            if not eligible_hands:
                continue
            
            # Find winner(s) - best hand wins
            best_hand = max(eligible_hands.values())
            winners = [p for p, h in eligible_hands.items() if h == best_hand]
            
            # Split pot among winners
            per_winner = pot_info['size'] // len(winners)
            remainder = pot_info['size'] % len(winners)
            
            for i, winner in enumerate(winners):
                amount = per_winner + (1 if i < remainder else 0)
                self.stacks[winner] += amount
                if winner not in pot_winners:
                    pot_winners[winner] = 0
                pot_winners[winner] += amount
        
        self.street = "HAND_OVER"
        return {
            "result": "SHOWDOWN",
            "pot_winners": pot_winners,
            "pot": self.pot(),
            "final_stacks": dict(self.stacks),
            "board": list(self.board),
            "hole_reveal": {p: list(self.hole[p]) for p in self.players},
            "hand_ranks": hand_ranks,
        }

    def observation_for(self, p: int) -> dict:
        legal = self.legal_actions(p)
        return {
            "protocol_version": 1,
            "type": "act",
            "street": self.street,
            "to_act": self.to_act,
            "hero": p,
            "hero_hole": list(self.hole[p]),
            "board": list(self.board),
            "stacks": dict(self.stacks),
            "pot": self.pot(),
            "bets_street": dict(self.bets_street),
            "current_bet": self.current_bet,
            "to_call": max(0, self.current_bet - self.bets_street[p]),
            "legal_actions": legal,
            "action_history": list(self.action_history),
        }

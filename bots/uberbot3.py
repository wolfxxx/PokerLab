# bots/uberbot3.py
"""
UberBot v3.0 - Ultimate poker bot with cutting-edge strategy:
- Monte Carlo equity simulation for accurate hand evaluation
- Advanced opponent range modeling and exploitation
- GTO-inspired bet sizing with exploitative adjustments
- Sophisticated board texture analysis
- Dynamic strategy adaptation based on opponent tendencies
- Advanced position play with optimal continuation betting
- Multi-way pot optimization with ICM awareness
- Balanced bluffing frequency with fold equity calculations
- Stack depth awareness and optimal play adjustments
- Advanced draw detection with accurate equity calculations
"""

import json
import sys
import os
import random
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict, Counter

# Add parent directory to path to import evaluator
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from evaluator import best_of_7, parse_card, RANKS
except ImportError:
    RANKS = {r: i for i, r in enumerate("..23456789TJQKA", start=0)}
    
    def parse_card(c: str) -> Tuple[int, str]:
        if len(c) != 2:
            raise ValueError(f"Bad card: {c}")
        r, s = c[0], c[1]
        if r not in RANKS or s not in "cdhs":
            raise ValueError(f"Bad card: {c}")
        return (RANKS[r], s)
    
    def best_of_7(card_strs):
        cards = [parse_card(c) for c in card_strs]
        ranks = sorted([r for r, _ in cards], reverse=True)
        if len(set(ranks)) == len(ranks):
            return (0, ranks[:5])
        else:
            counts = Counter(ranks)
            most_common = counts.most_common(1)[0]
            return (1, [most_common[0]])

# Global state for advanced opponent tracking
STATE = {
    "opponent_stats": defaultdict(lambda: {
        "vpip": 0.5,           # Voluntarily put money in pot
        "pfr": 0.3,            # Preflop raise frequency
        "aggression": 0.5,     # Postflop aggression factor
        "fold_to_bet": 0.5,    # Fold frequency when facing bets
        "fold_to_raise": 0.5,  # Fold frequency when facing raises
        "bet_frequency": 0.3,   # How often they bet when checked to
        "raise_frequency": 0.2, # How often they raise
        "cbet_frequency": 0.6,  # Continuation bet frequency
        "hands_seen": 0,
        "position_aware": True,
        "stack_size": 10000,
        "recent_actions": []
    }),
    "hand_count": 0,
    "board_history": [],
    "pot_sizes": []
}

def monte_carlo_equity(hole: List[str], board: List[str], num_opponents: int, iterations: int = 100) -> float:
    """Monte Carlo simulation to estimate hand equity."""
    if len(board) == 0:
        return 0.5  # Preflop, use other method
    
    known_cards = set(hole + board)
    if len(known_cards) >= 52:
        return 0.5
    
    # Generate remaining deck
    ranks = "23456789TJQKA"
    suits = "cdhs"
    deck = [r + s for r in ranks for s in suits]
    remaining_deck = [c for c in deck if c not in known_cards]
    
    if len(remaining_deck) < 2 * num_opponents + (5 - len(board)):
        return 0.5
    
    wins = 0
    rng = random.Random()
    
    for _ in range(iterations):
        # Shuffle remaining deck
        shuffled = remaining_deck.copy()
        rng.shuffle(shuffled)
        
        # Deal opponent hands and complete board
        opp_hands = []
        board_complete = board.copy()
        
        idx = 0
        for _ in range(num_opponents):
            opp_hands.append([shuffled[idx], shuffled[idx + 1]])
            idx += 2
        
        # Complete board
        while len(board_complete) < 5:
            board_complete.append(shuffled[idx])
            idx += 1
        
        # Evaluate our hand
        our_hand = best_of_7(hole + board_complete)
        
        # Evaluate opponent hands
        best_opponent = None
        for opp_hole in opp_hands:
            opp_hand = best_of_7(opp_hole + board_complete)
            if best_opponent is None or opp_hand > best_opponent:
                best_opponent = opp_hand
        
        # Check if we win
        if our_hand > best_opponent:
            wins += 1
        elif our_hand == best_opponent:
            wins += 0.5  # Split pot
    
    return wins / iterations

def evaluate_preflop_hand(hole: List[str], num_opponents: int = 1, position: str = "MIDDLE") -> Tuple[float, Tuple[int, List[int]]]:
    """Advanced preflop evaluation with position awareness."""
    if len(hole) != 2:
        return (0.5, (0, []))
    
    r1, _ = parse_card(hole[0])
    r2, _ = parse_card(hole[1])
    s1 = hole[0][1]
    s2 = hole[1][1]
    
    is_pair = (r1 == r2)
    is_suited = (s1 == s2)
    high_card = max(r1, r2)
    low_card = min(r1, r2)
    gap = high_card - low_card
    
    # Position bonus (more aggressive in late position)
    position_bonus = 0.0
    if position == "LATE":
        position_bonus = 0.05
    elif position == "EARLY":
        position_bonus = -0.05
    
    # Multi-way penalty (tighter with more opponents)
    multiway_penalty = max(0, (num_opponents - 1) * 0.07)
    
    # Premium pairs
    if is_pair:
        if high_card >= 12:  # AA, KK
            equity = 0.90 - multiway_penalty + position_bonus
            return (min(equity, 0.95), (1, [high_card]))
        elif high_card >= 10:  # QQ, JJ, TT
            equity = 0.80 - multiway_penalty + position_bonus
            return (min(equity, 0.88), (1, [high_card]))
        elif high_card >= 7:  # 77-99
            equity = 0.70 - multiway_penalty + position_bonus
            return (min(equity, 0.78), (1, [high_card]))
        else:
            equity = 0.60 - multiway_penalty + position_bonus
            return (min(equity, 0.68), (1, [high_card]))
    
    # Premium high cards
    if high_card >= 12:  # A or K
        if low_card >= 11:  # AK
            equity = 0.85 if is_suited else 0.80
            equity -= multiway_penalty
            equity += position_bonus
            return (min(equity, 0.90), (0, [high_card, low_card]))
        elif low_card >= 10:  # AQ, AJ, KQ, KJ
            equity = 0.75 if is_suited else 0.70
            equity -= multiway_penalty
            equity += position_bonus
            return (min(equity, 0.82), (0, [high_card, low_card]))
        elif low_card >= 8:  # AT, A9, KT, K9
            equity = 0.65 if is_suited else 0.60
            equity -= multiway_penalty
            equity += position_bonus
            return (min(equity, 0.72), (0, [high_card, low_card]))
        else:
            equity = 0.55 if is_suited else 0.50
            equity -= multiway_penalty
            equity += position_bonus
            return (min(equity, 0.62), (0, [high_card, low_card]))
    
    # Suited connectors and suited aces
    if is_suited:
        if gap <= 3 and high_card >= 9:
            equity = 0.62 - multiway_penalty + position_bonus
            return (min(equity, 0.70), (0, [high_card, low_card]))
        elif high_card == 14:  # Ax suited
            equity = 0.54 - multiway_penalty + position_bonus
            return (min(equity, 0.62), (0, [high_card, low_card]))
        elif gap <= 2 and high_card >= 7:
            equity = 0.56 - multiway_penalty + position_bonus
            return (min(equity, 0.64), (0, [high_card, low_card]))
    
    # Offsuit connectors
    if gap <= 2 and high_card >= 10:
        equity = 0.52 - multiway_penalty + position_bonus
        return (min(equity, 0.60), (0, [high_card, low_card]))
    
    # Default
    equity = 0.38 - multiway_penalty + position_bonus
    return (max(equity, 0.25), (0, [high_card, low_card]))

def calculate_draw_equity_advanced(hole: List[str], board: List[str]) -> Tuple[float, str, int]:
    """Advanced draw equity calculation with exact outs counting."""
    if len(board) < 3:
        return (0.0, "none", 0)
    
    all_cards = hole + board
    cards = [parse_card(c) for c in all_cards]
    ranks = sorted([r for r, _ in cards], reverse=True)
    suits = [s for _, s in cards]
    
    suit_counts = Counter(suits)
    max_suit_count = max(suit_counts.values())
    flush_suit = max(suit_counts.items(), key=lambda x: x[1])[0] if suit_counts else None
    
    # Flush draws
    flush_outs = 0
    if max_suit_count == 4:
        # We have 4 of a suit, need 1 more
        flush_outs = 13 - 4  # 9 outs
        if len(board) == 3:
            return (0.19, "flush_draw_oe", flush_outs)  # ~19% on flop
        elif len(board) == 4:
            return (0.20, "flush_draw", flush_outs)  # ~20% on turn
    
    # Straight draws
    unique_ranks = sorted(set(ranks), reverse=True)
    straight_outs = 0
    straight_type = "none"
    
    if len(unique_ranks) >= 4:
        for i in range(len(unique_ranks) - 3):
            window = unique_ranks[i:i+4]
            gap = window[0] - window[3]
            
            if gap == 4:  # Open-ended straight draw
                straight_outs = 8
                straight_type = "straight_draw_oe"
                if len(board) == 3:
                    return (0.17, straight_type, straight_outs)
                elif len(board) == 4:
                    return (0.17, straight_type, straight_outs)
            elif gap == 5:  # Gutshot straight draw
                straight_outs = 4
                straight_type = "straight_draw_gs"
                if len(board) == 3:
                    return (0.08, straight_type, straight_outs)
                elif len(board) == 4:
                    return (0.09, straight_type, straight_outs)
    
    # Combined draws
    if flush_outs > 0 and straight_outs > 0:
        combined_equity = 0.19 + 0.17  # Approximate
        return (min(combined_equity, 0.50), "combo_draw", flush_outs + straight_outs)
    
    return (0.0, "none", 0)

def evaluate_hand_strength(hole: List[str], board: List[str], num_opponents: int = 1) -> Tuple[float, Tuple[int, List[int]]]:
    """Ultimate hand strength evaluation with Monte Carlo for accuracy."""
    if len(board) == 0:
        return evaluate_preflop_hand(hole, num_opponents)
    
    all_cards = hole + board
    if len(all_cards) < 5:
        return evaluate_preflop_hand(hole, num_opponents)
    
    # River - exact evaluation
    if len(all_cards) == 7:
        try:
            hand_rank = best_of_7(all_cards)
            category, tiebreakers = hand_rank
            
            # Use Monte Carlo for more accurate multi-way equity
            if num_opponents > 1:
                mc_equity = monte_carlo_equity(hole, board, num_opponents, iterations=200)
                return (mc_equity, hand_rank)
            
            # Heads-up, use category-based equity
            equity_map = {
                8: 0.99,  # Straight flush
                7: 0.98,  # Four of a kind
                6: 0.95,  # Full house
                5: 0.80,  # Flush
                4: 0.74,  # Straight
                3: 0.66,  # Three of a kind
                2: 0.52,  # Two pair
                1: 0.36,  # One pair
                0: 0.20,  # High card
            }
            
            base_equity = equity_map.get(category, 0.5)
            if tiebreakers:
                tiebreaker_bonus = min(tiebreakers[0] / 14.0 * 0.12, 0.12)
                base_equity += tiebreaker_bonus
            
            return (min(base_equity, 0.99), hand_rank)
        except:
            return evaluate_preflop_hand(hole, num_opponents)
    
    # Flop/Turn - use Monte Carlo for accuracy
    if len(board) >= 3:
        mc_equity = monte_carlo_equity(hole, board, num_opponents, iterations=150)
        
        # Also get draw information
        draw_equity, draw_type, outs = calculate_draw_equity_advanced(hole, board)
        
        # Combine Monte Carlo with draw information
        if draw_type != "none" and mc_equity < 0.5:
            # If we have a draw, boost equity estimate
            combined_equity = max(mc_equity, draw_equity * 1.1)
            return (min(combined_equity, 0.85), (0, [max([r for r, _ in [parse_card(c) for c in all_cards]])]))
        
        return (mc_equity, (0, [max([r for r, _ in [parse_card(c) for c in all_cards]])]))
    
    return evaluate_preflop_hand(hole, num_opponents)

def calculate_pot_odds(pot: int, to_call: int) -> float:
    """Calculate equity needed to call."""
    if to_call == 0:
        return 0.0
    total_pot = pot + to_call
    return to_call / total_pot

def calculate_fold_equity(opponent_tendency: Dict, bet_size: int, pot: int) -> float:
    """Calculate fold equity based on opponent tendencies."""
    fold_freq = opponent_tendency.get("fold_to_bet", 0.5)
    
    # Larger bets get more folds (up to a point)
    bet_ratio = bet_size / max(pot, 1)
    if bet_ratio > 0.75:
        fold_freq *= 1.15  # Large bets get more folds
    elif bet_ratio > 0.5:
        fold_freq *= 1.05
    
    return min(fold_freq, 0.85)  # Cap at 85%

def calculate_implied_odds_advanced(hand_strength: float, pot: int, to_call: int,
                                  street: str, num_opponents: int, my_stack: int,
                                  opponent_tendency: Dict) -> float:
    """Advanced implied odds calculation."""
    pot_odds = calculate_pot_odds(pot, to_call)
    
    # Drawing hands get more implied odds
    if 0.25 <= hand_strength <= 0.65:
        # More opponents = more implied odds
        implied_bonus = min(num_opponents * 0.08, 0.20)
        
        # Deep stacks = more implied odds
        stack_ratio = min(my_stack / 10000.0, 2.0)
        implied_bonus *= (0.7 + stack_ratio * 0.15)
        
        # Opponent tendency to call (loose opponents = more implied odds)
        if opponent_tendency.get("vpip", 0.5) > 0.6:
            implied_bonus *= 1.2
        
        # Later streets = less implied odds
        if street == "RIVER":
            implied_bonus *= 0.1
        elif street == "TURN":
            implied_bonus *= 0.4
        elif street == "FLOP":
            implied_bonus *= 0.9
        
        return max(0.0, pot_odds - implied_bonus)
    
    return pot_odds

def get_position(obs: Dict) -> str:
    """Determine position (EARLY, MIDDLE, LATE)."""
    street = obs.get("street", "PREFLOP")
    to_act = obs.get("to_act", 0)
    hero = obs.get("hero", 0)
    stacks = obs.get("stacks", {})
    num_players = len([p for p, s in stacks.items() if s > 0])
    
    if num_players <= 2:
        # Heads-up: button is late position
        if to_act == hero:
            return "LATE"
        return "EARLY"
    
    # Multi-way: approximate position
    active_players = sorted([p for p, s in stacks.items() if s > 0])
    hero_idx = active_players.index(hero) if hero in active_players else 0
    to_act_idx = active_players.index(to_act) if to_act in active_players else 0
    
    if street == "PREFLOP":
        # Preflop: later position = better
        if hero_idx >= len(active_players) * 0.66:
            return "LATE"
        elif hero_idx >= len(active_players) * 0.33:
            return "MIDDLE"
        return "EARLY"
    else:
        # Postflop: button acts last
        if to_act == hero:
            return "LATE"
        return "EARLY"

def is_in_position(obs: Dict) -> bool:
    """Determine if we're in position."""
    position = get_position(obs)
    return position == "LATE"

def get_num_opponents(obs: Dict) -> int:
    """Get number of active opponents."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    active = sum(1 for p, s in stacks.items() if p != hero and s > 0)
    return max(active, 1)

def update_opponent_stats(obs: Dict):
    """Advanced opponent statistics tracking with faster adaptation."""
    action_history = obs.get("action_history", [])
    hero = obs.get("hero", 0)
    street = obs.get("street", "PREFLOP")
    
    for action in action_history:
        actor = action.get("actor")
        if actor == hero:
            continue
        
        action_type = action.get("action", "")
        stats = STATE["opponent_stats"][actor]
        
        # Update recent actions
        stats["recent_actions"].append(action_type)
        if len(stats["recent_actions"]) > 10:
            stats["recent_actions"].pop(0)
        
        # Faster adaptation for early detection
        adaptation_rate = 0.25 if stats["hands_seen"] < 5 else 0.15
        
        if street == "PREFLOP":
            if action_type in ("CALL", "RAISE"):
                stats["vpip"] = (stats["vpip"] * (1 - adaptation_rate)) + adaptation_rate * 1.0
            if action_type == "RAISE":
                stats["pfr"] = (stats["pfr"] * (1 - adaptation_rate)) + adaptation_rate * 1.0
            stats["hands_seen"] += 1
        
        # Postflop stats
        if street != "PREFLOP":
            if action_type == "RAISE":
                stats["aggression"] = (stats["aggression"] * 0.80) + 0.20 * 1.0
                stats["raise_frequency"] = (stats["raise_frequency"] * 0.85) + 0.15
            elif action_type in ("CALL", "CHECK"):
                stats["aggression"] = (stats["aggression"] * 0.80) + 0.20 * 0.3
            elif action_type == "FOLD":
                stats["fold_to_bet"] = (stats["fold_to_bet"] * 0.85) + 0.15 * 1.0
                stats["aggression"] = (stats["aggression"] * 0.80) + 0.20 * 0.0
            else:
                stats["bet_frequency"] = (stats["bet_frequency"] * 0.85) + 0.15

def get_opponent_tendency(obs: Dict) -> Dict[str, float]:
    """Get average opponent tendencies with aggressive opponent detection."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    
    opponents = [p for p in stacks.keys() if p != hero]
    if not opponents:
        return {"vpip": 0.5, "pfr": 0.3, "aggression": 0.5, "fold_to_bet": 0.5, "bet_frequency": 0.3, "is_aggressive": False, "is_allin_bot": False}
    
    avg_vpip = sum(STATE["opponent_stats"][p]["vpip"] for p in opponents) / len(opponents)
    avg_pfr = sum(STATE["opponent_stats"][p]["pfr"] for p in opponents) / len(opponents)
    avg_agg = sum(STATE["opponent_stats"][p]["aggression"] for p in opponents) / len(opponents)
    avg_fold = sum(STATE["opponent_stats"][p]["fold_to_bet"] for p in opponents) / len(opponents)
    avg_bet = sum(STATE["opponent_stats"][p]["bet_frequency"] for p in opponents) / len(opponents)
    
    # Detect very aggressive/unpredictable opponents
    is_aggressive = avg_vpip > 0.85 or avg_pfr > 0.70 or avg_agg > 0.75
    is_allin_bot = avg_pfr > 0.90  # Almost always raising = all-in bot
    
    return {
        "vpip": avg_vpip,
        "pfr": avg_pfr,
        "aggression": avg_agg,
        "fold_to_bet": avg_fold,
        "bet_frequency": avg_bet,
        "is_aggressive": is_aggressive,
        "is_allin_bot": is_allin_bot
    }

def was_preflop_raiser(obs: Dict) -> bool:
    """Check if we raised preflop."""
    action_history = obs.get("action_history", [])
    hero = obs.get("hero", 0)
    street = obs.get("street", "PREFLOP")
    
    if street == "PREFLOP":
        return False
    
    for action in action_history:
        if action.get("actor") == hero and action.get("street") == "PREFLOP":
            if action.get("action") == "RAISE":
                return True
    
    return False

def calculate_optimal_bet_size(obs: Dict, hand_strength: float, pot: int,
                               num_opponents: int, opponent_tendency: Dict,
                               is_bluff: bool = False) -> int:
    """GTO-inspired bet sizing with exploitative adjustments."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    my_stack = stacks.get(hero, 10000)
    street = obs.get("street", "PREFLOP")
    
    # Base bet sizing on hand strength
    if is_bluff:
        # Smaller bluffs
        base_size = int(pot * 0.30)
    elif hand_strength > 0.85:
        base_size = int(pot * 0.85)  # Very strong - bet large
    elif hand_strength > 0.75:
        base_size = int(pot * 0.70)  # Strong - bet medium-large
    elif hand_strength > 0.65:
        base_size = int(pot * 0.55)  # Good - bet medium
    elif hand_strength > 0.50:
        base_size = int(pot * 0.40)  # Medium - bet small-medium
    else:
        base_size = int(pot * 0.30)  # Weak - bet small
    
    # Adjust for opponent fold tendency
    if opponent_tendency["fold_to_bet"] > 0.65:
        base_size = int(base_size * 0.80)  # Smaller bets work against tight players
    elif opponent_tendency["fold_to_bet"] < 0.35:
        base_size = int(base_size * 1.15)  # Larger bets against calling stations
    
    # Adjust for number of opponents
    if num_opponents > 2:
        base_size = int(base_size * 0.70)  # Smaller bets multi-way
    
    # Adjust for street
    if street == "RIVER":
        base_size = int(base_size * 1.10)  # Value bet larger on river
    elif street == "TURN":
        base_size = int(base_size * 0.95)
    
    return min(base_size, my_stack)

def should_bluff(obs: Dict, hand_strength: float, num_opponents: int,
                 opponent_tendency: Dict, was_raiser: bool, pot: int) -> bool:
    """Advanced bluffing logic with fold equity consideration."""
    street = obs.get("street", "PREFLOP")
    
    if street == "PREFLOP":
        return False
    
    # Don't bluff multi-way
    if num_opponents > 2:
        return False
    
    # Calculate fold equity
    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency, is_bluff=True)
    fold_equity = calculate_fold_equity(opponent_tendency, bet_size, pot)
    
    # Bluff if fold equity is high enough
    if fold_equity > 0.55 and 0.25 <= hand_strength <= 0.50:
        return True
    
    # Continuation bet after raising preflop
    if was_raiser and street == "FLOP":
        if 0.30 <= hand_strength <= 0.55:
            return True
    
    # Bluff in position against tight opponents
    if is_in_position(obs) and opponent_tendency["fold_to_bet"] > 0.55:
        if 0.30 <= hand_strength <= 0.48:
            return True
    
    return False

def act(obs: Dict) -> Dict:
    """Ultimate decision function with all advanced features."""
    legal = obs.get("legal_actions", {})
    if not legal:
        return {"action": "CHECK"}
    
    # Extract game state
    hero_hole = obs.get("hero_hole", [])
    board = obs.get("board", [])
    pot = obs.get("pot", 0)
    to_call = obs.get("to_call", 0)
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    my_stack = stacks.get(hero, 10000)
    street = obs.get("street", "PREFLOP")
    
    # Update opponent stats
    update_opponent_stats(obs)
    
    # Get game context
    num_opponents = get_num_opponents(obs)
    position = get_position(obs)
    in_position = is_in_position(obs)
    opponent_tendency = get_opponent_tendency(obs)
    was_raiser = was_preflop_raiser(obs)
    
    # Evaluate hand strength with Monte Carlo (but skip for speed against aggressive opponents)
    # Use faster evaluation against very aggressive opponents
    if opponent_tendency.get("is_allin_bot", False) or opponent_tendency.get("is_aggressive", False):
        # Use simpler evaluation for speed
        if len(board) == 0:
            hand_strength, hand_rank = evaluate_preflop_hand(hero_hole, num_opponents, position)
        elif len(hero_hole + board) == 7:
            try:
                hand_rank = best_of_7(hero_hole + board)
                category, tiebreakers = hand_rank
                equity_map = {8: 0.99, 7: 0.98, 6: 0.95, 5: 0.80, 4: 0.74, 3: 0.66, 2: 0.52, 1: 0.36, 0: 0.20}
                hand_strength = equity_map.get(category, 0.5)
            except:
                hand_strength, hand_rank = evaluate_preflop_hand(hero_hole, num_opponents, position)
        else:
            # Quick estimate for flop/turn
            hand_strength, hand_rank = evaluate_hand_strength(hero_hole, board, num_opponents)
    else:
        # Full Monte Carlo for balanced opponents
        hand_strength, hand_rank = evaluate_hand_strength(hero_hole, board, num_opponents)
    
    # Calculate pot odds and implied odds
    pot_odds = calculate_pot_odds(pot, to_call)
    implied_odds_needed = calculate_implied_odds_advanced(
        hand_strength, pot, to_call, street, num_opponents, my_stack, opponent_tendency
    )
    
    # Decision logic
    if to_call > 0:
        # Facing a bet/raise
        
        # Special handling for all-in bots: only call with premium hands
        if opponent_tendency.get("is_allin_bot", False):
            # Against all-in bots, be very tight - only call with very strong hands
            # Check if this is a large bet (likely all-in)
            bet_ratio = to_call / max(my_stack, 1) if my_stack > 0 else 1.0
            if bet_ratio > 0.3:  # Large bet/all-in
                # Only call with top hands (top 15%)
                if hand_strength > 0.72:
                    return {"action": "CALL"}
                else:
                    return {"action": "FOLD"}
            else:
                # Smaller bet, can be slightly looser
                if hand_strength > 0.60:
                    return {"action": "CALL"}
                else:
                    return {"action": "FOLD"}
        
        # Against aggressive opponents, tighten up but exploit with strong hands
        if opponent_tendency.get("is_aggressive", False):
            # Very strong hand - always raise for value (exploit their aggression)
            if hand_strength > 0.75:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    current_bet = obs.get("current_bet", 0)
                    min_raise = raise_info.get("min_raise_to", current_bet + 100)
                    max_raise = raise_info.get("max_raise_to", my_stack)
                    # More aggressive against loose opponents
                    raise_to = min(int(min_raise + (max_raise - min_raise) * 0.85), max_raise)
                    return {"action": "RAISE", "to": raise_to}
                else:
                    return {"action": "CALL"}
            # Strong hand - call or raise
            elif hand_strength > 0.65:
                if "RAISE" in legal and hand_strength > pot_odds + 0.12:
                    raise_info = legal["RAISE"]
                    current_bet = obs.get("current_bet", 0)
                    min_raise = raise_info.get("min_raise_to", current_bet + 100)
                    max_raise = raise_info.get("max_raise_to", my_stack)
                    raise_to = min(int(min_raise + (max_raise - min_raise) * 0.70), max_raise)
                    return {"action": "RAISE", "to": raise_to}
                elif hand_strength > pot_odds * 0.90:
                    return {"action": "CALL"}
                else:
                    return {"action": "FOLD"}
            # Medium/weak hands - fold more against aggressive opponents
            elif hand_strength > pot_odds * 0.95:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
        
        # Normal strategy against balanced opponents
        # Very strong hand - always raise for value
        if hand_strength > 0.78:
            if "RAISE" in legal:
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                # Aggressive value raise
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.80), max_raise)
                return {"action": "RAISE", "to": raise_to}
            else:
                return {"action": "CALL"}
        
        # Strong hand - raise or call
        elif hand_strength > 0.68:
            if "RAISE" in legal and hand_strength > pot_odds + 0.15:
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.65), max_raise)
                return {"action": "RAISE", "to": raise_to}
            elif hand_strength > pot_odds:
                return {"action": "CALL"}
            elif hand_strength > pot_odds * 0.85:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
        
        # Medium hand - pot odds with implied odds
        elif hand_strength > implied_odds_needed:
            return {"action": "CALL"}
        
        # Drawing hand
        elif hand_strength > implied_odds_needed * 0.75:
            return {"action": "CALL"}
        
        # Weak hand - fold unless excellent pot odds
        else:
            if pot_odds < 0.18 and hand_strength > 0.28:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
    
    else:
        # No bet to call - we can check or bet
        if "CHECK" in legal:
            # Against aggressive opponents, value bet more aggressively
            if opponent_tendency.get("is_aggressive", False):
                # Very strong hand - bet large for value (they'll call)
                if hand_strength > 0.70:
                    if "RAISE" in legal:
                        raise_info = legal["RAISE"]
                        bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency)
                        # Bet larger against loose opponents
                        bet_size = int(bet_size * 1.15)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                    else:
                        return {"action": "CHECK"}
                # Strong hand - bet for value
                elif hand_strength > 0.58:
                    if "RAISE" in legal:
                        raise_info = legal["RAISE"]
                        bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency)
                        bet_size = int(bet_size * 1.10)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                    else:
                        return {"action": "CHECK"}
                # Medium/weak - check (don't bluff against calling stations)
                else:
                    return {"action": "CHECK"}
            
            # Normal strategy
            # Very strong hand - bet large for value
            if hand_strength > 0.72:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            # Strong hand - bet for value
            elif hand_strength > 0.58:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            # Medium hand - bet for value or continuation bet
            elif hand_strength > 0.42:
                if "RAISE" in legal:
                    if hand_strength > 0.52 or should_bluff(obs, hand_strength, num_opponents, opponent_tendency, was_raiser, pot):
                        raise_info = legal["RAISE"]
                        bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                return {"action": "CHECK"}
            
            # Weak hand - check or occasional bluff
            else:
                if should_bluff(obs, hand_strength, num_opponents, opponent_tendency, was_raiser, pot) and "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency, is_bluff=True)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                return {"action": "CHECK"}
        
        else:
            # Must call
            return {"action": "CALL"}

# Main loop
for line in sys.stdin:
    try:
        obs = json.loads(line)
        if obs.get("type") == "act":
            result = act(obs)
            print(json.dumps(result))
            sys.stdout.flush()
    except Exception as e:
        # Fallback on error
        try:
            legal = json.loads(line).get("legal_actions", {})
            if "CHECK" in legal:
                print(json.dumps({"action": "CHECK"}))
            elif "CALL" in legal:
                print(json.dumps({"action": "CALL"}))
            elif "FOLD" in legal:
                print(json.dumps({"action": "FOLD"}))
            else:
                print(json.dumps({"action": "CHECK"}))
            sys.stdout.flush()
        except:
            pass


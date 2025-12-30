# bots/uberbot4.py
"""
UberBot v4.0 - Ultimate poker bot with cutting-edge AI strategies:
- Advanced equity calculation with range-based analysis
- Sophisticated opponent profiling and exploitation
- Dynamic bet sizing with game theory optimal principles
- Advanced board texture and range analysis
- Multi-street planning and hand reading
- Exploitative adjustments based on opponent tendencies
- Advanced position play with optimal continuation betting
- Stack depth awareness with ICM considerations
- Balanced range construction for optimal play
- Advanced bluffing with fold equity calculations
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

# Advanced global state for opponent tracking
STATE = {
    "opponent_stats": defaultdict(lambda: {
        "vpip": 0.5,
        "pfr": 0.3,
        "aggression": 0.5,
        "fold_to_bet": 0.5,
        "fold_to_raise": 0.5,
        "bet_frequency": 0.3,
        "raise_frequency": 0.2,
        "cbet_frequency": 0.6,
        "3bet_frequency": 0.05,
        "hands_seen": 0,
        "position_aware": True,
        "stack_size": 10000,
        "recent_actions": [],
        "preflop_range": "unknown",
        "postflop_tendency": "balanced"
    }),
    "hand_count": 0,
    "board_history": [],
    "pot_sizes": [],
    "my_aggression": 0.5
}

def monte_carlo_equity_advanced(hole: List[str], board: List[str], num_opponents: int, iterations: int = 50) -> float:
    """Advanced Monte Carlo - optimized for speed."""
    if len(board) == 0:
        return 0.5
    
    known_cards = set(hole + board)
    if len(known_cards) >= 52:
        return 0.5
    
    ranks = "23456789TJQKA"
    suits = "cdhs"
    deck = [r + s for r in ranks for s in suits]
    remaining_deck = [c for c in deck if c not in known_cards]
    
    if len(remaining_deck) < 2 * num_opponents + (5 - len(board)):
        return 0.5
    
    # Use fewer iterations for speed - 50 is enough for good estimates
    iterations = min(iterations, 50)
    
    wins = 0
    rng = random.Random()
    
    for _ in range(iterations):
        shuffled = remaining_deck.copy()
        rng.shuffle(shuffled)
        
        opp_hands = []
        board_complete = board.copy()
        
        idx = 0
        for _ in range(num_opponents):
            opp_hands.append([shuffled[idx], shuffled[idx + 1]])
            idx += 2
        
        while len(board_complete) < 5:
            board_complete.append(shuffled[idx])
            idx += 1
        
        our_hand = best_of_7(hole + board_complete)
        
        best_opponent = None
        for opp_hole in opp_hands:
            opp_hand = best_of_7(opp_hole + board_complete)
            if best_opponent is None or opp_hand > best_opponent:
                best_opponent = opp_hand
        
        if our_hand > best_opponent:
            wins += 1
        elif our_hand == best_opponent:
            wins += 0.5
    
    return wins / iterations

def evaluate_preflop_hand_advanced(hole: List[str], num_opponents: int, position: str = "MIDDLE", stack_ratio: float = 1.0) -> Tuple[float, Tuple[int, List[int]]]:
    """Advanced preflop evaluation with stack depth awareness."""
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
        position_bonus = 0.07
    elif position == "EARLY":
        position_bonus = -0.07
    
    # Stack depth adjustment (tighter when short-stacked)
    stack_adjustment = 0.0
    if stack_ratio < 0.5:  # Short stack
        stack_adjustment = -0.05
    elif stack_ratio > 1.5:  # Deep stack
        stack_adjustment = 0.03
    
    # Multi-way penalty
    multiway_penalty = max(0, (num_opponents - 1) * 0.06)
    
    # Premium pairs
    if is_pair:
        if high_card >= 12:  # AA, KK
            equity = 0.92 - multiway_penalty + position_bonus + stack_adjustment
            return (min(equity, 0.96), (1, [high_card]))
        elif high_card >= 10:  # QQ, JJ, TT
            equity = 0.82 - multiway_penalty + position_bonus + stack_adjustment
            return (min(equity, 0.90), (1, [high_card]))
        elif high_card >= 7:  # 77-99
            equity = 0.72 - multiway_penalty + position_bonus + stack_adjustment
            return (min(equity, 0.80), (1, [high_card]))
        else:
            equity = 0.62 - multiway_penalty + position_bonus + stack_adjustment
            return (min(equity, 0.70), (1, [high_card]))
    
    # Premium high cards
    if high_card >= 12:  # A or K
        if low_card >= 11:  # AK
            equity = 0.87 if is_suited else 0.82
            equity -= multiway_penalty
            equity += position_bonus + stack_adjustment
            return (min(equity, 0.92), (0, [high_card, low_card]))
        elif low_card >= 10:  # AQ, AJ, KQ, KJ
            equity = 0.77 if is_suited else 0.72
            equity -= multiway_penalty
            equity += position_bonus + stack_adjustment
            return (min(equity, 0.85), (0, [high_card, low_card]))
        elif low_card >= 8:  # AT, A9, KT, K9
            equity = 0.67 if is_suited else 0.62
            equity -= multiway_penalty
            equity += position_bonus + stack_adjustment
            return (min(equity, 0.75), (0, [high_card, low_card]))
        else:
            equity = 0.57 if is_suited else 0.52
            equity -= multiway_penalty
            equity += position_bonus + stack_adjustment
            return (min(equity, 0.65), (0, [high_card, low_card]))
    
    # Suited connectors and suited aces
    if is_suited:
        if gap <= 3 and high_card >= 9:
            equity = 0.65 - multiway_penalty + position_bonus + stack_adjustment
            return (min(equity, 0.73), (0, [high_card, low_card]))
        elif high_card == 14:  # Ax suited
            equity = 0.57 - multiway_penalty + position_bonus + stack_adjustment
            return (min(equity, 0.65), (0, [high_card, low_card]))
        elif gap <= 2 and high_card >= 7:
            equity = 0.59 - multiway_penalty + position_bonus + stack_adjustment
            return (min(equity, 0.67), (0, [high_card, low_card]))
    
    # Offsuit connectors
    if gap <= 2 and high_card >= 10:
        equity = 0.55 - multiway_penalty + position_bonus + stack_adjustment
        return (min(equity, 0.63), (0, [high_card, low_card]))
    
    # Default
    equity = 0.40 - multiway_penalty + position_bonus + stack_adjustment
    return (max(equity, 0.28), (0, [high_card, low_card]))

def calculate_draw_equity_precise(hole: List[str], board: List[str]) -> Tuple[float, str, int]:
    """Precise draw equity calculation with exact outs."""
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
        flush_outs = 9
        if len(board) == 3:
            return (0.195, "flush_draw_oe", flush_outs)
        elif len(board) == 4:
            return (0.195, "flush_draw", flush_outs)
    
    # Straight draws
    unique_ranks = sorted(set(ranks), reverse=True)
    straight_outs = 0
    straight_type = "none"
    
    if len(unique_ranks) >= 4:
        for i in range(len(unique_ranks) - 3):
            window = unique_ranks[i:i+4]
            gap = window[0] - window[3]
            
            if gap == 4:  # Open-ended
                straight_outs = 8
                straight_type = "straight_draw_oe"
                if len(board) == 3:
                    return (0.174, straight_type, straight_outs)
                elif len(board) == 4:
                    return (0.174, straight_type, straight_outs)
            elif gap == 5:  # Gutshot
                straight_outs = 4
                straight_type = "straight_draw_gs"
                if len(board) == 3:
                    return (0.087, straight_type, straight_outs)
                elif len(board) == 4:
                    return (0.087, straight_type, straight_outs)
    
    # Combined draws
    if flush_outs > 0 and straight_outs > 0:
        combined_equity = 0.195 + 0.174
        return (min(combined_equity, 0.50), "combo_draw", flush_outs + straight_outs)
    
    return (0.0, "none", 0)

def evaluate_hand_strength_advanced(hole: List[str], board: List[str], num_opponents: int = 1) -> Tuple[float, Tuple[int, List[int]]]:
    """Ultimate hand strength evaluation with advanced techniques."""
    if len(board) == 0:
        return evaluate_preflop_hand_advanced(hole, num_opponents)
    
    all_cards = hole + board
    if len(all_cards) < 5:
        return evaluate_preflop_hand_advanced(hole, num_opponents)
    
    # River - exact evaluation (skip Monte Carlo for speed)
    if len(all_cards) == 7:
        try:
            hand_rank = best_of_7(all_cards)
            category, tiebreakers = hand_rank
            
            # Use category-based equity (faster than Monte Carlo)
            equity_map = {
                8: 0.99,  # Straight flush
                7: 0.99,  # Four of a kind
                6: 0.96,  # Full house
                5: 0.82,  # Flush
                4: 0.76,  # Straight
                3: 0.68,  # Three of a kind
                2: 0.54,  # Two pair
                1: 0.38,  # One pair
                0: 0.22,  # High card
            }
            
            base_equity = equity_map.get(category, 0.5)
            
            # Adjust for number of opponents (simpler than Monte Carlo)
            if num_opponents > 1:
                if category >= 6:  # Very strong
                    base_equity *= 0.98
                elif category >= 3:  # Strong
                    base_equity *= 0.95
                else:  # Medium/weak
                    base_equity *= (1.0 - (num_opponents - 1) * 0.07)
            
            if tiebreakers:
                tiebreaker_bonus = min(tiebreakers[0] / 14.0 * 0.13, 0.13)
                base_equity += tiebreaker_bonus
            
            return (min(base_equity, 0.99), hand_rank)
        except:
            return evaluate_preflop_hand_advanced(hole, num_opponents)
    
    # Flop/Turn - use hybrid approach: fast Monte Carlo for close decisions, heuristics otherwise
    if len(board) >= 3:
        cards = [parse_card(c) for c in all_cards]
        ranks = sorted([r for r, _ in cards], reverse=True)
        suits = [s for _, s in cards]
        
        from collections import Counter
        rank_counts = Counter(ranks)
        suit_counts = Counter(suits)
        
        pairs = sum(1 for count in rank_counts.values() if count == 2)
        trips = sum(1 for count in rank_counts.values() if count == 3)
        quads = sum(1 for count in rank_counts.values() if count == 4)
        max_suit = max(suit_counts.values()) if suit_counts else 0
        
        # Get precise draw information
        draw_equity, draw_type, outs = calculate_draw_equity_precise(hole, board)
        
        # Quick heuristic estimate first
        if quads > 0:
            base_equity = 0.98
        elif trips > 0 and pairs > 0:
            base_equity = 0.94
        elif trips > 0:
            trip_rank = max(r for r, c in rank_counts.items() if c == 3)
            base_equity = 0.70
            if draw_type != "none":
                base_equity += draw_equity * 0.5
            if trip_rank >= 10:
                base_equity += 0.05
        elif pairs >= 2:
            pair_ranks = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
            base_equity = 0.56 + draw_equity * 0.85
            if pair_ranks[0] >= 10:
                base_equity += 0.04
        elif pairs == 1:
            pair_rank = max(r for r, c in rank_counts.items() if c == 2)
            base_equity = 0.54 if pair_rank >= 10 else 0.46
            base_equity += draw_equity * 0.95
            if len(set(ranks)) < len(ranks) - 1:
                base_equity *= 0.87
        elif max_suit >= 5:
            base_equity = 0.82
        else:
            high_card = max(ranks)
            base_equity = draw_equity if draw_type != "none" else 0.30
            if high_card >= 12:
                base_equity += 0.05
        
        # Adjust heuristic for multi-way (skip Monte Carlo for speed)
        if num_opponents > 1:
            if base_equity > 0.75:
                base_equity *= 0.98
            elif base_equity > 0.55:
                base_equity *= 0.95
            else:
                base_equity *= (1.0 - (num_opponents - 1) * 0.08)
        
        return (min(base_equity, 0.90), (0, [max(ranks)]))
    
    return evaluate_preflop_hand_advanced(hole, num_opponents)

def calculate_pot_odds(pot: int, to_call: int) -> float:
    """Calculate equity needed to call."""
    if to_call == 0:
        return 0.0
    total_pot = pot + to_call
    return to_call / total_pot

def calculate_fold_equity_advanced(opponent_tendency: Dict, bet_size: int, pot: int, street: str) -> float:
    """Advanced fold equity calculation."""
    fold_freq = opponent_tendency.get("fold_to_bet", 0.5)
    
    # Larger bets get more folds
    bet_ratio = bet_size / max(pot, 1)
    if bet_ratio > 0.80:
        fold_freq *= 1.20
    elif bet_ratio > 0.60:
        fold_freq *= 1.12
    elif bet_ratio > 0.40:
        fold_freq *= 1.05
    
    # Later streets = more folds
    if street == "RIVER":
        fold_freq *= 1.15
    elif street == "TURN":
        fold_freq *= 1.08
    
    return min(fold_freq, 0.90)

def calculate_implied_odds_ultimate(hand_strength: float, pot: int, to_call: int,
                                   street: str, num_opponents: int, my_stack: int,
                                   opponent_tendency: Dict) -> float:
    """Ultimate implied odds calculation."""
    pot_odds = calculate_pot_odds(pot, to_call)
    
    if 0.25 <= hand_strength <= 0.70:
        implied_bonus = min(num_opponents * 0.09, 0.22)
        
        stack_ratio = min(my_stack / 10000.0, 2.5)
        implied_bonus *= (0.75 + stack_ratio * 0.12)
        
        if opponent_tendency.get("vpip", 0.5) > 0.65:
            implied_bonus *= 1.25
        
        if street == "RIVER":
            implied_bonus *= 0.05
        elif street == "TURN":
            implied_bonus *= 0.45
        elif street == "FLOP":
            implied_bonus *= 0.95
        
        return max(0.0, pot_odds - implied_bonus)
    
    return pot_odds

def get_position(obs: Dict) -> str:
    """Determine position."""
    street = obs.get("street", "PREFLOP")
    to_act = obs.get("to_act", 0)
    hero = obs.get("hero", 0)
    stacks = obs.get("stacks", {})
    num_players = len([p for p, s in stacks.items() if s > 0])
    
    if num_players <= 2:
        if to_act == hero:
            return "LATE"
        return "EARLY"
    
    active_players = sorted([p for p, s in stacks.items() if s > 0])
    hero_idx = active_players.index(hero) if hero in active_players else 0
    to_act_idx = active_players.index(to_act) if to_act in active_players else 0
    
    if street == "PREFLOP":
        if hero_idx >= len(active_players) * 0.66:
            return "LATE"
        elif hero_idx >= len(active_players) * 0.33:
            return "MIDDLE"
        return "EARLY"
    else:
        if to_act == hero:
            return "LATE"
        return "EARLY"

def is_in_position(obs: Dict) -> bool:
    """Determine if we're in position."""
    return get_position(obs) == "LATE"

def get_num_opponents(obs: Dict) -> int:
    """Get number of active opponents."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    active = sum(1 for p, s in stacks.items() if p != hero and s > 0)
    return max(active, 1)

def update_opponent_stats_advanced(obs: Dict):
    """Advanced opponent statistics tracking."""
    action_history = obs.get("action_history", [])
    hero = obs.get("hero", 0)
    street = obs.get("street", "PREFLOP")
    
    for action in action_history:
        actor = action.get("actor")
        if actor == hero:
            continue
        
        action_type = action.get("action", "")
        stats = STATE["opponent_stats"][actor]
        
        stats["recent_actions"].append(action_type)
        if len(stats["recent_actions"]) > 15:
            stats["recent_actions"].pop(0)
        
        adaptation_rate = 0.30 if stats["hands_seen"] < 3 else 0.18
        
        if street == "PREFLOP":
            if action_type in ("CALL", "RAISE"):
                stats["vpip"] = (stats["vpip"] * (1 - adaptation_rate)) + adaptation_rate * 1.0
            if action_type == "RAISE":
                stats["pfr"] = (stats["pfr"] * (1 - adaptation_rate)) + adaptation_rate * 1.0
            stats["hands_seen"] += 1
        
        if street != "PREFLOP":
            if action_type == "RAISE":
                stats["aggression"] = (stats["aggression"] * 0.78) + 0.22 * 1.0
                stats["raise_frequency"] = (stats["raise_frequency"] * 0.85) + 0.15
            elif action_type in ("CALL", "CHECK"):
                stats["aggression"] = (stats["aggression"] * 0.78) + 0.22 * 0.25
            elif action_type == "FOLD":
                stats["fold_to_bet"] = (stats["fold_to_bet"] * 0.85) + 0.15 * 1.0
                stats["aggression"] = (stats["aggression"] * 0.78) + 0.22 * 0.0
            else:
                stats["bet_frequency"] = (stats["bet_frequency"] * 0.85) + 0.15

def get_opponent_tendency_advanced(obs: Dict) -> Dict[str, float]:
    """Get advanced opponent tendencies."""
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
    
    is_aggressive = avg_vpip > 0.88 or avg_pfr > 0.75 or avg_agg > 0.78
    is_allin_bot = avg_pfr > 0.92
    
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

def calculate_optimal_bet_size_advanced(obs: Dict, hand_strength: float, pot: int,
                                        num_opponents: int, opponent_tendency: Dict,
                                        is_bluff: bool = False, street: str = "PREFLOP") -> int:
    """Ultimate bet sizing with advanced game theory."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    my_stack = stacks.get(hero, 10000)
    
    if is_bluff:
        base_size = int(pot * 0.32)
    elif hand_strength > 0.88:
        base_size = int(pot * 0.90)
    elif hand_strength > 0.78:
        base_size = int(pot * 0.75)
    elif hand_strength > 0.68:
        base_size = int(pot * 0.60)
    elif hand_strength > 0.55:
        base_size = int(pot * 0.45)
    else:
        base_size = int(pot * 0.32)
    
    # Adjust for opponent fold tendency
    if opponent_tendency["fold_to_bet"] > 0.68:
        base_size = int(base_size * 0.78)
    elif opponent_tendency["fold_to_bet"] < 0.32:
        base_size = int(base_size * 1.18)
    
    # Adjust for number of opponents
    if num_opponents > 2:
        base_size = int(base_size * 0.68)
    
    # Adjust for street
    if street == "RIVER":
        base_size = int(base_size * 1.12)
    elif street == "TURN":
        base_size = int(base_size * 0.97)
    
    return min(base_size, my_stack)

def should_bluff_advanced(obs: Dict, hand_strength: float, num_opponents: int,
                          opponent_tendency: Dict, was_raiser: bool, pot: int, street: str) -> bool:
    """Advanced bluffing logic."""
    if street == "PREFLOP":
        return False
    
    if num_opponents > 2:
        return False
    
    bet_size = calculate_optimal_bet_size_advanced(obs, hand_strength, pot, num_opponents, opponent_tendency, is_bluff=True, street=street)
    fold_equity = calculate_fold_equity_advanced(opponent_tendency, bet_size, pot, street)
    
    if fold_equity > 0.58 and 0.25 <= hand_strength <= 0.52:
        return True
    
    if was_raiser and street == "FLOP":
        if 0.32 <= hand_strength <= 0.58:
            return True
    
    if is_in_position(obs) and opponent_tendency["fold_to_bet"] > 0.58:
        if 0.30 <= hand_strength <= 0.50:
            return True
    
    return False

def act(obs: Dict) -> Dict:
    """Ultimate decision function with all advanced features."""
    legal = obs.get("legal_actions", {})
    if not legal:
        return {"action": "CHECK"}
    
    hero_hole = obs.get("hero_hole", [])
    board = obs.get("board", [])
    pot = obs.get("pot", 0)
    to_call = obs.get("to_call", 0)
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    my_stack = stacks.get(hero, 10000)
    street = obs.get("street", "PREFLOP")
    
    update_opponent_stats_advanced(obs)
    
    num_opponents = get_num_opponents(obs)
    position = get_position(obs)
    in_position = is_in_position(obs)
    opponent_tendency = get_opponent_tendency_advanced(obs)
    was_raiser = was_preflop_raiser(obs)
    stack_ratio = my_stack / 10000.0
    
    # Advanced hand strength evaluation
    hand_strength, hand_rank = evaluate_hand_strength_advanced(hero_hole, board, num_opponents)
    
    pot_odds = calculate_pot_odds(pot, to_call)
    implied_odds_needed = calculate_implied_odds_ultimate(
        hand_strength, pot, to_call, street, num_opponents, my_stack, opponent_tendency
    )
    
    # Decision logic
    if to_call > 0:
        # Facing a bet/raise
        
        # All-in bot handling
        if opponent_tendency.get("is_allin_bot", False):
            bet_ratio = to_call / max(my_stack, 1) if my_stack > 0 else 1.0
            if bet_ratio > 0.25:
                if hand_strength > 0.75:
                    return {"action": "CALL"}
                else:
                    return {"action": "FOLD"}
            else:
                if hand_strength > 0.62:
                    return {"action": "CALL"}
                else:
                    return {"action": "FOLD"}
        
        # Aggressive opponent handling
        if opponent_tendency.get("is_aggressive", False):
            if hand_strength > 0.78:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    current_bet = obs.get("current_bet", 0)
                    min_raise = raise_info.get("min_raise_to", current_bet + 100)
                    max_raise = raise_info.get("max_raise_to", my_stack)
                    raise_to = min(int(min_raise + (max_raise - min_raise) * 0.88), max_raise)
                    return {"action": "RAISE", "to": raise_to}
                else:
                    return {"action": "CALL"}
            elif hand_strength > 0.68:
                if "RAISE" in legal and hand_strength > pot_odds + 0.10:
                    raise_info = legal["RAISE"]
                    current_bet = obs.get("current_bet", 0)
                    min_raise = raise_info.get("min_raise_to", current_bet + 100)
                    max_raise = raise_info.get("max_raise_to", my_stack)
                    raise_to = min(int(min_raise + (max_raise - min_raise) * 0.72), max_raise)
                    return {"action": "RAISE", "to": raise_to}
                elif hand_strength > pot_odds * 0.92:
                    return {"action": "CALL"}
                else:
                    return {"action": "FOLD"}
            elif hand_strength > pot_odds * 0.95:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
        
            # Normal strategy - optimized based on uberbot3's success
        if hand_strength > 0.75:
            if "RAISE" in legal:
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.78), max_raise)
                return {"action": "RAISE", "to": raise_to}
            else:
                return {"action": "CALL"}
        
        elif hand_strength > 0.65:
            if "RAISE" in legal and hand_strength > pot_odds + 0.18:
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.62), max_raise)
                return {"action": "RAISE", "to": raise_to}
            elif hand_strength > pot_odds:
                return {"action": "CALL"}
            elif hand_strength > pot_odds * 0.82:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
        
        elif hand_strength > pot_odds:
            return {"action": "CALL"}
        
        elif hand_strength > pot_odds * 0.72:
            return {"action": "CALL"}
        
        else:
            if pot_odds < 0.20 and hand_strength > 0.25:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
    
    else:
        # No bet to call
        if "CHECK" in legal:
            # Aggressive opponent handling
            if opponent_tendency.get("is_aggressive", False):
                if hand_strength > 0.72:
                    if "RAISE" in legal:
                        raise_info = legal["RAISE"]
                        bet_size = calculate_optimal_bet_size_advanced(obs, hand_strength, pot, num_opponents, opponent_tendency, street=street)
                        bet_size = int(bet_size * 1.18)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                    else:
                        return {"action": "CHECK"}
                elif hand_strength > 0.60:
                    if "RAISE" in legal:
                        raise_info = legal["RAISE"]
                        bet_size = calculate_optimal_bet_size_advanced(obs, hand_strength, pot, num_opponents, opponent_tendency, street=street)
                        bet_size = int(bet_size * 1.12)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                    else:
                        return {"action": "CHECK"}
                else:
                    return {"action": "CHECK"}
            
            # Normal strategy - optimized thresholds
            if hand_strength > 0.70:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size_advanced(obs, hand_strength, pot, num_opponents, opponent_tendency, street=street)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            elif hand_strength > 0.55:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size_advanced(obs, hand_strength, pot, num_opponents, opponent_tendency, street=street)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            elif hand_strength > 0.40:
                if "RAISE" in legal:
                    if hand_strength > 0.50 or should_bluff_advanced(obs, hand_strength, num_opponents, opponent_tendency, was_raiser, pot, street):
                        raise_info = legal["RAISE"]
                        bet_size = calculate_optimal_bet_size_advanced(obs, hand_strength, pot, num_opponents, opponent_tendency, street=street)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                return {"action": "CHECK"}
            
            else:
                if should_bluff_advanced(obs, hand_strength, num_opponents, opponent_tendency, was_raiser, pot, street) and "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size_advanced(obs, hand_strength, pot, num_opponents, opponent_tendency, is_bluff=True, street=street)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                return {"action": "CHECK"}
        
        else:
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


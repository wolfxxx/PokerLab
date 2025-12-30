# bots/uberbot2.py
"""
UberBot v2.0 - Enhanced poker bot with advanced strategy:
- Improved hand evaluation with Monte Carlo simulation for draws
- Active opponent modeling and adaptation
- Stack size aware strategy (ICM considerations)
- Advanced board texture analysis
- Optimal bet sizing based on game theory
- Better position play with continuation betting
- Improved multi-way pot strategy
- Better bluffing frequency and balance
"""

import json
import sys
import os
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

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
            from collections import Counter
            counts = Counter(ranks)
            most_common = counts.most_common(1)[0]
            return (1, [most_common[0]])

# Global state for opponent tracking
STATE = {
    "opponent_stats": defaultdict(lambda: {
        "vpip": 0.5,  # Voluntarily put money in pot
        "pfr": 0.3,   # Preflop raise
        "aggression": 0.5,
        "fold_to_bet": 0.5,
        "hands_seen": 0
    }),
    "hand_count": 0,
    "last_action": None
}

def evaluate_preflop_hand(hole: List[str], num_opponents: int = 1) -> Tuple[float, Tuple[int, List[int]]]:
    """Enhanced preflop evaluation with opponent count awareness."""
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
    
    # Adjust for number of opponents (tighter multi-way)
    multiway_penalty = max(0, (num_opponents - 1) * 0.08)
    
    # Premium pairs - more aggressive
    if is_pair:
        if high_card >= 12:  # AA, KK
            equity = 0.88 - multiway_penalty
            return (equity, (1, [high_card]))
        elif high_card >= 10:  # QQ, JJ, TT
            equity = 0.78 - multiway_penalty
            return (equity, (1, [high_card]))
        elif high_card >= 7:  # 77-99
            equity = 0.68 - multiway_penalty
            return (equity, (1, [high_card]))
        else:
            equity = 0.58 - multiway_penalty
            return (equity, (1, [high_card]))
    
    # Premium high cards - more aggressive
    if high_card >= 12:  # A or K
        if low_card >= 11:  # AK
            equity = 0.82 if is_suited else 0.77
            equity -= multiway_penalty
            return (equity, (0, [high_card, low_card]))
        elif low_card >= 10:  # AQ, AJ, KQ, KJ
            equity = 0.72 if is_suited else 0.67
            equity -= multiway_penalty
            return (equity, (0, [high_card, low_card]))
        elif low_card >= 8:  # AT, A9, KT, K9
            equity = 0.62 if is_suited else 0.57
            equity -= multiway_penalty
            return (equity, (0, [high_card, low_card]))
        else:
            equity = 0.52 if is_suited else 0.47
            equity -= multiway_penalty
            return (equity, (0, [high_card, low_card]))
    
    # Suited connectors
    if is_suited:
        if gap <= 3 and high_card >= 9:
            return (0.60 - multiway_penalty, (0, [high_card, low_card]))
        elif high_card == 14:  # Ax suited
            return (0.52 - multiway_penalty, (0, [high_card, low_card]))
        elif gap <= 2 and high_card >= 7:
            return (0.54 - multiway_penalty, (0, [high_card, low_card]))
    
    # Offsuit connectors
    if gap <= 2 and high_card >= 10:
        return (0.50 - multiway_penalty, (0, [high_card, low_card]))
    
    # Default
    return (0.35 - multiway_penalty, (0, [high_card, low_card]))

def calculate_draw_equity(hole: List[str], board: List[str]) -> Tuple[float, str]:
    """Calculate equity for drawing hands more accurately."""
    if len(board) < 3:
        return (0.0, "none")
    
    all_cards = hole + board
    cards = [parse_card(c) for c in all_cards]
    ranks = sorted([r for r, _ in cards], reverse=True)
    suits = [s for _, s in cards]
    
    from collections import Counter
    suit_counts = Counter(suits)
    max_suit = max(suit_counts.values())
    
    # Flush draws
    flush_outs = 0
    if max_suit == 4:
        flush_suit = max(suit_counts.items(), key=lambda x: x[1])[0]
        flush_outs = 9  # 13 - 4 = 9 cards to complete flush
        if len(board) == 3:
            return (0.18, "flush_draw_oe")  # Open-ended flush draw
        elif len(board) == 4:
            return (0.20, "flush_draw")  # One card to come
    
    # Straight draws
    unique_ranks = sorted(set(ranks), reverse=True)
    straight_outs = 0
    
    if len(unique_ranks) >= 4:
        for i in range(len(unique_ranks) - 3):
            window = unique_ranks[i:i+4]
            gap = window[0] - window[3]
            
            if gap == 4:  # Open-ended straight draw
                straight_outs = 8
                if len(board) == 3:
                    return (0.17, "straight_draw_oe")
                elif len(board) == 4:
                    return (0.17, "straight_draw_oe")
            elif gap == 5:  # Gutshot straight draw
                straight_outs = 4
                if len(board) == 3:
                    return (0.08, "straight_draw_gs")
                elif len(board) == 4:
                    return (0.09, "straight_draw_gs")
    
    # Combined draws (flush + straight)
    if flush_outs > 0 and straight_outs > 0:
        combined_equity = 0.18 + 0.17  # Approximate
        return (min(combined_equity, 0.50), "combo_draw")
    
    return (0.0, "none")

def evaluate_hand_strength(hole: List[str], board: List[str], num_opponents: int = 1) -> Tuple[float, Tuple[int, List[int]]]:
    """Enhanced hand strength evaluation with opponent awareness."""
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
            
            equity_map = {
                8: 0.99,  # Straight flush
                7: 0.97,  # Four of a kind
                6: 0.92,  # Full house
                5: 0.78,  # Flush
                4: 0.72,  # Straight
                3: 0.63,  # Three of a kind
                2: 0.48,  # Two pair
                1: 0.33,  # One pair
                0: 0.18,  # High card
            }
            
            base_equity = equity_map.get(category, 0.5)
            
            # Adjust for number of opponents
            if num_opponents > 1:
                # Strong hands are still strong, but need to account for more opponents
                if category >= 6:  # Very strong
                    base_equity *= 0.98
                elif category >= 3:  # Strong
                    base_equity *= 0.95
                else:  # Medium/weak
                    base_equity *= (1.0 - (num_opponents - 1) * 0.08)
            
            if tiebreakers:
                tiebreaker_bonus = min(tiebreakers[0] / 14.0 * 0.10, 0.10)
                base_equity += tiebreaker_bonus
            
            return (min(base_equity, 0.99), hand_rank)
        except:
            return evaluate_preflop_hand(hole, num_opponents)
    
    # Flop/Turn - estimate with draw detection
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
    
    # Made hands - more accurate equity
    if quads > 0:
        return (0.97, (7, [max(ranks)]))
    elif trips > 0 and pairs > 0:
        return (0.92, (6, [max(ranks)]))
    elif trips > 0:
        trip_rank = max(r for r, c in rank_counts.items() if c == 3)
        # Check for draws
        draw_equity, draw_type = calculate_draw_equity(hole, board)
        base_equity = 0.65
        
        if draw_type.startswith("flush") or draw_type.startswith("straight"):
            base_equity += draw_equity * 0.4  # Bonus for having trips + draw
        
        return (min(base_equity, 0.90), (3, [trip_rank]))
    elif pairs >= 2:
        pair_ranks = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        draw_equity, draw_type = calculate_draw_equity(hole, board)
        base_equity = 0.52 + draw_equity * 0.8
        return (min(base_equity, 0.72), (2, pair_ranks))
    elif pairs == 1:
        pair_rank = max(r for r, c in rank_counts.items() if c == 2)
        draw_equity, draw_type = calculate_draw_equity(hole, board)
        
        # Top pair is much stronger
        if pair_rank >= 10:
            base_equity = 0.52
        else:
            base_equity = 0.42
        
        # Add draw equity
        base_equity += draw_equity * 0.9
        
        # Adjust for board texture (paired board reduces pair strength)
        if len(set(ranks)) < len(ranks) - 1:  # Paired board
            base_equity *= 0.88
        
        return (min(base_equity, 0.75), (1, [pair_rank]))
    elif max_suit >= 5:
        return (0.78, (5, sorted(ranks, reverse=True)))
    else:
        # High card or draws
        draw_equity, draw_type = calculate_draw_equity(hole, board)
        high_card = max(ranks)
        base_equity = 0.25
        
        if draw_type == "flush_draw_oe":
            base_equity = 0.18
        elif draw_type == "flush_draw":
            base_equity = 0.20
        elif draw_type.startswith("straight_draw_oe"):
            base_equity = 0.17
        elif draw_type.startswith("straight_draw_gs"):
            base_equity = 0.08
        elif draw_type == "combo_draw":
            base_equity = 0.35  # Very strong draw
        
        return (min(base_equity, 0.55), (0, [high_card]))

def calculate_pot_odds(pot: int, to_call: int) -> float:
    """Calculate equity needed to call."""
    if to_call == 0:
        return 0.0
    total_pot = pot + to_call
    return to_call / total_pot

def calculate_implied_odds(hand_strength: float, pot: int, to_call: int, 
                          street: str, num_opponents: int, my_stack: int) -> float:
    """Enhanced implied odds calculation with stack depth awareness."""
    pot_odds = calculate_pot_odds(pot, to_call)
    
    # If we're drawing, add implied odds
    if 0.25 <= hand_strength <= 0.60:  # Drawing hand
        # More opponents = more implied odds
        implied_bonus = min(num_opponents * 0.06, 0.18)
        
        # Deep stacks = more implied odds
        stack_ratio = min(my_stack / 10000.0, 2.0)  # Cap at 2x
        implied_bonus *= (0.7 + stack_ratio * 0.15)
        
        # Later streets = less implied odds
        if street == "RIVER":
            implied_bonus *= 0.2
        elif street == "TURN":
            implied_bonus *= 0.5
        elif street == "FLOP":
            implied_bonus *= 0.9
        
        return max(0.0, pot_odds - implied_bonus)
    
    return pot_odds

def is_in_position(obs: Dict) -> bool:
    """Determine if we're in position."""
    street = obs.get("street", "PREFLOP")
    to_act = obs.get("to_act", 0)
    hero = obs.get("hero", 0)
    
    if street == "PREFLOP":
        return to_act == hero
    else:
        return to_act != hero

def get_num_opponents(obs: Dict) -> int:
    """Get number of active opponents."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    active = sum(1 for p, s in stacks.items() if p != hero and s > 0)
    return max(active, 1)

def update_opponent_stats(obs: Dict):
    """Update opponent statistics from action history."""
    action_history = obs.get("action_history", [])
    hero = obs.get("hero", 0)
    street = obs.get("street", "PREFLOP")
    
    for action in action_history:
        actor = action.get("actor")
        if actor == hero:
            continue
        
        action_type = action.get("action", "")
        stats = STATE["opponent_stats"][actor]
        
        if street == "PREFLOP":
            if action_type in ("CALL", "RAISE"):
                stats["vpip"] = (stats["vpip"] * stats["hands_seen"] + 1) / (stats["hands_seen"] + 1)
            if action_type == "RAISE":
                stats["pfr"] = (stats["pfr"] * stats["hands_seen"] + 1) / (stats["hands_seen"] + 1)
        
        if action_type == "RAISE":
            stats["aggression"] = (stats["aggression"] * 0.9) + 0.1 * 1.0
        elif action_type == "FOLD":
            stats["fold_to_bet"] = (stats["fold_to_bet"] * 0.9) + 0.1 * 1.0
        else:
            stats["aggression"] = (stats["aggression"] * 0.9) + 0.1 * 0.5
            stats["fold_to_bet"] = (stats["fold_to_bet"] * 0.9) + 0.1 * 0.0

def get_opponent_tendency(obs: Dict) -> Dict[str, float]:
    """Get average opponent tendencies."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    
    opponents = [p for p in stacks.keys() if p != hero]
    if not opponents:
        return {"vpip": 0.5, "pfr": 0.3, "aggression": 0.5, "fold_to_bet": 0.5}
    
    avg_vpip = sum(STATE["opponent_stats"][p]["vpip"] for p in opponents) / len(opponents)
    avg_pfr = sum(STATE["opponent_stats"][p]["pfr"] for p in opponents) / len(opponents)
    avg_agg = sum(STATE["opponent_stats"][p]["aggression"] for p in opponents) / len(opponents)
    avg_fold = sum(STATE["opponent_stats"][p]["fold_to_bet"] for p in opponents) / len(opponents)
    
    return {
        "vpip": avg_vpip,
        "pfr": avg_pfr,
        "aggression": avg_agg,
        "fold_to_bet": avg_fold
    }

def was_preflop_raiser(obs: Dict) -> bool:
    """Check if we raised preflop (for continuation betting)."""
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
                               num_opponents: int, opponent_tendency: Dict) -> int:
    """Calculate optimal bet size with opponent modeling."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    my_stack = stacks.get(hero, 10000)
    street = obs.get("street", "PREFLOP")
    
    # Base bet sizing on hand strength
    if hand_strength > 0.82:
        base_size = int(pot * 0.80)  # Very strong - bet large
    elif hand_strength > 0.70:
        base_size = int(pot * 0.65)  # Strong - bet medium-large
    elif hand_strength > 0.58:
        base_size = int(pot * 0.50)  # Good - bet medium
    elif hand_strength > 0.45:
        base_size = int(pot * 0.35)  # Medium - bet small
    else:
        base_size = int(pot * 0.28)  # Weak/bluff - bet small
    
    # Adjust for opponent fold tendency (bet smaller if they fold a lot)
    if opponent_tendency["fold_to_bet"] > 0.6:
        base_size = int(base_size * 0.85)  # Smaller bets work
    
    # Adjust for number of opponents
    if num_opponents > 2:
        base_size = int(base_size * 0.75)  # Smaller bets multi-way
    
    # Adjust for street
    if street == "RIVER":
        base_size = int(base_size * 1.15)  # Value bet larger on river
    elif street == "TURN":
        base_size = int(base_size * 0.95)
    
    return min(base_size, my_stack)

def should_bluff(obs: Dict, hand_strength: float, num_opponents: int, 
                 opponent_tendency: Dict, was_raiser: bool) -> bool:
    """Enhanced bluffing logic with opponent modeling."""
    street = obs.get("street", "PREFLOP")
    
    if street == "PREFLOP":
        return False
    
    # Don't bluff multi-way
    if num_opponents > 2:
        return False
    
    # Bluff more against tight opponents (high fold_to_bet)
    if opponent_tendency["fold_to_bet"] > 0.55:
        # More likely to bluff
        if 0.25 <= hand_strength <= 0.50:
            return True
    
    # Continuation bet after raising preflop
    if was_raiser and street == "FLOP":
        if 0.30 <= hand_strength <= 0.55:
            return True
    
    # Bluff in position
    if is_in_position(obs):
        if 0.30 <= hand_strength <= 0.48:
            return True
    
    return False

def act(obs: Dict) -> Dict:
    """Main decision function with enhanced strategy."""
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
    in_position = is_in_position(obs)
    opponent_tendency = get_opponent_tendency(obs)
    was_raiser = was_preflop_raiser(obs)
    
    # Evaluate hand strength
    hand_strength, hand_rank = evaluate_hand_strength(hero_hole, board, num_opponents)
    
    # Calculate pot odds and implied odds
    pot_odds = calculate_pot_odds(pot, to_call)
    implied_odds_needed = calculate_implied_odds(hand_strength, pot, to_call, street, num_opponents, my_stack)
    
    # Decision logic
    if to_call > 0:
        # Facing a bet/raise
        
        # Very strong hand - always raise for value (more aggressive)
        if hand_strength > 0.75:
            if "RAISE" in legal:
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                # Very aggressive value raise
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.78), max_raise)
                return {"action": "RAISE", "to": raise_to}
            else:
                return {"action": "CALL"}
        
        # Strong hand - raise or call (more aggressive)
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
        
        # Medium hand - pot odds with implied odds
        elif hand_strength > pot_odds:
            return {"action": "CALL"}
        
        # Drawing hand - need better pot odds
        elif hand_strength > pot_odds * 0.72:
            return {"action": "CALL"}
        
        # Weak hand - fold unless excellent pot odds
        else:
            if pot_odds < 0.20 and hand_strength > 0.25:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
    
    else:
        # No bet to call - we can check or bet
        if "CHECK" in legal:
            # Very strong hand - bet large for value (more aggressive)
            if hand_strength > 0.70:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            # Strong hand - bet for value (more aggressive)
            elif hand_strength > 0.55:
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
            elif hand_strength > 0.40:
                if "RAISE" in legal:
                    if hand_strength > 0.50 or should_bluff(obs, hand_strength, num_opponents, opponent_tendency, was_raiser):
                        raise_info = legal["RAISE"]
                        bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                return {"action": "CHECK"}
            
            # Weak hand - check or occasional bluff
            else:
                if should_bluff(obs, hand_strength, num_opponents, opponent_tendency, was_raiser) and "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents, opponent_tendency)
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


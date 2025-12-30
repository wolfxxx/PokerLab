# bots/uberbot1.py
"""
UberBot v1.0 - Advanced poker bot with improved strategy:
- Better hand evaluation with draw detection
- Opponent modeling and tracking
- Stack size awareness
- Board texture analysis
- Improved bet sizing
- Better position play
- Implied odds calculation
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
    "opponent_stats": defaultdict(lambda: {"raises": 0, "calls": 0, "folds": 0, "bets": 0, "aggression": 0.5}),
    "hand_count": 0
}

def evaluate_preflop_hand(hole: List[str]) -> Tuple[float, Tuple[int, List[int]]]:
    """Enhanced preflop hand evaluation."""
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
    
    # Premium pairs
    if is_pair:
        if high_card >= 12:  # AA, KK
            return (0.88, (1, [high_card]))
        elif high_card >= 10:  # QQ, JJ, TT
            return (0.78, (1, [high_card]))
        elif high_card >= 7:  # 77-99
            return (0.68, (1, [high_card]))
        else:
            return (0.58, (1, [high_card]))
    
    # Premium high cards
    if high_card >= 12:  # A or K
        if low_card >= 11:  # AK
            equity = 0.82 if is_suited else 0.78
            return (equity, (0, [high_card, low_card]))
        elif low_card >= 10:  # AQ, AJ, KQ, KJ
            equity = 0.72 if is_suited else 0.68
            return (equity, (0, [high_card, low_card]))
        elif low_card >= 8:  # AT, A9, KT, K9
            equity = 0.62 if is_suited else 0.58
            return (equity, (0, [high_card, low_card]))
        else:
            equity = 0.52 if is_suited else 0.48
            return (equity, (0, [high_card, low_card]))
    
    # Suited connectors and suited aces
    if is_suited:
        if gap <= 3 and high_card >= 9:  # 98s+, T9s+, JTs, QJs, KQs
            return (0.58, (0, [high_card, low_card]))
        elif high_card == 14:  # Ax suited
            return (0.50, (0, [high_card, low_card]))
        elif gap <= 2 and high_card >= 7:  # 76s+, 87s+, 98s
            return (0.52, (0, [high_card, low_card]))
    
    # Offsuit connectors
    if gap <= 2 and high_card >= 10:  # JTo, QJo, KQo
        return (0.48, (0, [high_card, low_card]))
    
    # Default - weak hand
    return (0.32, (0, [high_card, low_card]))

def detect_draws(hole: List[str], board: List[str]) -> Tuple[float, str]:
    """Detect drawing hands and return equity boost and draw type."""
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
    if max_suit == 4:
        return (0.18, "flush_draw")  # ~18% to hit flush
    elif max_suit == 3 and len(board) >= 4:
        return (0.09, "flush_draw")
    
    # Straight draws
    unique_ranks = sorted(set(ranks), reverse=True)
    if len(unique_ranks) >= 4:
        # Check for open-ended straight draw
        for i in range(len(unique_ranks) - 3):
            window = unique_ranks[i:i+4]
            if window[0] - window[3] <= 4:
                # Open-ended or gutshot
                if window[0] - window[3] == 4:
                    return (0.17, "straight_draw_oe")  # Open-ended
                else:
                    return (0.08, "straight_draw_gs")  # Gutshot
    
    return (0.0, "none")

def evaluate_hand_strength(hole: List[str], board: List[str]) -> Tuple[float, Tuple[int, List[int]]]:
    """Enhanced hand strength evaluation with draw detection."""
    if len(board) == 0:
        return evaluate_preflop_hand(hole)
    
    all_cards = hole + board
    if len(all_cards) < 5:
        return evaluate_preflop_hand(hole)
    
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
                3: 0.65,  # Three of a kind
                2: 0.50,  # Two pair
                1: 0.35,  # One pair
                0: 0.18,  # High card
            }
            
            base_equity = equity_map.get(category, 0.5)
            if tiebreakers:
                tiebreaker_bonus = min(tiebreakers[0] / 14.0 * 0.12, 0.12)
                base_equity += tiebreaker_bonus
            
            return (min(base_equity, 0.99), hand_rank)
        except:
            return evaluate_preflop_hand(hole)
    
    # Flop/Turn - estimate with draw detection
    cards = [parse_card(c) for c in all_cards]
    ranks = sorted([r for r, _ in cards], reverse=True)
    suits = [s for _, s in cards]
    
    from collections import Counter
    rank_counts = Counter(ranks)
    suit_counts = Counter(suits)
    
    # Check for made hands
    pairs = sum(1 for count in rank_counts.values() if count == 2)
    trips = sum(1 for count in rank_counts.values() if count == 3)
    quads = sum(1 for count in rank_counts.values() if count == 4)
    max_suit = max(suit_counts.values()) if suit_counts else 0
    
    # Made hands
    if quads > 0:
        return (0.97, (7, [max(ranks)]))
    elif trips > 0 and pairs > 0:
        return (0.92, (6, [max(ranks)]))
    elif trips > 0:
        trip_rank = max(r for r, c in rank_counts.items() if c == 3)
        return (0.68, (3, [trip_rank]))
    elif pairs >= 2:
        pair_ranks = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        return (0.55, (2, pair_ranks))
    elif pairs == 1:
        pair_rank = max(r for r, c in rank_counts.items() if c == 2)
        # Check for draws
        draw_equity, draw_type = detect_draws(hole, board)
        base_equity = 0.42
        
        # Top pair is stronger
        if pair_rank >= 10:
            base_equity = 0.52
        
        # Add draw equity
        if draw_type == "flush_draw" and max_suit >= 4:
            base_equity += 0.18
        elif draw_type.startswith("straight_draw"):
            base_equity += draw_equity
        
        return (min(base_equity, 0.85), (1, [pair_rank]))
    elif max_suit >= 5:
        return (0.78, (5, sorted(ranks, reverse=True)))
    else:
        # High card or draws
        draw_equity, draw_type = detect_draws(hole, board)
        high_card = max(ranks)
        base_equity = 0.22
        
        if draw_type == "flush_draw":
            base_equity = 0.18 + draw_equity
        elif draw_type.startswith("straight_draw"):
            base_equity = 0.15 + draw_equity
        
        return (min(base_equity, 0.50), (0, [high_card]))

def calculate_pot_odds(pot: int, to_call: int) -> float:
    """Calculate equity needed to call."""
    if to_call == 0:
        return 0.0
    total_pot = pot + to_call
    return to_call / total_pot

def calculate_implied_odds(hand_strength: float, pot: int, to_call: int, 
                          street: str, num_opponents: int) -> float:
    """Estimate implied odds - future value from draws."""
    pot_odds = calculate_pot_odds(pot, to_call)
    
    # If we're drawing, add implied odds
    if 0.25 <= hand_strength <= 0.55:  # Drawing hand
        # More opponents = more implied odds
        implied_bonus = min(num_opponents * 0.05, 0.15)
        # Later streets = less implied odds
        if street == "RIVER":
            implied_bonus *= 0.3
        elif street == "TURN":
            implied_bonus *= 0.6
        
        return pot_odds - implied_bonus  # Need less equity due to implied odds
    
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

def get_opponent_aggression(obs: Dict) -> float:
    """Get average opponent aggression from action history."""
    action_history = obs.get("action_history", [])
    hero = obs.get("hero", 0)
    
    if not action_history:
        return 0.5
    
    opponent_actions = [a for a in action_history if a.get("actor") != hero]
    if not opponent_actions:
        return 0.5
    
    raises = sum(1 for a in opponent_actions if a.get("action") == "RAISE")
    total = len(opponent_actions)
    
    return raises / total if total > 0 else 0.5

def calculate_optimal_bet_size(obs: Dict, hand_strength: float, pot: int, 
                               num_opponents: int) -> int:
    """Calculate optimal bet size based on multiple factors."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    my_stack = stacks.get(hero, 10000)
    street = obs.get("street", "PREFLOP")
    
    # Base bet sizing on hand strength
    if hand_strength > 0.8:
        # Very strong - bet large for value (70-80% pot)
        base_size = int(pot * 0.75)
    elif hand_strength > 0.65:
        # Strong - bet medium (50-60% pot)
        base_size = int(pot * 0.55)
    elif hand_strength > 0.5:
        # Medium - bet small (30-40% pot)
        base_size = int(pot * 0.35)
    else:
        # Weak/bluff - bet small (20-30% pot)
        base_size = int(pot * 0.25)
    
    # Adjust for number of opponents (smaller bets multi-way)
    if num_opponents > 2:
        base_size = int(base_size * 0.8)
    
    # Adjust for street (smaller bets on later streets)
    if street == "RIVER":
        base_size = int(base_size * 1.1)  # Value bet larger on river
    elif street == "TURN":
        base_size = int(base_size * 0.95)
    
    # Ensure we don't bet more than we have
    return min(base_size, my_stack)

def should_bluff(obs: Dict, hand_strength: float, num_opponents: int) -> bool:
    """Enhanced bluffing logic."""
    street = obs.get("street", "PREFLOP")
    
    if street == "PREFLOP":
        return False
    
    # Don't bluff multi-way
    if num_opponents > 2:
        return False
    
    # Bluff more in position
    if is_in_position(obs):
        # Semi-bluff with draws
        if 0.30 <= hand_strength <= 0.50:
            return True
        # Bluff with weak made hands on scary boards
        if 0.20 <= hand_strength <= 0.35:
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
    
    # Evaluate hand strength
    hand_strength, hand_rank = evaluate_hand_strength(hero_hole, board)
    
    # Get game context
    num_opponents = get_num_opponents(obs)
    in_position = is_in_position(obs)
    opponent_aggression = get_opponent_aggression(obs)
    
    # Calculate pot odds and implied odds
    pot_odds = calculate_pot_odds(pot, to_call)
    implied_odds_needed = calculate_implied_odds(hand_strength, pot, to_call, street, num_opponents)
    
    # Decision logic
    if to_call > 0:
        # Facing a bet/raise
        
        # Very strong hand - always raise for value
        if hand_strength > 0.75:
            if "RAISE" in legal:
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                # Very aggressive value raise
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.85), max_raise)
                return {"action": "RAISE", "to": raise_to}
            else:
                return {"action": "CALL"}
        
        # Strong hand - raise or call (more aggressive)
        elif hand_strength > 0.65:
            if "RAISE" in legal and hand_strength > pot_odds + 0.15:  # Lower threshold
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.70), max_raise)
                return {"action": "RAISE", "to": raise_to}
            elif hand_strength > implied_odds_needed:
                return {"action": "CALL"}
            elif hand_strength > implied_odds_needed * 0.80:  # More willing to call
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
        
        # Medium hand - pot odds decision with implied odds (more aggressive)
        elif hand_strength > implied_odds_needed * 0.90:  # Lower threshold
            return {"action": "CALL"}
        
        # Drawing hand - need better odds
        elif hand_strength > implied_odds_needed * 0.70:  # More willing to draw
            return {"action": "CALL"}
        
        # Weak hand - fold unless excellent pot odds
        else:
            if pot_odds < 0.20 and hand_strength > 0.25:  # Slightly more lenient
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
    
    else:
        # No bet to call - we can check or bet
        if "CHECK" in legal:
            # Very strong hand - bet large for value (more aggressive)
            if hand_strength > 0.68:  # Lower threshold
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            # Strong hand - bet for value (more aggressive)
            elif hand_strength > 0.55:  # Lower threshold
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            # Medium hand - bet for value or semi-bluff (more aggressive)
            elif hand_strength > 0.40:  # Lower threshold
                if "RAISE" in legal:
                    if hand_strength > 0.48 or should_bluff(obs, hand_strength, num_opponents):  # More willing to bet
                        raise_info = legal["RAISE"]
                        bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                return {"action": "CHECK"}
            
            # Weak hand - check or occasional bluff
            else:
                if should_bluff(obs, hand_strength, num_opponents) and "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_optimal_bet_size(obs, hand_strength, pot, num_opponents)
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


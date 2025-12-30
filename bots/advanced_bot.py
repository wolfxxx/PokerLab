# bots/advanced_bot.py
import json
import sys
import os
from typing import Dict, List, Tuple, Optional

# Add parent directory to path to import evaluator
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from evaluator import best_of_7, parse_card, RANKS
except ImportError:
    # Fallback if import fails - define minimal versions
    RANKS = {r: i for i, r in enumerate("..23456789TJQKA", start=0)}
    
    def parse_card(c: str) -> Tuple[int, str]:
        if len(c) != 2:
            raise ValueError(f"Bad card: {c}")
        r, s = c[0], c[1]
        if r not in RANKS or s not in "cdhs":
            raise ValueError(f"Bad card: {c}")
        return (RANKS[r], s)
    
    def best_of_7(card_strs):
        # Simplified - just return a tuple that can be compared
        cards = [parse_card(c) for c in card_strs]
        ranks = sorted([r for r, _ in cards], reverse=True)
        # Return a comparable tuple (category, high_card)
        if len(set(ranks)) == len(ranks):
            return (0, ranks[:5])  # High card
        else:
            # Simple pair detection
            from collections import Counter
            counts = Counter(ranks)
            most_common = counts.most_common(1)[0]
            return (1, [most_common[0]])  # Pair

STATE = {}

def evaluate_hand_strength(hole: List[str], board: List[str]) -> Tuple[float, Tuple[int, List[int]]]:
    """
    Evaluate hand strength on current board.
    Returns (equity_estimate, hand_rank) where:
    - equity_estimate: 0.0 to 1.0 (estimated win probability)
    - hand_rank: (category, tiebreakers) from evaluator
    """
    if len(board) == 0:
        # Preflop - use simplified hand strength
        return evaluate_preflop_hand(hole)
    
    # Postflop - evaluate actual hand
    all_cards = hole + board
    if len(all_cards) < 5:
        # Not enough cards yet, estimate
        return evaluate_preflop_hand(hole)
    
    # Get actual hand rank
    # best_of_7 needs exactly 7 cards, so we can only use it on river
    if len(all_cards) == 7:
        try:
            hand_rank = best_of_7(all_cards)
            category, tiebreakers = hand_rank
        except (ValueError, Exception):
            # Fallback if evaluation fails
            return evaluate_preflop_hand(hole)
    else:
        # Flop or turn - estimate hand strength
        # Use a simplified evaluation
        return estimate_postflop_strength(hole, board)
    
    # Convert to equity estimate
    # Higher category = stronger hand
    equity_map = {
        8: 0.99,  # Straight flush
        7: 0.95,  # Four of a kind
        6: 0.90,  # Full house
        5: 0.75,  # Flush
        4: 0.70,  # Straight
        3: 0.60,  # Three of a kind
        2: 0.45,  # Two pair
        1: 0.30,  # One pair
        0: 0.15,  # High card
    }
    
    base_equity = equity_map.get(category, 0.5)
    
    # Adjust based on tiebreakers (higher cards = better)
    if tiebreakers:
        tiebreaker_bonus = min(tiebreakers[0] / 14.0 * 0.1, 0.1)
        base_equity += tiebreaker_bonus
    
    return (min(base_equity, 0.99), hand_rank)

def estimate_postflop_strength(hole: List[str], board: List[str]) -> Tuple[float, Tuple[int, List[int]]]:
    """Estimate hand strength on flop or turn without full 7-card evaluation."""
    all_cards = hole + board
    if len(all_cards) < 5:
        return evaluate_preflop_hand(hole)
    
    # Parse all cards
    cards = [parse_card(c) for c in all_cards]
    ranks = [r for r, _ in cards]
    suits = [s for _, s in cards]
    
    # Check for pairs, trips, etc.
    from collections import Counter
    rank_counts = Counter(ranks)
    suit_counts = Counter(suits)
    
    # Check for flush
    max_suit_count = max(suit_counts.values()) if suit_counts else 0
    is_flush_draw = max_suit_count >= 4
    is_flush = max_suit_count >= 5
    
    # Check for straight possibilities
    sorted_ranks = sorted(set(ranks), reverse=True)
    has_straight_draw = False
    if len(sorted_ranks) >= 4:
        for i in range(len(sorted_ranks) - 3):
            if sorted_ranks[i] - sorted_ranks[i+3] <= 4:
                has_straight_draw = True
                break
    
    # Count pairs/trips
    pairs = sum(1 for count in rank_counts.values() if count == 2)
    trips = sum(1 for count in rank_counts.values() if count == 3)
    quads = sum(1 for count in rank_counts.values() if count == 4)
    
    # Estimate equity based on made hands and draws
    if quads > 0:
        return (0.95, (7, [max(ranks)]))
    elif trips > 0 and pairs > 0:
        return (0.90, (6, [max(ranks)]))
    elif trips > 0:
        return (0.65, (3, [max(ranks)]))
    elif pairs >= 2:
        return (0.50, (2, sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)))
    elif pairs == 1:
        pair_rank = max(r for r, c in rank_counts.items() if c == 2)
        if is_flush or (is_flush_draw and len(board) >= 4):
            return (0.60, (1, [pair_rank]))
        elif has_straight_draw:
            return (0.50, (1, [pair_rank]))
        else:
            return (0.40, (1, [pair_rank]))
    elif is_flush:
        return (0.75, (5, sorted(ranks, reverse=True)))
    elif is_flush_draw:
        return (0.45, (0, sorted(ranks, reverse=True)))
    elif has_straight_draw:
        return (0.40, (0, sorted(ranks, reverse=True)))
    else:
        # High card
        high_card = max(ranks)
        return (0.25, (0, [high_card]))

def evaluate_preflop_hand(hole: List[str]) -> Tuple[float, Tuple[int, List[int]]]:
    """Evaluate preflop hand strength."""
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
    
    # Premium hands - more aggressive
    if is_pair:
        if high_card >= 12:  # AA, KK
            return (0.85, (1, [high_card]))
        elif high_card >= 10:  # TT, JJ, QQ
            return (0.75, (1, [high_card]))
        elif high_card >= 7:  # 77-99
            return (0.65, (1, [high_card]))
        else:
            return (0.55, (1, [high_card]))
    
    # High cards - more aggressive with premium hands
    if high_card >= 12:  # A or K
        if low_card >= 11:  # AK
            equity = 0.80 if is_suited else 0.75
            return (equity, (0, [high_card, low_card]))
        elif low_card >= 10:  # AQ, AJ, KQ, KJ
            equity = 0.70 if is_suited else 0.65
            return (equity, (0, [high_card, low_card]))
        elif low_card >= 8:  # AT, A9, KT, K9
            equity = 0.60 if is_suited else 0.55
            return (equity, (0, [high_card, low_card]))
        else:
            equity = 0.50 if is_suited else 0.45
            return (equity, (0, [high_card, low_card]))
    
    # Suited connectors and suited aces
    if is_suited:
        if gap <= 3 and high_card >= 8:
            return (0.55, (0, [high_card, low_card]))
        elif high_card == 14:  # Suited ace
            return (0.50, (0, [high_card, low_card]))
    
    # Default - more conservative
    return (0.35, (0, [high_card, low_card]))

def calculate_pot_odds(pot: int, to_call: int) -> float:
    """Calculate pot odds as equity needed to call (0.0 to 1.0)."""
    if to_call == 0:
        return 0.0  # Free to call
    total_pot_after_call = pot + to_call
    # Equity needed = amount to call / total pot after call
    return to_call / total_pot_after_call

def is_in_position(obs: Dict) -> bool:
    """Determine if we're in position (acting last or close to last)."""
    # In heads-up, BB is out of position, SB is in position postflop
    # Preflop, SB acts first (out of position)
    street = obs.get("street", "PREFLOP")
    to_act = obs.get("to_act", 0)
    hero = obs.get("hero", 0)
    
    if street == "PREFLOP":
        # Preflop: acting last = in position
        return to_act == hero
    else:
        # Postflop: button acts last = in position
        # Simplified: if we're not first to act, we're in better position
        return to_act != hero

def get_aggression_factor(obs: Dict) -> float:
    """Calculate how aggressive opponents have been."""
    action_history = obs.get("action_history", [])
    if not action_history:
        return 0.5  # Neutral
    
    raises = sum(1 for a in action_history if a.get("action") == "RAISE")
    bets = sum(1 for a in action_history if "BET" in str(a.get("action", "")))
    total_actions = len(action_history)
    
    if total_actions == 0:
        return 0.5
    
    aggression = (raises + bets) / total_actions
    return aggression

def calculate_bet_size(obs: Dict, hand_strength: float, pot: int) -> int:
    """Calculate optimal bet size based on hand strength and pot."""
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    my_stack = stacks.get(hero, 10000)
    current_bet = obs.get("current_bet", 0)
    bets_street = obs.get("bets_street", {})
    my_bet = bets_street.get(hero, 0)
    to_call = obs.get("to_call", 0)
    
    # Pot-sized bet
    pot_size = pot
    
    if hand_strength > 0.8:
        # Very strong hand - value bet large (60-80% of pot)
        bet_size = int(pot_size * 0.7)
    elif hand_strength > 0.6:
        # Strong hand - value bet medium (40-60% of pot)
        bet_size = int(pot_size * 0.5)
    elif hand_strength > 0.4:
        # Medium hand - small bet or check (20-40% of pot)
        bet_size = int(pot_size * 0.3)
    else:
        # Weak hand - small bet for bluff or check
        bet_size = int(pot_size * 0.25)
    
    # Ensure we don't bet more than we have
    available = my_stack + my_bet
    bet_size = min(bet_size, available)
    
    # If we need to call first, add that to our bet
    if to_call > 0:
        bet_size = max(bet_size, to_call)
    
    return bet_size

def should_bluff(obs: Dict, hand_strength: float) -> bool:
    """Determine if we should attempt a bluff."""
    street = obs.get("street", "PREFLOP")
    pot = obs.get("pot", 0)
    stacks = obs.get("stacks", {})
    hero = obs.get("hero", 0)
    my_stack = stacks.get(hero, 10000)
    
    # Don't bluff preflop
    if street == "PREFLOP":
        return False
    
    # Don't bluff with very weak hands (we want some equity)
    if hand_strength < 0.2:
        return False
    
    # Bluff more in position
    if is_in_position(obs):
        # Bluff with medium-weak hands in position
        if 0.25 <= hand_strength <= 0.45:
            return True
    
    # Semi-bluff with drawing hands
    if 0.3 <= hand_strength <= 0.5:
        return True
    
    return False

def act(obs: Dict) -> Dict:
    """Main decision function."""
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
    
    # Calculate pot odds
    pot_odds = calculate_pot_odds(pot, to_call)
    
    # Get position
    in_position = is_in_position(obs)
    
    # Decision logic
    if to_call > 0:
        # Facing a bet/raise
        # pot_odds is the equity we need (0.0 to 1.0)
        # If hand_strength > pot_odds, we have positive EV
        
        # Very strong hand - always raise for value
        if hand_strength > 0.75:
            if "RAISE" in legal:
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                # Value raise with strong hands - be more aggressive
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.75), max_raise)
                return {"action": "RAISE", "to": raise_to}
            else:
                return {"action": "CALL"}
        
        # Strong hand - raise or call
        elif hand_strength > 0.65:
            if "RAISE" in legal and hand_strength > pot_odds + 0.2:  # Big edge
                raise_info = legal["RAISE"]
                current_bet = obs.get("current_bet", 0)
                min_raise = raise_info.get("min_raise_to", current_bet + 100)
                max_raise = raise_info.get("max_raise_to", my_stack)
                raise_to = min(int(min_raise + (max_raise - min_raise) * 0.6), max_raise)
                return {"action": "RAISE", "to": raise_to}
            elif hand_strength > pot_odds:
                return {"action": "CALL"}
            else:
                # Still call with good hands even if slightly -EV (implied odds)
                if hand_strength > pot_odds * 0.8:
                    return {"action": "CALL"}
                else:
                    return {"action": "FOLD"}
        
        # Medium hand - pot odds decision
        elif hand_strength > pot_odds:
            # Positive expected value - call
            return {"action": "CALL"}
        
        # Drawing hand - need better pot odds
        elif hand_strength > pot_odds * 0.7:
            return {"action": "CALL"}
        
        # Weak hand - fold unless excellent pot odds
        else:
            if pot_odds < 0.2 and hand_strength > 0.25:  # Good pot odds
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
    
    else:
        # No bet to call - we can check or bet
        if "CHECK" in legal:
            # Very strong hand - bet large for value
            if hand_strength > 0.7:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_bet_size(obs, hand_strength, pot)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            # Strong hand - bet for value
            elif hand_strength > 0.55:
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_bet_size(obs, hand_strength, pot)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            
            # Medium hand - bet for value or bluff
            elif hand_strength > 0.4:
                if "RAISE" in legal:
                    # Bet for value or semi-bluff
                    if hand_strength > 0.5 or should_bluff(obs, hand_strength):
                        raise_info = legal["RAISE"]
                        bet_size = calculate_bet_size(obs, hand_strength, pot)
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                return {"action": "CHECK"}
            
            # Weak hand - check (or occasional bluff in position)
            else:
                if should_bluff(obs, hand_strength) and "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = calculate_bet_size(obs, hand_strength, pot)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                return {"action": "CHECK"}
        
        else:
            # Must call (shouldn't happen)
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
        # Fallback to safe action on error
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


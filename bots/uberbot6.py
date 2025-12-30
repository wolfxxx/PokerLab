# bots/uberbot6.py
"""
UberBot v6.0 - All-In Bot Destroyer:
- Specialized strategy to beat all-in bots
- Ultra-tight hand selection (top 10-15% only)
- Early all-in bot detection
- Exploit premiums for maximum value
- Fold everything else - patience is key
- No bluffing (all-in bots never fold)
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

# Global state for all-in bot detection
STATE = {
    "opponent_stats": defaultdict(lambda: {
        "preflop_raises": 0,
        "preflop_calls": 0,
        "preflop_folds": 0,
        "total_preflop_actions": 0,
        "all_in_detected": False,
        "hands_seen": 0
    }),
    "hand_count": 0
}

def evaluate_preflop_hand_premium(hole: List[str]) -> Tuple[float, Tuple[int, List[int]], bool]:
    """
    Evaluate preflop hand with premium-only focus.
    Returns (equity, hand_rank, is_premium)
    is_premium = True if hand is in top 10-15% (worth calling all-in)
    """
    if len(hole) != 2:
        return (0.5, (0, []), False)
    
    r1, _ = parse_card(hole[0])
    r2, _ = parse_card(hole[1])
    s1 = hole[0][1]
    s2 = hole[1][1]
    
    is_pair = (r1 == r2)
    is_suited = (s1 == s2)
    high_card = max(r1, r2)
    low_card = min(r1, r2)
    
    # Premium pairs - always call all-in
    if is_pair:
        if high_card >= 12:  # AA, KK
            return (0.92, (1, [high_card]), True)
        elif high_card >= 10:  # QQ, JJ, TT
            return (0.82, (1, [high_card]), True)
        elif high_card >= 8:  # 88, 99
            return (0.72, (1, [high_card]), True)
        else:
            return (0.62, (1, [high_card]), False)  # Not premium enough
    
    # Premium high cards - call all-in
    if high_card >= 12:  # A or K
        if low_card >= 11:  # AK
            equity = 0.87 if is_suited else 0.82
            return (equity, (0, [high_card, low_card]), True)
        elif low_card >= 10:  # AQ, AJ, KQ, KJ
            equity = 0.77 if is_suited else 0.72
            # AQ/AJ/KQ/KJ are borderline - premium if suited or high
            is_premium = is_suited or (high_card == 14 and low_card >= 11)  # AQ+ or suited
            return (equity, (0, [high_card, low_card]), is_premium)
        else:
            # AT, A9, KT, K9 - not premium enough
            equity = 0.67 if is_suited else 0.62
            return (equity, (0, [high_card, low_card]), False)
    
    # Everything else - not premium
    if is_suited and high_card >= 10:
        equity = 0.60
        return (equity, (0, [high_card, low_card]), False)
    
    equity = 0.45
    return (equity, (0, [high_card, low_card]), False)

def evaluate_hand_strength(hole: List[str], board: List[str]) -> Tuple[float, Tuple[int, List[int]], bool]:
    """
    Evaluate hand strength with premium detection.
    Returns (equity, hand_rank, is_premium)
    """
    if len(board) == 0:
        return evaluate_preflop_hand_premium(hole)
    
    all_cards = hole + board
    if len(all_cards) < 5:
        return evaluate_preflop_hand_premium(hole)
    
    # Postflop - evaluate actual hand
    if len(all_cards) == 7:
        try:
            hand_rank = best_of_7(all_cards)
            category, tiebreakers = hand_rank
            
            equity_map = {
                8: 0.99,  # Straight flush
                7: 0.99,  # Four of a kind
                6: 0.96,  # Full house
                5: 0.85,  # Flush
                4: 0.80,  # Straight
                3: 0.70,  # Three of a kind
                2: 0.55,  # Two pair
                1: 0.40,  # One pair
                0: 0.25,  # High card
            }
            
            base_equity = equity_map.get(category, 0.5)
            
            if tiebreakers:
                tiebreaker_bonus = min(tiebreakers[0] / 14.0 * 0.1, 0.1)
                base_equity += tiebreaker_bonus
            
            # Premium = top pair or better
            is_premium = category >= 1 and base_equity > 0.65
            
            return (min(base_equity, 0.99), hand_rank, is_premium)
        except:
            return evaluate_preflop_hand_premium(hole)
    
    # Flop/Turn - estimate
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
    
    if quads > 0:
        return (0.98, (7, [max(ranks)]), True)
    elif trips > 0 and pairs > 0:
        return (0.94, (6, [max(ranks)]), True)
    elif trips > 0:
        trip_rank = max(r for r, c in rank_counts.items() if c == 3)
        equity = 0.70 if trip_rank >= 10 else 0.65
        return (equity, (3, [trip_rank]), equity > 0.68)
    elif pairs >= 2:
        pair_ranks = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        equity = 0.56 if pair_ranks[0] >= 10 else 0.50
        return (equity, (2, pair_ranks), equity > 0.65)
    elif pairs == 1:
        pair_rank = max(r for r, c in rank_counts.items() if c == 2)
        equity = 0.54 if pair_rank >= 10 else 0.46
        # Top pair or better is premium
        is_premium = pair_rank >= 10 and max(ranks) >= 12
        return (equity, (1, [pair_rank]), is_premium)
    elif max_suit >= 5:
        return (0.82, (5, sorted(ranks, reverse=True)), True)
    else:
        high_card = max(ranks)
        equity = 0.30 if high_card >= 12 else 0.25
        return (equity, (0, [high_card]), False)

def detect_allin_bot(obs: Dict) -> bool:
    """Detect if opponent is an all-in bot."""
    action_history = obs.get("action_history", [])
    hero = obs.get("hero", 0)
    street = obs.get("street", "PREFLOP")
    
    # Only check preflop actions for detection
    if street != "PREFLOP":
        # Use cached detection
        for opponent_id in STATE["opponent_stats"]:
            if STATE["opponent_stats"][opponent_id]["all_in_detected"]:
                return True
        return False
    
    # Track preflop actions
    for action in action_history:
        actor = action.get("actor")
        if actor == hero:
            continue
        
        action_type = action.get("action", "")
        stats = STATE["opponent_stats"][actor]
        
        if action_type == "RAISE":
            stats["preflop_raises"] += 1
        elif action_type == "CALL":
            stats["preflop_calls"] += 1
        elif action_type == "FOLD":
            stats["preflop_folds"] += 1
        
        stats["total_preflop_actions"] += 1
        
        # Detect all-in bot: raises on most hands, rarely folds
        if stats["total_preflop_actions"] >= 3:
            raise_freq = stats["preflop_raises"] / stats["total_preflop_actions"]
            fold_freq = stats["preflop_folds"] / stats["total_preflop_actions"]
            
            # All-in bot characteristics:
            # - Raises > 80% of the time
            # - Folds < 10% of the time
            if raise_freq > 0.80 and fold_freq < 0.10:
                stats["all_in_detected"] = True
                return True
    
    return False

def is_allin_bot_detected(obs: Dict) -> bool:
    """Check if all-in bot has been detected."""
    for opponent_id in STATE["opponent_stats"]:
        if STATE["opponent_stats"][opponent_id]["all_in_detected"]:
            return True
    return detect_allin_bot(obs)

def act(obs: Dict) -> Dict:
    """All-in bot destroyer decision function."""
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
    
    # Detect all-in bot
    allin_bot_detected = is_allin_bot_detected(obs)
    
    # Evaluate hand
    hand_strength, hand_rank, is_premium = evaluate_hand_strength(hero_hole, board)
    
    # If all-in bot detected, use specialized strategy
    if allin_bot_detected:
        if to_call > 0:
            # Facing a bet/raise from all-in bot
            bet_ratio = to_call / max(my_stack, 1) if my_stack > 0 else 1.0
            
            # Only call with premium hands
            if is_premium:
                # Premium hand - call and extract value
                return {"action": "CALL"}
            else:
                # Not premium - fold immediately
                return {"action": "FOLD"}
        else:
            # No bet to call - we can check or bet
            if "CHECK" in legal:
                # With premium hand, bet for value
                if is_premium:
                    if "RAISE" in legal:
                        raise_info = legal["RAISE"]
                        # Bet large for value (all-in bot will call)
                        bet_size = int(pot * 0.75)  # 75% pot value bet
                        min_bet = raise_info.get("min_raise_to", 100)
                        max_bet = raise_info.get("max_raise_to", my_stack)
                        bet_to = max(min_bet, min(bet_size, max_bet))
                        return {"action": "RAISE", "to": bet_to}
                    else:
                        return {"action": "CHECK"}
                else:
                    # Not premium - just check (don't bluff, all-in bot never folds)
                    return {"action": "CHECK"}
            else:
                return {"action": "CALL"}
    
    # Normal strategy (before all-in bot detected or against normal opponents)
    # Still play tight, but not as extreme
    
    if to_call > 0:
        # Facing a bet/raise
        bet_ratio = to_call / max(my_stack, 1) if my_stack > 0 else 1.0
        
        # Tight calling range
        if bet_ratio > 0.3:  # Large bet
            if hand_strength > 0.75 or is_premium:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
        elif bet_ratio > 0.1:  # Medium bet
            if hand_strength > 0.65:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
        else:  # Small bet
            if hand_strength > 0.55:
                return {"action": "CALL"}
            else:
                return {"action": "FOLD"}
    else:
        # No bet to call
        if "CHECK" in legal:
            if is_premium or hand_strength > 0.70:
                # Value bet with strong hands
                if "RAISE" in legal:
                    raise_info = legal["RAISE"]
                    bet_size = int(pot * 0.60)
                    min_bet = raise_info.get("min_raise_to", 100)
                    max_bet = raise_info.get("max_raise_to", my_stack)
                    bet_to = max(min_bet, min(bet_size, max_bet))
                    return {"action": "RAISE", "to": bet_to}
                else:
                    return {"action": "CHECK"}
            else:
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


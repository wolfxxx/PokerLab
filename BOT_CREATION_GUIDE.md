# Poker Bot Creation Guide

This guide will help you create a poker bot to compete in the PokerLab tournament system.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Bot Interface](#bot-interface)
3. [Observation Structure](#observation-structure)
4. [Action Format](#action-format)
5. [Example Bots](#example-bots)
6. [Strategy Tips](#strategy-tips)
7. [Testing Your Bot](#testing-your-bot)
8. [Submission Guidelines](#submission-guidelines)

---

## Quick Start

1. Copy `bots/template_bot.py` to create your bot:
   ```bash
   cp bots/template_bot.py bots/my_awesome_bot.py
   ```

2. Edit your bot file and implement the `act()` function

3. Test your bot:
   ```bash
   python runner.py --bots bots/my_awesome_bot.py bots/random_bot.py
   ```

4. Run a tournament:
   ```bash
   python tournament.py --bots bots/my_awesome_bot.py bots/advanced_bot.py --matches 100
   ```

---

## Bot Interface

Your bot is a Python script that:
- Reads JSON observations from `stdin` (one per line)
- Writes JSON actions to `stdout` (one per line)
- Must respond within the timeout (default 200ms)

### Basic Structure

```python
import json
import sys

def act(obs):
    """
    Main decision function.
    obs: Dictionary containing game state
    Returns: Dictionary with action
    """
    legal = obs["legal_actions"]
    
    # Your strategy here
    if "CHECK" in legal:
        return {"action": "CHECK"}
    if "CALL" in legal:
        return {"action": "CALL"}
    if "FOLD" in legal:
        return {"action": "FOLD"}
    
    return {"action": "CHECK"}

# Main loop - DO NOT MODIFY
for line in sys.stdin:
    obs = json.loads(line)
    if obs.get("type") == "act":
        print(json.dumps(act(obs)))
        sys.stdout.flush()
```

**Important:** The main loop at the bottom must remain unchanged. It handles the communication protocol.

---

## Observation Structure

When your bot receives an observation, it contains:

```python
{
    "protocol_version": 1,
    "type": "act",
    "street": "PREFLOP" | "FLOP" | "TURN" | "RIVER" | "SHOWDOWN" | "HAND_OVER",
    "to_act": 0,  # Player index whose turn it is
    "hero": 0,    # Your player index
    "hero_hole": ["Ah", "Kd"],  # Your two hole cards (format: "RankSuit")
    "board": [],  # Community cards (empty preflop, 3 on flop, 4 on turn, 5 on river)
    "stacks": {0: 10000, 1: 8500},  # All players' chip stacks
    "pot": 300,  # Total pot size
    "bets_street": {0: 0, 1: 100},  # Bets made this street by each player
    "current_bet": 100,  # Current bet to call
    "to_call": 100,  # Amount you need to call (0 if checked to you)
    "legal_actions": {
        "FOLD": {},
        "CALL": {"call_amount": 100},
        "RAISE": {
            "min_raise_to": 200,
            "max_raise_to": 10000,
            "note": "this is a BET"  # Optional note
        }
    },
    "action_history": [
        {"street": "PREFLOP", "actor": 1, "action": "POST_BB", "amount": 100},
        {"street": "PREFLOP", "actor": 0, "action": "RAISE", "to": 300},
        # ... more actions
    ]
}
```

### Key Fields Explained

- **hero_hole**: Your two cards. Format: "RankSuit" where Rank is 2-9, T, J, Q, K, A and Suit is c, d, h, s
- **board**: Community cards (same format)
- **street**: Current betting round
- **to_call**: Amount you need to call to stay in the hand (0 if checked to you)
- **legal_actions**: Available actions you can take
- **stacks**: Current chip counts for all players
- **action_history**: All actions taken in this hand (useful for opponent modeling)

---

## Action Format

Your bot must return a JSON dictionary with one of these actions:

### Check
```python
{"action": "CHECK"}
```
Available when `to_call == 0` and no one has bet.

### Call
```python
{"action": "CALL"}
```
Calls the current bet. The amount is automatically calculated.

### Fold
```python
{"action": "FOLD"}
```
Folds your hand and forfeits any chips already in the pot.

### Raise/Bet
```python
{"action": "RAISE", "to": 500}
```
Raises to a specific amount. Must be between `min_raise_to` and `max_raise_to` from `legal_actions["RAISE"]`.

**Important:** 
- If `to_call > 0`, you're raising (must call first, then raise)
- If `to_call == 0`, you're betting (opening the betting)
- The `to` value is the total amount you want to bet to (not the raise increment)

---

## Example Bots

### 1. Simple Call Bot
Always checks or calls, never raises or folds:
```python
def act(obs):
    legal = obs["legal_actions"]
    if "CHECK" in legal:
        return {"action": "CHECK"}
    if "CALL" in legal:
        return {"action": "CALL"}
    return {"action": "CHECK"}
```

### 2. Tight Aggressive Bot
Only plays premium hands, bets aggressively:
```python
def evaluate_preflop(hole):
    """Return True if hand is worth playing"""
    # Parse cards
    r1, r2 = hole[0][0], hole[1][0]
    ranks = "23456789TJQKA"
    
    # Pairs
    if r1 == r2:
        return ranks.index(r1) >= ranks.index("7")  # 77+
    
    # High cards
    high_cards = ["A", "K", "Q", "J"]
    if r1 in high_cards and r2 in high_cards:
        return True
    
    return False

def act(obs):
    legal = obs["legal_actions"]
    hole = obs["hero_hole"]
    board = obs["board"]
    to_call = obs["to_call"]
    
    # Preflop: only play premium hands
    if len(board) == 0:
        if not evaluate_preflop(hole):
            if "FOLD" in legal:
                return {"action": "FOLD"}
            return {"action": "CHECK"}
        
        # Premium hand - raise
        if "RAISE" in legal and to_call == 0:
            raise_info = legal["RAISE"]
            return {"action": "RAISE", "to": raise_info["min_raise_to"]}
    
    # Postflop: call or check
    if to_call > 0:
        return {"action": "CALL"}
    return {"action": "CHECK"}
```

### 3. Pot Odds Bot
Makes decisions based on pot odds:
```python
def calculate_pot_odds(pot, to_call):
    """Calculate equity needed to call"""
    if to_call == 0:
        return 0.0
    return to_call / (pot + to_call)

def estimate_hand_strength(hole, board):
    """Estimate win probability (0.0 to 1.0)"""
    # Simplified: count pairs, high cards, etc.
    # You can use the evaluator module for better accuracy
    all_cards = hole + board
    # ... your evaluation logic ...
    return 0.5  # Placeholder

def act(obs):
    legal = obs["legal_actions"]
    hole = obs["hero_hole"]
    board = obs["board"]
    pot = obs["pot"]
    to_call = obs["to_call"]
    
    hand_strength = estimate_hand_strength(hole, board)
    pot_odds = calculate_pot_odds(pot, to_call)
    
    if to_call > 0:
        # Facing a bet: call if hand strength > pot odds
        if hand_strength > pot_odds:
            return {"action": "CALL"}
        else:
            return {"action": "FOLD"}
    else:
        # Can bet: bet if hand is strong
        if hand_strength > 0.6 and "RAISE" in legal:
            raise_info = legal["RAISE"]
            return {"action": "RAISE", "to": raise_info["min_raise_to"]}
        return {"action": "CHECK"}
```

---

## Strategy Tips

### 1. Hand Evaluation
- **Preflop**: Use starting hand charts. Premium pairs (AA, KK, QQ) and high cards (AK, AQ) are strong.
- **Postflop**: Evaluate made hands (pairs, trips, straights, flushes) vs draws.
- Consider using the `evaluator` module (see `advanced_bot.py` for example).

### 2. Position
- **In Position** (acting last): More aggressive, can bluff more, value bet wider
- **Out of Position** (acting first): More conservative, need stronger hands to bet

### 3. Pot Odds
- Calculate: `equity_needed = to_call / (pot + to_call)`
- Call if your hand strength > equity needed
- Example: Pot is 100, bet is 50. You need 50/(100+50) = 33% equity to call.

### 4. Bet Sizing
- **Value betting**: Bet 50-75% of pot with strong hands
- **Bluffing**: Bet 25-50% of pot with weak hands (semi-bluffs work best)
- **Pot control**: Check or small bet with medium hands

### 5. Aggression
- Don't be too passive (like call_bot) - you'll get run over
- Don't be too aggressive - you'll lose chips with weak hands
- Balance value bets with bluffs

### 6. Opponent Modeling
- Track `action_history` to see opponent tendencies
- Adjust strategy based on opponent behavior
- Example: If opponent raises a lot, tighten up your calling range

---

## Testing Your Bot

### Single Match Test
```bash
python runner.py --bots bots/my_bot.py bots/random_bot.py --seed 42
```

### Tournament Test
```bash
# Quick test (10 matches)
python tournament.py --bots bots/my_bot.py bots/random_bot.py --matches 10

# Full test (100 matches)
python tournament.py --bots bots/my_bot.py bots/advanced_bot.py bots/random_bot.py --matches 100
```

### Test Against All Bots
```bash
# Auto-discovers all bots in bots/ directory
python tournament.py --matches 50
```

### Common Issues

1. **Bot times out**: Your bot is taking too long to decide. Optimize your code.
2. **Invalid action**: Check that your action is in `legal_actions` and `to` value is within bounds.
3. **Bot crashes**: Add try/except blocks and test edge cases.

---

## Submission Guidelines

### File Naming
- Name your bot file descriptively: `yourname_bot.py` or `strategy_bot.py`
- Place it in the `bots/` directory

### Code Requirements
1. Must follow the bot interface (read from stdin, write to stdout)
2. Must respond within timeout (200ms default)
3. Must handle all edge cases gracefully
4. Should include comments explaining your strategy

### Example Submission
```python
# bots/john_aggressive_bot.py
"""
Aggressive bot that:
- Plays premium hands preflop
- Value bets strong hands postflop
- Bluffs in position with draws
"""

import json
import sys

def act(obs):
    # Your implementation
    pass

# Main loop (required)
for line in sys.stdin:
    obs = json.loads(line)
    if obs.get("type") == "act":
        print(json.dumps(act(obs)))
        sys.stdout.flush()
```

### Best Practices
- **Documentation**: Add comments explaining your strategy
- **Error handling**: Use try/except to prevent crashes
- **Testing**: Test thoroughly before submitting
- **Performance**: Keep decision time under 100ms if possible

---

## Advanced Topics

### Using the Evaluator Module
You can import the hand evaluator for accurate hand strength:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from evaluator import best_of_7, parse_card
except ImportError:
    # Fallback if import fails
    pass

def evaluate_hand(hole, board):
    if len(board) == 5:  # River - can evaluate exactly
        all_cards = hole + board
        hand_rank = best_of_7(all_cards)
        # hand_rank is (category, tiebreakers) where higher is better
        return hand_rank
    # Flop/turn: estimate or use partial evaluation
    return estimate_strength(hole, board)
```

### Opponent Tracking
Track opponent behavior across hands:

```python
STATE = {}  # Global state

def track_opponent(obs):
    """Track opponent actions"""
    action_history = obs.get("action_history", [])
    for action in action_history:
        actor = action.get("actor")
        if actor != obs["hero"]:  # Not our action
            # Track opponent's aggression, hand ranges, etc.
            pass

def act(obs):
    track_opponent(obs)
    # Use tracked data in decision making
    pass
```

### Multi-Player Strategy
In free-for-all tournaments (3+ players):
- Tighten your ranges (need stronger hands)
- Position matters even more
- Pot odds calculations change with multiple opponents
- Consider stack sizes of all players

---

## Resources

- **Template Bot**: `bots/template_bot.py` - Starting point
- **Example Bots**: 
  - `bots/call_bot.py` - Passive strategy
  - `bots/random_bot.py` - Random actions
  - `bots/advanced_bot.py` - Advanced strategy example
- **Engine Code**: `engine.py` - Understand the game rules
- **Evaluator**: `evaluator.py` - Hand evaluation functions

---

## Questions?

- Check existing bots for examples
- Review the engine code to understand game mechanics
- Test your bot thoroughly before submitting
- Good luck and may the best bot win!

---

**Happy Bot Building! 🎰♠️♥️♦️♣️**


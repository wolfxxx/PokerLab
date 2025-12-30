# pokertv.py
"""
PokerTV - Beautiful real-time visualization of poker matches between bots.
Watch bots play with a beautiful graphics interface showing:
- Real deck and card visualization
- Hole cards and community cards
- Bet progression and pot size
- Action history
- Stack sizes
- Hand progression (preflop, flop, turn, river, showdown)
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser

from engine import GameParams, Hand
from runner import BotProc, default_action

# Global state for TV mode
TV_STATE = {
    "current_match": None,
    "match_history": [],
    "is_running": False,
    "update_event": threading.Event()
}

def card_to_unicode(card: str) -> str:
    """Convert card string to Unicode playing card symbol."""
    if len(card) != 2:
        return "🂠"
    
    rank = card[0]
    suit = card[1]
    
    # Unicode playing cards (U+1F0A0 to U+1F0DF)
    suit_map = {
        's': 0x1F0A0,  # Spades
        'h': 0x1F0B0,  # Hearts
        'd': 0x1F0C0,  # Diamonds
        'c': 0x1F0D0,  # Clubs
    }
    
    rank_map = {
        'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
        '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13
    }
    
    if suit in suit_map and rank in rank_map:
        code_point = suit_map[suit] + rank_map[rank]
        return chr(code_point)
    
    return f"{rank}{suit}"

def card_to_suit_symbol(suit: str) -> str:
    """Convert suit to symbol."""
    suit_map = {
        's': '♠',  # Spades
        'h': '♥',  # Hearts
        'd': '♦',  # Diamonds
        'c': '♣',  # Clubs
    }
    return suit_map.get(suit, suit)

def card_to_rank_symbol(rank: str) -> str:
    """Convert rank to display symbol."""
    return rank

def get_card_color(suit: str) -> str:
    """Get color for suit (red for hearts/diamonds, black for spades/clubs)."""
    return "red" if suit in ['h', 'd'] else "black"

def run_match_tv(bot_paths: List[str], seed: int, decision_ms: int, 
                 hands_cap: int, output_dir: str = "pokertv_output") -> Dict:
    """Run a match and capture all game state for TV visualization."""
    params = GameParams(max_hands=hands_cap)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create bot processes
    bots = []
    bot_names = []
    try:
        for i, path in enumerate(bot_paths):
            bot_name = Path(path).stem
            bots.append(BotProc(path, bot_name))
            bot_names.append(bot_name)
        
        num_players = len(bots)
        stacks = {i: params.starting_stack for i in range(num_players)}
        button = 0
        hand_index = 0
        
        match_history = []
        
        active_players = [p for p, s in stacks.items() if s > 0]
        
        while hand_index < params.max_hands and len(active_players) >= 2:
            # Find next valid button position
            while button not in active_players:
                button = (button + 1) % num_players
            
            hand_seed = (seed * 1000003) ^ hand_index
            hand = Hand(params=params, stacks=stacks, button=button, hand_seed=hand_seed)
            
            # Capture initial hand state (before any actions, but after blinds)
            # Note: Hand is already initialized with blinds posted
            initial_pot = hand.pot()
            initial_bet = hand.current_bet
            
            hand_state = {
                "hand_number": hand_index,
                "button": button,
                "stacks": dict(stacks),
                "street": "PREFLOP",
                "hole_cards": {p: hand.hole[p].copy() for p in hand.players},
                "board": [],
                "pot": initial_pot,
                "current_bet": initial_bet,
                "to_act": hand.to_act,
                "action_history": [],
                "final_result": None
            }
            
            # Capture blinds posting from hand's action history
            blinds_info = []
            for action in hand.action_history:
                if action.get("action") in ["POST_SB", "POST_BB"]:
                    blinds_info.append({
                        "player": action.get("actor"),
                        "player_name": bot_names[action.get("actor")],
                        "action": action.get("action"),
                        "amount": action.get("amount", 0),
                        "street": "PREFLOP"
                    })
            
            # Add initial state as first "action" (preflop start with blinds posted)
            hand_state["action_history"].append({
                "player": None,
                "player_name": "DEAL",
                "action": "DEAL",
                "street": "PREFLOP",
                "pot": initial_pot,
                "stacks": dict(stacks),
                "current_bet": initial_bet,
                "to_call": 0,
                "board": [],
                "is_initial": True,
                "blinds_posted": blinds_info,
                "pot_after": initial_pot,
                "stacks_after": dict(stacks),
                "current_bet_after": initial_bet,
                "board_after": [],
                "street_after": "PREFLOP",
                "to_act_after": hand.to_act
            })
            
            # Play the hand
            hand_timeout = 0
            max_hand_actions = 100
            action_count = 0
            
            while hand.street != "HAND_OVER" and action_count < max_hand_actions:
                p = hand.to_act
                obs = hand.observation_for(p)
                resp = bots[p].ask(obs, timeout_s=decision_ms / 1000.0)
                if not resp or "action" not in resp:
                    resp = default_action(obs)
                
                # Capture state BEFORE action
                action_info = {
                    "player": p,
                    "player_name": bot_names[p],
                    "action": resp.get("action", "UNKNOWN"),
                    "street": hand.street,
                    "pot": hand.pot(),
                    "stacks": {p: s for p, s in hand.stacks.items()},
                    "current_bet": hand.current_bet,
                    "to_call": obs.get("to_call", 0),
                    "board": hand.board.copy(),
                    "to_act_before": p
                }
                
                if resp.get("action") == "RAISE" and "to" in resp:
                    action_info["raise_to"] = resp["to"]
                
                try:
                    result = hand.apply_action(p, resp)
                    action_count += 1
                    action_info["success"] = True
                except Exception:
                    resp2 = default_action(obs)
                    try:
                        result = hand.apply_action(p, resp2)
                        action_count += 1
                        action_info["action"] = resp2.get("action", "UNKNOWN")
                        action_info["success"] = True
                    except Exception:
                        result = hand.apply_action(p, {"action": "FOLD"})
                        action_count += 1
                        action_info["action"] = "FOLD"
                        action_info["success"] = True
                
                # Capture state AFTER action
                action_info["pot_after"] = hand.pot()
                action_info["stacks_after"] = {p: s for p, s in hand.stacks.items()}
                action_info["current_bet_after"] = hand.current_bet
                action_info["board_after"] = hand.board.copy()
                action_info["street_after"] = hand.street
                action_info["to_act_after"] = hand.to_act
                
                hand_state["action_history"].append(action_info)
                hand_state["street"] = hand.street
                hand_state["board"] = hand.board.copy()
                hand_state["pot"] = hand.pot()
                hand_state["current_bet"] = hand.current_bet
                hand_state["to_act"] = hand.to_act
                hand_state["stacks"] = {p: s for p, s in hand.stacks.items()}
                
                # Update TV state for real-time viewing
                TV_STATE["current_match"] = {
                    "hand_number": hand_index,
                    "current_hand": hand_state,
                    "match_stacks": dict(hand.stacks),
                    "bot_names": bot_names
                }
                TV_STATE["update_event"].set()
                
                if result is not None:
                    stacks = dict(result["final_stacks"])
                    hand_state["final_result"] = {
                        "result_type": result.get("result", "UNKNOWN"),
                        "pot": result.get("pot", 0),
                        "final_stacks": stacks,
                        "winner": result.get("winner", None),
                        "pot_winners": result.get("pot_winners", {})
                    }
                    break
            
            match_history.append(hand_state)
            stacks = dict(hand.stacks)
            button = (button + 1) % num_players
            hand_index += 1
            active_players = [p for p, s in stacks.items() if s > 0]
            
            # Small delay for TV viewing
            time.sleep(0.1)
        
        # Determine final winner
        active_players = [p for p, s in stacks.items() if s > 0]
        if len(active_players) == 1:
            winner_idx = active_players[0]
            winner_name = bot_names[winner_idx]
        elif len(active_players) == 0:
            winner_name = "TIE"
        else:
            winner_idx = max(stacks.items(), key=lambda x: x[1])[0]
            winner_name = bot_names[winner_idx]
        
        return {
            "winner": winner_name,
            "final_stacks": {bot_names[i]: stacks[i] for i in range(num_players)},
            "hands_played": hand_index,
            "match_history": match_history,
            "bot_names": bot_names
        }
    
    finally:
        for b in bots:
            b.terminate()

def generate_tv_html(match_data: Dict, output_file: str = "pokertv_output/match.html"):
    """Generate beautiful HTML interface for watching the match."""
    bot_names = match_data.get("bot_names", [])
    match_history = match_data.get("match_history", [])
    final_stacks = match_data.get("final_stacks", {})
    winner = match_data.get("winner", "Unknown")
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PokerTV - Live Match</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 10px;
            margin: 0;
            overflow-x: hidden;
        }}
        
        .container {{
            max-width: 1800px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 15px 30px;
            border-radius: 15px;
            margin-bottom: 10px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            flex-shrink: 0;
        }}
        
        .header h1 {{
            font-size: 1.8em;
            margin-bottom: 5px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .match-info {{
            display: flex;
            justify-content: space-around;
            margin-top: 20px;
            flex-wrap: wrap;
        }}
        
        .info-item {{
            text-align: center;
        }}
        
        .info-label {{
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }}
        
        .info-value {{
            font-size: 1.5em;
            font-weight: bold;
        }}
        
        .table-area {{
            background: #0f3460;
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            position: relative;
            flex: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }}
        
        .board {{
            text-align: center;
            margin: 20px 0;
        }}
        
        .board-label {{
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #ffd700;
        }}
        
        .cards-container {{
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .card {{
            width: 80px;
            height: 112px;
            background: white;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            font-weight: bold;
            font-size: 1.2em;
            transition: transform 0.3s ease;
        }}
        
        .card:hover {{
            transform: scale(1.1);
        }}
        
        .card.red {{
            color: #d32f2f;
        }}
        
        .card.black {{
            color: #212121;
        }}
        
        .card-back {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2em;
        }}
        
        .card-rank {{
            font-size: 1.5em;
        }}
        
        .card-suit {{
            font-size: 2em;
            text-align: center;
        }}
        
        .players-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        
        .player-card {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            border: 2px solid transparent;
            transition: all 0.3s ease;
        }}
        
        .player-card.active {{
            border-color: #ffd700;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
            background: rgba(255, 215, 0, 0.1);
        }}
        
        .player-card.winner {{
            border-color: #4CAF50;
            box-shadow: 0 0 20px rgba(76, 175, 80, 0.5);
        }}
        
        .player-name {{
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 15px;
            color: #ffd700;
        }}
        
        .player-stack {{
            font-size: 1.1em;
            margin-bottom: 10px;
        }}
        
        .player-hole {{
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }}
        
        .pot-display {{
            text-align: center;
            margin: 30px 0;
            font-size: 1.5em;
        }}
        
        .pot-amount {{
            color: #ffd700;
            font-size: 2em;
            font-weight: bold;
        }}
        
        .action-history {{
            background: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            padding: 15px;
            margin-top: 15px;
            max-height: 200px;
            overflow-y: auto;
            flex-shrink: 0;
        }}
        
        .action-history h3 {{
            margin-bottom: 15px;
            color: #ffd700;
        }}
        
        .action-item {{
            padding: 10px;
            margin: 5px 0;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
            border-left: 4px solid #667eea;
        }}
        
        .action-item.raise {{
            border-left-color: #ff9800;
        }}
        
        .action-item.call {{
            border-left-color: #2196F3;
        }}
        
        .action-item.fold {{
            border-left-color: #f44336;
        }}
        
        .action-item.check {{
            border-left-color: #4CAF50;
        }}
        
        .hand-selector {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 10px;
            flex-shrink: 0;
        }}
        
        .hand-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        
        .hand-controls button {{
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1.1em;
            font-weight: bold;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }}
        
        .hand-controls button:hover {{
            background: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }}
        
        .hand-controls button:active {{
            transform: translateY(0);
        }}
        
        .hand-controls button.primary {{
            background: #4CAF50;
            font-size: 1.2em;
            padding: 14px 28px;
        }}
        
        .hand-controls button.primary:hover {{
            background: #45a049;
        }}
        
        .hand-controls button:disabled {{
            background: #555;
            cursor: not-allowed;
        }}
        
        .hand-number {{
            font-size: 1.2em;
            font-weight: bold;
            margin: 0 20px;
        }}
        
        .street-indicator {{
            text-align: center;
            font-size: 1.5em;
            margin: 20px 0;
            color: #ffd700;
            font-weight: bold;
        }}
        
        .betting-info {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            text-align: center;
        }}
        
        .betting-info .current-bet {{
            font-size: 1.3em;
            color: #ff9800;
        }}
        
        .betting-info .to-call {{
            font-size: 1.1em;
            color: #2196F3;
        }}
        
        .action-controls {{
            margin-top: 15px;
        }}
        
        .action-controls button {{
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            transition: background 0.3s ease;
        }}
        
        .action-controls button:hover {{
            background: #764ba2;
        }}
        
        .action-item.current-action {{
            border-left-width: 6px !important;
            background: rgba(255, 215, 0, 0.3) !important;
            font-weight: bold;
        }}
        
        .action-item.past-action {{
            opacity: 0.7;
        }}
        
        .action-item.future-action {{
            opacity: 0.4;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎰 PokerTV - Live Match</h1>
            <div class="match-info">
                <div class="info-item">
                    <div class="info-label">Winner</div>
                    <div class="info-value">{winner}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Hands Played</div>
                    <div class="info-value">{len(match_history)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Players</div>
                    <div class="info-value">{len(bot_names)}</div>
                </div>
            </div>
        </div>
        
        <div class="hand-selector">
            <div class="hand-controls">
                <button onclick="previousHand()">◀ Previous Hand</button>
                <span class="hand-number">Hand <span id="current-hand-num">0</span> / {len(match_history)}</span>
                <button onclick="nextHand()">Next Hand ▶</button>
                <button onclick="goToHand(0)">First Hand</button>
                <button onclick="goToHand({len(match_history) - 1})">Last Hand</button>
            </div>
            <div class="action-controls" style="margin-top: 15px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: center;">
                <button onclick="previousAction()">◀◀ Previous Action</button>
                <span class="hand-number">Action <span id="current-action-num">0</span> / <span id="total-actions">0</span></span>
                <button onclick="nextAction()">Next Action ▶▶</button>
                <button onclick="autoPlayActions()" id="autoplay-actions-btn">▶▶ Auto Play Actions</button>
                <button onclick="goToAction(0)">Start of Hand</button>
            </div>
        </div>
        
        <div class="table-area" id="table-area">
            <!-- Content will be populated by JavaScript -->
        </div>
    </div>
    
    <script>
        const matchData = {json.dumps(match_data)};
        let currentHandIndex = 0;
        let currentActionIndex = 0;
        let autoPlayInterval = null;
        
        function renderHand(handIndex, actionIndex = null) {{
            if (handIndex < 0 || handIndex >= matchData.match_history.length) return;
            
            currentHandIndex = handIndex;
            const hand = matchData.match_history[handIndex];
            const tableArea = document.getElementById('table-area');
            const currentHandNum = document.getElementById('current-hand-num');
            const currentActionNum = document.getElementById('current-action-num');
            const totalActions = document.getElementById('total-actions');
            
            currentHandNum.textContent = handIndex + 1;
            totalActions.textContent = hand.action_history.length;
            
            // Use provided actionIndex or default to 0 (start of hand)
            if (actionIndex === null) {{
                actionIndex = currentActionIndex;
            }} else {{
                currentActionIndex = actionIndex;
            }}
            
            // Clamp actionIndex to valid range
            if (actionIndex < 0) actionIndex = 0;
            if (actionIndex >= hand.action_history.length) actionIndex = hand.action_history.length - 1;
            currentActionIndex = actionIndex;
            currentActionNum.textContent = actionIndex + 1;
            
            // Get state at this action
            let currentState;
            if (actionIndex === 0 && hand.action_history.length > 0) {{
                // First action (initial deal)
                const firstAction = hand.action_history[0];
                currentState = {{
                    street: firstAction.street || "PREFLOP",
                    board: firstAction.board || [],
                    pot: firstAction.pot || 0,
                    stacks: firstAction.stacks || hand.stacks || {{}},
                    current_bet: firstAction.current_bet || 0,
                    to_call: 0,
                    player: hand.to_act,
                    action: firstAction
                }};
            }} else if (actionIndex < hand.action_history.length) {{
                // Use state after the previous action
                const prevAction = hand.action_history[actionIndex - 1];
                const thisAction = hand.action_history[actionIndex];
                currentState = {{
                    street: prevAction.street_after || prevAction.street || "PREFLOP",
                    board: prevAction.board_after || prevAction.board || [],
                    pot: prevAction.pot_after || prevAction.pot || 0,
                    stacks: prevAction.stacks_after || prevAction.stacks || {{}},
                    current_bet: prevAction.current_bet_after || prevAction.current_bet || 0,
                    to_call: thisAction.to_call || 0,
                    player: thisAction.player,
                    action: thisAction
                }};
            }} else {{
                // Last action - use final state
                const lastAction = hand.action_history[hand.action_history.length - 1];
                currentState = {{
                    street: lastAction.street_after || lastAction.street || hand.street,
                    board: lastAction.board_after || lastAction.board || hand.board || [],
                    pot: lastAction.pot_after || lastAction.pot || hand.pot || 0,
                    stacks: lastAction.stacks_after || lastAction.stacks || hand.stacks || {{}},
                    current_bet: lastAction.current_bet_after || lastAction.current_bet || 0,
                    to_call: 0,
                    player: null,
                    action: lastAction
                }};
            }}
            
            let html = `
                <div class="street-indicator">${{getStreetName(currentState.street)}}</div>
                
                <div class="pot-display">
                    <div>Pot: <span class="pot-amount">${{formatNumber(currentState.pot)}}</span></div>
                    ${{currentState.pot === 150 && currentState.action && currentState.action.action === 'DEAL' ? '<div style="font-size: 0.9em; opacity: 0.8; margin-top: 5px;">(Blinds: SB $50 + BB $100)</div>' : ''}}
                </div>
                
                <div class="board">
                    <div class="board-label">Community Cards${{(currentState.board || []).length === 0 ? ' (None yet)' : ''}}</div>
                    <div class="cards-container">
                        ${{renderCards(currentState.board || [])}}
                    </div>
                </div>
                
                <div class="betting-info">
                    <div class="current-bet">Current Bet: ${{formatNumber(currentState.current_bet)}}</div>
                    ${{currentState.to_call > 0 ? `<div class="to-call">To Call: ${{formatNumber(currentState.to_call)}}</div>` : ''}}
                </div>
                
                <div class="players-container">
            `;
            
            // Render each player
            for (let i = 0; i < matchData.bot_names.length; i++) {{
                const playerName = matchData.bot_names[i];
                const stack = currentState.stacks[i] || 0;
                const isActive = currentState.player === i;
                const holeCards = hand.hole_cards[i] || [];
                const isWinner = matchData.final_stacks[playerName] === Math.max(...Object.values(matchData.final_stacks));
                
                html += `
                    <div class="player-card ${{isActive ? 'active' : ''}} ${{isWinner && handIndex === matchData.match_history.length - 1 ? 'winner' : ''}}">
                        <div class="player-name">${{playerName}}</div>
                        <div class="player-stack">Stack: ${{formatNumber(stack)}}</div>
                        <div class="player-hole">
                            ${{renderCards(holeCards, false)}}
                        </div>
                    </div>
                `;
            }}
            
            html += `</div>`;
            
            // Action history (highlight current action)
            html += `
                <div class="action-history">
                    <h3>Action History</h3>
            `;
            
            for (let i = 0; i < hand.action_history.length; i++) {{
                const action = hand.action_history[i];
                if (!action) continue;
                
                const actionClass = action.action.toLowerCase();
                const isCurrent = i === actionIndex;
                const isPast = i < actionIndex;
                
                let actionText = `${{action.player_name || 'DEAL'}} ${{action.action}}`;
                if (action.action === 'DEAL' && action.blinds_posted) {{
                    // Show blinds information for DEAL action
                    const blinds = action.blinds_posted;
                    if (blinds.length > 0) {{
                        const sb = blinds.find(b => b.action === 'POST_SB');
                        const bb = blinds.find(b => b.action === 'POST_BB');
                        actionText = `DEAL - Blinds posted: ${{sb ? sb.player_name + ' posts SB ($' + formatNumber(sb.amount) + ')' : ''}}${{sb && bb ? ', ' : ''}}${{bb ? bb.player_name + ' posts BB ($' + formatNumber(bb.amount) + ')' : ''}}`;
                    }}
                }} else if (action.action === 'RAISE' && action.raise_to) {{
                    actionText += ` to ${{formatNumber(action.raise_to)}}`;
                }} else if (action.action === 'POST_SB') {{
                    actionText = `${{action.player_name}} posts Small Blind (${{formatNumber(action.amount || 50)}})`;
                }} else if (action.action === 'POST_BB') {{
                    actionText = `${{action.player_name}} posts Big Blind (${{formatNumber(action.amount || 100)}})`;
                }}
                
                const highlightClass = isCurrent ? 'current-action' : (isPast ? 'past-action' : 'future-action');
                
                html += `
                    <div class="action-item ${{actionClass}} ${{highlightClass}}" style="${{isCurrent ? 'border-left-width: 6px; background: rgba(255, 215, 0, 0.2); font-weight: bold;' : ''}}">
                        <strong>${{action.street}}</strong> - ${{actionText}}
                        ${{action.pot ? ` (Pot: ${{formatNumber(action.pot)}})` : ''}}
                    </div>
                `;
            }}
            
            html += `</div>`;
            
            tableArea.innerHTML = html;
        }}
        
        function previousAction() {{
            if (currentActionIndex > 0) {{
                renderHand(currentHandIndex, currentActionIndex - 1);
            }}
        }}
        
        function nextAction() {{
            const hand = matchData.match_history[currentHandIndex];
            if (currentActionIndex < hand.action_history.length - 1) {{
                renderHand(currentHandIndex, currentActionIndex + 1);
            }}
        }}
        
        function goToAction(index) {{
            renderHand(currentHandIndex, index);
        }}
        
        let autoPlaySpeed = 1000;
        
        function updateAutoPlaySpeed() {{
            const select = document.getElementById('speed-select');
            autoPlaySpeed = parseInt(select.value);
            if (autoPlayInterval) {{
                clearInterval(autoPlayInterval);
                autoPlayInterval = setInterval(playNextAction, autoPlaySpeed);
            }}
        }}
        
        function playNextAction() {{
            const hand = matchData.match_history[currentHandIndex];
            if (currentActionIndex < hand.action_history.length - 1) {{
                nextAction();
            }} else {{
                // Move to next hand
                if (currentHandIndex < matchData.match_history.length - 1) {{
                    currentHandIndex++;
                    currentActionIndex = 0;
                    renderHand(currentHandIndex, 0);
                }} else {{
                    autoPlayActions(); // Stop at end
                }}
            }}
        }}
        
        function autoPlayActions() {{
            const btn = document.getElementById('autoplay-actions-btn');
            if (autoPlayInterval) {{
                clearInterval(autoPlayInterval);
                autoPlayInterval = null;
                btn.textContent = '▶▶ AUTO PLAY';
                btn.classList.remove('primary');
            }} else {{
                autoPlayInterval = setInterval(playNextAction, autoPlaySpeed);
                btn.textContent = '⏸ PAUSE';
                btn.classList.add('primary');
            }}
        }}
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {{
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            
            switch(e.key) {{
                case ' ': // Spacebar - toggle auto-play
                    e.preventDefault();
                    autoPlayActions();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    previousAction();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    nextAction();
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    previousHand();
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    nextHand();
                    break;
            }}
        }});
        
        function renderCards(cards, faceDown = false) {{
            if (!cards || cards.length === 0) {{
                // For community cards (board), show nothing when empty
                // For hole cards, show face-down cards
                if (faceDown) {{
                    return '<div class="card card-back">🂠</div><div class="card card-back">🂠</div>';
                }}
                return ''; // Empty board - no cards shown
            }}
            
            return cards.map(card => {{
                if (faceDown) {{
                    return '<div class="card card-back">🂠</div>';
                }}
                
                const rank = card[0];
                const suit = card[1];
                const color = (suit === 'h' || suit === 'd') ? 'red' : 'black';
                const suitSymbol = getSuitSymbol(suit);
                
                // Convert poker notation to display format
                const rankDisplay = rank === 'T' ? '10' : rank;
                
                return `
                    <div class="card ${{color}}">
                        <div class="card-rank">${{rankDisplay}}</div>
                        <div class="card-suit">${{suitSymbol}}</div>
                    </div>
                `;
            }}).join('');
        }}
        
        function getSuitSymbol(suit) {{
            const suits = {{'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}};
            return suits[suit] || suit;
        }}
        
        function getStreetName(street) {{
            const names = {{
                'PREFLOP': 'Pre-Flop',
                'FLOP': 'Flop',
                'TURN': 'Turn',
                'RIVER': 'River',
                'SHOWDOWN': 'Showdown',
                'HAND_OVER': 'Hand Over'
            }};
            return names[street] || street;
        }}
        
        function formatNumber(num) {{
            return num.toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ",");
        }}
        
        function previousHand() {{
            if (currentHandIndex > 0) {{
                currentActionIndex = 0;
                renderHand(currentHandIndex - 1, 0);
            }}
        }}
        
        function nextHand() {{
            if (currentHandIndex < matchData.match_history.length - 1) {{
                currentActionIndex = 0;
                renderHand(currentHandIndex + 1, 0);
            }}
        }}
        
        function goToHand(index) {{
            if (index >= 0 && index < matchData.match_history.length) {{
                currentActionIndex = 0;
                renderHand(index, 0);
            }}
        }}
        
        // Initialize - start at first hand, first action
        renderHand(0, 0);
    </script>
</body>
</html>
"""
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

class TVRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for serving PokerTV files."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="pokertv_output", **kwargs)
    
    def log_message(self, format, *args):
        # Suppress log messages
        pass

def start_tv_server(port: int = 8000):
    """Start a local web server for PokerTV."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, TVRequestHandler)
    print(f"PokerTV server started at http://localhost:{port}")
    print("Open http://localhost:{port}/match.html in your browser")
    return httpd

def main():
    ap = argparse.ArgumentParser(
        description="PokerTV - Watch bots play with beautiful real-time visualization",
        formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("--bots", nargs="+", required=True,
                   help="List of bot paths, e.g., --bots bot1.py bot2.py bot3.py")
    ap.add_argument("--seed", type=int, default=12345,
                   help="Random seed for the match (default: 12345)")
    ap.add_argument("--hands_cap", type=int, default=50,
                   help="Maximum hands to play (default: 50)")
    ap.add_argument("--decision_ms", type=int, default=500,
                   help="Decision timeout in milliseconds (default: 500)")
    ap.add_argument("--port", type=int, default=8000,
                   help="Port for web server (default: 8000)")
    ap.add_argument("--no-browser", action="store_true",
                   help="Don't automatically open browser")
    
    args = ap.parse_args()
    
    if len(args.bots) < 2:
        print("Error: Need at least 2 bots")
        return
    
    print("🎰 Starting PokerTV match...")
    print(f"Bots: {[Path(p).stem for p in args.bots]}")
    print(f"Seed: {args.seed}, Max hands: {args.hands_cap}")
    print()
    
    # Run match and capture all data
    match_data = run_match_tv(
        args.bots,
        args.seed,
        args.decision_ms,
        args.hands_cap,
        "pokertv_output"
    )
    
    # Generate HTML
    print("📺 Generating PokerTV interface...")
    generate_tv_html(match_data, "pokertv_output/match.html")
    
    # Start web server
    print(f"🌐 Starting web server on port {args.port}...")
    httpd = start_tv_server(args.port)
    
    # Open browser
    if not args.no_browser:
        time.sleep(1)
        webbrowser.open(f"http://localhost:{args.port}/match.html")
    
    print("\n✅ PokerTV is ready!")
    print(f"   Open http://localhost:{args.port}/match.html in your browser")
    print("   Press Ctrl+C to stop the server")
    print()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down PokerTV server...")
        httpd.shutdown()

if __name__ == "__main__":
    main()


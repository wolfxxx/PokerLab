# tournament.py
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

from engine import GameParams, Hand
from stats import TournamentStats
from leaderboard import generate_leaderboard, generate_h2h_summary, export_to_json, export_to_csv

# Import BotProc and default_action from runner
from runner import BotProc, default_action

def discover_bots(bots_dir: str = "bots") -> List[str]:
    """Discover all bot files in the bots directory."""
    bots_path = Path(bots_dir)
    if not bots_path.exists():
        return []
    
    bot_files = []
    for file in bots_path.iterdir():
        if file.suffix == ".py" and file.name != "template_bot.py":
            bot_files.append(str(file))
    
    return sorted(bot_files)

def run_match(bot_paths: List[str], seed: int, decision_ms: int, 
              hands_cap: int, verbose: bool = False) -> Optional[Dict]:
    """Run a single free-for-all match with given bots.
    
    Returns match result dict with winner and final stacks, or None if error.
    """
    params = GameParams(max_hands=hands_cap)
    
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
        
        if verbose:
            print(f"  Match seed={seed} players={num_players}")
        
        # Get active players
        active_players = [p for p, s in stacks.items() if s > 0]
        
        while hand_index < params.max_hands and len(active_players) >= 2:
            # Find next valid button position
            while button not in active_players:
                button = (button + 1) % num_players
            
            hand_seed = (seed * 1000003) ^ hand_index
            hand = Hand(params=params, stacks=stacks, button=button, hand_seed=hand_seed)
            
            # Play the hand
            hand_timeout = 0
            max_hand_actions = 100  # Prevent infinite loops
            action_count = 0
            
            while hand.street != "HAND_OVER" and action_count < max_hand_actions:
                p = hand.to_act
                obs = hand.observation_for(p)
                resp = bots[p].ask(obs, timeout_s=decision_ms / 1000.0)
                if not resp or "action" not in resp:
                    resp = default_action(obs)
                
                try:
                    result = hand.apply_action(p, resp)
                    action_count += 1
                except Exception:
                    resp2 = default_action(obs)
                    try:
                        result = hand.apply_action(p, resp2)
                        action_count += 1
                    except Exception:
                        result = hand.apply_action(p, {"action": "FOLD"})
                        action_count += 1
                
                if result is not None:
                    stacks = dict(result["final_stacks"])
                    break
            
            # Safety check - if hand didn't end, force end it
            if hand.street != "HAND_OVER":
                if verbose:
                    print(f"  Warning: Hand {hand_index} didn't complete, forcing end")
                # Award pot to player with most chips
                winner_idx = max(stacks.items(), key=lambda x: x[1])[0]
                stacks[winner_idx] += sum(stacks.values()) - stacks[winner_idx]
                for i in range(num_players):
                    if i != winner_idx:
                        stacks[i] = 0
            
            # Next hand
            button = (button + 1) % num_players
            hand_index += 1
            active_players = [p for p, s in stacks.items() if s > 0]
        
        # Determine winner
        active_players = [p for p, s in stacks.items() if s > 0]
        if len(active_players) == 1:
            winner_idx = active_players[0]
            winner_name = bot_names[winner_idx]
        elif len(active_players) == 0:
            # Tie - find player with highest stack
            winner_idx = max(stacks.items(), key=lambda x: x[1])[0]
            winner_name = bot_names[winner_idx]
        else:
            # Multiple players left - find highest stack
            winner_idx = max(stacks.items(), key=lambda x: x[1])[0]
            winner_name = bot_names[winner_idx]
        
        # Map final stacks to bot names
        final_stacks = {bot_names[i]: stacks[i] for i in range(num_players)}
        
        return {
            "winner": winner_name,
            "final_stacks": final_stacks,
            "bot_names": bot_names,
            "hands_played": hand_index
        }
    
    except Exception as e:
        if verbose:
            print(f"  Error in match: {e}")
        return None
    
    finally:
        for b in bots:
            b.terminate()

def run_tournament(bot_paths: List[str], num_matches: int, base_seed: int,
                  decision_ms: int, hands_cap: int, verbose: bool = False) -> TournamentStats:
    """Run a tournament with multiple matches."""
    stats = TournamentStats()
    
    # Create mapping of bot names to paths
    bot_paths_map = {Path(p).stem: p for p in bot_paths}
    
    print(f"Starting tournament with {len(bot_paths)} bots, {num_matches} matches")
    print(f"Bots: {list(bot_paths_map.keys())}")
    print()
    
    for match_num in range(num_matches):
        seed = base_seed + match_num
        try:
            result = run_match(bot_paths, seed, decision_ms, hands_cap, verbose=False)
            
            if result:
                stats.record_match_result(
                    result["winner"],
                    result["final_stacks"],
                    result["bot_names"],
                    bot_paths_map
                )
                
                # Show progress every match (for better GUI feedback)
                print(f"Match {match_num + 1}/{num_matches}: {result['winner']} wins", flush=True)
                
                # Show progress every 100 matches for large tournaments
                if (match_num + 1) % 100 == 0:
                    print(f"Progress: {match_num + 1}/{num_matches} matches completed ({100 * (match_num + 1) / num_matches:.1f}%)", flush=True)
            else:
                if verbose:
                    print(f"Match {match_num + 1}/{num_matches}: ERROR - skipping", flush=True)
        except Exception as e:
            if verbose:
                print(f"Match {match_num + 1}/{num_matches}: Exception - {e}", flush=True)
            continue
        else:
            if verbose:
                print(f"Match {match_num + 1}/{num_matches}: ERROR", flush=True)
    
    print(f"\nTournament completed! Processing results...", flush=True)
    
    return stats

def main():
    ap = argparse.ArgumentParser(
        description="Run a poker bot tournament",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run tournament with all bots in bots/ directory
  python tournament.py
  
  # Run with custom number of matches
  python tournament.py --matches 200
  
  # Run with specific bots only
  python tournament.py --bots bots/my_bot.py bots/friend_bot.py
  
  # Save results to JSON file
  python tournament.py --output results.json
  
  # Save results to CSV file
  python tournament.py --output results.csv
  
  # Generate beautiful HTML report with charts
  python tournament.py --output results.html
        """
    )
    ap.add_argument("--bots", nargs="+", default=None,
                   help="List of bot paths. If not specified, auto-discovers bots in bots/ directory")
    ap.add_argument("--matches", type=int, default=100,
                   help="Number of matches to run (default: 100)")
    ap.add_argument("--seed", type=int, default=12345,
                   help="Base seed for random number generation (default: 12345)")
    ap.add_argument("--decision_ms", type=int, default=200,
                   help="Decision timeout in milliseconds (default: 200)")
    ap.add_argument("--hands_cap", type=int, default=2000,
                   help="Maximum hands per match (default: 2000)")
    ap.add_argument("--output", type=str, default=None,
                   help="Output file path (JSON or CSV format)")
    ap.add_argument("--verbose", action="store_true",
                   help="Show detailed match information")
    args = ap.parse_args()
    
    # Discover or use specified bots
    if args.bots:
        bot_paths = args.bots
    else:
        bot_paths = discover_bots()
        if not bot_paths:
            print("Error: No bots found in bots/ directory")
            print("Either place bot files in bots/ or specify with --bots")
            return
    
    if len(bot_paths) < 2:
        print("Error: Need at least 2 bots for a tournament")
        return
    
    # Run tournament
    stats = run_tournament(
        bot_paths,
        args.matches,
        args.seed,
        args.decision_ms,
        args.hands_cap,
        args.verbose
    )
    
    # Generate and display leaderboard
    all_stats = stats.get_all_stats()
    print("\n" + "=" * 80)
    print("TOURNAMENT RESULTS")
    print("=" * 80)
    print()
    print(generate_leaderboard(all_stats))
    print(generate_h2h_summary(all_stats))
    
    # Export to file if requested
    if args.output:
        output_path = Path(args.output)
        if output_path.suffix.lower() == ".csv":
            export_to_csv(all_stats, str(output_path))
            print(f"\nResults exported to {output_path}")
        elif output_path.suffix.lower() == ".html":
            from leaderboard import export_to_html
            tournament_info = {
                "matches": args.matches,
                "bots": len(bot_paths),
                "seed": args.seed
            }
            export_to_html(all_stats, str(output_path), tournament_info)
            print(f"\nBeautiful HTML report exported to {output_path}")
            print(f"   Open it in your browser to view the interactive charts!")
        else:
            # Default to JSON
            data = export_to_json(all_stats)
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\nResults exported to {output_path}")

if __name__ == "__main__":
    main()


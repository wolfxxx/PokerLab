# runner.py
from __future__ import annotations
import argparse
import json
import queue
import subprocess
import sys
import threading
from typing import Optional, Tuple

from engine import GameParams, Hand

class BotProc:
    def __init__(self, path: str, name: str):
        self.path = path
        self.name = name
        self.p = subprocess.Popen(
            [sys.executable, path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.q = queue.Queue()
        self._t = threading.Thread(target=self._reader, daemon=True)
        self._t.start()

    def _reader(self):
        assert self.p.stdout is not None
        for line in self.p.stdout:
            self.q.put(line.rstrip("\n"))

    def ask(self, msg: dict, timeout_s: float) -> Optional[dict]:
        assert self.p.stdin is not None
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        try:
            line = self.q.get(timeout=timeout_s)
        except queue.Empty:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def terminate(self):
        if self.p.poll() is None:
            self.p.kill()

def default_action(obs: dict) -> dict:
    legal = obs.get("legal_actions", {})
    if "CHECK" in legal:
        return {"action": "CHECK"}
    if "CALL" in legal:
        return {"action": "CALL"}
    if "FOLD" in legal:
        return {"action": "FOLD"}
    # if nothing legal (all-in), shouldn't be asked
    return {"action": "CHECK"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bots", nargs="+", required=True,
                   help="List of bot paths, e.g., --bots bot1.py bot2.py bot3.py")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--hands_cap", type=int, default=2000)
    ap.add_argument("--decision_ms", type=int, default=200)
    args = ap.parse_args()

    if len(args.bots) < 2:
        print("Error: Need at least 2 bots")
        return

    params = GameParams(max_hands=args.hands_cap)

    # Create bot processes
    bots = [BotProc(path, f"Bot{i}") for i, path in enumerate(args.bots)]
    num_players = len(bots)
    
    # Initialize stacks for all players
    stacks = {i: params.starting_stack for i in range(num_players)}
    button = 0
    hand_index = 0

    print(f"Starting match. seed={args.seed} players={num_players} stacks={stacks}")

    try:
        # Get active players (those with chips)
        active_players = [p for p, s in stacks.items() if s > 0]
        
        while hand_index < params.max_hands and len(active_players) >= 2:
            # Find next valid button position
            while button not in active_players:
                button = (button + 1) % num_players
            
            hand_seed = (args.seed * 1000003) ^ hand_index
            hand = Hand(params=params, stacks=stacks, button=button, hand_seed=hand_seed)

            # play the hand
            while hand.street != "HAND_OVER":
                p = hand.to_act
                # if all-in player, engine won't request them (but just in case)
                obs = hand.observation_for(p)
                resp = bots[p].ask(obs, timeout_s=args.decision_ms / 1000.0)
                if not resp or "action" not in resp:
                    resp = default_action(obs)

                try:
                    result = hand.apply_action(p, resp)
                except Exception as e:
                    # illegal action -> penalize with default action
                    resp2 = default_action(obs)
                    try:
                        result = hand.apply_action(p, resp2)
                    except Exception:
                        # still failing: force fold
                        result = hand.apply_action(p, {"action": "FOLD"})

                if result is not None:
                    stacks = dict(result["final_stacks"])
                    result_str = result['result']
                    if result_str == "SHOWDOWN" and "pot_winners" in result:
                        winners_str = ", ".join([f"Bot{w}(+{result['pot_winners'][w]})" for w in result['pot_winners']])
                        print(f"Hand {hand_index} over: {result_str} pot={result['pot']} winners={winners_str} stacks={stacks}")
                    elif "winner" in result:
                        print(f"Hand {hand_index} over: {result_str} pot={result['pot']} winner=Bot{result['winner']} stacks={stacks}")
                    else:
                        print(f"Hand {hand_index} over: {result_str} pot={result['pot']} stacks={stacks}")
                    break

            # next hand: rotate button to next active player
            button = (button + 1) % num_players
            hand_index += 1
            active_players = [p for p, s in stacks.items() if s > 0]

        # Determine winner
        active_players = [p for p, s in stacks.items() if s > 0]
        if len(active_players) == 1:
            winner = f"Bot{active_players[0]}"
        elif len(active_players) == 0:
            winner = "TIE"
        else:
            winner = "CAP_REACHED"
        print(f"Match ended: {winner}, hands={hand_index}, stacks={stacks}")

    finally:
        for b in bots:
            b.terminate()

if __name__ == "__main__":
    main()

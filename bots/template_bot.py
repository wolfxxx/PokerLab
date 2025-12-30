# bots/template_bot.py
import json
import sys

STATE = {}

def act(obs):
    # obs includes hero_hole, board, stacks, pot, legal_actions, action_history, etc.
    legal = obs["legal_actions"]

    # TODO: your strategy here
    if "CHECK" in legal:
        return {"action": "CHECK"}
    if "CALL" in legal:
        return {"action": "CALL"}
    if "FOLD" in legal:
        return {"action": "FOLD"}
    return {"action": "CHECK"}

for line in sys.stdin:
    obs = json.loads(line)
    if obs.get("type") == "act":
        print(json.dumps(act(obs)))
        sys.stdout.flush()

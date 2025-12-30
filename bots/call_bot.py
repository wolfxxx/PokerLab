# bots/call_bot.py
import json
import sys

def choose(obs):
    legal = obs["legal_actions"]
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
        print(json.dumps(choose(obs)))
        sys.stdout.flush()

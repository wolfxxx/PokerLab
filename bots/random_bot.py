# bots/random_bot.py
import json
import random
import sys

rng = random.Random(1)

def choose(obs):
    legal = obs["legal_actions"]
    if "RAISE" in legal and rng.random() < 0.2:
        lo = int(legal["RAISE"]["min_raise_to"])
        hi = int(legal["RAISE"]["max_raise_to"])
        to = rng.randint(lo, hi)
        return {"action": "RAISE", "to": to}
    # prefer check/call
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

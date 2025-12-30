# bots/allin_bot.py
"""
All-in bot: Always goes all-in on every hand.
This is an extreme aggressive strategy for testing purposes.
"""

import json
import sys

def act(obs):
    """Always go all-in if possible, otherwise call/check."""
    legal = obs.get("legal_actions", {})
    
    # If we can raise, go all-in
    if "RAISE" in legal:
        raise_info = legal["RAISE"]
        max_raise = raise_info.get("max_raise_to", 0)
        
        # Go all-in (raise to maximum)
        if max_raise > 0:
            return {"action": "RAISE", "to": max_raise}
    
    # If we can call, call (might be all-in call)
    if "CALL" in legal:
        return {"action": "CALL"}
    
    # If we can check, check
    if "CHECK" in legal:
        return {"action": "CHECK"}
    
    # Last resort: fold (shouldn't happen)
    if "FOLD" in legal:
        return {"action": "FOLD"}
    
    # Default fallback
    return {"action": "CHECK"}

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
            if "RAISE" in legal:
                raise_info = legal["RAISE"]
                max_raise = raise_info.get("max_raise_to", 0)
                if max_raise > 0:
                    print(json.dumps({"action": "RAISE", "to": max_raise}))
                else:
                    print(json.dumps({"action": "CALL"}))
            elif "CALL" in legal:
                print(json.dumps({"action": "CALL"}))
            elif "CHECK" in legal:
                print(json.dumps({"action": "CHECK"}))
            else:
                print(json.dumps({"action": "FOLD"}))
            sys.stdout.flush()
        except:
            pass


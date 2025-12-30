# Example PokerTV usage - Watch bots play
# PowerShell script

# Basic usage - watch two bots
python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py --hands_cap 10 --seed 42

# Advanced usage - watch multiple bots with all options
# python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py bots/uberbot2.py --seed 42 --hands_cap 20 --decision_ms 500 --port 8000

# Watch without auto-opening browser
# python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py --no-browser


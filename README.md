# PokerLab 🎰

A comprehensive poker bot testing framework for Texas Hold'em. Build, test, and compete with AI poker bots in tournaments with detailed statistics and beautiful visualizations.

## Features

- 🎮 **Multi-Player Support**: Play with 2+ bots simultaneously
- 🏆 **Tournament System**: Run free-for-all matches with customizable settings
- 📊 **Statistics & Leaderboards**: Track win rates, head-to-head records, and performance metrics
- 📈 **Beautiful HTML Reports**: Interactive charts and visualizations of tournament results
- 📺 **PokerTV**: Watch bots play in real-time with step-by-step action replay
- 🎨 **GUI Interface**: User-friendly graphical interface for launching tournaments and PokerTV
- 🤖 **Bot Framework**: Easy-to-use bot creation system with JSON-based communication

## Quick Start

### Prerequisites

- Python 3.7 or higher
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/wolfxxx/PokerLab.git
cd PokerLab
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate
```

3. No additional dependencies required! The project uses only Python's standard library.
   
   **Note**: The GUI (`pokerlab_gui.py`) requires `tkinter`, which is included with most Python installations. If you encounter issues, install it:
   - **Ubuntu/Debian**: `sudo apt-get install python3-tk`
   - **macOS**: Usually pre-installed
   - **Windows**: Usually pre-installed

## Usage

### Command Line

#### Run a Tournament

Run a tournament with all bots in the `bots/` directory:
```bash
python tournament.py
```

Run with specific bots:
```bash
python tournament.py --bots bots/uberbot1.py bots/uberbot2.py bots/uberbot3.py
```

Customize tournament settings:
```bash
python tournament.py --matches 200 --seed 42 --output results.html
```

#### Watch a Match (PokerTV)

Watch bots play in real-time:
```bash
python pokertv.py --bots bots/uberbot1.py bots/uberbot2.py --hands_cap 10
```

### Graphical Interface

Launch the GUI for an easy-to-use interface:
```bash
python pokerlab_gui.py
```

The GUI allows you to:
- Select bots visually
- Configure tournament settings
- Launch tournaments or PokerTV
- View results directly in your browser

## Project Structure

```
PokerLab/
├── bots/                  # Bot implementations
│   ├── template_bot.py   # Template for creating new bots
│   ├── call_bot.py       # Simple calling bot
│   ├── random_bot.py     # Random action bot
│   ├── advanced_bot.py   # Intermediate strategy bot
│   ├── uberbot1.py       # Advanced bot v1
│   ├── uberbot2.py       # Advanced bot v2
│   ├── uberbot3.py       # Advanced bot v3
│   ├── uberbot4.py       # Advanced bot v4
│   ├── uberbot5.py       # SPR-based strategy bot
│   ├── uberbot6.py       # All-in bot destroyer
│   └── allin_bot.py      # Always all-in bot
├── engine.py              # Core game logic
├── evaluator.py           # Hand evaluation
├── runner.py              # Single match runner
├── tournament.py          # Tournament system
├── stats.py               # Statistics tracking
├── leaderboard.py         # Leaderboard generation
├── pokertv.py             # Real-time visualization
├── pokerlab_gui.py        # GUI interface
├── BOT_CREATION_GUIDE.md  # Guide for creating bots
└── README.md              # This file
```

## Creating Your Own Bot

See [BOT_CREATION_GUIDE.md](BOT_CREATION_GUIDE.md) for detailed instructions.

### Quick Example

Create a bot file in `bots/` directory:

```python
import json
import sys

def act(obs):
    """Make a decision based on observation."""
    legal = obs.get("legal_actions", {})
    hero_hole = obs.get("hero_hole", [])
    pot = obs.get("pot", 0)
    to_call = obs.get("to_call", 0)
    
    # Simple strategy: call with any pair, fold otherwise
    if len(hero_hole) == 2:
        if hero_hole[0][0] == hero_hole[1][0]:  # Pair
            if "CALL" in legal:
                return {"action": "CALL"}
    
    if "FOLD" in legal:
        return {"action": "FOLD"}
    return {"action": "CHECK"}

# Main loop
for line in sys.stdin:
    try:
        obs = json.loads(line)
        if obs.get("type") == "act":
            result = act(obs)
            print(json.dumps(result))
            sys.stdout.flush()
    except Exception:
        pass
```

## Tournament Options

### Command Line Arguments

```bash
python tournament.py [OPTIONS]

Options:
  --bots BOT1 BOT2 ...    List of bot paths (default: auto-discover)
  --matches N              Number of matches (default: 100)
  --seed N                 Random seed (default: 12345)
  --decision_ms N          Decision timeout in ms (default: 200)
  --hands_cap N             Max hands per match (default: 2000)
  --output FILE            Output file (JSON, CSV, or HTML)
  --verbose                Show detailed match information
```

### Output Formats

- **JSON**: Machine-readable data
- **CSV**: Spreadsheet-compatible format
- **HTML**: Beautiful interactive report with charts

## Game Rules

- **Starting Stack**: 10,000 chips per player
- **Blinds**: Small Blind 50, Big Blind 100
- **Max Hands**: 2,000 per match (configurable)
- **Format**: No-limit Texas Hold'em
- **Players**: 2+ players supported

## Bot Communication Protocol

Bots communicate via JSON over stdin/stdout:

**Observation** (sent to bot):
```json
{
  "type": "act",
  "hero": 0,
  "hero_hole": ["As", "Kh"],
  "board": ["Qc", "Jd", "Th"],
  "pot": 500,
  "to_call": 100,
  "stacks": {0: 9500, 1: 10500},
  "street": "FLOP",
  "legal_actions": {
    "FOLD": {},
    "CALL": {},
    "RAISE": {"min_raise_to": 200, "max_raise_to": 9500}
  }
}
```

**Action** (bot responds):
```json
{"action": "RAISE", "to": 500}
```

## Example Bots

- **call_bot**: Always calls/checks
- **random_bot**: Random actions
- **advanced_bot**: Intermediate strategy with pot odds
- **uberbot1-6**: Advanced bots with various strategies:
  - **uberbot1**: Opponent modeling, implied odds
  - **uberbot2**: Monte Carlo simulation, ICM awareness
  - **uberbot3**: Advanced opponent profiling
  - **uberbot4**: Ultimate strategy with all features
  - **uberbot5**: SPR-based (Stack-to-Pot Ratio) strategy
  - **uberbot6**: Specialized all-in bot destroyer
- **allin_bot**: Always goes all-in (for testing)

## Contributing

Contributions are welcome! Feel free to:
- Create new bots
- Improve existing bots
- Add new features
- Fix bugs
- Improve documentation

## License

This project is open source and available for educational and personal use.

## Acknowledgments

Built for learning and experimenting with poker AI strategies. Have fun building and testing your bots!

---

**Happy Bot Building! 🚀**


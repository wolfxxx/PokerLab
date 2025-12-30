# 🎰 PokerTV - Watch Bots Play Live!

PokerTV is a beautiful real-time visualization tool that lets you watch your poker bots play against each other with a stunning graphics interface.

## Features

✨ **Beautiful Visual Interface**
- Real-time card visualization with proper suits and colors
- Community cards displayed on the table
- Player cards (face-down for opponents, revealed at showdown)
- Smooth animations and transitions

📊 **Complete Game Information**
- Current pot size
- Stack sizes for each player
- Betting progression
- Current bet and amount to call
- Street indicator (Pre-Flop, Flop, Turn, River, Showdown)

📜 **Action History**
- Complete chronological list of all actions
- Color-coded by action type (Raise, Call, Fold, Check)
- Shows which player acted and when

🎮 **Interactive Controls**
- Navigate between hands with Previous/Next buttons
- Jump to first or last hand
- Auto-play mode to watch hands automatically
- Hand counter showing current hand number

## Usage

### Basic Usage

**Windows PowerShell:**
```powershell
python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py
```

**Linux/Mac (Bash):**
```bash
python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py
```

### Advanced Options

**Windows PowerShell:**
```powershell
python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py bots/uberbot2.py --seed 42 --hands_cap 50 --decision_ms 500 --port 8000 --no-browser
```

**Linux/Mac (Bash):**
```bash
python pokertv.py \
    --bots bots/uberbot4.py bots/uberbot3.py bots/uberbot2.py \
    --seed 42 \
    --hands_cap 50 \
    --decision_ms 500 \
    --port 8000 \
    --no-browser
```

### Command Line Arguments

- `--bots` (required): List of bot paths to play against each other
- `--seed` (default: 12345): Random seed for the match
- `--hands_cap` (default: 50): Maximum number of hands to play
- `--decision_ms` (default: 500): Decision timeout in milliseconds
- `--port` (default: 8000): Port for the web server
- `--no-browser`: Don't automatically open browser (useful for remote servers)

## How It Works

1. **Match Execution**: PokerTV runs a complete match between the specified bots, capturing all game state at every action.

2. **HTML Generation**: A beautiful HTML interface is generated with all match data embedded.

3. **Web Server**: A local web server starts on the specified port (default 8000).

4. **Browser Viewing**: The interface automatically opens in your browser (unless `--no-browser` is used).

## Example

Watch uberbot4 play against uberbot3 for 10 hands:

**Windows PowerShell:**
```powershell
python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py --hands_cap 10
```

**Linux/Mac (Bash):**
```bash
python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py --hands_cap 10
```

This will:
1. Run the match
2. Generate the HTML interface
3. Start a web server on port 8000
4. Open your browser to view the match

## Interface Guide

### Header
- Shows match winner
- Total hands played
- Number of players

### Table Area
- **Community Cards**: The board cards (flop, turn, river) displayed in the center
- **Player Cards**: Each player's hole cards (face-down for opponents)
- **Pot Display**: Current pot size
- **Betting Info**: Current bet and amount to call

### Player Cards
- **Active Player**: Highlighted with a gold border
- **Winner**: Highlighted with a green border at the end
- Shows player name, stack size, and hole cards

### Action History
- Scrollable list of all actions
- Color-coded by action type:
  - 🟠 **Orange**: Raise
  - 🔵 **Blue**: Call
  - 🔴 **Red**: Fold
  - 🟢 **Green**: Check

### Controls
- **◀ Previous**: Go to previous hand
- **Next ▶**: Go to next hand
- **▶ Auto Play**: Automatically advance through hands (2 seconds per hand)
- **First Hand**: Jump to the first hand
- **Last Hand**: Jump to the last hand

## Tips

- Use **Auto Play** mode to watch the entire match automatically
- Navigate to specific hands to analyze interesting situations
- Check the action history to understand betting patterns
- Watch how stack sizes change throughout the match

## Troubleshooting

**Port already in use?**
- Use `--port` to specify a different port: `--port 8080`

**Browser doesn't open?**
- Use `--no-browser` and manually open `http://localhost:8000/match.html`

**Match takes too long?**
- Reduce `--hands_cap` to play fewer hands
- Reduce `--decision_ms` to speed up bot decisions

**Want to watch more players?**
- Add more bots: `--bots bot1.py bot2.py bot3.py bot4.py`

## Technical Details

- The HTML file is saved to `pokertv_output/match.html`
- All match data is embedded in the HTML (no external files needed)
- The web server serves files from the `pokertv_output` directory
- Press Ctrl+C to stop the server

Enjoy watching your bots play! 🎰🎉


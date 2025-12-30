# stats.py
from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

@dataclass
class BotStats:
    """Statistics for a single bot."""
    bot_name: str
    bot_path: str
    wins: int = 0
    losses: int = 0
    total_chips: int = 0  # Sum of final chips across all matches
    matches_played: int = 0
    
    # Head-to-head records: opponent_name -> (wins, losses)
    h2h: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate as percentage."""
        if self.matches_played == 0:
            return 0.0
        return (self.wins / self.matches_played) * 100.0
    
    @property
    def avg_chips(self) -> float:
        """Calculate average final chip count."""
        if self.matches_played == 0:
            return 0.0
        return self.total_chips / self.matches_played
    
    def record_win(self, final_chips: int, opponents: List[str]):
        """Record a win for this bot."""
        self.wins += 1
        self.matches_played += 1
        self.total_chips += final_chips
        
        # Update head-to-head: this bot beat all opponents
        for opponent in opponents:
            if opponent not in self.h2h:
                self.h2h[opponent] = (0, 0)
            wins, losses = self.h2h[opponent]
            self.h2h[opponent] = (wins + 1, losses)
    
    def record_loss(self, final_chips: int, opponents: List[str], winner: str):
        """Record a loss for this bot."""
        self.losses += 1
        self.matches_played += 1
        self.total_chips += final_chips
        
        # Update head-to-head: winner beat this bot
        if winner in self.h2h:
            wins, losses = self.h2h[winner]
            self.h2h[winner] = (wins, losses + 1)
        else:
            self.h2h[winner] = (0, 1)
    
    def get_h2h_summary(self, opponent: str) -> str:
        """Get head-to-head summary string for an opponent."""
        if opponent not in self.h2h:
            return ""
        wins, losses = self.h2h[opponent]
        return f"{wins}-{losses}"

class TournamentStats:
    """Container for all bot statistics in a tournament."""
    
    def __init__(self):
        self.stats: Dict[str, BotStats] = {}
    
    def get_or_create(self, bot_name: str, bot_path: str) -> BotStats:
        """Get existing stats or create new one for a bot."""
        if bot_name not in self.stats:
            self.stats[bot_name] = BotStats(bot_name=bot_name, bot_path=bot_path)
        return self.stats[bot_name]
    
    def record_match_result(self, winner_name: str, final_stacks: Dict[str, int], 
                          bot_names: List[str], bot_paths: Dict[str, str]):
        """Record the result of a match."""
        # Get all opponent names (excluding winner)
        opponents = [name for name in bot_names if name != winner_name]
        
        # Record win for winner
        winner_path = bot_paths.get(winner_name, "")
        winner_stats = self.get_or_create(winner_name, winner_path)
        winner_stats.record_win(final_stacks.get(winner_name, 0), opponents)
        
        # Record losses for all other bots
        for bot_name in bot_names:
            if bot_name != winner_name:
                bot_path = bot_paths.get(bot_name, "")
                bot_stats = self.get_or_create(bot_name, bot_path)
                bot_stats.record_loss(
                    final_stacks.get(bot_name, 0),
                    opponents,
                    winner_name
                )
    
    def get_all_stats(self) -> List[BotStats]:
        """Get all bot statistics as a list."""
        return list(self.stats.values())
    
    def get_bot_names(self) -> List[str]:
        """Get list of all bot names."""
        return list(self.stats.keys())


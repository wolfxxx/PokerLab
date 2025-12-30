# leaderboard.py
from __future__ import annotations
from typing import List
from stats import BotStats
import json
from datetime import datetime

def generate_leaderboard(stats_list: List[BotStats]) -> str:
    """Generate a formatted leaderboard table."""
    if not stats_list:
        return "No statistics available."
    
    # Sort by win rate (descending), then by average chips (descending)
    sorted_stats = sorted(
        stats_list,
        key=lambda s: (s.win_rate, s.avg_chips),
        reverse=True
    )
    
    # Calculate column widths
    max_name_len = max(len(s.bot_name) for s in sorted_stats) if sorted_stats else 10
    max_name_len = max(max_name_len, 8)  # At least "Bot Name"
    
    # Header
    header = (
        f"{'Rank':<5} | "
        f"{'Bot Name':<{max_name_len}} | "
        f"{'Wins':<5} | "
        f"{'Losses':<7} | "
        f"{'Win Rate':<9} | "
        f"{'Avg Chips':<10}"
    )
    
    separator = "-" * len(header)
    
    lines = [header, separator]
    
    # Rows
    for rank, stat in enumerate(sorted_stats, 1):
        win_rate_str = f"{stat.win_rate:.1f}%"
        avg_chips_str = f"{stat.avg_chips:.0f}"
        
        row = (
            f"{rank:<5} | "
            f"{stat.bot_name:<{max_name_len}} | "
            f"{stat.wins:<5} | "
            f"{stat.losses:<7} | "
            f"{win_rate_str:<9} | "
            f"{avg_chips_str:<10}"
        )
        lines.append(row)
    
    return "\n".join(lines)

def generate_h2h_summary(stats_list: List[BotStats], top_n: int = 5) -> str:
    """Generate head-to-head summary for top N bots."""
    if not stats_list:
        return ""
    
    # Sort and get top N
    sorted_stats = sorted(
        stats_list,
        key=lambda s: (s.win_rate, s.avg_chips),
        reverse=True
    )[:top_n]
    
    lines = ["\nHead-to-Head Records (Top 5):"]
    lines.append("=" * 60)
    
    for stat in sorted_stats:
        if not stat.h2h:
            continue
        
        lines.append(f"\n{stat.bot_name}:")
        # Sort opponents by total matches (wins + losses)
        opponents = sorted(
            stat.h2h.items(),
            key=lambda x: sum(x[1]),
            reverse=True
        )[:3]  # Show top 3 opponents
        
        for opponent, (wins, losses) in opponents:
            total = wins + losses
            win_pct = (wins / total * 100) if total > 0 else 0
            lines.append(f"  vs {opponent}: {wins}-{losses} ({win_pct:.1f}%)")
    
    return "\n".join(lines)

def export_to_json(stats_list: List[BotStats]) -> dict:
    """Export statistics to JSON-serializable format."""
    sorted_stats = sorted(
        stats_list,
        key=lambda s: (s.win_rate, s.avg_chips),
        reverse=True
    )
    
    return {
        "leaderboard": [
            {
                "rank": rank,
                "bot_name": stat.bot_name,
                "bot_path": stat.bot_path,
                "wins": stat.wins,
                "losses": stat.losses,
                "win_rate": stat.win_rate,
                "avg_chips": stat.avg_chips,
                "total_chips": stat.total_chips,
                "matches_played": stat.matches_played,
                "head_to_head": {
                    opponent: {"wins": wins, "losses": losses}
                    for opponent, (wins, losses) in stat.h2h.items()
                }
            }
            for rank, stat in enumerate(sorted_stats, 1)
        ]
    }

def export_to_csv(stats_list: List[BotStats], filename: str):
    """Export statistics to CSV file."""
    import csv
    
    sorted_stats = sorted(
        stats_list,
        key=lambda s: (s.win_rate, s.avg_chips),
        reverse=True
    )
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank", "Bot Name", "Bot Path", "Wins", "Losses", 
            "Win Rate", "Avg Chips", "Total Chips", "Matches Played"
        ])
        
        for rank, stat in enumerate(sorted_stats, 1):
            writer.writerow([
                rank,
                stat.bot_name,
                stat.bot_path,
                stat.wins,
                stat.losses,
                f"{stat.win_rate:.2f}",
                f"{stat.avg_chips:.2f}",
                stat.total_chips,
                stat.matches_played
            ])

def export_to_html(stats_list: List[BotStats], filename: str, tournament_info: dict = None):
    """Export a beautiful HTML report with charts and styling."""
    sorted_stats = sorted(
        stats_list,
        key=lambda s: (s.win_rate, s.avg_chips),
        reverse=True
    )
    
    # Prepare data for charts
    bot_names = [stat.bot_name for stat in sorted_stats]
    win_rates = [stat.win_rate for stat in sorted_stats]
    avg_chips = [stat.avg_chips for stat in sorted_stats]
    wins = [stat.wins for stat in sorted_stats]
    losses = [stat.losses for stat in sorted_stats]
    
    # Prepare H2H data
    h2h_data = {}
    for stat in sorted_stats:
        h2h_data[stat.bot_name] = {
            opponent: {"wins": w, "losses": l}
            for opponent, (w, l) in stat.h2h.items()
        }
    
    # Generate medal emojis
    def get_medal(rank):
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        return f"#{rank}"
    
    # Generate color based on rank
    def get_rank_color(rank, total):
        if rank == 1:
            return "#FFD700"  # Gold
        elif rank == 2:
            return "#C0C0C0"  # Silver
        elif rank == 3:
            return "#CD7F32"  # Bronze
        else:
            # Gradient from green to gray
            ratio = (rank - 1) / (total - 1) if total > 1 else 0
            r = int(100 + ratio * 155)
            g = int(200 - ratio * 100)
            b = int(100 + ratio * 155)
            return f"rgb({r}, {g}, {b})"
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poker Tournament Results</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        
        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .section {{
            margin-bottom: 50px;
        }}
        
        .section-title {{
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .leaderboard-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-radius: 10px;
            overflow: hidden;
        }}
        
        .leaderboard-table thead {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        .leaderboard-table th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
            font-size: 1.1em;
        }}
        
        .leaderboard-table td {{
            padding: 15px;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .leaderboard-table tbody tr {{
            transition: all 0.3s ease;
        }}
        
        .leaderboard-table tbody tr:hover {{
            background: #f5f5f5;
            transform: scale(1.01);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .rank-cell {{
            font-weight: bold;
            font-size: 1.2em;
            text-align: center;
        }}
        
        .win-rate {{
            font-weight: bold;
            font-size: 1.1em;
        }}
        
        .win-rate.high {{
            color: #4CAF50;
        }}
        
        .win-rate.medium {{
            color: #FF9800;
        }}
        
        .win-rate.low {{
            color: #F44336;
        }}
        
        .charts-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            margin: 30px 0;
        }}
        
        .chart-wrapper {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .chart-title {{
            font-size: 1.3em;
            margin-bottom: 15px;
            color: #667eea;
            text-align: center;
        }}
        
        .h2h-section {{
            margin-top: 40px;
        }}
        
        .h2h-card {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .h2h-card h3 {{
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.4em;
        }}
        
        .h2h-record {{
            display: flex;
            justify-content: space-between;
            padding: 10px;
            margin: 5px 0;
            background: white;
            border-radius: 5px;
            border-left: 4px solid #667eea;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        
        .stat-card .label {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .footer {{
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏆 Poker Tournament Results</h1>
            <div class="subtitle">
                Generated on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}
                {f" | {tournament_info.get('matches', 'N/A')} matches" if tournament_info else ""}
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2 class="section-title">📊 Tournament Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="label">Total Matches</div>
                        <div class="value">{sum(s.matches_played for s in sorted_stats) // len(sorted_stats) if sorted_stats else 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Total Bots</div>
                        <div class="value">{len(sorted_stats)}</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Best Win Rate</div>
                        <div class="value">{sorted_stats[0].win_rate:.1f}%</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Highest Avg Chips</div>
                        <div class="value">{int(sorted_stats[0].avg_chips):,}</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">🏅 Leaderboard</h2>
                <table class="leaderboard-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Bot Name</th>
                            <th>Wins</th>
                            <th>Losses</th>
                            <th>Win Rate</th>
                            <th>Avg Chips</th>
                            <th>Total Chips</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    for rank, stat in enumerate(sorted_stats, 1):
        medal = get_medal(rank)
        win_rate_class = "high" if stat.win_rate >= 30 else "medium" if stat.win_rate >= 20 else "low"
        
        html_content += f"""
                        <tr style="background: {get_rank_color(rank, len(sorted_stats))}20;">
                            <td class="rank-cell">{medal}</td>
                            <td><strong>{stat.bot_name}</strong></td>
                            <td>{stat.wins}</td>
                            <td>{stat.losses}</td>
                            <td class="win-rate {win_rate_class}">{stat.win_rate:.1f}%</td>
                            <td>{int(stat.avg_chips):,}</td>
                            <td>{stat.total_chips:,}</td>
                        </tr>
"""
    
    html_content += """
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2 class="section-title">📈 Visualizations</h2>
                <div class="charts-container">
                    <div class="chart-wrapper">
                        <div class="chart-title">Win Rate Comparison</div>
                        <canvas id="winRateChart"></canvas>
                    </div>
                    <div class="chart-wrapper">
                        <div class="chart-title">Average Chips Comparison</div>
                        <canvas id="chipsChart"></canvas>
                    </div>
                    <div class="chart-wrapper">
                        <div class="chart-title">Wins vs Losses</div>
                        <canvas id="winsLossesChart"></canvas>
                    </div>
                </div>
            </div>
"""
    
    # Add H2H section
    if any(stat.h2h for stat in sorted_stats[:5]):
        html_content += """
            <div class="section h2h-section">
                <h2 class="section-title">⚔️ Head-to-Head Records (Top 5)</h2>
"""
        for stat in sorted_stats[:5]:
            if stat.h2h:
                html_content += f"""
                <div class="h2h-card">
                    <h3>{stat.bot_name}</h3>
"""
                for opponent, (h2h_wins, h2h_losses) in sorted(stat.h2h.items(), key=lambda x: sum(x[1]), reverse=True)[:5]:
                    total = h2h_wins + h2h_losses
                    win_pct = (h2h_wins / total * 100) if total > 0 else 0
                    html_content += f"""
                    <div class="h2h-record">
                        <span><strong>vs {opponent}</strong></span>
                        <span>{h2h_wins}-{h2h_losses} ({win_pct:.1f}%)</span>
                    </div>
"""
                html_content += """
                </div>
"""
    
    # Add JavaScript for charts
    html_content += f"""
        </div>
        
        <div class="footer">
            <p>Generated by PokerLab Tournament System</p>
        </div>
    </div>
    
    <script>
        // Win Rate Chart
        const winRateCtx = document.getElementById('winRateChart').getContext('2d');
        new Chart(winRateCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(bot_names)},
                datasets: [{{
                    label: 'Win Rate (%)',
                    data: {json.dumps(win_rates)},
                    backgroundColor: [
                        '#FFD700',
                        '#C0C0C0',
                        '#CD7F32',
                        '#4CAF50',
                        '#2196F3',
                        '#FF9800',
                        '#9C27B0'
                    ].slice(0, {len(bot_names)}),
                    borderColor: '#667eea',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: false
                    }},
                    title: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        ticks: {{
                            callback: function(value) {{
                                return value + '%';
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Chips Chart
        const chipsCtx = document.getElementById('chipsChart').getContext('2d');
        new Chart(chipsCtx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(bot_names)},
                datasets: [{{
                    label: 'Average Chips',
                    data: {json.dumps(avg_chips)},
                    borderColor: '#764ba2',
                    backgroundColor: 'rgba(118, 75, 162, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{
                                return value.toLocaleString();
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Wins vs Losses Chart
        const winsLossesCtx = document.getElementById('winsLossesChart').getContext('2d');
        new Chart(winsLossesCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(bot_names)},
                datasets: [
                    {{
                        label: 'Wins',
                        data: {json.dumps(wins)},
                        backgroundColor: '#4CAF50',
                        borderColor: '#4CAF50',
                        borderWidth: 2
                    }},
                    {{
                        label: 'Losses',
                        data: {json.dumps(losses)},
                        backgroundColor: '#F44336',
                        borderColor: '#F44336',
                        borderWidth: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    x: {{
                        stacked: true
                    }},
                    y: {{
                        stacked: true,
                        beginAtZero: true
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)


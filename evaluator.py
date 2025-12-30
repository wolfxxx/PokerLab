# evaluator.py
from __future__ import annotations
from itertools import combinations
from typing import Iterable, List, Tuple

RANKS = {r: i for i, r in enumerate("..23456789TJQKA", start=0)}  # '2'->2 ... 'A'->14
INV_RANKS = {v: k for k, v in RANKS.items()}

def parse_card(c: str) -> Tuple[int, str]:
    # "Ah" -> (14, "h")
    if len(c) != 2:
        raise ValueError(f"Bad card: {c}")
    r, s = c[0], c[1]
    if r not in RANKS or s not in "cdhs":
        raise ValueError(f"Bad card: {c}")
    return (RANKS[r], s)

def _is_straight(ranks_desc: List[int]) -> int | None:
    """Return high card of straight, or None. ranks_desc are distinct and sorted desc."""
    if len(ranks_desc) < 5:
        return None
    # wheel A-5
    wheel = [14, 5, 4, 3, 2]
    if all(x in ranks_desc for x in wheel):
        return 5
    for i in range(len(ranks_desc) - 4):
        window = ranks_desc[i:i+5]
        if window[0] - window[4] == 4 and len(set(window)) == 5:
            return window[0]
    return None

def rank_5(cards5: List[Tuple[int, str]]) -> Tuple[int, List[int]]:
    """
    Returns (category, tiebreakers) where higher is better.
    category:
      8 straight flush
      7 four of a kind
      6 full house
      5 flush
      4 straight
      3 trips
      2 two pair
      1 one pair
      0 high card
    """
    ranks = sorted([r for r, _ in cards5], reverse=True)
    suits = [s for _, s in cards5]

    # counts
    counts = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    # sort by (count desc, rank desc)
    groups = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

    is_flush = len(set(suits)) == 1
    distinct_desc = sorted(set(ranks), reverse=True)
    straight_high = _is_straight(distinct_desc)

    if is_flush and straight_high is not None:
        return (8, [straight_high])

    if groups[0][1] == 4:
        quad = groups[0][0]
        kicker = max([r for r in ranks if r != quad])
        return (7, [quad, kicker])

    if groups[0][1] == 3 and groups[1][1] == 2:
        trips = groups[0][0]
        pair = groups[1][0]
        return (6, [trips, pair])

    if is_flush:
        return (5, sorted(ranks, reverse=True))

    if straight_high is not None:
        return (4, [straight_high])

    if groups[0][1] == 3:
        trips = groups[0][0]
        kickers = sorted([r for r in ranks if r != trips], reverse=True)
        return (3, [trips] + kickers)

    if groups[0][1] == 2 and groups[1][1] == 2:
        high_pair = max(groups[0][0], groups[1][0])
        low_pair = min(groups[0][0], groups[1][0])
        kicker = max([r for r in ranks if r != high_pair and r != low_pair])
        return (2, [high_pair, low_pair, kicker])

    if groups[0][1] == 2:
        pair = groups[0][0]
        kickers = sorted([r for r in ranks if r != pair], reverse=True)
        return (1, [pair] + kickers)

    return (0, sorted(ranks, reverse=True))

def best_of_7(card_strs: Iterable[str]) -> Tuple[int, List[int]]:
    cards = [parse_card(c) for c in card_strs]
    if len(cards) != 7:
        raise ValueError("best_of_7 expects exactly 7 cards")
    best = (-1, [])
    for combo in combinations(cards, 5):
        r = rank_5(list(combo))
        if r > best:
            best = r
    return best

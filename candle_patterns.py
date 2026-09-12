"""
Candlestick pattern detection — informational only, not wired into the
composite score (see the "why not score it yet" note in app.py where this
is called). Runs against the daily OHLC bars already sitting in
stock_agent._ohlcv_cache (populated every scan cycle for every ticker
anyway), so this adds zero network calls.

Deliberately hand-rolled rather than pulling in TA-Lib/pandas-ta:
- TA-Lib needs a system C library — risky to add to a Railway deploy that's
  currently pure-Python and has no such dependency today.
- pandas-ta is pure Python but still a new dependency for ~6 patterns that
  are each a few lines of arithmetic on OHLC values already in memory.

Only the two most recent daily bars are needed (single-candle patterns use
the last bar; the two two-candle patterns — engulfing — compare it to the
one before). Checked in priority order: a stronger/more specific pattern
(engulfing) wins over a weaker single-candle read (doji) when both would
technically match.
"""

import pandas as pd
from typing import Dict


def detect_candle_pattern(df: pd.DataFrame) -> Dict:
    """df: OHLC DataFrame (columns open/high/low/close, most recent last —
    matches market_data.py's fetch_ohlcv output). Returns a dict with the
    pattern name, its bullish/bearish/neutral classification, and the raw
    OHLC of the candle being described (so the UI can draw the real shape,
    not just a canned icon).

    Returns {'pattern': 'No Data', 'signal': 'neutral', ...zeros} if df is
    too short to evaluate — callers should treat that as "nothing to show",
    not as a real neutral reading.
    """
    empty = {"pattern": "No Data", "signal": "neutral",
             "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0}
    if df is None or len(df) < 1:
        return empty

    last = df.iloc[-1]
    o, h, l, c = float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"])
    if h <= l:  # degenerate bar (e.g. a single trade printed) — nothing to read
        return empty

    body = abs(c - o)
    rng = h - l
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    bullish_day = c > o

    result = {"open": o, "high": h, "low": l, "close": c}

    # Two-candle patterns first — they're a stronger, more specific read
    # than anything a single bar can tell you, so they take priority.
    if len(df) >= 2:
        prev = df.iloc[-2]
        po, pc = float(prev["open"]), float(prev["close"])
        prev_body = abs(pc - po)
        if prev_body > 0:
            # Bullish engulfing: prior candle red, this one green and its
            # body fully covers the prior candle's body.
            if pc < po and c > o and o <= pc and c >= po:
                return {**result, "pattern": "Bullish Engulfing", "signal": "bullish"}
            # Bearish engulfing: mirror image.
            if pc > po and c < o and o >= pc and c <= po:
                return {**result, "pattern": "Bearish Engulfing", "signal": "bearish"}

    # Single-candle patterns — body vs. range and wick-symmetry shape reads.
    if rng > 0:
        body_ratio = body / rng
        # Doji: open and close are essentially the same price — indecision,
        # not a directional read regardless of which way the day leaned.
        if body_ratio <= 0.1:
            return {**result, "pattern": "Doji", "signal": "neutral"}

        # Marubozu: a large body with almost no wicks either side — a
        # strong, conviction move in one direction with no real pushback.
        if body_ratio >= 0.9:
            return {**result, "pattern": "Bullish Marubozu" if bullish_day else "Bearish Marubozu",
                    "signal": "bullish" if bullish_day else "bearish"}

        # Hammer: small body sitting in the upper part of the range, a long
        # lower wick (sellers pushed it down, buyers dragged it back up),
        # little to no upper wick.
        if lower_wick >= 2 * body and upper_wick <= body * 0.5 and body_ratio <= 0.35:
            return {**result, "pattern": "Hammer", "signal": "bullish"}

        # Shooting Star: mirror of Hammer — long upper wick, small body low
        # in the range, little lower wick.
        if upper_wick >= 2 * body and lower_wick <= body * 0.5 and body_ratio <= 0.35:
            return {**result, "pattern": "Shooting Star", "signal": "bearish"}

    # No named pattern — still real information: which way the day closed.
    return {**result, "pattern": "Bullish Day" if bullish_day else "Bearish Day",
            "signal": "bullish" if bullish_day else "bearish"}

"""
Integrated FastAPI Application with MCP Stock Analysis Agent

Options + Stock Trading Recommendation System - v3.3.0
Provides API endpoints for analysis, portfolio, watchlist, and stock agent.

Endpoints:
- POST /api/v1/analyze - Analyze stock and get recommendations
- GET /api/v1/portfolio - Get portfolio positions
- POST /api/v1/watchlist - Add/remove from watchlist
- GET /api/v1/watchlist - Get watchlist
- WebSocket /ws/analyze/{symbol} - Real-time analysis stream

MCP Agent Endpoints:
- GET /api/v1/agent/status - Agent status
- POST /api/v1/agent/analyze - Analyze ticker with buy signal
- GET /api/v1/agent/watchlist - Get agent watchlist
- POST /api/v1/agent/watchlist/add - Add to agent watchlist
- GET /api/v1/agent/opportunities - Get buy opportunities
- POST /api/v1/agent/notify - Send notification
- GET /api/v1/agent/history - Get analysis history
- GET /api/v1/agent/performance - Get metrics
- WS /ws/agent/stream - Real-time agent stream

SP500 Options Endpoints:
- GET /api/v1/sp500/options-recommendations - Top options recs (ticker, CALL/PUT, strike, expiry, score)
- WS /ws/sp500/options - Real-time push of options recommendations every 20 min
"""

import logging
import os
import math
import hashlib
import random
import re
import yfinance as yf
from fastapi import FastAPI, HTTPException, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from zoneinfo import ZoneInfo

# Import analyzers
from analyzer.news_analyzer import NewsAnalyzer
from analyzer.technical_analyzer import TechnicalAnalyzer
from analyzer.options_analyzer import OptionsAnalyzer
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.strategy_selector import StrategySelector
from analyzer.call_put_predictor import CallPutPredictor
from analyzer.reasoning_generator import ReasoningGenerator

# Import agent and notifications
from mcp_stock_agent import MCPStockAgent, BuySignal, ConfidenceLevel
from notification_manager import NotificationManager
import dynamic_tickers

logger = logging.getLogger(__name__)

# Alpaca credentials — used for options/market data (contracts, quotes,
# snapshots), loaded from alpaca.env file (or env vars as fallback). No
# trading happens against these; this backend never executes real or
# simulated trades.
def _load_alpaca_keys() -> tuple:
    """Read ALPACA_API_KEY and ALPACA_API_SECRET from alpaca.env, then env vars."""
    env_file = os.path.join(os.path.dirname(__file__), "alpaca.env")
    if os.path.exists(env_file):
        from dotenv import dotenv_values
        cfg = dotenv_values(env_file)
        key    = cfg.get("ALPACA_API_KEY", "").strip()
        secret = cfg.get("ALPACA_API_SECRET", "").strip()
        if key and key != "your-key-id-here":
            logger.info("Alpaca credentials loaded from alpaca.env")
            return key, secret
    # Fall back to shell environment variables
    return os.environ.get("ALPACA_API_KEY", ""), os.environ.get("ALPACA_API_SECRET", "")

_ALPACA_KEY, _ALPACA_SECRET = _load_alpaca_keys()

_ET = ZoneInfo("America/New_York")

def _is_market_open() -> bool:
    """Return True only during optimal options trading window (10:00–15:30 ET, Mon–Fri).
    Avoids the open (wide spreads, gap volatility) and close (accelerated time decay)."""
    now_et = datetime.now(_ET)
    if now_et.weekday() >= 5:          # Saturday=5, Sunday=6
        return False
    market_open  = now_et.replace(hour=10, minute=0,  second=0, microsecond=0)
    market_close = now_et.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now_et < market_close


# ============================================================================
# OPTIONS RECOMMENDATION DATA MODEL
# ============================================================================

@dataclass
class OptionsRecommendation:
    """Options recommendation with full options details"""
    ticker: str
    action: str          # "CALL" or "PUT"
    strike_price: float
    expiry_date: str     # "YYYY-MM-DD"
    score: float         # 0.0 - 1.0
    confidence: str      # "VERY_HIGH", "HIGH", "MODERATE", "LOW"
    current_price: float
    buy_signal: str
    technical_score: float
    sentiment_score: float
    ml_score: float
    timestamp: str
    thesis: str = ""
    days_to_expiry: int = 30
    iv_rank: float = 50.0
    volume_ratio: float = 1.0
    rs_vs_spy: float = 0.0
    days_to_earnings: int = 999
    analyst_upside: float = 0.0
    long_term_score: float = 0.0  # weeks-to-months stock ranking — see _compute_long_term_score
    news_headlines: list = None  # display-only, not used in scoring
    fundamentals: dict = None    # balance sheet, cash flow, income — top 20 only
    catalyst_age_days: int = -1        # days since the most recent headline; -1 = no news found
    price_change_since_catalyst: float = 0.0  # % move since that headline — see _compute_catalyst_freshness
    intraday_move_pct: float = 0.0     # % faded off today's high (CALL) or bounced off today's low (PUT)
    key_factors: list = None  # see _generate_key_factors_and_risks — same real signals that drive `score`
    risks: list = None
    day_change_pct: float = 0.0        # today's overall % move vs prior close — regardless of
                                        # direction/reversal, unlike intraday_move_pct above
    avg_dollar_volume: float = 0.0     # 20d avg shares x price — absolute liquidity/"how fast
                                        # does this normally move" measure, not self-relative
                                        # like volume_ratio
    # Candlestick read on the most recent completed 1-hour bar — see
    # _detect_candle_pattern. Hourly (not daily) because that's the
    # timeframe people actually mean by "the last candle" for a short-term
    # bullish/bearish read — a daily bar can't tell you what's about to
    # happen in the next hour, only what already happened today. Purely
    # informational, NOT a scoring input (adding it into the composite
    # score would mean re-weighting and re-validating the already-
    # calibrated 0.55/0.65/0.70/0.80 confidence thresholds).
    candle_pattern: str = "No Data"
    candle_signal: str = "neutral"     # "bullish" | "bearish" | "neutral" — drives the UI's color
    candle_open: float = 0.0
    candle_high: float = 0.0
    candle_low: float = 0.0
    candle_close: float = 0.0
    # Multi-day version of the existing same-day reversal penalty below —
    # see _detect_fade_streak. fade_streak_days of the last fade_streak_total
    # sessions gave back >=2% from the day's own high (CALL) or low (PUT)
    # by the close. Unlike the same-day check, THIS is a real scoring input
    # (a small, capped penalty) since a repeat pattern across days is a
    # stronger signal than one day's own intraday wiggle.
    fade_streak_days: int = 0
    fade_streak_total: int = 0
    # Analysts covering this ticker — < 3 means fundamental_score (and the
    # "Fundamentals" component below) is a neutral default, not a real
    # read. See mcp_stock_agent.py's _fetch_real_fundamental_data.
    analyst_count: int = 0
    # The REAL composite-score math, exposed so the UI never has to (and
    # never again silently drifts from) reconstruct it client-side — see
    # _make_options_rec's "Expert composite score" block for where this is
    # built. Shape: {"components": [{"label", "weight", "value", "contribution"}],
    # "adjustments": [{"label", "amount"}], "final_score": float}. adjustments
    # only lists ones that actually applied (same-day reversal / fade streak).
    # sum(contributions) + sum(adjustment amounts) == final_score == this
    # rec's own `score`/`long_term_score`, always, by construction.
    score_breakdown: dict = None
    long_term_score_breakdown: dict = None
    # When this exact (ticker, action) signal was first surfaced, and what
    # price it was at then — from scan_history via _fetch_signal_first_seen.
    # signal_state is the Fresh/Active/Extended/Faded/Invalidated read
    # derived from age + price_change_since_signal_pct — see
    # _make_options_rec's "Signal freshness" block for the real thresholds.
    signal_detected_at: str = ""
    price_at_signal: float = 0.0
    price_change_since_signal_pct: float = 0.0
    signal_state: str = "Fresh"

    def __post_init__(self):
        if self.news_headlines is None:
            self.news_headlines = []
        if self.fundamentals is None:
            self.fundamentals = {}
        if self.key_factors is None:
            self.key_factors = []
        if self.risks is None:
            self.risks = []
        if self.score_breakdown is None:
            self.score_breakdown = {}
        if self.long_term_score_breakdown is None:
            self.long_term_score_breakdown = {}


def _next_monthly_expiry(from_date: datetime = None) -> str:
    """Return the 3rd Friday of next month as options expiry date."""
    if from_date is None:
        from_date = datetime.utcnow()
    # Move to next month
    if from_date.month == 12:
        year, month = from_date.year + 1, 1
    else:
        year, month = from_date.year, from_date.month + 1
    # Find 3rd Friday
    first_day = date(year, month, 1)
    # weekday(): Monday=0 ... Friday=4 ... Sunday=6
    days_to_friday = (4 - first_day.weekday()) % 7
    third_friday = first_day + timedelta(days=days_to_friday + 14)
    return third_friday.strftime("%Y-%m-%d")


def _is_price_plausible(price: float, today_low: Optional[float], today_high: Optional[float]) -> bool:
    """A live price must fall within its own day's high/low (small buffer
    for bid/ask spread and rounding) — extracted as its own testable
    function after a real bug: MSTR showed $115.74 in one scan while its
    real intraday range that day was $119.38-$127.90, a stale/mismatched
    fetch (yfinance falling back to a prior session) that the prev-close
    gap check didn't catch because $115.74 wasn't an implausible jump from
    the prior close, just wrong. Returns True (plausible) whenever
    today_low/today_high aren't both available — this check only rejects
    a price when it has real data to check it against."""
    if not today_low or not today_high or today_low <= 0 or today_high <= 0:
        return True
    return today_low * 0.97 <= price <= today_high * 1.03


def _strike_for_action(price: float, action: str) -> float:
    """Round to nearest $5 strike, slight OTM for call or put."""
    rounded = round(price / 5) * 5
    if action == "CALL":
        # Slightly OTM call: next $5 above ATM
        return rounded + 5 if price > rounded else rounded
    else:
        # Slightly OTM put: next $5 below ATM
        return rounded - 5 if price < rounded else rounded


def _interpret_composite_score(score: float) -> Tuple[str, str]:
    """Map the composite ranking score (technical/RS/IV-rank/volume/fundamentals,
    see _make_options_rec) to (confidence, buy_signal) — so the label shown next
    to a ticker always agrees with where it ranks.

    Thresholds are calibrated to *this* score's own range, not borrowed from
    mcp_stock_agent.py's separate sentiment/ML-weighted score (which runs
    higher and would otherwise collapse everything here into one bucket —
    this formula has topped out around 0.74 in practice)."""
    if score >= 0.80:
        return "VERY_HIGH", "STRONG_BUY"
    elif score >= 0.70:
        return "HIGH", "BUY"
    elif score >= 0.65:
        return "MODERATE", "ACCUMULATE"
    elif score >= 0.55:
        return "LOW", "HOLD"
    else:
        return "VERY_LOW", "AVOID"


MIN_OPEN_INTEREST = 500  # below this, contracts are too thin to trade reliably (wide spreads, bad fills).
# Lowered from 1000 after measuring the real tradeoff directly: 1000 was
# cutting 80% of the top-100 score-qualified candidates (100 -> 20 final),
# while 969 tickers were clearing the score bar in the same scan -- the
# bottleneck was liquidity, not scoring. 500 nearly doubles the final list
# (20 -> 34 in that same test) while still screening out the truly thin/
# dead contracts (OI 0-499) where fill risk concentrates most.

_liquidity_client = None  # lazy, cached Alpaca TradingClient — used only for
                           # options-contract/liquidity lookups, not trading


def _get_liquidity_client():
    global _liquidity_client
    if _liquidity_client is None and _ALPACA_KEY and _ALPACA_SECRET:
        try:
            from alpaca.trading.client import TradingClient
            _liquidity_client = TradingClient(_ALPACA_KEY, _ALPACA_SECRET, paper=True)
        except Exception as e:
            logger.warning(f"[Liquidity] Could not init Alpaca client: {e}")
    return _liquidity_client


def _check_open_interest(ticker: str, strike: float, expiry: str, action: str) -> Optional[int]:
    """Look up real open interest for this exact contract via Alpaca.
    Returns None (not 0) on any lookup failure, so callers can tell
    'genuinely thin' apart from 'couldn't check' and fail open rather
    than silently dropping every rec when Alpaca is unavailable."""
    client = _get_liquidity_client()
    if client is None:
        return None
    try:
        from alpaca.trading.requests import GetOptionContractsRequest
        from alpaca.trading.enums import ContractType
        req = GetOptionContractsRequest(
            underlying_symbols=[ticker],
            expiration_date_gte=datetime.strptime(expiry, "%Y-%m-%d").date(),
            expiration_date_lte=datetime.strptime(expiry, "%Y-%m-%d").date(),
            type=ContractType.CALL if action == "CALL" else ContractType.PUT,
            strike_price_gte=str(strike), strike_price_lte=str(strike),
        )
        resp = client.get_option_contracts(req)
        contracts = resp.option_contracts if hasattr(resp, 'option_contracts') else list(resp)
        if not contracts:
            return 0
        return int(contracts[0].open_interest or 0)
    except Exception as e:
        logger.debug(f"[Liquidity] {ticker} OI check failed: {e}")
        return None


COVERED_CALL_DEFAULT_BUDGET = 5000.0  # 100 shares must fit in this to be a candidate

_option_quote_client = None  # lazy, cached — separate client, options quotes need
                              # OptionHistoricalDataClient, not the trading client above


def _get_option_quote_client():
    global _option_quote_client
    if _option_quote_client is None and _ALPACA_KEY and _ALPACA_SECRET:
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            _option_quote_client = OptionHistoricalDataClient(_ALPACA_KEY, _ALPACA_SECRET)
        except Exception as e:
            logger.warning(f"[CoveredCall] Could not init option quote client: {e}")
    return _option_quote_client


def _find_covered_call_candidates(budget: float = COVERED_CALL_DEFAULT_BUDGET) -> List[Dict]:
    """From the latest scored CALL recs, find ones where 100 shares fits the
    budget, then find a real liquid slightly-OTM call to sell against them —
    analysis only, this does not place any order. Strike target mirrors the
    pattern seen in real covered-call trades: ~3-10% above current price."""
    candidates: List[Dict] = []
    trading_client = _get_liquidity_client()
    quote_client = _get_option_quote_client()
    if trading_client is None or quote_client is None:
        return candidates

    eligible = [r for r in latest_options_recs
                if r.action == "CALL" and r.current_price > 0 and r.current_price * 100 <= budget]

    for rec in eligible:
        try:
            from alpaca.trading.requests import GetOptionContractsRequest
            from alpaca.trading.enums import ContractType
            from alpaca.data.requests import OptionLatestQuoteRequest

            price = rec.current_price
            expiry = _next_monthly_expiry()
            req = GetOptionContractsRequest(
                underlying_symbols=[rec.ticker],
                expiration_date_gte=datetime.strptime(expiry, "%Y-%m-%d").date(),
                expiration_date_lte=datetime.strptime(expiry, "%Y-%m-%d").date(),
                type=ContractType.CALL,
                strike_price_gte=str(round(price * 1.03, 2)),
                strike_price_lte=str(round(price * 1.10, 2)),
            )
            resp = trading_client.get_option_contracts(req)
            contracts = resp.option_contracts if hasattr(resp, 'option_contracts') else list(resp)
            liquid = [c for c in contracts if c.open_interest and int(c.open_interest) >= MIN_OPEN_INTEREST]
            if not liquid:
                continue

            target = price * 1.05
            contract = min(liquid, key=lambda c: abs(float(c.strike_price) - target))

            quote = quote_client.get_option_latest_quote(
                OptionLatestQuoteRequest(symbol_or_symbols=contract.symbol)
            ).get(contract.symbol)
            if not quote:
                continue
            bid = float(quote.bid_price or 0)
            ask = float(quote.ask_price or 0)
            if bid <= 0:
                continue
            premium = (bid + ask) / 2 if ask > 0 else bid

            shares_cost = round(price * 100, 2)
            premium_total = round(premium * 100, 2)
            strike = float(contract.strike_price)

            candidates.append({
                "ticker": rec.ticker,
                "score": rec.score,
                "buy_signal": rec.buy_signal,
                "current_price": round(price, 2),
                "shares_cost": shares_cost,
                "strike": strike,
                "expiry_date": expiry,
                "premium_per_share": round(premium, 2),
                "premium_total": premium_total,
                "yield_pct": round(premium_total / shares_cost * 100, 2),
                "breakeven": round(price - premium, 2),
                "max_profit_if_called": round((strike - price) * 100 + premium_total, 2),
                "open_interest": int(contract.open_interest or 0),
            })
        except Exception as e:
            logger.debug(f"[CoveredCall] {rec.ticker} skipped: {e}")
            continue

    candidates.sort(key=lambda c: -c["yield_pct"])
    return candidates


def _compute_long_term_score(tech: float, rs_score: float, fund: float, analyst_upside: float, is_bearish: bool) -> float:
    """Weeks-to-months stock ranking — deliberately different weighting from
    the options composite score above. Fundamentals and analyst upside carry
    most of the weight here since they matter for holding a stock over weeks/
    months; IV rank is excluded entirely (it's an options-pricing signal,
    meaningless for a long-term stock decision) and short-term volume isn't
    used either (noise at this horizon, not signal)."""
    upside_score = min(1.0, max(0.0, analyst_upside / 30.0))  # +30% target -> 1.0
    if is_bearish:
        raw = ((1.0 - fund)         * 0.40 +
               (1.0 - upside_score) * 0.25 +
               (1.0 - tech)         * 0.25 +
               (1.0 - rs_score)     * 0.10)
    else:
        raw = (fund         * 0.40 +
               upside_score * 0.25 +
               tech         * 0.25 +
               rs_score     * 0.10)
    return round(min(1.0, max(0.0, raw)), 4)


def _generate_thesis(ticker: str, action: str, score: float, confidence: str,
                      tech: float, rs: float, iv_rank: float, vol_ratio: float,
                      intraday_move_pct: float, price: float, strike: float,
                      days_to_earnings: int, rsi: float = 50.0,
                      market_score: float = 0.5) -> str:
    """Build a plain-language, multi-paragraph explanation from the SAME real
    signals that drive `score` above — not just a stat summary, but something
    a non-expert can actually read and act on: what's happening, why, what
    to watch for, and a forward-looking "if this / then that" scenario.
    Previously this came from mcp_stock_agent's own separate
    strategy_selector/reasoning_generator path, which leaned on the broad
    market regime rather than this ticker's actual numbers and could (and
    did) produce bullish-sounding text attached to an AVOID/PUT verdict —
    every sentence here traces back to a number already on screen."""
    bullish = action == "CALL"
    strength = {
        "VERY_HIGH": "a high-conviction", "HIGH": "a solid", "MODERATE": "a moderate",
        "LOW": "a weak", "VERY_LOW": "a very weak",
    }.get(confidence, "a mixed")
    paragraphs: List[str] = []

    # ── Opening: what's happening, in plain terms ──────────────────────────
    if bullish:
        if tech >= 0.55 and rs >= 1.0:
            opener = (f"{ticker} has been trending higher and is showing more strength than the "
                      f"broader market right now — that combination is what's driving {strength} "
                      f"bullish read ({score:.0%}).")
        elif tech >= 0.55:
            opener = (f"{ticker} has been trending higher recently, which is the main thing behind "
                      f"{strength} bullish read ({score:.0%}).")
        else:
            opener = (f"The overall read on {ticker} leans bullish ({score:.0%}), but that's {strength} "
                      f"call — the recent price action itself hasn't been especially strong, so this "
                      f"rests more on the other factors below than on clear momentum.")
    else:
        if tech <= 0.45 and rs <= -1.0:
            opener = (f"{ticker} has been trending lower and underperforming the broader market — "
                      f"that combination is what's driving {strength} bearish read ({score:.0%}).")
        elif tech <= 0.45:
            opener = (f"{ticker} has been trending lower recently, which is the main thing behind "
                      f"{strength} bearish read ({score:.0%}).")
        else:
            opener = (f"The overall read on {ticker} leans bearish ({score:.0%}), but that's {strength} "
                      f"call — the price action itself hasn't clearly broken down yet, so this is more "
                      f"about warning signs below than an obvious downtrend.")
    paragraphs.append(opener)

    # ── Supporting detail: RS, volume, IV — in plain language ──────────────
    detail: List[str] = []
    if abs(rs) >= 1.0:
        rel = "outperforming" if rs > 0 else "underperforming"
        detail.append(
            f"Over the recent trading days it's been {rel} the S&P 500 by about {abs(rs):.1f}% — "
            f"stocks that move independently of the broader market are usually reacting to something "
            f"specific to the company, not just riding the overall market up or down."
        )
    if vol_ratio >= 1.5:
        detail.append(
            f"Trading volume has also picked up, running about {vol_ratio:.1f}x the normal daily "
            f"average — that usually means real money is behind this move, not just noise."
        )
    elif vol_ratio <= 0.6:
        detail.append(
            f"One thing to watch: volume has actually been below average ({vol_ratio:.1f}x normal), "
            f"so this move hasn't attracted much real conviction yet — it could fade as easily as it started."
        )
    if iv_rank <= 30:
        detail.append(
            f"Options themselves are relatively cheap right now (IV rank {iv_rank:.0f}/100), which "
            f"works in your favor — you're not paying a big premium for the market's fear or excitement."
        )
    elif iv_rank >= 70:
        detail.append(
            f"Options are expensive right now (IV rank {iv_rank:.0f}/100) — you're paying up for this "
            f"trade, which means {ticker} needs to move further just to break even, let alone profit."
        )
    if detail:
        paragraphs.append(" ".join(detail))

    # ── Where this sits in its move — fresh vs already-stretched, using RSI.
    # This is the piece that answers "is this the start of a run or has it
    # already run" — RSI was already being computed for scoring and quietly
    # discarded before this; it's the standard way to measure that without
    # guessing, and it cuts both ways (stretched can still keep going,
    # oversold can still keep falling), which the text says explicitly.
    if bullish:
        if rsi >= 70:
            paragraphs.append(
                f"Where this sits in its move matters too: {ticker}'s RSI is at {rsi:.0f}, which is "
                f"technically \"overbought\" — it's already climbed enough to be considered stretched, "
                f"not just getting started. That doesn't mean it has to stop here, but stretched moves "
                f"are more prone to at least pausing or pulling back to cool off, on top of anything "
                f"else going on. If it does keep running from here, it's an extension of an existing "
                f"move rather than a fresh breakout."
            )
        elif rsi <= 40:
            paragraphs.append(
                f"Where this sits in its move: {ticker}'s RSI is at {rsi:.0f}, still on the low side, "
                f"which means this bullish read is catching it early rather than chasing something "
                f"that's already run hard — closer to the start of a potential move than the middle or "
                f"end of one, if the thesis plays out. The flip side of \"hasn't moved much yet\" is "
                f"that the case is less proven so far."
            )
        else:
            paragraphs.append(
                f"Where this sits in its move: {ticker}'s RSI is a middling {rsi:.0f} — not stretched, "
                f"not fresh off the bottom either. There's room for this to continue without being "
                f"flagged as overheated, but it's also not an obvious early-stage setup."
            )
    else:
        if rsi <= 30:
            paragraphs.append(
                f"Where this sits in its move matters too: {ticker}'s RSI is at {rsi:.0f}, technically "
                f"\"oversold\" — it's already fallen enough that a bounce becomes more likely on its "
                f"own, purely on a mean-reversion basis. That's a real risk to this bearish case: "
                f"oversold doesn't mean safe from further declines, but a lot of the drop may already "
                f"be behind it rather than still ahead."
            )
        elif rsi >= 60:
            paragraphs.append(
                f"Where this sits in its move: {ticker}'s RSI is at {rsi:.0f}, still on the elevated "
                f"side, meaning this bearish case is more about a pullback from an extended level than "
                f"a stock that's already broken down — closer to the start of a potential reversal than "
                f"something that's already fallen a long way."
            )
        else:
            paragraphs.append(
                f"Where this sits in its move: {ticker}'s RSI is a middling {rsi:.0f} — not stretched "
                f"to the upside, not oversold either. There's room for this to keep sliding without "
                f"being flagged as already-overdone, but it's also not a screaming oversold bounce risk."
            )

    # ── Broader market context — a risk this setup can't fully protect against ─
    if market_score >= 0.65:
        paragraphs.append(
            f"Worth noting: the broader market itself is in a supportive stretch right now, which "
            f"tends to lift most stocks together — that's a tailwind for this trade beyond {ticker}'s "
            f"own numbers. If that changes and the overall market turns down, this setup would be "
            f"fighting the tide instead of riding it."
        )
    elif market_score <= 0.4:
        paragraphs.append(
            f"One real risk sitting outside everything above: the broader market itself looks shaky "
            f"right now. Even a stock with genuinely strong individual signals can get pulled down if "
            f"the overall market turns lower — that's a risk {ticker}'s own numbers can't fully protect against."
        )
    else:
        paragraphs.append(
            f"The broader market itself is roughly neutral right now — not a strong tailwind, not a "
            f"headwind either, so this trade is mostly standing on {ticker}'s own numbers rather than "
            f"being carried or dragged by the overall market."
        )

    # ── Near-term wrinkle: same-day reversal ────────────────────────────────
    if bullish and intraday_move_pct <= -1.5:
        paragraphs.append(
            f"There's a near-term wrinkle, though: {ticker} has already pulled back "
            f"{abs(intraday_move_pct):.1f}% from its high today. Buying right now means buying after "
            f"the strongest part of today's move already happened, not before it."
        )
    elif not bullish and intraday_move_pct >= 1.5:
        paragraphs.append(
            f"There's a near-term wrinkle, though: {ticker} has already bounced "
            f"{intraday_move_pct:.1f}% off its low today. Betting on further downside right now means "
            f"betting that bounce fails, not that the drop is still fresh."
        )

    # ── Earnings risk ────────────────────────────────────────────────────────
    if days_to_earnings is not None and 0 <= days_to_earnings <= 10:
        paragraphs.append(
            f"Also worth knowing: {ticker} reports earnings in {days_to_earnings} day(s). That's a "
            f"real wildcard — a single earnings report can move a stock more in one day than weeks of "
            f"normal trading, in either direction, regardless of everything above."
        )

    # ── Both directions, explicitly, each with real reasons ─────────────────
    # Not just a primary call with a brief caveat — a genuine "it could go
    # this way because X, or that way because Y," built from whichever of
    # this ticker's own real signals actually support each side.
    dist_pct = abs(strike - price) / price * 100 if price > 0 else 0.0
    if bullish:
        up_reasons = []
        if rs >= 1.0:
            up_reasons.append(f"it's already outperforming the market by {rs:.1f}%")
        if vol_ratio >= 1.3:
            up_reasons.append(f"volume ({vol_ratio:.1f}x average) is confirming real interest, not just drift")
        if rsi < 65:
            up_reasons.append("it isn't technically overbought yet, so there's room before this measure would call it stretched")
        if not up_reasons:
            up_reasons.append("the composite score leans this way even without one single dominant factor")

        down_reasons = []
        if rsi >= 65:
            down_reasons.append(f"RSI at {rsi:.0f} means it's already stretched, which is exactly the kind of setup that tends to pause or pull back")
        if intraday_move_pct <= -1.5:
            down_reasons.append(f"it's already faded {abs(intraday_move_pct):.1f}% off today's high, showing some hesitation right now")
        if vol_ratio < 0.8:
            down_reasons.append("volume is on the light side, so the move so far hasn't attracted much real conviction")
        if market_score <= 0.4:
            down_reasons.append("the broader market itself is shaky, which drags on individual stocks regardless of their own setup")
        if not down_reasons:
            down_reasons.append("no single stock's setup is bulletproof — a broader market wobble or fresh negative news could turn this regardless of what's driving it today")

        paragraphs.append(
            f"Put together: {ticker} could keep climbing toward the ${strike:.0f} level "
            f"(about {dist_pct:.1f}% above the current ${price:.2f}) because " + ", and ".join(up_reasons) +
            f". On the other hand, it could turn lower instead because " + ", and ".join(down_reasons) +
            f" — in that case, slipping back below where it opened today would usually be the first real "
            f"sign this setup is losing steam. Both are live possibilities; this isn't a forecast of "
            f"which one happens, just what the current numbers support on each side."
        )
    else:
        down_reasons = []
        if rs <= -1.0:
            down_reasons.append(f"it's already underperforming the market by {abs(rs):.1f}%")
        if vol_ratio >= 1.3:
            down_reasons.append(f"volume ({vol_ratio:.1f}x average) is confirming real selling, not just drift")
        if rsi > 35:
            down_reasons.append("it isn't technically oversold yet, so there's room before this measure would call the drop overdone")
        if not down_reasons:
            down_reasons.append("the composite score leans this way even without one single dominant factor")

        up_reasons = []
        if rsi <= 35:
            up_reasons.append(f"RSI at {rsi:.0f} means it's already oversold, which is exactly the kind of setup that tends to bounce")
        if intraday_move_pct >= 1.5:
            up_reasons.append(f"it's already bounced {intraday_move_pct:.1f}% off today's low, showing some support right now")
        if vol_ratio < 0.8:
            up_reasons.append("volume is on the light side, so the drop so far hasn't attracted much real conviction")
        if market_score >= 0.65:
            up_reasons.append("the broader market itself is supportive right now, which tends to lift individual stocks regardless of their own setup")
        if not up_reasons:
            up_reasons.append("no breakdown is guaranteed to continue — a broader market rally or fresh positive news could reverse this regardless of what's driving it today")

        paragraphs.append(
            f"Put together: {ticker} could keep sliding toward the ${strike:.0f} level "
            f"(about {dist_pct:.1f}% below the current ${price:.2f}) because " + ", and ".join(down_reasons) +
            f". On the other hand, it could stabilize or bounce instead because " + ", and ".join(up_reasons) +
            f" — in that case, climbing back above where it opened today would usually be the first real "
            f"sign this breakdown isn't following through. Both are live possibilities; this isn't a "
            f"forecast of which one happens, just what the current numbers support on each side."
        )

    return " ".join(paragraphs)


def _append_catalyst_narrative(thesis: str, ticker: str, catalyst_age_days: int,
                                price_change_since_catalyst: float) -> str:
    """Append a plain-language paragraph about news timing to an already-built
    thesis. Separate from _generate_thesis because catalyst_age_days/
    price_change_since_catalyst require an expensive news+historical-price
    lookup (_compute_catalyst_freshness) only run for the top-ranked
    candidates, not the full scanned pool — see call sites."""
    if catalyst_age_days is None or catalyst_age_days < 0:
        return thesis
    if catalyst_age_days == 0:
        addition = (
            f"There's also fresh news out on {ticker} today driving some of this — the market is "
            f"still digesting it, so the next day or two is usually when most of any further reaction happens."
        )
    elif catalyst_age_days == 1:
        addition = (
            f"The news behind this surfaced yesterday, so there may still be a little more room for "
            f"the market to react, but the bulk of the initial move has likely already happened."
        )
    elif catalyst_age_days >= 5:
        addition = (
            f"Worth flagging: the news driving this is already {catalyst_age_days} days old, and "
            f"{ticker} has moved {price_change_since_catalyst:+.1f}% since then — a lot of that story "
            f"may already be priced in. A trade here is more a bet the move continues than a bet on "
            f"genuinely new information."
        )
    else:
        return thesis
    return thesis + " " + addition


def _generate_key_factors_and_risks(rec: OptionsRecommendation) -> Tuple[List[str], List[str]]:
    """Key factors / risks for the single-ticker analyze endpoint, built from
    the same real signals that already drove `rec.score` — replaces the old
    mcp_stock_agent narrative (strategy_selector/reasoning_generator), which
    was decoupled from this score and could contradict the actual verdict."""
    bullish = rec.action == "CALL"
    factors: List[str] = []
    risks: List[str] = []

    if bullish:
        if rec.technical_score >= 0.55:
            factors.append(f"Technical score of {rec.technical_score:.0%} supports the bullish case.")
        else:
            risks.append(f"Technical score is only {rec.technical_score:.0%} — not strongly confirming.")
        if rec.rs_vs_spy >= 1.0:
            factors.append(f"Outperforming SPY by {rec.rs_vs_spy:.1f}% over the lookback window.")
        elif rec.rs_vs_spy <= -1.0:
            risks.append(f"Underperforming SPY by {abs(rec.rs_vs_spy):.1f}% despite the bullish lean.")
    else:
        if rec.technical_score <= 0.45:
            factors.append(f"Technical score of {rec.technical_score:.0%} confirms the bearish case.")
        else:
            risks.append(f"Technical score is {rec.technical_score:.0%} — not deeply bearish yet.")
        if rec.rs_vs_spy <= -1.0:
            factors.append(f"Underperforming SPY by {abs(rec.rs_vs_spy):.1f}%.")
        elif rec.rs_vs_spy >= 1.0:
            risks.append(f"Outperforming SPY by {rec.rs_vs_spy:.1f}% despite the bearish lean.")

    if rec.iv_rank <= 30:
        factors.append(f"IV rank {rec.iv_rank:.0f} — options are relatively cheap to buy.")
    elif rec.iv_rank >= 70:
        risks.append(f"IV rank {rec.iv_rank:.0f} — options are expensive, eating into edge.")

    if rec.volume_ratio >= 1.5:
        factors.append(f"Volume running {rec.volume_ratio:.1f}x average — real interest behind the move.")
    elif rec.volume_ratio <= 0.5:
        risks.append("Volume is thin — low conviction behind the move.")

    if rec.analyst_upside >= 5:
        factors.append(f"Analysts see {rec.analyst_upside:.1f}% upside to target price.")
    elif rec.analyst_upside <= -5:
        risks.append(f"Analysts see {rec.analyst_upside:.1f}% downside to target price.")

    if bullish and rec.intraday_move_pct <= -1.5:
        risks.append(f"Already faded {abs(rec.intraday_move_pct):.1f}% off today's high — chasing a move that may be reversing.")
    elif not bullish and rec.intraday_move_pct >= 1.5:
        risks.append(f"Already bounced {rec.intraday_move_pct:.1f}% off today's low — chasing a move that may be reversing.")

    if rec.catalyst_age_days is not None and rec.catalyst_age_days >= 0:
        if rec.catalyst_age_days <= 1:
            factors.append("Catalyst is fresh — most recent headline is from today or yesterday.")
        elif rec.catalyst_age_days >= 5:
            risks.append(
                f"Catalyst is {rec.catalyst_age_days} days old — the move may already be "
                f"priced in ({rec.price_change_since_catalyst:+.1f}% since then)."
            )

    if 0 <= rec.days_to_earnings <= 5:
        risks.append(f"Earnings in {rec.days_to_earnings} day(s) — expect elevated volatility.")

    if not factors:
        factors.append("No single factor stands out — this is a low-conviction, borderline signal.")
    if not risks:
        risks.append("No major red flags identified in the scanned signals.")

    return factors, risks


# Candlestick pattern detection — informational only, not wired into the
# composite score. Runs against 1-hour OHLC bars — hourly, not the daily
# bars already cached for technical scoring, because "the last candle" for
# a short-term bullish/bearish read is an intraday concept; a daily bar
# only tells you what already happened today; see _prefetch_hourly_ohlcv
# for the batched fetch this reads from (one call per scan, not per ticker).
#
# Deliberately hand-rolled rather than pulling in TA-Lib/pandas-ta:
# - TA-Lib needs a system C library — risky to add to a Railway deploy
#   that's currently pure-Python and has no such dependency today.
# - pandas-ta is pure Python but still a new dependency for ~6 patterns
#   that are each a few lines of arithmetic on OHLC values already in memory.
#
# Deliberately inlined here rather than in its own module — a separate
# candle_patterns.py file was tried first and reproducibly caused every
# recommendation to silently drop to zero: the Dockerfile COPYs source
# files by explicit name (no wildcard), the new file was never added to
# that list, so `import candle_patterns` raised ModuleNotFoundError for
# every single ticker, caught by the scan's broad per-ticker exception
# handler. Living inside app.py means it can never be missing from a build.
#
# Only the two most recent bars are needed (single-candle patterns use the
# last bar; the two two-candle patterns — engulfing — compare it to the one
# before). Checked in priority order: a stronger/more specific pattern
# (engulfing) wins over a weaker single-candle read (doji) when both would
# technically match.
def _detect_candle_pattern(df) -> Dict:
    """df: hourly OHLC DataFrame (columns open/high/low/close, most recent
    last — matches _prefetch_hourly_ohlcv's shape). Returns a dict with the
    pattern name, its bullish/bearish/neutral classification, and the raw
    OHLC of the candle being described (so the UI can draw the real shape,
    not just a canned icon).

    Returns {'pattern': 'No Data', 'signal': 'neutral', ...zeros} if df is
    too short to evaluate — callers should treat that as "nothing to show",
    not as a real neutral reading."""
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
    bullish = c > o

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
            return {**result, "pattern": "Bullish Marubozu" if bullish else "Bearish Marubozu",
                    "signal": "bullish" if bullish else "bearish"}

        # Hammer: small body sitting in the upper part of the range, a long
        # lower wick (sellers pushed it down, buyers dragged it back up),
        # little to no upper wick.
        if lower_wick >= 2 * body and upper_wick <= body * 0.5 and body_ratio <= 0.35:
            return {**result, "pattern": "Hammer", "signal": "bullish"}

        # Shooting Star: mirror of Hammer — long upper wick, small body low
        # in the range, little lower wick.
        if upper_wick >= 2 * body and lower_wick <= body * 0.5 and body_ratio <= 0.35:
            return {**result, "pattern": "Shooting Star", "signal": "bearish"}

    # No named pattern — still real information: which way this hour closed.
    return {**result, "pattern": "Bullish Candle" if bullish else "Bearish Candle",
            "signal": "bullish" if bullish else "bearish"}


FADE_STREAK_LOOKBACK_DAYS = 3
FADE_STREAK_DAY_THRESHOLD_PCT = 2.0   # a day "counts" if it gave back this much from its own extreme
FADE_STREAK_MIN_DAYS = 2              # need at least this many faded days (of the lookback) to flag it


# The existing same-day reversal penalty a few lines below (intraday_move_pct)
# only ever looks at TODAY — a ticker that faded off its high yesterday too,
# and the day before, gets scored fresh each time with no memory of that
# repeat. Real example that prompted this: CRWV/IREN/HOOD each rallied early
# and gave back the gain by the close on two straight days (confirmed via
# real hourly bars) — a pattern the existing single-day check can't see at
# all. Pure computation on the SAME daily OHLC already cached for technical
# scoring (stock_agent._ohlcv_cache) — no new data fetch, unlike the hourly
# candle cache above.
def _detect_fade_streak(df, is_bearish: bool) -> Dict:
    """df: daily OHLC DataFrame, most recent last (stock_agent._ohlcv_cache's
    shape). For a bullish (CALL) read, checks whether the last
    FADE_STREAK_LOOKBACK_DAYS days each gave back >= FADE_STREAK_DAY_THRESHOLD_PCT
    of their own high by the close (didn't hold the day's own strength). For
    a bearish (PUT) read, checks the mirror — bouncing back from the day's
    own low. Returns {'days': int, 'total': int, 'is_streak': bool} — days
    is how many of the last `total` days faded; is_streak is True once days
    >= FADE_STREAK_MIN_DAYS."""
    empty = {"days": 0, "total": 0, "is_streak": False}
    if df is None or len(df) < FADE_STREAK_MIN_DAYS:
        return empty

    recent = df.iloc[-FADE_STREAK_LOOKBACK_DAYS:]
    faded_days = 0
    for _, row in recent.iterrows():
        h, l, c = float(row["high"]), float(row["low"]), float(row["close"])
        if is_bearish:
            if l <= 0:
                continue
            fade_pct = (c - l) / l * 100  # bounced back up from the low
        else:
            if h <= 0:
                continue
            fade_pct = (h - c) / h * 100  # gave back from the high
        if fade_pct >= FADE_STREAK_DAY_THRESHOLD_PCT:
            faded_days += 1

    total = len(recent)
    return {"days": faded_days, "total": total, "is_streak": faded_days >= FADE_STREAK_MIN_DAYS}


# Separate from stock_agent._ohlcv_cache (which holds ~1y of DAILY bars for
# technical scoring) — candle-pattern reads need hourly bars instead, since
# that's the timeframe a short-term bullish/bearish read actually means
# (see _detect_candle_pattern). A distinct cache and a distinct batched
# fetch, refreshed once per scan cycle, same shape/pattern as
# stock_agent.prefetch_ohlcv but never touching that cache — the two are
# unrelated data at unrelated timeframes.
_hourly_ohlcv_cache: Dict[str, "pd.DataFrame"] = {}


def _prefetch_hourly_ohlcv(tickers: List[str]) -> None:
    """Batch-fetch the last few days of hourly bars for all tickers in one
    call per chunk (Alpaca caps a single request's symbol count) — same
    one-request-per-N-tickers shape as stock_agent.prefetch_ohlcv, not a
    per-ticker loop. A per-ticker version of exactly this kind of fetch is
    what turned one real scan into ~1500 sequential network calls earlier;
    this fetches at most len(tickers)/200 times per scan cycle, not once
    per ticker. 5 days back comfortably covers weekends/holidays while
    keeping each ticker to well under 100 hourly bars — plenty for the
    2-candle patterns this needs, nowhere near the ~1y of daily history
    stock_agent's own cache carries."""
    global _hourly_ohlcv_cache
    _hourly_ohlcv_cache = {}
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        key = os.environ.get('ALPACA_API_KEY', '')
        secret = os.environ.get('ALPACA_API_SECRET', '')
        if not (key and secret):
            return
        client = StockHistoricalDataClient(key, secret)
        chunk_size = 200
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i + chunk_size]
            try:
                req = StockBarsRequest(
                    symbol_or_symbols=chunk,
                    timeframe=TimeFrame.Hour,
                    start=datetime.utcnow() - timedelta(days=5),
                    end=datetime.utcnow(),
                    adjustment='all',
                )
                raw = client.get_stock_bars(req).df
                if raw.empty:
                    continue
                symbols_present = set(raw.index.get_level_values(0))
                for ticker in chunk:
                    if ticker not in symbols_present:
                        continue
                    try:
                        tdf = raw.loc[ticker]
                        df = tdf[['close', 'high', 'low', 'open', 'volume']].dropna(subset=['close'])
                        if len(df) >= 1:
                            _hourly_ohlcv_cache[ticker] = df
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"[HourlyOHLCV] chunk {i} failed: {e}")
    except Exception as e:
        logger.warning(f"[HourlyOHLCV] prefetch failed entirely: {e}")


def _make_options_rec(ticker: str, analysis_result, price: float,
                       today_high: float = None, today_low: float = None,
                       prev_close: float = None, precomputed_candle: dict = None,
                       precomputed_fade_streak: tuple = None,
                       precomputed_first_seen: tuple = None) -> OptionsRecommendation:
    """Build an OptionsRecommendation from an AnalysisResult using expert multi-factor scoring.
    today_high/today_low (optional — from _fetch_intraday_extremes_batch) let a same-day
    reversal dampen the score even though the technical component below is daily-bar-based
    and can't see it on its own. prev_close (optional — from _fetch_prev_closes_batch) is
    informational only (day_change_pct below) — does not affect score. precomputed_candle
    (optional) skips the live _ohlcv_cache lookup below — the SP500 scan's Pass 1 reads it
    at the one point already proven to have this ticker's cache entry (right after checking
    `ticker in stock_agent._ohlcv_cache`), rather than trusting the entry is still there by
    the time this runs — real production behavior seen: a ticker confirmed present in Pass 1
    consistently reads back empty here despite nothing in this codebase ever removing cache
    entries, so this sidesteps that instead of relying on it. precomputed_fade_streak
    (optional) is a (bullish_result, bearish_result) tuple from _detect_fade_streak, computed
    both ways in Pass 1 since is_bearish isn't known until here — same cache-timing reasoning
    as precomputed_candle, just needing both directions precomputed instead of one read.
    precomputed_first_seen (optional) is a (detected_at, price_at_signal) tuple from
    _fetch_signal_first_seen, keyed by (ticker, action) — action isn't known until here either,
    so Pass 1 passes the single dict entry for this exact (ticker, action) pair (unlike
    precomputed_fade_streak, first-seen doesn't need both directions precomputed since a
    ticker's CALL and PUT rows in scan_history are already separate keys)."""
    is_bearish = (analysis_result.technical_score < 0.48 or
                  analysis_result.buy_signal in [BuySignal.HOLD, BuySignal.AVOID])
    action = "PUT" if is_bearish else "CALL"

    tech = analysis_result.technical_score
    sent = analysis_result.sentiment_score

    # ── New expert signals ───────────────────────────────────────────────────
    iv_rank     = getattr(analysis_result, 'iv_rank', 50.0)
    vol_ratio   = getattr(analysis_result, 'volume_ratio', 1.0)
    rs          = getattr(analysis_result, 'rs_vs_spy', 0.0)
    fund        = getattr(analysis_result, 'fundamental_score', 0.5)
    upside      = getattr(analysis_result, 'analyst_upside', 0.0)

    # Normalise volume: 0.3× avg → 0.0,  1.0× avg → 0.5,  2.0× avg → 1.0
    vol_score = min(1.0, max(0.0, vol_ratio / 2.0))

    # Normalise RS: −5% vs SPY → 0.0,  0% → 0.5,  +5% → 1.0
    rs_score = min(1.0, max(0.0, (rs + 5.0) / 10.0))

    # IV score: cheap options (low rank) = better to buy — normalised 0→1
    # iv_rank == 0.0 means data unavailable — treat as neutral (50)
    effective_iv = iv_rank if iv_rank > 0.0 else 50.0
    iv_score = max(0.0, 1.0 - (effective_iv / 100.0))  # rank 10 → 0.90, rank 80 → 0.20

    # ── Expert composite score ────────────────────────────────────────────────
    # Weights: technical=30%, RS vs SPY=25%, IV rank=20%, volume=15%, fundamentals=10%
    # Sentiment removed — lexicon scoring adds noise, not signal for short-term options
    if is_bearish:
        raw = ((1.0 - tech)     * 0.30 +
               (1.0 - rs_score) * 0.25 +
               iv_score         * 0.20 +
               vol_score        * 0.15 +
               (1.0 - fund)     * 0.10)
    else:
        raw = (tech      * 0.30 +
               rs_score  * 0.25 +
               iv_score  * 0.20 +
               vol_score * 0.15 +
               fund      * 0.10)

    score = round(min(1.0, max(0.0, raw)), 4)

    # ── Same-day reversal penalty ──────────────────────────────────────────
    # A CALL that's already faded well off today's own high (or a PUT that's
    # already bounced well off today's own low) is chasing a move that's
    # reversing right now, in real time — the daily-bar technical score
    # above can't see that on its own. Penalty is capped at 15 points so a
    # single intraday wiggle can't wipe out an otherwise-strong signal.
    intraday_move_pct = 0.0
    same_day_penalty = 0.0  # actual delta applied (post 0-floor clip) — see score_breakdown below
    if not is_bearish and today_high and today_high > 0 and price < today_high:
        intraday_move_pct = round((price - today_high) / today_high * 100, 2)
        if intraday_move_pct <= -1.5:
            pre = score
            score = round(max(0.0, score - min(0.15, abs(intraday_move_pct) * 0.03)), 4)
            same_day_penalty = round(pre - score, 4)
    elif is_bearish and today_low and today_low > 0 and price > today_low:
        intraday_move_pct = round((price - today_low) / today_low * 100, 2)
        if intraday_move_pct >= 1.5:
            pre = score
            score = round(max(0.0, score - min(0.15, intraday_move_pct * 0.03)), 4)
            same_day_penalty = round(pre - score, 4)

    # ── Multi-day fade-streak penalty ────────────────────────────────────────
    # The same-day check above has no memory of yesterday — a ticker that
    # faded off its own high/low on 2+ of the last 3 sessions gets scored
    # fresh here each time regardless. Real example that prompted this:
    # CRWV/IREN/HOOD each rallied early and gave the gain back by the close
    # on two straight days. Flat 8-point penalty once the streak threshold
    # is hit (not scaled by how much it faded — the pattern repeating is
    # what matters here, not the size of any one day's giveback, which the
    # same-day check above already covers) — smaller than the same-day
    # penalty's 15-point cap since this is a slower-moving, lower-certainty
    # signal than today's own live price action.
    fade_streak = (precomputed_fade_streak[1] if is_bearish else precomputed_fade_streak[0]) \
        if precomputed_fade_streak is not None \
        else _detect_fade_streak(stock_agent._ohlcv_cache.get(ticker) if stock_agent else None, is_bearish)
    fade_streak_penalty = 0.0  # actual delta applied — see score_breakdown below
    if fade_streak["is_streak"]:
        pre = score
        score = round(max(0.0, score - 0.08), 4)
        fade_streak_penalty = round(pre - score, 4)

    confidence, buy_signal = _interpret_composite_score(score)

    # ── Signal freshness ──────────────────────────────────────────────────
    # When was THIS exact (ticker, action) signal first surfaced, and how
    # has price moved since — the basis for signal_state below. No
    # precomputed_first_seen (on-demand /analyze calls, or a ticker's
    # first-ever appearance today) means there's no history to distrust
    # yet, so it's always "detected right now" — never a false Extended/
    # Faded/Invalidated claim from missing data.
    signal_detected_at, price_at_signal = precomputed_first_seen or (datetime.utcnow(), price)
    age_minutes = (datetime.utcnow() - signal_detected_at).total_seconds() / 60.0
    if price_at_signal > 0:
        # Positive = price moved IN FAVOR of the thesis since signal (up for
        # a CALL, down for a PUT) — mirrors the same direction convention
        # used throughout this function (e.g. the same-day reversal penalty).
        price_change_since_signal_pct = round(
            (price - price_at_signal) / price_at_signal * 100 * (1 if not is_bearish else -1), 2)
    else:
        price_change_since_signal_pct = 0.0

    # Thresholds reuse the app's own already-calibrated numbers rather than
    # inventing new ones: 1.5% matches the same-day reversal penalty above,
    # 5% matches the "EXT" big-move threshold this replaces. Checked in this
    # order — Fresh first (too new to judge), then Invalidated (the
    # composite score itself has degraded — a stronger claim than a price
    # wiggle), then Faded/Extended by price move, else Active.
    if age_minutes < 15:
        signal_state = "Fresh"
    elif buy_signal in ("HOLD", "AVOID"):
        signal_state = "Invalidated"
    elif price_change_since_signal_pct <= -1.5:
        signal_state = "Faded"
    elif price_change_since_signal_pct >= 5.0:
        signal_state = "Extended"
    else:
        signal_state = "Active"

    upside_score = min(1.0, max(0.0, upside / 30.0))
    long_term_score = _compute_long_term_score(tech, rs_score, fund, upside, is_bearish)

    # ── Score breakdown (single source of truth for the UI) ─────────────────
    # Mirrors the composite-score math above exactly — same direction-
    # adjusted values, same weights — plus whichever penalties actually
    # applied, in the same score-point units as `score`/`long_term_score`
    # themselves. The UI renders this directly instead of ever
    # reconstructing the formula client-side (see DashboardView.swift's
    # ScoreBreakdownCard) — the two can never disagree again since they're
    # built from the exact same variables in the exact same call.
    if is_bearish:
        _st_components = [("Technical", 0.30, 1.0 - tech), ("RS vs SPY", 0.25, 1.0 - rs_score),
                           ("IV Rank", 0.20, iv_score), ("Volume", 0.15, vol_score),
                           ("Fundamentals", 0.10, 1.0 - fund)]
        _lt_components = [("Fundamentals", 0.40, 1.0 - fund), ("Analyst Upside", 0.25, 1.0 - upside_score),
                           ("Technical", 0.25, 1.0 - tech), ("RS vs SPY", 0.10, 1.0 - rs_score)]
    else:
        _st_components = [("Technical", 0.30, tech), ("RS vs SPY", 0.25, rs_score),
                           ("IV Rank", 0.20, iv_score), ("Volume", 0.15, vol_score),
                           ("Fundamentals", 0.10, fund)]
        _lt_components = [("Fundamentals", 0.40, fund), ("Analyst Upside", 0.25, upside_score),
                           ("Technical", 0.25, tech), ("RS vs SPY", 0.10, rs_score)]

    def _breakdown(components: list, adjustments: list, final_score: float) -> dict:
        return {
            "components": [
                {"label": label, "weight": weight, "value": round(value, 4),
                 "contribution": round(weight * value, 4)}
                for label, weight, value in components
            ],
            "adjustments": [{"label": label, "amount": -amt} for label, amt in adjustments if amt],
            "final_score": final_score,
        }

    score_breakdown = _breakdown(
        _st_components,
        [("Same-day reversal", same_day_penalty), ("Multi-day fade streak", fade_streak_penalty)],
        score,
    )
    long_term_score_breakdown = _breakdown(_lt_components, [], long_term_score)

    # Candlestick read — precomputed_candle (see docstring) is preferred;
    # only fall back to a live _hourly_ohlcv_cache lookup for the 3 call
    # sites that don't pass it (their tickers may not be in that cache at
    # all if the main SP500 scan hasn't run recently — a miss here just
    # means "No Data" for those, same as any other cache miss).
    if precomputed_candle is not None:
        candle = precomputed_candle
    else:
        candle = _detect_candle_pattern(_hourly_ohlcv_cache.get(ticker))
    # NaN is valid Python/pandas but invalid JSON per Postgres's strict
    # parser — guarding cheaply against it regardless of a scoring/display
    # field ever silently becoming NaN (not observed in testing).
    for _k in ("open", "high", "low", "close"):
        if candle[_k] != candle[_k]:  # NaN != NaN is the classic no-import check
            candle[_k] = 0.0

    strike = _strike_for_action(price, action)
    expiry = _next_monthly_expiry()
    expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
    days_to_expiry = (expiry_dt - datetime.utcnow()).days

    rec = OptionsRecommendation(
        ticker=ticker,
        action=action,
        strike_price=strike,
        expiry_date=expiry,
        score=score,
        confidence=confidence,
        current_price=price,
        buy_signal=buy_signal,
        technical_score=round(analysis_result.technical_score, 4),
        sentiment_score=round(analysis_result.sentiment_score, 4),
        ml_score=round(analysis_result.ml_score, 4),
        timestamp=datetime.utcnow().isoformat(),
        thesis=_generate_thesis(ticker, action, score, confidence, tech, rs, iv_rank, vol_ratio,
                                 intraday_move_pct, price, strike,
                                 getattr(analysis_result, 'days_to_earnings', 999),
                                 getattr(analysis_result, 'rsi', 50.0),
                                 getattr(analysis_result, 'market_score', 0.5)),
        days_to_expiry=days_to_expiry,
        iv_rank=round(getattr(analysis_result, 'iv_rank', 50.0), 1),
        volume_ratio=round(getattr(analysis_result, 'volume_ratio', 1.0), 2),
        rs_vs_spy=round(getattr(analysis_result, 'rs_vs_spy', 0.0), 2),
        days_to_earnings=getattr(analysis_result, 'days_to_earnings', 999),
        analyst_upside=round(getattr(analysis_result, 'analyst_upside', 0.0), 1),
        analyst_count=getattr(analysis_result, 'analyst_count', 0),
        score_breakdown=score_breakdown,
        long_term_score_breakdown=long_term_score_breakdown,
        signal_detected_at=signal_detected_at.isoformat(),
        price_at_signal=round(price_at_signal, 2),
        price_change_since_signal_pct=price_change_since_signal_pct,
        signal_state=signal_state,
        long_term_score=long_term_score,
        intraday_move_pct=intraday_move_pct,
        day_change_pct=round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
        avg_dollar_volume=round(getattr(analysis_result, 'avg_dollar_volume', 0.0), 0),
        candle_pattern=candle["pattern"],
        candle_signal=candle["signal"],
        candle_open=round(candle["open"], 2),
        candle_high=round(candle["high"], 2),
        candle_low=round(candle["low"], 2),
        candle_close=round(candle["close"], 2),
        fade_streak_days=fade_streak["days"],
        fade_streak_total=fade_streak["total"],
    )
    # Computed here so every scanned rec carries them (cheap, no network calls)
    # — not just the ones enriched with catalyst data later. See call sites
    # below that recompute after catalyst_age_days is set, for freshness.
    rec.key_factors, rec.risks = _generate_key_factors_and_risks(rec)
    return rec


_POSITIVE_WORDS = {'surge','soar','rally','gain','growth','profit','strong','rebound','upgrade',
                   'beat','exceed','bullish','outstanding','breakthrough','positive','optimistic'}
_NEGATIVE_WORDS = {'crash','collapse','plunge','plummet','decline','weak','miss','loss','bearish',
                   'downgrade','disappointing','crisis','recession','failure','drop','poor'}

_news_client = None  # lazy, cached — same Alpaca credentials already used everywhere else


def _get_news_client():
    global _news_client
    if _news_client is None and _ALPACA_KEY and _ALPACA_SECRET:
        try:
            from alpaca.data.historical.news import NewsClient
            _news_client = NewsClient(_ALPACA_KEY, _ALPACA_SECRET)
        except Exception as e:
            logger.warning(f"[News] Could not init Alpaca news client: {e}")
    return _news_client


def _fetch_ticker_news(ticker: str) -> list:
    """Fetch up to 5 recent headlines for a ticker via Alpaca (switched from
    yfinance — its news endpoint was failing frequently, ~28 errors/day).
    Display-only, not used in scoring."""
    try:
        from alpaca.data.requests import NewsRequest
        client = _get_news_client()
        if client is None:
            return []
        req = NewsRequest(symbols=ticker, limit=5)
        items = client.get_news(req).data.get('news', [])
        result = []
        for item in items[:5]:
            title = item.headline or ''
            words = set(title.lower().split())
            pos = len(words & _POSITIVE_WORDS)
            neg = len(words & _NEGATIVE_WORDS)
            if pos > neg:
                sentiment = 'positive'
            elif neg > pos:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            result.append({
                'title': title,
                'publisher': item.source or '',
                'published_at': int(item.created_at.timestamp()) if item.created_at else 0,
                'sentiment': sentiment,
            })
        return result
    except Exception:
        return []


def _find_price_near_date(ticker: str, target_date) -> Optional[float]:
    """Ticker's scanned price on/soon after target_date, from the real
    Postgres scan_history table (same one GET /sp500/scan-history reads) —
    used to measure how much of a move already happened before today's
    signal, not just whether the headline is old. Replaces a local-JSON-
    file lookup that silently always returned None on Railway (ephemeral
    filesystem, wiped on every redeploy) — price_change_since_catalyst was
    always defaulting to 0.0 in production as a result (confirmed
    2026-09-11 by cross-checking real dated headlines against the field
    for several tickers).

    Note: scan_history is pruned to the 2 most recent trading dates (see
    _save_scan_history_pg), so this still can't resolve a catalyst older
    than that window — it'll cleanly return None (correctly defaulting to
    0.0) rather than silently claiming data it doesn't have."""
    conn = _get_pg_conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            for offset in range(3):  # target day, then up to 2 days later (weekends/holidays)
                day = target_date + timedelta(days=offset)
                cur.execute(
                    "SELECT current_price FROM scan_history "
                    "WHERE ticker = %s AND scan_time::date = %s "
                    "ORDER BY scan_time ASC LIMIT 1",
                    (ticker, day),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return float(row[0])
        return None
    except Exception as e:
        logger.debug("[CatalystFreshness] %s price lookup failed: %s", ticker, e)
        return None


def _compute_catalyst_freshness(ticker: str, headlines: list, current_price: float):
    """How old is the news driving this signal, and how much of the move
    already happened? Catches cases like TEM's Merck/Moderna pop on
    2026-08-19 — by the following Monday the most recent headline is days
    old with no fresh follow-up, and most of the price move already
    happened, so a fresh BUY signal that day would be chasing a move that's
    largely over, not catching a new one. Returns (age_days, pct_change),
    either of which is None if there isn't enough data to compute it."""
    if not headlines:
        return None, None
    try:
        newest_ts = max((h.get("published_at") or 0) for h in headlines)
        if not newest_ts:
            return None, None
        newest_dt = datetime.utcfromtimestamp(newest_ts)
        age_days = (datetime.utcnow() - newest_dt).days
        hist_price = _find_price_near_date(ticker, newest_dt.date())
        pct_change = None
        if hist_price and hist_price > 0 and current_price > 0:
            pct_change = round((current_price - hist_price) / hist_price * 100, 1)
        return age_days, pct_change
    except Exception:
        return None, None


def _fetch_fundamentals(ticker: str) -> dict:
    """Fetch key fundamental metrics for display in Before You Buy.
    Finnhub-backed — replaced yfinance's .info scrape (see
    mcp_stock_agent.py's _fetch_real_options_data docstring for the
    yfinance-removal incident this is part of). Display-only, not a
    scoring input, so partial coverage is an acceptable degradation:
    Finnhub's free-tier /stock/metric endpoint has no direct equivalent
    for total_cash/free_cashflow/operating_cashflow (it exposes ratios
    and per-share figures, not raw balance-sheet dollar amounts) — those
    three stay None (the existing _f() / iOS side already treat None as
    "omit this row", not a fake zero) rather than being approximated.
    The growth/margin/ROE fields Finnhub does have come back as whole
    percentages (e.g. 14.24 meaning 14.24%) where yfinance's equivalent
    fields were fractions (0.1424) — divided by 100 here so the stored
    value keeps the same units the existing display code already expects,
    with no iOS change needed."""
    try:
        import requests
        api_key = os.environ.get('FINNHUB_API_KEY', '')
        if not api_key:
            raise RuntimeError("Finnhub API key not configured")
        resp = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={"symbol": ticker, "metric": "all", "token": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        m = resp.json().get("metric") or {}

        def _f(key, scale=1.0):
            v = m.get(key)
            if v is None or (isinstance(v, float) and v != v):
                return None
            return v / scale

        return {
            "debt_to_equity":   _f("totalDebt/totalEquityQuarterly"),
            "current_ratio":    _f("currentRatioQuarterly"),
            "total_cash":       None,   # no free raw-dollar equivalent on Finnhub
            "free_cashflow":    None,   # no free raw-dollar equivalent on Finnhub
            "operating_cashflow": None, # no free raw-dollar equivalent on Finnhub
            "revenue_growth":   _f("revenueGrowthTTMYoy", scale=100.0),
            "earnings_growth":  _f("epsGrowthTTMYoy", scale=100.0),
            "profit_margins":   _f("netProfitMarginTTM", scale=100.0),
            "gross_margins":    _f("grossMarginTTM", scale=100.0),
            "trailing_pe":      _f("peTTM"),
            "forward_pe":       _f("forwardPE"),
            "price_to_book":    _f("pbQuarterly"),
            "return_on_equity": _f("roeTTM", scale=100.0),
        }
    except Exception as e:
        logger.debug("[Fundamentals] %s failed: %s", ticker, e)
        return {}


# ============================================================================
# GLOBAL STATE
# ============================================================================

news_analyzer = None
technical_analyzer = None
options_analyzer = None
market_analyzer = None
strategy_selector = None
call_put_predictor = None
reasoning_generator = None

stock_agent = None
notification_manager = None

# Active WebSocket connections
active_connections = {}
agent_connections = []
options_ws_connections: List[WebSocket] = []   # SP500 options live stream

# Latest SP500 analysis results (updated every 20 min)
latest_options_recs: List[OptionsRecommendation] = []
last_sp500_run: Optional[datetime] = None

_RESULTS_FILE = "/tmp/sp500_results.json"

# ── Postgres persistence ─────────────────────────────────────────────────
# The in-memory cache and the /tmp JSON fallback below are both wiped by
# every Railway redeploy — confirmed the hard way on 2026-08-24, when a
# deploy after market close left the app with zero recommendations because
# /tmp doesn't survive a redeploy and local_runner.py had already gone to
# sleep for the night. Postgres actually survives redeploys. Used as the
# primary store; the /tmp file stays as a secondary fallback in case
# DATABASE_URL is ever unset, so nothing regresses if Postgres is briefly
# unreachable.
_pg_conn = None


def _get_pg_conn():
    global _pg_conn
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        if _pg_conn is not None and not _pg_conn.closed:
            # A previous failed write leaves Postgres transactions on this
            # connection aborted — without a rollback, every subsequent
            # query on it fails too, for the rest of the process's life,
            # not just the one bad write. Rolling back a connection with no
            # open transaction is a harmless no-op, so this runs
            # unconditionally rather than trying to detect whether it's
            # actually needed.
            try:
                _pg_conn.rollback()
                return _pg_conn
            except Exception:
                _pg_conn = None  # truly dead (e.g. network drop) — reconnect below
        import psycopg2
        _pg_conn = psycopg2.connect(db_url)
        with _pg_conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS latest_scan (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    recommendations JSONB NOT NULL,
                    last_run TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            # Deliberately lean (no thesis/fundamentals/key_factors blob) —
            # this exists to answer "what did we score ticker X at time Y",
            # not to replay the full analysis. Kept to the last 2 distinct
            # trading dates only (see _prune_scan_history), so row count
            # stays bounded regardless of how long the app has been running.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    id BIGSERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    action TEXT NOT NULL,
                    score DOUBLE PRECISION NOT NULL,
                    current_price DOUBLE PRECISION NOT NULL,
                    scan_time TIMESTAMPTZ NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_ticker_time ON scan_history (ticker, scan_time)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_time ON scan_history (scan_time)")
        _pg_conn.commit()
        return _pg_conn
    except Exception as e:
        logger.warning(f"[Postgres] Connection failed: {e}")
        _pg_conn = None
        return None


def _save_results_pg():
    conn = _get_pg_conn()
    if conn is None:
        return
    try:
        import json as _json
        # allow_nan=False so a stray NaN/Infinity raises here (caught below,
        # save just skipped for this cycle) instead of producing JSON text
        # that Postgres's strict parser would reject at INSERT time anyway.
        payload = _json.dumps([asdict(r) for r in latest_options_recs], allow_nan=False)
        last_run_dt = last_sp500_run or datetime.utcnow()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO latest_scan (id, recommendations, last_run, updated_at)
                VALUES (1, %s, %s, now())
                ON CONFLICT (id) DO UPDATE
                SET recommendations = EXCLUDED.recommendations,
                    last_run = EXCLUDED.last_run,
                    updated_at = now()
            """, (payload, last_run_dt))
        conn.commit()
    except Exception as e:
        logger.warning(f"[Postgres] Save failed: {e}")


def _save_scan_history_pg():
    """One row per rec, per scan cycle — the actual history that answers
    'what did Arka score X at time Y', which the single-row latest_scan
    table above can never answer since each cycle overwrites it. Pruned to
    the 2 most recent distinct trading dates on every call so this can run
    indefinitely without unbounded growth."""
    conn = _get_pg_conn()
    if conn is None or not latest_options_recs:
        return
    try:
        scan_time = last_sp500_run or datetime.utcnow()
        rows = [(r.ticker, r.action, r.score, r.current_price, scan_time) for r in latest_options_recs]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO scan_history (ticker, action, score, current_price, scan_time) VALUES (%s, %s, %s, %s, %s)",
                rows,
            )
            cur.execute("""
                DELETE FROM scan_history
                WHERE scan_time::date NOT IN (
                    SELECT DISTINCT scan_time::date FROM scan_history ORDER BY scan_time::date DESC LIMIT 2
                )
            """)
        conn.commit()
    except Exception as e:
        logger.warning(f"[Postgres] scan_history save failed: {e}")


def _load_results_pg() -> bool:
    """Returns True if it successfully restored from Postgres, so the /tmp
    fallback below can be skipped when this already worked."""
    global latest_options_recs, last_sp500_run
    conn = _get_pg_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT recommendations, last_run FROM latest_scan WHERE id = 1")
            row = cur.fetchone()
        if not row:
            return False
        recs_data, last_run = row
        saved_date = last_run.astimezone(ZoneInfo("America/New_York")).date()
        today = datetime.now(ZoneInfo("America/New_York")).date()
        if saved_date < today:
            logger.info("[Postgres] Saved results are from a previous day — skipping load")
            return False
        recs = []
        for r in recs_data:
            try:
                recs.append(OptionsRecommendation(**{k: r[k] for k in r if k in OptionsRecommendation.__dataclass_fields__}))
            except Exception:
                continue
        latest_options_recs = recs
        # last_sp500_run is naive UTC everywhere else in this codebase (set
        # via datetime.utcnow()) -- must convert to UTC here too, not ET.
        # This used to convert to America/New_York and strip tzinfo,
        # silently mislabeling an ET-valued naive datetime as if it were
        # UTC. Every value read back after a restart was off by the
        # UTC-ET offset (4-5h depending on DST) until the next real scan
        # overwrote it -- confirmed directly: a status check showed
        # last_run as "2026-09-17T21:29:33", exactly 4 hours off the real
        # "2026-09-18T01:29:33" UTC value of that same scan.
        last_sp500_run = last_run.astimezone(timezone.utc).replace(tzinfo=None)
        logger.info(f"[Postgres] Restored {len(recs)} recommendations from database")
        return True
    except Exception as e:
        logger.warning(f"[Postgres] Load failed: {e}")
        return False


def _save_results():
    _save_results_pg()
    try:
        import json as _json
        data = {"last_run": last_sp500_run.isoformat() if last_sp500_run else None,
                "recommendations": [asdict(r) for r in latest_options_recs]}
        with open(_RESULTS_FILE, "w") as f:
            _json.dump(data, f)
    except Exception as e:
        logger.warning(f"Could not save results: {e}")

def _load_results():
    global latest_options_recs, last_sp500_run
    if _load_results_pg():
        return
    try:
        import json as _json
        with open(_RESULTS_FILE) as f:
            data = _json.load(f)
        # Don't load stale data from a previous trading day
        if data.get("last_run"):
            saved_dt = datetime.fromisoformat(data["last_run"])
            saved_date = saved_dt.astimezone(ZoneInfo("America/New_York")).date()
            today = datetime.now(ZoneInfo("America/New_York")).date()
            if saved_date < today:
                logger.info("Saved results are from a previous day — skipping load")
                return
        recs = []
        for r in data.get("recommendations", []):
            recs.append(OptionsRecommendation(**{k: r[k] for k in r if k in OptionsRecommendation.__dataclass_fields__}))
        latest_options_recs = recs
        if data.get("last_run"):
            last_sp500_run = datetime.fromisoformat(data["last_run"])
        logger.info(f"Loaded {len(latest_options_recs)} saved results from disk")
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"Could not load saved results: {e}")

async def _eod_clear_loop():
    """Clear results at 4:05 PM ET every trading day."""
    import os as _os
    while True:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        # Calculate seconds until next 4:05 PM ET
        target = now_et.replace(hour=16, minute=5, second=0, microsecond=0)
        if now_et >= target:
            target = target.replace(day=target.day + 1)
        wait = (target - now_et).total_seconds()
        await asyncio.sleep(wait)
        global latest_options_recs, last_sp500_run
        latest_options_recs = []
        last_sp500_run = None
        try:
            _os.remove(_RESULTS_FILE)
        except FileNotFoundError:
            pass
        logger.info("EOD: cleared SP500 results for next trading day")

# Hourly snapshots: list of {"timestamp": str, "hour_label": str, "recommendations": [...]}
# Only saved during market hours; cleared each new trading day.
hourly_snapshots: List[Dict] = []
_last_snapshot_hour: Optional[int] = None  # ET hour of last saved snapshot
_last_snapshot_date: Optional[str]  = None  # ET date of last saved snapshot (clears daily)


# ============================================================================
# SP500 SCHEDULER (background task)
# ============================================================================

GAP_RISK_PCT = 0.07  # already-moved-this-much-since-last-close is treated as "something happened"

_data_feed_cache = None  # None = not yet checked; DataFeed.SIP or DataFeed.IEX once known


def _get_data_feed():
    """Detect once whether the Alpaca account has real-time SIP entitlement
    and cache the result — avoids retrying a failing SIP check on every
    single request. Measured 2026-08-24: the free IEX feed (single venue,
    not the consolidated tape) runs ~10-27 minutes behind wall-clock time
    depending on the ticker, which every price-based score has been quietly
    running on. Once the account is upgraded to the paid SIP plan, this
    starts returning DataFeed.SIP automatically on the next process
    restart — no further code change needed."""
    global _data_feed_cache
    if _data_feed_cache is not None:
        return _data_feed_cache
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest
        from alpaca.data.enums import DataFeed
        client = StockHistoricalDataClient(_ALPACA_KEY, _ALPACA_SECRET)
        client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols="SPY", feed=DataFeed.SIP))
        _data_feed_cache = DataFeed.SIP
        logger.info("[DataFeed] Real-time SIP feed available — using it")
    except Exception:
        from alpaca.data.enums import DataFeed
        _data_feed_cache = DataFeed.IEX
        logger.info("[DataFeed] SIP not available on this account — using free IEX feed (delayed)")
    return _data_feed_cache


def _fetch_prev_closes_batch(tickers: List[str]) -> Dict[str, float]:
    """Previous session's close per ticker, via the same Alpaca snapshot data
    _fetch_prices_batch already pulls current prices from. Used as an
    earnings/news-agnostic gap check — the earnings-date lookup is unreliable
    exactly around the event itself (see _fetch_earnings_date), but a large
    already-happened gap is a reliable signal regardless of the cause."""
    prev_closes: Dict[str, float] = {}
    if not (_ALPACA_KEY and _ALPACA_SECRET):
        return prev_closes
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockSnapshotRequest
        client = StockHistoricalDataClient(_ALPACA_KEY, _ALPACA_SECRET)
        chunk_size = 500
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i + chunk_size]
            snaps = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=chunk, feed=_get_data_feed()))
            for sym, snap in snaps.items():
                if snap.previous_daily_bar and snap.previous_daily_bar.close:
                    prev_closes[sym] = float(snap.previous_daily_bar.close)
    except Exception as e:
        logger.warning(f"[Gap check] Previous close fetch failed: {e}")
    return prev_closes


def _fetch_intraday_extremes_batch(tickers: List[str]) -> Dict[str, Tuple[float, float]]:
    """Today's high/low so far per ticker, via the same Alpaca snapshot data
    the price/gap batches already use. The technical score is built entirely
    from daily bars, so it has no way to see a same-day reversal — a stock
    that's already faded 4% off today's own high still scores as if today
    were still at its open. This lets _make_options_rec apply a same-day
    fade/bounce penalty the daily-bar technicals can't see on their own."""
    extremes: Dict[str, Tuple[float, float]] = {}
    if not (_ALPACA_KEY and _ALPACA_SECRET):
        return extremes
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockSnapshotRequest
        client = StockHistoricalDataClient(_ALPACA_KEY, _ALPACA_SECRET)
        chunk_size = 500
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i + chunk_size]
            snaps = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=chunk, feed=_get_data_feed()))
            for sym, snap in snaps.items():
                bar = snap.daily_bar
                if bar and bar.high and bar.low:
                    extremes[sym] = (float(bar.high), float(bar.low))
    except Exception as e:
        logger.warning(f"[Intraday extremes] Fetch failed: {e}")
    return extremes


def _fetch_signal_first_seen() -> Dict[Tuple[str, str], Tuple[datetime, float]]:
    """Earliest scan_time + price today for every (ticker, action) pair
    already in scan_history — i.e. "when did we first flag this exact
    signal, and at what price" — the basis for signal_state/age below.
    One query per scan cycle, not per-ticker, same batching discipline as
    _fetch_prev_closes_batch/_fetch_intraday_extremes_batch above. Reuses
    the same scan_history table those write to (app.py's own persistence,
    not a new table) — see _save_scan_history_pg. Fails open: a miss (no
    Postgres, or a ticker with no rows yet today) just means the caller
    falls back to "detected now," never a crash or a false claim."""
    first_seen: Dict[Tuple[str, str], Tuple[datetime, float]] = {}
    conn = _get_pg_conn()
    if conn is None:
        return first_seen
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (ticker, action) ticker, action, scan_time, current_price
                FROM scan_history
                WHERE scan_time::date = CURRENT_DATE
                ORDER BY ticker, action, scan_time ASC
            """)
            for ticker, action, scan_time, price in cur.fetchall():
                # psycopg2 returns TIMESTAMPTZ columns as timezone-aware
                # datetimes; the rest of this codebase (including what gets
                # subtracted from this in _make_options_rec) uses naive
                # datetime.utcnow() throughout. Stripped here — not down at
                # the subtraction — so first_seen stays a normal (naive utc)
                # datetime everywhere it's used, same as every other
                # timestamp in this file. Confirmed via a real production
                # incident: every ticker crashed on this exact
                # naive-minus-aware TypeError on the first scan cycle that
                # had real scan_history rows to compare against, silently
                # caught by Pass 3's per-ticker try/except and producing 0
                # recommendations with no visible error.
                if scan_time.tzinfo is not None:
                    scan_time = scan_time.replace(tzinfo=None)
                first_seen[(ticker, action)] = (scan_time, float(price))
    except Exception as e:
        logger.warning(f"[Signal freshness] first-seen fetch failed: {e}")
    return first_seen


def _fetch_prices_batch(tickers: List[str]) -> Dict[str, float]:
    """Fetch real-time mid-prices via Alpaca snapshots. Falls back to yfinance on failure."""
    prices: Dict[str, float] = {}

    # Primary: Alpaca real-time snapshots
    if _ALPACA_KEY and _ALPACA_SECRET:
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockSnapshotRequest
            client = StockHistoricalDataClient(_ALPACA_KEY, _ALPACA_SECRET)
            chunk_size = 500
            for i in range(0, len(tickers), chunk_size):
                chunk = tickers[i:i + chunk_size]
                snaps = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=chunk, feed=_get_data_feed()))
                for sym, snap in snaps.items():
                    p = 0.0
                    if snap.latest_quote:
                        ask = float(snap.latest_quote.ask_price or 0)
                        bid = float(snap.latest_quote.bid_price or 0)
                        p = (ask + bid) / 2 if ask > 0 and bid > 0 else ask or bid
                    if p <= 0 and snap.latest_trade:
                        p = float(snap.latest_trade.price or 0)
                    if p > 0:
                        prices[sym] = round(p, 2)
            logger.info(f"[Alpaca] Real-time prices for {len(prices)}/{len(tickers)} tickers")
        except Exception as e:
            logger.warning(f"[Alpaca] Snapshot failed: {e} — falling back to yfinance")

    # Fallback: yfinance for any tickers Alpaca missed
    missing = [t for t in tickers if t not in prices]
    if missing:
        try:
            data = yf.download(missing, period="1d", progress=False, auto_adjust=True, threads=True)
            close = data["Close"] if "Close" in data.columns else data
            last_row = close.iloc[-1]
            for ticker in missing:
                try:
                    p = float(last_row[ticker])
                    if p > 0 and not math.isnan(p):
                        prices[ticker] = round(p, 2)
                except Exception:
                    pass
            logger.info(f"[yfinance] Fallback prices for {len([t for t in missing if t in prices])}/{len(missing)} tickers")
        except Exception as e:
            logger.warning(f"[yfinance] Fallback batch failed: {e}")

    return prices


def _fallback_price(ticker: str) -> float:
    """Fetch individual real-time price via Alpaca. Falls back to yfinance."""
    if _ALPACA_KEY and _ALPACA_SECRET:
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestQuoteRequest
            client = StockHistoricalDataClient(_ALPACA_KEY, _ALPACA_SECRET)
            quotes = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=ticker, feed=_get_data_feed()))
            q = quotes.get(ticker)
            if q:
                ask = float(q.ask_price or 0)
                bid = float(q.bid_price or 0)
                p = (ask + bid) / 2 if ask > 0 and bid > 0 else ask or bid
                if p > 0:
                    return round(p, 2)
        except Exception:
            pass
    try:
        p = yf.Ticker(ticker).fast_info.last_price
        if p and p > 0:
            return round(float(p), 2)
    except Exception:
        pass
    return 0.0


# Bounded concurrency for per-ticker analysis. analyze_ticker() is `async def`
# but its internals (yfinance options-chain/fundamentals/earnings lookups)
# are all plain blocking calls with no real `await` inside — so scanning
# tickers one at a time via a straight `await` loop never overlapped any of
# that I/O, which is why a scan could take 10+ minutes once the 20-min
# options-chain cache expired. Running it through a real thread pool lets
# up to ANALYZE_CONCURRENCY tickers' worth of blocking yfinance/Alpaca calls
# be in flight at once. Raised from 8 to 16 alongside the ticker-universe
# expansion (dynamic_tickers.py, ~431 -> ~1,650 tickers) to keep the scan
# comfortably inside the 2-min cycle. Still kept modest rather than 50+
# because yfinance has no official rate limit and aggressive concurrency
# risks Yahoo throttling.
ANALYZE_CONCURRENCY = 16
_ANALYZE_EXECUTOR = ThreadPoolExecutor(max_workers=ANALYZE_CONCURRENCY, thread_name_prefix="analyze")


def _analyze_ticker_sync(ticker: str, price: float, use_finnhub: bool = True):
    """Thread-pool entry point — analyze_ticker has no internal awaits, so a
    fresh event loop per call is cheap and safe (no other loop touches this thread)."""
    return asyncio.run(stock_agent.analyze_ticker(ticker, price, use_finnhub=use_finnhub))


def _score_analyzed_results(
    analyzed_list,
    intraday_extremes_map: Dict[str, Tuple[Optional[float], Optional[float]]],
    prev_close_map: Dict[str, float],
    candles: Dict[str, dict],
    fade_streaks: Dict[str, tuple],
    first_seen_map: Dict[Tuple[str, str], Tuple[datetime, float]],
) -> Dict[str, OptionsRecommendation]:
    """Shared scoring/gating logic: earnings gate, bullish/bearish
    threshold, minimum score cutoff. Used by both the full
    _analyze_sp500_options scan and _refresh_final_tickers's fast re-score
    loop, so the two can't silently diverge into different rules for what
    counts as a signal."""
    out: Dict[str, OptionsRecommendation] = {}
    for idx, (ticker, price, result, err) in enumerate(analyzed_list, 1):
        if err is not None:
            logger.debug(f"[SP500] {ticker} skipped: {err}")
            continue
        try:
            # Skip if earnings are ≤3 days away — IV crush kills option buyers
            if result.days_to_earnings <= 3:
                logger.debug("[SP500] %s skipped — earnings in %d days",
                             ticker, result.days_to_earnings)
                continue

            # Include bullish (CALL, tech >= 0.55) and bearish (PUT, tech <= 0.45)
            is_bullish = result.technical_score >= 0.55
            is_bearish = result.technical_score <= 0.45
            if is_bullish or is_bearish:
                t_high, t_low = intraday_extremes_map.get(ticker, (None, None))
                # Matches _make_options_rec's own internal is_bearish check —
                # never disagrees in practice since that check's 0.48 cutoff
                # sits strictly between this gate's 0.55/0.45 thresholds.
                action = "PUT" if is_bearish else "CALL"
                rec = _make_options_rec(ticker, result, price, today_high=t_high, today_low=t_low,
                                         prev_close=prev_close_map.get(ticker),
                                         precomputed_candle=candles.get(ticker),
                                         precomputed_fade_streak=fade_streaks.get(ticker),
                                         precomputed_first_seen=first_seen_map.get((ticker, action)))
                if rec.score >= 0.55:  # minimum signal strength
                    out[ticker] = rec

            if idx % 100 == 0:
                logger.info(f"[SP500] Progress {idx}/{len(analyzed_list)}")
        except Exception as e:
            logger.debug(f"[SP500] {ticker} skipped: {e}")
    return out


async def _analyze_sp500_options() -> List[OptionsRecommendation]:
    """Analyze top 500 liquid US stocks, return top options recommendations."""
    global latest_options_recs, last_sp500_run

    from dynamic_tickers import get_dynamic_tickers
    loop = asyncio.get_event_loop()
    tickers = await loop.run_in_executor(None, get_dynamic_tickers)
    if not tickers:
        # No static-list fallback — a stale, hand-curated ticker list (dead
        # tickers, non-S&P-500 names mixed in) would silently mislead rather
        # than help. Skip this cycle and keep the last good recommendations;
        # the next cycle retries the real dynamic fetch.
        logger.error("[SP500] Dynamic ticker universe fetch returned 0 tickers — skipping this scan cycle")
        return latest_options_recs

    # Discovery: pull in tickers making breaking news that haven't cleared
    # the normal market-cap/price/volume quality filter yet. They still go
    # through the full gap/earnings/technical-score gauntlet below like any
    # other ticker — this just gives them a chance to be considered at all.
    news_tickers = await loop.run_in_executor(None, stock_agent.get_news_matched_tickers)
    discovered = sorted(t for t in news_tickers
                         if t not in tickers and re.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?", t))
    if discovered:
        logger.info(f"[SP500] +{len(discovered)} tickers pulled in from breaking news: {discovered}")
        tickers = tickers + discovered

    logger.info(f"[SP500] Starting full analysis of {len(tickers)} tickers...")

    # Fetch real prices + OHLCV for all tickers up front (one batch call each)
    loop = asyncio.get_event_loop()
    price_map = await loop.run_in_executor(None, _fetch_prices_batch, tickers)
    prev_close_map = await loop.run_in_executor(None, _fetch_prev_closes_batch, tickers)
    intraday_extremes_map = await loop.run_in_executor(None, _fetch_intraday_extremes_batch, tickers)
    # One query for every (ticker, action) already in today's scan_history —
    # not per-ticker, same batching discipline as the two fetches above.
    first_seen_map = await loop.run_in_executor(None, _fetch_signal_first_seen)
    # SPY must be cached too — rs_vs_spy (25% of the composite score) reads it
    # from _ohlcv_cache directly and silently defaults to 0.0 if it's missing,
    # which it always was since SPY isn't one of the 500 scanned tickers.
    prefetch_list = tickers if 'SPY' in tickers else tickers + ['SPY']
    await loop.run_in_executor(None, stock_agent.prefetch_ohlcv, prefetch_list)
    # Separate cache, separate timeframe (hourly, not daily) — see
    # _prefetch_hourly_ohlcv's docstring for why this is its own batched
    # call rather than reusing stock_agent's daily-bar cache.
    await loop.run_in_executor(None, _prefetch_hourly_ohlcv, tickers)

    recs: List[OptionsRecommendation] = []
    gapped_tickers: set = set()

    # Pass 1 — cheap, in-memory filtering only (no network calls), sequential.
    candidates: List[Tuple[str, float]] = []
    # Candle read computed HERE, not in Pass 3 — this is the one point
    # already proven reliable for the (separate, daily) _ohlcv_cache lookup
    # right below, and read from _hourly_ohlcv_cache (see
    # _prefetch_hourly_ohlcv) rather than stock_agent's daily cache, since
    # an hourly bar is what "the last candle" actually means for a
    # short-term bullish/bearish read. .get(), not direct indexing — the
    # hourly fetch can legitimately miss a ticker the daily one has
    # (separate call, separate failure modes), and a miss here just means
    # "No Data" for that one ticker's candle read.
    candles: Dict[str, dict] = {}
    # Fade-streak precomputed HERE for the same reason as candles above —
    # this loop is the one proven-reliable point of access to
    # stock_agent._ohlcv_cache. Direction (CALL vs PUT) isn't known until
    # deep inside _make_options_rec, so both directions are computed once
    # here and the right one is picked later — mirrors precomputed_candle.
    fade_streaks: Dict[str, tuple] = {}
    for ticker in tickers:
        # Skip tickers that have no real OHLCV data (delisted / bankrupt)
        if ticker not in stock_agent._ohlcv_cache:
            continue
        candles[ticker] = _detect_candle_pattern(_hourly_ohlcv_cache.get(ticker))
        fade_streaks[ticker] = (
            _detect_fade_streak(stock_agent._ohlcv_cache[ticker], is_bearish=False),
            _detect_fade_streak(stock_agent._ohlcv_cache[ticker], is_bearish=True),
        )

        price = price_map.get(ticker) or _fallback_price(ticker)
        if not price or price <= 0:
            continue

        # Gap check — used to hard-skip tickers that already moved a lot
        # since last close (originally to catch earnings/news moves the
        # unreliable days_to_earnings lookup below can miss, e.g. COHR's
        # -14% earnings-day drop on 2026-08-13 slipping through with
        # days_to_earnings misreported as 999). That silently hid the
        # day's biggest movers entirely — a user asking "why isn't DELL/
        # HPE on my list" had no way to know they'd gapped past the
        # threshold and gotten excluded before analysis even ran. Now
        # still analyzed and shown (still subject to the real
        # days_to_earnings <= 3 filter below), just flagged via
        # is_gapped/day_change_pct so the UI can badge it as already
        # having moved rather than hiding it.
        prev_close = prev_close_map.get(ticker)
        if prev_close and prev_close > 0:
            gap = abs(price - prev_close) / prev_close
            if gap > GAP_RISK_PCT:
                gapped_tickers.add(ticker)
                logger.debug("[SP500] %s already gapped %.1f%% since last close — analyzing anyway",
                             ticker, gap * 100)

        # Sanity check — a live price must fall within its own day's
        # high/low (already fetched this same scan via the same Alpaca
        # snapshot call). If it doesn't, the price itself is bad — a stale
        # or mismatched fetch (e.g. yfinance falling back to a prior
        # session for one ticker) rather than a real move. MSTR showed
        # $115.74 in one scan while its real intraday range that day was
        # $119.38-$127.90 — nowhere close to Friday's prior-session data
        # it apparently returned; the gap check above didn't catch it
        # because $115.74 wasn't an implausible jump from prev_close,
        # just wrong.
        today_high, today_low = intraday_extremes_map.get(ticker, (None, None))
        if not _is_price_plausible(price, today_low, today_high):
            logger.warning(
                "[SP500] %s skipped — price $%.2f outside today's own range $%.2f-$%.2f (bad fetch)",
                ticker, price, today_low or 0.0, today_high or 0.0)
            continue

        candidates.append((ticker, float(price)))

    # Batch-prefetch options data for every candidate in a handful of large
    # calls instead of one Trading-API call per ticker in Pass 2 — see
    # prefetch_options_data's docstring for why the per-ticker version was
    # a hard bottleneck (Alpaca's Trading API is rate-limited account-wide,
    # independent of connection reuse or thread concurrency; confirmed in
    # production that a full scan took 7.5-8.5 minutes regardless).
    await loop.run_in_executor(None, stock_agent.prefetch_options_data, candidates)

    # Pass 2 — the expensive part, run concurrently across a thread pool.
    # Two-tier: tier 1 is Alpaca+technical+news only (use_finnhub=False,
    # neutral earnings/analyst defaults) for every candidate — cheap, no
    # Finnhub rate-limit exposure. Finnhub's free tier (60 calls/min) can't
    # cover a ~1,600-ticker universe needing 2 calls each per scan (a
    # direct 16-way-parallel test against it got only 12/50 calls through,
    # rest 429'd) — so real earnings/analyst data is only fetched in tier 2
    # for the top-ranked candidates from tier 1's preliminary scoring.
    async def _analyze_one(ticker: str, price: float, use_finnhub: bool):
        try:
            result = await loop.run_in_executor(
                _ANALYZE_EXECUTOR, _analyze_ticker_sync, ticker, price, use_finnhub)
            return ticker, price, result, None
        except Exception as e:
            return ticker, price, None, e

    analyzed = await asyncio.gather(*[_analyze_one(t, p, False) for t, p in candidates])

    # Pass 3 — cheap, in-memory scoring/filtering over analyzed results.
    # Reused for both tiers: tier 1 uses this to rank candidates (with
    # earnings/analyst still at neutral defaults, so the earnings gate
    # is a no-op there); tier 2 re-runs it over the enriched top-N
    # results, where the earnings gate can now actually fire on real data.
    def _score_pass(analyzed_list):
        return _score_analyzed_results(analyzed_list, intraday_extremes_map, prev_close_map,
                                        candles, fade_streaks, first_seen_map)

    prelim = _score_pass(analyzed)

    # Tier 2 — spend Finnhub's rate-limited budget only on the strongest
    # candidates. Reuses tier 1's warm per-ticker caches (5-min options
    # cache, prefetched OHLCV/technical/news) so this second pass only adds
    # the incremental Finnhub network calls, not a full re-fetch.
    #
    # N and the timeout below are both sized against the scheduler's hard
    # 240s budget for the ENTIRE scan (see the asyncio.wait_for around
    # _analyze_sp500_options — a comment there documents this exact failure
    # mode already happening once: repeated timeouts silently zeroing out
    # recommendations for a whole morning). Tier 1 alone over the full
    # ~1,600-ticker universe has been measured at 120-190s with no Finnhub
    # calls in it at all, so tier 2 has only ~50-100s of real headroom.
    # finnhub_limiter cap is 50/min shared — N=30 needs up to 60 calls,
    # ~72s worst case if every single one queues for the full window,
    # comfortably inside that headroom. wait_for is a second, independent
    # safety net: if Finnhub is unusually slow this cycle, tier 2 gives up
    # on its own well before the 240s deadline and falls back to tier 1's
    # already-good (neutral-default) results, rather than risking the
    # whole scan (including tier 1's finished work) getting killed by the
    # outer timeout and returning zero recommendations.
    FINNHUB_TOP_N = 30
    top_tickers = sorted(prelim.values(), key=lambda r: r.score, reverse=True)[:FINNHUB_TOP_N]
    top_ticker_set = {r.ticker for r in top_tickers}
    enrich_candidates = [(t, p) for t, p in candidates if t in top_ticker_set]
    tier2_timed_out = False
    try:
        analyzed_enriched = await asyncio.wait_for(
            asyncio.gather(*[_analyze_one(t, p, True) for t, p in enrich_candidates]),
            timeout=100,
        )
        enriched = _score_pass(analyzed_enriched)
    except asyncio.TimeoutError:
        logger.warning("[SP500] Tier-2 Finnhub enrichment exceeded 100s — "
                        "keeping tier-1 (neutral-default) results for this cycle")
        tier2_timed_out = True
        enriched = {}

    # Merge: enriched (real earnings/analyst data) results replace their
    # tier-1 counterparts. A top-N ticker can also be correctly DROPPED
    # here if real data shows earnings ≤3 days away or the real score
    # falls below 0.55 — protection tier 1 could never apply, since it
    # only ever saw the neutral 999/0.0 defaults. Skipped entirely on a
    # tier-2 timeout — there the absence of a ticker from `enriched` means
    # "didn't get to it in time", not "real data says drop it", so tier 1's
    # result must stand instead of being deleted.
    final_map = dict(prelim)
    final_map.update(enriched)
    if not tier2_timed_out:
        for t in top_ticker_set - set(enriched.keys()):
            final_map.pop(t, None)
    recs.extend(final_map.values())

    # Sort by score descending, keep top 100
    recs.sort(key=lambda r: r.score, reverse=True)
    top_recs = recs[:100]

    # Liquidity filter — drop contracts too thin to trade reliably (see
    # MIN_OPEN_INTEREST). Checked here, not earlier, so only the ~100
    # candidates that already cleared scoring pay the extra Alpaca lookup.
    liquid_recs = []
    for rec in top_recs:
        oi = _check_open_interest(rec.ticker, rec.strike_price, rec.expiry_date, rec.action)
        if oi is None or oi >= MIN_OPEN_INTEREST:
            liquid_recs.append(rec)
        else:
            logger.debug(f"[Liquidity] Dropping {rec.ticker} — OI {oi} < {MIN_OPEN_INTEREST}")
    dropped = len(top_recs) - len(liquid_recs)
    if dropped:
        logger.info(f"[Liquidity] Dropped {dropped} thin contracts (OI < {MIN_OPEN_INTEREST})")
    top_recs = liquid_recs

    # Fetch news + fundamentals for top 20 only (Mac has no memory limits)
    for rec in top_recs[:20]:
        rec.news_headlines = _fetch_ticker_news(rec.ticker)
        rec.fundamentals   = _fetch_fundamentals(rec.ticker)
        age_days, pct_change = _compute_catalyst_freshness(rec.ticker, rec.news_headlines, rec.current_price)
        rec.catalyst_age_days = age_days if age_days is not None else -1
        rec.price_change_since_catalyst = pct_change if pct_change is not None else 0.0
        rec.thesis = _append_catalyst_narrative(rec.thesis, rec.ticker, rec.catalyst_age_days, rec.price_change_since_catalyst)
        rec.key_factors, rec.risks = _generate_key_factors_and_risks(rec)  # recompute — catalyst fields now set

    latest_options_recs = top_recs
    last_sp500_run = datetime.utcnow()
    _save_results()  # survive a Railway restart mid-day, same as pushed results already did
    _save_scan_history_pg()  # one row per rec — separate from the single-row latest_scan above

    logger.info(f"[SP500] Analysis complete: {len(recs)} signals, top 100 kept"
                + (f" ({len(gapped_tickers)} already gapped >{GAP_RISK_PCT*100:.0f}% but still analyzed)" if gapped_tickers else ""))

    # Save hourly snapshot — market hours only, reset each trading day
    global hourly_snapshots, _last_snapshot_hour, _last_snapshot_date
    now_et = datetime.now(_ET)
    today_str = now_et.strftime("%Y-%m-%d")
    current_hour = now_et.hour
    is_weekday = now_et.weekday() < 5
    market_open_et  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close_et = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
    in_market_hours = is_weekday and market_open_et <= now_et < market_close_et

    if in_market_hours and latest_options_recs:
        # Clear snapshots at the start of a new trading day
        if _last_snapshot_date != today_str:
            hourly_snapshots = []
            _last_snapshot_hour = None
            _last_snapshot_date = today_str

        if _last_snapshot_hour != current_hour:
            snapshot = {
                "timestamp": now_et.isoformat(),
                "hour_label": now_et.strftime("%-I:%M %p"),
                "recommendations": [asdict(r) for r in latest_options_recs[:10]],
            }
            hourly_snapshots.insert(0, snapshot)   # newest first
            hourly_snapshots = hourly_snapshots[:8] # keep max 8 hours (full trading day)
            _last_snapshot_hour = current_hour
            logger.info("[SP500] Hourly snapshot saved for %s", snapshot["hour_label"])

    return latest_options_recs


async def _refresh_final_tickers() -> List[OptionsRecommendation]:
    """Fast re-score of just the current final signals (~30 tickers, not
    the full ~1,660-ticker universe), run every REFRESH_INTERVAL seconds
    during the cooldown between full scans (see _sp500_scheduler_loop) so
    displayed data stays close to real-time instead of only updating once
    per full scan. Mirrors _analyze_sp500_options's per-ticker pipeline
    (price, OHLCV, options, Finnhub, scoring) exactly — via the same
    _score_analyzed_results function — just scoped to a small ticker set,
    so it completes in a few seconds instead of minutes.

    Score/action CAN change here: a signal can flip CALL<->PUT or drop
    below the 0.55 threshold between full scans, and the refreshed list
    entirely replaces latest_options_recs (not merged with it) — same
    "full re-score" semantics as a real scan, just scoped down. This
    backend doesn't execute trades of any kind, so a flip here is a
    display-only concern, not a risk one.

    Does NOT call _save_scan_history_pg() — that inserts one row per rec
    per call, and running it every ~15-20s instead of every ~3.5 min would
    multiply scan_history's write volume ~10x and blur its "one row-set
    per scan cycle" semantics that other tooling (e.g. the local
    prediction tracker) relies on. _save_results() (a single-row upsert)
    still runs, so a mid-cooldown restart doesn't lose the latest refresh.
    Also does not touch last_sp500_run — that timestamp marks full-scan
    completions specifically; freshness from this loop shows up via
    latest_options_recs's own content instead."""
    global latest_options_recs

    if not latest_options_recs:
        return latest_options_recs

    tickers = [r.ticker for r in latest_options_recs]
    loop = asyncio.get_event_loop()

    price_map = await loop.run_in_executor(None, _fetch_prices_batch, tickers)
    prev_close_map = await loop.run_in_executor(None, _fetch_prev_closes_batch, tickers)
    intraday_extremes_map = await loop.run_in_executor(None, _fetch_intraday_extremes_batch, tickers)
    first_seen_map = await loop.run_in_executor(None, _fetch_signal_first_seen)
    prefetch_list = tickers if 'SPY' in tickers else tickers + ['SPY']
    await loop.run_in_executor(None, stock_agent.prefetch_ohlcv, prefetch_list)
    await loop.run_in_executor(None, _prefetch_hourly_ohlcv, tickers)

    candles: Dict[str, dict] = {}
    fade_streaks: Dict[str, tuple] = {}
    candidates: List[Tuple[str, float]] = []
    for ticker in tickers:
        if ticker not in stock_agent._ohlcv_cache:
            continue
        candles[ticker] = _detect_candle_pattern(_hourly_ohlcv_cache.get(ticker))
        fade_streaks[ticker] = (
            _detect_fade_streak(stock_agent._ohlcv_cache[ticker], is_bearish=False),
            _detect_fade_streak(stock_agent._ohlcv_cache[ticker], is_bearish=True),
        )
        price = price_map.get(ticker) or _fallback_price(ticker)
        if not price or price <= 0:
            continue
        today_high, today_low = intraday_extremes_map.get(ticker, (None, None))
        if not _is_price_plausible(price, today_low, today_high):
            logger.warning("[Refresh] %s skipped — price $%.2f outside today's own range $%.2f-$%.2f (bad fetch)",
                            ticker, price, today_low or 0.0, today_high or 0.0)
            continue
        candidates.append((ticker, float(price)))

    if not candidates:
        return latest_options_recs

    await loop.run_in_executor(None, stock_agent.prefetch_options_data, candidates)

    async def _analyze_one(ticker: str, price: float):
        try:
            result = await loop.run_in_executor(
                _ANALYZE_EXECUTOR, _analyze_ticker_sync, ticker, price, True)
            return ticker, price, result, None
        except Exception as e:
            return ticker, price, None, e

    analyzed = await asyncio.gather(*[_analyze_one(t, p) for t, p in candidates])
    scored = _score_analyzed_results(analyzed, intraday_extremes_map, prev_close_map,
                                      candles, fade_streaks, first_seen_map)

    recs = sorted(scored.values(), key=lambda r: r.score, reverse=True)

    liquid_recs = []
    for rec in recs:
        oi = _check_open_interest(rec.ticker, rec.strike_price, rec.expiry_date, rec.action)
        if oi is None or oi >= MIN_OPEN_INTEREST:
            liquid_recs.append(rec)
        else:
            logger.debug(f"[Refresh] Dropping {rec.ticker} — OI {oi} < {MIN_OPEN_INTEREST}")
    recs = liquid_recs

    for rec in recs[:20]:
        rec.news_headlines = _fetch_ticker_news(rec.ticker)
        rec.fundamentals   = _fetch_fundamentals(rec.ticker)
        age_days, pct_change = _compute_catalyst_freshness(rec.ticker, rec.news_headlines, rec.current_price)
        rec.catalyst_age_days = age_days if age_days is not None else -1
        rec.price_change_since_catalyst = pct_change if pct_change is not None else 0.0
        rec.thesis = _append_catalyst_narrative(rec.thesis, rec.ticker, rec.catalyst_age_days, rec.price_change_since_catalyst)
        rec.key_factors, rec.risks = _generate_key_factors_and_risks(rec)

    latest_options_recs = recs
    _save_results()
    logger.info(f"[Refresh] Re-scored {len(candidates)}/{len(tickers)} final tickers — {len(recs)} still clear the bar")
    return recs


SP500_SCAN_INTERVAL = 60  # cooldown after each full scan finishes, not a
# fixed clock tick — the loop is sequential (scan, then cooldown, then scan
# again), so this never overlaps a running scan. Lowered from 2 min once
# the options-fetch batching fix (see prefetch_options_data) cut scan time
# from 7.5-8.5 min back down to ~2.5 min; real cadence is scan time + this
# value, not this value alone.

REFRESH_INTERVAL = 15  # during SP500_SCAN_INTERVAL's cooldown, re-score just
# the current final tickers this often (see _refresh_final_tickers) so
# displayed data stays close to real-time between full scans, not just
# updating once every ~3.5 min.


async def _push_options_update(recs: List[OptionsRecommendation], event: str) -> None:
    """Push a recommendations payload to all connected WebSocket clients —
    shared by the full scan and the fast refresh loop so both update
    subscribers the same way."""
    if not (options_ws_connections and recs):
        return
    payload = [asdict(r) for r in recs]
    dead = []
    for ws in list(options_ws_connections):
        try:
            await ws.send_json({
                "event": event,
                "timestamp": datetime.utcnow().isoformat(),
                "count": len(payload),
                "recommendations": payload,
            })
        except Exception:
            dead.append(ws)
    for ws in dead:
        options_ws_connections.remove(ws)


async def _sp500_scheduler_loop():
    """Background loop replacing local_runner.py — runs the full SP500 scan
    directly on Railway instead of relying on a push from the Mac. Mirrors
    local_runner's market-hours gating (9:25 AM-4:05 PM ET weekdays, first
    scan waits for 9:31 options open). Read-only — no trade execution of
    any kind happens from this backend, paper or real; it only produces
    signals."""
    await asyncio.sleep(30)  # let server come up healthy first
    first_scan_done = False

    while True:
        now_et = datetime.now(_ET)
        is_weekday = now_et.weekday() < 5
        session_start = now_et.replace(hour=9, minute=25, second=0, microsecond=0)
        session_end   = now_et.replace(hour=16, minute=5, second=0, microsecond=0)
        options_open  = now_et.replace(hour=9, minute=31, second=0, microsecond=0)

        if not is_weekday or now_et < session_start or now_et >= session_end:
            first_scan_done = False
            await asyncio.sleep(300)  # re-check every 5 min rather than sleeping for hours —
            continue                  # Railway runs 24/7 anyway, unlike the Mac's caffeinate setup

        if not first_scan_done:
            if now_et < options_open:
                await asyncio.sleep((options_open - now_et).total_seconds())
                continue
            first_scan_done = True

        try:
            # Wrapped in a timeout — without one, a single abnormally slow
            # cycle (observed in production: ~4 hours, likely driven by
            # repeated yfinance retries against a garbage ticker) blocks this
            # loop forever, since try/except only catches raised errors, not
            # a hang. The 90s budget this used to have assumed a ~30-60s
            # happy-path scan time, which stopped being true as the ticker
            # universe grew — confirmed in production on 2026-09-16: two
            # consecutive manual full scans over 1657 tickers took 158s and
            # 188s, meaning EVERY automatic cycle had been hitting the 90s
            # timeout and getting cancelled all morning (last_run stuck null,
            # zero signals shown) despite the scan itself working fine. 240s
            # leaves real headroom over the observed worst case while still
            # catching genuine multi-hour hangs.
            recs = await asyncio.wait_for(_analyze_sp500_options(), timeout=240)
            await _push_options_update(recs, "sp500_options_update")

        except asyncio.TimeoutError:
            logger.error("[SP500 Scheduler] Scan cycle exceeded 90s timeout — skipping to next cycle")
        except Exception as e:
            logger.error(f"[SP500 Scheduler] Error: {e}")

        # Cooldown before the next full scan — broken into short sub-cycles
        # that each re-score just the current final tickers (see
        # _refresh_final_tickers) so the displayed data keeps moving in
        # near-real-time through the whole cooldown, not just at the start.
        num_refreshes = max(1, SP500_SCAN_INTERVAL // REFRESH_INTERVAL)
        for _ in range(num_refreshes):
            await asyncio.sleep(REFRESH_INTERVAL)
            try:
                refreshed = await asyncio.wait_for(_refresh_final_tickers(), timeout=REFRESH_INTERVAL * 2)
                await _push_options_update(refreshed, "sp500_options_refresh")
            except asyncio.TimeoutError:
                logger.warning("[Refresh] Final-ticker re-score exceeded %ss — skipping this sub-cycle",
                                REFRESH_INTERVAL * 2)
            except Exception as e:
                logger.warning(f"[Refresh] Final-ticker re-score failed: {e}")


# ============================================================================
# LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — server starts immediately, everything else runs in background."""

    async def _init_all():
        global news_analyzer, technical_analyzer, options_analyzer
        global market_analyzer, strategy_selector, call_put_predictor
        global reasoning_generator, stock_agent, notification_manager

        logger.info("Initializing analyzers...")
        news_analyzer = NewsAnalyzer()
        technical_analyzer = TechnicalAnalyzer()
        options_analyzer = OptionsAnalyzer()
        market_analyzer = MarketAnalyzer()
        strategy_selector = StrategySelector()
        call_put_predictor = CallPutPredictor()
        reasoning_generator = ReasoningGenerator()
        stock_agent = MCPStockAgent()
        notification_manager = NotificationManager(
            slack_webhook=os.getenv("SLACK_WEBHOOK_URL"),
            email_config={
                "smtp_server": os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com"),
                "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
                "username": os.getenv("EMAIL_USER"),
                "password": os.getenv("EMAIL_PASSWORD"),
                "from_address": os.getenv("EMAIL_FROM", "alerts@trading-system.com")
            },
            discord_webhook=os.getenv("DISCORD_WEBHOOK_URL"),
            custom_webhook=os.getenv("CUSTOM_WEBHOOK_URL")
        )
        logger.info("✅ Analyzers ready")

        # Only run local SP500 scanner if not in push mode (Railway uses push-results endpoint)
        if not os.getenv("PUSH_MODE"):
            await _sp500_scheduler_loop()

    _load_results()
    sp500_task = asyncio.create_task(_init_all())
    asyncio.create_task(_eod_clear_loop())
    logger.info("System initializing in background — server ready")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    sp500_task.cancel()
    active_connections.clear()
    agent_connections.clear()
    options_ws_connections.clear()
    logger.info("Shutdown complete")


# ============================================================================
# APP
# ============================================================================

app = FastAPI(
    title="Options Trading Recommendation System with MCP Agent",
    description="Comprehensive options analysis with intelligent stock monitoring agent",
    version="3.3.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "3.2.0",
        "components": {
            "analyzers": all([news_analyzer, technical_analyzer, options_analyzer,
                              market_analyzer, strategy_selector, call_put_predictor,
                              reasoning_generator]),
            "agent": stock_agent is not None,
            "notifications": notification_manager is not None,
            "sp500_scheduler": last_sp500_run is not None,
        },
        "sp500": {
            "last_run": last_sp500_run.isoformat() if last_sp500_run else None,
            "recommendations_available": len(latest_options_recs),
        }
    }


@app.get("/api/v1/status")
async def system_status(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "system_status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "analyzers": {
            "news_analyzer": news_analyzer.__class__.__name__ if news_analyzer else "uninitialized",
            "technical_analyzer": technical_analyzer.__class__.__name__ if technical_analyzer else "uninitialized",
            "options_analyzer": options_analyzer.__class__.__name__ if options_analyzer else "uninitialized",
            "market_analyzer": market_analyzer.__class__.__name__ if market_analyzer else "uninitialized",
            "strategy_selector": strategy_selector.__class__.__name__ if strategy_selector else "uninitialized",
            "call_put_predictor": call_put_predictor.__class__.__name__ if call_put_predictor else "uninitialized",
            "reasoning_generator": reasoning_generator.__class__.__name__ if reasoning_generator else "uninitialized",
        },
        "agent_status": {
            "initialized": stock_agent is not None,
            "watchlist_size": len(stock_agent.watchlist) if stock_agent else 0,
            "total_analyses": sum(len(h) for h in stock_agent.analysis_history.values()) if stock_agent else 0,
            "notifications_sent": len(stock_agent.notifications_sent) if stock_agent else 0,
        },
        "sp500": {
            "last_run": last_sp500_run.isoformat() if last_sp500_run else None,
            "recommendations_available": len(latest_options_recs),
            # Reads today's cached dynamic universe without forcing a fresh
            # screener fetch inside a status endpoint — 0 just means it
            # hasn't run yet today, not that the universe is empty.
            "ticker_count": len(dynamic_tickers._cached_tickers),
        },
        "active_websocket_connections": len(active_connections) + len(agent_connections) + len(options_ws_connections),
    }


# ============================================================================
# SP500 OPTIONS RECOMMENDATIONS  ← NEW
# ============================================================================

@app.get("/api/v1/sp500/options-recommendations")
async def get_sp500_options_recommendations(
    limit: int = 20,
    action: Optional[str] = None,      # "CALL" or "PUT" filter
    min_score: float = 0.65,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get top options recommendations for all 500 tickers.

    Returns ticker, CALL/PUT action, strike price, expiry date, and score.
    Results are updated every 20 minutes by the background scheduler.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    recs = latest_options_recs
    if action:
        recs = [r for r in recs if r.action.upper() == action.upper()]
    recs = [r for r in recs if r.score >= min_score]
    recs = recs[:limit]

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "last_analysis": last_sp500_run.isoformat() if last_sp500_run else None,
        "total_available": len(latest_options_recs),
        "count": len(recs),
        # SP500_SCAN_INTERVAL alone (1 min) understates this — that's just
        # the sleep between cycles, not the scan itself, which takes
        # ~2.5 min over the current ~1660-ticker universe since the
        # options-fetch batching fix (see prefetch_options_data). ~3.5 min
        # total is a rough but honest estimate of real end-to-end cadence,
        # not a precise measurement.
        "next_refresh_in_minutes": SP500_SCAN_INTERVAL // 60 + 3,
        "recommendations": [asdict(r) for r in recs],
    }


@app.get("/api/v1/covered-calls/candidates")
async def get_covered_call_candidates(
    budget: float = COVERED_CALL_DEFAULT_BUDGET,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Covered-call candidates: from the latest scored CALL recs, only tickers
    cheap enough that 100 shares fits your budget, paired with a real liquid
    slightly-OTM call and its actual current premium.

    Analysis only — this does not buy shares or sell any option. You still
    place the trade yourself (buy 100 shares, then sell the shown contract).
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    loop = asyncio.get_event_loop()
    candidates = await loop.run_in_executor(None, _find_covered_call_candidates, budget)
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "budget": budget,
        "count": len(candidates),
        "candidates": candidates,
    }


@app.get("/api/v1/sp500/history")
async def get_sp500_history(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Return hourly top-10 snapshots from today (newest first, up to 8 hours)."""
    return {
        "count": len(hourly_snapshots),
        "snapshots": hourly_snapshots,
    }


@app.get("/api/v1/market-news")
async def get_market_news(
    limit: int = 10,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Top market-wide headlines for the app's scrolling news banner.
    Served straight from the same 30-min broad-news cache the sentiment
    scoring already uses — no extra Alpaca calls beyond what's already
    happening every scan cycle."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    loop = asyncio.get_event_loop()
    headlines = await loop.run_in_executor(None, stock_agent.get_top_headlines, limit)
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "count": len(headlines),
        "headlines": headlines,
    }


@app.get("/api/v1/market-pulse")
async def get_market_pulse_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """SPY day-change + VIX snapshot for the dashboard banner's fixed
    leading chip — same 30-min-cached SPY/VIX fetch the market_score
    composite weight already uses, reshaped for display."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    loop = asyncio.get_event_loop()
    pulse = await loop.run_in_executor(None, stock_agent.get_market_pulse)
    return {
        "timestamp": datetime.utcnow().isoformat(),
        **pulse,
    }


def _compute_consistent_tickers() -> List[Dict]:
    """Rank tickers by how many of today's hourly snapshots they appeared in
    — built from the same hourly_snapshots already collected for /history.
    A ticker that's been a top-10 signal across several independent scan
    cycles is a stronger, more validated signal than one that spiked once
    and vanished; this surfaces that pattern directly instead of requiring
    the user to manually flip through hours and compare."""
    if not hourly_snapshots:
        return []
    total_scans = len(hourly_snapshots)
    latest_tickers = {r['ticker'] for r in hourly_snapshots[0]['recommendations']}

    ticker_data: Dict[str, Dict] = {}
    for snap in reversed(hourly_snapshots):  # oldest first, so first_seen is correct
        for r in snap['recommendations']:
            t = r['ticker']
            if t not in ticker_data:
                ticker_data[t] = {'ticker': t, 'count': 0, 'first_seen_hour': snap['hour_label']}
            ticker_data[t]['count'] += 1
            ticker_data[t]['action'] = r['action']
            ticker_data[t]['latest_score'] = r['score']
            ticker_data[t]['latest_hour'] = snap['hour_label']

    results = [
        {
            'ticker': d['ticker'],
            'action': d['action'],
            'appearances': d['count'],
            'total_scans': total_scans,
            'first_seen_hour': d['first_seen_hour'],
            'still_active': d['ticker'] in latest_tickers,
            'latest_score': d['latest_score'],
        }
        for d in ticker_data.values()
    ]
    results.sort(key=lambda x: (-x['appearances'], -x['latest_score']))
    return results


@app.get("/api/v1/sp500/consistent-tickers")
async def get_consistent_tickers(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Tickers ranked by how consistently they've shown up as a top signal
    today, replacing the old hour-by-hour history browser with a direct
    answer to 'what's been reliably strong today' instead of raw snapshots
    the user had to cross-reference manually."""
    results = _compute_consistent_tickers()
    return {"count": len(results), "tickers": results}


@app.get("/api/v1/sp500/scan-history")
async def get_scan_history(
    ticker: Optional[str] = None,
    date: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Real per-cycle scan history — answers 'what did Arka score ticker X
    at time Y' for the last 2 trading days (older rows are pruned; see
    _save_scan_history_pg). Unlike /consistent-tickers and /history, this
    survives past the current trading day, since it's a real Postgres
    table rather than an in-memory list that resets daily.

    ticker: optional, case-insensitive exact match (e.g. "NOW").
    date: optional, YYYY-MM-DD (America/New_York), filters to that trading day.
    Both omitted returns everything still retained (up to 2 trading days).

    Row cap is 25,000 — comfortably above a single day's realistic maximum
    (~100 recs x ~195 cycles ~= 19,500) so an unfiltered date query never
    silently truncates in normal operation, while still bounding a
    pathological case. The response's `truncated` flag makes it explicit
    either way, since a query that appeared to return "everything" but was
    actually cut off (a real bug found 2026-08-31 with the old 2,000 cap
    — a query for a whole day's data silently returned only its most
    recent slice, with no signal that anything was missing) is worse than
    one that visibly tells you it hit the cap."""
    conn = _get_pg_conn()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database not available")

    where = []
    params: list = []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.strip().upper())
    if date:
        where.append("scan_time::date = %s")
        params.append(date)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    row_cap = 25000

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT ticker, action, score, current_price, scan_time FROM scan_history {clause} "
                f"ORDER BY scan_time DESC LIMIT %s",
                params + [row_cap],
            )
            rows = cur.fetchall()
    except Exception as e:
        logger.warning(f"[Postgres] scan_history query failed: {e}")
        raise HTTPException(status_code=500, detail="Query failed")

    return {
        "count": len(rows),
        "truncated": len(rows) == row_cap,
        "entries": [
            {"ticker": r[0], "action": r[1], "score": r[2], "current_price": r[3], "scan_time": r[4].isoformat()}
            for r in rows
        ],
    }


@app.post("/api/v1/sp500/push-results")
async def push_sp500_results(
    payload: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Receive pre-computed SP500 results pushed from local machine."""
    global latest_options_recs, last_sp500_run
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    recs_data = payload.get("recommendations", [])
    recs = []
    for r in recs_data:
        try:
            recs.append(OptionsRecommendation(
                ticker=r["ticker"],
                action=r["action"],
                strike_price=r["strike_price"],
                expiry_date=r["expiry_date"],
                score=r["score"],
                confidence=r.get("confidence", "HIGH"),
                current_price=r.get("current_price", 0.0),
                buy_signal=r.get("buy_signal", "BUY"),
                technical_score=r.get("technical_score", 0.0),
                sentiment_score=r.get("sentiment_score", 0.0),
                ml_score=r.get("ml_score", 0.0),
                timestamp=r.get("timestamp", datetime.utcnow().isoformat()),
                thesis=r.get("thesis", ""),
                days_to_expiry=r.get("days_to_expiry", 30),
                iv_rank=r.get("iv_rank", 50.0),
                volume_ratio=r.get("volume_ratio", 1.0),
                rs_vs_spy=r.get("rs_vs_spy", 0.0),
                days_to_earnings=r.get("days_to_earnings", 999),
                analyst_upside=r.get("analyst_upside", 0.0),
                long_term_score=r.get("long_term_score", 0.0),
                fundamentals=r.get("fundamentals", {}),
                news_headlines=r.get("news_headlines", []),
                catalyst_age_days=r.get("catalyst_age_days", -1),
                price_change_since_catalyst=r.get("price_change_since_catalyst", 0.0),
                intraday_move_pct=r.get("intraday_move_pct", 0.0),
            ))
        except Exception as e:
            logger.warning(f"Skipping bad rec: {e}")

    latest_options_recs = sorted(recs, key=lambda x: x.score, reverse=True)
    last_sp500_run = datetime.utcnow()
    _save_results()
    _save_scan_history_pg()
    logger.info(f"[push-results] Received {len(latest_options_recs)} recommendations from local runner")
    return {"received": len(latest_options_recs), "timestamp": last_sp500_run.isoformat()}


@app.post("/api/v1/sp500/trigger-analysis")
async def trigger_sp500_analysis(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Manually trigger an immediate SP500 analysis run (for testing)."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Run a quick sample of 20 tickers immediately (full run is in background)
    loop = asyncio.get_event_loop()
    all_tickers = await loop.run_in_executor(None, dynamic_tickers.get_dynamic_tickers)
    sample = all_tickers[:20]
    price_map = await loop.run_in_executor(None, _fetch_prices_batch, sample)
    await loop.run_in_executor(None, stock_agent.prefetch_ohlcv, sample)
    recs = []
    for ticker in sample:
        try:
            price = price_map.get(ticker) or _fallback_price(ticker)
            result = await stock_agent.analyze_ticker(ticker, float(price))
            is_bullish = result.technical_score >= 0.55
            is_bearish = result.technical_score <= 0.45
            if is_bullish or is_bearish:
                rec = _make_options_rec(ticker, result, float(price))
                if rec.score >= 0.50:
                    recs.append(asdict(rec))
        except Exception:
            continue

    return {
        "status": "triggered",
        "tickers_sampled": len(sample),
        "signals_found": len(recs),
        "recommendations": sorted(recs, key=lambda r: r["score"], reverse=True),
    }


@app.post("/api/v1/sp500/refresh-now")
async def refresh_sp500_now(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Manually run the REAL full scan (same _analyze_sp500_options the
    scheduler calls) and persist it — unlike trigger-analysis above, which
    only samples 20 tickers and doesn't update the live cache. For
    refreshing stale/bad data on demand outside the scheduler's market-hours
    window. Safe after-hours: trade execution inside _analyze_sp500_options
    already checks _is_market_open() itself before placing anything."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    recs = await _analyze_sp500_options()
    return {"status": "refreshed", "recommendations_available": len(recs)}


# ============================================================================
# PHASE 3A: ANALYSIS ENDPOINTS
# ============================================================================

def _validate_ticker_symbol(raw: str) -> str:
    """Strip + uppercase + shape-check a user-supplied ticker before it ever
    reaches a yfinance/Alpaca lookup. Production logs showed garbage like
    "NVDA " (trailing space, from iOS autocorrect) and "MCDANIEL" (a
    surname) reaching these calls and burning minutes on repeated failed
    retries — this rejects that shape of input immediately instead."""
    ticker = raw.strip().upper()
    if not ticker or not re.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?", ticker):
        raise HTTPException(status_code=400, detail=f"'{raw}' doesn't look like a valid ticker symbol")
    return ticker


@app.get("/api/v1/quote/{ticker}")
async def get_quote(
    ticker: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Real current price for a single ticker — lets the app auto-fill a
    price instead of the user having to already know it and drag a slider
    to guess it (the Analysis tab's old behavior)."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ticker = _validate_ticker_symbol(ticker)
    loop = asyncio.get_event_loop()
    price = await loop.run_in_executor(None, _fallback_price, ticker)
    if not price or price <= 0:
        raise HTTPException(status_code=404, detail=f"No price available for {ticker}")
    return {"ticker": ticker, "price": round(price, 2)}


@app.post("/api/v1/analyze")
async def analyze_stock(
    symbol: str,
    price: float = 0.0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Full real-data analysis for a single ticker — runs the same pipeline
    as the main SP500 scan (real technicals, real news, catalyst freshness,
    same-day reversal awareness, long-term score) instead of the fixed
    mock news/technical/options/market data this endpoint used before,
    which returned a plausible-looking but entirely fabricated result
    regardless of the actual ticker or price passed in."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    ticker = _validate_ticker_symbol(symbol)
    try:
        loop = asyncio.get_event_loop()

        # Prefer the real current price over whatever the client sent —
        # keeps this endpoint accurate even if the caller has a stale one.
        real_price = await loop.run_in_executor(None, _fallback_price, ticker)
        use_price = real_price if real_price and real_price > 0 else price
        if not use_price or use_price <= 0:
            raise HTTPException(status_code=404, detail=f"No price available for {ticker}")

        await loop.run_in_executor(None, stock_agent.prefetch_ohlcv, [ticker, "SPY"])
        # Own hourly prefetch — this endpoint used to rely entirely on the
        # shared _hourly_ohlcv_cache the periodic full-market scan fills,
        # which meant the candle read here silently went "No Data" whenever
        # that scan hadn't run recently (e.g. weekends, or right after a
        # deploy restarts the process and wipes it — confirmed in production:
        # AAPL/IREN both showed "No Data" here on a Sunday with an empty
        # cache, while the SP500 scan's own rows were fine). Single-ticker,
        # so the batching that _prefetch_hourly_ohlcv exists for doesn't
        # matter here.
        await loop.run_in_executor(None, _prefetch_hourly_ohlcv, [ticker])
        extremes = await loop.run_in_executor(None, _fetch_intraday_extremes_batch, [ticker])
        t_high, t_low = extremes.get(ticker, (None, None))
        prev_closes = await loop.run_in_executor(None, _fetch_prev_closes_batch, [ticker])

        result = await stock_agent.analyze_ticker(ticker, float(use_price))
        rec = _make_options_rec(ticker, result, float(use_price), today_high=t_high, today_low=t_low,
                                 prev_close=prev_closes.get(ticker))
        rec.news_headlines = await loop.run_in_executor(None, _fetch_ticker_news, ticker)
        age_days, pct_change = _compute_catalyst_freshness(ticker, rec.news_headlines, rec.current_price)
        rec.catalyst_age_days = age_days if age_days is not None else -1
        rec.price_change_since_catalyst = pct_change if pct_change is not None else 0.0
        rec.thesis = _append_catalyst_narrative(rec.thesis, rec.ticker, rec.catalyst_age_days, rec.price_change_since_catalyst)
        rec.fundamentals = await loop.run_in_executor(None, _fetch_fundamentals, ticker)
        rec.key_factors, rec.risks = _generate_key_factors_and_risks(rec)  # recompute — catalyst fields now set

        return {
            "symbol": ticker,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "recommendation": asdict(rec),
            "key_factors": rec.key_factors,
            "risks": rec.risks,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ============================================================================
# PORTFOLIO ENDPOINTS
# ============================================================================

@app.get("/api/v1/portfolio")
async def get_portfolio(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "user_id": "demo_user",
        "positions": [],
        "total_value": 0,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/v1/portfolio/position")
async def add_portfolio_position(
    symbol: str,
    quantity: int,
    entry_price: float,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "status": "position_added",
        "symbol": symbol,
        "quantity": quantity,
        "entry_price": entry_price,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# WATCHLIST ENDPOINTS
# ============================================================================

@app.get("/api/v1/watchlist")
async def get_watchlist(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "user_id": "demo_user",
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "count": 3,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/v1/watchlist/add/{symbol}")
async def add_to_watchlist(
    symbol: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "status": "added_to_watchlist",
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# MCP AGENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/agent/status")
async def agent_status(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return {
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "watchlist_size": len(stock_agent.watchlist),
        "total_analyses": sum(len(h) for h in stock_agent.analysis_history.values()),
        "notifications_sent": len(stock_agent.notifications_sent),
        "last_analysis": max(
            (analysis[-1].timestamp.isoformat() for analysis in stock_agent.analysis_history.values() if analysis),
            default=None
        )
    }


@app.post("/api/v1/agent/analyze")
async def agent_analyze(
    ticker: str,
    price: float,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        result = await stock_agent.analyze_ticker(ticker, price)
        rec = _make_options_rec(ticker, result, price)
        return {
            "ticker": result.ticker,
            "timestamp": result.timestamp.isoformat(),
            "price": result.price,
            "buy_score": result.buy_score,
            "buy_signal": result.buy_signal.value,
            "confidence": result.confidence.value,
            "risk_level": result.risk_level.value,
            "technical_score": result.technical_score,
            "sentiment_score": result.sentiment_score,
            "ml_score": result.ml_score,
            "strategy_score": result.strategy_score,
            "market_score": result.market_score,
            "thesis": result.thesis,
            "key_factors": result.key_factors,
            "risks": result.risks,
            "targets": {
                "entry_price": result.targets.entry_price,
                "stop_loss": result.targets.stop_loss,
                "profit_target_1": result.targets.profit_target_1,
                "profit_target_2": result.targets.profit_target_2
            },
            "options_recommendation": asdict(rec),
        }
    except Exception as e:
        logger.error(f"Error in agent analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/v1/agent/watchlist")
async def agent_get_watchlist(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return await stock_agent.get_watchlist()


@app.post("/api/v1/agent/watchlist/add")
async def agent_add_watchlist(
    ticker: str,
    buy_threshold: float = 0.70,
    max_position_size: float = 1000.0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return await stock_agent.add_to_watchlist(ticker, buy_threshold, max_position_size)


@app.get("/api/v1/agent/opportunities")
async def agent_get_opportunities(
    min_score: float = 0.75,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return await stock_agent.get_trending_opportunities(min_score)


@app.post("/api/v1/agent/notify")
async def agent_send_notification(
    ticker: str,
    channels: List[str] = ["email"],
    recipients: List[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return await stock_agent.send_notification(ticker, channels, recipients)


@app.get("/api/v1/agent/history/{ticker}")
async def agent_get_history(
    ticker: str,
    days: int = 30,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return await stock_agent.get_analysis_history(ticker, days)


@app.get("/api/v1/agent/performance")
async def agent_performance(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return {
        "watchlist_size": len(stock_agent.watchlist),
        "total_analyses": sum(len(h) for h in stock_agent.analysis_history.values()),
        "notifications_sent": len(stock_agent.notifications_sent),
        "buy_signals_sent": sum(
            1 for notif in stock_agent.notifications_sent
            if "BUY" in notif.get('analysis', {}).get('buy_signal', '')
        ),
        "avg_buy_score": (
            sum(
                sum(analysis.buy_score for analysis in histories)
                for histories in stock_agent.analysis_history.values()
            ) / sum(len(h) for h in stock_agent.analysis_history.values())
            if sum(len(h) for h in stock_agent.analysis_history.values()) > 0
            else 0.5
        )
    }


# ============================================================================
# STOCK SIGNALS ENDPOINT (read-only — no trading happens from this backend)
# ============================================================================

@app.get("/api/v1/stock-trading/signals")
async def get_stock_signals(
    min_score: float = 0.0,
    limit: int = 20,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Long-term-ranked bullish stock signals (weeks-to-months horizon) from
    the same scanned pool as the options recs, but sorted by long_term_score
    (fundamentals/analyst-upside/trend weighted) instead of the short-term,
    options-focused score — see _compute_long_term_score. min_score is
    checked against long_term_score here, not the options score."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    recs = [r for r in latest_options_recs
            if r.action == "CALL" and r.long_term_score >= min_score]
    recs = sorted(recs, key=lambda r: r.long_term_score, reverse=True)[:limit]
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "last_scan": last_sp500_run.isoformat() if last_sp500_run else None,
        "count": len(recs),
        "signals": [asdict(r) for r in recs],
    }


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@app.websocket("/ws/analyze/{symbol}")
async def websocket_analyze(websocket: WebSocket, symbol: str):
    await websocket.accept()
    active_connections[symbol] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Analysis for {symbol}: {data}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        active_connections.pop(symbol, None)


@app.websocket("/ws/agent/stream")
async def websocket_agent_stream(websocket: WebSocket):
    await websocket.accept()
    agent_connections.append(websocket)
    try:
        while True:
            if stock_agent and stock_agent.watchlist:
                results = await stock_agent.analyze_watchlist()
                for result in results:
                    await websocket.send_json({
                        "ticker": result.ticker,
                        "price": result.price,
                        "buy_score": result.buy_score,
                        "buy_signal": result.buy_signal.value,
                        "confidence": result.confidence.value,
                        "timestamp": result.timestamp.isoformat()
                    })
            await asyncio.sleep(30)
    except Exception as e:
        logger.error(f"WebSocket agent error: {str(e)}")
    finally:
        if websocket in agent_connections:
            agent_connections.remove(websocket)


@app.websocket("/ws/sp500/options")
async def websocket_sp500_options(websocket: WebSocket):
    """
    Real-time WebSocket for SP500 options recommendations.

    Sends a snapshot immediately on connect, then pushes two kinds of
    updates during market hours: a full-scan update ("sp500_options_update")
    every ~3.5 min (see SP500_SCAN_INTERVAL), and a faster re-score update
    ("sp500_options_refresh") of just the current final tickers every
    REFRESH_INTERVAL seconds in between (see _refresh_final_tickers) — the
    same shape, distinguished only by the event name, so a client that
    doesn't care about the distinction can treat both identically. Each
    message has the structure:
      {
        "event": "sp500_options_update" | "sp500_options_refresh",
        "timestamp": "...",
        "count": N,
        "recommendations": [ { ticker, action, strike_price, expiry_date, score, ... }, ... ]
      }
    """
    await websocket.accept()
    options_ws_connections.append(websocket)
    logger.info(f"[WS] SP500 options client connected (total: {len(options_ws_connections)})")

    try:
        # Send current data immediately on connect
        if latest_options_recs:
            await websocket.send_json({
                "event": "sp500_options_snapshot",
                "timestamp": datetime.utcnow().isoformat(),
                "count": len(latest_options_recs),
                "recommendations": [asdict(r) for r in latest_options_recs],
            })
        else:
            await websocket.send_json({
                "event": "sp500_options_waiting",
                "message": "First analysis in progress, results will arrive within ~2 min",
                "timestamp": datetime.utcnow().isoformat(),
            })

        # Keep connection alive, send heartbeats
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"event": "heartbeat", "timestamp": datetime.utcnow().isoformat()})

    except Exception as e:
        logger.debug(f"[WS] SP500 options client disconnected: {e}")
    finally:
        if websocket in options_ws_connections:
            options_ws_connections.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


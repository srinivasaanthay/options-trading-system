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
import yfinance as yf
from fastapi import FastAPI, HTTPException, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, date
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
from paper_trading_service import PaperTradingService
from stock_trading_service import StockTradingService

logger = logging.getLogger(__name__)

# Paper trading — loaded from alpaca.env file (or env vars as fallback)
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
paper_trader: Optional[PaperTradingService] = None
stock_trader: Optional[StockTradingService] = None

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
# SP500 TICKERS - Real S&P 500 companies
# ============================================================================

SP500_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B', 'JPM', 'V',
    'UNH', 'XOM', 'JNJ', 'WMT', 'MA', 'PG', 'LLY', 'HD', 'CVX', 'MRK',
    'ABBV', 'PEP', 'KO', 'COST', 'AVGO', 'BAC', 'TMO', 'ACN', 'MCD', 'CSCO',
    'ABT', 'CRM', 'ADBE', 'DHR', 'LIN', 'NEE', 'TXN', 'PM', 'NKE', 'DIS',
    'VZ', 'ORCL', 'CMCSA', 'RTX', 'T', 'BMY', 'INTC', 'AMD', 'AMGN', 'HON',
    'UPS', 'QCOM', 'COP', 'SBUX', 'INTU', 'IBM', 'CAT', 'DE', 'GS', 'AXP',
    'BKNG', 'SPGI', 'BA', 'BLK', 'MS', 'GILD', 'C', 'LMT', 'MDT', 'ADP',
    'SYK', 'AMAT', 'MDLZ', 'ADI', 'PLD', 'TJX', 'ISRG', 'CI', 'REGN', 'VRTX',
    'MMC', 'ZTS', 'PANW', 'SLB', 'BSX', 'NOW', 'MO', 'LRCX', 'EOG', 'KLAC',
    'HCA', 'ITW', 'ETN', 'AON', 'APD', 'MAR', 'MCO', 'TGT', 'USB', 'WFC',
    'GE', 'PNC', 'SNPS', 'CDNS', 'FDX', 'DUK', 'SO', 'ICE', 'MU', 'CL',
    'FCX', 'CSX', 'NSC', 'EMR', 'HUM', 'CTAS', 'PYPL', 'WM', 'CME', 'EQIX',
    'MNST', 'ORLY', 'MCHP', 'WELL', 'PCAR', 'FTNT', 'MSI', 'APH', 'GD', 'ROP',
    'IDXX', 'EW', 'DXCM', 'ODFL', 'CPRT', 'ROST', 'AZO', 'PAYX', 'VRSK', 'NDAQ',
    'FAST', 'BIIB', 'CTVA', 'CEG', 'CCI', 'CARR', 'AMT', 'TT', 'GLW', 'DLTR',
    'ON', 'A', 'PWR', 'IQV', 'FANG', 'GEHC', 'KEYS', 'WAB', 'TROW', 'ELV',
    'MTD', 'LVS', 'CSGP', 'ACGL', 'ENPH', 'SEDG', 'ALGN', 'TSCO', 'POOL', 'ULTA',
    'NUE', 'CF', 'MOS', 'IP', 'PKG', 'AVY', 'SEE', 'SON', 'CCK', 'BALL',
    'LHX', 'TDG', 'TDY', 'HEI', 'HWM', 'SPR', 'WWD', 'AXON', 'MOOG', 'DRS',
    'LDOS', 'SAIC', 'BAH', 'CACI', 'MRNA', 'ILMN', 'IEX', 'PODD', 'HOLX', 'BAX',
    'RMD', 'STE', 'COO', 'NVCR', 'INSP', 'SWAV', 'NTRA', 'IRTC', 'TMDX', 'RXRX',
    'PCVX', 'ARWR', 'ALNY', 'BMRN', 'RARE', 'PTCT', 'FOLD', 'SRPT', 'IONS', 'BLUE',
    'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'USB', 'PNC', 'TFC', 'COF',
    'AXP', 'DFS', 'SYF', 'AIG', 'MET', 'PRU', 'AFL', 'ALL', 'CB', 'HIG',
    'LNC', 'UNM', 'GL', 'FNF', 'FAF', 'CINF', 'ERIE', 'WR', 'HCI', 'KMPR',
    'AMZN', 'EBAY', 'ETSY', 'W', 'CHWY', 'PTON', 'NFLX', 'ROKU', 'FUBO', 'PARA',
    'VIAC', 'FOX', 'FOXA', 'NYT', 'SSP', 'GCI', 'LEA', 'MHK', 'TPX', 'SNBR',
    'WSM', 'RH', 'TGT', 'KSS', 'M', 'JWN', 'DDS', 'BKE', 'CATO',
    'CROX', 'SKX', 'NKE', 'COLM', 'VFC', 'PVH', 'HBI', 'RL', 'UAA', 'GOOS',
    'GPS', 'ANF', 'AEO', 'URBN', 'CRI', 'BURL', 'FIVE', 'OLLI', 'BIG', 'BGFV',
    'CAL', 'RCII', 'PRTS', 'AAP', 'ORLY', 'AZO', 'GPC', 'LKQ', 'BWA', 'APTV',
    'LEA', 'MGA', 'ALV', 'DORM', 'THRM', 'MODG', 'F', 'GM', 'STLA', 'TM',
    'HMC', 'NSANY', 'VWAGY', 'BMWYY', 'DDAIF', 'TSLA', 'RIVN', 'LCID', 'FSR', 'NIO',
    'XPEV', 'LI', 'PDD', 'JD', 'BABA', 'BIDU', 'TCOM', 'IQ', 'VNET', 'CAN',
    'TSM', 'ASML', 'LRCX', 'AMAT', 'KLAC', 'TER', 'ONTO', 'COHU', 'ACLS', 'FORM',
    'IPGP', 'IIVI', 'IPAR', 'OLED', 'AEIS', 'AXTI', 'ENTG', 'MKSI', 'AZTA', 'UCTT',
    'CRUS', 'SLAB', 'ALGM', 'DIOD', 'VICR', 'IXYS', 'POWI', 'AEHR', 'MPWR', 'MTSI',
    'RMBS', 'SMTC', 'SWKS', 'QRVO', 'SIMO', 'NXPI', 'MXIM', 'ADI', 'TXN', 'MCHP',
    'BRKS', 'CCMP', 'CEVA', 'CMTL', 'CNXN', 'COHU', 'COPY', 'CREE', 'CY', 'DSPG',
    'EMKR', 'ERIC', 'ESIO', 'FARO', 'FORM', 'FN', 'GNSS', 'GRMN', 'HOLI', 'ICHR',
    'IDTI', 'IIVI', 'IMOS', 'INPHI', 'IPHI', 'ISSI', 'IXYS', 'JNPR', 'KTCC', 'LSCC',
    'LLTC', 'MACOM', 'MFIN', 'MRAM', 'MRVL', 'MTSC', 'MU', 'MXIM', 'NANO', 'NATI',
    'NOVT', 'NSR', 'NTGR', 'ONTO', 'OIIM', 'ORCL', 'PBYI', 'PDFS', 'PLAB', 'PLT',
    'PMCS', 'PSEM', 'PTEC', 'PVTL', 'QCOM', 'RDWR', 'RFMD', 'RMBS', 'RNST', 'RPXC',
    'RSYS', 'RTEC', 'SCON', 'SLAB', 'SMSC', 'SMTC', 'SNPS', 'SPIL', 'SPY', 'SSNI',
    'SSTI', 'SWIR', 'SYNA', 'SYMC', 'TQNT', 'TRMB', 'TTMI', 'UEIC', 'ULTI', 'UTSI',
    'VIAV', 'VICR', 'VRNT', 'VSAT', 'XLNX', 'XRAY', 'ZDGE', 'ZIGO',
]

# Deduplicate while preserving order
seen = set()
SP500_TICKERS = [t for t in SP500_TICKERS if not (t in seen or seen.add(t))]


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

    def __post_init__(self):
        if self.news_headlines is None:
            self.news_headlines = []
        if self.fundamentals is None:
            self.fundamentals = {}


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


MIN_OPEN_INTEREST = 1000  # below this, contracts are too thin to trade reliably (wide spreads, bad fills)

_liquidity_client = None  # lazy, cached Alpaca TradingClient — independent of paper_trader,
                           # which local_runner.py's process never initializes


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


def _make_options_rec(ticker: str, analysis_result, price: float,
                       today_high: float = None, today_low: float = None) -> OptionsRecommendation:
    """Build an OptionsRecommendation from an AnalysisResult using expert multi-factor scoring.
    today_high/today_low (optional — from _fetch_intraday_extremes_batch) let a same-day
    reversal dampen the score even though the technical component below is daily-bar-based
    and can't see it on its own."""
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
    if not is_bearish and today_high and today_high > 0 and price < today_high:
        intraday_move_pct = round((price - today_high) / today_high * 100, 2)
        if intraday_move_pct <= -1.5:
            score = round(max(0.0, score - min(0.15, abs(intraday_move_pct) * 0.03)), 4)
    elif is_bearish and today_low and today_low > 0 and price > today_low:
        intraday_move_pct = round((price - today_low) / today_low * 100, 2)
        if intraday_move_pct >= 1.5:
            score = round(max(0.0, score - min(0.15, intraday_move_pct * 0.03)), 4)

    confidence, buy_signal = _interpret_composite_score(score)
    long_term_score = _compute_long_term_score(tech, rs_score, fund, upside, is_bearish)

    strike = _strike_for_action(price, action)
    expiry = _next_monthly_expiry()
    expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
    days_to_expiry = (expiry_dt - datetime.utcnow()).days

    return OptionsRecommendation(
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
        thesis=analysis_result.thesis[:200] if analysis_result.thesis else "",
        days_to_expiry=days_to_expiry,
        iv_rank=round(getattr(analysis_result, 'iv_rank', 50.0), 1),
        volume_ratio=round(getattr(analysis_result, 'volume_ratio', 1.0), 2),
        rs_vs_spy=round(getattr(analysis_result, 'rs_vs_spy', 0.0), 2),
        days_to_earnings=getattr(analysis_result, 'days_to_earnings', 999),
        analyst_upside=round(getattr(analysis_result, 'analyst_upside', 0.0), 1),
        long_term_score=long_term_score,
        intraday_move_pct=intraday_move_pct,
    )


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


_SCAN_HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_history")


def _find_price_near_date(ticker: str, target_date) -> Optional[float]:
    """Look up ticker's scanned price on/soon after target_date from the local
    scan_history archive — used to measure how much of a move already
    happened before today's signal, not just whether the headline is old."""
    try:
        import json as _json
        for offset in range(3):  # target day, then up to 2 days later (weekends/holidays)
            day_dir = os.path.join(_SCAN_HISTORY_DIR, (target_date + timedelta(days=offset)).strftime("%Y-%m-%d"))
            if not os.path.isdir(day_dir):
                continue
            for fname in sorted(os.listdir(day_dir)):
                path = os.path.join(day_dir, fname)
                try:
                    with open(path) as f:
                        data = _json.load(f)
                except Exception:
                    continue
                for r in data.get("recommendations", []):
                    if r.get("ticker") == ticker and r.get("current_price"):
                        return float(r["current_price"])
        return None
    except Exception:
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
    """Fetch key fundamental metrics from yfinance for display in Before You Buy."""
    try:
        info = yf.Ticker(ticker).info
        def _f(key, default=None):
            v = info.get(key)
            return None if v is None or (isinstance(v, float) and (v != v)) else v

        return {
            "debt_to_equity":   _f("debtToEquity"),
            "current_ratio":    _f("currentRatio"),
            "total_cash":       _f("totalCash"),
            "free_cashflow":    _f("freeCashflow"),
            "operating_cashflow": _f("operatingCashflow"),
            "revenue_growth":   _f("revenueGrowth"),
            "earnings_growth":  _f("earningsGrowth"),
            "profit_margins":   _f("profitMargins"),
            "gross_margins":    _f("grossMargins"),
            "trailing_pe":      _f("trailingPE"),
            "forward_pe":       _f("forwardPE"),
            "price_to_book":    _f("priceToBook"),
            "return_on_equity": _f("returnOnEquity"),
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
            return _pg_conn
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
        payload = _json.dumps([asdict(r) for r in latest_options_recs])
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
        last_sp500_run = last_run.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
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
# be in flight at once. Kept modest (not e.g. 50+) because yfinance has no
# official rate limit and aggressive concurrency risks Yahoo throttling.
ANALYZE_CONCURRENCY = 8
_ANALYZE_EXECUTOR = ThreadPoolExecutor(max_workers=ANALYZE_CONCURRENCY, thread_name_prefix="analyze")


def _analyze_ticker_sync(ticker: str, price: float):
    """Thread-pool entry point — analyze_ticker has no internal awaits, so a
    fresh event loop per call is cheap and safe (no other loop touches this thread)."""
    return asyncio.run(stock_agent.analyze_ticker(ticker, price))


async def _analyze_sp500_options() -> List[OptionsRecommendation]:
    """Analyze top 500 liquid US stocks, return top options recommendations."""
    global latest_options_recs, last_sp500_run

    from dynamic_tickers import get_dynamic_tickers
    loop = asyncio.get_event_loop()
    tickers = await loop.run_in_executor(None, get_dynamic_tickers)
    if not tickers:
        tickers = SP500_TICKERS  # fallback to static list

    logger.info(f"[SP500] Starting full analysis of {len(tickers)} tickers...")

    # Fetch real prices + OHLCV for all tickers up front (one batch call each)
    loop = asyncio.get_event_loop()
    price_map = await loop.run_in_executor(None, _fetch_prices_batch, tickers)
    prev_close_map = await loop.run_in_executor(None, _fetch_prev_closes_batch, tickers)
    intraday_extremes_map = await loop.run_in_executor(None, _fetch_intraday_extremes_batch, tickers)
    # SPY must be cached too — rs_vs_spy (25% of the composite score) reads it
    # from _ohlcv_cache directly and silently defaults to 0.0 if it's missing,
    # which it always was since SPY isn't one of the 500 scanned tickers.
    prefetch_list = tickers if 'SPY' in tickers else tickers + ['SPY']
    await loop.run_in_executor(None, stock_agent.prefetch_ohlcv, prefetch_list)

    recs: List[OptionsRecommendation] = []
    gap_skipped = 0

    # Pass 1 — cheap, in-memory filtering only (no network calls), sequential.
    candidates: List[Tuple[str, float]] = []
    for ticker in tickers:
        # Skip tickers that have no real OHLCV data (delisted / bankrupt)
        if ticker not in stock_agent._ohlcv_cache:
            continue

        price = price_map.get(ticker) or _fallback_price(ticker)
        if not price or price <= 0:
            continue

        # Gap check — catches earnings/news moves the (unreliable, esp.
        # right around the event) earnings-date lookup below can miss.
        # COHR's -14% earnings-day drop on 2026-08-13 slipped through
        # with days_to_earnings misreported as 999; this doesn't depend
        # on knowing *why* the move happened, just that it already did.
        prev_close = prev_close_map.get(ticker)
        if prev_close and prev_close > 0:
            gap = abs(price - prev_close) / prev_close
            if gap > GAP_RISK_PCT:
                gap_skipped += 1
                logger.debug("[SP500] %s skipped — already gapped %.1f%% since last close",
                             ticker, gap * 100)
                continue

        candidates.append((ticker, float(price)))

    # Pass 2 — the expensive part, run concurrently across a thread pool.
    async def _analyze_one(ticker: str, price: float):
        try:
            result = await loop.run_in_executor(_ANALYZE_EXECUTOR, _analyze_ticker_sync, ticker, price)
            return ticker, price, result, None
        except Exception as e:
            return ticker, price, None, e

    analyzed = await asyncio.gather(*[_analyze_one(t, p) for t, p in candidates])

    # Pass 3 — cheap, in-memory scoring/filtering over the results, sequential.
    for idx, (ticker, price, result, err) in enumerate(analyzed, 1):
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
                rec = _make_options_rec(ticker, result, price, today_high=t_high, today_low=t_low)
                if rec.score >= 0.55:  # minimum signal strength
                    recs.append(rec)

            if idx % 100 == 0:
                logger.info(f"[SP500] Progress {idx}/{len(analyzed)}")

        except Exception as e:
            logger.debug(f"[SP500] {ticker} skipped: {e}")
            continue

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

    latest_options_recs = top_recs
    last_sp500_run = datetime.utcnow()
    _save_results()  # survive a Railway restart mid-day, same as pushed results already did

    logger.info(f"[SP500] Analysis complete: {len(recs)} signals, top 100 kept"
                + (f" ({gap_skipped} skipped — already gapped >{GAP_RISK_PCT*100:.0f}%)" if gap_skipped else ""))

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

    # Auto-execute paper trades only during optimal trading window (10:00–15:30 ET)
    if paper_trader and paper_trader.connected:
        if _is_market_open():
            rec_dicts = [asdict(r) for r in latest_options_recs]
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, paper_trader.execute_signals, rec_dicts)
            logger.info("[SP500] Paper trades executed during market hours")
        else:
            now_et = datetime.now(_ET)
            logger.info("[SP500] Market closed (%s ET) — skipping trade execution",
                        now_et.strftime("%H:%M %Z"))

    return latest_options_recs


SP500_SCAN_INTERVAL = 2 * 60  # matches local_runner.py's cadence


async def _sp500_scheduler_loop():
    """Background loop replacing local_runner.py — runs the full SP500 scan
    directly on Railway instead of relying on a push from the Mac. Mirrors
    local_runner's market-hours gating (9:25 AM-4:05 PM ET weekdays, first
    scan waits for 9:31 options open) and the stale-position cleanup +
    stock-trade execution it used to trigger via HTTP self-calls — done as
    direct in-process calls here since this now runs in the same process.
    _analyze_sp500_options() already executes paper (options) trades
    internally; stock trading does not, so it's triggered explicitly below."""
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
            if paper_trader and paper_trader.connected:
                try:
                    loop = asyncio.get_event_loop()
                    all_positions = await loop.run_in_executor(None, paper_trader.client.get_all_positions)
                    tracked = {t.option_symbol for t in paper_trader.trade_history if t.option_symbol}
                    for p in all_positions:
                        if p.symbol not in tracked:
                            await loop.run_in_executor(None, paper_trader.client.close_position, p.symbol)
                            logger.info("[Scheduler] Closed stale position %s", p.symbol)
                except Exception as e:
                    logger.warning(f"[Scheduler] close-stale failed: {e}")
            first_scan_done = True

        try:
            recs = await _analyze_sp500_options()  # also executes paper trades internally

            # Push to all connected WebSocket clients
            if options_ws_connections and recs:
                payload = [asdict(r) for r in recs]
                dead = []
                for ws in list(options_ws_connections):
                    try:
                        await ws.send_json({
                            "event": "sp500_options_update",
                            "timestamp": datetime.utcnow().isoformat(),
                            "count": len(payload),
                            "recommendations": payload,
                        })
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    options_ws_connections.remove(ws)

            # Stock trading — not handled inside _analyze_sp500_options, so
            # trigger it explicitly the same way local_runner.py used to.
            if stock_trader and stock_trader.connected and _is_market_open() and recs:
                try:
                    loop = asyncio.get_event_loop()
                    rec_dicts = [asdict(r) for r in recs]
                    results = await loop.run_in_executor(None, stock_trader.execute_signals, rec_dicts)
                    if results:
                        logger.info(f"[Scheduler] Stock trades executed: {len(results)}")
                except Exception as e:
                    logger.warning(f"[Scheduler] stock trade execution failed: {e}")

        except Exception as e:
            logger.error(f"[SP500 Scheduler] Error: {e}")

        await asyncio.sleep(SP500_SCAN_INTERVAL)


# ============================================================================
# LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — server starts immediately, everything else runs in background."""

    async def _init_all():
        global news_analyzer, technical_analyzer, options_analyzer
        global market_analyzer, strategy_selector, call_put_predictor
        global reasoning_generator, stock_agent, notification_manager, paper_trader, stock_trader

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

        if _ALPACA_KEY and _ALPACA_SECRET:
            paper_trader = PaperTradingService(_ALPACA_KEY, _ALPACA_SECRET)
            loop = asyncio.get_event_loop()
            ok = await loop.run_in_executor(None, paper_trader.connect)
            logger.info("✅ Paper trader %s", "connected" if ok else "FAILED")

            _stock_dry_run = os.getenv("STOCK_ORDERS_DISABLED", "false").lower() == "true"
            stock_trader = StockTradingService(_ALPACA_KEY, _ALPACA_SECRET, dry_run=_stock_dry_run)
            ok2 = await loop.run_in_executor(None, stock_trader.connect)
            logger.info("✅ Stock trader %s (dry_run=%s)", "connected" if ok2 else "FAILED", _stock_dry_run)

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
            "ticker_count": len(SP500_TICKERS),
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
        "next_refresh_in_minutes": 20,
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
    sample = SP500_TICKERS[:20]
    loop = asyncio.get_event_loop()
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


# ============================================================================
# PHASE 3A: ANALYSIS ENDPOINTS
# ============================================================================

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
    loop = asyncio.get_event_loop()
    price = await loop.run_in_executor(None, _fallback_price, ticker.upper())
    if not price or price <= 0:
        raise HTTPException(status_code=404, detail=f"No price available for {ticker.upper()}")
    return {"ticker": ticker.upper(), "price": round(price, 2)}


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

    ticker = symbol.upper()
    try:
        loop = asyncio.get_event_loop()

        # Prefer the real current price over whatever the client sent —
        # keeps this endpoint accurate even if the caller has a stale one.
        real_price = await loop.run_in_executor(None, _fallback_price, ticker)
        use_price = real_price if real_price and real_price > 0 else price
        if not use_price or use_price <= 0:
            raise HTTPException(status_code=404, detail=f"No price available for {ticker}")

        await loop.run_in_executor(None, stock_agent.prefetch_ohlcv, [ticker, "SPY"])
        extremes = await loop.run_in_executor(None, _fetch_intraday_extremes_batch, [ticker])
        t_high, t_low = extremes.get(ticker, (None, None))

        result = await stock_agent.analyze_ticker(ticker, float(use_price))
        rec = _make_options_rec(ticker, result, float(use_price), today_high=t_high, today_low=t_low)
        rec.news_headlines = await loop.run_in_executor(None, _fetch_ticker_news, ticker)
        age_days, pct_change = _compute_catalyst_freshness(ticker, rec.news_headlines, rec.current_price)
        rec.catalyst_age_days = age_days if age_days is not None else -1
        rec.price_change_since_catalyst = pct_change if pct_change is not None else 0.0
        rec.fundamentals = await loop.run_in_executor(None, _fetch_fundamentals, ticker)

        return {
            "symbol": ticker,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "recommendation": asdict(rec),
            "key_factors": result.key_factors,
            "risks": result.risks,
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
# PAPER TRADING ENDPOINTS
# ============================================================================

def _require_paper_trader(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not paper_trader:
        raise HTTPException(
            status_code=503,
            detail="Paper trading not initialised. Set ALPACA_API_KEY + ALPACA_API_SECRET env vars and restart."
        )
    if not paper_trader.connected:
        raise HTTPException(status_code=503, detail="Paper trader is not connected to Alpaca")
    return paper_trader


@app.get("/api/v1/paper-trading/portfolio")
async def get_paper_portfolio(pt: PaperTradingService = Depends(_require_paper_trader)):
    """Current paper trading portfolio: account balance, open positions, P&L."""
    loop = asyncio.get_event_loop()
    snapshot = await loop.run_in_executor(None, pt.get_portfolio_snapshot)
    positions = await loop.run_in_executor(None, pt.get_positions)
    return {
        "portfolio": asdict(snapshot),
        "positions": positions,
    }


@app.get("/api/v1/paper-trading/trades")
async def get_paper_trades(pt: PaperTradingService = Depends(_require_paper_trader)):
    """Full trade history — open and closed positions."""
    return {
        "trades": pt.get_trade_history(),
        "total": len(pt.trade_history),
    }


@app.get("/api/v1/paper-trading/performance")
async def get_paper_performance(pt: PaperTradingService = Depends(_require_paper_trader)):
    """Performance summary: win rate, P&L, return vs $1000 start."""
    loop = asyncio.get_event_loop()
    snapshot = await loop.run_in_executor(None, pt.get_portfolio_snapshot)
    realized = await loop.run_in_executor(None, pt.get_realized_stats)
    closed = realized["closed_trades"]

    # Break down by option type (reconstructed from Alpaca's own order history,
    # not pt.trade_history — that resets on every process restart)
    long_trades  = [t for t in closed if t["type"] == "call"]
    short_trades = [t for t in closed if t["type"] == "put"]

    def stats(trades):
        if not trades:
            return {"count": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl": 0}
        wins = [t for t in trades if t["pnl"] > 0]
        return {
            "count":     len(trades),
            "wins":      len(wins),
            "losses":    len(trades) - len(wins),
            "win_rate":  round(len(wins) / len(trades) * 100, 1),
            "total_pnl": round(sum(t["pnl"] for t in trades), 2),
            "avg_pnl":   round(sum(t["pnl"] for t in trades) / len(trades), 2),
        }

    return {
        "summary":      asdict(snapshot),
        "call_signals": stats(long_trades),
        "put_signals":  stats(short_trades),
        "orders":       await asyncio.get_event_loop().run_in_executor(None, pt.get_recent_orders, 10),
    }


@app.post("/api/v1/paper-trading/execute-now")
async def execute_paper_trades_now(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    pt: PaperTradingService = Depends(_require_paper_trader)
):
    """Manually trigger paper trades from the latest SP500 recommendations."""
    if not _is_market_open():
        now_et = datetime.now(_ET)
        raise HTTPException(
            status_code=400,
            detail=f"Market is closed ({now_et.strftime('%H:%M %Z')}). Trading only allowed 9:30–16:00 ET Mon–Fri."
        )
    if not latest_options_recs:
        raise HTTPException(status_code=404, detail="No SP500 recommendations available yet")
    rec_dicts = [asdict(r) for r in latest_options_recs]
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, pt.execute_signals, rec_dicts)
    return {"executed": len(results), "trades": results}


@app.post("/api/v1/paper-trading/close-all")
async def close_all_paper_positions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    pt: PaperTradingService = Depends(_require_paper_trader)
):
    """Close all open positions immediately — closes options individually since Alpaca bulk-close skips them."""
    try:
        loop = asyncio.get_event_loop()
        closed = await loop.run_in_executor(None, pt.close_all_open_positions)
        return {"status": "all positions closed", "closed": closed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/paper-trading/close-stale")
async def close_stale_positions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    pt: PaperTradingService = Depends(_require_paper_trader)
):
    """Close positions held from a previous session (no entry in current trade_history)."""
    try:
        loop = asyncio.get_event_loop()
        all_positions = await loop.run_in_executor(None, pt.client.get_all_positions)
        tracked = {t.option_symbol for t in pt.trade_history if t.option_symbol}
        closed, skipped = [], []
        for p in all_positions:
            if p.symbol not in tracked:
                try:
                    await loop.run_in_executor(None, pt.client.close_position, p.symbol)
                    closed.append(p.symbol)
                    logger.info("[PaperTrading] Closed stale position %s", p.symbol)
                except Exception as e:
                    skipped.append(p.symbol)
                    logger.error("[PaperTrading] Could not close stale %s: %s", p.symbol, e)
        return {"closed": len(closed), "symbols": closed, "skipped": skipped}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/paper-trading/close-violations")
async def close_violating_positions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    pt: PaperTradingService = Depends(_require_paper_trader)
):
    """Close only positions that violated current entry rules (pre-fix, chased, out-of-window)."""
    now_et = datetime.now(_ET)
    market_open_et  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close_et = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
    is_weekday = now_et.weekday() < 5
    if not (is_weekday and market_open_et <= now_et < market_close_et):
        raise HTTPException(
            status_code=400,
            detail=f"Market is closed ({now_et.strftime('%H:%M %Z')}). Can only close positions during market hours (9:30–16:00 ET Mon–Fri)."
        )
    loop = asyncio.get_event_loop()
    closed = await loop.run_in_executor(None, pt.close_rule_violating_positions)
    return {"closed": len(closed), "positions": closed}


# ============================================================================
# STOCK TRADING ENDPOINTS
# ============================================================================

def _require_stock_trader(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stock_trader:
        raise HTTPException(
            status_code=503,
            detail="Stock trading not initialised. Set ALPACA_API_KEY + ALPACA_API_SECRET env vars and restart."
        )
    if not stock_trader.connected:
        raise HTTPException(status_code=503, detail="Stock trader is not connected to Alpaca")
    return stock_trader


@app.get("/api/v1/stock-trading/portfolio")
async def get_stock_portfolio(st: StockTradingService = Depends(_require_stock_trader)):
    """Stock trading portfolio: account snapshot, open positions, P&L."""
    loop = asyncio.get_event_loop()
    snapshot = await loop.run_in_executor(None, st.get_portfolio_snapshot)
    positions = await loop.run_in_executor(None, st.get_positions)
    return {
        "portfolio": snapshot,
        "positions": positions,
    }


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


@app.post("/api/v1/stock-trading/execute-now")  # TEST ONLY — remove after testing
async def execute_stock_trades_now(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    st: StockTradingService = Depends(_require_stock_trader),
):
    """Execute stock trades from the latest CALL signals (market hours only).
    dry_run=True by default — set STOCK_ORDERS_ENABLED=true env var to place real orders."""
    if not _is_market_open():
        now_et = datetime.now(_ET)
        raise HTTPException(
            status_code=400,
            detail=f"Market is closed ({now_et.strftime('%H:%M %Z')}). Trading only allowed 9:30–16:00 ET Mon–Fri."
        )
    if not latest_options_recs:
        raise HTTPException(status_code=404, detail="No SP500 recommendations available yet")
    rec_dicts = [asdict(r) for r in latest_options_recs]
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, st.execute_signals, rec_dicts)
    return {"trades_executed": len(results), "trades": results, "dry_run": st.dry_run}


@app.post("/api/v1/stock-trading/close-all")
async def close_all_stock_positions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    st: StockTradingService = Depends(_require_stock_trader),
):
    """Close all open stock positions immediately."""
    try:
        loop = asyncio.get_event_loop()
        closed = await loop.run_in_executor(None, st.close_all)
        return {"status": "closed", "count": closed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

    Sends a snapshot immediately on connect, then pushes updates every 20 min.
    Each message has the structure:
      {
        "event": "sp500_options_update",
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
                "message": "First analysis in progress, results will arrive within 20 min",
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


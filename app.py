"""
Integrated FastAPI Application with MCP Stock Analysis Agent

Options Trading Recommendation System - Phase 3B with Agent Integration
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
from typing import List, Optional, Dict
import asyncio
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


def _make_options_rec(ticker: str, analysis_result, price: float) -> OptionsRecommendation:
    """Build an OptionsRecommendation from an AnalysisResult using expert multi-factor scoring."""
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

    # Normalise volume: 0.3× avg → 0.0,  1.0× avg → 0.5,  2.0× avg → 1.0
    vol_score = min(1.0, max(0.0, vol_ratio / 2.0))

    # Normalise RS: −5% vs SPY → 0.0,  0% → 0.5,  +5% → 1.0
    rs_score = min(1.0, max(0.0, (rs + 5.0) / 10.0))

    # IV factor: cheap options (IV rank < 30) get a 10% bonus; expensive (> 70) get 20% penalty
    # iv_rank == 0.0 means data unavailable — treat as neutral (50), not cheap
    effective_iv = iv_rank if iv_rank > 0.0 else 50.0
    if effective_iv < 30:
        iv_factor = 1.10
    elif effective_iv > 70:
        iv_factor = 0.80
    else:
        iv_factor = 1.0

    # ── Expert composite score ────────────────────────────────────────────────
    # Weights: technical=30%, sentiment=15%, RS vs SPY=25%, volume=15%, fundamentals=15%
    if is_bearish:
        raw = ((1.0 - tech)     * 0.30 +
               (1.0 - sent)     * 0.15 +
               (1.0 - rs_score) * 0.25 +
               vol_score        * 0.15 +
               (1.0 - fund)     * 0.15)
    else:
        raw = (tech     * 0.30 +
               sent     * 0.15 +
               rs_score * 0.25 +
               vol_score * 0.15 +
               fund      * 0.15)

    score = round(min(1.0, max(0.0, raw * iv_factor)), 4)

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
        confidence=analysis_result.confidence.value,
        current_price=price,
        buy_signal=analysis_result.buy_signal.value,
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
    )


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

# Hourly snapshots: list of {"timestamp": str, "hour_label": str, "recommendations": [...]}
# Only saved during market hours; cleared each new trading day.
hourly_snapshots: List[Dict] = []
_last_snapshot_hour: Optional[int] = None  # ET hour of last saved snapshot
_last_snapshot_date: Optional[str]  = None  # ET date of last saved snapshot (clears daily)


# ============================================================================
# SP500 SCHEDULER (background task)
# ============================================================================

def _fetch_prices_batch(tickers: List[str]) -> Dict[str, float]:
    """Batch-fetch latest closing prices via yfinance. Falls back to hash-derived price on failure."""
    prices: Dict[str, float] = {}
    try:
        data = yf.download(tickers, period="1d", progress=False, auto_adjust=True, threads=True)
        close = data["Close"] if "Close" in data.columns else data
        last_row = close.iloc[-1]
        for ticker in tickers:
            try:
                p = float(last_row[ticker])
                if p > 0 and not math.isnan(p):
                    prices[ticker] = round(p, 2)
            except Exception:
                pass
        logger.info(f"[yfinance] Fetched prices for {len(prices)}/{len(tickers)} tickers")
    except Exception as e:
        logger.warning(f"[yfinance] Batch fetch failed: {e}")
    return prices


def _fallback_price(ticker: str) -> float:
    """Deterministic fallback price when yfinance has no data for a ticker."""
    seed = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % 10000
    return round(50.0 + (seed % 450), 2)


async def _analyze_sp500_options() -> List[OptionsRecommendation]:
    """Analyze all SP500 tickers, return top options recommendations."""
    global latest_options_recs, last_sp500_run

    logger.info(f"[SP500] Starting full analysis of {len(SP500_TICKERS)} tickers...")

    # Fetch real prices + OHLCV for all tickers up front (one batch call each)
    loop = asyncio.get_event_loop()
    price_map = await loop.run_in_executor(None, _fetch_prices_batch, SP500_TICKERS)
    await loop.run_in_executor(None, stock_agent.prefetch_ohlcv, SP500_TICKERS)

    recs: List[OptionsRecommendation] = []

    for idx, ticker in enumerate(SP500_TICKERS, 1):
        try:
            # Skip tickers that have no real OHLCV data (delisted / bankrupt)
            if ticker not in stock_agent._ohlcv_cache:
                continue

            price = price_map.get(ticker) or _fallback_price(ticker)

            result = await stock_agent.analyze_ticker(ticker, float(price))

            # Skip if earnings are ≤3 days away — IV crush kills option buyers
            if result.days_to_earnings <= 3:
                logger.debug("[SP500] %s skipped — earnings in %d days",
                             ticker, result.days_to_earnings)
                continue

            # Include bullish (CALL, tech >= 0.55) and bearish (PUT, tech <= 0.45)
            is_bullish = result.technical_score >= 0.55
            is_bearish = result.technical_score <= 0.45
            if is_bullish or is_bearish:
                rec = _make_options_rec(ticker, result, float(price))
                if rec.score >= 0.55:  # minimum signal strength
                    recs.append(rec)

            if idx % 100 == 0:
                logger.info(f"[SP500] Progress {idx}/{len(SP500_TICKERS)}")

        except Exception as e:
            logger.debug(f"[SP500] {ticker} skipped: {e}")
            continue

    # Sort by score descending, keep top 50
    recs.sort(key=lambda r: r.score, reverse=True)
    latest_options_recs = recs[:50]
    last_sp500_run = datetime.utcnow()

    logger.info(f"[SP500] Analysis complete: {len(recs)} signals, top 50 kept")

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


async def _sp500_scheduler_loop():
    """Background loop: analyze SP500 every 20 minutes, push to WebSocket clients."""
    # Wait for server to come up healthy before first scan
    await asyncio.sleep(30)
    while True:
        try:
            recs = await _analyze_sp500_options()

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

        except Exception as e:
            logger.error(f"[SP500 Scheduler] Error: {e}")

        # Wait 20 minutes before next run
        await asyncio.sleep(20 * 60)


# ============================================================================
# LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — server starts immediately, everything else runs in background."""

    async def _init_all():
        global news_analyzer, technical_analyzer, options_analyzer
        global market_analyzer, strategy_selector, call_put_predictor
        global reasoning_generator, stock_agent, notification_manager, paper_trader

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

        await _sp500_scheduler_loop()

    sp500_task = asyncio.create_task(_init_all())
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
    version="3.2.0",
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


@app.get("/api/v1/sp500/history")
async def get_sp500_history(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Return hourly top-10 snapshots from today (newest first, up to 8 hours)."""
    return {
        "count": len(hourly_snapshots),
        "snapshots": hourly_snapshots,
    }


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

@app.post("/api/v1/analyze")
async def analyze_stock(
    symbol: str,
    price: float,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not all([news_analyzer, technical_analyzer, market_analyzer]):
        raise HTTPException(status_code=503, detail="Analyzers not initialized")

    try:
        news_data = {
            'overall_sentiment': 0.3,
            'strength': 0.7,
            'recency_score': 0.8,
            'trend': 'improving',
            'news_count': 5
        }
        technical_data = {
            'trend': 'uptrend',
            'momentum': 45,
            'strength': 0.75,
            'technical_score': 65,
            'support_resistance': {'support': price * 0.97, 'resistance': price * 1.03}
        }
        options_data = {
            'calls': {
                'recommendations': [
                    {'strike': price, 'suitability': {'option_score': 75}},
                    {'strike': price + 5, 'suitability': {'option_score': 70}}
                ],
                'avg_iv': 0.25
            },
            'puts': {
                'recommendations': [
                    {'strike': price, 'suitability': {'option_score': 55}},
                    {'strike': price - 5, 'suitability': {'option_score': 50}}
                ],
                'avg_iv': 0.25
            }
        }
        market_data = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium', 'vix': 18},
            'health_score': 70,
            'breadth': {'breadth_score': 0.75}
        }

        market_analysis = market_analyzer.analyze_market(market_data)
        strategy_rec = strategy_selector.recommend_strategy(market_analysis, options_data, price)
        ml_prediction = call_put_predictor.predict(
            news_data, technical_data, options_data, market_analysis, price
        )
        reasoning = reasoning_generator.generate_reasoning(
            symbol, news_data, technical_data, options_data, market_analysis,
            strategy_rec['recommendations'][0] if strategy_rec.get('recommendations') else {},
            ml_prediction, price
        )

        # Build options details
        action = ml_prediction.get('recommendation', 'neutral').upper()
        if action not in ('CALL', 'PUT'):
            action = 'CALL'
        strike = _strike_for_action(price, action)
        expiry = _next_monthly_expiry()

        return {
            "symbol": symbol,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "price": price,
            "recommendation": ml_prediction.get('recommendation'),
            "confidence": ml_prediction.get('confidence'),
            "strategy": strategy_rec.get('best_strategy'),
            "thesis": reasoning.get('main_thesis'),
            "supporting_analysis": reasoning.get('supporting_analysis'),
            "risk_reward": reasoning.get('risk_reward_analysis'),
            "key_catalysts": reasoning.get('key_catalysts'),
            "key_levels": reasoning.get('key_levels'),
            "market_regime": market_analysis.get('trend', {}).get('direction'),
            "options_recommendation": {
                "action": action,
                "strike_price": strike,
                "expiry_date": expiry,
                "score": ml_prediction.get('confidence', 0.5),
            }
        }

    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
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
    closed = [t for t in pt.trade_history if t.status == "closed" and t.pnl is not None]

    # Break down by direction
    long_trades  = [t for t in closed if t.direction == "LONG"]
    short_trades = [t for t in closed if t.direction == "SHORT"]

    def stats(trades):
        if not trades:
            return {"count": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl": 0}
        wins = [t for t in trades if (t.pnl or 0) > 0]
        return {
            "count":     len(trades),
            "wins":      len(wins),
            "losses":    len(trades) - len(wins),
            "win_rate":  round(len(wins) / len(trades) * 100, 1),
            "total_pnl": round(sum(t.pnl or 0 for t in trades), 2),
            "avg_pnl":   round(sum(t.pnl or 0 for t in trades) / len(trades), 2),
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
    """Close all open positions immediately (end-of-week cleanup)."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, pt.client.close_all_positions)
        return {"status": "all positions closed"}
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

"""
MCP Stock Analysis Agent

Analyzes stock tickers and sends buy signal notifications.
Integrates with existing analyzer framework.
"""

import asyncio
import json
import logging
import os
import threading
import time
from collections import deque
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from analyzer.news_analyzer import NewsAnalyzer
from analyzer.technical_analyzer import TechnicalAnalyzer
from analyzer.options_analyzer import OptionsAnalyzer
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.strategy_selector import StrategySelector
from analyzer.call_put_predictor import CallPutPredictor
from analyzer.reasoning_generator import ReasoningGenerator


logger = logging.getLogger(__name__)


class _RateLimiter:
    """Thread-safe sliding-window rate limiter — blocks the calling thread
    until a call is allowed, rather than firing and letting the API reject
    it. Needed because Finnhub's free-tier cap (60/min) applies per API key
    across ALL endpoints combined, and the scan's 16-way thread pool would
    otherwise burst far past that in the same second (confirmed directly:
    a 16-way parallel test against /stock/recommendation got only 12/50
    calls through, the rest 429'd). Capped at 50, not 60, to leave headroom
    for app.py's separate top-20 display-fundamentals calls sharing the
    same Finnhub key."""
    def __init__(self, max_calls: int, period_seconds: float):
        self._max_calls = max_calls
        self._period = period_seconds
        self._calls = deque()
        self._lock = threading.Lock()

    def acquire(self):
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] > self._period:
                    self._calls.popleft()
                if len(self._calls) < self._max_calls:
                    self._calls.append(now)
                    return
                wait = self._period - (now - self._calls[0])
            time.sleep(max(0.05, wait))


finnhub_limiter = _RateLimiter(max_calls=50, period_seconds=60.0)


class BuySignal(Enum):
    """Buy signal categories"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    ACCUMULATE = "ACCUMULATE"
    HOLD = "HOLD"
    AVOID = "AVOID"


class ConfidenceLevel(Enum):
    """Confidence levels"""
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


class RiskLevel(Enum):
    """Risk levels"""
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


@dataclass
class AnalysisComponent:
    """Individual component score"""
    name: str
    score: float
    weight: float
    description: str = ""


@dataclass
class PriceTargets:
    """Price targets from analysis"""
    entry_price: float
    stop_loss: float
    profit_target_1: float
    profit_target_2: float
    stop_loss_pct: float = 0.0
    target1_pct: float = 0.0
    target2_pct: float = 0.0


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    ticker: str
    timestamp: datetime
    price: float

    # Buy signal
    buy_score: float
    buy_signal: BuySignal
    confidence: ConfidenceLevel
    risk_level: RiskLevel

    # Components
    technical_score: float
    sentiment_score: float
    ml_score: float
    strategy_score: float
    market_score: float

    # Reasoning
    thesis: str
    key_factors: List[str]
    risks: List[str]

    # Price targets
    targets: PriceTargets

    # Metadata
    analysis_id: str = ""
    version: str = "1.0"

    # Expert analysis signals (added for enhanced scoring)
    iv_rank: float = 50.0           # 0-100: low = cheap options, high = expensive
    volume_ratio: float = 1.0       # current vol / 20d avg vol
    rs_vs_spy: float = 0.0          # 5d return relative to SPY (e.g. +2.0 = outperformed by 2%)
    days_to_earnings: int = 999     # days until next earnings announcement
    fundamental_score: float = 0.5  # 0-1 from analyst targets + short interest
    analyst_count: int = 0          # analysts covering this ticker — < 3 means
                                     # fundamental_score above is a neutral default,
                                     # not a real read (see _fetch_real_fundamental_data)
    analyst_upside: float = 0.0     # analyst consensus target vs current price (%)
    short_interest_pct: float = 0.0 # short interest as % of float
    rsi: float = 50.0               # 14-day RSI — was computed for scoring and discarded;
                                     # exposed so narrative text can say whether a move is
                                     # fresh (room to continue) or already stretched (>70/<30)
    avg_dollar_volume: float = 0.0  # 20d avg shares x price — absolute, cross-ticker
                                     # liquidity/"how fast does this normally move" measure,
                                     # unlike volume_ratio which is self-relative to the
                                     # ticker's own history and can't distinguish a genuinely
                                     # liquid stock from a thin one having a busy day


@dataclass
class WatchlistItem:
    """Watchlist item"""
    ticker: str
    added_date: datetime
    buy_threshold: float = 0.70
    max_position_size: float = 1000.0
    notes: str = ""

    # Analysis tracking
    last_analysis: Optional[AnalysisResult] = None
    last_buy_signal_sent: Optional[datetime] = None
    buy_signal_count: int = 0
    false_positives: int = 0


class MCPStockAgent:
    """
    MCP Stock Analysis Agent

    Analyzes stocks using 7 analyzers and determines buy signals.
    Manages watchlist and sends notifications.
    """

    # Analysis weights
    WEIGHTS = {
        "technical": 0.25,
        "sentiment": 0.20,
        "ml_prediction": 0.30,
        "strategy": 0.15,
        "market": 0.10
    }

    # Buy score thresholds
    BUY_THRESHOLDS = {
        BuySignal.STRONG_BUY: 0.85,
        BuySignal.BUY: 0.75,
        BuySignal.ACCUMULATE: 0.65,
        BuySignal.HOLD: 0.50,
    }

    # News sentiment keyword sets — shared by the broad market-wide fetch
    # and the per-ticker path, so both score headlines identically.
    # Strong, specific signals only — generic market words removed to avoid
    # inflating sentiment from broad "stocks higher today" headlines.
    _BULLISH_WORDS = {
        'beat', 'beats', 'upgrade', 'upgraded', 'outperform',
        'buy', 'bullish', 'breakthrough', 'milestone', 'record',
        'profit', 'profits', 'soars', 'soared', 'surges', 'surged', 'surge',
        'jumps', 'jumped', 'raises', 'raised', 'boosted', 'accelerates',
        'expansion', 'rallies', 'rallied',
    }
    _BEARISH_WORDS = {
        'miss', 'misses', 'missed', 'cut', 'cuts', 'downgrade', 'downgraded',
        'layoff', 'layoffs', 'loss', 'losses', 'weak', 'disappoints', 'disappointed',
        'warning', 'recall', 'investigation', 'fine', 'penalty',
        'drops', 'dropped', 'bearish', 'sell', 'reduces', 'reduced',
        'shrinks', 'slumps', 'slumped', 'slides', 'tumbles', 'tumbled',
        'probe', 'lawsuit', 'bankruptcy', 'decline', 'declines',
    }
    # General-market openers — articles starting with these are index/macro
    # news, not company news, and shouldn't affect per-ticker sentiment.
    _MARKET_OPENERS = {
        'stocks', 's&p', 'dow', 'nasdaq', 'market', 'wall', 'futures',
        'global', 'asian', 'european', 'fed', 'investors', 'treasury',
    }

    def __init__(self):
        """Initialize agent with all analyzers"""
        logger.info("Initializing MCP Stock Agent")

        # Initialize analyzers
        self.news_analyzer = NewsAnalyzer()
        self.technical_analyzer = TechnicalAnalyzer()
        self.options_analyzer = OptionsAnalyzer()
        self.market_analyzer = MarketAnalyzer()
        self.strategy_selector = StrategySelector()
        self.ml_predictor = CallPutPredictor()
        self.reasoning_generator = ReasoningGenerator()

        # State
        self.watchlist: Dict[str, WatchlistItem] = {}
        self.analysis_history: Dict[str, List[AnalysisResult]] = {}
        self.notifications_sent: List[Dict] = []

        # Real-data caches
        self._ohlcv_cache: Dict[str, pd.DataFrame] = {}
        self._alpaca_feed_cache = None  # cached SIP/IEX choice, see _get_alpaca_feed
        self._market_cache: Dict = {}
        self._market_cache_time: Optional[datetime] = None
        self._options_cache: Dict[str, Tuple[Dict, datetime]] = {}
        # Shared, lazily-built Alpaca clients for _fetch_real_options_data —
        # NOT per-call. Each Trading/OptionHistoricalDataClient constructs
        # its own requests.Session() (confirmed by reading the SDK source),
        # so building one per ticker meant every one of ~1,660 tickers paid
        # a cold TCP+TLS handshake instead of reusing a warm connection —
        # this alone stretched a scan that used to take ~150-190s out to
        # ~6 minutes, blowing the scheduler's 240s timeout every cycle.
        # app.py's _get_liquidity_client() already used this cached pattern;
        # this just brings _fetch_real_options_data in line with it.
        self._alpaca_trading_client = None
        self._alpaca_option_data_client = None
        self._broad_news_cache: Optional[Tuple[List[Dict], datetime]] = None
        self._earnings_cache: Dict[str, Tuple[int, datetime]] = {}    # ticker → (days_to_earn, fetched_at)
        self._fundamental_cache: Dict[str, Tuple[Dict, datetime]] = {} # ticker → (data, fetched_at)

        logger.info("MCP Stock Agent initialized successfully")

    async def analyze_ticker(
        self,
        ticker: str,
        price: float,
        use_finnhub: bool = True
    ) -> AnalysisResult:
        """
        Analyze a ticker and generate buy signal

        Args:
            ticker: Stock ticker symbol
            price: Current stock price
            use_finnhub: When False, skip the Finnhub-backed earnings-date
                and analyst-consensus calls entirely and use their neutral
                defaults (999 days / 0.0 upside / 0.5 fundamental_score) —
                the same values these calls already fall back to on
                failure. Exists so app.py's scan can do a cheap first pass
                over every candidate (Alpaca + technical + news only) and
                spend Finnhub's free-tier rate budget (60 calls/min) only
                on the top-ranked candidates in a second pass, rather than
                bursting ~3,000 calls at it for a ~1,600-ticker universe
                and having nearly all of them 429 (confirmed directly: a
                16-way parallel burst got only 12/50 calls through).

        Returns:
            AnalysisResult with comprehensive analysis
        """
        logger.info(f"Analyzing {ticker} at ${price}")

        try:
            # Prepare data for analyzers — all real yfinance-derived
            news_data      = self._fetch_real_news_data(ticker)
            technical_data = self._fetch_real_technical_data(ticker, price)
            options_data   = self._fetch_real_options_data(ticker, price)
            market_data    = self._fetch_real_market_data()
            if use_finnhub:
                fundamental    = self._fetch_real_fundamental_data(ticker, price)
                days_to_earn   = self._fetch_earnings_date(ticker)
            else:
                fundamental    = {'analyst_upside': 0.0, 'short_interest_pct': 0.0,
                                   'analyst_count': 0,    'fundamental_score': 0.5}
                days_to_earn   = 999

            # Run all analyzers
            # news_data and technical_data are pre-formatted simulation dicts;
            # pass them directly to the predictor rather than through analyzers
            # that expect live API data.
            news_sentiment = news_data
            technical_result = technical_data
            market_analysis = self.market_analyzer.analyze_market(market_data)
            strategy_rec = self.strategy_selector.recommend_strategy(
                market_analysis,
                options_data,
                price
            )
            ml_prediction = self.ml_predictor.predict(
                news_data,
                technical_data,
                options_data,
                market_analysis,
                price
            )

            # Calculate scores
            scores = self._calculate_scores(
                news_sentiment,
                technical_result,
                options_data,
                market_analysis,
                ml_prediction
            )

            # Determine buy signal
            buy_score = self._calculate_buy_score(scores)
            buy_signal, confidence = self._interpret_buy_signal(buy_score)
            risk_level = self._assess_risk(
                technical_result,
                market_analysis
            )

            # Generate reasoning
            reasoning = self.reasoning_generator.generate_reasoning(
                ticker,
                news_data,
                technical_data,
                options_data,
                market_analysis,
                strategy_rec.get('recommendations', [{}])[0],
                ml_prediction,
                price
            )

            # Extract price targets
            targets = PriceTargets(
                entry_price=price,
                stop_loss=price * 0.97,
                profit_target_1=price * 1.01,
                profit_target_2=price * 1.03,
                stop_loss_pct=-3.0,
                target1_pct=1.0,
                target2_pct=3.0
            )

            # Create result
            result = AnalysisResult(
                ticker=ticker,
                timestamp=datetime.utcnow(),
                price=price,
                buy_score=buy_score,
                buy_signal=buy_signal,
                confidence=confidence,
                risk_level=risk_level,
                technical_score=scores['technical'],
                sentiment_score=scores['sentiment'],
                ml_score=scores['ml_prediction'],
                strategy_score=scores['strategy'],
                market_score=scores['market'],
                thesis=reasoning.get('main_thesis', ''),
                key_factors=reasoning.get('supporting_analysis', []),
                risks=self._identify_risks(technical_result, market_analysis),
                targets=targets,
                analysis_id=self._generate_id(),
                # Expert analysis signals
                iv_rank=options_data.get('iv_rank', 50.0),
                volume_ratio=technical_data.get('volume_ratio', 1.0),
                rs_vs_spy=technical_data.get('rs_vs_spy', 0.0),
                days_to_earnings=days_to_earn,
                fundamental_score=fundamental.get('fundamental_score', 0.5),
                analyst_count=fundamental.get('analyst_count', 0),
                analyst_upside=fundamental.get('analyst_upside', 0.0),
                short_interest_pct=fundamental.get('short_interest_pct', 0.0),
                rsi=technical_data.get('rsi', 50.0),
                avg_dollar_volume=technical_data.get('avg_dollar_volume', 0.0),
            )

            # Store in history
            if ticker not in self.analysis_history:
                self.analysis_history[ticker] = []
            self.analysis_history[ticker].append(result)

            # Keep only last 100 analyses per ticker
            if len(self.analysis_history[ticker]) > 100:
                self.analysis_history[ticker] = self.analysis_history[ticker][-100:]

            logger.info(
                f"Analysis complete for {ticker}: "
                f"score={buy_score:.2f}, signal={buy_signal.value}"
            )

            return result

        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {str(e)}")
            raise

    async def add_to_watchlist(
        self,
        ticker: str,
        buy_threshold: float = 0.70,
        max_position_size: float = 1000.0,
        notes: str = ""
    ) -> Dict:
        """Add ticker to watchlist"""
        logger.info(f"Adding {ticker} to watchlist (threshold: {buy_threshold})")

        self.watchlist[ticker] = WatchlistItem(
            ticker=ticker,
            added_date=datetime.utcnow(),
            buy_threshold=buy_threshold,
            max_position_size=max_position_size,
            notes=notes
        )

        return {
            "status": "added",
            "ticker": ticker,
            "threshold": buy_threshold,
            "max_position_size": max_position_size
        }

    async def remove_from_watchlist(self, ticker: str) -> Dict:
        """Remove ticker from watchlist"""
        logger.info(f"Removing {ticker} from watchlist")

        if ticker in self.watchlist:
            del self.watchlist[ticker]
            return {"status": "removed", "ticker": ticker}

        return {"status": "not_found", "ticker": ticker}

    async def get_watchlist(self) -> List[Dict]:
        """Get current watchlist"""
        return [
            {
                "ticker": item.ticker,
                "added_date": item.added_date.isoformat(),
                "threshold": item.buy_threshold,
                "max_position_size": item.max_position_size,
                "last_analysis": (
                    item.last_analysis.timestamp.isoformat()
                    if item.last_analysis else None
                ),
                "last_signal": item.last_analysis.buy_signal.value if item.last_analysis else None,
                "buy_signal_count": item.buy_signal_count
            }
            for item in self.watchlist.values()
        ]

    async def analyze_watchlist(self) -> List[AnalysisResult]:
        """Analyze all tickers in watchlist"""
        logger.info(f"Analyzing watchlist ({len(self.watchlist)} tickers)")

        results = []
        for ticker, item in self.watchlist.items():
            try:
                # Use sample price for demonstration
                price = 100.0 + hash(ticker) % 100
                result = await self.analyze_ticker(ticker, price)
                results.append(result)

                # Update watchlist item
                item.last_analysis = result
                if result.buy_signal in [BuySignal.STRONG_BUY, BuySignal.BUY]:
                    item.buy_signal_count += 1
                    item.last_buy_signal_sent = datetime.utcnow()

            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {str(e)}")
                continue

        return results

    async def get_trending_opportunities(
        self,
        min_score: float = 0.75
    ) -> List[Dict]:
        """Get tickers with high buy scores"""
        opportunities = []

        for ticker, item in self.watchlist.items():
            if item.last_analysis and item.last_analysis.buy_score >= min_score:
                opportunities.append({
                    "ticker": ticker,
                    "score": item.last_analysis.buy_score,
                    "signal": item.last_analysis.buy_signal.value,
                    "confidence": item.last_analysis.confidence.value,
                    "price": item.last_analysis.price,
                    "timestamp": item.last_analysis.timestamp.isoformat()
                })

        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        return opportunities

    async def get_analysis_history(
        self,
        ticker: str,
        days: int = 30
    ) -> List[Dict]:
        """Get analysis history for ticker"""
        if ticker not in self.analysis_history:
            return []

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        return [
            {
                "date": analysis.timestamp.isoformat(),
                "price": analysis.price,
                "score": analysis.buy_score,
                "signal": analysis.buy_signal.value,
                "confidence": analysis.confidence.value,
                "risk": analysis.risk_level.value
            }
            for analysis in self.analysis_history[ticker]
            if analysis.timestamp >= cutoff_date
        ]

    async def send_notification(
        self,
        ticker: str,
        channels: List[str] = None,
        recipients: List[str] = None
    ) -> Dict:
        """Send notification for buy signal"""
        if ticker not in self.watchlist:
            return {"status": "error", "message": "Ticker not in watchlist"}

        item = self.watchlist[ticker]
        if not item.last_analysis:
            return {"status": "error", "message": "No analysis available"}

        notification = {
            "id": self._generate_id(),
            "ticker": ticker,
            "timestamp": datetime.utcnow().isoformat(),
            "channels": channels or ["email"],
            "recipients": recipients or [],
            "analysis": asdict(item.last_analysis)
        }

        self.notifications_sent.append(notification)
        logger.info(f"Notification sent for {ticker} via {channels}")

        return {
            "status": "sent",
            "notification_id": notification['id'],
            "ticker": ticker,
            "channels": channels
        }

    def _calculate_scores(
        self,
        news_sentiment,
        technical_result,
        options_data,
        market_analysis,
        ml_prediction
    ) -> Dict[str, float]:
        """Calculate individual component scores"""
        return {
            "technical": min(1.0, max(0.0, technical_result.get('technical_score', 0.5) / 100)),
            "sentiment": min(1.0, max(0.0, (news_sentiment.get('overall_sentiment', 0) + 1) / 2)),
            "ml_prediction": ml_prediction.get('confidence', 0.5),
            "strategy": min(1.0, max(0.0, options_data.get('calls', {}).get('avg_iv', 0.25) / 0.5)),
            "market": min(1.0, max(0.0, market_analysis.get('health_score', 50) / 100))
        }

    def _calculate_buy_score(self, scores: Dict[str, float]) -> float:
        """Calculate composite buy score"""
        score = (
            scores['technical'] * self.WEIGHTS['technical'] +
            scores['sentiment'] * self.WEIGHTS['sentiment'] +
            scores['ml_prediction'] * self.WEIGHTS['ml_prediction'] +
            scores['strategy'] * self.WEIGHTS['strategy'] +
            scores['market'] * self.WEIGHTS['market']
        )
        return min(1.0, max(0.0, score))

    def _interpret_buy_signal(
        self,
        score: float
    ) -> Tuple[BuySignal, ConfidenceLevel]:
        """Interpret buy score into signal and confidence"""

        if score >= 0.85:
            return BuySignal.STRONG_BUY, ConfidenceLevel.VERY_HIGH
        elif score >= 0.75:
            return BuySignal.BUY, ConfidenceLevel.HIGH
        elif score >= 0.65:
            return BuySignal.ACCUMULATE, ConfidenceLevel.MODERATE
        elif score >= 0.50:
            return BuySignal.HOLD, ConfidenceLevel.LOW
        else:
            return BuySignal.AVOID, ConfidenceLevel.VERY_LOW

    def _assess_risk(
        self,
        technical_result,
        market_analysis
    ) -> RiskLevel:
        """Assess overall risk level"""

        # Simple risk assessment
        if market_analysis.get('volatility', {}).get('vix', 20) > 40:
            return RiskLevel.VERY_HIGH
        elif market_analysis.get('volatility', {}).get('vix', 20) > 30:
            return RiskLevel.HIGH
        elif market_analysis.get('volatility', {}).get('vix', 20) > 20:
            return RiskLevel.MODERATE
        elif market_analysis.get('volatility', {}).get('vix', 20) > 10:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW

    def _identify_risks(
        self,
        technical_result,
        market_analysis
    ) -> List[str]:
        """Identify key risks"""
        risks = []

        if market_analysis.get('volatility', {}).get('regime') == 'extreme':
            risks.append("Extreme market volatility")

        if technical_result.get('trend') == 'downtrend':
            risks.append("Downtrend in progress")

        if market_analysis.get('health_score', 50) < 50:
            risks.append("Weak market health")

        return risks or ["Market conditions normal"]

    # -----------------------------------------------------------------------
    # Real data methods (Alpaca-backed, yfinance fallback)
    # -----------------------------------------------------------------------

    def _get_alpaca_feed(self):
        """Cache SIP vs IEX choice for this process — same auto-detect
        pattern app.py's _get_data_feed() uses; duplicated here rather than
        imported to avoid a circular import (app.py imports this module)."""
        if self._alpaca_feed_cache is not None:
            return self._alpaca_feed_cache
        from alpaca.data.enums import DataFeed
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestTradeRequest
            key = os.environ.get('ALPACA_API_KEY', '')
            secret = os.environ.get('ALPACA_API_SECRET', '')
            client = StockHistoricalDataClient(key, secret)
            client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols="SPY", feed=DataFeed.SIP))
            self._alpaca_feed_cache = DataFeed.SIP
        except Exception:
            self._alpaca_feed_cache = DataFeed.IEX
        return self._alpaca_feed_cache

    def prefetch_ohlcv(self, tickers: List[str]) -> None:
        """Batch-fetch ~1-year daily OHLCV for all tickers and fill cache.
        Alpaca primary (same credentials/feed used everywhere else in this
        system) — this was the highest-traffic yfinance dependency in the
        whole pipeline (every ticker, every scan) and is what
        technical_score/RS-vs-SPY are actually computed from, so it's worth
        being on the more reliable source. yfinance kept only as a fallback
        for tickers Alpaca's batch call doesn't return."""
        cached_via_alpaca = set()
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            key = os.environ.get('ALPACA_API_KEY', '')
            secret = os.environ.get('ALPACA_API_SECRET', '')
            if key and secret:
                client = StockHistoricalDataClient(key, secret)
                chunk_size = 200
                for i in range(0, len(tickers), chunk_size):
                    chunk = tickers[i:i + chunk_size]
                    try:
                        req = StockBarsRequest(
                            symbol_or_symbols=chunk,
                            timeframe=TimeFrame.Day,
                            start=datetime.utcnow() - timedelta(days=400),
                            end=datetime.utcnow(),
                            feed=self._get_alpaca_feed(),
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
                                if len(df) >= 20:
                                    self._ohlcv_cache[ticker] = df
                                    cached_via_alpaca.add(ticker)
                            except Exception:
                                continue
                    except Exception as e:
                        logger.warning(f"[OHLCV] Alpaca chunk {i} failed: {e}")
                logger.info(f"[OHLCV] Alpaca prefetched {len(cached_via_alpaca)}/{len(tickers)} tickers")
        except Exception as e:
            logger.warning(f"[OHLCV] Alpaca prefetch failed entirely: {e}")

        missing = [t for t in tickers if t not in cached_via_alpaca]
        if missing:
            try:
                import yfinance as yf
                chunk_size = 100
                total_cached = 0
                for i in range(0, len(missing), chunk_size):
                    chunk = missing[i:i + chunk_size]
                    try:
                        raw = yf.download(
                            chunk, period='1y', interval='1d',
                            progress=False, auto_adjust=True
                        )
                        if raw.empty:
                            continue
                        for ticker in chunk:
                            try:
                                if isinstance(raw.columns, pd.MultiIndex):
                                    close = raw['Close'][ticker]
                                    high = raw['High'][ticker]
                                    low = raw['Low'][ticker]
                                    open_ = raw['Open'][ticker]
                                    vol = raw['Volume'][ticker]
                                else:
                                    close = raw['Close']
                                    high = raw['High']
                                    low = raw['Low']
                                    open_ = raw['Open']
                                    vol = raw['Volume']
                                df = pd.DataFrame({
                                    'close': close, 'high': high,
                                    'low': low, 'open': open_, 'volume': vol
                                }).dropna(subset=['close'])
                                if len(df) >= 20:
                                    self._ohlcv_cache[ticker] = df
                                    total_cached += 1
                            except Exception:
                                continue
                    except Exception as e:
                        logger.warning(f"[OHLCV] yfinance fallback chunk {i} failed: {e}")
                logger.info(f"[OHLCV] yfinance fallback covered {total_cached}/{len(missing)} remaining tickers")
            except Exception as e:
                logger.error(f"[OHLCV] yfinance fallback failed: {e}")

    def _get_ohlcv(self, ticker: str) -> Optional[pd.DataFrame]:
        """Return cached OHLCV df; fetch individually if not cached.
        Alpaca primary, yfinance fallback — same as prefetch_ohlcv."""
        if ticker in self._ohlcv_cache:
            return self._ohlcv_cache[ticker]
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            key = os.environ.get('ALPACA_API_KEY', '')
            secret = os.environ.get('ALPACA_API_SECRET', '')
            if key and secret:
                client = StockHistoricalDataClient(key, secret)
                req = StockBarsRequest(
                    symbol_or_symbols=ticker,
                    timeframe=TimeFrame.Day,
                    start=datetime.utcnow() - timedelta(days=400),
                    end=datetime.utcnow(),
                    feed=self._get_alpaca_feed(),
                    adjustment='all',
                )
                raw = client.get_stock_bars(req).df
                if not raw.empty and ticker in raw.index.get_level_values(0):
                    tdf = raw.loc[ticker]
                    df = tdf[['close', 'high', 'low', 'open', 'volume']].dropna(subset=['close'])
                    if len(df) >= 20:
                        self._ohlcv_cache[ticker] = df
                        return df
        except Exception as e:
            logger.debug(f"[OHLCV] Alpaca single-ticker fetch failed for {ticker}: {e}")
        try:
            import yfinance as yf
            raw = yf.download(ticker, period='1y', interval='1d',
                              progress=False, auto_adjust=True)
            if raw.empty:
                return None
            df = raw.rename(columns={
                'Close': 'close', 'High': 'high',
                'Low': 'low', 'Open': 'open', 'Volume': 'volume'
            })[['close', 'high', 'low', 'open', 'volume']].dropna(subset=['close'])
            if len(df) >= 20:
                self._ohlcv_cache[ticker] = df
                return df
        except Exception:
            pass
        return None

    def _compute_indicators(self, df: Optional[pd.DataFrame]) -> Dict:
        """Compute RSI, MACD, SMA, EMA from an OHLCV DataFrame."""
        if df is None or len(df) < 20:
            return {}
        close = df['close'].astype(float)

        # RSI-14
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = float((100 - 100 / (1 + gain / (loss + 1e-10))).iloc[-1])

        # MACD 12/26/9
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = float((macd_line - signal_line).iloc[-1])

        # SMAs
        sma20 = float(close.rolling(20).mean().iloc[-1]) if len(df) >= 20 else None
        sma50 = float(close.rolling(50).mean().iloc[-1]) if len(df) >= 50 else None
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

        # Price returns for sentiment proxy
        ret5 = float((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6]) if len(df) >= 6 else 0.0
        ret20 = float((close.iloc[-1] - close.iloc[-21]) / close.iloc[-21]) if len(df) >= 21 else ret5

        return {
            'rsi': rsi, 'macd_hist': macd_hist,
            'sma20': sma20, 'sma50': sma50, 'sma200': sma200,
            'ema12': float(ema12.iloc[-1]), 'ema26': float(ema26.iloc[-1]),
            'ret5': ret5, 'ret20': ret20
        }

    def _fetch_real_technical_data(self, ticker: str, price: float) -> Dict:
        """Compute technical indicators from real OHLCV data."""
        df  = self._get_ohlcv(ticker)
        ind = self._compute_indicators(df)
        if not ind:
            return self._generate_technical_data()

        rsi = ind['rsi']
        sma20, sma50, sma200 = ind.get('sma20'), ind.get('sma50'), ind.get('sma200')
        macd_hist = ind['macd_hist']

        # Trend: how many SMAs is price above?
        above = sum(1 for s in [sma20, sma50, sma200] if s and price > s)
        trend = 'uptrend' if above >= 2 else ('downtrend' if above == 0 else 'sideways')

        # Momentum: MACD histogram, normalised to ±100
        norm = (macd_hist / max(price, 1)) * 1000
        momentum = max(-100.0, min(100.0, norm * 100))

        # Strength: fraction of bullish indicators out of 5
        bulls = sum([
            bool(sma20 and price > sma20),
            bool(sma50 and price > sma50),
            bool(sma200 and price > sma200),
            rsi < 70,
            macd_hist > 0,
        ])
        strength = bulls / 5.0

        # ── Volume confirmation ──────────────────────────────────────────────
        volume_ratio = 1.0
        avg_dollar_volume = 0.0  # 20d avg shares x price — an absolute, cross-
        # ticker liquidity measure. volume_ratio above is deliberately
        # self-relative (today vs this ticker's own history) so it can't
        # tell a genuinely high-volume stock apart from a thin one having a
        # busier-than-usual day; this uses the same avg_vol already computed
        # below, no extra fetch needed.
        if df is not None and 'volume' in df.columns and len(df) >= 20:
            vol = df['volume'].astype(float)
            avg_vol = float(vol.rolling(20).mean().iloc[-1])
            cur_vol = float(vol.iloc[-1])
            if avg_vol > 0:
                volume_ratio = round(cur_vol / avg_vol, 2)
                avg_dollar_volume = round(avg_vol * price, 0)

        # ── Relative strength vs SPY ─────────────────────────────────────────
        rs_vs_spy = 0.0
        spy_df = self._ohlcv_cache.get('SPY')
        if spy_df is not None and len(spy_df) >= 6:
            spy_ret5 = float((spy_df['close'].iloc[-1] - spy_df['close'].iloc[-6]) /
                             spy_df['close'].iloc[-6]) * 100
            stock_ret5 = ind.get('ret5', 0.0) * 100
            rs_vs_spy = round(stock_ret5 - spy_ret5, 2)

        # Technical score 0–100
        score = 50.0
        if rsi < 30:    score += 15   # oversold → bullish
        elif rsi < 50:  score += 5
        elif rsi > 70:  score -= 15   # overbought → bearish
        elif rsi > 60:  score -= 5
        if sma20:
            score += 10 if price > sma20 else -8
        if sma50:
            score += 10 if price > sma50 else -8
        if sma200:
            score += 8 if price > sma200 else -8
        score += 9 if macd_hist > 0 else -9

        # Volume bonus: above-average volume confirms the move (+5/-3)
        if volume_ratio >= 1.5:
            score += 5 if macd_hist > 0 else -3
        elif volume_ratio < 0.5:
            score -= 3  # thin volume weakens any signal

        # Relative strength bonus: outperforming SPY by 2%+ is bullish
        if rs_vs_spy >= 2.0:
            score += 5
        elif rs_vs_spy >= 1.0:
            score += 3
        elif rs_vs_spy <= -2.0:
            score -= 5
        elif rs_vs_spy <= -1.0:
            score -= 3

        score = max(0.0, min(100.0, score))

        return {
            'trend': trend,
            'momentum': momentum,
            'strength': strength,
            'technical_score': score,
            'rsi': rsi,
            'macd_hist': macd_hist,
            'volume_ratio': volume_ratio,
            'avg_dollar_volume': avg_dollar_volume,
            'rs_vs_spy': rs_vs_spy,
            'support_resistance': {
                'support': (sma20 or price) * 0.98,
                'resistance': (sma20 or price) * 1.02
            }
        }

    def _score_headlines(self, headlines: List[str]) -> Optional[Dict]:
        """Keyword-score a batch of headlines for one ticker. Returns None if
        no headline produced a signal (caller decides the neutral fallback)."""
        bullish = bearish = 0
        for title in headlines:
            if not title:
                continue
            parts = title.lower().split()
            first_word = parts[0].strip('.,!?:;"\'') if parts else ''
            if first_word in self._MARKET_OPENERS:
                continue
            words = {w.strip('.,!?:;"\'') for w in parts}
            bullish += len(words & self._BULLISH_WORDS)
            bearish += len(words & self._BEARISH_WORDS)

        total = bullish + bearish
        if total == 0:
            return None

        raw = (bullish - bearish) / total
        sentiment = max(-1.0, min(1.0, raw * 2.0))
        strength = min(1.0, total / 10.0 + 0.3)
        trend = ('improving' if sentiment > 0.1
                 else 'deteriorating' if sentiment < -0.1 else 'stable')
        return {
            'overall_sentiment': sentiment,
            'strength': strength,
            'recency_score': 0.9,
            'trend': trend,
            'news_count': len(headlines),
        }

    def _fetch_broad_articles(self) -> List[Dict]:
        """One market-wide news pull (no symbol filter) instead of ~1,650
        per-ticker calls, cached 30 min — market-wide headlines don't turn
        over meaningfully faster than that. Returns raw articles
        (most-recent-first, as Alpaca returns them) shared by both the
        per-ticker sentiment map (_fetch_broad_market_news) and the
        top-headlines banner feed (get_top_headlines)."""
        now = datetime.utcnow()
        if self._broad_news_cache:
            cached, fetched_at = self._broad_news_cache
            if (now - fetched_at).total_seconds() < 1800:
                return cached

        articles: List[Dict] = []
        try:
            from alpaca.data.historical.news import NewsClient
            from alpaca.data.requests import NewsRequest
            client = NewsClient(os.environ.get('ALPACA_API_KEY', ''), os.environ.get('ALPACA_API_SECRET', ''))
            req = NewsRequest(limit=50)  # no symbols= -> top market-wide news
            raw_articles = client.get_news(req).data.get('news', [])
            for article in raw_articles:
                title = article.headline or ''
                if not title:
                    continue
                articles.append({'headline': title, 'symbols': list(article.symbols or [])})

        except Exception:
            logger.warning("Broad market news fetch failed", exc_info=True)
            # Keep the previous cache (if any) rather than wiping it out on a
            # transient API failure — stale-but-real articles beat none.
            if self._broad_news_cache:
                return self._broad_news_cache[0]

        self._broad_news_cache = (articles, now)
        return articles

    def _fetch_broad_market_news(self) -> Dict[str, Dict]:
        """Per-ticker sentiment map derived from the shared broad-article
        cache — doubles as the discovery feed (see get_news_matched_tickers)."""
        headlines_by_ticker: Dict[str, List[str]] = {}
        for article in self._fetch_broad_articles():
            for sym in article['symbols']:
                headlines_by_ticker.setdefault(sym, []).append(article['headline'])

        result: Dict[str, Dict] = {}
        for ticker, headlines in headlines_by_ticker.items():
            scored = self._score_headlines(headlines)
            if scored is not None:
                result[ticker] = scored
        return result

    def get_news_matched_tickers(self) -> Set[str]:
        """Tickers named in the current broad-news pull — used to pull
        breaking-news tickers into the scan even if they didn't clear the
        normal quality filter yet."""
        return set(self._fetch_broad_market_news().keys())

    def get_top_headlines(self, limit: int = 10) -> List[Dict]:
        """Top market headlines for the UI ticker banner — most recent
        first, deduplicated by headline text (the same story often gets
        tagged to multiple tickers as separate article entries)."""
        seen = set()
        out: List[Dict] = []
        for article in self._fetch_broad_articles():
            headline = article['headline']
            if headline in seen:
                continue
            seen.add(headline)
            out.append({
                'headline': headline,
                'tickers': article['symbols'][:3],  # cap display tags
            })
            if len(out) >= limit:
                break
        return out

    def _fetch_real_news_data(self, ticker: str) -> Dict:
        """Sentiment for one ticker, sourced from the shared broad market-news
        pull. No per-ticker API call and no price-momentum fallback: if a
        ticker wasn't in the latest top-news batch, there's no real signal to
        report, so it scores neutral rather than a fabricated proxy that would
        double-count price action already captured by the technical/strategy
        weights (this covers most tickers most cycles — the broad feed only
        surfaces the ~50 highest-profile headlines, not full market coverage)."""
        broad_map = self._fetch_broad_market_news()
        if ticker in broad_map:
            return broad_map[ticker]

        return {
            'overall_sentiment': 0.0,
            'strength': 0.3,
            'recency_score': 0.0,
            'trend': 'stable',
            'news_count': 0,
        }

    def _fetch_real_market_data(self) -> Dict:
        """Fetch SPY+VIX market regime data; cached for 30 minutes."""
        now = datetime.utcnow()
        if (self._market_cache_time and
                (now - self._market_cache_time).total_seconds() < 1800):
            return self._market_cache
        try:
            import yfinance as yf
            raw = yf.download(['SPY', 'IWM', '^VIX'], period='1y', interval='1d',
                              progress=False, auto_adjust=True)
            spy = raw['Close']['SPY'].dropna()
            iwm = raw['Close']['IWM'].dropna()
            vix_s = raw['Close']['^VIX'].dropna()
            spy_price = float(spy.iloc[-1])
            spy_prev_close = float(spy.iloc[-2]) if len(spy) > 1 else spy_price
            iwm_price = float(iwm.iloc[-1])
            iwm_prev_close = float(iwm.iloc[-2]) if len(iwm) > 1 else iwm_price
            spy_sma50 = float(spy.rolling(50).mean().iloc[-1])
            spy_sma200 = float(spy.rolling(200).mean().iloc[-1])
            vix = float(vix_s.iloc[-1])

            trend_dir = ('uptrend' if spy_price > spy_sma50 > spy_sma200
                         else 'downtrend' if spy_price < spy_sma50
                         else 'sideways')
            vol_regime = ('low' if vix < 15 else
                          'medium' if vix < 25 else
                          'high' if vix < 40 else 'extreme')
            health = 65.0
            health += 20 if trend_dir == 'uptrend' else (-20 if trend_dir == 'downtrend' else 0)
            health += 10 if vix < 15 else (-10 if vix > 30 else 0)
            health = max(0.0, min(100.0, health))

            result = {
                'spy_price': spy_price,
                'spy_change_pct': round((spy_price - spy_prev_close) / spy_prev_close * 100, 2) if spy_prev_close else 0.0,
                'iwm_change_pct': round((iwm_price - iwm_prev_close) / iwm_prev_close * 100, 2) if iwm_prev_close else 0.0,
                'spy_sma50': spy_sma50,
                'spy_sma200': spy_sma200,
                'vix': vix,
                'trend': {'direction': trend_dir},
                'volatility': {'regime': vol_regime, 'vix': vix},
                'health_score': health,
                'breadth': {'breadth_score': 0.70 if trend_dir == 'uptrend' else 0.45}
            }
            self._market_cache = result
            self._market_cache_time = now
            logger.info(f"[Market] SPY={spy_price:.2f} VIX={vix:.1f} trend={trend_dir}")
            return result
        except Exception as e:
            logger.error(f"[Market] fetch failed: {e}")
            return self._generate_market_data()

    def get_market_pulse(self) -> Dict:
        """Compact SPY/VIX/IWM snapshot for the dashboard banner — the same
        30-min-cached fetch that already feeds the market_score composite
        weight, just reshaped for display instead of scoring.

        trade_advisory is the actionable verdict (Favorable/Caution/
        Unfavorable) the banner surfaces as its primary signal — built from
        two real risk indicators, not price direction alone: VIX regime
        (real fear/options-pricing risk) and the SPY-vs-IWM divergence
        (small caps underperforming large caps signals risk-off rotation
        and rising correlation, both of which make individual per-ticker
        technical signals less trustworthy even on a calm-looking index
        day — this is exactly the pattern found investigating 2026-09-09,
        where SPY was only -0.47% but IWM was -1.35%)."""
        data = self._fetch_real_market_data()
        change = data.get('spy_change_pct', 0.0)
        iwm_change = data.get('iwm_change_pct', 0.0)
        vix = data.get('vix', 20.0)
        regime = data.get('volatility', {}).get('regime', 'medium')
        divergence = round(change - iwm_change, 2)  # positive = small caps lagging

        if regime in ('high', 'extreme') or abs(divergence) >= 2.0:
            advisory = 'Unfavorable'
        elif regime == 'medium' or abs(divergence) >= 1.0:
            advisory = 'Caution'
        else:
            advisory = 'Favorable'

        if regime in ('high', 'extreme'):
            summary = 'Volatile'
        elif change >= 0.5:
            summary = 'Rallying'
        elif change <= -0.5:
            summary = 'Selling off'
        elif abs(change) < 0.3 and regime == 'low':
            summary = 'Quiet session'
        else:
            summary = 'Mixed'

        return {
            'spy_change_pct': change,
            'iwm_change_pct': iwm_change,
            'divergence_pct': divergence,
            'vix': round(vix, 2),
            'vix_regime': regime,
            'trade_advisory': advisory,
            'summary': summary,
        }

    def _fetch_real_options_data(self, ticker: str, price: float) -> Dict:
        """Fetch real options chain: IV per contract, put/call ratio, ATM
        recommendations. Alpaca-backed — replaced a yfinance options-chain
        scrape after confirming Yahoo had blocked Railway's production IP
        at the network level (100% of live signals defaulting to neutral
        IV rank, while the exact same yfinance code succeeded instantly
        from a non-Railway machine — an IP block, not a data or code
        problem, so a retry couldn't fix it). Alpaca is authenticated and
        already used reliably elsewhere in this app (covered-calls premium
        fetching), and its option snapshot returns real implied_volatility
        directly — no manual IV computation needed, unlike yfinance's raw
        chain."""
        now = datetime.utcnow()
        if ticker in self._options_cache:
            cached, fetched_at = self._options_cache[ticker]
            if (now - fetched_at).total_seconds() < 300:
                return cached

        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import GetOptionContractsRequest
            from alpaca.trading.enums import ContractType
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionSnapshotRequest
            from datetime import date as _date, timedelta as _timedelta

            key = os.environ.get('ALPACA_API_KEY', '')
            secret = os.environ.get('ALPACA_API_SECRET', '')
            if not key or not secret:
                raise RuntimeError("Alpaca credentials not configured")

            # Reused across every ticker/call — see the __init__ comment on
            # these attributes for why building fresh clients per-call was
            # a serious latency bug at ~1,660-ticker scale. requests.Session
            # (which these wrap) is safe for concurrent use across threads.
            if self._alpaca_trading_client is None:
                self._alpaca_trading_client = TradingClient(key, secret, paper=True)
            if self._alpaca_option_data_client is None:
                self._alpaca_option_data_client = OptionHistoricalDataClient(key, secret)
            trading_client = self._alpaca_trading_client
            data_client = self._alpaca_option_data_client

            # ATM window: ±10% of current price, same as before. Expiry
            # window 14-45 days out — avoids 0DTE noise on one end and
            # LEAPS on the other, roughly matching the old "nearest expiry
            # >=7 days out" intent with a bounded upper end too.
            lo, hi = round(price * 0.90, 2), round(price * 1.10, 2)
            exp_lo = _date.today() + _timedelta(days=14)
            exp_hi = _date.today() + _timedelta(days=45)

            # 2 network calls total per ticker (1 contract list + 1 batched
            # snapshot), not 4 — an earlier version fetched calls/puts as
            # separate contract-list AND separate snapshot calls, which was
            # fine per-ticker but made the full ~1660-ticker scan take
            # ~15 minutes instead of the usual ~3, risking every automatic
            # scheduler cycle hitting its own 240s timeout. Alpaca returns
            # both contract types in one call when `type` is omitted.
            # limit=30 cut the contract-list call from 3-6s to <0.1s for
            # most tickers in direct testing (heavily-optioned tickers were
            # the slow ones — Alpaca's backend appears to spend that time
            # server-side building the larger unlimited result set before
            # this client ever sees it). Some individual calls still run
            # slow regardless (observed variability isn't tied to any one
            # ticker consistently) — 16-way scan concurrency and the
            # scheduler's own 240s cycle timeout are the backstops for that
            # residual variance, not something fixable purely client-side.
            req = GetOptionContractsRequest(
                underlying_symbols=[ticker],
                expiration_date_gte=exp_lo,
                expiration_date_lte=exp_hi,
                strike_price_gte=str(lo),
                strike_price_lte=str(hi),
                limit=30,
            )
            resp = trading_client.get_option_contracts(req)
            all_contracts = resp.option_contracts if hasattr(resp, 'option_contracts') else list(resp)
            calls = [c for c in all_contracts if c.type == ContractType.CALL][:15]
            puts = [c for c in all_contracts if c.type == ContractType.PUT][:15]

            snaps = {}
            symbols = [c.symbol for c in calls + puts]
            if symbols:
                snap_req = OptionSnapshotRequest(symbol_or_symbols=symbols)
                snaps = data_client.get_option_snapshot(snap_req)
            call_snaps = put_snaps = snaps  # same combined dict, kept as two names below for minimal diff

            def _ivs(contracts, snaps):
                vals = []
                for c in contracts:
                    s = snaps.get(c.symbol)
                    iv = getattr(s, 'implied_volatility', None) if s else None
                    if iv and iv > 0:
                        vals.append(float(iv))
                return vals

            call_ivs = _ivs(calls, call_snaps)
            put_ivs = _ivs(puts, put_snaps)
            call_iv = sum(call_ivs) / len(call_ivs) if call_ivs else 0.25
            put_iv = sum(put_ivs) / len(put_ivs) if put_ivs else 0.25

            # Put/call OI ratio — > 1 is bearish skew
            call_oi = sum(int(c.open_interest or 0) for c in calls)
            put_oi = sum(int(c.open_interest or 0) for c in puts)
            pc_ratio = put_oi / max(call_oi, 1)

            def _top_recs(contracts, snaps, n=2):
                if not contracts:
                    return []
                # Ranked by open interest (liquidity) — same "most relevant
                # contracts" intent as the old volume-based ranking, using
                # what Alpaca's contract object actually exposes.
                ranked = sorted(contracts, key=lambda c: int(c.open_interest or 0), reverse=True)
                recs = []
                for c in ranked[:n]:
                    s = snaps.get(c.symbol)
                    iv = getattr(s, 'implied_volatility', None) if s else None
                    iv = float(iv) if iv and iv > 0 else 0.25
                    recs.append({
                        'strike': float(c.strike_price),
                        'suitability': {'option_score': min(95, int(iv * 150 + 40))}
                    })
                return recs

            # ── IV Rank (proxy via realized vol comparison) ──────────────────
            # Unchanged math from the yfinance version — only the IV input
            # source changed. Compare ATM implied vol to 20-day historical vol.
            # IV/HV ratio > 2 = expensive options (rank ~100), < 0.7 = cheap (rank ~0).
            iv_rank = 50.0
            hv_df = self._ohlcv_cache.get(ticker)
            if hv_df is not None and len(hv_df) >= 21:
                log_ret = np.log(hv_df['close'].astype(float) / hv_df['close'].astype(float).shift(1)).dropna()
                hv20 = float(log_ret.tail(20).std() * np.sqrt(252))
                if hv20 > 0:
                    iv_hv_ratio = call_iv / hv20
                    iv_rank = round(min(100.0, max(0.0, (iv_hv_ratio - 0.7) / 1.3 * 100)), 1)

            result = {
                'calls': {
                    'recommendations': _top_recs(calls, call_snaps) or [{'strike': round(price * 1.05), 'suitability': {'option_score': 60}}],
                    'avg_iv': call_iv
                },
                'puts': {
                    'recommendations': _top_recs(puts, put_snaps) or [{'strike': round(price * 0.95), 'suitability': {'option_score': 55}}],
                    'avg_iv': put_iv
                },
                'pc_ratio': pc_ratio,
                'iv_rank': iv_rank,
            }
            self._options_cache[ticker] = (result, now)
            logger.debug(f"[Options] {ticker} call_iv={call_iv:.2f} put_iv={put_iv:.2f} pc={pc_ratio:.2f} (Alpaca)")
            return result

        except Exception as e:
            logger.debug(f"[Options] {ticker} Alpaca fetch failed: {e}")
            return self._generate_options_data()

    # -----------------------------------------------------------------------
    # Expert signals: earnings date + fundamental data
    # -----------------------------------------------------------------------

    def _fetch_earnings_date(self, ticker: str) -> int:
        """Return days until next earnings announcement (999 = unknown/far out). 24h cache.
        Finnhub-backed — replaced yfinance's .calendar scrape as part of
        removing yfinance entirely after Yahoo blocked Railway's production
        IP (see _fetch_real_options_data's docstring for the full incident).
        Free-tier Finnhub confirmed working for this specific endpoint via
        direct testing (real upcoming dates for AAPL/AMD/MSFT, empty array
        for a nonexistent ticker — no auth/tier restriction hit here, unlike
        the price-target endpoint)."""
        now = datetime.utcnow()
        if ticker in self._earnings_cache:
            cached_days, fetched_at = self._earnings_cache[ticker]
            if (now - fetched_at).total_seconds() < 86400:
                return cached_days
        days = 999
        success = False  # only cache on real success — a 429/timeout must
        # not lock a ticker at the default for the full 24h TTL, or a
        # single rate-limited moment "poisons" it for the rest of the day.
        try:
            import requests
            from datetime import date as _date, timedelta as _timedelta
            api_key = os.environ.get('FINNHUB_API_KEY', '')
            if not api_key:
                raise RuntimeError("Finnhub API key not configured")
            today = _date.today()
            finnhub_limiter.acquire()
            resp = requests.get(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={
                    "from": today.isoformat(),
                    "to": (today + _timedelta(days=180)).isoformat(),
                    "symbol": ticker,
                    "token": api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            events = resp.json().get("earningsCalendar") or []
            if events:
                # Events come back sorted by date already; take the soonest.
                earn_date = _date.fromisoformat(events[0]["date"])
                days = max(0, (earn_date - today).days)
            success = True
        except Exception as e:
            logger.debug(f"[Earnings] {ticker} Finnhub fetch failed: {e}")
        if success:
            self._earnings_cache[ticker] = (days, now)
        return days

    def _fetch_real_fundamental_data(self, ticker: str, price: float) -> Dict:
        """Fetch analyst consensus and short interest. 4-hour cache.
        Finnhub-backed — replaced yfinance's .info scrape (see
        _fetch_real_options_data's docstring for the yfinance-removal
        incident this is part of). Finnhub's free tier blocks its
        price-target endpoint outright ("You don't have access to this
        resource", confirmed directly) and has no short-interest data at
        any tier we tested — only its recommendation-trends endpoint
        (buy/hold/sell analyst counts) is both free and populated. Per
        explicit product decision: analyst_upside is no longer a literal
        "target price vs current price" percentage (that data isn't
        available for free anywhere) — it's now a consensus-derived
        proxy on a comparable scale, computed from the real buy/hold/sell
        distribution rather than a fabricated number. short_interest_pct
        stays 0.0 / neutral, same as the pre-existing "no data" branch
        below already handled when yfinance had nothing either."""
        now = datetime.utcnow()
        if ticker in self._fundamental_cache:
            cached, fetched_at = self._fundamental_cache[ticker]
            if (now - fetched_at).total_seconds() < 14400:
                return cached

        result = {'analyst_upside': 0.0, 'short_interest_pct': 0.0,
                  'analyst_count': 0,    'fundamental_score': 0.5}
        success = False  # only cache on real success — see _fetch_earnings_date
        try:
            import requests
            api_key = os.environ.get('FINNHUB_API_KEY', '')
            if not api_key:
                raise RuntimeError("Finnhub API key not configured")
            finnhub_limiter.acquire()
            resp = requests.get(
                "https://finnhub.io/api/v1/stock/recommendation",
                params={"symbol": ticker, "token": api_key},
                timeout=10,
            )
            resp.raise_for_status()
            periods = resp.json() or []
            short_float = 0.0  # not available free on any tested tier

            if periods:
                latest = periods[0]  # API returns most-recent period first
                strong_buy = int(latest.get('strongBuy') or 0)
                buy = int(latest.get('buy') or 0)
                hold = int(latest.get('hold') or 0)
                sell = int(latest.get('sell') or 0)
                strong_sell = int(latest.get('strongSell') or 0)
                n_analysts = strong_buy + buy + hold + sell + strong_sell

                if n_analysts > 0:
                    # Per-analyst-weighted sentiment: +2/+1/0/-1/-2, normalized
                    # to [-1, 1] by the maximum possible weight (unanimous
                    # strongBuy or strongSell).
                    consensus = (2 * strong_buy + buy - sell - 2 * strong_sell) / (2 * n_analysts)
                    # Mapped onto the same rough magnitude range real analyst
                    # upside percentages tend to fall in (-25% to +25%) so
                    # this reads comparably to the old field, while being
                    # honestly consensus-derived rather than a price target.
                    upside = round(consensus * 25, 1)
                else:
                    upside = 0.0
            else:
                n_analysts = 0
                upside = 0.0

            # upside score: same shape as before — 0%→0.3, 10%→0.6, 25%+→1.0
            upside_score = min(1.0, max(0.0, 0.3 + upside / 35.0))
            # short squeeze score: neutral default — no free short-interest source
            short_score = min(1.0, short_float / 0.15) if short_float > 0 else 0.3

            # Only trust consensus if ≥3 analysts cover the stock
            if n_analysts >= 3:
                fund_score = round(upside_score * 0.75 + short_score * 0.25, 4)
            else:
                fund_score = 0.5  # neutral when no coverage

            result = {
                'analyst_upside':    upside,
                'short_interest_pct': round(short_float * 100, 1),
                'analyst_count':     n_analysts,
                'fundamental_score': fund_score,
            }
            success = True
        except Exception as e:
            logger.debug("[Fundamentals] %s failed: %s", ticker, e)

        if success:
            self._fundamental_cache[ticker] = (result, now)
        return result

    # -----------------------------------------------------------------------
    # Fallback generators (used when yfinance data is unavailable)
    # -----------------------------------------------------------------------

    def _generate_technical_data(self) -> Dict:
        """Fallback: neutral technical data"""
        return {
            'trend': 'sideways',
            'momentum': 0,
            'strength': 0.5,
            'technical_score': 50,
            'support_resistance': {'support': 95, 'resistance': 105}
        }

    def _generate_options_data(self) -> Dict:
        """Generate options IV data"""
        return {
            'calls': {
                'recommendations': [
                    {'strike': 100, 'suitability': {'option_score': 75}},
                    {'strike': 105, 'suitability': {'option_score': 70}}
                ],
                'avg_iv': 0.25
            },
            'puts': {
                'recommendations': [
                    {'strike': 100, 'suitability': {'option_score': 55}},
                    {'strike': 95, 'suitability': {'option_score': 50}}
                ],
                'avg_iv': 0.25
            }
        }

    def _generate_market_data(self) -> Dict:
        """Fallback: neutral market data"""
        return {
            'spy_price': 500.0,
            'spy_change_pct': 0.0,
            'iwm_change_pct': 0.0,
            'spy_sma50': 490.0,
            'spy_sma200': 470.0,
            'vix': 20.0,
            'trend': {'direction': 'sideways'},
            'volatility': {'regime': 'medium', 'vix': 20},
            'health_score': 65,
            'breadth': {'breadth_score': 0.55}
        }

    def _generate_id(self) -> str:
        """Generate unique ID"""
        import uuid
        return str(uuid.uuid4())[:8]


async def main():
    """Example usage"""
    agent = MCPStockAgent()

    # Add tickers to watchlist
    await agent.add_to_watchlist("AAPL", buy_threshold=0.70)
    await agent.add_to_watchlist("MSFT", buy_threshold=0.75)
    await agent.add_to_watchlist("NVDA", buy_threshold=0.75)

    # Analyze watchlist
    results = await agent.analyze_watchlist()

    # Print results
    for result in results:
        print(f"\n{result.ticker}: {result.buy_score:.1%}")
        print(f"Signal: {result.buy_signal.value}")
        print(f"Thesis: {result.thesis[:100]}...")

    # Get trending opportunities
    opportunities = await agent.get_trending_opportunities(min_score=0.70)
    print(f"\nTrending Opportunities ({len(opportunities)}):")
    for opp in opportunities:
        print(f"  {opp['ticker']}: {opp['score']:.1%} - {opp['signal']}")


if __name__ == "__main__":
    asyncio.run(main())

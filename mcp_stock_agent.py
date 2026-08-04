"""
MCP Stock Analysis Agent

Analyzes stock tickers and sends buy signal notifications.
Integrates with existing analyzer framework.
"""

import asyncio
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum

from analyzer.news_analyzer import NewsAnalyzer
from analyzer.technical_analyzer import TechnicalAnalyzer
from analyzer.options_analyzer import OptionsAnalyzer
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.strategy_selector import StrategySelector
from analyzer.call_put_predictor import CallPutPredictor
from analyzer.reasoning_generator import ReasoningGenerator


logger = logging.getLogger(__name__)


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
    analyst_upside: float = 0.0     # analyst consensus target vs current price (%)
    short_interest_pct: float = 0.0 # short interest as % of float


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
        self._market_cache: Dict = {}
        self._market_cache_time: Optional[datetime] = None
        self._options_cache: Dict[str, Tuple[Dict, datetime]] = {}
        self._news_cache: Dict[str, Tuple[Dict, datetime]] = {}
        self._earnings_cache: Dict[str, Tuple[int, datetime]] = {}    # ticker → (days_to_earn, fetched_at)
        self._fundamental_cache: Dict[str, Tuple[Dict, datetime]] = {} # ticker → (data, fetched_at)

        logger.info("MCP Stock Agent initialized successfully")

    async def analyze_ticker(
        self,
        ticker: str,
        price: float
    ) -> AnalysisResult:
        """
        Analyze a ticker and generate buy signal

        Args:
            ticker: Stock ticker symbol
            price: Current stock price

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
            fundamental    = self._fetch_real_fundamental_data(ticker, price)
            days_to_earn   = self._fetch_earnings_date(ticker)

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
                analyst_upside=fundamental.get('analyst_upside', 0.0),
                short_interest_pct=fundamental.get('short_interest_pct', 0.0),
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
    # Real data methods (yfinance-backed)
    # -----------------------------------------------------------------------

    def prefetch_ohlcv(self, tickers: List[str]) -> None:
        """Batch-download 1-year daily OHLCV for all tickers and fill cache."""
        try:
            import yfinance as yf
            chunk_size = 100
            total_cached = 0
            for i in range(0, len(tickers), chunk_size):
                chunk = tickers[i:i + chunk_size]
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
                    logger.warning(f"[OHLCV] chunk {i} failed: {e}")
            logger.info(f"[OHLCV] Prefetched {total_cached}/{len(tickers)} tickers")
        except Exception as e:
            logger.error(f"[OHLCV] prefetch_ohlcv failed: {e}")

    def _get_ohlcv(self, ticker: str) -> Optional[pd.DataFrame]:
        """Return cached OHLCV df; fetch individually if not cached."""
        if ticker in self._ohlcv_cache:
            return self._ohlcv_cache[ticker]
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
        if df is not None and 'volume' in df.columns and len(df) >= 20:
            vol = df['volume'].astype(float)
            avg_vol = float(vol.rolling(20).mean().iloc[-1])
            cur_vol = float(vol.iloc[-1])
            if avg_vol > 0:
                volume_ratio = round(cur_vol / avg_vol, 2)

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
            'rs_vs_spy': rs_vs_spy,
            'support_resistance': {
                'support': (sma20 or price) * 0.98,
                'resistance': (sma20 or price) * 1.02
            }
        }

    def _fetch_real_news_data(self, ticker: str) -> Dict:
        """Score sentiment from real yfinance news headlines with keyword analysis."""
        # Check cache (30-min TTL — news changes slowly)
        now = datetime.utcnow()
        if ticker in self._news_cache:
            cached, fetched_at = self._news_cache[ticker]
            if (now - fetched_at).total_seconds() < 1800:
                return cached

        # Strong, specific signals only — generic market words removed to avoid
        # inflating sentiment from broad "stocks higher today" headlines.
        BULLISH = {
            'beat', 'beats', 'upgrade', 'upgraded', 'outperform',
            'buy', 'bullish', 'breakthrough', 'milestone', 'record',
            'profit', 'profits', 'soars', 'soared', 'surges', 'surged', 'surge',
            'jumps', 'jumped', 'raises', 'raised', 'boosted', 'accelerates',
            'expansion', 'rallies', 'rallied',
        }
        BEARISH = {
            'miss', 'misses', 'missed', 'cut', 'cuts', 'downgrade', 'downgraded',
            'layoff', 'layoffs', 'loss', 'losses', 'weak', 'disappoints', 'disappointed',
            'warning', 'recall', 'investigation', 'fine', 'penalty',
            'drops', 'dropped', 'bearish', 'sell', 'reduces', 'reduced',
            'shrinks', 'slumps', 'slumped', 'slides', 'tumbles', 'tumbled',
            'probe', 'lawsuit', 'bankruptcy', 'decline', 'declines',
        }

        # General-market openers — articles starting with these are index/macro news,
        # not company news, and shouldn't affect per-ticker sentiment.
        MARKET_OPENERS = {
            'stocks', 's&p', 'dow', 'nasdaq', 'market', 'wall', 'futures',
            'global', 'asian', 'european', 'fed', 'investors', 'treasury',
        }

        try:
            import yfinance as yf
            articles = yf.Ticker(ticker).news or []
            if not articles:
                raise ValueError("no articles")

            bullish = bearish = 0
            for article in articles[:15]:
                # yfinance >= 0.2.x nests title inside content dict
                content = article.get('content', {})
                title = (content.get('title') or
                         content.get('description') or
                         article.get('title') or '')
                if not title:
                    continue
                # Skip obvious macro/index headlines — they inflate all tickers equally.
                parts = title.lower().split()
                first_word = parts[0].strip('.,!?:;"\'') if parts else ''
                if first_word in MARKET_OPENERS:
                    continue
                # Strip punctuation from each token before keyword matching
                words = {w.strip('.,!?:;"\'') for w in parts}
                bullish += len(words & BULLISH)
                bearish += len(words & BEARISH)

            total = bullish + bearish
            if total == 0:
                raise ValueError("no sentiment signals after market-article filter")

            raw = (bullish - bearish) / total
            sentiment = max(-1.0, min(1.0, raw * 2.0))
            strength = min(1.0, total / 10.0 + 0.3)
            trend = ('improving' if sentiment > 0.1
                     else 'deteriorating' if sentiment < -0.1 else 'stable')

            result = {
                'overall_sentiment': sentiment,
                'strength': strength,
                'recency_score': 0.9,
                'trend': trend,
                'news_count': len(articles)
            }
            self._news_cache[ticker] = (result, now)
            return result

        except Exception:
            # Fallback: price-momentum proxy when no news available
            ind = self._compute_indicators(self._get_ohlcv(ticker))
            if not ind:
                return self._generate_news_data()
            ret5  = ind.get('ret5',  0.0)
            ret20 = ind.get('ret20', 0.0)
            sentiment = max(-1.0, min(1.0, (ret5 * 0.6 + ret20 * 0.4) * 4.0))
            trend = ('improving' if sentiment > 0.1
                     else 'deteriorating' if sentiment < -0.1 else 'stable')
            result = {
                'overall_sentiment': sentiment,
                'strength': min(1.0, abs(sentiment) * 0.8 + 0.2),
                'recency_score': 0.6,
                'trend': trend,
                'news_count': 0
            }
            self._news_cache[ticker] = (result, now)
            return result

    def _fetch_real_market_data(self) -> Dict:
        """Fetch SPY+VIX market regime data; cached for 30 minutes."""
        now = datetime.utcnow()
        if (self._market_cache_time and
                (now - self._market_cache_time).total_seconds() < 1800):
            return self._market_cache
        try:
            import yfinance as yf
            raw = yf.download(['SPY', '^VIX'], period='1y', interval='1d',
                              progress=False, auto_adjust=True)
            spy = raw['Close']['SPY'].dropna()
            vix_s = raw['Close']['^VIX'].dropna()
            spy_price = float(spy.iloc[-1])
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

    def _fetch_real_options_data(self, ticker: str, price: float) -> Dict:
        """Fetch real options chain: IV per strike, put/call ratio, ATM recommendations."""
        # 20-min cache matches the analysis cycle
        now = datetime.utcnow()
        if ticker in self._options_cache:
            cached, fetched_at = self._options_cache[ticker]
            if (now - fetched_at).total_seconds() < 1200:
                return cached

        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            expirations = t.options
            if not expirations:
                raise ValueError("no options chain")

            # Pick nearest expiry that is at least 7 days away
            expiry = expirations[0]
            for exp in expirations:
                from datetime import date as _date
                exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
                if (exp_date - _date.today()).days >= 7:
                    expiry = exp
                    break

            chain = t.option_chain(expiry)
            calls_df = chain.calls.copy()
            puts_df  = chain.puts.copy()

            # ATM window: ±10% of current price
            lo, hi = price * 0.90, price * 1.10
            atm_calls = calls_df[(calls_df['strike'] >= lo) & (calls_df['strike'] <= hi)]
            atm_puts  = puts_df[ (puts_df['strike']  >= lo) & (puts_df['strike']  <= hi)]

            call_iv = float(atm_calls['impliedVolatility'].mean()) if not atm_calls.empty else 0.25
            put_iv  = float(atm_puts['impliedVolatility'].mean())  if not atm_puts.empty  else 0.25
            call_iv = call_iv if np.isfinite(call_iv) and call_iv > 0 else 0.25
            put_iv  = put_iv  if np.isfinite(put_iv)  and put_iv  > 0 else 0.25

            # Put/call OI ratio — > 1 is bearish skew
            call_oi = float(atm_calls['openInterest'].fillna(0).sum())
            put_oi  = float(atm_puts['openInterest'].fillna(0).sum())
            pc_ratio = put_oi / max(call_oi, 1)

            def _top_recs(df, n=2):
                if df.empty:
                    return []
                top = df.nlargest(n, 'volume') if 'volume' in df.columns else df.head(n)
                recs = []
                for _, row in top.iterrows():
                    iv = float(row.get('impliedVolatility', 0.25))
                    iv = iv if np.isfinite(iv) and iv > 0 else 0.25
                    recs.append({
                        'strike': float(row['strike']),
                        'suitability': {'option_score': min(95, int(iv * 150 + 40))}
                    })
                return recs

            # ── IV Rank (proxy via realized vol comparison) ──────────────────
            # Compare ATM implied vol to 20-day historical vol.
            # IV/HV ratio > 2 = expensive options (rank ~100), < 0.7 = cheap (rank ~0).
            iv_rank = 50.0
            hv_df = self._ohlcv_cache.get(ticker)
            if hv_df is not None and len(hv_df) >= 21:
                log_ret = np.log(hv_df['close'].astype(float) / hv_df['close'].astype(float).shift(1)).dropna()
                hv20 = float(log_ret.tail(20).std() * np.sqrt(252))
                if hv20 > 0:
                    iv_hv_ratio = call_iv / hv20
                    # ratio 0.7 → rank 0, ratio 1.0 → rank 33, ratio 2.0 → rank 100
                    iv_rank = round(min(100.0, max(0.0, (iv_hv_ratio - 0.7) / 1.3 * 100)), 1)

            result = {
                'calls': {
                    'recommendations': _top_recs(atm_calls) or [{'strike': round(price * 1.05), 'suitability': {'option_score': 60}}],
                    'avg_iv': call_iv
                },
                'puts': {
                    'recommendations': _top_recs(atm_puts) or [{'strike': round(price * 0.95), 'suitability': {'option_score': 55}}],
                    'avg_iv': put_iv
                },
                'pc_ratio': pc_ratio,
                'iv_rank': iv_rank,
            }
            self._options_cache[ticker] = (result, now)
            logger.debug(f"[Options] {ticker} call_iv={call_iv:.2f} put_iv={put_iv:.2f} pc={pc_ratio:.2f}")
            return result

        except Exception as e:
            logger.debug(f"[Options] {ticker} fetch failed: {e}")
            return self._generate_options_data()

    # -----------------------------------------------------------------------
    # Expert signals: earnings date + fundamental data
    # -----------------------------------------------------------------------

    def _fetch_earnings_date(self, ticker: str) -> int:
        """Return days until next earnings announcement (999 = unknown/far out). 24h cache."""
        now = datetime.utcnow()
        if ticker in self._earnings_cache:
            cached_days, fetched_at = self._earnings_cache[ticker]
            if (now - fetched_at).total_seconds() < 86400:
                return cached_days
        days = 999
        try:
            import yfinance as yf
            from datetime import date as _date
            cal = yf.Ticker(ticker).calendar
            if cal is not None and not (hasattr(cal, 'empty') and cal.empty):
                # Newer yfinance: dict with 'Earnings Date' key
                if isinstance(cal, dict):
                    earn = cal.get('Earnings Date')
                    if earn:
                        earn_dt = earn[0] if isinstance(earn, list) else earn
                        if hasattr(earn_dt, 'date'):
                            days = max(0, (earn_dt.date() - _date.today()).days)
                # Older yfinance: DataFrame with 'Earnings Date' row
                elif hasattr(cal, 'loc'):
                    if 'Earnings Date' in cal.index:
                        val = cal.loc['Earnings Date'].iloc[0]
                        if hasattr(val, 'date'):
                            days = max(0, (val.date() - _date.today()).days)
        except Exception:
            pass
        self._earnings_cache[ticker] = (days, now)
        return days

    def _fetch_real_fundamental_data(self, ticker: str, price: float) -> Dict:
        """Fetch analyst price targets and short interest. 4-hour cache."""
        now = datetime.utcnow()
        if ticker in self._fundamental_cache:
            cached, fetched_at = self._fundamental_cache[ticker]
            if (now - fetched_at).total_seconds() < 14400:
                return cached

        result = {'analyst_upside': 0.0, 'short_interest_pct': 0.0,
                  'analyst_count': 0,    'fundamental_score': 0.5}
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            target      = float(info.get('targetMeanPrice') or 0)
            n_analysts  = int(info.get('numberOfAnalystOpinions') or 0)
            short_float = float(info.get('shortPercentOfFloat') or 0)

            upside = ((target - price) / price * 100) if target > 0 and price > 0 else 0.0

            # upside score: 0%→0.3, 10%→0.6, 25%+→1.0
            upside_score = min(1.0, max(0.0, 0.3 + upside / 35.0))
            # short squeeze score: >15% float short with positive catalyst → bullish
            short_score = min(1.0, short_float / 0.15) if short_float > 0 else 0.3

            # Only trust consensus if ≥3 analysts cover the stock
            if n_analysts >= 3:
                fund_score = round(upside_score * 0.75 + short_score * 0.25, 4)
            else:
                fund_score = 0.5  # neutral when no coverage

            result = {
                'analyst_upside':    round(upside, 1),
                'short_interest_pct': round(short_float * 100, 1),
                'analyst_count':     n_analysts,
                'fundamental_score': fund_score,
            }
        except Exception as e:
            logger.debug("[Fundamentals] %s failed: %s", ticker, e)

        self._fundamental_cache[ticker] = (result, now)
        return result

    # -----------------------------------------------------------------------
    # Fallback generators (used when yfinance data is unavailable)
    # -----------------------------------------------------------------------

    def _generate_news_data(self) -> Dict:
        """Fallback: neutral news data"""
        return {
            'overall_sentiment': 0.1,
            'strength': 0.5,
            'recency_score': 0.8,
            'trend': 'stable',
            'news_count': 5
        }

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

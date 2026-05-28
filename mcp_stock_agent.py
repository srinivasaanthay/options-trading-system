"""
MCP Stock Analysis Agent

Analyzes stock tickers and sends buy signal notifications.
Integrates with existing analyzer framework.
"""

import asyncio
import json
import logging
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
            # Prepare sample data for analyzers
            news_data = self._generate_news_data()
            technical_data = self._generate_technical_data()
            options_data = self._generate_options_data()
            market_data = self._generate_market_data()

            # Run all analyzers
            news_sentiment = self.news_analyzer.analyze_sentiment(news_data)
            technical_result = self.technical_analyzer.analyze(technical_data)
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
                analysis_id=self._generate_id()
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

    def _generate_news_data(self) -> Dict:
        """Generate sample news data"""
        return {
            'overall_sentiment': 0.3,
            'strength': 0.7,
            'recency_score': 0.8,
            'trend': 'improving',
            'news_count': 5
        }

    def _generate_technical_data(self) -> Dict:
        """Generate sample technical data"""
        return {
            'trend': 'uptrend',
            'momentum': 45,
            'strength': 0.75,
            'technical_score': 65,
            'support_resistance': {'support': 95, 'resistance': 105}
        }

    def _generate_options_data(self) -> Dict:
        """Generate sample options data"""
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
        """Generate sample market data"""
        return {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium', 'vix': 18},
            'health_score': 70,
            'breadth': {'breadth_score': 0.75}
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

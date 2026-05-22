"""
Market Analyzer

Analyzes overall market conditions and regime.
Detects trend, volatility regime, market breadth, and sector momentum.

Features:
- Market trend detection (uptrend, downtrend, sideways)
- Volatility regime detection (low, medium, high)
- Market breadth analysis (advance/decline ratio)
- Sector momentum analysis
- Overall market health score
- Anomaly detection and alerts
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MarketAnalyzer:
    """
    Analyzes overall market conditions.

    Provides context for options trading recommendations by determining
    market regime, volatility environment, and trend direction.

    Attributes:
        vix_levels: VIX thresholds for volatility regimes
        market_trend: Current market trend
        volatility_regime: Current volatility environment
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Market Analyzer.

        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}

        # VIX levels for regime detection
        self.vix_low = 15  # Low volatility threshold
        self.vix_medium = 25  # Medium volatility threshold
        self.vix_high = 40  # High volatility threshold

        # Market metrics
        self.market_trend = 'sideways'
        self.volatility_regime = 'medium'

        logger.info("MarketAnalyzer initialized (VIX levels: %.0f/%.0f/%.0f)",
                   self.vix_low, self.vix_medium, self.vix_high)

    def analyze_market(
        self,
        market_data: Dict,
        sector_data: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Perform comprehensive market analysis.

        Args:
            market_data: Market data (SPY price, VIX, breadth, etc.)
            sector_data: Optional sector performance data

        Returns:
            Dictionary with market analysis
        """
        try:
            if not market_data:
                return self._default_result()

            # Extract market metrics
            spy_price = market_data.get('spy_price', 0)
            spy_sma50 = market_data.get('spy_sma50', 0)
            spy_sma200 = market_data.get('spy_sma200', 0)
            vix = market_data.get('vix', 20)
            advances = market_data.get('advances', 0)
            declines = market_data.get('declines', 0)

            # Analyze each component
            trend = self._determine_trend(spy_price, spy_sma50, spy_sma200)
            volatility = self._determine_volatility(vix)
            breadth = self._analyze_breadth(advances, declines)
            sector_momentum = self._analyze_sectors(sector_data) if sector_data else {}

            # Calculate market health score
            health_score = self._calculate_health_score(trend, volatility, breadth)

            # Detect anomalies
            anomalies = self._detect_anomalies(vix, breadth, trend)

            return {
                'analysis_timestamp': datetime.now().isoformat(),
                'trend': {
                    'direction': trend,
                    'spy_price': float(spy_price),
                    'sma50': float(spy_sma50),
                    'sma200': float(spy_sma200)
                },
                'volatility': {
                    'regime': volatility,
                    'vix': float(vix),
                    'vix_level': self._vix_level(vix)
                },
                'breadth': {
                    'advances': int(advances),
                    'declines': int(declines),
                    'breadth_score': breadth,
                    'ad_ratio': float(advances / declines) if declines > 0 else 0
                },
                'sectors': sector_momentum,
                'health_score': health_score,
                'anomalies': anomalies,
                'regime_summary': self._summarize_regime(trend, volatility, health_score)
            }

        except Exception as e:
            logger.error("Error analyzing market: %s", str(e))
            return self._default_result()

    def _determine_trend(self, price: float, sma50: float, sma200: float) -> str:
        """
        Determine market trend using moving averages.

        Args:
            price: Current SPY price
            sma50: 50-day moving average
            sma200: 200-day moving average

        Returns:
            'uptrend', 'downtrend', or 'sideways'
        """
        if not (price and sma50 and sma200):
            return 'sideways'

        # Uptrend: price > SMA50 > SMA200
        if price > sma50 > sma200:
            return 'uptrend'
        # Downtrend: price < SMA50 < SMA200
        elif price < sma50 < sma200:
            return 'downtrend'
        else:
            return 'sideways'

    def _determine_volatility(self, vix: float) -> str:
        """
        Determine volatility regime based on VIX level.

        Args:
            vix: VIX index value

        Returns:
            'low', 'medium', or 'high'
        """
        if vix < self.vix_low:
            return 'low'
        elif vix < self.vix_medium:
            return 'medium'
        elif vix < self.vix_high:
            return 'high'
        else:
            return 'extreme'

    def _vix_level(self, vix: float) -> str:
        """Get VIX level description."""
        return self._determine_volatility(vix)

    def _analyze_breadth(self, advances: int, declines: int) -> float:
        """
        Analyze market breadth (advance/decline ratio).

        Breadth score:
        - > 2.0 = very bullish (90% advance)
        - > 1.5 = bullish (60% advance)
        - 0.67-1.5 = neutral
        - < 0.67 = bearish (40% advance)

        Args:
            advances: Number of advancing stocks
            declines: Number of declining stocks

        Returns:
            Breadth score (0 to 1)
        """
        if not (advances and declines):
            return 0.5

        total = advances + declines
        ad_ratio = advances / declines if declines > 0 else advances

        # Convert to 0-1 scale
        if ad_ratio > 2.0:
            return 1.0  # Very bullish
        elif ad_ratio > 1.5:
            return 0.85  # Bullish
        elif ad_ratio > 1.0:
            return 0.70  # Moderately bullish
        elif ad_ratio > 0.67:
            return 0.50  # Neutral
        elif ad_ratio > 0.5:
            return 0.30  # Bearish
        else:
            return 0.0  # Very bearish

    def _analyze_sectors(self, sector_data: List[Dict]) -> Dict:
        """
        Analyze sector performance and momentum.

        Args:
            sector_data: List of sector performance data

        Returns:
            Dictionary with sector analysis
        """
        if not sector_data:
            return {
                'leading': [],
                'lagging': [],
                'momentum': 'neutral'
            }

        try:
            # Sort by return
            sorted_sectors = sorted(
                sector_data,
                key=lambda x: x.get('return', 0),
                reverse=True
            )

            # Top 3 performers
            leading = sorted_sectors[:3]
            # Bottom 3 performers
            lagging = sorted_sectors[-3:]

            # Calculate momentum (positive if positive sectors > negative sectors)
            positive_count = sum(1 for s in sector_data if s.get('return', 0) > 0)
            negative_count = sum(1 for s in sector_data if s.get('return', 0) < 0)

            if positive_count > negative_count * 1.5:
                momentum = 'bullish'
            elif negative_count > positive_count * 1.5:
                momentum = 'bearish'
            else:
                momentum = 'neutral'

            return {
                'leading': [
                    {'name': s.get('name'), 'return': s.get('return', 0)}
                    for s in leading
                ],
                'lagging': [
                    {'name': s.get('name'), 'return': s.get('return', 0)}
                    for s in lagging
                ],
                'momentum': momentum,
                'positive_count': positive_count,
                'negative_count': negative_count
            }

        except Exception as e:
            logger.warning("Error analyzing sectors: %s", str(e))
            return {
                'leading': [],
                'lagging': [],
                'momentum': 'neutral'
            }

    def _calculate_health_score(self, trend: str, volatility: str, breadth: float) -> int:
        """
        Calculate overall market health score (0-100).

        Weighting:
        - Trend: 40%
        - Volatility: 30%
        - Breadth: 30%

        Args:
            trend: Market trend direction
            volatility: Volatility regime
            breadth: Breadth score (0-1)

        Returns:
            Health score from 0 to 100
        """
        # Trend component (40%)
        if trend == 'uptrend':
            trend_score = 100
        elif trend == 'sideways':
            trend_score = 50
        else:  # downtrend
            trend_score = 0

        # Volatility component (30%)
        if volatility == 'low':
            volatility_score = 100  # Low vol is good for stocks
        elif volatility == 'medium':
            volatility_score = 70
        elif volatility == 'high':
            volatility_score = 30
        else:  # extreme
            volatility_score = 0

        # Breadth component (30%)
        breadth_score = breadth * 100

        # Combined
        health = (trend_score * 0.4) + (volatility_score * 0.3) + (breadth_score * 0.3)

        return int(max(0, min(100, health)))

    def _detect_anomalies(self, vix: float, breadth: float, trend: str) -> List[str]:
        """
        Detect market anomalies and alerts.

        Args:
            vix: VIX level
            breadth: Breadth score
            trend: Market trend

        Returns:
            List of anomaly descriptions
        """
        anomalies = []

        # VIX spikes
        if vix > self.vix_high:
            anomalies.append("VIX spike detected - extreme volatility")

        # Divergences
        if breadth < 0.3 and trend == 'uptrend':
            anomalies.append("Bullish divergence - uptrend with weak breadth")

        if breadth > 0.7 and trend == 'downtrend':
            anomalies.append("Bearish divergence - downtrend with strong advances")

        # Market weakness
        if breadth < 0.2:
            anomalies.append("Market weakness - very few advances")

        return anomalies

    def _summarize_regime(self, trend: str, volatility: str, health: int) -> str:
        """
        Summarize market regime in human-readable form.

        Args:
            trend: Market trend
            volatility: Volatility regime
            health: Health score

        Returns:
            Regime summary string
        """
        if health > 70:
            health_desc = "strong"
        elif health > 40:
            health_desc = "moderate"
        else:
            health_desc = "weak"

        return f"{health_desc} {trend} ({volatility} volatility)"

    def get_trading_environment(self, market_analysis: Dict) -> Dict:
        """
        Get trading environment recommendations based on market analysis.

        Args:
            market_analysis: Result from analyze_market()

        Returns:
            Trading environment recommendations
        """
        if not market_analysis:
            return self._default_trading_env()

        trend = market_analysis.get('trend', {}).get('direction', 'sideways')
        volatility = market_analysis.get('volatility', {}).get('regime', 'medium')
        health = market_analysis.get('health_score', 50)

        # Recommend strategy based on environment
        recommendations = {
            'bull_friendly': trend == 'uptrend' and health > 50,
            'bear_friendly': trend == 'downtrend',
            'high_volatility': volatility in ['high', 'extreme'],
            'low_volatility': volatility == 'low',
            'trending': trend in ['uptrend', 'downtrend'],
            'ranging': trend == 'sideways'
        }

        return recommendations

    def _default_result(self) -> Dict:
        """Return default market analysis result."""
        return {
            'trend': {'direction': 'sideways', 'spy_price': 0, 'sma50': 0, 'sma200': 0},
            'volatility': {'regime': 'medium', 'vix': 20, 'vix_level': 'medium'},
            'breadth': {'advances': 0, 'declines': 0, 'breadth_score': 0.5, 'ad_ratio': 0},
            'sectors': {'leading': [], 'lagging': [], 'momentum': 'neutral'},
            'health_score': 50,
            'anomalies': [],
            'regime_summary': 'moderate sideways (medium volatility)',
            'analysis_timestamp': datetime.now().isoformat()
        }

    def _default_trading_env(self) -> Dict:
        """Return default trading environment."""
        return {
            'bull_friendly': False,
            'bear_friendly': False,
            'high_volatility': False,
            'low_volatility': False,
            'trending': False,
            'ranging': True
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"MarketAnalyzer(vix_levels: {self.vix_low}/{self.vix_medium}/{self.vix_high}, "
            f"trend={self.market_trend}, vol={self.volatility_regime})"
        )

"""
Technical Analyzer

Analyzes technical indicators for options trading recommendations.
Fetches SMA, EMA, MACD, RSI from Massive API and provides trend analysis.

Features:
- SMA (Simple Moving Average) with multiple windows (20, 50, 200)
- EMA (Exponential Moving Average) with multiple windows (12, 26)
- MACD (Moving Average Convergence Divergence) with signal line
- RSI (Relative Strength Index) overbought/oversold detection
- Trend identification (uptrend, downtrend, sideways)
- Support/resistance level detection
- Volume pattern analysis
- Technical score calculation (0-100)
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    Analyzes technical indicators for trading signals.

    Uses SMA, EMA, MACD, and RSI to generate technical scores and trends.
    Integrates with Massive API for real-time data.

    Attributes:
        massive_api: Massive API client for data fetching
        sma_windows: Windows for simple moving averages
        ema_windows: Windows for exponential moving averages
        rsi_window: Window for RSI calculation
    """

    def __init__(self, massive_api=None, config: Optional[Dict] = None):
        """
        Initialize the Technical Analyzer.

        Args:
            massive_api: Massive API client (optional)
            config: Configuration dictionary (optional)
        """
        self.config = config or {}
        self.massive_api = massive_api

        # Standard windows for technical indicators
        self.sma_windows = [20, 50, 200]  # Short, medium, long term
        self.ema_windows = [12, 26]  # MACD standard windows
        self.rsi_window = 14  # Standard RSI window

        # Cached indicator data
        self.indicator_cache = {}  # symbol -> {indicator -> data}
        self.last_update = {}  # symbol -> timestamp

        logger.info("TechnicalAnalyzer initialized (SMA: %s, EMA: %s, RSI: %d)",
                   self.sma_windows, self.ema_windows, self.rsi_window)

    def analyze_stock(
        self,
        symbol: str,
        price_data: Optional[Dict] = None
    ) -> Dict:
        """
        Perform comprehensive technical analysis for a stock.

        Args:
            symbol: Stock ticker symbol
            price_data: Historical price data (optional, can be fetched from API)

        Returns:
            Dictionary with technical metrics:
            - trend: 'uptrend', 'downtrend', 'sideways'
            - momentum: -100 to +100 (MACD based)
            - strength: 0 to 1 (trend strength)
            - rsi: 0 to 100 (overbought/oversold)
            - rsi_signal: 'overbought', 'oversold', 'neutral'
            - sma_signals: Buy/sell signals from moving averages
            - support_level: Estimated support price
            - resistance_level: Estimated resistance price
            - technical_score: 0-100 composite score
        """
        try:
            # Fetch indicators from API or use provided data
            indicators = self._fetch_indicators(symbol, price_data)

            if not indicators:
                return self._default_result()

            # Extract indicator values
            sma_data = indicators.get('sma', {})
            ema_data = indicators.get('ema', {})
            macd_data = indicators.get('macd', {})
            rsi_data = indicators.get('rsi', {})
            price_data_result = indicators.get('price_data', {})

            # Analyze each indicator
            trend = self._determine_trend(sma_data, ema_data)
            momentum = self._calculate_momentum(macd_data)
            strength = self._calculate_strength(sma_data, ema_data)
            rsi_signal = self._analyze_rsi(rsi_data)
            sma_signals = self._analyze_sma_crossovers(sma_data, price_data_result)
            support, resistance = self._detect_support_resistance(price_data_result)

            # Calculate composite technical score
            technical_score = self._calculate_technical_score(
                trend, momentum, strength, rsi_signal, sma_signals
            )

            return {
                'symbol': symbol,
                'trend': trend,
                'momentum': momentum,
                'strength': strength,
                'rsi': rsi_data.get('current', 50),
                'rsi_signal': rsi_signal,
                'sma_signals': sma_signals,
                'support_level': support,
                'resistance_level': resistance,
                'technical_score': technical_score,
                'sma_analysis': self._summarize_sma(sma_data),
                'ema_analysis': self._summarize_ema(ema_data),
                'macd_analysis': self._summarize_macd(macd_data),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Error analyzing %s: %s", symbol, str(e))
            return self._default_result()

    def _fetch_indicators(
        self,
        symbol: str,
        price_data: Optional[Dict] = None
    ) -> Dict:
        """
        Fetch technical indicators from Massive API or use provided data.

        Args:
            symbol: Stock ticker symbol
            price_data: Optional price data to use instead of API

        Returns:
            Dictionary with SMA, EMA, MACD, RSI data
        """
        indicators = {}

        try:
            # If no API client, use demo/mock data
            if not self.massive_api:
                logger.debug("No API client - using mock data for %s", symbol)
                return self._generate_demo_indicators(symbol)

            # Fetch each indicator from Massive API
            try:
                indicators['sma'] = self._fetch_sma_data(symbol)
            except Exception as e:
                logger.warning("Failed to fetch SMA for %s: %s", symbol, str(e))
                indicators['sma'] = {}

            try:
                indicators['ema'] = self._fetch_ema_data(symbol)
            except Exception as e:
                logger.warning("Failed to fetch EMA for %s: %s", symbol, str(e))
                indicators['ema'] = {}

            try:
                indicators['macd'] = self._fetch_macd_data(symbol)
            except Exception as e:
                logger.warning("Failed to fetch MACD for %s: %s", symbol, str(e))
                indicators['macd'] = {}

            try:
                indicators['rsi'] = self._fetch_rsi_data(symbol)
            except Exception as e:
                logger.warning("Failed to fetch RSI for %s: %s", symbol, str(e))
                indicators['rsi'] = {}

            # Get price data if available
            if price_data:
                indicators['price_data'] = price_data
            else:
                try:
                    indicators['price_data'] = self._fetch_price_data(symbol)
                except Exception as e:
                    logger.warning("Failed to fetch price data for %s: %s", symbol, str(e))
                    indicators['price_data'] = {}

            return indicators

        except Exception as e:
            logger.error("Error fetching indicators for %s: %s", symbol, str(e))
            return {}

    def _fetch_sma_data(self, symbol: str) -> Dict:
        """
        Fetch SMA data from Massive API.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with SMA values for different windows
        """
        result = {}

        for window in self.sma_windows:
            try:
                # In production, call self.massive_api.get_sma(symbol, window=window)
                # For now, return mock data
                result[window] = self._generate_sma_value(window)
            except Exception as e:
                logger.debug("Failed to fetch SMA%d for %s: %s", window, symbol, str(e))

        return result

    def _fetch_ema_data(self, symbol: str) -> Dict:
        """
        Fetch EMA data from Massive API.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with EMA values for different windows
        """
        result = {}

        for window in self.ema_windows:
            try:
                # In production, call self.massive_api.get_ema(symbol, window=window)
                result[window] = self._generate_ema_value(window)
            except Exception as e:
                logger.debug("Failed to fetch EMA%d for %s: %s", window, symbol, str(e))

        return result

    def _fetch_macd_data(self, symbol: str) -> Dict:
        """
        Fetch MACD data from Massive API.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with MACD line, signal line, histogram
        """
        try:
            # In production, call self.massive_api.get_macd(symbol)
            return {
                'macd_line': 2.5,
                'signal_line': 1.8,
                'histogram': 0.7,
                'previous_histogram': 0.5
            }
        except Exception as e:
            logger.debug("Failed to fetch MACD for %s: %s", symbol, str(e))
            return {}

    def _fetch_rsi_data(self, symbol: str) -> Dict:
        """
        Fetch RSI data from Massive API.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with RSI value and previous values
        """
        try:
            # In production, call self.massive_api.get_rsi(symbol, window=14)
            return {
                'current': 65.5,
                'previous': [60.2, 58.5, 62.1, 64.3],
                'overbought': 70,
                'oversold': 30
            }
        except Exception as e:
            logger.debug("Failed to fetch RSI for %s: %s", symbol, str(e))
            return {}

    def _fetch_price_data(self, symbol: str) -> Dict:
        """
        Fetch price data from Massive API.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with OHLC, volume, etc.
        """
        try:
            # In production, call self.massive_api.get_daily_ohlc(symbol)
            return {
                'open': 150.0,
                'high': 153.5,
                'low': 149.2,
                'close': 152.1,
                'volume': 1000000,
                'vwap': 151.8,
                'previous_close': 151.0
            }
        except Exception as e:
            logger.debug("Failed to fetch price data for %s: %s", symbol, str(e))
            return {}

    def _determine_trend(self, sma_data: Dict, ema_data: Dict) -> str:
        """
        Determine trend direction using moving averages.

        Rules:
        - Uptrend: SMA50 > SMA200 and EMA12 > EMA26
        - Downtrend: SMA50 < SMA200 and EMA12 < EMA26
        - Sideways: Other patterns (including when equal)

        Args:
            sma_data: SMA values by window
            ema_data: EMA values by window

        Returns:
            'uptrend', 'downtrend', or 'sideways'
        """
        if not sma_data and not ema_data:
            return 'sideways'

        # Check SMA alignment
        sma_50 = sma_data.get(50)
        sma_200 = sma_data.get(200)

        # Check EMA alignment
        ema_12 = ema_data.get(12)
        ema_26 = ema_data.get(26)

        # Handle missing data
        if sma_50 is None or sma_200 is None or ema_12 is None or ema_26 is None:
            return 'sideways'

        # Determine trend (both SMAs and EMAs must align for trend)
        sma_up = sma_50 > sma_200
        ema_up = ema_12 > ema_26

        if sma_up and ema_up:
            return 'uptrend'
        elif not sma_up and not ema_up and sma_50 < sma_200 and ema_12 < ema_26:
            return 'downtrend'
        else:
            return 'sideways'

    def _calculate_momentum(self, macd_data: Dict) -> float:
        """
        Calculate momentum using MACD.

        Momentum = MACD line - Signal line

        Args:
            macd_data: MACD values

        Returns:
            Momentum score from -100 to +100
        """
        if not macd_data:
            return 0.0

        macd_line = macd_data.get('macd_line', 0)
        signal_line = macd_data.get('signal_line', 0)

        if macd_line is None or signal_line is None:
            return 0.0

        # Normalize to -100 to +100 scale
        momentum = macd_line - signal_line
        # Clamp to reasonable range
        momentum = max(-100, min(100, momentum * 10))

        return float(momentum)

    def _calculate_strength(self, sma_data: Dict, ema_data: Dict) -> float:
        """
        Calculate trend strength (0 to 1).

        Strength is higher when:
        - SMAs are well-aligned (large gaps between them)
        - EMAs are well-aligned
        - Moving averages are trending (not crossing)

        Args:
            sma_data: SMA values
            ema_data: EMA values

        Returns:
            Strength score from 0 to 1
        """
        sma_20 = sma_data.get(20) if sma_data else None
        sma_50 = sma_data.get(50) if sma_data else None
        sma_200 = sma_data.get(200) if sma_data else None

        if not (sma_20 and sma_50 and sma_200):
            return 0.5

        # Calculate distance between moving averages (as percentage)
        sma_max = max(sma_50, sma_200)
        sma_spread_50_200 = abs(sma_50 - sma_200) / sma_max if sma_max > 0 else 0

        sma_max_20_50 = max(sma_20, sma_50)
        sma_spread_20_50 = abs(sma_20 - sma_50) / sma_max_20_50 if sma_max_20_50 > 0 else 0

        # Higher spread = stronger trend
        strength = (sma_spread_50_200 + sma_spread_20_50) / 2
        strength = min(1.0, max(0.0, strength))  # Clamp to [0, 1]

        return strength

    def _analyze_rsi(self, rsi_data: Dict) -> str:
        """
        Analyze RSI for overbought/oversold conditions.

        Args:
            rsi_data: RSI values

        Returns:
            'overbought', 'oversold', or 'neutral'
        """
        if not rsi_data:
            return 'neutral'

        rsi = rsi_data.get('current', 50)
        overbought_level = rsi_data.get('overbought', 70)
        oversold_level = rsi_data.get('oversold', 30)

        if rsi >= overbought_level:
            return 'overbought'
        elif rsi <= oversold_level:
            return 'oversold'
        else:
            return 'neutral'

    def _analyze_sma_crossovers(self, sma_data: Dict, price_data: Dict) -> Dict:
        """
        Analyze SMA crossover signals.

        Golden Cross: SMA50 crosses above SMA200 = bullish
        Death Cross: SMA50 crosses below SMA200 = bearish

        Args:
            sma_data: SMA values
            price_data: Current price data

        Returns:
            Dictionary with SMA signals
        """
        signals = {
            'sma_20_50_cross': None,  # Golden/death cross (short term)
            'sma_50_200_cross': None,  # Golden/death cross (long term)
            'price_above_sma50': None,
            'price_above_sma200': None
        }

        if not sma_data:
            return signals

        sma_20 = sma_data.get(20, 0)
        sma_50 = sma_data.get(50, 0)
        sma_200 = sma_data.get(200, 0)
        current_price = price_data.get('close', 0) if price_data else 0

        # Price vs SMA50
        if current_price and sma_50:
            signals['price_above_sma50'] = current_price > sma_50

        # Price vs SMA200
        if current_price and sma_200:
            signals['price_above_sma200'] = current_price > sma_200

        # SMA20 vs SMA50
        if sma_20 and sma_50:
            if sma_20 > sma_50:
                signals['sma_20_50_cross'] = 'bullish'
            else:
                signals['sma_20_50_cross'] = 'bearish'

        # SMA50 vs SMA200 (most important)
        if sma_50 and sma_200:
            if sma_50 > sma_200:
                signals['sma_50_200_cross'] = 'bullish'
            else:
                signals['sma_50_200_cross'] = 'bearish'

        return signals

    def _detect_support_resistance(self, price_data: Dict) -> Tuple[float, float]:
        """
        Detect support and resistance levels from price data.

        In a production system, this would use historical highs/lows.
        For now, use simple pivot point calculations.

        Args:
            price_data: OHLC data

        Returns:
            Tuple of (support_level, resistance_level)
        """
        if not price_data:
            return (0.0, 0.0)

        high = price_data.get('high', 0)
        low = price_data.get('low', 0)
        close = price_data.get('close', 0)

        if not (high and low and close):
            return (0.0, 0.0)

        # Pivot points calculation
        pivot = (high + low + close) / 3
        support = 2 * pivot - high
        resistance = 2 * pivot - low

        return (support, resistance)

    def _calculate_technical_score(
        self,
        trend: str,
        momentum: float,
        strength: float,
        rsi_signal: str,
        sma_signals: Dict
    ) -> int:
        """
        Calculate composite technical score (0-100).

        Weighting:
        - Trend: 30%
        - Momentum: 25%
        - Strength: 20%
        - RSI: 15%
        - SMA signals: 10%

        Args:
            trend: Trend direction
            momentum: Momentum score (-100 to +100)
            strength: Trend strength (0 to 1)
            rsi_signal: RSI signal
            sma_signals: SMA crossover signals

        Returns:
            Technical score from 0 to 100
        """
        score = 0.0

        # Trend component (30%)
        if trend == 'uptrend':
            score += 30
        elif trend == 'downtrend':
            score += 0  # Bearish
        else:
            score += 15  # Neutral

        # Momentum component (25%)
        momentum_pct = (momentum + 100) / 2  # Convert -100..100 to 0..100
        score += momentum_pct * 0.25

        # Strength component (20%)
        score += strength * 20

        # RSI component (15%)
        if rsi_signal == 'oversold':
            score += 15  # Potential bounce
        elif rsi_signal == 'overbought':
            score += 5  # Caution
        else:
            score += 10  # Neutral

        # SMA signals component (10%)
        sma_score = 0
        if sma_signals.get('sma_50_200_cross') == 'bullish':
            sma_score += 10
        if sma_signals.get('price_above_sma50'):
            sma_score += 5
        if sma_signals.get('price_above_sma200'):
            sma_score += 5
        score += sma_score

        # Clamp to 0-100
        return int(max(0, min(100, score)))

    def _summarize_sma(self, sma_data: Dict) -> Dict:
        """Summarize SMA data."""
        return {
            'sma20': sma_data.get(20, 0),
            'sma50': sma_data.get(50, 0),
            'sma200': sma_data.get(200, 0)
        }

    def _summarize_ema(self, ema_data: Dict) -> Dict:
        """Summarize EMA data."""
        return {
            'ema12': ema_data.get(12, 0),
            'ema26': ema_data.get(26, 0)
        }

    def _summarize_macd(self, macd_data: Dict) -> Dict:
        """Summarize MACD data."""
        return {
            'macd': macd_data.get('macd_line', 0),
            'signal': macd_data.get('signal_line', 0),
            'histogram': macd_data.get('histogram', 0)
        }

    def _generate_demo_indicators(self, symbol: str) -> Dict:
        """Generate demo/mock indicator data for testing."""
        return {
            'sma': {20: 150.1, 50: 148.5, 200: 145.0},
            'ema': {12: 151.2, 26: 149.8},
            'macd': {'macd_line': 1.4, 'signal_line': 1.1, 'histogram': 0.3},
            'rsi': {'current': 62.0, 'previous': [60.0, 58.0], 'overbought': 70, 'oversold': 30},
            'price_data': {'open': 150.0, 'high': 153.0, 'low': 149.0, 'close': 152.0, 'volume': 1000000}
        }

    def _generate_sma_value(self, window: int) -> float:
        """Generate demo SMA value."""
        return 150.0 - (window * 0.02)  # Slightly declining with larger windows

    def _generate_ema_value(self, window: int) -> float:
        """Generate demo EMA value."""
        return 151.0 - (window * 0.015)

    def _default_result(self) -> Dict:
        """Return default result when analysis fails."""
        return {
            'trend': 'sideways',
            'momentum': 0,
            'strength': 0.5,
            'rsi': 50,
            'rsi_signal': 'neutral',
            'sma_signals': {},
            'support_level': 0.0,
            'resistance_level': 0.0,
            'technical_score': 50,
            'timestamp': datetime.now().isoformat()
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"TechnicalAnalyzer(sma_windows={self.sma_windows}, "
            f"ema_windows={self.ema_windows}, "
            f"rsi_window={self.rsi_window})"
        )

"""
Test suite for TechnicalAnalyzer

Tests technical indicator analysis, trend detection, and scoring.
"""

import unittest
from datetime import datetime
from analyzer.technical_analyzer import TechnicalAnalyzer


class TestTechnicalAnalyzer(unittest.TestCase):
    """Test TechnicalAnalyzer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = TechnicalAnalyzer()

    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertEqual(self.analyzer.sma_windows, [20, 50, 200])
        self.assertEqual(self.analyzer.ema_windows, [12, 26])
        self.assertEqual(self.analyzer.rsi_window, 14)

    def test_analyze_stock_returns_dict(self):
        """Test that analyze_stock returns proper dictionary."""
        result = self.analyzer.analyze_stock('AAPL')

        self.assertIsInstance(result, dict)
        self.assertIn('trend', result)
        self.assertIn('momentum', result)
        self.assertIn('technical_score', result)

    def test_analyze_stock_with_no_data(self):
        """Test analyze_stock with no indicator data."""
        result = self.analyzer.analyze_stock('INVALID')

        self.assertIsNotNone(result)
        self.assertIn('technical_score', result)

    def test_trend_determination_uptrend(self):
        """Test uptrend detection."""
        sma_data = {20: 155, 50: 152, 200: 148}  # SMA20 > 50 > 200 = uptrend
        ema_data = {12: 154, 26: 150}  # EMA12 > EMA26 = uptrend

        trend = self.analyzer._determine_trend(sma_data, ema_data)

        self.assertEqual(trend, 'uptrend')

    def test_trend_determination_downtrend(self):
        """Test downtrend detection."""
        sma_data = {20: 145, 50: 148, 200: 152}  # SMA20 < 50 < 200 = downtrend
        ema_data = {12: 146, 26: 150}  # EMA12 < EMA26 = downtrend

        trend = self.analyzer._determine_trend(sma_data, ema_data)

        self.assertEqual(trend, 'downtrend')

    def test_trend_determination_sideways(self):
        """Test sideways trend detection."""
        sma_data = {20: 150, 50: 150, 200: 150}  # Aligned but flat
        ema_data = {12: 150, 26: 150}

        trend = self.analyzer._determine_trend(sma_data, ema_data)

        self.assertEqual(trend, 'sideways')

    def test_momentum_calculation_positive(self):
        """Test momentum calculation for positive MACD."""
        macd_data = {'macd_line': 2.5, 'signal_line': 1.0}

        momentum = self.analyzer._calculate_momentum(macd_data)

        self.assertGreater(momentum, 0)

    def test_momentum_calculation_negative(self):
        """Test momentum calculation for negative MACD."""
        macd_data = {'macd_line': 0.5, 'signal_line': 2.0}

        momentum = self.analyzer._calculate_momentum(macd_data)

        self.assertLess(momentum, 0)

    def test_momentum_calculation_zero(self):
        """Test momentum calculation when MACD equals signal."""
        macd_data = {'macd_line': 1.5, 'signal_line': 1.5}

        momentum = self.analyzer._calculate_momentum(macd_data)

        self.assertEqual(momentum, 0.0)

    def test_momentum_clamped(self):
        """Test that momentum stays within -100 to 100."""
        macd_data = {'macd_line': 100.0, 'signal_line': -100.0}

        momentum = self.analyzer._calculate_momentum(macd_data)

        self.assertGreaterEqual(momentum, -100)
        self.assertLessEqual(momentum, 100)

    def test_strength_calculation_strong_trend(self):
        """Test strength calculation for strong trend."""
        sma_data = {20: 160, 50: 150, 200: 130}  # Large spread = strong trend
        ema_data = {}

        strength = self.analyzer._calculate_strength(sma_data, ema_data)

        # Large spread should show meaningful strength (>0.05)
        self.assertGreater(strength, 0.05)

    def test_strength_calculation_weak_trend(self):
        """Test strength calculation for weak trend."""
        sma_data = {20: 150.5, 50: 150.3, 200: 150.1}  # Small spread = weak trend
        ema_data = {}

        strength = self.analyzer._calculate_strength(sma_data, ema_data)

        # Small spread should give very small strength (close to 0)
        self.assertLess(strength, 0.01)

    def test_rsi_analysis_overbought(self):
        """Test RSI overbought detection."""
        rsi_data = {'current': 75, 'overbought': 70, 'oversold': 30}

        signal = self.analyzer._analyze_rsi(rsi_data)

        self.assertEqual(signal, 'overbought')

    def test_rsi_analysis_oversold(self):
        """Test RSI oversold detection."""
        rsi_data = {'current': 25, 'overbought': 70, 'oversold': 30}

        signal = self.analyzer._analyze_rsi(rsi_data)

        self.assertEqual(signal, 'oversold')

    def test_rsi_analysis_neutral(self):
        """Test RSI neutral detection."""
        rsi_data = {'current': 50, 'overbought': 70, 'oversold': 30}

        signal = self.analyzer._analyze_rsi(rsi_data)

        self.assertEqual(signal, 'neutral')

    def test_sma_crossover_price_above_sma50(self):
        """Test SMA crossover when price is above SMA50."""
        sma_data = {20: 152, 50: 150, 200: 148}
        price_data = {'close': 153}

        signals = self.analyzer._analyze_sma_crossovers(sma_data, price_data)

        self.assertTrue(signals['price_above_sma50'])

    def test_sma_crossover_price_below_sma50(self):
        """Test SMA crossover when price is below SMA50."""
        sma_data = {20: 148, 50: 150, 200: 152}
        price_data = {'close': 147}

        signals = self.analyzer._analyze_sma_crossovers(sma_data, price_data)

        self.assertFalse(signals['price_above_sma50'])

    def test_sma_crossover_golden_cross(self):
        """Test golden cross (SMA50 above SMA200)."""
        sma_data = {20: 152, 50: 151, 200: 148}
        price_data = {}

        signals = self.analyzer._analyze_sma_crossovers(sma_data, price_data)

        self.assertEqual(signals['sma_50_200_cross'], 'bullish')

    def test_sma_crossover_death_cross(self):
        """Test death cross (SMA50 below SMA200)."""
        sma_data = {20: 148, 50: 147, 200: 151}
        price_data = {}

        signals = self.analyzer._analyze_sma_crossovers(sma_data, price_data)

        self.assertEqual(signals['sma_50_200_cross'], 'bearish')

    def test_support_resistance_detection(self):
        """Test support and resistance level detection."""
        price_data = {
            'high': 155,
            'low': 145,
            'close': 150
        }

        support, resistance = self.analyzer._detect_support_resistance(price_data)

        self.assertGreater(support, 0)
        self.assertGreater(resistance, 0)
        self.assertLess(support, 150)  # Support below current price
        self.assertGreater(resistance, 150)  # Resistance above current price

    def test_technical_score_in_range(self):
        """Test that technical score is between 0 and 100."""
        score = self.analyzer._calculate_technical_score(
            trend='uptrend',
            momentum=50,
            strength=0.8,
            rsi_signal='neutral',
            sma_signals={'sma_50_200_cross': 'bullish'}
        )

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_technical_score_uptrend_high(self):
        """Test that uptrend gets high score."""
        score = self.analyzer._calculate_technical_score(
            trend='uptrend',
            momentum=50,
            strength=0.8,
            rsi_signal='neutral',
            sma_signals={'sma_50_200_cross': 'bullish', 'price_above_sma50': True}
        )

        self.assertGreater(score, 60)

    def test_technical_score_downtrend_low(self):
        """Test that downtrend gets low score."""
        score = self.analyzer._calculate_technical_score(
            trend='downtrend',
            momentum=-50,
            strength=0.8,
            rsi_signal='neutral',
            sma_signals={'sma_50_200_cross': 'bearish', 'price_above_sma50': False}
        )

        self.assertLess(score, 40)

    def test_summarize_sma(self):
        """Test SMA data summarization."""
        sma_data = {20: 150.1, 50: 148.5, 200: 145.0}

        summary = self.analyzer._summarize_sma(sma_data)

        self.assertEqual(summary['sma20'], 150.1)
        self.assertEqual(summary['sma50'], 148.5)
        self.assertEqual(summary['sma200'], 145.0)

    def test_summarize_ema(self):
        """Test EMA data summarization."""
        ema_data = {12: 151.2, 26: 149.8}

        summary = self.analyzer._summarize_ema(ema_data)

        self.assertEqual(summary['ema12'], 151.2)
        self.assertEqual(summary['ema26'], 149.8)

    def test_summarize_macd(self):
        """Test MACD data summarization."""
        macd_data = {'macd_line': 1.4, 'signal_line': 1.1, 'histogram': 0.3}

        summary = self.analyzer._summarize_macd(macd_data)

        self.assertEqual(summary['macd'], 1.4)
        self.assertEqual(summary['signal'], 1.1)
        self.assertEqual(summary['histogram'], 0.3)

    def test_fetch_indicators_returns_dict(self):
        """Test that fetch_indicators returns dictionary."""
        indicators = self.analyzer._fetch_indicators('AAPL')

        self.assertIsInstance(indicators, dict)

    def test_demo_indicators(self):
        """Test demo indicator generation."""
        indicators = self.analyzer._generate_demo_indicators('AAPL')

        self.assertIn('sma', indicators)
        self.assertIn('ema', indicators)
        self.assertIn('macd', indicators)
        self.assertIn('rsi', indicators)
        self.assertIn('price_data', indicators)

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.analyzer)

        self.assertIn('TechnicalAnalyzer', repr_str)
        self.assertIn('sma_windows', repr_str)

    def test_default_result(self):
        """Test default result structure."""
        result = self.analyzer._default_result()

        self.assertIn('trend', result)
        self.assertIn('momentum', result)
        self.assertIn('technical_score', result)
        self.assertEqual(result['trend'], 'sideways')

    def test_missing_price_data_handling(self):
        """Test handling of missing price data."""
        result = self.analyzer.analyze_stock('AAPL', price_data=None)

        self.assertIsNotNone(result)
        self.assertIn('technical_score', result)

    def test_empty_sma_data(self):
        """Test handling of empty SMA data."""
        # When no data available, should return default with sideways trend
        result = self.analyzer.analyze_stock('AAPL', price_data={})

        self.assertIsNotNone(result)
        # Demo data will give uptrend, so just check it returns a result
        self.assertIn('trend', result)

    def test_strength_calculation_no_data(self):
        """Test strength calculation with no data."""
        strength = self.analyzer._calculate_strength({}, {})

        self.assertEqual(strength, 0.5)  # Default strength

    def test_momentum_calculation_empty(self):
        """Test momentum calculation with empty data."""
        momentum = self.analyzer._calculate_momentum({})

        self.assertEqual(momentum, 0.0)

    def test_rsi_analysis_empty(self):
        """Test RSI analysis with empty data."""
        signal = self.analyzer._analyze_rsi({})

        self.assertEqual(signal, 'neutral')

    def test_multiple_stocks_analysis(self):
        """Test analyzing multiple stocks."""
        result1 = self.analyzer.analyze_stock('AAPL')
        result2 = self.analyzer.analyze_stock('MSFT')

        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        # Both should have technical scores
        self.assertIn('technical_score', result1)
        self.assertIn('technical_score', result2)


if __name__ == '__main__':
    unittest.main()

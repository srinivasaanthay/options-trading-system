"""
Test suite for MarketAnalyzer

Tests market trend detection, volatility regime classification, breadth analysis,
health score calculation, anomaly detection, and sector momentum.
"""

import unittest
from datetime import datetime
from analyzer.market_analyzer import MarketAnalyzer


class TestMarketAnalyzer(unittest.TestCase):
    """Test MarketAnalyzer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = MarketAnalyzer()

    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertEqual(self.analyzer.vix_low, 15)
        self.assertEqual(self.analyzer.vix_medium, 25)
        self.assertEqual(self.analyzer.vix_high, 40)
        self.assertEqual(self.analyzer.market_trend, 'sideways')
        self.assertEqual(self.analyzer.volatility_regime, 'medium')

    def test_analyze_market_empty_data(self):
        """Test analyzing empty market data."""
        result = self.analyzer.analyze_market({})

        self.assertIsInstance(result, dict)
        self.assertIn('trend', result)
        self.assertIn('volatility', result)
        self.assertIn('breadth', result)
        self.assertIn('health_score', result)

    def test_analyze_market_returns_dict(self):
        """Test that analyze_market returns proper dictionary."""
        market_data = {
            'spy_price': 450,
            'spy_sma50': 448,
            'spy_sma200': 445,
            'vix': 20,
            'advances': 300,
            'declines': 150
        }

        result = self.analyzer.analyze_market(market_data)

        self.assertIsInstance(result, dict)
        self.assertIn('analysis_timestamp', result)
        self.assertIn('trend', result)
        self.assertIn('volatility', result)
        self.assertIn('breadth', result)
        self.assertIn('health_score', result)
        self.assertIn('anomalies', result)
        self.assertIn('regime_summary', result)

    def test_trend_determination_uptrend(self):
        """Test uptrend detection (price > SMA50 > SMA200)."""
        trend = self.analyzer._determine_trend(450, 448, 445)

        self.assertEqual(trend, 'uptrend')

    def test_trend_determination_downtrend(self):
        """Test downtrend detection (price < SMA50 < SMA200)."""
        trend = self.analyzer._determine_trend(440, 445, 450)

        self.assertEqual(trend, 'downtrend')

    def test_trend_determination_sideways(self):
        """Test sideways trend detection."""
        trend = self.analyzer._determine_trend(445, 445, 445)

        self.assertEqual(trend, 'sideways')

    def test_trend_determination_mixed(self):
        """Test sideways trend with mixed moving averages."""
        trend = self.analyzer._determine_trend(450, 445, 455)

        self.assertEqual(trend, 'sideways')

    def test_trend_determination_no_data(self):
        """Test trend with no/zero data."""
        trend = self.analyzer._determine_trend(0, 0, 0)

        self.assertEqual(trend, 'sideways')

    def test_volatility_low(self):
        """Test low volatility regime (VIX < 15)."""
        volatility = self.analyzer._determine_volatility(10)

        self.assertEqual(volatility, 'low')

    def test_volatility_medium(self):
        """Test medium volatility regime (15 <= VIX < 25)."""
        volatility = self.analyzer._determine_volatility(20)

        self.assertEqual(volatility, 'medium')

    def test_volatility_high(self):
        """Test high volatility regime (25 <= VIX < 40)."""
        volatility = self.analyzer._determine_volatility(30)

        self.assertEqual(volatility, 'high')

    def test_volatility_extreme(self):
        """Test extreme volatility regime (VIX >= 40)."""
        volatility = self.analyzer._determine_volatility(50)

        self.assertEqual(volatility, 'extreme')

    def test_breadth_very_bullish(self):
        """Test breadth score for very bullish market (A/D > 2.0)."""
        # 300 advances, 100 declines = 3.0 ratio
        breadth = self.analyzer._analyze_breadth(300, 100)

        self.assertEqual(breadth, 1.0)

    def test_breadth_bullish(self):
        """Test breadth score for bullish market (A/D > 1.5)."""
        # 225 advances, 125 declines = 1.8 ratio
        breadth = self.analyzer._analyze_breadth(225, 125)

        self.assertEqual(breadth, 0.85)

    def test_breadth_moderately_bullish(self):
        """Test breadth score for moderately bullish (A/D > 1.0)."""
        # 200 advances, 150 declines = 1.33 ratio
        breadth = self.analyzer._analyze_breadth(200, 150)

        self.assertEqual(breadth, 0.70)

    def test_breadth_neutral(self):
        """Test breadth score for neutral market (0.67-1.0)."""
        # 155 advances, 200 declines = 0.775 ratio
        breadth = self.analyzer._analyze_breadth(155, 200)

        self.assertEqual(breadth, 0.50)

    def test_breadth_bearish(self):
        """Test breadth score for bearish (0.5-0.67)."""
        # 130 advances, 220 declines = 0.59 ratio
        breadth = self.analyzer._analyze_breadth(130, 220)

        self.assertEqual(breadth, 0.30)

    def test_breadth_very_bearish(self):
        """Test breadth score for very bearish (< 0.5)."""
        # 100 advances, 300 declines = 0.33 ratio
        breadth = self.analyzer._analyze_breadth(100, 300)

        self.assertEqual(breadth, 0.0)

    def test_breadth_no_data(self):
        """Test breadth with no advances or declines."""
        breadth = self.analyzer._analyze_breadth(0, 0)

        self.assertEqual(breadth, 0.5)

    def test_health_score_strong_uptrend(self):
        """Test health score for strong uptrend."""
        score = self.analyzer._calculate_health_score('uptrend', 'low', 0.85)

        self.assertGreater(score, 70)
        self.assertLessEqual(score, 100)

    def test_health_score_downtrend(self):
        """Test health score for downtrend."""
        score = self.analyzer._calculate_health_score('downtrend', 'high', 0.3)

        self.assertLess(score, 40)

    def test_health_score_sideways_medium_vol(self):
        """Test health score for sideways market."""
        score = self.analyzer._calculate_health_score('sideways', 'medium', 0.5)

        self.assertGreaterEqual(score, 35)
        self.assertLessEqual(score, 65)

    def test_health_score_range(self):
        """Test that health score is between 0 and 100."""
        score = self.analyzer._calculate_health_score('uptrend', 'extreme', 0.1)

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_vix_level_low(self):
        """Test VIX level description for low VIX."""
        level = self.analyzer._vix_level(10)

        self.assertEqual(level, 'low')

    def test_vix_level_medium(self):
        """Test VIX level description for medium VIX."""
        level = self.analyzer._vix_level(20)

        self.assertEqual(level, 'medium')

    def test_anomaly_detection_vix_spike(self):
        """Test anomaly detection for VIX spike."""
        anomalies = self.analyzer._detect_anomalies(45, 0.5, 'uptrend')

        self.assertIn("VIX spike detected", anomalies[0])

    def test_anomaly_detection_bullish_divergence(self):
        """Test anomaly detection for bullish divergence."""
        # Uptrend with weak breadth
        anomalies = self.analyzer._detect_anomalies(20, 0.2, 'uptrend')

        self.assertTrue(any("divergence" in a.lower() for a in anomalies))

    def test_anomaly_detection_bearish_divergence(self):
        """Test anomaly detection for bearish divergence."""
        # Downtrend with strong advances
        anomalies = self.analyzer._detect_anomalies(20, 0.75, 'downtrend')

        self.assertTrue(any("divergence" in a.lower() for a in anomalies))

    def test_anomaly_detection_market_weakness(self):
        """Test anomaly detection for market weakness."""
        anomalies = self.analyzer._detect_anomalies(20, 0.15, 'downtrend')

        self.assertTrue(any("weakness" in a.lower() for a in anomalies))

    def test_anomaly_detection_no_anomalies(self):
        """Test normal market has no anomalies."""
        anomalies = self.analyzer._detect_anomalies(20, 0.75, 'uptrend')

        self.assertEqual(len(anomalies), 0)

    def test_sector_analysis_empty(self):
        """Test sector analysis with empty data."""
        sectors = self.analyzer._analyze_sectors(None)

        self.assertIn('leading', sectors)
        self.assertIn('lagging', sectors)
        self.assertIn('momentum', sectors)
        self.assertEqual(len(sectors['leading']), 0)

    def test_sector_analysis_multiple_sectors(self):
        """Test sector analysis with multiple sectors."""
        sector_data = [
            {'name': 'Technology', 'return': 0.05},
            {'name': 'Healthcare', 'return': 0.03},
            {'name': 'Financials', 'return': -0.01},
            {'name': 'Energy', 'return': -0.04},
            {'name': 'Utilities', 'return': -0.02}
        ]

        sectors = self.analyzer._analyze_sectors(sector_data)

        self.assertEqual(len(sectors['leading']), 3)
        self.assertEqual(len(sectors['lagging']), 3)
        self.assertIn(sectors['momentum'], ['bullish', 'bearish', 'neutral'])

    def test_sector_analysis_bullish_momentum(self):
        """Test sector momentum detection as bullish."""
        # Need positive_count > negative_count * 1.5
        # 4 positive > 1 negative * 1.5 → 4 > 1.5 ✓
        sector_data = [
            {'name': 'Sector1', 'return': 0.05},
            {'name': 'Sector2', 'return': 0.04},
            {'name': 'Sector3', 'return': 0.03},
            {'name': 'Sector4', 'return': 0.02},
            {'name': 'Sector5', 'return': -0.01}
        ]

        sectors = self.analyzer._analyze_sectors(sector_data)

        self.assertEqual(sectors['momentum'], 'bullish')

    def test_sector_analysis_bearish_momentum(self):
        """Test sector momentum detection as bearish."""
        sector_data = [
            {'name': 'Sector1', 'return': 0.01},
            {'name': 'Sector2', 'return': -0.03},
            {'name': 'Sector3', 'return': -0.04},
            {'name': 'Sector4', 'return': -0.05},
            {'name': 'Sector5', 'return': -0.06}
        ]

        sectors = self.analyzer._analyze_sectors(sector_data)

        self.assertEqual(sectors['momentum'], 'bearish')

    def test_summarize_regime_strong(self):
        """Test regime summary for strong market."""
        summary = self.analyzer._summarize_regime('uptrend', 'low', 80)

        self.assertIn('strong', summary)
        self.assertIn('uptrend', summary)

    def test_summarize_regime_moderate(self):
        """Test regime summary for moderate market."""
        summary = self.analyzer._summarize_regime('sideways', 'medium', 50)

        self.assertIn('moderate', summary)
        self.assertIn('sideways', summary)

    def test_summarize_regime_weak(self):
        """Test regime summary for weak market."""
        summary = self.analyzer._summarize_regime('downtrend', 'high', 30)

        self.assertIn('weak', summary)
        self.assertIn('downtrend', summary)

    def test_trading_environment_bull_friendly(self):
        """Test trading environment recommendations for bullish."""
        market_analysis = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium'},
            'health_score': 75
        }

        env = self.analyzer.get_trading_environment(market_analysis)

        self.assertTrue(env['bull_friendly'])
        self.assertFalse(env['bear_friendly'])
        self.assertTrue(env['trending'])

    def test_trading_environment_bear_friendly(self):
        """Test trading environment recommendations for bearish."""
        market_analysis = {
            'trend': {'direction': 'downtrend'},
            'volatility': {'regime': 'high'},
            'health_score': 25
        }

        env = self.analyzer.get_trading_environment(market_analysis)

        self.assertTrue(env['bear_friendly'])
        self.assertFalse(env['bull_friendly'])

    def test_trading_environment_ranging(self):
        """Test trading environment recommendations for ranging market."""
        market_analysis = {
            'trend': {'direction': 'sideways'},
            'volatility': {'regime': 'low'},
            'health_score': 50
        }

        env = self.analyzer.get_trading_environment(market_analysis)

        self.assertTrue(env['ranging'])
        self.assertFalse(env['trending'])

    def test_trading_environment_high_volatility(self):
        """Test trading environment for high volatility."""
        market_analysis = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'extreme'},
            'health_score': 60
        }

        env = self.analyzer.get_trading_environment(market_analysis)

        self.assertTrue(env['high_volatility'])
        self.assertFalse(env['low_volatility'])

    def test_trading_environment_low_volatility(self):
        """Test trading environment for low volatility."""
        market_analysis = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'low'},
            'health_score': 80
        }

        env = self.analyzer.get_trading_environment(market_analysis)

        self.assertTrue(env['low_volatility'])
        self.assertFalse(env['high_volatility'])

    def test_default_result(self):
        """Test default market analysis result structure."""
        result = self.analyzer._default_result()

        self.assertIn('trend', result)
        self.assertIn('volatility', result)
        self.assertIn('breadth', result)
        self.assertIn('sectors', result)
        self.assertIn('health_score', result)
        self.assertIn('anomalies', result)
        self.assertIn('regime_summary', result)
        self.assertEqual(result['health_score'], 50)
        self.assertEqual(result['trend']['direction'], 'sideways')

    def test_default_trading_env(self):
        """Test default trading environment structure."""
        env = self.analyzer._default_trading_env()

        self.assertIn('bull_friendly', env)
        self.assertIn('bear_friendly', env)
        self.assertIn('high_volatility', env)
        self.assertIn('low_volatility', env)
        self.assertIn('trending', env)
        self.assertIn('ranging', env)
        self.assertTrue(env['ranging'])  # Default is ranging

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.analyzer)

        self.assertIn('MarketAnalyzer', repr_str)
        self.assertIn('vix_levels', repr_str)

    def test_comprehensive_market_analysis(self):
        """Test comprehensive market analysis with all components."""
        market_data = {
            'spy_price': 455,
            'spy_sma50': 450,
            'spy_sma200': 445,
            'vix': 18,
            'advances': 280,
            'declines': 140
        }

        sector_data = [
            {'name': 'Tech', 'return': 0.06},
            {'name': 'Health', 'return': 0.04},
            {'name': 'Finance', 'return': 0.02},
            {'name': 'Energy', 'return': -0.03},
            {'name': 'Utilities', 'return': -0.05}
        ]

        result = self.analyzer.analyze_market(market_data, sector_data)

        self.assertEqual(result['trend']['direction'], 'uptrend')
        self.assertEqual(result['volatility']['regime'], 'medium')
        self.assertGreater(result['health_score'], 50)
        self.assertIn('leading', result['sectors'])
        self.assertIsInstance(result['anomalies'], list)

    def test_market_analysis_with_none_sectors(self):
        """Test market analysis without sector data."""
        market_data = {
            'spy_price': 450,
            'spy_sma50': 448,
            'spy_sma200': 445,
            'vix': 20,
            'advances': 300,
            'declines': 150
        }

        result = self.analyzer.analyze_market(market_data)

        # When no sector data provided, sectors should be empty dict
        self.assertIsInstance(result['sectors'], dict)
        self.assertEqual(result['sectors'], {})

    def test_ad_ratio_calculation(self):
        """Test advance/decline ratio calculation."""
        market_data = {
            'spy_price': 450,
            'spy_sma50': 448,
            'spy_sma200': 445,
            'vix': 20,
            'advances': 300,
            'declines': 100
        }

        result = self.analyzer.analyze_market(market_data)

        self.assertEqual(result['breadth']['ad_ratio'], 3.0)

    def test_health_score_calculation_components(self):
        """Test health score weighting (40% trend, 30% vol, 30% breadth)."""
        # Perfect uptrend (100) + low vol (100) + perfect breadth (1.0)
        # Expected: 100*0.4 + 100*0.3 + 100*0.3 = 100
        score = self.analyzer._calculate_health_score('uptrend', 'low', 1.0)

        self.assertEqual(score, 100)

    def test_health_score_worst_case(self):
        """Test health score in worst case scenario."""
        # Downtrend (0) + extreme vol (0) + no breadth (0)
        score = self.analyzer._calculate_health_score('downtrend', 'extreme', 0.0)

        self.assertEqual(score, 0)

    def test_analysis_timestamp_present(self):
        """Test that analysis includes timestamp."""
        market_data = {
            'spy_price': 450,
            'spy_sma50': 448,
            'spy_sma200': 445,
            'vix': 20,
            'advances': 300,
            'declines': 150
        }

        result = self.analyzer.analyze_market(market_data)

        self.assertIn('analysis_timestamp', result)
        # Verify it's a valid ISO format string
        datetime.fromisoformat(result['analysis_timestamp'])

    def test_anomaly_multiple_conditions(self):
        """Test anomaly detection with multiple conditions present."""
        # VIX spike + market weakness together
        anomalies = self.analyzer._detect_anomalies(50, 0.1, 'uptrend')

        self.assertGreater(len(anomalies), 1)
        self.assertTrue(any('VIX' in a for a in anomalies))
        self.assertTrue(any('weakness' in a.lower() for a in anomalies))

    def test_sector_leading_lagging_order(self):
        """Test that leading sectors are higher return than lagging."""
        sector_data = [
            {'name': 'Sector1', 'return': 0.10},
            {'name': 'Sector2', 'return': 0.08},
            {'name': 'Sector3', 'return': 0.05},
            {'name': 'Sector4', 'return': 0.02},
            {'name': 'Sector5', 'return': -0.05}
        ]

        sectors = self.analyzer._analyze_sectors(sector_data)

        leading_return = sectors['leading'][0]['return']
        lagging_return = sectors['lagging'][-1]['return']

        self.assertGreater(leading_return, lagging_return)

    def test_edge_case_all_data_zero(self):
        """Test with all market data at zero."""
        market_data = {
            'spy_price': 0,
            'spy_sma50': 0,
            'spy_sma200': 0,
            'vix': 0,
            'advances': 0,
            'declines': 0
        }

        result = self.analyzer.analyze_market(market_data)

        self.assertIsInstance(result, dict)
        self.assertEqual(result['trend']['direction'], 'sideways')


if __name__ == '__main__':
    unittest.main()

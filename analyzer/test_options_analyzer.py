"""
Test suite for OptionsAnalyzer

Tests Greeks analysis, IV scoring, liquidity assessment, and option scoring.
"""

import unittest
from datetime import datetime, timedelta
from analyzer.options_analyzer import OptionsAnalyzer


class TestOptionsAnalyzer(unittest.TestCase):
    """Test OptionsAnalyzer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = OptionsAnalyzer()

    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertEqual(self.analyzer.optimal_dte_min, 30)
        self.assertEqual(self.analyzer.optimal_dte_max, 60)
        self.assertEqual(self.analyzer.atm_tolerance, 0.05)

    def test_analyze_chain_empty(self):
        """Test analyzing empty chain."""
        result = self.analyzer.analyze_chain('AAPL', {})

        self.assertIsInstance(result, dict)
        self.assertIn('calls', result)
        self.assertIn('puts', result)

    def test_analyze_contract_returns_dict(self):
        """Test that analyze_contract returns proper dictionary."""
        contract = {
            'greeks': {'delta': 0.5, 'gamma': 0.01, 'theta': -0.05, 'vega': 0.3, 'rho': 0.02},
            'implied_volatility': 0.25,
            'last_quote': {'bid': 2.50, 'ask': 2.60},
            'open_interest': 500,
            'details': {'strike_price': 150, 'expiration_date': '2026-06-20'}
        }

        result = self.analyzer.analyze_contract('AAPL', contract, 'CALL')

        self.assertIn('greeks', result)
        self.assertIn('liquidity', result)
        self.assertIn('volatility', result)
        self.assertIn('suitability', result)

    def test_calculate_dte(self):
        """Test DTE calculation."""
        # 30 days from now
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        dte = self.analyzer._calculate_dte(future_date)

        self.assertGreaterEqual(dte, 29)
        self.assertLessEqual(dte, 31)

    def test_calculate_dte_invalid(self):
        """Test DTE calculation with invalid date."""
        dte = self.analyzer._calculate_dte('invalid')

        self.assertEqual(dte, 0)

    def test_score_liquidity_tight_spread(self):
        """Test liquidity scoring for tight bid/ask spread."""
        # Bid/ask spread of $0.10 on $100 option = 0.1% = excellent
        liquidity = self.analyzer._score_liquidity(9.95, 10.05, 1000)

        self.assertGreater(liquidity, 0.8)

    def test_score_liquidity_wide_spread(self):
        """Test liquidity scoring for wide bid/ask spread."""
        # Bid/ask spread of $1.00 on $100 option = 1% = poor
        liquidity = self.analyzer._score_liquidity(9.50, 10.50, 50)

        self.assertLess(liquidity, 0.5)

    def test_score_liquidity_no_quotes(self):
        """Test liquidity scoring with no quotes."""
        liquidity = self.analyzer._score_liquidity(0, 0, 500)

        self.assertEqual(liquidity, 0.0)

    def test_score_greeks_positive_theta(self):
        """Test Greeks scoring with positive theta."""
        score = self.analyzer._score_greeks(0.5, 0.01, 0.05, 0.3, 'CALL')

        self.assertGreater(score, 0.5)

    def test_score_greeks_negative_theta(self):
        """Test Greeks scoring with negative theta."""
        score = self.analyzer._score_greeks(0.5, 0.01, -0.05, 0.3, 'CALL')

        self.assertLess(score, 0.8)

    def test_score_iv_optimal(self):
        """Test IV scoring for optimal range."""
        # 25% IV is in optimal 20-40% range
        score = self.analyzer._score_iv(0.25)

        self.assertEqual(score, 1.0)

    def test_score_iv_high(self):
        """Test IV scoring for high IV."""
        # 80% IV is very high
        score = self.analyzer._score_iv(0.80)

        self.assertEqual(score, 0.3)

    def test_score_iv_low(self):
        """Test IV scoring for low IV."""
        # 5% IV is very low
        score = self.analyzer._score_iv(0.05)

        self.assertEqual(score, 0.3)

    def test_score_dte_optimal(self):
        """Test DTE scoring for optimal range."""
        # 45 days is optimal
        score = self.analyzer._score_dte(45)

        self.assertEqual(score, 1.0)

    def test_score_dte_short(self):
        """Test DTE scoring for too short."""
        # 5 days is too short
        score = self.analyzer._score_dte(5)

        self.assertEqual(score, 0.3)

    def test_score_dte_long(self):
        """Test DTE scoring for too long."""
        # 200 days is too long
        score = self.analyzer._score_dte(200)

        self.assertEqual(score, 0.3)

    def test_calculate_option_score_in_range(self):
        """Test that option score is between 0 and 100."""
        score = self.analyzer._calculate_option_score(0.8, 0.7, 0.9, 0.8)

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_calculate_option_score_perfect(self):
        """Test option score with perfect metrics."""
        score = self.analyzer._calculate_option_score(1.0, 1.0, 1.0, 1.0)

        self.assertEqual(score, 100)

    def test_calculate_option_score_poor(self):
        """Test option score with poor metrics."""
        score = self.analyzer._calculate_option_score(0.1, 0.2, 0.1, 0.2)

        self.assertLess(score, 30)

    def test_calculate_avg_iv(self):
        """Test average IV calculation."""
        contracts = [
            {'implied_volatility': 0.20},
            {'implied_volatility': 0.30},
            {'implied_volatility': 0.40}
        ]

        avg_iv = self.analyzer._calculate_avg_iv(contracts)

        self.assertEqual(avg_iv, 0.30)

    def test_calculate_avg_iv_empty(self):
        """Test average IV with empty contracts."""
        avg_iv = self.analyzer._calculate_avg_iv([])

        self.assertEqual(avg_iv, 0.0)

    def test_calculate_avg_spread(self):
        """Test average spread calculation."""
        contracts = [
            {'last_quote': {'bid': 2.50, 'ask': 2.60}},
            {'last_quote': {'bid': 1.50, 'ask': 1.70}},
            {'last_quote': {'bid': 3.00, 'ask': 3.20}}
        ]

        avg_spread = self.analyzer._calculate_avg_spread(contracts)

        self.assertAlmostEqual(avg_spread, 0.2, places=1)

    def test_analyze_contracts_filters_by_dte(self):
        """Test that analyze_contracts returns recommendations within optimal DTE."""
        contracts = [
            {
                'greeks': {'delta': 0.5, 'gamma': 0.01, 'theta': 0.05, 'vega': 0.3, 'rho': 0},
                'implied_volatility': 0.25,
                'last_quote': {'bid': 2.50, 'ask': 2.60},
                'open_interest': 500,
                'details': {'strike_price': 150, 'expiration_date': (datetime.now() + timedelta(days=45)).strftime('%Y-%m-%d')}
            }
        ]

        recommendations = self.analyzer._analyze_contracts('AAPL', contracts, 'CALL', 150)

        # Should have at least some recommendations with good metrics
        self.assertGreaterEqual(len(recommendations), 0)
        if recommendations:
            self.assertGreater(recommendations[0]['suitability']['option_score'], 50)

    def test_analyze_contracts_returns_top_5(self):
        """Test that analyze_contracts returns at most 5 recommendations."""
        contracts = []
        for i in range(10):
            contracts.append({
                'greeks': {'delta': 0.5, 'gamma': 0.01, 'theta': 0.05, 'vega': 0.3, 'rho': 0},
                'implied_volatility': 0.25,
                'last_quote': {'bid': 2.50, 'ask': 2.60},
                'open_interest': 500 + i * 100,
                'details': {'strike_price': 150 + i, 'expiration_date': (datetime.now() + timedelta(days=45)).strftime('%Y-%m-%d')}
            })

        recommendations = self.analyzer._analyze_contracts('AAPL', contracts, 'CALL', 150)

        self.assertLessEqual(len(recommendations), 5)

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.analyzer)

        self.assertIn('OptionsAnalyzer', repr_str)
        self.assertIn('30-60', repr_str)

    def test_default_chain_result(self):
        """Test default chain result structure."""
        result = self.analyzer._default_chain_result()

        self.assertIn('calls', result)
        self.assertIn('puts', result)
        self.assertEqual(result['calls']['count'], 0)

    def test_default_contract_result(self):
        """Test default contract result structure."""
        result = self.analyzer._default_contract_result()

        self.assertIn('greeks', result)
        self.assertIn('liquidity', result)
        self.assertIn('volatility', result)
        self.assertIn('suitability', result)

    def test_analyze_multiple_contracts_with_different_metrics(self):
        """Test analyzing multiple contracts with varying metrics."""
        contract1 = {  # Good liquidity, good Greeks
            'greeks': {'delta': 0.5, 'gamma': 0.01, 'theta': 0.05, 'vega': 0.3, 'rho': 0},
            'implied_volatility': 0.25,
            'last_quote': {'bid': 2.50, 'ask': 2.60},
            'open_interest': 1000,
            'details': {'strike_price': 150, 'expiration_date': '2026-06-20'}
        }

        contract2 = {  # Poor liquidity, poor Greeks
            'greeks': {'delta': 0.95, 'gamma': 0.001, 'theta': -0.02, 'vega': 0.05, 'rho': 0},
            'implied_volatility': 0.80,
            'last_quote': {'bid': 0.50, 'ask': 1.50},
            'open_interest': 10,
            'details': {'strike_price': 160, 'expiration_date': '2026-06-20'}
        }

        result1 = self.analyzer.analyze_contract('AAPL', contract1, 'CALL')
        result2 = self.analyzer.analyze_contract('AAPL', contract2, 'CALL')

        # First should score better than second
        score1 = result1['suitability']['option_score']
        score2 = result2['suitability']['option_score']

        self.assertGreater(score1, score2)

    def test_liquidity_score_with_high_open_interest(self):
        """Test liquidity with high open interest."""
        # Tight spread (0.05%) + high OI (5000) = excellent liquidity
        liquidity = self.analyzer._score_liquidity(9.95, 10.05, 5000)

        # Should be very high (spread score 1.0 * 0.6 + OI score 1.0 * 0.4 = 1.0)
        self.assertGreater(liquidity, 0.8)

    def test_liquidity_score_with_low_open_interest(self):
        """Test liquidity with low open interest."""
        liquidity = self.analyzer._score_liquidity(9.95, 10.05, 20)

        self.assertLess(liquidity, 0.8)

    def test_greeks_scoring_zero_values(self):
        """Test Greeks scoring with zero values."""
        score = self.analyzer._score_greeks(0, 0, 0, 0, 'CALL')

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)

    def test_iv_scoring_boundary_cases(self):
        """Test IV scoring at boundaries."""
        score_lower = self.analyzer._score_iv(0.20)
        score_upper = self.analyzer._score_iv(0.40)
        score_mid = self.analyzer._score_iv(0.30)

        self.assertEqual(score_lower, 1.0)
        self.assertEqual(score_upper, 1.0)
        self.assertEqual(score_mid, 1.0)

    def test_dte_scoring_boundary_cases(self):
        """Test DTE scoring at boundaries."""
        score_lower = self.analyzer._score_dte(30)
        score_upper = self.analyzer._score_dte(60)
        score_mid = self.analyzer._score_dte(45)

        self.assertEqual(score_lower, 1.0)
        self.assertEqual(score_upper, 1.0)
        self.assertEqual(score_mid, 1.0)


if __name__ == '__main__':
    unittest.main()

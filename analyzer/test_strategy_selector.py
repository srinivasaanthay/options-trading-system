"""
Test suite for StrategySelector

Tests strategy recommendations, market regime detection, and risk/reward analysis
for all 10 strategy types.
"""

import unittest
from analyzer.strategy_selector import StrategySelector


class TestStrategySelector(unittest.TestCase):
    """Test StrategySelector functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.selector = StrategySelector()

    def test_initialization(self):
        """Test selector initialization."""
        self.assertEqual(len(self.selector.strategies), 10)
        self.assertEqual(self.selector.max_loss_tolerance, 0.05)
        self.assertEqual(self.selector.profit_target, 0.20)

    def test_recommend_strategy_empty_data(self):
        """Test strategy recommendation with empty data."""
        result = self.selector.recommend_strategy({}, {}, 100)

        self.assertIsInstance(result, dict)
        self.assertIn('market_regime', result)
        self.assertIn('recommendations', result)

    def test_market_regime_strong_bullish(self):
        """Test market regime detection for strong bullish."""
        regime = self.selector._determine_market_regime('uptrend', 'low', 75)

        self.assertEqual(regime, 'strong_bullish')

    def test_market_regime_bullish(self):
        """Test market regime detection for bullish."""
        regime = self.selector._determine_market_regime('uptrend', 'medium', 55)

        self.assertEqual(regime, 'bullish')

    def test_market_regime_strong_bearish(self):
        """Test market regime detection for strong bearish."""
        regime = self.selector._determine_market_regime('downtrend', 'high', 30)

        self.assertEqual(regime, 'strong_bearish')

    def test_market_regime_bearish(self):
        """Test market regime detection for bearish."""
        regime = self.selector._determine_market_regime('downtrend', 'medium', 50)

        self.assertEqual(regime, 'bearish')

    def test_market_regime_high_volatility(self):
        """Test market regime detection for high volatility."""
        regime = self.selector._determine_market_regime('sideways', 'extreme', 50)

        self.assertEqual(regime, 'high_volatility')

    def test_market_regime_neutral(self):
        """Test market regime detection for neutral."""
        regime = self.selector._determine_market_regime('sideways', 'low', 50)

        self.assertEqual(regime, 'neutral')

    def test_bull_call_spread_profitable(self):
        """Test bull call spread with profitable setup."""
        call_recs = [
            {
                'strike': 100,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 3.00, 'ask': 3.10}
            },
            {
                'strike': 105,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 1.50, 'ask': 1.60}
            }
        ]

        strategy = self.selector._analyze_bull_call_spread(call_recs, 100)

        self.assertEqual(strategy['strategy'], 'bull_call_spread')
        self.assertGreater(strategy['max_profit'], 0)
        self.assertGreater(strategy['confidence'], 0.5)

    def test_bull_call_spread_strike_order(self):
        """Test bull call spread has correct strike ordering."""
        call_recs = [
            {'strike': 100, 'liquidity': {'bid': 3.00, 'ask': 3.10}},
            {'strike': 105, 'liquidity': {'bid': 1.50, 'ask': 1.60}}
        ]

        strategy = self.selector._analyze_bull_call_spread(call_recs, 100)

        self.assertEqual(strategy['long_strike'], 100)
        self.assertEqual(strategy['short_strike'], 105)

    def test_bull_put_spread(self):
        """Test bull put spread analysis."""
        put_recs = [
            {
                'strike': 100,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 1.50, 'ask': 1.60}
            },
            {
                'strike': 95,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 0.50, 'ask': 0.60}
            }
        ]

        strategy = self.selector._analyze_bull_put_spread(put_recs, 100)

        self.assertEqual(strategy['strategy'], 'bull_put_spread')
        self.assertGreater(strategy['net_credit'], 0)

    def test_bear_call_spread(self):
        """Test bear call spread analysis."""
        call_recs = [
            {
                'strike': 100,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 3.00, 'ask': 3.10}
            },
            {
                'strike': 105,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 1.50, 'ask': 1.60}
            }
        ]

        strategy = self.selector._analyze_bear_call_spread(call_recs, 100)

        self.assertEqual(strategy['strategy'], 'bear_call_spread')
        self.assertGreater(strategy['net_credit'], 0)

    def test_bear_put_spread(self):
        """Test bear put spread analysis."""
        put_recs = [
            {
                'strike': 100,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 1.50, 'ask': 1.60}
            },
            {
                'strike': 95,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 0.50, 'ask': 0.60}
            }
        ]

        strategy = self.selector._analyze_bear_put_spread(put_recs, 100)

        self.assertEqual(strategy['strategy'], 'bear_put_spread')

    def test_iron_condor(self):
        """Test iron condor analysis."""
        call_recs = [
            {'strike': 105, 'liquidity': {'bid': 1.50, 'ask': 1.60}},
            {'strike': 110, 'liquidity': {'bid': 0.50, 'ask': 0.60}}
        ]
        put_recs = [
            {'strike': 95, 'liquidity': {'bid': 1.50, 'ask': 1.60}},
            {'strike': 90, 'liquidity': {'bid': 0.50, 'ask': 0.60}}
        ]

        strategy = self.selector._analyze_iron_condor(call_recs, put_recs, 100)

        self.assertEqual(strategy['strategy'], 'iron_condor')
        self.assertIn('call_short_strike', strategy)
        self.assertIn('put_short_strike', strategy)

    def test_long_straddle(self):
        """Test long straddle analysis."""
        call_recs = [
            {
                'strike': 100,
                'liquidity': {'ask': 3.00},
                'expiration': '2026-06-20',
                'dte': 30
            }
        ]
        put_recs = [
            {
                'strike': 100,
                'liquidity': {'ask': 2.50},
                'expiration': '2026-06-20',
                'dte': 30
            }
        ]

        strategy = self.selector._analyze_long_straddle(call_recs, put_recs, 100)

        self.assertEqual(strategy['strategy'], 'long_straddle')
        self.assertGreater(strategy['total_cost'], 0)
        self.assertEqual(strategy['strike'], 100)

    def test_long_strangle(self):
        """Test long strangle analysis."""
        call_recs = [
            {'strike': 100, 'liquidity': {'ask': 3.00}},
            {'strike': 105, 'liquidity': {'ask': 1.50}, 'expiration': '2026-06-20', 'dte': 30}
        ]
        put_recs = [
            {'strike': 100, 'liquidity': {'ask': 2.50}},
            {'strike': 95, 'liquidity': {'ask': 1.00}, 'expiration': '2026-06-20', 'dte': 30}
        ]

        strategy = self.selector._analyze_long_strangle(call_recs, put_recs, 100)

        self.assertEqual(strategy['strategy'], 'long_strangle')
        self.assertGreater(strategy['total_cost'], 0)

    def test_calendar_spread(self):
        """Test calendar spread analysis."""
        call_recs = [
            {
                'strike': 100,
                'liquidity': {'bid': 2.00, 'ask': 2.10},
                'expiration': '2026-06-20',
                'dte': 30
            }
        ]

        strategy = self.selector._analyze_calendar_spread(call_recs, [], 100)

        self.assertEqual(strategy['strategy'], 'calendar_spread')
        self.assertEqual(strategy['strike'], 100)

    def test_covered_call(self):
        """Test covered call analysis."""
        call_recs = [
            {
                'strike': 105,
                'liquidity': {'bid': 2.00, 'ask': 2.10},
                'expiration': '2026-06-20',
                'dte': 30
            }
        ]

        strategy = self.selector._analyze_covered_call(call_recs, 100)

        self.assertEqual(strategy['strategy'], 'covered_call')
        self.assertEqual(strategy['stock_price'], 100)
        self.assertGreater(strategy['call_premium'], 0)

    def test_strategy_max_profit_positive(self):
        """Test that profitable strategies have positive max profit."""
        call_recs = [
            {'strike': 100, 'liquidity': {'bid': 3.00, 'ask': 3.10}},
            {'strike': 105, 'liquidity': {'bid': 1.50, 'ask': 1.60}}
        ]

        strategy = self.selector._analyze_bull_call_spread(call_recs, 100)

        self.assertGreater(strategy['max_profit'], 0)

    def test_strategy_max_loss_non_negative(self):
        """Test that max loss is non-negative."""
        call_recs = [
            {'strike': 100, 'liquidity': {'bid': 3.00, 'ask': 3.10}},
            {'strike': 105, 'liquidity': {'bid': 1.50, 'ask': 1.60}}
        ]

        strategy = self.selector._analyze_bull_call_spread(call_recs, 100)

        self.assertGreaterEqual(strategy['max_loss'], 0)

    def test_strategy_risk_reward_ratio(self):
        """Test risk/reward ratio calculation."""
        call_recs = [
            {'strike': 100, 'liquidity': {'bid': 3.00, 'ask': 3.10}},
            {'strike': 105, 'liquidity': {'bid': 1.50, 'ask': 1.60}}
        ]

        strategy = self.selector._analyze_bull_call_spread(call_recs, 100)

        if strategy['max_loss'] > 0:
            self.assertGreater(strategy['risk_reward_ratio'], 0)

    def test_recommendation_includes_top_3(self):
        """Test that recommendation returns up to 3 strategies."""
        market_analysis = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium'},
            'health_score': 70
        }

        options_analysis = {
            'calls': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 3.0, 'ask': 3.1}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 105, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ],
                'avg_iv': 0.25
            },
            'puts': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 95, 'liquidity': {'bid': 0.5, 'ask': 0.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ]
            }
        }

        result = self.selector.recommend_strategy(market_analysis, options_analysis, 100)

        self.assertLessEqual(len(result['recommendations']), 3)

    def test_recommendation_has_best_strategy(self):
        """Test that recommendation identifies best strategy."""
        market_analysis = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium'},
            'health_score': 70
        }

        options_analysis = {
            'calls': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 3.0, 'ask': 3.1}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 105, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ],
                'avg_iv': 0.25
            },
            'puts': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 95, 'liquidity': {'bid': 0.5, 'ask': 0.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ]
            }
        }

        result = self.selector.recommend_strategy(market_analysis, options_analysis, 100)

        if result['recommendations']:
            self.assertIsNotNone(result['best_strategy'])
            self.assertIn(result['best_strategy'], self.selector.strategies)

    def test_bullish_market_recommends_bull_strategies(self):
        """Test that bullish market recommends bull strategies."""
        market_analysis = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium'},
            'health_score': 75
        }

        options_analysis = {
            'calls': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 3.0, 'ask': 3.1}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 105, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ],
                'avg_iv': 0.25
            },
            'puts': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 95, 'liquidity': {'bid': 0.5, 'ask': 0.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ]
            }
        }

        result = self.selector.recommend_strategy(market_analysis, options_analysis, 100)

        # Should include bull call spread or bull put spread
        strategies = [r['strategy'] for r in result['recommendations']]
        self.assertTrue(any('bull' in s for s in strategies))

    def test_bearish_market_recommends_bear_strategies(self):
        """Test that bearish market recommends bear strategies."""
        market_analysis = {
            'trend': {'direction': 'downtrend'},
            'volatility': {'regime': 'high'},
            'health_score': 35
        }

        options_analysis = {
            'calls': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 3.0, 'ask': 3.1}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 105, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ],
                'avg_iv': 0.25
            },
            'puts': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 95, 'liquidity': {'bid': 0.5, 'ask': 0.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ]
            }
        }

        result = self.selector.recommend_strategy(market_analysis, options_analysis, 100)

        # Should include bear call spread or bear put spread
        strategies = [r['strategy'] for r in result['recommendations']]
        self.assertTrue(any('bear' in s for s in strategies) or len(strategies) == 0)

    def test_high_volatility_recommends_straddle(self):
        """Test that high volatility recommends straddle."""
        market_analysis = {
            'trend': {'direction': 'sideways'},
            'volatility': {'regime': 'extreme'},
            'health_score': 50
        }

        options_analysis = {
            'calls': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 3.0, 'ask': 3.1}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 105, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ],
                'avg_iv': 0.50
            },
            'puts': {
                'recommendations': [
                    {'strike': 100, 'liquidity': {'bid': 1.5, 'ask': 1.6}, 'dte': 30, 'expiration': '2026-06-20'},
                    {'strike': 95, 'liquidity': {'bid': 0.5, 'ask': 0.6}, 'dte': 30, 'expiration': '2026-06-20'}
                ]
            }
        }

        result = self.selector.recommend_strategy(market_analysis, options_analysis, 100)

        strategies = [r['strategy'] for r in result['recommendations']]
        # Should recommend straddle or strangle for high IV
        self.assertTrue(any(s in ['long_straddle', 'long_strangle', 'iron_condor'] for s in strategies))

    def test_confidence_score_present(self):
        """Test that recommendations include confidence scores."""
        call_recs = [
            {'strike': 100, 'liquidity': {'bid': 3.00, 'ask': 3.10}},
            {'strike': 105, 'liquidity': {'bid': 1.50, 'ask': 1.60}}
        ]

        strategy = self.selector._analyze_bull_call_spread(call_recs, 100)

        self.assertIn('confidence', strategy)
        self.assertGreaterEqual(strategy['confidence'], 0)
        self.assertLessEqual(strategy['confidence'], 1)

    def test_default_strategy_structure(self):
        """Test default strategy has required fields."""
        strategy = self.selector._default_strategy()

        self.assertIn('strategy', strategy)
        self.assertIn('confidence', strategy)
        self.assertEqual(strategy['confidence'], 0.0)

    def test_default_recommendation_structure(self):
        """Test default recommendation has required fields."""
        result = self.selector._default_recommendation()

        self.assertIn('market_regime', result)
        self.assertIn('recommendations', result)
        self.assertIn('best_strategy', result)
        self.assertIn('confidence_score', result)

    def test_calculate_pop_at_price(self):
        """Test probability of profit at current price."""
        pop = self.selector._calculate_pop(100, 100)

        self.assertEqual(pop, 0.5)

    def test_calculate_pop_above_breakeven(self):
        """Test probability of profit above breakeven."""
        pop = self.selector._calculate_pop(105, 100)

        self.assertLess(pop, 0.5)

    def test_calculate_pop_below_breakeven(self):
        """Test probability of profit below breakeven."""
        pop = self.selector._calculate_pop(95, 100)

        self.assertLess(pop, 0.5)

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.selector)

        self.assertIn('StrategySelector', repr_str)
        self.assertIn('strategies', repr_str)

    def test_insufficient_contracts_for_spread(self):
        """Test strategy with insufficient contracts."""
        call_recs = [
            {'strike': 100, 'liquidity': {'bid': 3.0, 'ask': 3.1}}
        ]

        strategy = self.selector._analyze_bull_call_spread(call_recs, 100)

        self.assertEqual(strategy['strategy'], 'none')

    def test_iron_condor_requires_both_sides(self):
        """Test iron condor requires both calls and puts."""
        call_recs = [
            {'strike': 105, 'liquidity': {'bid': 1.50, 'ask': 1.60}},
            {'strike': 110, 'liquidity': {'bid': 0.50, 'ask': 0.60}}
        ]

        strategy = self.selector._analyze_iron_condor(call_recs, [], 100)

        self.assertEqual(strategy['strategy'], 'none')

    def test_expiration_data_preserved(self):
        """Test that expiration data is preserved in analysis."""
        call_recs = [
            {
                'strike': 100,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 3.0, 'ask': 3.1}
            },
            {
                'strike': 105,
                'expiration': '2026-06-20',
                'dte': 30,
                'liquidity': {'bid': 1.5, 'ask': 1.6}
            }
        ]

        strategy = self.selector._analyze_bull_call_spread(call_recs, 100)

        self.assertEqual(strategy['dte'], 30)
        self.assertEqual(strategy['expiration'], '2026-06-20')


if __name__ == '__main__':
    unittest.main()

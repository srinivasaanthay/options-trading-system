"""
Test suite for ReasoningGenerator

Tests narrative generation, catalyst identification, risk/reward analysis,
and complete reasoning synthesis.
"""

import unittest
from analyzer.reasoning_generator import ReasoningGenerator


class TestReasoningGenerator(unittest.TestCase):
    """Test ReasoningGenerator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = ReasoningGenerator()
        self.sample_news = {
            'overall_sentiment': 0.5,
            'strength': 0.7,
            'recency_score': 0.8,
            'trend': 'improving'
        }
        self.sample_technical = {
            'trend': 'uptrend',
            'momentum': 60,
            'technical_score': 70,
            'support_resistance': {'support': 95, 'resistance': 105}
        }
        self.sample_options = {
            'calls': {
                'recommendations': [
                    {'suitability': {'option_score': 75}},
                    {'suitability': {'option_score': 70}}
                ]
            },
            'puts': {
                'recommendations': [
                    {'suitability': {'option_score': 55}},
                    {'suitability': {'option_score': 50}}
                ]
            }
        }
        self.sample_market = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium', 'vix': 18},
            'health_score': 70,
            'breadth': {'breadth_score': 0.75}
        }
        self.sample_strategy = {
            'strategy': 'bull_call_spread',
            'max_profit': 5.00,
            'max_loss': 2.00,
            'risk_reward_ratio': 2.5
        }
        self.sample_ml = {
            'recommendation': 'CALL',
            'confidence': 0.75,
            'directional_strength': 0.7
        }

    def test_initialization(self):
        """Test generator initialization."""
        self.assertGreater(len(self.generator.tone_levels), 0)
        self.assertGreater(len(self.generator.catalyst_weights), 0)

    def test_generate_reasoning_returns_dict(self):
        """Test that generate_reasoning returns proper dictionary."""
        result = self.generator.generate_reasoning(
            'AAPL',
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            self.sample_strategy,
            self.sample_ml,
            100
        )

        self.assertIsInstance(result, dict)
        self.assertIn('recommendation', result)
        self.assertIn('main_thesis', result)
        self.assertIn('complete_reasoning', result)

    def test_generate_reasoning_empty_data(self):
        """Test reasoning with empty data."""
        result = self.generator.generate_reasoning(
            'AAPL',
            {},
            {},
            {},
            {},
            {},
            {},
            100
        )

        self.assertEqual(result['recommendation'], 'neutral')
        self.assertEqual(result['confidence_score'], 0.50)

    def test_catalyst_identification_returns_list(self):
        """Test that catalyst identification returns list."""
        catalysts = self.generator._identify_catalysts(
            self.sample_news,
            self.sample_technical,
            self.sample_market
        )

        self.assertIsInstance(catalysts, list)
        self.assertLessEqual(len(catalysts), 4)

    def test_catalyst_has_required_fields(self):
        """Test catalysts have required fields."""
        catalysts = self.generator._identify_catalysts(
            self.sample_news,
            self.sample_technical,
            self.sample_market
        )

        if catalysts:
            for catalyst in catalysts:
                self.assertIn('type', catalyst)
                self.assertIn('description', catalyst)
                self.assertIn('strength', catalyst)
                self.assertIn('weight', catalyst)

    def test_catalyst_positive_sentiment(self):
        """Test catalyst detection for positive sentiment."""
        bullish_news = {**self.sample_news, 'overall_sentiment': 0.7}

        catalysts = self.generator._identify_catalysts(
            bullish_news,
            self.sample_technical,
            self.sample_market
        )

        catalyst_types = [c['type'] for c in catalysts]
        self.assertTrue(any('sentiment' in t for t in catalyst_types))

    def test_catalyst_technical_breakout(self):
        """Test catalyst detection for technical breakout."""
        strong_technical = {**self.sample_technical, 'momentum': 80, 'trend': 'uptrend'}

        catalysts = self.generator._identify_catalysts(
            self.sample_news,
            strong_technical,
            self.sample_market
        )

        catalyst_types = [c['type'] for c in catalysts]
        self.assertTrue(any('technical' in t or 'breakout' in t for t in catalyst_types))

    def test_catalyst_high_volatility(self):
        """Test catalyst detection for high volatility."""
        high_vol_market = {**self.sample_market, 'volatility': {'regime': 'extreme', 'vix': 50}}

        catalysts = self.generator._identify_catalysts(
            self.sample_news,
            self.sample_technical,
            high_vol_market
        )

        catalyst_types = [c['type'] for c in catalysts]
        self.assertTrue(any('volatility' in t for t in catalyst_types))

    def test_risk_reward_analysis(self):
        """Test risk/reward analysis."""
        result = self.generator._analyze_risk_reward(
            'CALL',
            self.sample_strategy,
            100,
            self.sample_market
        )

        self.assertIn('max_profit', result)
        self.assertIn('max_loss', result)
        self.assertIn('risk_reward_ratio', result)
        self.assertIn('risk_rating', result)

    def test_risk_reward_max_profit(self):
        """Test risk/reward max profit calculation."""
        result = self.generator._analyze_risk_reward(
            'CALL',
            self.sample_strategy,
            100,
            self.sample_market
        )

        self.assertEqual(result['max_profit'], 5.00)

    def test_risk_reward_max_loss(self):
        """Test risk/reward max loss calculation."""
        result = self.generator._analyze_risk_reward(
            'CALL',
            self.sample_strategy,
            100,
            self.sample_market
        )

        self.assertEqual(result['max_loss'], 2.00)

    def test_risk_reward_ratio(self):
        """Test risk/reward ratio calculation."""
        result = self.generator._analyze_risk_reward(
            'CALL',
            self.sample_strategy,
            100,
            self.sample_market
        )

        self.assertEqual(result['risk_reward_ratio'], 2.5)

    def test_main_narrative_call(self):
        """Test main narrative for CALL recommendation."""
        result = self.generator._generate_main_narrative(
            'AAPL',
            'CALL',
            0.75,
            0.7,
            self.sample_news,
            self.sample_technical,
            self.sample_market
        )

        self.assertIn('thesis', result)
        thesis = result['thesis']
        self.assertTrue('CALL' in thesis or 'upside' in thesis.lower())

    def test_main_narrative_put(self):
        """Test main narrative for PUT recommendation."""
        bearish_news = {**self.sample_news, 'overall_sentiment': -0.6}
        bearish_technical = {**self.sample_technical, 'trend': 'downtrend', 'momentum': -70}
        bearish_market = {**self.sample_market, 'trend': {'direction': 'downtrend'}}

        result = self.generator._generate_main_narrative(
            'AAPL',
            'PUT',
            0.70,
            0.6,
            bearish_news,
            bearish_technical,
            bearish_market
        )

        self.assertIn('thesis', result)

    def test_supporting_analysis_returns_list(self):
        """Test supporting analysis returns list."""
        analysis = self.generator._generate_supporting_analysis(
            'CALL',
            self.sample_technical,
            self.sample_options,
            self.sample_market
        )

        self.assertIsInstance(analysis, list)
        self.assertLessEqual(len(analysis), 5)

    def test_supporting_analysis_content(self):
        """Test supporting analysis has text content."""
        analysis = self.generator._generate_supporting_analysis(
            'CALL',
            self.sample_technical,
            self.sample_options,
            self.sample_market
        )

        if analysis:
            for point in analysis:
                self.assertIsInstance(point, str)
                self.assertGreater(len(point), 10)

    def test_risk_narrative(self):
        """Test risk narrative generation."""
        risk_reward = {
            'max_profit': 5.00,
            'max_loss': 2.00,
            'risk_reward_ratio': 2.5,
            'risk_rating': 'moderate'
        }

        narrative = self.generator._generate_risk_narrative(risk_reward, 0.75)

        self.assertIsInstance(narrative, str)
        self.assertGreater(len(narrative), 20)
        self.assertIn('profit', narrative.lower())
        self.assertIn('loss', narrative.lower())

    def test_identify_key_levels(self):
        """Test key level identification."""
        levels = self.generator._identify_key_levels(
            self.sample_technical,
            100,
            self.sample_market
        )

        self.assertIn('current_price', levels)
        self.assertIn('support', levels)
        self.assertIn('resistance', levels)
        self.assertIn('stop_loss', levels)
        self.assertIn('profit_target_1', levels)

    def test_key_levels_values(self):
        """Test key levels have numeric values."""
        levels = self.generator._identify_key_levels(
            self.sample_technical,
            100,
            self.sample_market
        )

        self.assertEqual(levels['current_price'], 100)
        self.assertIsInstance(levels['support'], (int, float))
        self.assertIsInstance(levels['resistance'], (int, float))
        self.assertGreater(levels['resistance'], levels['support'])

    def test_synthesize_reasoning(self):
        """Test reasoning synthesis."""
        main_narrative = {'thesis': 'Test thesis'}
        supporting = ['Point 1', 'Point 2']
        risk_narrative = 'Risk narrative text'
        catalysts = [{'description': 'Catalyst 1'}]
        levels = {
            'current_price': 100,
            'support': 95,
            'resistance': 105,
            'stop_loss': 94,
            'stop_loss_pct': 1.0,
            'profit_target_1': 102,
            'target1_pct': 2.0,
            'profit_target_2': 105,
            'target2_pct': 5.0
        }

        reasoning = self.generator._synthesize_reasoning(
            main_narrative,
            supporting,
            risk_narrative,
            catalysts,
            levels,
            'CALL',
            0.75
        )

        self.assertIsInstance(reasoning, str)
        self.assertGreater(len(reasoning), 50)
        self.assertIn('THESIS', reasoning)
        self.assertIn('RISK', reasoning)

    def test_tone_low_confidence(self):
        """Test tone for low confidence."""
        tone = self.generator._get_tone(0.50)

        self.assertEqual(tone, 'Consider')

    def test_tone_medium_confidence(self):
        """Test tone for medium confidence."""
        tone = self.generator._get_tone(0.65)

        self.assertEqual(tone, 'We believe')

    def test_tone_high_confidence(self):
        """Test tone for high confidence."""
        tone = self.generator._get_tone(0.80)

        self.assertEqual(tone, 'We are convinced')

    def test_confidence_label_low(self):
        """Test confidence label for low confidence."""
        label = self.generator._get_confidence_label(0.50)

        self.assertEqual(label, 'Low')

    def test_confidence_label_moderate(self):
        """Test confidence label for moderate confidence."""
        label = self.generator._get_confidence_label(0.65)

        self.assertEqual(label, 'Moderate')

    def test_confidence_label_high(self):
        """Test confidence label for high confidence."""
        label = self.generator._get_confidence_label(0.78)

        self.assertEqual(label, 'High')

    def test_confidence_label_very_high(self):
        """Test confidence label for very high confidence."""
        label = self.generator._get_confidence_label(0.90)

        self.assertEqual(label, 'Very High')

    def test_strength_label_weak(self):
        """Test strength label for weak."""
        label = self.generator._get_strength_label(0.10)

        self.assertEqual(label, 'Weak')

    def test_strength_label_moderate(self):
        """Test strength label for moderate."""
        label = self.generator._get_strength_label(0.40)

        self.assertEqual(label, 'Moderate')

    def test_strength_label_strong(self):
        """Test strength label for strong."""
        label = self.generator._get_strength_label(0.65)

        self.assertEqual(label, 'Strong')

    def test_complete_reasoning_structure(self):
        """Test complete reasoning has all required sections."""
        result = self.generator.generate_reasoning(
            'AAPL',
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            self.sample_strategy,
            self.sample_ml,
            100
        )

        required_fields = [
            'recommendation',
            'confidence_level',
            'main_thesis',
            'supporting_analysis',
            'risk_reward_analysis',
            'key_catalysts',
            'key_levels',
            'complete_reasoning'
        ]

        for field in required_fields:
            self.assertIn(field, result)

    def test_recommendation_field_present(self):
        """Test that recommendation is included."""
        result = self.generator.generate_reasoning(
            'AAPL',
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            self.sample_strategy,
            self.sample_ml,
            100
        )

        self.assertIn(result['recommendation'], ['CALL', 'PUT', 'neutral'])

    def test_thesis_is_string(self):
        """Test that thesis is a proper string."""
        result = self.generator.generate_reasoning(
            'AAPL',
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            self.sample_strategy,
            self.sample_ml,
            100
        )

        self.assertIsInstance(result['main_thesis'], str)
        self.assertGreater(len(result['main_thesis']), 10)

    def test_timestamp_present(self):
        """Test that timestamp is included."""
        result = self.generator.generate_reasoning(
            'AAPL',
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            self.sample_strategy,
            self.sample_ml,
            100
        )

        self.assertIn('reasoning_timestamp', result)
        from datetime import datetime
        datetime.fromisoformat(result['reasoning_timestamp'])

    def test_symbol_in_result(self):
        """Test that symbol is included in result."""
        result = self.generator.generate_reasoning(
            'AAPL',
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            self.sample_strategy,
            self.sample_ml,
            100
        )

        self.assertEqual(result['symbol'], 'AAPL')

    def test_confidence_score_in_range(self):
        """Test confidence score is in valid range."""
        result = self.generator.generate_reasoning(
            'AAPL',
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            self.sample_strategy,
            self.sample_ml,
            100
        )

        self.assertGreaterEqual(result['confidence_score'], 0)
        self.assertLessEqual(result['confidence_score'], 1)

    def test_default_reasoning_structure(self):
        """Test default reasoning has required structure."""
        result = self.generator._default_reasoning()

        self.assertEqual(result['recommendation'], 'neutral')
        self.assertEqual(result['confidence_score'], 0.50)
        self.assertIsInstance(result['supporting_analysis'], list)

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.generator)

        self.assertIn('ReasoningGenerator', repr_str)

    def test_catalyst_weights_are_valid(self):
        """Test that catalyst weights are reasonable."""
        for weight in self.generator.catalyst_weights.values():
            self.assertGreaterEqual(weight, 0)
            self.assertLessEqual(weight, 1.0)


if __name__ == '__main__':
    unittest.main()

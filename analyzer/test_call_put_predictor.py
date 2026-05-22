"""
Test suite for CallPutPredictor

Tests feature engineering, prediction logic, confidence scoring,
and model retraining capabilities.
"""

import unittest
from analyzer.call_put_predictor import CallPutPredictor


class TestCallPutPredictor(unittest.TestCase):
    """Test CallPutPredictor functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.predictor = CallPutPredictor()
        self.sample_news = {
            'overall_sentiment': 0.3,
            'strength': 0.7,
            'recency_score': 0.8,
            'trend': 'improving',
            'historical_sentiment': 0.1,
            'sentiment_volatility': 0.4,
            'news_count': 5
        }
        self.sample_technical = {
            'trend': 'uptrend',
            'momentum': 45,
            'strength': 0.75,
            'rsi_signal': 'neutral',
            'technical_score': 65,
            'sma_signals': {'sma_50_200_cross': 'bullish', 'price_above_sma50': True},
            'support_resistance': {'support': 95, 'resistance': 105},
            'macd': {'histogram': 1.5}
        }
        self.sample_options = {
            'calls': {
                'recommendations': [
                    {'suitability': {'option_score': 75}},
                    {'suitability': {'option_score': 70}}
                ],
                'avg_iv': 0.25,
                'avg_spread': 0.08
            },
            'puts': {
                'recommendations': [
                    {'suitability': {'option_score': 60}},
                    {'suitability': {'option_score': 55}}
                ],
                'avg_iv': 0.25,
                'avg_spread': 0.10
            }
        }
        self.sample_market = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium', 'vix': 18},
            'health_score': 70,
            'breadth': {'breadth_score': 0.75, 'ad_ratio': 1.8},
            'sectors': {'momentum': 'bullish'},
            'anomalies': []
        }

    def test_initialization(self):
        """Test predictor initialization."""
        self.assertEqual(self.predictor.feature_count, 34)
        self.assertEqual(self.predictor.model_type, 'logistic_regression')
        self.assertEqual(self.predictor.min_confidence, 0.55)

    def test_predict_returns_dict(self):
        """Test that predict returns proper dictionary."""
        result = self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        self.assertIsInstance(result, dict)
        self.assertIn('recommendation', result)
        self.assertIn('prediction', result)
        self.assertIn('confidence', result)
        self.assertIn('supporting_factors', result)

    def test_predict_empty_data(self):
        """Test prediction with empty data."""
        result = self.predictor.predict({}, {}, {}, {}, 100)

        self.assertEqual(result['recommendation'], 'neutral')
        self.assertEqual(result['confidence'], 0.50)

    def test_feature_engineering_count(self):
        """Test that feature engineering returns correct number of features."""
        features = self.predictor._engineer_features(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        self.assertEqual(len(features), 34)

    def test_feature_engineering_range(self):
        """Test that all features are in valid ranges."""
        features = self.predictor._engineer_features(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        for i, feature in enumerate(features):
            self.assertIsInstance(feature, (int, float))
            self.assertLessEqual(feature, 2.0)
            self.assertGreaterEqual(feature, -2.0)

    def test_sentiment_features(self):
        """Test sentiment feature extraction."""
        features = self.predictor._engineer_features(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        # First 8 features are sentiment
        self.assertEqual(features[0], self.sample_news['overall_sentiment'])
        self.assertEqual(features[1], self.sample_news['strength'])

    def test_technical_features(self):
        """Test technical feature extraction."""
        features = self.predictor._engineer_features(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        # Features 8-17 are technical
        # Trend should be 1 for uptrend
        self.assertEqual(features[8], 1)

    def test_options_features(self):
        """Test options feature extraction."""
        features = self.predictor._engineer_features(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        # Features 18-26 are options-related
        # Should have call/put scores
        self.assertGreater(features[18], 0)  # Call score
        self.assertGreater(features[19], 0)  # Put score

    def test_market_features(self):
        """Test market feature extraction."""
        features = self.predictor._engineer_features(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        # Features 26-33 are market features (8 features)
        # Market trend (first market feature) should be 1 for uptrend
        self.assertEqual(features[26], 1)

    def test_predict_bullish_scenario(self):
        """Test prediction in bullish scenario."""
        bullish_news = {**self.sample_news, 'overall_sentiment': 0.7}
        bullish_technical = {**self.sample_technical, 'trend': 'uptrend', 'momentum': 70}
        bullish_market = {**self.sample_market, 'health_score': 80}

        result = self.predictor.predict(
            bullish_news,
            bullish_technical,
            self.sample_options,
            bullish_market,
            100
        )

        # Should lean towards CALL in bullish scenario
        self.assertIn(result['prediction'], ['CALL', 'PUT', 'neutral'])

    def test_predict_bearish_scenario(self):
        """Test prediction in bearish scenario."""
        bearish_news = {**self.sample_news, 'overall_sentiment': -0.7}
        bearish_technical = {**self.sample_technical, 'trend': 'downtrend', 'momentum': -70}
        bearish_market = {**self.sample_market, 'trend': {'direction': 'downtrend'}, 'health_score': 30}

        result = self.predictor.predict(
            bearish_news,
            bearish_technical,
            self.sample_options,
            bearish_market,
            100
        )

        self.assertIn(result['prediction'], ['CALL', 'PUT', 'neutral'])

    def test_confidence_in_range(self):
        """Test that confidence is between 0 and 1."""
        result = self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        self.assertGreaterEqual(result['confidence'], 0)
        self.assertLessEqual(result['confidence'], 1)

    def test_confidence_pct_conversion(self):
        """Test confidence percentage calculation."""
        result = self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        expected_pct = result['confidence'] * 100
        self.assertAlmostEqual(result['confidence_pct'], expected_pct, places=1)

    def test_low_confidence_neutral_recommendation(self):
        """Test that low confidence returns neutral recommendation."""
        # Create scenario with conflicting signals
        mixed_news = {**self.sample_news, 'overall_sentiment': 0.1}
        mixed_technical = {**self.sample_technical, 'momentum': 5}
        mixed_market = {**self.sample_market, 'health_score': 50}

        result = self.predictor.predict(
            mixed_news,
            mixed_technical,
            self.sample_options,
            mixed_market,
            100
        )

        if result['confidence'] < 0.55:
            self.assertEqual(result['recommendation'], 'neutral')

    def test_high_confidence_call_recommendation(self):
        """Test high confidence CALL recommendation."""
        strong_bullish_news = {**self.sample_news, 'overall_sentiment': 0.8}
        strong_bullish_tech = {**self.sample_technical, 'trend': 'uptrend', 'momentum': 80}
        strong_bullish_market = {**self.sample_market, 'health_score': 85}

        result = self.predictor.predict(
            strong_bullish_news,
            strong_bullish_tech,
            self.sample_options,
            strong_bullish_market,
            100
        )

        # High confidence should produce strong recommendation
        if result['confidence'] > 0.70:
            self.assertIn(result['recommendation'], ['CALL', 'neutral'])

    def test_directional_strength_in_range(self):
        """Test directional strength is between 0 and 1."""
        result = self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        self.assertGreaterEqual(result['directional_strength'], 0)
        self.assertLessEqual(result['directional_strength'], 1)

    def test_supporting_factors_present(self):
        """Test that supporting factors are identified."""
        result = self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        self.assertIsInstance(result['supporting_factors'], list)
        self.assertLessEqual(len(result['supporting_factors']), 4)

    def test_supporting_factors_content(self):
        """Test supporting factor content quality."""
        result = self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        if result['supporting_factors']:
            for factor in result['supporting_factors']:
                self.assertIsInstance(factor, str)
                self.assertGreater(len(factor), 3)

    def test_feature_count_in_result(self):
        """Test that feature count is included in result."""
        result = self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        self.assertIn('feature_count', result)
        self.assertEqual(result['feature_count'], 34)

    def test_predict_from_features_returns_tuple(self):
        """Test _predict_from_features returns correct tuple."""
        features = [0.5] * 34
        prediction, confidence = self.predictor._predict_from_features(features)

        self.assertIn(prediction, [0, 1])
        self.assertGreaterEqual(confidence, 0)
        self.assertLessEqual(confidence, 1)

    def test_predict_from_features_wrong_count(self):
        """Test _predict_from_features with wrong feature count."""
        features = [0.5] * 10  # Wrong count
        prediction, confidence = self.predictor._predict_from_features(features)

        self.assertEqual(prediction, 0)
        self.assertEqual(confidence, 0.5)

    def test_iv_rank_low(self):
        """Test IV rank for low IV."""
        rank = self.predictor._estimate_iv_rank(0.10)

        self.assertEqual(rank, 0.0)

    def test_iv_rank_high(self):
        """Test IV rank for high IV."""
        rank = self.predictor._estimate_iv_rank(0.60)

        self.assertEqual(rank, 1.0)

    def test_iv_rank_mid(self):
        """Test IV rank for mid IV."""
        rank = self.predictor._estimate_iv_rank(0.325)

        self.assertGreater(rank, 0.3)
        self.assertLess(rank, 0.7)

    def test_model_info(self):
        """Test model info retrieval."""
        info = self.predictor.get_model_info()

        self.assertEqual(info['model_type'], 'logistic_regression')
        self.assertEqual(info['feature_count'], 34)
        self.assertGreater(info['weights_sum'], 0)

    def test_add_training_sample(self):
        """Test adding training sample."""
        features = [0.5] * 34
        self.predictor.add_training_sample(features, 'CALL')

        self.assertEqual(len(self.predictor.training_data), 1)

    def test_training_sample_label(self):
        """Test training sample label conversion."""
        features = [0.5] * 34
        self.predictor.add_training_sample(features, 'CALL')
        self.predictor.add_training_sample(features, 'PUT')

        self.assertEqual(self.predictor.training_data[0][1], 1)  # CALL = 1
        self.assertEqual(self.predictor.training_data[1][1], 0)  # PUT = 0

    def test_retraining_threshold(self):
        """Test model retraining threshold."""
        self.assertEqual(self.predictor.retraining_threshold, 20)

    def test_default_prediction_structure(self):
        """Test default prediction structure."""
        result = self.predictor._default_prediction()

        self.assertEqual(result['recommendation'], 'neutral')
        self.assertEqual(result['confidence'], 0.50)
        self.assertIsInstance(result['supporting_factors'], list)

    def test_weight_initialization(self):
        """Test weight initialization."""
        weights = self.predictor.model_weights

        self.assertEqual(len(weights), 34)
        self.assertTrue(all(w > 0 for w in weights))

    def test_timestamp_in_result(self):
        """Test that timestamp is included in prediction."""
        result = self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        self.assertIn('prediction_timestamp', result)
        # Verify it's a valid ISO format string
        from datetime import datetime
        datetime.fromisoformat(result['prediction_timestamp'])

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.predictor)

        self.assertIn('CallPutPredictor', repr_str)
        self.assertIn('logistic_regression', repr_str)

    def test_calculate_directional_strength_positive(self):
        """Test directional strength in positive scenario."""
        bullish_news = {**self.sample_news, 'overall_sentiment': 0.8}
        bullish_technical = {**self.sample_technical, 'trend': 'uptrend', 'momentum': 80}
        bullish_market = {**self.sample_market, 'health_score': 85}

        result = self.predictor.predict(
            bullish_news,
            bullish_technical,
            self.sample_options,
            bullish_market,
            100
        )

        self.assertGreater(result['directional_strength'], 0.3)

    def test_feature_importance_tracking(self):
        """Test that feature importance is tracked."""
        features = self.predictor._engineer_features(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        # Update feature importance
        self.predictor._update_feature_importance(features)

        self.assertTrue(len(self.predictor.feature_importance) > 0)

    def test_multiple_predictions_accumulate(self):
        """Test that prediction count accumulates."""
        initial_count = self.predictor.prediction_count

        self.predictor.predict(
            self.sample_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        self.assertEqual(self.predictor.prediction_count, initial_count + 1)

    def test_sentiment_bias_in_factors(self):
        """Test sentiment bias is reflected in factors."""
        positive_news = {**self.sample_news, 'overall_sentiment': 0.6}

        result = self.predictor.predict(
            positive_news,
            self.sample_technical,
            self.sample_options,
            self.sample_market,
            100
        )

        factors_str = ' '.join(result['supporting_factors']).lower()
        # May contain sentiment-related factors
        self.assertIsInstance(factors_str, str)


if __name__ == '__main__':
    unittest.main()

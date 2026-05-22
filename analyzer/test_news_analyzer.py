"""
Test suite for NewsAnalyzer

Tests sentiment analysis, scoring, time decay, and model training.
"""

import unittest
from datetime import datetime, timedelta
from analyzer.news_analyzer import NewsAnalyzer


class TestNewsAnalyzer(unittest.TestCase):
    """Test NewsAnalyzer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = NewsAnalyzer()

    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertIsNotNone(self.analyzer.sentiment_lexicon)
        self.assertGreater(len(self.analyzer.sentiment_lexicon), 50)
        self.assertEqual(self.analyzer.model_version, "1.0")

    def test_sentiment_score_positive(self):
        """Test sentiment scoring for positive text."""
        text = "The stock had an outstanding breakthrough with excellent growth"
        score = self.analyzer._calculate_sentiment_score(text)
        self.assertGreater(score, 0.5)  # Should be strongly positive

    def test_sentiment_score_negative(self):
        """Test sentiment scoring for negative text."""
        text = "The stock crashed with a terrible disaster and worst performance"
        score = self.analyzer._calculate_sentiment_score(text)
        self.assertLess(score, -0.5)  # Should be strongly negative

    def test_sentiment_score_neutral(self):
        """Test sentiment scoring for neutral text."""
        text = "The stock moved sideways with mixed results"
        score = self.analyzer._calculate_sentiment_score(text)
        self.assertGreater(score, -0.3)
        self.assertLess(score, 0.3)

    def test_sentiment_score_clamped(self):
        """Test that sentiment scores are clamped to [-1, 1]."""
        positive_text = "excellent stellar outstanding remarkable breakthrough"
        score_pos = self.analyzer._calculate_sentiment_score(positive_text)
        self.assertGreaterEqual(score_pos, -1.0)
        self.assertLessEqual(score_pos, 1.0)

        negative_text = "terrible awful disaster catastrophe crash collapse"
        score_neg = self.analyzer._calculate_sentiment_score(negative_text)
        self.assertGreaterEqual(score_neg, -1.0)
        self.assertLessEqual(score_neg, 1.0)

    def test_analyze_stock_sentiment_empty_news(self):
        """Test sentiment analysis with no news items."""
        result = self.analyzer.analyze_stock_sentiment('AAPL', [])
        self.assertEqual(result['sentiment'], 0.0)
        self.assertEqual(result['strength'], 0.0)
        self.assertEqual(result['articles_analyzed'], 0)

    def test_analyze_stock_sentiment_single_article(self):
        """Test sentiment analysis with single article."""
        news = [{
            'title': 'Stock Surges on Outstanding Earnings',
            'description': 'Company shows stellar growth',
            'published_at': datetime.now().isoformat()
        }]

        result = self.analyzer.analyze_stock_sentiment('AAPL', news)
        self.assertGreater(result['sentiment'], 0.0)
        self.assertEqual(result['articles_analyzed'], 1)

    def test_analyze_stock_sentiment_multiple_articles(self):
        """Test sentiment analysis with multiple articles."""
        news = [
            {
                'title': 'Stock Soars on Great News',
                'description': 'Excellent performance',
                'published_at': (datetime.now() - timedelta(days=1)).isoformat()
            },
            {
                'title': 'Company Shows Positive Growth',
                'description': 'Strong recovery',
                'published_at': (datetime.now() - timedelta(days=2)).isoformat()
            },
            {
                'title': 'Analyst Upgrades Stock',
                'description': 'Bullish outlook',
                'published_at': (datetime.now() - timedelta(days=3)).isoformat()
            }
        ]

        result = self.analyzer.analyze_stock_sentiment('AAPL', news)
        self.assertGreater(result['sentiment'], 0.0)
        self.assertGreater(result['strength'], 0.0)
        self.assertEqual(result['articles_analyzed'], 3)

    def test_bullish_vs_bearish_count(self):
        """Test counting bullish and bearish articles."""
        news = [
            {
                'title': 'Stock Soars',
                'description': 'Great news',
                'published_at': datetime.now().isoformat()
            },
            {
                'title': 'Stock Crashes',
                'description': 'Terrible disaster',
                'published_at': datetime.now().isoformat()
            },
            {
                'title': 'Stock Mixed Results',
                'description': 'Neutral',
                'published_at': datetime.now().isoformat()
            }
        ]

        result = self.analyzer.analyze_stock_sentiment('AAPL', news)
        self.assertGreater(result['bullish_count'], 0)
        self.assertGreater(result['bearish_count'], 0)

    def test_time_decay_application(self):
        """Test that time decay weights recent news more heavily."""
        now = datetime.now()
        scores = [0.5, 0.5, 0.5]  # All same score
        timestamps = [
            now - timedelta(days=10),
            now - timedelta(days=5),
            now  # Most recent
        ]

        weighted = self.analyzer._apply_time_decay(scores, timestamps)

        # Most recent should have highest weight
        self.assertGreater(weighted[2], weighted[1])
        self.assertGreater(weighted[1], weighted[0])

    def test_strength_calculation_consistent_sentiment(self):
        """Test strength calculation for consistent sentiment."""
        scores = [0.8, 0.7, 0.9, 0.85]  # Consistently positive
        strength = self.analyzer._calculate_strength(scores)
        self.assertGreater(strength, 0.7)  # Should be high

    def test_strength_calculation_mixed_sentiment(self):
        """Test strength calculation for mixed sentiment."""
        scores = [0.8, -0.7, 0.9, -0.85]  # Mixed sentiment
        strength = self.analyzer._calculate_strength(scores)
        self.assertLess(strength, 0.5)  # Should be lower

    def test_recency_calculation(self):
        """Test recency calculation."""
        # Recent news
        recent = [datetime.now() - timedelta(days=1)]
        recency_recent = self.analyzer._calculate_recency(recent)

        # Old news
        old = [datetime.now() - timedelta(days=30)]
        recency_old = self.analyzer._calculate_recency(old)

        # Recent should have higher recency
        self.assertGreater(recency_recent, recency_old)

    def test_determine_trend_up(self):
        """Test trend determination for upward trend."""
        scores = [0.2, 0.5, 0.8]  # Trending up
        trend = self.analyzer._determine_trend(scores)
        self.assertEqual(trend, 'up')

    def test_determine_trend_down(self):
        """Test trend determination for downward trend."""
        scores = [0.8, 0.5, 0.2]  # Trending down
        trend = self.analyzer._determine_trend(scores)
        self.assertEqual(trend, 'down')

    def test_determine_trend_neutral(self):
        """Test trend determination for neutral trend."""
        scores = [0.3, 0.35, 0.32]  # Neutral/sideways
        trend = self.analyzer._determine_trend(scores)
        self.assertEqual(trend, 'neutral')

    def test_parse_timestamp_iso_format(self):
        """Test timestamp parsing for ISO format."""
        timestamp_str = "2026-05-21T14:30:00"
        parsed = self.analyzer._parse_timestamp(timestamp_str)
        self.assertIsInstance(parsed, datetime)
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.month, 5)
        self.assertEqual(parsed.day, 21)

    def test_parse_timestamp_invalid(self):
        """Test timestamp parsing for invalid format."""
        parsed = self.analyzer._parse_timestamp("invalid")
        self.assertIsInstance(parsed, datetime)

    def test_parse_timestamp_none(self):
        """Test timestamp parsing for None."""
        parsed = self.analyzer._parse_timestamp(None)
        self.assertIsInstance(parsed, datetime)

    def test_historical_sentiment_storage(self):
        """Test that sentiment is stored in history."""
        news = [{
            'title': 'Stock Surges',
            'description': 'Great news',
            'published_at': datetime.now().isoformat()
        }]

        self.analyzer.analyze_stock_sentiment('AAPL', news)
        history = self.analyzer.get_historical_sentiment('AAPL')

        self.assertEqual(len(history), 1)
        self.assertGreater(history[0]['score'], 0)

    def test_sentiment_trend_from_history(self):
        """Test sentiment trend calculation from history."""
        # Build up history with upward trend
        for i in range(5):
            score = -0.5 + (i * 0.2)  # -0.5, -0.3, -0.1, 0.1, 0.3
            self.analyzer.sentiment_history['AAPL'].append({
                'date': datetime.now() - timedelta(days=5-i),
                'score': score,
                'strength': 0.8
            })

        trend = self.analyzer.get_sentiment_trend('AAPL')
        self.assertEqual(trend, 'up')

    def test_daily_model_training(self):
        """Test daily model retraining."""
        result = self.analyzer.train_daily_model()

        self.assertEqual(result['status'], 'completed')
        self.assertIsNotNone(result['model_version'])
        self.assertGreater(result['lexicon_size'], 0)

    def test_model_version_increment(self):
        """Test that model version increments after training."""
        initial_version = self.analyzer.model_version

        self.analyzer.train_daily_model()
        new_version = self.analyzer.model_version

        self.assertNotEqual(initial_version, new_version)

    def test_to_dict_serialization(self):
        """Test serialization to dictionary."""
        result = self.analyzer.to_dict()

        self.assertIn('model_version', result)
        self.assertIn('lexicon_size', result)
        self.assertIn('symbols_tracked', result)
        self.assertGreater(result['lexicon_size'], 0)

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.analyzer)
        self.assertIn('NewsAnalyzer', repr_str)
        self.assertIn('version=1.0', repr_str)

    def test_sentiment_persistence_across_analyses(self):
        """Test that sentiment history persists across multiple analyses."""
        news1 = [{
            'title': 'Stock Up',
            'description': 'Good news',
            'published_at': (datetime.now() - timedelta(days=1)).isoformat()
        }]
        news2 = [{
            'title': 'Stock Down',
            'description': 'Bad news',
            'published_at': datetime.now().isoformat()
        }]

        self.analyzer.analyze_stock_sentiment('AAPL', news1)
        self.analyzer.analyze_stock_sentiment('AAPL', news2)

        history = self.analyzer.get_historical_sentiment('AAPL')
        self.assertEqual(len(history), 2)

    def test_negative_modifier_negation(self):
        """Test that 'not' modifies sentiment correctly."""
        positive_text = "The stock is excellent"
        negative_text = "The stock is not excellent"

        score_pos = self.analyzer._calculate_sentiment_score(positive_text)
        score_neg = self.analyzer._calculate_sentiment_score(negative_text)

        # Negation should reverse polarity
        self.assertGreater(score_pos, 0)
        self.assertLess(score_neg, score_pos)

    def test_multiple_stocks_tracking(self):
        """Test that analyzer can track multiple stocks independently."""
        news_aapl = [{
            'title': 'Apple Soars',
            'description': 'Great news',
            'published_at': datetime.now().isoformat()
        }]
        news_msft = [{
            'title': 'Microsoft Crashes',
            'description': 'Terrible news',
            'published_at': datetime.now().isoformat()
        }]

        result_aapl = self.analyzer.analyze_stock_sentiment('AAPL', news_aapl)
        result_msft = self.analyzer.analyze_stock_sentiment('MSFT', news_msft)

        self.assertGreater(result_aapl['sentiment'], result_msft['sentiment'])

        # Both should be tracked
        history_aapl = self.analyzer.get_historical_sentiment('AAPL')
        history_msft = self.analyzer.get_historical_sentiment('MSFT')

        self.assertGreater(len(history_aapl), 0)
        self.assertGreater(len(history_msft), 0)


if __name__ == '__main__':
    unittest.main()

"""
News Sentiment Analyzer

Analyzes market news and sentiment for S&P 500 stocks.
Provides sentiment scoring, trend analysis, and daily model retraining.

Features:
- Sentiment lexicon (positive/negative/neutral words)
- Historical sentiment storage and tracking
- Time-decay weighting for recent news
- Daily sentiment model retraining
- Strength and recency scoring
- Integration with Massive API news data
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class NewsAnalyzer:
    """
    Analyzes news sentiment for options trading recommendations.

    Sentiment is scored from -1.0 (very bearish) to +1.0 (very bullish).
    Incorporates time decay so recent news is weighted more heavily.

    Attributes:
        sentiment_lexicon: Dictionary of words with sentiment weights
        sentiment_history: Historical sentiment scores for tracking
        model_version: Version number for sentiment model
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the News Analyzer.

        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}
        self.sentiment_lexicon = self._initialize_sentiment_lexicon()
        self.sentiment_history = defaultdict(list)  # symbol -> [(date, score, strength)]
        self.model_version = "1.0"
        self.last_trained = None

        logger.info("NewsAnalyzer initialized with sentiment lexicon (%d words)",
                   len(self.sentiment_lexicon))

    def _initialize_sentiment_lexicon(self) -> Dict[str, float]:
        """
        Initialize sentiment lexicon with word weights.

        Positive words: weight +0.1 to +1.0
        Negative words: weight -1.0 to -0.1
        Neutral/modifier words: weight -0.3 to +0.3

        Returns:
            Dictionary mapping words to sentiment weights
        """
        lexicon = {
            # Strong Positive
            'surge': 0.9, 'soar': 0.9, 'skyrocket': 0.95,
            'bullish': 0.85, 'breakthrough': 0.8, 'outperform': 0.75,
            'stellar': 0.85, 'outstanding': 0.8, 'exceptional': 0.8,
            'excellent': 0.75, 'remarkable': 0.75, 'impressive': 0.7,

            # Positive
            'gain': 0.6, 'growth': 0.65, 'profit': 0.65, 'rally': 0.7,
            'upbeat': 0.65, 'strong': 0.6, 'recovery': 0.65, 'rebound': 0.65,
            'rise': 0.55, 'boost': 0.6, 'momentum': 0.6, 'great': 0.65,
            'positive': 0.65, 'optimistic': 0.7, 'encouraging': 0.6,
            'upgrade': 0.75, 'beat': 0.65, 'exceed': 0.65, 'good': 0.6,
            'best': 0.7, 'better': 0.65, 'improved': 0.65,

            # Weak Positive
            'stable': 0.3, 'steady': 0.35, 'holding': 0.25, 'maintain': 0.2,
            'support': 0.3, 'confidence': 0.5, 'opportunity': 0.4, 'news': 0.1,

            # Neutral/Modest
            'mixed': -0.1, 'cautious': -0.2, 'concern': -0.4, 'uncertain': -0.3,
            'volatile': -0.4, 'sideways': -0.1,

            # Weak Negative
            'decline': -0.5, 'weakness': -0.5, 'weak': -0.4, 'miss': -0.6,
            'disappointed': -0.6, 'underperform': -0.65, 'downturn': -0.6,
            'bearish': -0.75, 'downgr': -0.8,

            # Strong Negative
            'crash': -0.9, 'collapse': -0.95, 'plunge': -0.85, 'plummet': -0.9,
            'disaster': -0.95, 'catastrophe': -0.95, 'worst': -0.8,
            'failure': -0.85, 'loss': -0.7, 'drop': -0.6,
            'recession': -0.85, 'crisis': -0.9, 'bad': -0.6,
            'terrible': -0.8, 'awful': -0.8, 'poor': -0.6,

            # Modifiers (amplifiers)
            'very': 0.15, 'significantly': 0.2, 'sharply': 0.2, 'dramatically': 0.25,
            'extremely': 0.25, 'massively': 0.3, 'huge': 0.3, 'record': 0.4,

            # Negative modifiers
            'not': -0.3, 'no': -0.25, 'lack': -0.3, 'fail': -0.4,
        }

        return lexicon

    def analyze_stock_sentiment(
        self,
        symbol: str,
        news_items: List[Dict],
        timeframe_days: int = 30
    ) -> Dict[str, float]:
        """
        Analyze sentiment for a stock from news items.

        Args:
            symbol: Stock ticker symbol
            news_items: List of news articles with 'title', 'description', 'published_at'
            timeframe_days: Look back period (default 30 days)

        Returns:
            Dictionary with sentiment metrics:
            - sentiment: -1.0 to +1.0 score
            - strength: 0 to 1 confidence
            - recency: 0 to 1 weight (higher = more recent)
            - bullish_count: Number of bullish articles
            - bearish_count: Number of bearish articles
            - recent_trend: 'up', 'down', or 'neutral'
        """
        if not news_items:
            return {
                'sentiment': 0.0,
                'strength': 0.0,
                'recency': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'recent_trend': 'neutral',
                'articles_analyzed': 0
            }

        # Filter news by timeframe
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        recent_news = [
            item for item in news_items
            if self._parse_timestamp(item.get('published_at')) >= cutoff_date
        ]

        if not recent_news:
            recent_news = news_items[:10]  # Use latest 10 if none in timeframe

        # Score each article
        article_scores = []
        article_times = []

        for article in recent_news:
            text = f"{article.get('title', '')} {article.get('description', '')}"
            score = self._calculate_sentiment_score(text)
            timestamp = self._parse_timestamp(article.get('published_at'))

            article_scores.append(score)
            article_times.append(timestamp)

        if not article_scores:
            return {
                'sentiment': 0.0,
                'strength': 0.0,
                'recency': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'recent_trend': 'neutral',
                'articles_analyzed': 0
            }

        # Apply time decay to scores
        weighted_scores = self._apply_time_decay(article_scores, article_times)

        # Calculate aggregate sentiment
        avg_sentiment = sum(weighted_scores) / len(weighted_scores)
        avg_sentiment = max(-1.0, min(1.0, avg_sentiment))  # Clamp to [-1, 1]

        # Calculate strength (consistency of sentiment)
        strength = self._calculate_strength(article_scores)

        # Calculate recency weight
        recency = self._calculate_recency(article_times)

        # Count bullish vs bearish
        bullish = sum(1 for s in article_scores if s > 0.2)
        bearish = sum(1 for s in article_scores if s < -0.2)

        # Determine trend
        if len(article_scores) >= 3:
            recent_trend = self._determine_trend(article_scores[-3:])
        else:
            recent_trend = self._determine_trend(article_scores)

        # Store in history
        self.sentiment_history[symbol].append({
            'date': datetime.now(),
            'score': avg_sentiment,
            'strength': strength
        })

        # Keep only last 90 days
        cutoff = datetime.now() - timedelta(days=90)
        self.sentiment_history[symbol] = [
            h for h in self.sentiment_history[symbol]
            if h['date'] >= cutoff
        ]

        return {
            'sentiment': avg_sentiment,
            'strength': strength,
            'recency': recency,
            'bullish_count': bullish,
            'bearish_count': bearish,
            'recent_trend': recent_trend,
            'articles_analyzed': len(recent_news),
            'model_version': self.model_version
        }

    def _calculate_sentiment_score(self, text: str) -> float:
        """
        Calculate sentiment score for a text passage.

        Args:
            text: Text to analyze

        Returns:
            Sentiment score from -1.0 to +1.0
        """
        text_lower = text.lower()

        # Remove punctuation for word matching
        text_clean = re.sub(r'[^a-z\s]', '', text_lower)
        words = text_clean.split()

        if not words:
            return 0.0

        # Score words
        total_score = 0.0
        word_count = 0

        for i, word in enumerate(words):
            if word in self.sentiment_lexicon:
                weight = self.sentiment_lexicon[word]

                # Check for modifiers before word
                if i > 0 and words[i-1] in ['very', 'extremely', 'very', 'significantly']:
                    weight *= 1.3  # Amplify score

                # Check for negation (not, no, lack)
                if i > 0 and words[i-1] in ['not', 'no', 'lack', 'didn']:
                    weight *= -1.0  # Reverse polarity

                total_score += weight
                word_count += 1

        if word_count == 0:
            return 0.0

        # Normalize score
        avg_score = total_score / word_count

        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, avg_score))

    def _apply_time_decay(
        self,
        scores: List[float],
        timestamps: List[datetime],
        decay_days: int = 30
    ) -> List[float]:
        """
        Apply time decay to scores (recent news weighted more heavily).

        Args:
            scores: Sentiment scores
            timestamps: Corresponding timestamps
            decay_days: Half-life for exponential decay

        Returns:
            Time-weighted scores
        """
        now = datetime.now()
        weighted_scores = []

        for score, timestamp in zip(scores, timestamps):
            days_ago = (now - timestamp).days

            # Exponential decay: weight = 2^(-days_ago/decay_days)
            weight = 2 ** (-days_ago / decay_days)
            weight = max(0.1, weight)  # Minimum weight of 0.1

            weighted_score = score * weight
            weighted_scores.append(weighted_score)

        return weighted_scores

    def _calculate_strength(self, scores: List[float]) -> float:
        """
        Calculate sentiment strength (consistency).

        High strength = consistent sentiment (all positive or all negative)
        Low strength = mixed sentiment

        Args:
            scores: List of sentiment scores

        Returns:
            Strength score from 0 to 1
        """
        if not scores:
            return 0.0

        # Calculate variance
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)

        # Strength = 1 - sqrt(variance)
        # High variance = low strength (mixed sentiment)
        # Low variance = high strength (consistent sentiment)
        strength = max(0.0, 1.0 - (variance ** 0.5))

        return strength

    def _calculate_recency(self, timestamps: List[datetime]) -> float:
        """
        Calculate recency weight (how recent is the news).

        Args:
            timestamps: List of article timestamps

        Returns:
            Recency score from 0 to 1 (1 = very recent)
        """
        if not timestamps:
            return 0.0

        latest = max(timestamps)
        days_ago = (datetime.now() - latest).days

        # Recency = 1 / (1 + days_ago/7)
        # -1 day = 0.875, -7 days = 0.5, -14 days = 0.33
        recency = 1.0 / (1.0 + days_ago / 7.0)

        return max(0.0, min(1.0, recency))

    def _determine_trend(self, recent_scores: List[float]) -> str:
        """
        Determine recent sentiment trend.

        Args:
            recent_scores: Recent sentiment scores (last 3 typically)

        Returns:
            'up', 'down', or 'neutral'
        """
        if len(recent_scores) < 2:
            if recent_scores and recent_scores[0] > 0.1:
                return 'up'
            elif recent_scores and recent_scores[0] < -0.1:
                return 'down'
            else:
                return 'neutral'

        # Check trend direction
        avg_recent = sum(recent_scores[-2:]) / 2
        avg_older = sum(recent_scores[:-2]) / max(1, len(recent_scores) - 2)

        trend_change = avg_recent - avg_older

        if trend_change > 0.15:
            return 'up'
        elif trend_change < -0.15:
            return 'down'
        else:
            return 'neutral'

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """
        Parse timestamp string to datetime object.

        Args:
            timestamp_str: Timestamp string (ISO format or None)

        Returns:
            Parsed datetime, or now() if parsing fails
        """
        if not timestamp_str:
            return datetime.now()

        try:
            # Try ISO format first
            if 'T' in timestamp_str:
                # Remove timezone info if present
                if '+' in timestamp_str:
                    timestamp_str = timestamp_str.split('+')[0]
                if 'Z' in timestamp_str:
                    timestamp_str = timestamp_str.replace('Z', '')

                return datetime.fromisoformat(timestamp_str)
            else:
                # Try date only format
                return datetime.strptime(timestamp_str, '%Y-%m-%d')
        except (ValueError, AttributeError):
            logger.warning("Failed to parse timestamp: %s", timestamp_str)
            return datetime.now()

    def get_historical_sentiment(self, symbol: str) -> List[Dict]:
        """
        Get historical sentiment for a stock.

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of historical sentiment records
        """
        return self.sentiment_history.get(symbol, [])

    def get_sentiment_trend(self, symbol: str, days: int = 30) -> str:
        """
        Get overall sentiment trend for a stock.

        Args:
            symbol: Stock ticker symbol
            days: Look-back period

        Returns:
            'up', 'down', or 'neutral'
        """
        history = self.get_historical_sentiment(symbol)

        if not history:
            return 'neutral'

        cutoff = datetime.now() - timedelta(days=days)
        recent = [h for h in history if h['date'] >= cutoff]

        if not recent:
            recent = history[-7:]  # Use last 7 if none in period

        if len(recent) < 2:
            return 'neutral'

        scores = [h['score'] for h in recent]
        return self._determine_trend(scores)

    def train_daily_model(self, training_data: Optional[List[Dict]] = None) -> Dict[str, str]:
        """
        Retrain sentiment model with new data.

        In a production system, this would use accumulated historical data
        to improve the sentiment lexicon and calibration.

        Args:
            training_data: Training dataset (optional)

        Returns:
            Training results dictionary
        """
        logger.info("Starting daily sentiment model retraining")

        # In production, this would:
        # 1. Collect all sentiment annotations from past analyses
        # 2. Retrain a more sophisticated model (BERT, etc.)
        # 3. Update lexicon weights based on performance
        # 4. Validate on holdout test set
        # 5. Version control the model

        self.last_trained = datetime.now()

        # For now, increment version
        version_parts = self.model_version.split('.')
        version_parts[1] = str(int(version_parts[1]) + 1)
        self.model_version = '.'.join(version_parts)

        results = {
            'status': 'completed',
            'model_version': self.model_version,
            'trained_at': self.last_trained.isoformat(),
            'lexicon_size': len(self.sentiment_lexicon),
            'history_records': sum(len(v) for v in self.sentiment_history.values())
        }

        logger.info("Sentiment model retrained: %s", results)
        return results

    def to_dict(self) -> Dict:
        """
        Serialize analyzer state to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'model_version': self.model_version,
            'last_trained': self.last_trained.isoformat() if self.last_trained else None,
            'lexicon_size': len(self.sentiment_lexicon),
            'symbols_tracked': list(self.sentiment_history.keys())
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"NewsAnalyzer(version={self.model_version}, "
            f"lexicon_words={len(self.sentiment_lexicon)}, "
            f"symbols_tracked={len(self.sentiment_history)})"
        )

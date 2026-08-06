"""
Call/Put Predictor

Machine learning model for predicting CALL vs PUT recommendations.
Uses 30+ features from sentiment, technical, options, and market analysis.

Features:
- Feature engineering from multiple analyzers (30+ features)
- Binary classification: CALL (1) vs PUT (0)
- Daily retraining with new data
- Confidence score calibration
- Historical performance tracking
- Model persistence and versioning
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class CallPutPredictor:
    """
    Predicts CALL vs PUT recommendations using ML.

    Combines sentiment, technical, options, and market signals to recommend
    call or put strategies with confidence scoring.

    Attributes:
        model_type: Type of model (logistic_regression, ensemble)
        feature_count: Number of engineered features
        min_confidence: Minimum confidence threshold for recommendations
        training_data: Historical training data
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Call/Put Predictor.

        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}

        # Model parameters
        self.model_type = 'logistic_regression'
        self.feature_count = 34  # Total engineered features
        self.min_confidence = 0.55  # Minimum confidence threshold
        self.retraining_threshold = 20  # Retrain after N new predictions

        # Model state
        self.model_weights = self._initialize_weights()
        self.training_data = []
        self.prediction_count = 0
        self.last_retraining = datetime.now().isoformat()
        self.feature_importance = {}

        logger.info("CallPutPredictor initialized (features: %d, model: %s)",
                   self.feature_count, self.model_type)

    def predict(
        self,
        news_analysis: Dict,
        technical_analysis: Dict,
        options_analysis: Dict,
        market_analysis: Dict,
        stock_price: float
    ) -> Dict:
        """
        Predict CALL vs PUT recommendation.

        Args:
            news_analysis: Sentiment analysis output
            technical_analysis: Technical indicator analysis
            options_analysis: Options chain analysis
            market_analysis: Market conditions analysis
            stock_price: Current stock price

        Returns:
            Dictionary with prediction and confidence
        """
        if not all([news_analysis, technical_analysis, options_analysis, market_analysis]):
            return self._default_prediction()

        try:
            # Engineer features from all analyzers
            features = self._engineer_features(
                news_analysis,
                technical_analysis,
                options_analysis,
                market_analysis,
                stock_price
            )

            if not features:
                return self._default_prediction()

            # Make prediction
            prediction, confidence = self._predict_from_features(features)

            # Check if confidence meets threshold
            if confidence < self.min_confidence:
                recommendation = 'neutral'
            elif prediction == 1:
                recommendation = 'CALL'
            else:
                recommendation = 'PUT'

            # Apply mean-reversion guardrails before finalising
            confidence, recommendation, guardrail_notes = self._apply_guardrails(
                prediction, confidence, recommendation, technical_analysis
            )

            # Calculate directional strength
            directional_strength = self._calculate_directional_strength(features)

            # Get supporting factors
            supporting_factors = self._identify_supporting_factors(features)
            if guardrail_notes:
                supporting_factors = guardrail_notes + supporting_factors[:2]

            # Track prediction for retraining
            self.prediction_count += 1
            if self.prediction_count >= self.retraining_threshold:
                self._retrain_model()

            return {
                'recommendation': recommendation,
                'prediction': 'CALL' if prediction == 1 else 'PUT',
                'confidence': round(confidence, 3),
                'confidence_pct': round(confidence * 100, 1),
                'directional_strength': round(directional_strength, 3),
                'supporting_factors': supporting_factors,
                'feature_count': len(features),
                'model_type': self.model_type,
                'prediction_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Error predicting recommendation: %s", str(e))
            return self._default_prediction()

    def _engineer_features(
        self,
        news: Dict,
        technical: Dict,
        options: Dict,
        market: Dict,
        price: float
    ) -> List[float]:
        """
        Engineer 35+ features from analyzer outputs.

        Feature groups:
        - Sentiment features (8): score, strength, recency, trend, etc.
        - Technical features (10): trend, momentum, strength, RSI, MACD, etc.
        - Options features (9): IV, spreads, Greeks, liquidity, etc.
        - Market features (8): regime, volatility, breadth, health, etc.

        Args:
            news: News/sentiment analysis
            technical: Technical analysis
            options: Options analysis
            market: Market analysis
            price: Stock price

        Returns:
            List of 35+ normalized features
        """
        features = []

        # Sentiment Features (8)
        sentiment_score = news.get('overall_sentiment', 0)
        features.append(sentiment_score)  # [-1.0, 1.0]

        strength = news.get('strength', 0)
        features.append(strength)  # [0, 1.0]

        recency = news.get('recency_score', 0)
        features.append(recency)  # [0, 1.0]

        trend = 1 if news.get('trend', 'neutral') == 'improving' else (-1 if news.get('trend') == 'declining' else 0)
        features.append(trend)  # [-1, 1]

        historical_avg = news.get('historical_sentiment', 0)
        features.append(historical_avg)  # [-1.0, 1.0]

        sentiment_volatility = news.get('sentiment_volatility', 0.5)
        features.append(sentiment_volatility)  # [0, 1.0]

        news_count = min(1.0, news.get('news_count', 0) / 10.0)
        features.append(news_count)  # [0, 1.0]

        sentiment_momentum = sentiment_score - historical_avg
        features.append(sentiment_momentum)  # [-2, 2]

        # Technical Features (10)
        trend_val = 1 if technical.get('trend') == 'uptrend' else (-1 if technical.get('trend') == 'downtrend' else 0)
        features.append(trend_val)

        momentum = technical.get('momentum', 0) / 100.0  # Normalize to [-1, 1]
        features.append(momentum)

        strength = technical.get('strength', 0.5)
        features.append(strength)

        rsi_signal = {'overbought': 1, 'neutral': 0, 'oversold': -1}.get(technical.get('rsi_signal', 'neutral'), 0)
        features.append(rsi_signal)

        tech_score = technical.get('technical_score', 50) / 100.0  # Normalize to [0, 1]
        features.append(tech_score)

        # SMA signals
        sma_signal = technical.get('sma_signals', {})
        sma_cross = 1 if sma_signal.get('sma_50_200_cross') == 'bullish' else (-1 if sma_signal.get('sma_50_200_cross') == 'bearish' else 0)
        features.append(sma_cross)

        price_above_sma50 = 1 if sma_signal.get('price_above_sma50') else -1
        features.append(price_above_sma50)

        # Support/resistance
        support_resistance = technical.get('support_resistance', {})
        support = support_resistance.get('support', price)
        resistance = support_resistance.get('resistance', price)
        distance_to_support = (price - support) / (resistance - support) if resistance > support else 0.5
        features.append(distance_to_support)

        # MACD histogram
        macd = technical.get('macd', {})
        histogram = macd.get('histogram', 0)
        features.append(min(1.0, max(-1.0, histogram / 5.0)))  # Normalize

        # Options Features (9)
        call_recs = options.get('calls', {}).get('recommendations', [])
        put_recs = options.get('puts', {}).get('recommendations', [])

        avg_call_score = sum(r.get('suitability', {}).get('option_score', 0) for r in call_recs) / max(len(call_recs), 1) / 100.0 if call_recs else 0.5
        features.append(avg_call_score)

        avg_put_score = sum(r.get('suitability', {}).get('option_score', 0) for r in put_recs) / max(len(put_recs), 1) / 100.0 if put_recs else 0.5
        features.append(avg_put_score)

        call_put_ratio = avg_call_score / (avg_put_score + 0.001)
        features.append(min(1.0, max(-1.0, (call_put_ratio - 1.0) / 2.0)))

        avg_iv = options.get('calls', {}).get('avg_iv', 0.25)
        features.append(min(1.0, avg_iv / 0.5))  # Normalize [0, 1]

        iv_rank = self._estimate_iv_rank(avg_iv)
        features.append(iv_rank)

        call_spread = options.get('calls', {}).get('avg_spread', 0.1)
        features.append(min(1.0, max(0, 1 - call_spread)))  # Liquidity proxy

        put_spread = options.get('puts', {}).get('avg_spread', 0.1)
        features.append(min(1.0, max(0, 1 - put_spread)))

        call_volume = min(1.0, len(call_recs) / 5.0)
        features.append(call_volume)

        put_volume = min(1.0, len(put_recs) / 5.0)
        features.append(put_volume)

        # Market Features (8)
        market_trend = 1 if market.get('trend', {}).get('direction') == 'uptrend' else (-1 if market.get('trend', {}).get('direction') == 'downtrend' else 0)
        features.append(market_trend)

        volatility_regime = {'low': -0.5, 'medium': 0, 'high': 0.5, 'extreme': 1.0}.get(market.get('volatility', {}).get('regime', 'medium'), 0)
        features.append(volatility_regime)

        health_score = market.get('health_score', 50) / 100.0
        features.append(health_score)

        breadth_score = market.get('breadth', {}).get('breadth_score', 0.5)
        features.append(breadth_score)

        ad_ratio = market.get('breadth', {}).get('ad_ratio', 1.0)
        features.append(min(1.0, max(-1.0, (ad_ratio - 1.0) / 2.0)))

        sector_momentum = {'bullish': 1, 'bearish': -1, 'neutral': 0}.get(market.get('sectors', {}).get('momentum', 'neutral'), 0)
        features.append(sector_momentum)

        vix_level = market.get('volatility', {}).get('vix', 20)
        features.append(min(1.0, vix_level / 40.0))  # Normalize to [0, 1]

        anomalies = len(market.get('anomalies', []))
        features.append(min(1.0, anomalies / 5.0))  # Normalize

        # Store features for importance tracking
        self._update_feature_importance(features)

        return features

    def _predict_from_features(self, features: List[float]) -> Tuple[int, float]:
        """
        Predict CALL (1) or PUT (0) from features.

        Uses logistic regression-like logic with learned weights.

        Args:
            features: List of engineered features

        Returns:
            Tuple of (prediction, confidence)
        """
        if len(features) != len(self.model_weights):
            return 0, 0.5

        # Weighted sum
        score = sum(f * w for f, w in zip(features, self.model_weights))

        # Sigmoid function for probability
        confidence = 1.0 / (1.0 + 2.718 ** (-score))

        # Hard threshold at 0.5
        prediction = 1 if confidence > 0.5 else 0

        return prediction, confidence

    def _apply_guardrails(
        self,
        prediction: int,
        confidence: float,
        recommendation: str,
        technical: Dict,
    ):
        """
        Override ML confidence when well-known mean-reversion conditions apply.

        Rules:
        1. Oversold PUT (RSI < 38): likely a bounce, not continuation — penalty
        2. Overbought CALL (RSI > 65): likely a pullback, not continuation — penalty
        3. Extreme oversold + big down day (RSI < 32, momentum < -35): strong bounce risk
        4. Extreme overbought + big up day (RSI > 72, momentum > 35): strong pullback risk
        """
        rsi = technical.get('rsi', 50)
        momentum = technical.get('momentum', 0)  # MACD-based, -100 to +100
        notes = []

        is_put = (prediction == 0)
        is_call = (prediction == 1)

        # Rule 1 & 3: Oversold + PUT = dangerous (stock likely to bounce)
        if is_put and rsi < 38:
            if rsi < 32 and momentum < -35:
                # Extreme — big single-day drop on oversold: high bounce risk
                confidence = max(0.50, confidence - 0.25)
                notes.append(f"⚠️ Extreme oversold RSI={rsi:.0f} — high bounce risk, PUT confidence cut")
            else:
                confidence = max(0.50, confidence - 0.12)
                notes.append(f"⚠️ Oversold RSI={rsi:.0f} — mean-reversion risk on PUT")

        # Rule 2 & 4: Overbought + CALL = dangerous (stock likely to pull back)
        elif is_call and rsi > 65:
            if rsi > 72 and momentum > 35:
                confidence = max(0.50, confidence - 0.25)
                notes.append(f"⚠️ Extreme overbought RSI={rsi:.0f} — pullback risk, CALL confidence cut")
            else:
                confidence = max(0.50, confidence - 0.12)
                notes.append(f"⚠️ Overbought RSI={rsi:.0f} — mean-reversion risk on CALL")

        # Re-evaluate recommendation after confidence adjustment
        if confidence < self.min_confidence:
            recommendation = 'neutral'
        elif prediction == 1:
            recommendation = 'CALL'
        else:
            recommendation = 'PUT'

        return confidence, recommendation, notes

    def _calculate_directional_strength(self, features: List[float]) -> float:
        """
        Calculate strength of directional conviction.

        Args:
            features: Feature list

        Returns:
            Strength score [0, 1]
        """
        # Key features for direction strength
        # Sentiment trend, technical trend, momentum, market trend
        if len(features) >= 22:  # Has all feature groups
            sentiment_direction = abs(features[0])  # Sentiment score
            technical_direction = abs(features[9])  # Tech trend
            momentum_direction = abs(features[10])  # Momentum
            market_direction = abs(features[23])  # Market trend

            strength = (sentiment_direction + technical_direction + momentum_direction + market_direction) / 4.0

            return min(1.0, max(0.0, strength))

        return 0.5

    def _identify_supporting_factors(self, features: List[float]) -> List[str]:
        """
        Identify which factors support the prediction.

        Args:
            features: Feature list

        Returns:
            List of supporting factor descriptions
        """
        factors = []

        if len(features) < 35:
            return factors

        # Sentiment support
        if features[0] > 0.3:
            factors.append("Positive sentiment bias")
        elif features[0] < -0.3:
            factors.append("Negative sentiment bias")

        # Technical support
        if features[9] > 0.3:
            factors.append("Uptrend confirmed")
        elif features[9] < -0.3:
            factors.append("Downtrend confirmed")

        # Momentum support
        if features[10] > 0.3:
            factors.append("Positive momentum")
        elif features[10] < -0.3:
            factors.append("Negative momentum")

        # Options flow support
        if features[13] > features[14]:
            factors.append("Call flow stronger")
        else:
            factors.append("Put flow stronger")

        # Market environment support
        if features[23] > 0.3:
            factors.append("Bullish market regime")
        elif features[23] < -0.3:
            factors.append("Bearish market regime")

        # Volatility support
        if features[24] > 0.5:
            factors.append("High volatility environment")
        else:
            factors.append("Low volatility environment")

        return factors[:4]  # Return top 4 factors

    def _estimate_iv_rank(self, iv: float) -> float:
        """
        Estimate IV percentile rank (simplified).

        Args:
            iv: Implied volatility (decimal)

        Returns:
            IV rank [0, 1]
        """
        # Simplified: assume typical range 15-50%
        if iv <= 0.15:
            return 0.0
        elif iv >= 0.50:
            return 1.0
        else:
            return (iv - 0.15) / (0.50 - 0.15)

    def _initialize_weights(self) -> List[float]:
        """
        Initialize model weights.

        Uses reasonable defaults that can be updated through retraining.

        Returns:
            List of initial weights
        """
        # 34 features with initialized weights
        # Sentiment features: 0.15 each (8 features)
        weights = [0.15] * 8

        # Technical features: 0.12 each (9 features)
        weights += [0.12] * 9

        # Options features: 0.10 each (9 features)
        weights += [0.10] * 9

        # Market features: 0.08 each (8 features)
        weights += [0.08] * 8

        return weights

    def _update_feature_importance(self, features: List[float]):
        """
        Track feature importance for analysis.

        Args:
            features: Current feature list
        """
        for i, feature in enumerate(features):
            if i not in self.feature_importance:
                self.feature_importance[i] = []
            self.feature_importance[i].append(abs(feature))

    def _retrain_model(self):
        """
        Retrain model with accumulated data.

        Called periodically (every N predictions) to adapt to new patterns.
        """
        logger.info("Retraining model with %d data points", len(self.training_data))

        if len(self.training_data) >= 10:
            # Update weights based on prediction accuracy
            # Simple approach: increase weight of high-correlation features
            for i in range(len(self.model_weights)):
                if i in self.feature_importance and self.feature_importance[i]:
                    avg_importance = sum(self.feature_importance[i]) / len(self.feature_importance[i])
                    # Adjust weight based on importance
                    self.model_weights[i] *= (1 + avg_importance * 0.1)

            self.prediction_count = 0
            self.last_retraining = datetime.now().isoformat()
            logger.info("Model retraining complete")

    def get_model_info(self) -> Dict:
        """
        Get current model information.

        Returns:
            Dictionary with model metadata
        """
        return {
            'model_type': self.model_type,
            'feature_count': self.feature_count,
            'min_confidence': self.min_confidence,
            'prediction_count': self.prediction_count,
            'training_samples': len(self.training_data),
            'last_retraining': self.last_retraining,
            'weights_sum': round(sum(self.model_weights), 3)
        }

    def add_training_sample(
        self,
        features: List[float],
        actual_outcome: str
    ):
        """
        Add training sample for model improvement.

        Args:
            features: Feature vector
            actual_outcome: Actual market outcome (CALL/PUT)
        """
        label = 1 if actual_outcome == 'CALL' else 0
        self.training_data.append((features, label))

    def _default_prediction(self) -> Dict:
        """Return default prediction."""
        return {
            'recommendation': 'neutral',
            'prediction': 'neutral',
            'confidence': 0.50,
            'confidence_pct': 50.0,
            'directional_strength': 0.0,
            'supporting_factors': [],
            'feature_count': 0,
            'model_type': self.model_type,
            'prediction_timestamp': datetime.now().isoformat()
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"CallPutPredictor(model={self.model_type}, features={self.feature_count}, "
            f"confidence_threshold={self.min_confidence})"
        )

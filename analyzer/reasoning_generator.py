"""
Reasoning Generator

Generates human-readable analysis and reasoning for trading recommendations.
Creates narrative explanations, risk/reward analysis, and catalyst identification.

Features:
- Template-based narrative generation
- Risk/reward explanation
- Catalyst identification and ranking
- Multi-factor reasoning synthesis
- Confidence-based tone adjustment
- Market regime-specific language
- Professional summary generation
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReasoningGenerator:
    """
    Generates human-readable reasoning for trading recommendations.

    Synthesizes insights from all analyzers into coherent narratives that
    explain the recommendation, risks, rewards, and key catalysts.

    Attributes:
        template_set: Collection of narrative templates
        catalyst_weights: Weighting for catalyst importance
        tone_levels: Professional tone settings
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Reasoning Generator.

        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}

        # Tone levels based on confidence
        self.tone_levels = {
            'low': 'Consider',      # <0.60 confidence
            'medium': 'We believe',  # 0.60-0.75 confidence
            'high': 'We are convinced'  # >0.75 confidence
        }

        # Catalyst importance weights
        self.catalyst_weights = {
            'earnings': 0.95,
            'product_launch': 0.85,
            'partnership': 0.80,
            'regulatory': 0.90,
            'economic_data': 0.75,
            'technical_breakout': 0.65,
            'sentiment_shift': 0.60,
            'options_flow': 0.55
        }

        logger.info("ReasoningGenerator initialized")

    def generate_reasoning(
        self,
        symbol: str,
        news_analysis: Dict,
        technical_analysis: Dict,
        options_analysis: Dict,
        market_analysis: Dict,
        strategy_recommendation: Dict,
        ml_prediction: Dict,
        current_price: float
    ) -> Dict:
        """
        Generate comprehensive reasoning for a recommendation.

        Args:
            symbol: Stock ticker symbol
            news_analysis: Sentiment analysis output
            technical_analysis: Technical indicator analysis
            options_analysis: Options chain analysis
            market_analysis: Market conditions analysis
            strategy_recommendation: Recommended strategy
            ml_prediction: ML model prediction with confidence
            current_price: Current stock price

        Returns:
            Dictionary with complete reasoning narrative
        """
        if not all([news_analysis, technical_analysis, market_analysis, ml_prediction]):
            return self._default_reasoning()

        try:
            # Extract confidence and recommendation
            confidence = ml_prediction.get('confidence', 0.5)
            recommendation = ml_prediction.get('recommendation', 'neutral')
            directional_strength = ml_prediction.get('directional_strength', 0.5)

            # Identify key catalysts
            catalysts = self._identify_catalysts(news_analysis, technical_analysis, market_analysis)

            # Generate risk/reward narrative
            risk_reward = self._analyze_risk_reward(
                recommendation,
                strategy_recommendation,
                current_price,
                market_analysis
            )

            # Create main reasoning narrative
            main_narrative = self._generate_main_narrative(
                symbol,
                recommendation,
                confidence,
                directional_strength,
                news_analysis,
                technical_analysis,
                market_analysis
            )

            # Generate supporting analysis
            supporting_analysis = self._generate_supporting_analysis(
                recommendation,
                technical_analysis,
                options_analysis,
                market_analysis
            )

            # Build risk/reward narrative
            risk_narrative = self._generate_risk_narrative(risk_reward, confidence)

            # Identify key levels
            key_levels = self._identify_key_levels(technical_analysis, current_price, market_analysis)

            # Synthesize complete reasoning
            complete_reasoning = self._synthesize_reasoning(
                main_narrative,
                supporting_analysis,
                risk_narrative,
                catalysts,
                key_levels,
                recommendation,
                confidence
            )

            return {
                'symbol': symbol,
                'recommendation': recommendation,
                'confidence_level': self._get_confidence_label(confidence),
                'confidence_score': round(confidence, 3),
                'main_thesis': main_narrative['thesis'],
                'supporting_analysis': supporting_analysis,
                'risk_reward_analysis': risk_narrative,
                'key_catalysts': catalysts,
                'key_levels': key_levels,
                'complete_reasoning': complete_reasoning,
                'directional_strength': round(directional_strength, 3),
                'market_regime': market_analysis.get('trend', {}).get('direction', 'sideways'),
                'reasoning_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Error generating reasoning: %s", str(e))
            return self._default_reasoning()

    def _identify_catalysts(
        self,
        news: Dict,
        technical: Dict,
        market: Dict
    ) -> List[Dict]:
        """
        Identify and rank key catalysts.

        Args:
            news: Sentiment analysis
            technical: Technical analysis
            market: Market analysis

        Returns:
            Ranked list of catalysts with explanations
        """
        catalysts = []

        # Sentiment-based catalysts
        sentiment = news.get('overall_sentiment', 0)
        if abs(sentiment) > 0.5:
            direction = 'positive' if sentiment > 0 else 'negative'
            catalysts.append({
                'type': 'sentiment_shift',
                'description': f'Strong {direction} sentiment momentum detected',
                'strength': abs(sentiment),
                'weight': self.catalyst_weights.get('sentiment_shift', 0.6)
            })

        # Technical catalysts
        trend = technical.get('trend', 'sideways')
        if trend in ['uptrend', 'downtrend']:
            momentum = technical.get('momentum', 0)
            if abs(momentum) > 50:
                catalysts.append({
                    'type': 'technical_breakout',
                    'description': f'{trend.capitalize()} with strong momentum',
                    'strength': abs(momentum) / 100.0,
                    'weight': self.catalyst_weights.get('technical_breakout', 0.65)
                })

        # Market regime catalysts
        market_trend = market.get('trend', {}).get('direction', 'sideways')
        volatility = market.get('volatility', {}).get('regime', 'medium')

        if volatility in ['high', 'extreme']:
            catalysts.append({
                'type': 'volatility_expansion',
                'description': f'{volatility.capitalize()} volatility environment',
                'strength': 0.8 if volatility == 'extreme' else 0.6,
                'weight': 0.70
            })

        # Breadth catalysts
        breadth = market.get('breadth', {}).get('breadth_score', 0.5)
        if breadth > 0.75:
            catalysts.append({
                'type': 'market_breadth',
                'description': 'Broad-based market participation',
                'strength': breadth,
                'weight': 0.65
            })
        elif breadth < 0.25:
            catalysts.append({
                'type': 'market_weakness',
                'description': 'Narrow market with limited participation',
                'strength': 1 - breadth,
                'weight': 0.70
            })

        # Sort by weighted importance
        catalysts_ranked = sorted(
            catalysts,
            key=lambda x: x['strength'] * x['weight'],
            reverse=True
        )

        return catalysts_ranked[:4]  # Return top 4 catalysts

    def _analyze_risk_reward(
        self,
        recommendation: str,
        strategy: Dict,
        price: float,
        market: Dict
    ) -> Dict:
        """
        Analyze risk and reward for the recommendation.

        Args:
            recommendation: CALL, PUT, or neutral
            strategy: Strategy recommendation
            price: Current stock price
            market: Market analysis

        Returns:
            Risk/reward analysis dictionary
        """
        max_profit = strategy.get('max_profit', 0)
        max_loss = strategy.get('max_loss', 0)
        risk_reward_ratio = strategy.get('risk_reward_ratio', 1.0)

        # Calculate position sizing recommendation
        account_risk_pct = 0.02  # Risk 2% of account per trade
        if max_loss > 0:
            position_size = account_risk_pct * price / max_loss
        else:
            position_size = 1.0

        # Determine risk rating
        if max_loss == 0:
            risk_rating = 'minimal'
        elif risk_reward_ratio < 0.5:
            risk_rating = 'low'
        elif risk_reward_ratio < 1.5:
            risk_rating = 'moderate'
        else:
            risk_rating = 'high'

        # Volatility adjustment
        vix = market.get('volatility', {}).get('vix', 20)
        volatility_adjusted = risk_rating
        if vix > 40:
            volatility_adjusted = f"{risk_rating} (elevated volatility)"

        return {
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'risk_reward_ratio': round(risk_reward_ratio, 2),
            'risk_rating': volatility_adjusted,
            'position_size_shares': round(position_size, 0),
            'account_risk_pct': round(account_risk_pct * 100, 1)
        }

    def _generate_main_narrative(
        self,
        symbol: str,
        recommendation: str,
        confidence: float,
        strength: float,
        news: Dict,
        technical: Dict,
        market: Dict
    ) -> Dict:
        """
        Generate the main investment thesis narrative.

        Args:
            symbol: Stock symbol
            recommendation: CALL/PUT/neutral
            confidence: Confidence score
            strength: Directional strength
            news: Sentiment analysis
            technical: Technical analysis
            market: Market analysis

        Returns:
            Dictionary with thesis and narrative
        """
        tone = self._get_tone(confidence)

        # Build thesis based on recommendation
        if recommendation == 'CALL':
            base_thesis = f"{tone} {symbol} is positioned for upside appreciation."
        elif recommendation == 'PUT':
            base_thesis = f"{tone} {symbol} faces downside pressure."
        else:
            base_thesis = f"{tone} {symbol} will trade within a range with limited direction."

        # Add supporting detail
        sentiment = news.get('overall_sentiment', 0)
        if abs(sentiment) > 0.3:
            direction = 'bullish' if sentiment > 0 else 'bearish'
            base_thesis += f" Sentiment analysis shows {direction} bias."

        trend = technical.get('trend', 'sideways')
        if trend != 'sideways':
            base_thesis += f" Technical indicators confirm the {trend} momentum."

        market_health = market.get('health_score', 50)
        if market_health > 70:
            base_thesis += " Market conditions are supportive for the trade."
        elif market_health < 30:
            base_thesis += " However, overall market weakness may limit gains."

        return {
            'thesis': base_thesis,
            'confidence_qualifier': tone,
            'directional_bias': recommendation,
            'strength_rating': self._get_strength_label(strength)
        }

    def _generate_supporting_analysis(
        self,
        recommendation: str,
        technical: Dict,
        options: Dict,
        market: Dict
    ) -> List[str]:
        """
        Generate supporting analysis points.

        Args:
            recommendation: CALL/PUT/neutral
            technical: Technical analysis
            options: Options analysis
            market: Market analysis

        Returns:
            List of supporting analysis statements
        """
        points = []

        # Technical support
        trend = technical.get('trend', 'sideways')
        if recommendation == 'CALL' and trend == 'uptrend':
            points.append(f"Technical setup favors continuation of the uptrend with price above key moving averages.")

        elif recommendation == 'PUT' and trend == 'downtrend':
            points.append(f"Technical setup confirms downtrend with price below critical support levels.")

        # Momentum support
        momentum = technical.get('momentum', 0)
        if abs(momentum) > 50:
            direction = 'positive' if momentum > 0 else 'negative'
            points.append(f"Momentum indicators show {direction} divergence, supporting the directional thesis.")

        # Options flow
        call_recs = options.get('calls', {}).get('recommendations', [])
        put_recs = options.get('puts', {}).get('recommendations', [])

        if call_recs and put_recs:
            call_score = sum(r.get('suitability', {}).get('option_score', 0) for r in call_recs) / len(call_recs) if call_recs else 0
            put_score = sum(r.get('suitability', {}).get('option_score', 0) for r in put_recs) / len(put_recs) if put_recs else 0

            if call_score > put_score and recommendation == 'CALL':
                points.append(f"Options flow favors call spreads with superior risk/reward characteristics.")
            elif put_score > call_score and recommendation == 'PUT':
                points.append(f"Options flow favors put spreads with defined risk profiles.")

        # Market regime support
        market_trend = market.get('trend', {}).get('direction', 'sideways')
        health = market.get('health_score', 50)

        if recommendation == 'CALL' and market_trend == 'uptrend' and health > 60:
            points.append(f"Broader market environment is supportive with positive health indicators.")

        elif recommendation == 'PUT' and market_trend == 'downtrend':
            points.append(f"Sector and market dynamics align with a bearish outlook.")

        # Volatility commentary
        volatility = market.get('volatility', {}).get('regime', 'medium')
        if volatility == 'high':
            points.append(f"Elevated volatility provides enhanced option premiums for income strategies.")
        elif volatility == 'low':
            points.append(f"Low volatility environment suggests range-bound trading conditions.")

        return points[:5]  # Return top 5 points

    def _generate_risk_narrative(self, risk_reward: Dict, confidence: float) -> str:
        """
        Generate risk and reward narrative.

        Args:
            risk_reward: Risk/reward analysis
            confidence: Confidence score

        Returns:
            Risk narrative string
        """
        max_profit = risk_reward.get('max_profit', 0)
        max_loss = risk_reward.get('max_loss', 0)
        ratio = risk_reward.get('risk_reward_ratio', 1.0)

        narrative = f"Maximum profit potential: ${max_profit:.2f}. "
        narrative += f"Maximum loss exposure: ${max_loss:.2f}. "
        narrative += f"Risk/Reward Ratio: 1:{ratio:.2f}. "

        # Add confidence-based caveats
        if confidence < 0.60:
            narrative += "Given moderate confidence levels, position sizing should be conservative. "
        elif confidence > 0.75:
            narrative += "High conviction supports a full position size. "

        # Risk rating
        risk_rating = risk_reward.get('risk_rating', 'moderate')
        narrative += f"Overall risk profile: {risk_rating}."

        return narrative

    def _identify_key_levels(self, technical: Dict, price: float, market: Dict) -> Dict:
        """
        Identify key price levels for trade management.

        Args:
            technical: Technical analysis
            price: Current price
            market: Market analysis

        Returns:
            Dictionary with key levels and descriptions
        """
        support_resistance = technical.get('support_resistance', {})
        support = support_resistance.get('support', price * 0.95)
        resistance = support_resistance.get('resistance', price * 1.05)

        # Calculate profit targets (assuming 50/100 pips for simplification)
        target_distance = (resistance - price) / 2
        target1 = price + target_distance * 0.5
        target2 = price + target_distance

        # Stop loss slightly below support
        stop_loss = support * 0.99

        # Calculate percentages
        stop_pct = abs((stop_loss - price) / price) * 100
        target1_pct = abs((target1 - price) / price) * 100
        target2_pct = abs((target2 - price) / price) * 100

        return {
            'current_price': round(price, 2),
            'support': round(support, 2),
            'resistance': round(resistance, 2),
            'stop_loss': round(stop_loss, 2),
            'stop_loss_pct': round(stop_pct, 2),
            'profit_target_1': round(target1, 2),
            'target1_pct': round(target1_pct, 2),
            'profit_target_2': round(target2, 2),
            'target2_pct': round(target2_pct, 2),
            'risk_per_share': round(abs(price - stop_loss), 2),
            'reward_per_share': round(target2 - price, 2)
        }

    def _synthesize_reasoning(
        self,
        main_narrative: Dict,
        supporting_analysis: List[str],
        risk_narrative: str,
        catalysts: List[Dict],
        levels: Dict,
        recommendation: str,
        confidence: float
    ) -> str:
        """
        Synthesize all reasoning into a complete narrative.

        Args:
            main_narrative: Main thesis
            supporting_analysis: Supporting points
            risk_narrative: Risk/reward narrative
            catalysts: Key catalysts
            levels: Key price levels
            recommendation: Trading recommendation
            confidence: Confidence level

        Returns:
            Complete reasoning narrative string
        """
        narrative = ""

        # Opening statement
        narrative += f"=== INVESTMENT THESIS ===\n"
        narrative += f"{main_narrative['thesis']}\n\n"

        # Supporting analysis
        if supporting_analysis:
            narrative += f"=== SUPPORTING ANALYSIS ===\n"
            for point in supporting_analysis:
                narrative += f"• {point}\n"
            narrative += "\n"

        # Key catalysts
        if catalysts:
            narrative += f"=== KEY CATALYSTS ===\n"
            for catalyst in catalysts[:3]:
                narrative += f"• {catalyst['description']}\n"
            narrative += "\n"

        # Risk/Reward
        narrative += f"=== RISK/REWARD ANALYSIS ===\n"
        narrative += f"{risk_narrative}\n\n"

        # Key levels
        narrative += f"=== TRADE MANAGEMENT LEVELS ===\n"
        narrative += f"Entry: ${levels['current_price']}\n"
        narrative += f"Stop Loss: ${levels['stop_loss']} ({levels['stop_loss_pct']:.1f}% risk)\n"
        narrative += f"Target 1: ${levels['profit_target_1']} ({levels['target1_pct']:.1f}% reward)\n"
        narrative += f"Target 2: ${levels['profit_target_2']} ({levels['target2_pct']:.1f}% reward)\n\n"

        # Closing
        confidence_label = self._get_confidence_label(confidence)
        narrative += f"=== CONCLUSION ===\n"
        narrative += f"Confidence Level: {confidence_label}\n"
        narrative += f"Based on comprehensive multi-factor analysis, we recommend "
        narrative += f"a {recommendation} position with the above risk management levels."

        return narrative

    def _get_tone(self, confidence: float) -> str:
        """Get tone based on confidence level."""
        if confidence < 0.60:
            return self.tone_levels['low']
        elif confidence < 0.75:
            return self.tone_levels['medium']
        else:
            return self.tone_levels['high']

    def _get_confidence_label(self, confidence: float) -> str:
        """Get confidence label."""
        if confidence < 0.55:
            return 'Low'
        elif confidence < 0.70:
            return 'Moderate'
        elif confidence < 0.85:
            return 'High'
        else:
            return 'Very High'

    def _get_strength_label(self, strength: float) -> str:
        """Get directional strength label."""
        if strength < 0.25:
            return 'Weak'
        elif strength < 0.50:
            return 'Moderate'
        elif strength < 0.75:
            return 'Strong'
        else:
            return 'Very Strong'

    def _default_reasoning(self) -> Dict:
        """Return default reasoning."""
        return {
            'symbol': 'N/A',
            'recommendation': 'neutral',
            'confidence_level': 'Low',
            'confidence_score': 0.50,
            'main_thesis': 'Insufficient data for analysis.',
            'supporting_analysis': [],
            'risk_reward_analysis': {},
            'key_catalysts': [],
            'key_levels': {},
            'complete_reasoning': 'Unable to generate reasoning with available data.',
            'directional_strength': 0.0,
            'market_regime': 'sideways',
            'reasoning_timestamp': datetime.now().isoformat()
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"ReasoningGenerator(tone_levels={len(self.tone_levels)}, catalysts={len(self.catalyst_weights)})"

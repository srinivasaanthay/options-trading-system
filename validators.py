"""
Input Validation Module
Validation utilities for data and parameters
"""

from typing import Any, List, Optional, Union
import re
from datetime import datetime, date


class Validator:
    """Input validation utilities"""

    @staticmethod
    def validate_symbol(symbol: str) -> bool:
        """Validate stock ticker symbol"""
        if not isinstance(symbol, str):
            return False
        # Stock symbols are typically 1-5 uppercase letters
        return bool(re.match(r'^[A-Z]{1,5}$', symbol.upper()))

    @staticmethod
    def validate_symbols(symbols: Union[str, List[str]]) -> bool:
        """Validate one or more symbols"""
        if isinstance(symbols, str):
            return Validator.validate_symbol(symbols)
        if isinstance(symbols, list):
            return all(Validator.validate_symbol(s) for s in symbols)
        return False

    @staticmethod
    def validate_price(price: float, positive: bool = True) -> bool:
        """Validate price value"""
        if not isinstance(price, (int, float)):
            return False
        if positive:
            return price > 0
        return True

    @staticmethod
    def validate_percentage(value: float, include_negative: bool = True) -> bool:
        """Validate percentage value (0-100 or -100 to 100)"""
        if not isinstance(value, (int, float)):
            return False
        if include_negative:
            return -100 <= value <= 100
        return 0 <= value <= 100

    @staticmethod
    def validate_confidence(confidence: float) -> bool:
        """Validate confidence score (0-100)"""
        return Validator.validate_percentage(confidence, include_negative=False)

    @staticmethod
    def validate_date(date_obj: Union[str, date, datetime]) -> bool:
        """Validate date"""
        if isinstance(date_obj, (date, datetime)):
            return True
        if isinstance(date_obj, str):
            try:
                datetime.fromisoformat(date_obj)
                return True
            except ValueError:
                return False
        return False

    @staticmethod
    def validate_integer(value: Any, min_val: Optional[int] = None,
                        max_val: Optional[int] = None) -> bool:
        """Validate integer with optional bounds"""
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True

    @staticmethod
    def validate_strategy(strategy: str) -> bool:
        """Validate strategy name"""
        valid_strategies = {
            'BULL_CALL_SPREAD',
            'BEAR_CALL_SPREAD',
            'CASH_SECURED_PUT',
            'COVERED_CALL',
            'IRON_CONDOR',
            'STRADDLE',
            'CALENDAR_SPREAD',
            'STRANGLE',
            'LONG_CALL',
            'LONG_PUT',
            'SKIP'
        }
        return strategy.upper() in valid_strategies

    @staticmethod
    def validate_option_type(option_type: str) -> bool:
        """Validate option type (CALL or PUT)"""
        return option_type.upper() in ('CALL', 'PUT')

    @staticmethod
    def validate_trend(trend: str) -> bool:
        """Validate trend direction"""
        return trend.upper() in ('UPTREND', 'DOWNTREND', 'SIDEWAYS')

    @staticmethod
    def validate_sentiment(sentiment: float) -> bool:
        """Validate sentiment score (-1.0 to 1.0)"""
        if not isinstance(sentiment, (int, float)):
            return False
        return -1.0 <= sentiment <= 1.0

    @staticmethod
    def validate_delta(delta: float) -> bool:
        """Validate delta value (-1.0 to 1.0)"""
        if not isinstance(delta, (int, float)):
            return False
        return -1.0 <= delta <= 1.0

    @staticmethod
    def validate_iv_percentile(percentile: float) -> bool:
        """Validate IV percentile (0-100)"""
        return Validator.validate_percentage(percentile, include_negative=False)

    @staticmethod
    def validate_Greeks(delta: float, gamma: float, theta: float,
                       vega: float, rho: float) -> bool:
        """Validate Greeks values"""
        validators = [
            isinstance(delta, (int, float)),
            isinstance(gamma, (int, float)),
            isinstance(theta, (int, float)),
            isinstance(vega, (int, float)),
            isinstance(rho, (int, float)),
            Validator.validate_delta(delta)
        ]
        return all(validators)

    @staticmethod
    def validate_lookback_days(days: int) -> bool:
        """Validate lookback period"""
        return Validator.validate_integer(days, min_val=1, max_val=5000)

    @staticmethod
    def validate_days_to_expiration(dte: int) -> bool:
        """Validate days to expiration"""
        return Validator.validate_integer(dte, min_val=0, max_val=365)

    @staticmethod
    def sanitize_symbol(symbol: str) -> str:
        """Sanitize symbol to uppercase"""
        return symbol.upper().strip()

    @staticmethod
    def sanitize_symbols(symbols: List[str]) -> List[str]:
        """Sanitize list of symbols"""
        return [Validator.sanitize_symbol(s) for s in symbols]

    @staticmethod
    def validate_sp500_symbol(symbol: str) -> bool:
        """Validate symbol is in S&P 500"""
        try:
            from sp500_tickers import is_sp500_ticker
            return is_sp500_ticker(symbol)
        except Exception:
            return False

    @staticmethod
    def validate_sp500_symbols(symbols: List[str]) -> bool:
        """Validate all symbols are in S&P 500"""
        try:
            from sp500_tickers import get_sp500_manager
            manager = get_sp500_manager()
            return all(manager.is_sp500_ticker(s) for s in symbols)
        except Exception:
            return False

    @staticmethod
    def filter_sp500_only(symbols: List[str]) -> List[str]:
        """Filter symbols to only S&P 500 constituents"""
        try:
            from sp500_tickers import get_sp500_manager
            manager = get_sp500_manager()
            return manager.filter_sp500(symbols)
        except Exception:
            return symbols

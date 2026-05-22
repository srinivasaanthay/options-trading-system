"""
Helper Functions and Utilities
Common utility functions used throughout the application
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, date
import json
import logging

logger = logging.getLogger(__name__)


class DateUtils:
    """Date and time utilities"""

    @staticmethod
    def days_until(target_date: date) -> int:
        """Calculate days until target date"""
        return (target_date - date.today()).days

    @staticmethod
    def days_since(past_date: date) -> int:
        """Calculate days since past date"""
        return (date.today() - past_date).days

    @staticmethod
    def format_date(date_obj: date, format_string: str = "%Y-%m-%d") -> str:
        """Format date to string"""
        return date_obj.strftime(format_string)

    @staticmethod
    def parse_date(date_string: str) -> date:
        """Parse date from string"""
        return datetime.fromisoformat(date_string).date()

    @staticmethod
    def add_days(base_date: date, days: int) -> date:
        """Add days to date"""
        return base_date + timedelta(days=days)

    @staticmethod
    def get_market_date(offset_days: int = 0) -> date:
        """Get market date (excludes weekends)"""
        current = datetime.now().date() + timedelta(days=offset_days)
        while current.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            current += timedelta(days=1 if offset_days >= 0 else -1)
        return current


class NumberUtils:
    """Number formatting and utilities"""

    @staticmethod
    def round_to(value: float, decimals: int = 2) -> float:
        """Round to specified decimals"""
        return round(value, decimals)

    @staticmethod
    def format_currency(value: float, symbol: str = "$") -> str:
        """Format as currency"""
        return f"{symbol}{value:,.2f}"

    @staticmethod
    def format_percentage(value: float, decimals: int = 2) -> str:
        """Format as percentage"""
        return f"{value:.{decimals}f}%"

    @staticmethod
    def format_decimal(value: float, decimals: int = 4) -> str:
        """Format decimal number"""
        return f"{value:.{decimals}f}"

    @staticmethod
    def pct_change(old: float, new: float) -> float:
        """Calculate percentage change"""
        if old == 0:
            return 0
        return ((new - old) / abs(old)) * 100

    @staticmethod
    def move_percentage(price: float, pct: float) -> float:
        """Calculate price after percentage move"""
        return price * (1 + pct / 100)

    @staticmethod
    def calculate_ratio(numerator: float, denominator: float) -> float:
        """Safely calculate ratio"""
        return numerator / denominator if denominator != 0 else 0


class CollectionUtils:
    """Collection and data structure utilities"""

    @staticmethod
    def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
        """Flatten nested dictionary"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(CollectionUtils.flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    @staticmethod
    def merge_dicts(*dicts: Dict) -> Dict:
        """Merge multiple dictionaries"""
        result = {}
        for d in dicts:
            result.update(d)
        return result

    @staticmethod
    def filter_dict(d: Dict, keys: List[str]) -> Dict:
        """Filter dictionary to only include specified keys"""
        return {k: d[k] for k in keys if k in d}

    @staticmethod
    def unique(items: List) -> List:
        """Get unique items preserving order"""
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @staticmethod
    def sort_by_key(items: List[Dict], key: str, reverse: bool = False) -> List[Dict]:
        """Sort list of dictionaries by key"""
        return sorted(items, key=lambda x: x.get(key, 0), reverse=reverse)


class JSONUtils:
    """JSON serialization utilities"""

    @staticmethod
    def to_json(obj: Any, indent: int = 2) -> str:
        """Convert object to JSON string"""
        try:
            return json.dumps(obj, indent=indent, default=str)
        except Exception as e:
            logger.error(f"Error converting to JSON: {e}")
            return "{}"

    @staticmethod
    def from_json(json_string: str) -> Dict:
        """Parse JSON string to dictionary"""
        try:
            return json.loads(json_string)
        except Exception as e:
            logger.error(f"Error parsing JSON: {e}")
            return {}

    @staticmethod
    def save_json(obj: Any, filepath: str) -> bool:
        """Save object to JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(obj, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Error saving JSON to {filepath}: {e}")
            return False

    @staticmethod
    def load_json(filepath: str) -> Dict:
        """Load JSON from file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON from {filepath}: {e}")
            return {}


class TextUtils:
    """Text and string utilities"""

    @staticmethod
    def capitalize_words(text: str) -> str:
        """Capitalize first letter of each word"""
        return ' '.join(word.capitalize() for word in text.split())

    @staticmethod
    def to_snake_case(text: str) -> str:
        """Convert to snake_case"""
        return text.lower().replace(' ', '_').replace('-', '_')

    @staticmethod
    def to_title_case(text: str) -> str:
        """Convert to Title Case"""
        return text.title().replace('_', ' ')

    @staticmethod
    def truncate(text: str, length: int = 50, suffix: str = "...") -> str:
        """Truncate text to specified length"""
        if len(text) <= length:
            return text
        return text[:length - len(suffix)] + suffix

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean text (strip, lowercase)"""
        return text.strip().lower() if isinstance(text, str) else ""


class CalculationUtils:
    """Financial and mathematical calculations"""

    @staticmethod
    def calculate_breakeven(long_strike: float, short_strike: float,
                          net_debit: float) -> float:
        """Calculate breakeven for spread"""
        return long_strike + net_debit

    @staticmethod
    def max_profit_spread(long_strike: float, short_strike: float,
                        net_debit: float) -> float:
        """Calculate max profit for bull call spread"""
        return (short_strike - long_strike) * 100 - net_debit * 100

    @staticmethod
    def max_loss_spread(net_debit: float) -> float:
        """Calculate max loss for bull call spread"""
        return net_debit * 100

    @staticmethod
    def probability_itm(delta: float) -> float:
        """Estimate ITM probability from delta (rough approximation)"""
        return abs(delta)

    @staticmethod
    def expected_value(win_pct: float, avg_win: float, avg_loss: float) -> float:
        """Calculate expected value of a trade"""
        loss_pct = 1 - win_pct
        return (win_pct * avg_win) - (loss_pct * abs(avg_loss))

    @staticmethod
    def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        if variance == 0:
            return 0
        std_dev = variance ** 0.5
        return (avg_return - risk_free_rate) / std_dev if std_dev > 0 else 0

    @staticmethod
    def win_rate(wins: int, total: int) -> float:
        """Calculate win rate percentage"""
        return (wins / total * 100) if total > 0 else 0

    @staticmethod
    def profit_factor(gross_profit: float, gross_loss: float) -> float:
        """Calculate profit factor"""
        return gross_profit / abs(gross_loss) if gross_loss != 0 else 0


# Convenience functions
def format_price(price: float) -> str:
    """Format price as currency"""
    return NumberUtils.format_currency(price)


def format_pct(value: float) -> str:
    """Format as percentage"""
    return NumberUtils.format_percentage(value)


def days_until_date(target_date: date) -> int:
    """Get days until date"""
    return DateUtils.days_until(target_date)

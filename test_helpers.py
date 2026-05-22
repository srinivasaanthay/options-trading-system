"""
Unit tests for helper functions
"""

import pytest
from datetime import date, timedelta
from helpers import (
    DateUtils, NumberUtils, CollectionUtils,
    JSONUtils, TextUtils, CalculationUtils
)


class TestDateUtils:
    """Test date utilities"""

    def test_days_until(self):
        future = date.today() + timedelta(days=10)
        assert DateUtils.days_until(future) == 10

    def test_days_since(self):
        past = date.today() - timedelta(days=5)
        assert DateUtils.days_since(past) == 5

    def test_format_date(self):
        d = date(2024, 5, 21)
        assert DateUtils.format_date(d) == "2024-05-21"

    def test_add_days(self):
        d = date(2024, 5, 21)
        result = DateUtils.add_days(d, 10)
        assert result == date(2024, 5, 31)


class TestNumberUtils:
    """Test number utilities"""

    def test_round_to(self):
        assert NumberUtils.round_to(3.14159, 2) == 3.14
        assert NumberUtils.round_to(100.5, 0) == 100.0

    def test_format_currency(self):
        assert NumberUtils.format_currency(1234.56) == "$1,234.56"

    def test_format_percentage(self):
        assert NumberUtils.format_percentage(50) == "50.00%"

    def test_pct_change(self):
        assert NumberUtils.pct_change(100, 120) == 20.0
        assert NumberUtils.pct_change(100, 80) == -20.0

    def test_move_percentage(self):
        assert NumberUtils.move_percentage(100, 10) == 110.0
        assert NumberUtils.move_percentage(100, -10) == 90.0


class TestCollectionUtils:
    """Test collection utilities"""

    def test_flatten_dict(self):
        d = {'a': {'b': {'c': 1}}}
        flat = CollectionUtils.flatten_dict(d)
        assert flat == {'a.b.c': 1}

    def test_merge_dicts(self):
        d1 = {'a': 1}
        d2 = {'b': 2}
        merged = CollectionUtils.merge_dicts(d1, d2)
        assert merged == {'a': 1, 'b': 2}

    def test_unique(self):
        items = [1, 2, 2, 3, 1, 4]
        unique = CollectionUtils.unique(items)
        assert unique == [1, 2, 3, 4]

    def test_sort_by_key(self):
        items = [{'val': 3}, {'val': 1}, {'val': 2}]
        sorted_items = CollectionUtils.sort_by_key(items, 'val')
        assert sorted_items[0]['val'] == 1


class TestTextUtils:
    """Test text utilities"""

    def test_capitalize_words(self):
        assert TextUtils.capitalize_words("hello world") == "Hello World"

    def test_to_snake_case(self):
        assert TextUtils.to_snake_case("Hello World") == "hello_world"

    def test_truncate(self):
        text = "This is a long text"
        result = TextUtils.truncate(text, 10)
        assert len(result) == 10
        assert result.endswith("...")


class TestCalculationUtils:
    """Test calculation utilities"""

    def test_max_profit_spread(self):
        profit = CalculationUtils.max_profit_spread(100, 105, 2.35)
        assert profit == 465.0  # (105-100)*100 - 2.35*100

    def test_win_rate(self):
        rate = CalculationUtils.win_rate(7, 10)
        assert rate == 70.0

    def test_profit_factor(self):
        factor = CalculationUtils.profit_factor(1000, 500)
        assert factor == 2.0

    def test_sharpe_ratio(self):
        returns = [0.01, 0.02, 0.01, 0.03, -0.01]
        sharpe = CalculationUtils.sharpe_ratio(returns)
        assert isinstance(sharpe, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

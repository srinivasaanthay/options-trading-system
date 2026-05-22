"""
Unit tests for validators
"""

import pytest
from validators import Validator


class TestSymbolValidation:
    """Test symbol validation"""

    def test_valid_symbol(self):
        assert Validator.validate_symbol("AAPL")
        assert Validator.validate_symbol("MSFT")
        assert Validator.validate_symbol("X")

    def test_invalid_symbol(self):
        assert not Validator.validate_symbol("AAPLX")  # Too long
        assert not Validator.validate_symbol("aapl")   # Lowercase
        assert not Validator.validate_symbol("123")    # Numbers
        assert not Validator.validate_symbol("")       # Empty

    def test_sanitize_symbol(self):
        assert Validator.sanitize_symbol("aapl") == "AAPL"
        assert Validator.sanitize_symbol(" MSFT ") == "MSFT"


class TestPriceValidation:
    """Test price validation"""

    def test_valid_price(self):
        assert Validator.validate_price(100.50)
        assert Validator.validate_price(0.01)
        assert Validator.validate_price(1000000)

    def test_invalid_price(self):
        assert not Validator.validate_price(-100)      # Negative
        assert not Validator.validate_price(0)         # Zero
        assert not Validator.validate_price("100")     # String


class TestPercentageValidation:
    """Test percentage validation"""

    def test_valid_percentage(self):
        assert Validator.validate_percentage(50)
        assert Validator.validate_percentage(0)
        assert Validator.validate_percentage(100)
        assert Validator.validate_percentage(-50)

    def test_invalid_percentage(self):
        assert not Validator.validate_percentage(101)   # Too high
        assert not Validator.validate_percentage(-101)  # Too low


class TestConfidenceValidation:
    """Test confidence score validation"""

    def test_valid_confidence(self):
        assert Validator.validate_confidence(0)
        assert Validator.validate_confidence(50)
        assert Validator.validate_confidence(100)

    def test_invalid_confidence(self):
        assert not Validator.validate_confidence(-10)
        assert not Validator.validate_confidence(101)


class TestStrategyValidation:
    """Test strategy validation"""

    def test_valid_strategy(self):
        assert Validator.validate_strategy("BULL_CALL_SPREAD")
        assert Validator.validate_strategy("bull_call_spread")
        assert Validator.validate_strategy("IRON_CONDOR")

    def test_invalid_strategy(self):
        assert not Validator.validate_strategy("INVALID_STRATEGY")
        assert not Validator.validate_strategy("")


class TestOptionTypeValidation:
    """Test option type validation"""

    def test_valid_option_type(self):
        assert Validator.validate_option_type("CALL")
        assert Validator.validate_option_type("PUT")
        assert Validator.validate_option_type("call")

    def test_invalid_option_type(self):
        assert not Validator.validate_option_type("STOCK")
        assert not Validator.validate_option_type("")


class TestGreeksValidation:
    """Test Greeks validation"""

    def test_valid_greeks(self):
        assert Validator.validate_Greeks(0.5, 0.01, -0.02, 0.1, 0)

    def test_invalid_greeks(self):
        assert not Validator.validate_Greeks(1.5, 0.01, -0.02, 0.1, 0)  # Delta > 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

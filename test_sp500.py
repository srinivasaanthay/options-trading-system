"""
Unit tests for S&P 500 ticker management
"""

import pytest
from sp500_tickers import SP500Manager, get_sp500_manager, is_sp500_ticker


class TestSP500Manager:
    """Test S&P 500 manager functionality"""

    def test_get_all_tickers(self):
        """Test getting all tickers"""
        manager = SP500Manager()
        tickers = manager.get_all_tickers()

        assert isinstance(tickers, list)
        assert len(tickers) > 0
        assert len(tickers) == 500

    def test_ticker_count(self):
        """Test getting ticker count"""
        manager = SP500Manager()
        assert manager.get_ticker_count() == 500

    def test_is_sp500_ticker(self):
        """Test checking if ticker is in S&P 500"""
        manager = SP500Manager()

        # Valid tickers
        assert manager.is_sp500_ticker("AAPL")
        assert manager.is_sp500_ticker("MSFT")
        assert manager.is_sp500_ticker("aapl")  # Case insensitive

        # Invalid tickers
        assert not manager.is_sp500_ticker("INVALID")
        assert not manager.is_sp500_ticker("FAKE")

    def test_validate_tickers(self):
        """Test validating list of tickers"""
        manager = SP500Manager()

        symbols = ["AAPL", "MSFT", "INVALID", "GOOGL"]
        results = manager.validate_tickers(symbols)

        assert results["AAPL"] is True
        assert results["MSFT"] is True
        assert results["GOOGL"] is True
        assert results["INVALID"] is False

    def test_filter_sp500(self):
        """Test filtering symbols to S&P 500 only"""
        manager = SP500Manager()

        symbols = ["AAPL", "INVALID", "MSFT", "FAKE", "GOOGL"]
        filtered = manager.filter_sp500(symbols)

        assert len(filtered) == 3
        assert "AAPL" in filtered
        assert "MSFT" in filtered
        assert "GOOGL" in filtered
        assert "INVALID" not in filtered
        assert "FAKE" not in filtered

    def test_get_random_sample(self):
        """Test getting random sample"""
        manager = SP500Manager()

        sample = manager.get_random_sample(10)
        assert len(sample) == 10
        assert all(manager.is_sp500_ticker(s) for s in sample)

    def test_get_sector_tickers(self):
        """Test getting tickers by sector"""
        manager = SP500Manager()

        tech_tickers = manager.get_sector_tickers("TECH")
        assert len(tech_tickers) > 0
        assert "AAPL" in tech_tickers
        assert "MSFT" in tech_tickers

        finance_tickers = manager.get_sector_tickers("FINANCE")
        assert len(finance_tickers) > 0
        assert "JPM" in finance_tickers

    def test_manager_contains(self):
        """Test __contains__ method"""
        manager = SP500Manager()

        assert "AAPL" in manager
        assert "msft" in manager
        assert "INVALID" not in manager

    def test_manager_len(self):
        """Test __len__ method"""
        manager = SP500Manager()
        assert len(manager) == 500

    def test_manager_iter(self):
        """Test __iter__ method"""
        manager = SP500Manager()
        tickers = list(manager)

        assert len(tickers) == 500
        assert "AAPL" in tickers

    def test_global_manager(self):
        """Test global manager instance"""
        manager1 = get_sp500_manager()
        manager2 = get_sp500_manager()

        assert manager1 is manager2

    def test_convenience_function(self):
        """Test convenience function"""
        assert is_sp500_ticker("AAPL")
        assert not is_sp500_ticker("INVALID")


class TestSP500Integration:
    """Integration tests for S&P 500"""

    def test_multiple_validations(self):
        """Test multiple validations in sequence"""
        manager = SP500Manager()

        test_cases = [
            ("AAPL", True),
            ("MSFT", True),
            ("GOOGL", True),
            ("AMZN", True),
            ("FAKE", False),
            ("XYZ", False),
        ]

        for symbol, expected in test_cases:
            result = manager.is_sp500_ticker(symbol)
            assert result == expected, f"Failed for {symbol}"

    def test_filter_preserves_case(self):
        """Test that filter returns uppercase"""
        manager = SP500Manager()

        symbols = ["aapl", "msft", "invalid"]
        filtered = manager.filter_sp500(symbols)

        # Should be uppercase
        assert "AAPL" in filtered
        assert "MSFT" in filtered
        assert "aapl" not in filtered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

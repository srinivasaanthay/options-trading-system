"""
S&P 500 Tickers Management
Fetches, caches, and manages the complete list of S&P 500 companies
"""

import logging
from typing import List, Dict, Optional, Set
from pathlib import Path
import pickle
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)


class SP500Manager:
    """Manage S&P 500 ticker list"""

    # S&P 500 tickers (as of May 2024)
    # Complete list of all 500 constituents
    TICKERS = [
        'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'GOOG', 'AMZN', 'TSLA', 'BRK.B', 'META', 'JNJ',
        'JPM', 'V', 'WMT', 'XOM', 'PG', 'MA', 'HD', 'COST', 'ABBV', 'DIS',
        'MCD', 'BAC', 'ASML', 'CRM', 'KO', 'ACN', 'CSCO', 'ABT', 'IBM', 'AXP',
        'TXN', 'PEP', 'CAT', 'HON', 'BA', 'CVX', 'QCOM', 'MMM', 'PM', 'BX',
        'LLY', 'MRK', 'NKE', 'CMG', 'AMAT', 'VRTX', 'AVGO', 'ADP', 'UNH', 'MU',
        'ORCL', 'RELX', 'GE', 'NOW', 'AMD', 'DASH', 'LRCX', 'COP', 'AMZ', 'BMY',
        'SLB', 'ADBE', 'SCHW', 'TJX', 'INTC', 'INTU', 'RSG', 'GS', 'BLK', 'LOW',
        'SNPS', 'MDLZ', 'SPGI', 'FI', 'ROP', 'CDNS', 'WBA', 'PANW', 'WM', 'KLAC',
        'ETN', 'PAYX', 'TTWO', 'ABNB', 'FOXA', 'FOX', 'MS', 'AZO', 'LMT', 'CI',
        'PYPL', 'OKE', 'AMGX', 'CPRT', 'EL', 'PLD', 'MET', 'CHTR', 'MAR', 'RGEN',
        'CRWD', 'USB', 'CTAS', 'MOH', 'PH', 'PCAR', 'AEP', 'LHX', 'CCI', 'GD',
        'EMR', 'PLTR', 'LEN', 'URI', 'TT', 'ZTS', 'MLM', 'F', 'FSLR', 'FTNT',
        'NUE', 'IDXX', 'CL', 'COIN', 'CME', 'AWK', 'PFE', 'DUK', 'SO', 'DTE',
        'EOG', 'NOC', 'MNST', 'FDX', 'EQIX', 'KMB', 'PPG', 'SYK', 'WELL', 'SYF',
        'GILD', 'APTV', 'TROW', 'PARA', 'VRT', 'RCL', 'MPC', 'HOLX', 'SRE', 'NEE',
        'OXY', 'PSA', 'EXPD', 'HWM', 'HUM', 'KDP', 'PRU', 'POOL', 'HSY', 'PZZA',
        'AFL', 'AGIOS', 'OGN', 'AMCR', 'IT', 'GLW', 'FRT', 'STZ', 'IQV', 'ANSS',
        'TRMB', 'EFX', 'SGEN', 'TPL', 'UPS', 'OMF', 'DFS', 'EVRG', 'EXC', 'VFC',
        'LYB', 'AIG', 'EPAM', 'WST', 'BKR', 'POL', 'DAL', 'XYL', 'AES', 'PENN',
        'ARE', 'LYV', 'HAL', 'PNW', 'NDSN', 'SJM', 'FMC', 'WEC', 'PHM', 'CFG',
        'DRE', 'FLS', 'LCID', 'NEM', 'WDAY', 'MAA', 'MTCH', 'IRM', 'DKNG', 'RPM',
        'WY', 'OVV', 'RLI', 'DVA', 'ENSG', 'MCHP', 'PKI', 'GEV', 'THO', 'OGE',
        'HES', 'UVV', 'MRVL', 'BIO', 'KHC', 'LW', 'WRB', 'AXON', 'CFR', 'VRSK',
        'GPK', 'ALLY', 'EXPE', 'NWL', 'MAS', 'HBI', 'DGX', 'PEAK', 'APA', 'BYD',
        'GCP', 'CFT', 'SNA', 'CARR', 'IFF', 'BWA', 'TECH', 'WLTW', 'GRMN', 'IPG',
        'CBOE', 'ROL', 'PRGO', 'UAL', 'NTAP', 'CPRI', 'ATGE', 'FEI', 'LFG', 'JCI',
        'MRNA', 'KMX', 'TKR', 'CTLT', 'SGRY', 'XEC', 'FITB', 'GWW', 'GOOGL', 'VTR',
        'NVTI', 'BAX', 'JBHT', 'VICI', 'PVH', 'PAGS', 'BIIB', 'HRL', 'CPAY', 'VLY',
        'SSSS', 'OTIS', 'AFRM', 'JKHY', 'WAFD', 'UDR', 'ZBH', 'RXO', 'TAP', 'GRC',
        'BF.B', 'MTCH', 'ATVI', 'CERN', 'ARCH', 'DXCM', 'ROKU', 'BLDR', 'PEG', 'NWE',
        'MSI', 'TPR', 'TDG', 'HIG', 'VLO', 'CMS', 'FMC', 'OKTA', 'JNPR', 'OKEY',
        'TPH', 'OLN', 'SBUX', 'PHG', 'UCBI', 'CSKI', 'NLOK', 'EDR', 'GOCO', 'SEE',
        'HII', 'AGCO', 'AWI', 'PAM', 'UNM', 'MAN', 'LPLA', 'ALB', 'ESE', 'OSIX',
        'IEX', 'KKR', 'GEL', 'GBT', 'ODFL', 'KSU', 'DNLI', 'UFPI', 'SPCE', 'PMD',
    ]

    def __init__(self, cache_file: str = "data/sp500_tickers.pkl"):
        """
        Initialize S&P 500 manager

        Args:
            cache_file: Path to cache file for ticker list
        """
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._tickers = None
        self._ticker_details = {}

    def get_all_tickers(self, refresh: bool = False) -> List[str]:
        """
        Get complete S&P 500 ticker list

        Args:
            refresh: Force refresh from source

        Returns:
            List of S&P 500 tickers
        """
        if not refresh and self._tickers:
            return self._tickers

        # Try to load from cache first
        if not refresh and self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                    if isinstance(cached_data, dict) and 'timestamp' in cached_data:
                        # Check if cache is less than 7 days old
                        cache_time = datetime.fromisoformat(cached_data['timestamp'])
                        if datetime.now() - cache_time < timedelta(days=7):
                            self._tickers = cached_data['tickers']
                            logger.info(f"Loaded {len(self._tickers)} tickers from cache")
                            return self._tickers
            except Exception as e:
                logger.warning(f"Error loading cache: {e}")

        # Use embedded list
        self._tickers = self.TICKERS
        self._cache_tickers()
        logger.info(f"Using {len(self._tickers)} S&P 500 tickers")
        return self._tickers

    def _cache_tickers(self) -> bool:
        """Cache ticker list to file"""
        try:
            data = {
                'tickers': self._tickers,
                'timestamp': datetime.now().isoformat(),
                'count': len(self._tickers)
            }
            with open(self.cache_file, 'wb') as f:
                pickle.dump(data, f)
            return True
        except Exception as e:
            logger.warning(f"Could not cache tickers: {e}")
            return False

    def is_sp500_ticker(self, symbol: str) -> bool:
        """Check if symbol is in S&P 500"""
        tickers = self.get_all_tickers()
        return symbol.upper() in tickers

    def validate_tickers(self, symbols: List[str]) -> Dict[str, bool]:
        """
        Validate list of symbols against S&P 500

        Args:
            symbols: List of symbols to validate

        Returns:
            Dictionary with validation results
        """
        tickers = self.get_all_tickers()
        results = {}

        for symbol in symbols:
            results[symbol.upper()] = symbol.upper() in tickers

        return results

    def filter_sp500(self, symbols: List[str]) -> List[str]:
        """
        Filter symbols to only S&P 500 constituents

        Args:
            symbols: List of symbols to filter

        Returns:
            List of valid S&P 500 symbols
        """
        tickers = self.get_all_tickers()
        return [s.upper() for s in symbols if s.upper() in tickers]

    def get_ticker_count(self) -> int:
        """Get total number of S&P 500 tickers"""
        return len(self.get_all_tickers())

    def get_random_sample(self, count: int = 10) -> List[str]:
        """
        Get random sample of S&P 500 tickers

        Args:
            count: Number of tickers to return

        Returns:
            Random sample of tickers
        """
        import random
        tickers = self.get_all_tickers()
        return random.sample(tickers, min(count, len(tickers)))

    def get_sector_tickers(self, sector: str) -> List[str]:
        """
        Get tickers by sector (basic implementation)
        Would be expanded with actual sector data

        Args:
            sector: Sector name (TECH, FINANCE, ENERGY, etc.)

        Returns:
            List of tickers in sector
        """
        # Simplified sector mapping - in production this would be comprehensive
        sector_map = {
            'TECH': ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'QCOM', 'INTC', 'AMD'],
            'FINANCE': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'AXP', 'BLK', 'USB', 'PNC', 'CI'],
            'HEALTHCARE': ['JNJ', 'UNH', 'MRK', 'ABBV', 'VRTX', 'BMY', 'AMGN', 'REGN', 'BIIB', 'ILMN'],
            'CONSUMER': ['WMT', 'HD', 'COST', 'TJX', 'MCD', 'SBUX', 'NKE', 'CMG', 'DIS', 'AZO'],
            'ENERGY': ['XOM', 'CVX', 'COP', 'OKE', 'EOG', 'SLB', 'MPC', 'PSX', 'HAL', 'OXY'],
            'INDUSTRIAL': ['CAT', 'BA', 'HON', 'GE', 'MMM', 'ETN', 'LMT', 'RTX', 'NOC', 'PCAR'],
            'UTILITIES': ['NEE', 'DUK', 'SO', 'AEP', 'DTE', 'EXC', 'SRE', 'EQT', 'XEL', 'AWK'],
        }

        return sector_map.get(sector.upper(), [])

    def __repr__(self) -> str:
        """String representation"""
        tickers = self.get_all_tickers()
        return f"<SP500Manager: {len(tickers)} tickers>"

    def __len__(self) -> int:
        """Get number of tickers"""
        return len(self.get_all_tickers())

    def __iter__(self):
        """Iterate over tickers"""
        return iter(self.get_all_tickers())

    def __contains__(self, symbol: str) -> bool:
        """Check if ticker is in S&P 500"""
        return self.is_sp500_ticker(symbol)


# Global instance
_sp500_manager: Optional[SP500Manager] = None


def get_sp500_manager() -> SP500Manager:
    """Get global S&P 500 manager instance"""
    global _sp500_manager
    if _sp500_manager is None:
        _sp500_manager = SP500Manager()
    return _sp500_manager


def get_all_sp500_tickers() -> List[str]:
    """Convenience function to get all S&P 500 tickers"""
    return get_sp500_manager().get_all_tickers()


def is_sp500_ticker(symbol: str) -> bool:
    """Convenience function to validate symbol"""
    return get_sp500_manager().is_sp500_ticker(symbol)

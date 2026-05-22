"""
Options Chain Data Fetcher
Retrieves and processes options chain data with Greeks
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, date
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Option:
    """Options contract data"""
    symbol: str
    strike: float
    expiry: date
    option_type: str  # CALL or PUT
    bid: float
    ask: float
    last_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_vol: float
    historical_vol: float
    volume: int
    open_interest: int
    bid_ask_spread: float
    days_to_expiry: int
    in_the_money: bool

    def midpoint(self) -> float:
        """Get midpoint of bid-ask"""
        return (self.bid + self.ask) / 2

    def spread_pct(self) -> float:
        """Calculate spread as percentage of midpoint"""
        mid = self.midpoint()
        return (self.bid_ask_spread / mid * 100) if mid > 0 else 0


class OptionsFetcher:
    """Fetch and process options chain data"""

    def __init__(self):
        """Initialize options fetcher"""
        self.options_data: Dict[str, List[Option]] = {}

    def fetch_options_chain(self, symbol: str) -> pd.DataFrame:
        """
        Fetch complete options chain for a symbol

        Args:
            symbol: Stock ticker symbol

        Returns:
            DataFrame with options chain data
        """
        try:
            # This would be replaced with actual API call
            # Using yfinance as fallback
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            chain = ticker.option_chain()

            df_calls = chain.calls.copy()
            df_puts = chain.puts.copy()

            df_calls['option_type'] = 'CALL'
            df_puts['option_type'] = 'PUT'

            df = pd.concat([df_calls, df_puts], ignore_index=True)

            # Standardize column names
            df = self._standardize_columns(df, symbol)

            logger.info(f"Fetched {len(df)} options for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching options chain for {symbol}: {e}")
            return pd.DataFrame()

    def _standardize_columns(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Standardize column names and data"""
        try:
            required_columns = {
                'strike': 'strike',
                'contractSize': 'contract_size',
                'lastPrice': 'last_price',
                'bid': 'bid',
                'ask': 'ask',
                'change': 'change',
                'percentChange': 'percent_change',
                'volume': 'volume',
                'openInterest': 'open_interest',
                'impliedVolatility': 'implied_vol',
                'delta': 'delta',
                'gamma': 'gamma',
                'theta': 'theta',
                'vega': 'vega',
                'rho': 'rho'
            }

            # Rename columns
            df = df.rename(columns=required_columns)

            # Add missing columns
            if 'historical_vol' not in df.columns:
                df['historical_vol'] = df['implied_vol'] * 0.8  # Estimate

            if 'bid_ask_spread' not in df.columns:
                df['bid_ask_spread'] = df['ask'] - df['bid']

            # Add symbol and clean up
            df['symbol'] = symbol
            df = df[['symbol', 'strike', 'option_type', 'bid', 'ask', 'last_price',
                     'delta', 'gamma', 'theta', 'vega', 'rho', 'implied_vol',
                     'historical_vol', 'volume', 'open_interest', 'bid_ask_spread']]

            # Filter out invalid data
            df = df.dropna(subset=['bid', 'ask', 'delta'])
            df = df[df['bid'] > 0]
            df = df[df['ask'] >= df['bid']]

            return df

        except Exception as e:
            logger.error(f"Error standardizing columns: {e}")
            return df

    def get_best_expiration(self, df: pd.DataFrame, min_dte: int = 7,
                          max_dte: int = 60) -> Optional[date]:
        """
        Get best expiration date from options chain

        Args:
            df: Options chain DataFrame
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration

        Returns:
            Best expiration date or None
        """
        if df.empty:
            return None

        # This assumes expirations are in the dataframe
        # Would need to add DTE calculation
        return None

    def filter_calls(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter to call options only"""
        return df[df['option_type'] == 'CALL']

    def filter_puts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter to put options only"""
        return df[df['option_type'] == 'PUT']

    def filter_itm(self, df: pd.DataFrame, stock_price: float) -> pd.DataFrame:
        """Filter to in-the-money options"""
        calls = df[df['option_type'] == 'CALL']
        puts = df[df['option_type'] == 'PUT']

        calls_itm = calls[calls['strike'] < stock_price]
        puts_itm = puts[puts['strike'] > stock_price]

        return pd.concat([calls_itm, puts_itm])

    def filter_otm(self, df: pd.DataFrame, stock_price: float) -> pd.DataFrame:
        """Filter to out-of-the-money options"""
        calls = df[df['option_type'] == 'CALL']
        puts = df[df['option_type'] == 'PUT']

        calls_otm = calls[calls['strike'] > stock_price]
        puts_otm = puts[puts['strike'] < stock_price]

        return pd.concat([calls_otm, puts_otm])

    def filter_by_delta(self, df: pd.DataFrame, min_delta: float,
                       max_delta: float) -> pd.DataFrame:
        """Filter options by delta range"""
        return df[(df['delta'] >= min_delta) & (df['delta'] <= max_delta)]

    def filter_by_liquidity(self, df: pd.DataFrame, min_volume: int = 10,
                           max_spread_pct: float = 5.0) -> pd.DataFrame:
        """Filter to liquid options"""
        df = df[df['volume'] >= min_volume]

        # Calculate spread percentage
        df['spread_pct'] = (df['bid_ask_spread'] / ((df['bid'] + df['ask']) / 2)) * 100

        return df[df['spread_pct'] <= max_spread_pct]

    def get_implied_volatility_percentile(self, df: pd.DataFrame,
                                         historical_iv: float) -> pd.DataFrame:
        """Add IV percentile calculation"""
        if df.empty:
            return df

        df['iv_vs_historical'] = df['implied_vol'] / historical_iv if historical_iv > 0 else 1

        return df

    def calculate_probability_itm(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add probability ITM based on delta"""
        df['prob_itm'] = df['delta'].abs()
        return df

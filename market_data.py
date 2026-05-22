"""
Market Data Handler
Fetches and processes OHLCV and fundamental data
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MarketDataHandler:
    """Fetch and process market data"""

    def __init__(self):
        """Initialize market data handler"""
        pass

    def fetch_ohlcv(self, symbol: str, period: str = "1d",
                   lookback_days: int = 252) -> pd.DataFrame:
        """
        Fetch OHLCV data

        Args:
            symbol: Stock ticker symbol
            period: Data period (1d, 1wk, 1mo)
            lookback_days: Number of days of historical data

        Returns:
            DataFrame with OHLCV data
        """
        try:
            import yfinance as yf

            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            df = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                interval=period,
                progress=False
            )

            if df.empty:
                logger.warning(f"No OHLCV data for {symbol}")
                return pd.DataFrame()

            # Standardize columns
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Adj Close': 'adj_close'
            })

            df['symbol'] = symbol
            df['date'] = df.index

            logger.info(f"Fetched {len(df)} candles for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_current_price(self, symbol: str) -> float:
        """
        Fetch current stock price

        Args:
            symbol: Stock ticker symbol

        Returns:
            Current price or 0 if not available
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            price = ticker.info.get('currentPrice', 0)

            return float(price) if price else 0

        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return 0

    def fetch_fundamentals(self, symbol: str) -> Dict:
        """
        Fetch fundamental data

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with fundamental data
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'dividend_yield': info.get('dividendYield', 0),
                'beta': info.get('beta', 1),
                '52_week_high': info.get('fiftyTwoWeekHigh', 0),
                '52_week_low': info.get('fiftyTwoWeekLow', 0),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'earnings_date': info.get('earningsDate', None)
            }

        except Exception as e:
            logger.error(f"Error fetching fundamentals for {symbol}: {e}")
            return {}

    def fetch_dividend_history(self, symbol: str,
                              years: int = 5) -> pd.DataFrame:
        """
        Fetch dividend history

        Args:
            symbol: Stock ticker symbol
            years: Number of years of history

        Returns:
            DataFrame with dividend data
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            dividends = ticker.dividends

            if dividends.empty:
                return pd.DataFrame()

            # Filter to recent years
            lookback = date.today() - timedelta(days=365 * years)
            dividends = dividends[dividends.index >= lookback]

            df = pd.DataFrame({
                'date': dividends.index,
                'dividend': dividends.values,
                'symbol': symbol
            })

            return df

        except Exception as e:
            logger.error(f"Error fetching dividend history for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_volatility(self, df: pd.DataFrame, window: int = 20) -> float:
        """
        Calculate historical volatility

        Args:
            df: DataFrame with price data
            window: Period for volatility calculation

        Returns:
            Annualized volatility
        """
        if df.empty or len(df) < window:
            return 0

        returns = df['close'].pct_change()
        volatility = returns.std() * np.sqrt(252)  # Annualize

        return float(volatility)

    def calculate_returns(self, df: pd.DataFrame, periods: List[int] = None) -> Dict:
        """
        Calculate returns for different periods

        Args:
            df: DataFrame with price data
            periods: List of periods (days)

        Returns:
            Dictionary with returns
        """
        if periods is None:
            periods = [1, 5, 20, 60]

        if df.empty:
            return {}

        returns = {}
        latest_price = df['close'].iloc[-1]

        for period in periods:
            if len(df) > period:
                past_price = df['close'].iloc[-period]
                ret = (latest_price - past_price) / past_price
                returns[f'{period}d'] = ret

        return returns

    def get_52_week_range(self, df: pd.DataFrame) -> Tuple[float, float]:
        """
        Get 52-week high and low

        Args:
            df: DataFrame with price data

        Returns:
            Tuple of (52w_high, 52w_low)
        """
        if df.empty or len(df) < 252:
            return (0, 0)

        high_52w = df['high'].tail(252).max()
        low_52w = df['low'].tail(252).min()

        return (high_52w, low_52w)

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Average True Range

        Args:
            df: DataFrame with OHLC data
            period: Period for ATR

        Returns:
            Current ATR value
        """
        if df.empty or len(df) < period:
            return 0

        df = df.copy()
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        atr = df['tr'].rolling(period).mean()

        return float(atr.iloc[-1]) if len(atr) > 0 else 0

    def identify_support_resistance(self, df: pd.DataFrame,
                                   lookback: int = 252) -> Tuple[List[float], List[float]]:
        """
        Identify support and resistance levels

        Args:
            df: DataFrame with price data
            lookback: Number of periods to look back

        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        if df.empty or len(df) < lookback:
            return ([], [])

        recent = df['close'].tail(lookback)

        # Simple approach: find local minima and maxima
        support_levels = []
        resistance_levels = []

        # This is simplified; in production, use more sophisticated methods
        min_val = recent.min()
        max_val = recent.max()

        if min_val > 0:
            support_levels = [min_val * 0.98, min_val]
        if max_val > 0:
            resistance_levels = [max_val, max_val * 1.02]

        return (support_levels, resistance_levels)

"""
Data Pipeline Orchestrator
Master data aggregation and processing for all analysis
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from massive_api import MassiveComAPI
from options_fetcher import OptionsFetcher
from market_data import MarketDataHandler
from data_cache import DataCache
from config import get_config
from validators import Validator

logger = logging.getLogger(__name__)


class DataPipeline:
    """Master data aggregation and processing"""

    def __init__(self, config=None):
        """
        Initialize data pipeline

        Args:
            config: Configuration object
        """
        self.config = config or get_config()

        # Initialize API clients and handlers
        api_key = self.config.get('api.massive_com.api_key')
        api_url = self.config.get('api.massive_com.base_url')
        api_timeout = self.config.get('api.massive_com.timeout', 30)
        max_retries = self.config.get('api.massive_com.max_retries', 3)

        self.massive_api = MassiveComAPI(
            api_key=api_key or "dummy_key",
            base_url=api_url,
            timeout=api_timeout,
            max_retries=max_retries
        )
        self.options_fetcher = OptionsFetcher()
        self.market_data = MarketDataHandler()

        # Initialize cache
        cache_ttl = self.config.get('data.cache_ttl', 3600)
        cache_enabled = self.config.get('data.cache_enabled', True)
        self.cache = DataCache(ttl_seconds=cache_ttl) if cache_enabled else None

        logger.info("Data pipeline initialized")

    def fetch_all_data(self, symbols: List[str], lookback: int = None) -> Dict[str, Dict]:
        """
        Fetch and aggregate all data for analysis

        Args:
            symbols: List of stock symbols
            lookback: Number of days of historical data

        Returns:
            Dictionary with aggregated data for each symbol
        """
        if lookback is None:
            lookback = self.config.get('data.lookback_days', 252)

        # Validate symbols
        symbols = [Validator.sanitize_symbol(s) for s in symbols]
        invalid = [s for s in symbols if not Validator.validate_symbol(s)]
        if invalid:
            logger.warning(f"Invalid symbols: {invalid}")
            symbols = [s for s in symbols if s not in invalid]

        logger.info(f"Fetching data for {len(symbols)} symbols (lookback: {lookback} days)")

        all_data = {}
        batch_size = self.config.get('data.batch_size', 100)

        # Process in batches
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            batch_data = self._fetch_batch(batch, lookback)
            all_data.update(batch_data)

        logger.info(f"Completed fetching data for {len(all_data)} symbols")
        return all_data

    def _fetch_batch(self, symbols: List[str], lookback: int) -> Dict[str, Dict]:
        """Fetch data for a batch of symbols in parallel"""
        batch_data = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_symbol = {
                executor.submit(self._fetch_symbol_data, symbol, lookback): symbol
                for symbol in symbols
            }

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    data = future.result()
                    if data:
                        batch_data[symbol] = data
                except Exception as e:
                    logger.error(f"Error fetching data for {symbol}: {e}")

        return batch_data

    def _fetch_symbol_data(self, symbol: str, lookback: int) -> Optional[Dict]:
        """Fetch all data for a single symbol"""
        try:
            # Check cache
            cache_key = f"symbol_data_{symbol}_{lookback}"
            if self.cache:
                cached = self.cache.get(cache_key)
                if cached:
                    logger.debug(f"Using cached data for {symbol}")
                    return cached

            logger.info(f"Fetching complete data for {symbol}")

            data = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'price': self.get_current_price(symbol),
                'technical': self.get_technical_data(symbol, lookback),
                'options': self.get_options_chain(symbol),
                'sentiment': self.get_news_sentiment(symbol),
                'catalysts': self.get_catalysts(symbol),
                'fundamentals': self.get_fundamentals(symbol),
                'volatility': self.get_volatility(symbol, lookback)
            }

            # Cache the result
            if self.cache:
                self.cache.set(cache_key, data)

            return data

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str) -> float:
        """Get current stock price"""
        try:
            return self.market_data.fetch_current_price(symbol)
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return 0

    def get_technical_data(self, symbol: str, lookback: int = 252) -> Optional[pd.DataFrame]:
        """Get OHLCV + technical indicators"""
        try:
            df = self.market_data.fetch_ohlcv(symbol, lookback_days=lookback)
            if df.empty:
                return None

            # Basic technical data returned; actual indicators come in Phase 2
            return {
                'ohlcv': df.to_dict('records') if not df.empty else [],
                'rows': len(df),
                'latest_close': float(df['close'].iloc[-1]) if len(df) > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error getting technical data for {symbol}: {e}")
            return None

    def get_options_chain(self, symbol: str) -> Optional[Dict]:
        """Get current options chain with Greeks"""
        try:
            df = self.options_fetcher.fetch_options_chain(symbol)
            if df.empty:
                return None

            return {
                'chains': df.to_dict('records') if not df.empty else [],
                'total_contracts': len(df),
                'calls': len(df[df['option_type'] == 'CALL']),
                'puts': len(df[df['option_type'] == 'PUT']),
                'data_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting options chain for {symbol}: {e}")
            return None

    def get_news_sentiment(self, symbol: str, days: int = 30) -> Dict:
        """Fetch news and sentiment analysis"""
        try:
            # Get news
            news = self.massive_api.get_news(symbol, days=days)

            # Get sentiment
            sentiment = self.massive_api.get_sentiment(symbol, days=days)

            return {
                'current_sentiment': sentiment.get('current_sentiment', 0),
                'sentiment_7d_ma': sentiment.get('sentiment_7d_ma', 0),
                'sentiment_30d_ma': sentiment.get('sentiment_30d_ma', 0),
                'sentiment_trend': sentiment.get('sentiment_trend', 'unknown'),
                'articles_count': len(news),
                'articles_sample': news[:5] if news else [],
                'data_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting sentiment for {symbol}: {e}")
            return {
                'current_sentiment': 0,
                'sentiment_7d_ma': 0,
                'sentiment_30d_ma': 0,
                'sentiment_trend': 'unknown',
                'articles_count': 0
            }

    def get_catalysts(self, symbol: str, days_ahead: int = 60) -> List[Dict]:
        """Identify major catalysts"""
        try:
            events = self.massive_api.get_events(symbol, days_ahead=days_ahead)
            return events if events else []
        except Exception as e:
            logger.error(f"Error getting catalysts for {symbol}: {e}")
            return []

    def get_fundamentals(self, symbol: str) -> Dict:
        """Get fundamental data"""
        try:
            return self.market_data.fetch_fundamentals(symbol)
        except Exception as e:
            logger.error(f"Error getting fundamentals for {symbol}: {e}")
            return {}

    def get_volatility(self, symbol: str, lookback: int = 252) -> Dict:
        """Get volatility analysis"""
        try:
            df = self.market_data.fetch_ohlcv(symbol, lookback_days=lookback)
            if df.empty:
                return {}

            historical_vol = self.market_data.calculate_volatility(df)
            returns = self.market_data.calculate_returns(df)

            return {
                'historical_volatility': float(historical_vol),
                'returns': returns,
                'atr': float(self.market_data.calculate_atr(df))
            }

        except Exception as e:
            logger.error(f"Error getting volatility for {symbol}: {e}")
            return {}

    def get_earnings_dates(self, symbols: List[str], days_ahead: int = 90) -> List[Dict]:
        """Get upcoming earnings dates"""
        try:
            return self.massive_api.get_earnings_calendar(symbols, days_ahead)
        except Exception as e:
            logger.error(f"Error getting earnings: {e}")
            return []

    def get_economic_calendar(self, days_ahead: int = 30) -> List[Dict]:
        """Get economic calendar events"""
        try:
            return self.massive_api.get_economic_calendar(days_ahead)
        except Exception as e:
            logger.error(f"Error getting economic calendar: {e}")
            return []

    def health_check(self) -> Dict[str, bool]:
        """Check health of all data sources"""
        health = {
            'massive_api': self.massive_api.health_check(),
            'cache': self.cache is not None,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"Health check: {health}")
        return health

    def clear_cache(self) -> bool:
        """Clear all cached data"""
        if self.cache:
            return self.cache.clear()
        return False

    def cache_stats(self) -> Dict:
        """Get cache statistics"""
        if self.cache:
            return self.cache.get_cache_stats()
        return {}

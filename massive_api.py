"""
Massive.com API Integration
Handles all API calls to massive.com for news, sentiment, and market data
"""

import requests
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom exception for API errors"""
    pass


class MassiveComAPI:
    """Wrapper for massive.com API calls"""

    def __init__(self, api_key: str, base_url: str = "https://api.massive.com",
                 timeout: int = 30, max_retries: int = 3, retry_delay: int = 2):
        """
        Initialize Massive.com API client

        Args:
            api_key: API key for authentication
            base_url: Base URL for API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make API request with retry logic

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data

        Returns:
            API response as dictionary

        Raises:
            APIError: If request fails after retries
        """
        url = f"{self.base_url}{endpoint}"
        attempt = 0

        while attempt < self.max_retries:
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=data,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    logger.warning(f"Rate limited. Waiting {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    attempt += 1
                elif response.status_code == 401:
                    raise APIError("Invalid API key")
                elif response.status_code >= 400:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    attempt += 1
                else:
                    return {}

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout. Retry {attempt + 1}/{self.max_retries}")
                attempt += 1
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Request error: {e}")
                attempt += 1
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        raise APIError(f"Failed to complete request after {self.max_retries} retries")

    def get_news(self, symbol: str, days: int = 30, limit: int = 50) -> List[Dict]:
        """
        Get news articles for a symbol

        Args:
            symbol: Stock ticker symbol
            days: Number of days to look back
            limit: Maximum number of articles

        Returns:
            List of news articles with metadata
        """
        try:
            response = self._request(
                "GET",
                f"/news/{symbol}",
                params={"days": days, "limit": limit}
            )
            return response.get("articles", [])
        except APIError as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []

    def get_sentiment(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """
        Get aggregated sentiment scores

        Args:
            symbol: Stock ticker symbol
            days: Number of days to look back

        Returns:
            Sentiment data with scores and trends
        """
        try:
            response = self._request(
                "GET",
                f"/sentiment/{symbol}",
                params={"days": days}
            )
            return {
                "current_sentiment": response.get("current_sentiment", 0),
                "sentiment_7d_ma": response.get("sentiment_7d_ma", 0),
                "sentiment_30d_ma": response.get("sentiment_30d_ma", 0),
                "sentiment_trend": response.get("sentiment_trend", "stable"),
                "sources": response.get("sources", {})
            }
        except APIError as e:
            logger.error(f"Error fetching sentiment for {symbol}: {e}")
            return {
                "current_sentiment": 0,
                "sentiment_7d_ma": 0,
                "sentiment_30d_ma": 0,
                "sentiment_trend": "unknown"
            }

    def get_events(self, symbol: str, days_ahead: int = 60) -> List[Dict]:
        """
        Get upcoming events and catalysts

        Args:
            symbol: Stock ticker symbol
            days_ahead: Number of days to look ahead

        Returns:
            List of upcoming events
        """
        try:
            response = self._request(
                "GET",
                f"/events/{symbol}",
                params={"days": days_ahead}
            )
            return response.get("events", [])
        except APIError as e:
            logger.error(f"Error fetching events for {symbol}: {e}")
            return []

    def get_market_data(self, symbol: str, lookback_days: int = 252) -> Dict[str, Any]:
        """
        Get market data for a symbol

        Args:
            symbol: Stock ticker symbol
            lookback_days: Days of historical data

        Returns:
            Market data including price and volume
        """
        try:
            response = self._request(
                "GET",
                f"/market-data/{symbol}",
                params={"lookback": lookback_days}
            )
            return response
        except APIError as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return {}

    def get_earnings_calendar(self, symbols: Optional[List[str]] = None,
                            days_ahead: int = 90) -> List[Dict]:
        """
        Get earnings dates for symbols

        Args:
            symbols: List of symbols (None for all)
            days_ahead: Days to look ahead

        Returns:
            List of earnings events
        """
        try:
            params = {"days": days_ahead}
            if symbols:
                params["symbols"] = ",".join(symbols)

            response = self._request(
                "GET",
                "/earnings-calendar",
                params=params
            )
            return response.get("earnings", [])
        except APIError as e:
            logger.error(f"Error fetching earnings calendar: {e}")
            return []

    def get_economic_calendar(self, days_ahead: int = 30) -> List[Dict]:
        """
        Get upcoming economic events

        Args:
            days_ahead: Days to look ahead

        Returns:
            List of economic events
        """
        try:
            response = self._request(
                "GET",
                "/economic-calendar",
                params={"days": days_ahead}
            )
            return response.get("events", [])
        except APIError as e:
            logger.error(f"Error fetching economic calendar: {e}")
            return []

    def get_analyst_ratings(self, symbol: str) -> Dict[str, Any]:
        """
        Get analyst ratings summary

        Args:
            symbol: Stock ticker symbol

        Returns:
            Analyst ratings data
        """
        try:
            response = self._request(
                "GET",
                f"/analyst-ratings/{symbol}"
            )
            return response
        except APIError as e:
            logger.error(f"Error fetching analyst ratings for {symbol}: {e}")
            return {}

    def health_check(self) -> bool:
        """Check if API is accessible"""
        try:
            self._request("GET", "/health")
            logger.info("API health check passed")
            return True
        except APIError:
            logger.error("API health check failed")
            return False

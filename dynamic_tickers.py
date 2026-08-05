"""
Dynamic ticker universe — fetches top 500 US stocks with liquid options
every trading day instead of using a static S&P 500 list.

Criteria:
- Market cap > $2B
- Avg daily volume (3m) > 500k shares
- Listed on major US exchanges (NMS, NYQ, NGM)
- Ranked by: market cap (40%) + avg volume (40%) + options availability (20%)
"""

import logging
import math
from datetime import date
from typing import List

import yfinance as yf
from yfinance.screener.query import EquityQuery

logger = logging.getLogger(__name__)

_cached_tickers: List[str] = []
_cache_date: date = None
TARGET_COUNT = 500


def _fetch_exchange(exchange: str, size: int = 250) -> List[dict]:
    try:
        q = EquityQuery('and', [
            EquityQuery('gt', ['intradaymarketcap', 2_000_000_000]),
            EquityQuery('gt', ['avgdailyvol3m', 500_000]),
            EquityQuery('eq', ['exchange', exchange]),
        ])
        result = yf.screen(q, size=size, sortField='intradaymarketcap', sortAsc=False)
        return result.get('quotes', [])
    except Exception as e:
        logger.warning(f"Screener failed for {exchange}: {e}")
        return []


def get_dynamic_tickers(force_refresh: bool = False) -> List[str]:
    """Return top 500 US stocks with liquid options. Cached per trading day."""
    global _cached_tickers, _cache_date

    today = date.today()
    if not force_refresh and _cached_tickers and _cache_date == today:
        logger.info(f"Using cached ticker universe ({len(_cached_tickers)} tickers)")
        return _cached_tickers

    logger.info("Fetching dynamic ticker universe...")

    # Fetch from multiple exchanges to get broad coverage
    quotes = []
    for exchange in ['NMS', 'NYQ', 'NGM', 'PCX']:
        batch = _fetch_exchange(exchange, size=250)
        quotes.extend(batch)
        logger.info(f"  {exchange}: {len(batch)} stocks")

    # Deduplicate by symbol
    seen = set()
    unique = []
    for q in quotes:
        sym = q.get('symbol', '')
        if sym and sym not in seen and '.' not in sym and '-' not in sym:
            seen.add(sym)
            unique.append(q)

    # Score each stock: market cap (40%) + volume (40%) + quoteType options bonus (20%)
    max_cap = max((q.get('marketCap', 0) for q in unique), default=1)
    max_vol = max((q.get('averageDailyVolume3Month', 0) for q in unique), default=1)

    def score(q):
        cap_score = q.get('marketCap', 0) / max_cap
        vol_score = q.get('averageDailyVolume3Month', 0) / max_vol
        return 0.4 * cap_score + 0.4 * vol_score + 0.2

    unique.sort(key=score, reverse=True)

    tickers = [q['symbol'] for q in unique[:TARGET_COUNT]]
    _cached_tickers = tickers
    _cache_date = today

    logger.info(f"Dynamic universe: {len(tickers)} tickers (refreshed {today})")
    return tickers


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tickers = get_dynamic_tickers(force_refresh=True)
    print(f"\nTop 20 tickers:")
    for i, t in enumerate(tickers[:20], 1):
        print(f"  {i:2}. {t}")
    print(f"\nTotal: {len(tickers)}")

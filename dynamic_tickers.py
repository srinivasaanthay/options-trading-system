"""
Dynamic ticker universe — fetches every liquid US stock meeting quality
filters, every trading day, instead of using a static S&P 500 list.

Criteria (all must hold — this is the actual gate, not TARGET_COUNT below):
- Market cap > $2B
- Share price > $5 (explicit penny-stock exclusion, on top of the market-cap floor)
- Avg daily volume (3m) > 500k shares
- Listed on major US exchanges (NMS, NYQ, NGM, PCX)
- Ranked by: market cap (40%) + avg volume (40%) + options availability (20%)
"""

import logging
import math
import re
from datetime import date
from typing import List

import yfinance as yf
from yfinance.screener.query import EquityQuery

logger = logging.getLogger(__name__)

_cached_tickers: List[str] = []
_cache_date: date = None
TARGET_COUNT = 3000  # safety ceiling only — the quality filters above are the
                      # real gate; ~1,650 tickers currently qualify, well under this


def _fetch_exchange(exchange: str, page_size: int = 250) -> List[dict]:
    """Yahoo caps a single screener call at 250 results, so page through
    `offset` to get everything that matches — not just the first page."""
    try:
        q = EquityQuery('and', [
            EquityQuery('gt', ['intradaymarketcap', 2_000_000_000]),
            EquityQuery('gt', ['avgdailyvol3m', 500_000]),
            EquityQuery('gt', ['intradayprice', 5]),
            EquityQuery('eq', ['exchange', exchange]),
        ])
        quotes: List[dict] = []
        offset = 0
        while True:
            result = yf.screen(q, offset=offset, size=page_size, sortField='intradaymarketcap', sortAsc=False)
            page = result.get('quotes', [])
            quotes.extend(page)
            total = result.get('total', len(quotes))
            offset += page_size
            if offset >= total or not page:
                break
        return quotes
    except Exception as e:
        logger.warning(f"Screener failed for {exchange}: {e}")
        return []


def get_dynamic_tickers(force_refresh: bool = False) -> List[str]:
    """Return every liquid US stock meeting the quality filters above (see
    module docstring), ranked and capped at TARGET_COUNT. Cached per trading day."""
    global _cached_tickers, _cache_date

    today = date.today()
    if not force_refresh and _cached_tickers and _cache_date == today:
        logger.info(f"Using cached ticker universe ({len(_cached_tickers)} tickers)")
        return _cached_tickers

    logger.info("Fetching dynamic ticker universe...")

    # Fetch from multiple exchanges to get broad coverage
    quotes = []
    for exchange in ['NMS', 'NYQ', 'NGM', 'PCX']:
        batch = _fetch_exchange(exchange)
        quotes.extend(batch)
        logger.info(f"  {exchange}: {len(batch)} stocks")

    # Deduplicate by symbol, and reject anything that isn't a real ticker
    # shape (1-5 uppercase letters). Belt-and-suspenders: the actual garbage
    # seen in production ("MCDANIEL", "NVDA " with a trailing space) came
    # from a separate iOS input bug, not this screener, but validating here
    # too means a bad row from Yahoo can never reach yfinance lookups either.
    _TICKER_RE = re.compile(r'^[A-Z]{1,5}$')
    seen = set()
    unique = []
    for q in quotes:
        sym = q.get('symbol', '')
        if sym and sym not in seen and _TICKER_RE.match(sym):
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

"""
Local SP500 scanner — runs full 500-ticker analysis every 19 minutes
and pushes results to Railway.

Usage:
    python local_runner.py
"""

import asyncio
import logging
import os
import time
from dataclasses import asdict
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

_ET = ZoneInfo("America/New_York")

load_dotenv()

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://arka.up.railway.app")
API_TOKEN   = os.getenv("API_SECRET_KEY", "arka-secret-2024")
INTERVAL    = 5 * 60   # 5 minutes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


def close_stale_on_railway():
    """Close positions left over from previous sessions before first scan."""
    url = f"{RAILWAY_URL}/api/v1/paper-trading/close-stale"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    try:
        resp = requests.post(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("closed", 0) > 0:
                logger.info(f"🧹 Closed {data['closed']} stale positions: {data['symbols']}")
        else:
            logger.warning(f"close-stale returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"close-stale failed: {e}")


def push_to_railway(recs: list):
    url = f"{RAILWAY_URL}/api/v1/sp500/push-results"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"recommendations": [asdict(r) if hasattr(r, '__dataclass_fields__') else r for r in recs]}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"✅ Pushed {data['received']} recs to Railway")
        else:
            logger.error(f"❌ Push failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.error(f"❌ Push error: {e}")


def execute_trades_on_railway():
    """Trigger paper trade execution after each scan."""
    url = f"{RAILWAY_URL}/api/v1/paper-trading/execute-now"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    try:
        resp = requests.post(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            trades = data.get("trades_executed", 0)
            if trades > 0:
                details = ", ".join(
                    f"{t.get('ticker','?')} {t.get('action','?')} ({t.get('score','?')})"
                    for t in data.get("trades", [])
                )
                logger.info(f"📈 Executed {trades} trade(s): {details}")
            else:
                logger.info("📊 No new trades this scan (positions full or no qualifying recs)")
        elif resp.status_code == 400 and "closed" in resp.text.lower():
            pass  # market closed, expected
        else:
            logger.warning(f"execute-now returned {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        logger.warning(f"execute-now failed: {e}")


def execute_stocks_on_railway():
    """Trigger stock trade execution after each scan."""
    url = f"{RAILWAY_URL}/api/v1/stock-trading/execute-now"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    try:
        resp = requests.post(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            trades = data.get("trades_executed", 0)
            dry = data.get("dry_run", False)
            if trades > 0:
                details = ", ".join(
                    f"{t.get('ticker','?')} ${t.get('entry_price','?')} ({t.get('signal_score','?')})"
                    for t in data.get("trades", [])
                )
                tag = "[DRY RUN] " if dry else ""
                logger.info(f"🏦 {tag}Stock trades {trades}: {details}")
        elif resp.status_code == 400 and "closed" in resp.text.lower():
            pass  # market closed, expected
        elif resp.status_code == 503:
            pass  # stock trader not yet initialised on Railway
        else:
            logger.warning(f"stock execute-now returned {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        logger.warning(f"stock execute-now failed: {e}")


async def run_once():
    from app import _analyze_sp500_options, news_analyzer, technical_analyzer
    from app import options_analyzer, market_analyzer, strategy_selector
    from app import call_put_predictor, reasoning_generator, stock_agent
    from analyzer.news_analyzer import NewsAnalyzer
    from analyzer.technical_analyzer import TechnicalAnalyzer
    from analyzer.options_analyzer import OptionsAnalyzer
    from analyzer.market_analyzer import MarketAnalyzer
    from analyzer.strategy_selector import StrategySelector
    from analyzer.call_put_predictor import CallPutPredictor
    from analyzer.reasoning_generator import ReasoningGenerator
    from mcp_stock_agent import MCPStockAgent
    import app as app_module

    # Initialize if not already done
    if app_module.news_analyzer is None:
        logger.info("Initializing analyzers...")
        app_module.news_analyzer      = NewsAnalyzer()
        app_module.technical_analyzer = TechnicalAnalyzer()
        app_module.options_analyzer   = OptionsAnalyzer()
        app_module.market_analyzer    = MarketAnalyzer()
        app_module.strategy_selector  = StrategySelector()
        app_module.call_put_predictor = CallPutPredictor()
        app_module.reasoning_generator = ReasoningGenerator()
        app_module.stock_agent        = MCPStockAgent()
        logger.info("✅ Analyzers ready")

    logger.info("Starting SP500 scan (500 tickers)...")
    start = time.time()
    recs = await _analyze_sp500_options()
    elapsed = time.time() - start
    logger.info(f"Scan complete: {len(recs)} recs in {elapsed:.0f}s")
    return recs


async def main():
    logger.info("=" * 50)
    logger.info("Local SP500 Runner started")
    logger.info(f"Pushing to: {RAILWAY_URL}")
    logger.info(f"Interval: {INTERVAL//60} minutes")
    logger.info("=" * 50)

    first_scan_done = False
    while True:
        now_et = datetime.now(_ET)
        market_open  = now_et.replace(hour=9,  minute=25, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=5,  second=0, microsecond=0)
        options_open = now_et.replace(hour=9,  minute=31, second=0, microsecond=0)
        is_weekday   = now_et.weekday() < 5

        if not is_weekday or now_et < market_open or now_et >= market_close:
            # Sleep until 9:25 AM ET next weekday
            next_open = now_et.replace(hour=9, minute=25, second=0, microsecond=0)
            if now_et >= market_close or not is_weekday:
                days_ahead = 1
                while (now_et.weekday() + days_ahead) % 7 >= 5:
                    days_ahead += 1
                from datetime import timedelta
                next_open = (now_et + timedelta(days=days_ahead)).replace(
                    hour=9, minute=25, second=0, microsecond=0)
            wait_secs = max(60, (next_open - now_et).total_seconds())
            logger.info(f"Market closed — sleeping {wait_secs/3600:.1f}h until {next_open.strftime('%a %I:%M %p ET')}")
            first_scan_done = False  # reset for next session
            await asyncio.sleep(min(wait_secs, 3600))  # wake hourly to recheck
            continue

        if not first_scan_done:
            if now_et >= options_open:
                logger.info("First scan of session — closing any stale positions first...")
                close_stale_on_railway()
                first_scan_done = True
            else:
                wait_secs = (options_open - now_et).total_seconds()
                logger.info(f"Waiting {wait_secs:.0f}s for options market open (9:31 AM)...")
                await asyncio.sleep(wait_secs)
                continue

        try:
            recs = await run_once()
            if recs:
                push_to_railway(recs)
                execute_trades_on_railway()
                execute_stocks_on_railway()
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)

        logger.info(f"Next scan in {INTERVAL//60} minutes...")
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())

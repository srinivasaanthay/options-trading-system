"""
Stock Options ML Agent - Main Entry Point
Runs the prediction engine for options trading
"""

import sys
import logging
from typing import List, Optional
from pathlib import Path
from datetime import datetime

from config import load_config, get_config
from logger import setup_logging, get_logger
from data_pipeline import DataPipeline
from sp500_tickers import get_sp500_manager, get_all_sp500_tickers
from validators import Validator

# Set up logging
setup_logging(log_dir="logs", log_file="stock_agent.log", level="INFO")
logger = get_logger(__name__)


class StockOptionsMLAgent:
    """Main agent class"""

    def __init__(self, config_file: str = "config.yaml"):
        """Initialize the agent"""
        self.config = load_config(config_file)
        self.data_pipeline = DataPipeline(self.config)
        logger.info("Stock Options ML Agent initialized")

    def run_analysis(self, symbols: List[str], lookback_days: Optional[int] = None):
        """
        Run complete analysis for given symbols

        Args:
            symbols: List of stock symbols to analyze (must be S&P 500 tickers)
            lookback_days: Number of days of historical data
        """
        # Validate and filter to S&P 500 only
        sp500_manager = get_sp500_manager()

        original_count = len(symbols)
        symbols = sp500_manager.filter_sp500(symbols)

        if len(symbols) < original_count:
            invalid_count = original_count - len(symbols)
            logger.warning(f"Filtered out {invalid_count} non-S&P 500 symbols")

        if not symbols:
            logger.error("No valid S&P 500 symbols provided")
            return {}

        logger.info(f"Starting analysis for {len(symbols)} S&P 500 symbols")

        try:
            # Check health
            health = self.data_pipeline.health_check()
            logger.info(f"Data pipeline health: {health}")

            # Fetch all data
            all_data = self.data_pipeline.fetch_all_data(
                symbols,
                lookback=lookback_days
            )

            logger.info(f"Analysis complete. Processed {len(all_data)} symbols")

            # In Phase 2, technical analysis will be added here
            # In Phase 3, ML predictions will be added
            # In Phase 4, strategy selection will be added
            # In Phase 5, output formatting will be added

            return all_data

        except Exception as e:
            logger.error(f"Error during analysis: {e}", exc_info=True)
            raise

    def run(self, symbols: List[str] = None, use_sample: bool = False, sample_size: int = 10):
        """
        Run the agent on S&P 500 symbols

        Args:
            symbols: Optional list of S&P 500 symbols to analyze
            use_sample: Use random sample of S&P 500 if no symbols provided
            sample_size: Size of random sample (default 10)
        """
        try:
            logger.info("=" * 60)
            logger.info("Stock Options ML Agent - S&P 500 Edition")
            logger.info(f"Time: {datetime.now().isoformat()}")
            logger.info("=" * 60)

            sp500_manager = get_sp500_manager()

            # Determine symbols to analyze
            if symbols is None:
                if use_sample:
                    symbols = sp500_manager.get_random_sample(sample_size)
                    logger.info(f"Using random sample of {len(symbols)} S&P 500 symbols")
                else:
                    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
                    logger.info(f"Using default S&P 500 symbols: {', '.join(symbols)}")

            logger.info(f"S&P 500 Manager: {len(sp500_manager)} total constituents")

            # Run analysis
            results = self.run_analysis(symbols)

            logger.info(f"Agent run complete. Results for {len(results)} symbols.")

            # Print summary (in production, would format and save)
            for symbol, data in results.items():
                logger.info(f"\n{symbol}:")
                logger.info(f"  Price: ${data.get('price', 0):.2f}")
                if data.get('sentiment'):
                    logger.info(f"  Sentiment: {data['sentiment'].get('current_sentiment', 0):.2f}")
                if data.get('technical'):
                    logger.info(f"  Technical data points: {data['technical'].get('rows', 0)}")
                if data.get('options'):
                    logger.info(f"  Options: {data['options'].get('total_contracts', 0)} contracts")

            return results

        except Exception as e:
            logger.error(f"Agent run failed: {e}", exc_info=True)
            return None

    def get_cache_stats(self):
        """Get cache statistics"""
        return self.data_pipeline.cache_stats()

    def clear_cache(self):
        """Clear cached data"""
        return self.data_pipeline.clear_cache()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Stock Options ML Agent - S&P 500 Edition (Options Trading Prediction Engine)"
    )
    parser.add_argument(
        "symbols",
        nargs="*",
        help="S&P 500 symbols to analyze (e.g., AAPL MSFT GOOGL) - defaults to sample if not provided"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Configuration file path"
    )
    parser.add_argument(
        "--lookback",
        type=int,
        help="Number of days of historical data"
    )
    parser.add_argument(
        "--sample",
        type=int,
        metavar="N",
        help="Use random sample of N S&P 500 symbols"
    )
    parser.add_argument(
        "--list-sp500",
        action="store_true",
        help="List all S&P 500 tickers"
    )
    parser.add_argument(
        "--count-sp500",
        action="store_true",
        help="Show total count of S&P 500 symbols"
    )
    parser.add_argument(
        "--validate",
        nargs="+",
        help="Validate if symbols are in S&P 500"
    )
    parser.add_argument(
        "--cache-stats",
        action="store_true",
        help="Show cache statistics"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cached data"
    )

    args = parser.parse_args()

    try:
        # Handle S&P 500 info commands
        if args.list_sp500:
            sp500_manager = get_sp500_manager()
            tickers = sp500_manager.get_all_tickers()
            print(f"\nS&P 500 Tickers ({len(tickers)} total):")
            for i, ticker in enumerate(tickers, 1):
                print(f"  {ticker}", end="")
                if i % 10 == 0:
                    print()
                else:
                    print("  ", end="")
            print("\n")
            return 0

        if args.count_sp500:
            sp500_manager = get_sp500_manager()
            count = sp500_manager.get_ticker_count()
            print(f"\nTotal S&P 500 constituents: {count}\n")
            return 0

        if args.validate:
            sp500_manager = get_sp500_manager()
            results = sp500_manager.validate_tickers(args.validate)
            print("\nS&P 500 Validation Results:")
            for symbol, is_valid in results.items():
                status = "✓ Valid" if is_valid else "✗ Not in S&P 500"
                print(f"  {symbol}: {status}")
            print()
            return 0

        # Initialize agent
        agent = StockOptionsMLAgent(config_file=args.config)

        # Handle cache operations
        if args.cache_stats:
            stats = agent.get_cache_stats()
            print("\nCache Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
            return 0

        if args.clear_cache:
            if agent.clear_cache():
                print("Cache cleared successfully")
            else:
                print("Failed to clear cache")
            return 0

        # Run analysis
        if args.sample:
            print(f"\nAnalyzing random sample of {args.sample} S&P 500 symbols...")
            results = agent.run(use_sample=True, sample_size=args.sample)
        elif args.symbols:
            print(f"\nAnalyzing {len(args.symbols)} S&P 500 symbols...")
            results = agent.run(args.symbols)
        else:
            print("\nAnalyzing default S&P 500 symbols (AAPL, MSFT, GOOGL, AMZN, TSLA)...")
            results = agent.run()

        if results:
            print(f"\n✓ Analysis complete for {len(results)} symbols")
            return 0
        else:
            print("\n✗ Analysis failed")
            return 1

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

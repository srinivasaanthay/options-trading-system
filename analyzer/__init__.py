"""
Options Trading Analysis Engine

Comprehensive analyzer package for sentiment, technical, options, market,
strategy, and machine learning analysis of S&P 500 stocks.

Modules:
- news_analyzer: Sentiment analysis from news data
- technical_analyzer: Technical indicators and price patterns
- options_analyzer: Greeks, IV, liquidity analysis
- market_analyzer: Market trends and volatility
- strategy_selector: Options strategy selection
- call_put_predictor: ML-based CALL vs PUT prediction
- reasoning_generator: Human-readable explanations
"""

# Lazy imports - only load modules as they're imported
try:
    from .news_analyzer import NewsAnalyzer
except ImportError:
    pass

try:
    from .technical_analyzer import TechnicalAnalyzer
except ImportError:
    pass

try:
    from .options_analyzer import OptionsAnalyzer
except ImportError:
    pass

try:
    from .market_analyzer import MarketAnalyzer
except ImportError:
    pass

try:
    from .strategy_selector import StrategySelector
except ImportError:
    pass

try:
    from .call_put_predictor import CallPutPredictor
except ImportError:
    pass

try:
    from .reasoning_generator import ReasoningGenerator
except ImportError:
    pass

__all__ = [
    'NewsAnalyzer',
    'TechnicalAnalyzer',
    'OptionsAnalyzer',
    'MarketAnalyzer',
    'StrategySelector',
    'CallPutPredictor',
    'ReasoningGenerator'
]

__version__ = '0.1.0'

#!/bin/bash

echo "======================================"
echo "Options Trading System - Local Setup"
echo "======================================"
echo ""

# Check Python version
echo "✓ Checking Python version..."
python --version

# Create virtual environment
echo "✓ Creating virtual environment..."
python -m venv venv
source venv/bin/activate

# Install minimal requirements for testing
echo "✓ Installing minimal requirements..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1

# Test analyzer imports
echo "✓ Testing analyzer imports..."
python << 'PYEOF'
from analyzer.news_analyzer import NewsAnalyzer
from analyzer.technical_analyzer import TechnicalAnalyzer
from analyzer.options_analyzer import OptionsAnalyzer
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.strategy_selector import StrategySelector
from analyzer.call_put_predictor import CallPutPredictor
from analyzer.reasoning_generator import ReasoningGenerator

print("✓ All analyzers imported successfully")

# Test initialization
analyzers = {
    'NewsAnalyzer': NewsAnalyzer(),
    'TechnicalAnalyzer': TechnicalAnalyzer(),
    'OptionsAnalyzer': OptionsAnalyzer(),
    'MarketAnalyzer': MarketAnalyzer(),
    'StrategySelector': StrategySelector(),
    'CallPutPredictor': CallPutPredictor(),
    'ReasoningGenerator': ReasoningGenerator()
}

print("\n✓ All analyzers initialized successfully:")
for name, analyzer in analyzers.items():
    print(f"  - {name}: Ready")

PYEOF

echo ""
echo "======================================"
echo "✓ Local setup complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Activate venv: source venv/bin/activate"
echo "2. Run tests: python -m unittest discover -s analyzer -p 'test_*.py' -v"
echo "3. Run FastAPI: pip install fastapi uvicorn && python app.py"

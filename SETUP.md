# Stock Options ML Agent - Setup Guide

Complete setup instructions for the Stock Options ML Agent (Phase 1 - Foundation)

## Prerequisites

- Python 3.9 or higher
- pip package manager
- Git (for version control)
- Massive.com API key (for news/sentiment data)
- Optional: Polygon.io API key (higher quality options data)

## Step 1: Clone or Download the Project

```bash
# If using git
git clone <repository_url>
cd stock-options-ml-agent

# Or download and extract the ZIP file
unzip stock-options-ml-agent.zip
cd stock-options-ml-agent
```

## Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Verify activation (you should see (venv) in your prompt)
which python  # macOS/Linux
where python  # Windows
```

## Step 3: Install Dependencies

```bash
# Upgrade pip, setuptools, and wheel
pip install --upgrade pip setuptools wheel

# Install all dependencies
pip install -r requirements.txt

# Optional: Install development dependencies for testing
pip install -e ".[dev]"
```

## Step 4: Configure Environment Variables

### Option A: Using .env File

```bash
# Create .env file
cp .env.example .env  # or create manually

# Edit .env and add your API keys:
```

**.env file contents:**
```
MASSIVE_COM_API_KEY=your_api_key_here
POLYGON_API_KEY=your_polygon_api_key_here
```

### Option B: Using Environment Variables Directly

```bash
# macOS/Linux
export MASSIVE_COM_API_KEY="your_api_key_here"
export POLYGON_API_KEY="your_polygon_api_key_here"

# Windows (CMD)
set MASSIVE_COM_API_KEY=your_api_key_here
set POLYGON_API_KEY=your_polygon_api_key_here

# Windows (PowerShell)
$env:MASSIVE_COM_API_KEY="your_api_key_here"
$env:POLYGON_API_KEY="your_polygon_api_key_here"
```

## Step 5: Configure the Application

```bash
# Copy the default config
cp config.yaml config.local.yaml

# Edit config.local.yaml to customize settings:
# - API timeouts
# - Data lookback periods
# - Technical indicator periods
# - ML model parameters
# - Risk management settings
# - Strategy parameters
```

## Step 6: Create Required Directories

```bash
# The application will create these automatically, but you can pre-create them:
mkdir -p logs
mkdir -p data/raw
mkdir -p data/processed
mkdir -p data/cache
mkdir -p models
mkdir -p outputs
```

## Step 7: Verify Installation

```bash
# Check Python version
python --version  # Should be 3.9 or higher

# Check if packages are installed
python -c "import pandas, numpy, yfinance; print('All packages installed!')"

# Run basic health check
python main.py --cache-stats
```

## Step 8: Run First Analysis

```bash
# Test with default symbols
python main.py

# Or specify your own symbols
python main.py AAPL MSFT TSLA GOOGL

# See cache stats
python main.py --cache-stats
```

## Step 9: Run Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run specific test file
pytest test_validators.py -v

# Run specific test function
pytest test_config.py::test_config_load -v
```

## Configuration File Walkthrough

Key sections in `config.yaml`:

### API Configuration
```yaml
api:
  massive_com:
    api_key: ${MASSIVE_COM_API_KEY}  # Set via environment variable
    base_url: "https://api.massive.com"
    timeout: 30  # Request timeout in seconds
    max_retries: 3
```

### Data Configuration
```yaml
data:
  lookback_days: 252  # 1 year of historical data
  refresh_interval: 3600  # Cache TTL in seconds
  cache_enabled: true
  batch_size: 100  # Process 100 symbols per batch
```

### Technical Analysis
```yaml
technical:
  indicators:
    sma_periods: [20, 50, 200]  # Simple moving averages
    rsi_period: 14  # RSI (relative strength index)
    bollinger_period: 20  # Bollinger bands
```

### Risk Management
```yaml
risk:
  max_loss_per_trade: 0.02  # Never risk more than 2% per trade
  position_size_method: "kelly"  # Use Kelly Criterion for sizing
  kelly_fraction: 0.25  # Use 25% of Kelly recommendation
```

## Logging

Logs are stored in the `logs/` directory:

```bash
# View latest logs
tail -f logs/stock_agent.log

# Search logs for specific symbol
grep "AAPL" logs/stock_agent.log

# Filter by log level
grep "ERROR" logs/stock_agent.log
```

## Troubleshooting

### Import Errors
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate  # Windows

# Reinstall packages
pip install -r requirements.txt --force-reinstall
```

### API Key Issues
```bash
# Test if API key is set
python -c "import os; print(os.getenv('MASSIVE_COM_API_KEY'))"

# If empty, check .env file or set manually
export MASSIVE_COM_API_KEY="your_key_here"
```

### Data Fetch Errors
```bash
# Check API health
python main.py --health-check

# Clear cache and retry
python main.py --clear-cache
python main.py AAPL
```

### Permission Errors
```bash
# Make sure you have write permissions
chmod u+w logs/
chmod u+w data/

# Or run with appropriate user
sudo python main.py
```

## Next Steps

1. **Phase 2**: Technical Analysis Implementation
   - Implement 15+ technical indicators
   - Add signal generation
   - Create visualization

2. **Phase 3**: ML Models
   - Build XGBoost directional predictor
   - Create neural network for profitability
   - Train volatility models

3. **Phase 4**: Strategy Engine
   - Implement 8 trading strategies
   - Add Greeks calculations
   - Build risk management

4. **Phase 5**: Output & Reporting
   - Standardized prediction formatting
   - Email notifications
   - Dashboard visualization

## Development Tips

### Using in Interactive Python
```python
from main import StockOptionsMLAgent

# Initialize agent
agent = StockOptionsMLAgent()

# Run analysis
results = agent.run(["AAPL", "MSFT"])

# Access data
for symbol, data in results.items():
    print(f"{symbol}: ${data['price']:.2f}")
```

### Adding Custom Symbols
```python
agent = StockOptionsMLAgent()
symbols = ["NVDA", "AMD", "SOXX"]  # Tech stocks
results = agent.run(symbols)
```

### Cache Management
```python
from data_cache import DataCache

cache = DataCache(cache_dir="data/cache", ttl_seconds=3600)
cache.clear()  # Clear all cache
stats = cache.get_cache_stats()  # Get stats
```

## Performance Considerations

- **Lookback period**: Longer = more accurate but slower. Default is 252 days (1 year)
- **Batch size**: Larger batches are faster but use more memory. Default is 100 symbols
- **Cache TTL**: Lower values = fresher data but more API calls
- **Max workers**: More threads = faster but higher CPU usage

## Updating Code

```bash
# Pull latest changes (if using git)
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Run tests to verify everything works
pytest
```

## Getting Help

- Check logs in `logs/stock_agent.log`
- Review README.md for usage examples
- Check test files for usage patterns
- Consult config.yaml comments for parameter meanings

## Useful Commands

```bash
# List installed packages
pip list

# Show package details
pip show pandas

# Update all packages
pip install --upgrade -r requirements.txt

# Remove virtual environment (if needed)
rm -rf venv  # macOS/Linux
rmdir /s venv  # Windows

# Check code quality
flake8 *.py

# Format code
black *.py

# Type checking
mypy main.py
```

---

**Installation Complete!** 🎉

Your Stock Options ML Agent is ready to use. Start with:

```bash
python main.py AAPL MSFT GOOGL
```

For next steps, see README.md for usage documentation.

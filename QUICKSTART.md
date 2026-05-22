# Stock Options ML Agent - Quick Start (5 minutes)

## 1. Install (1 minute)

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## 2. Configure (1 minute)

```bash
# Set your API key (required)
export MASSIVE_COM_API_KEY="your_api_key_here"

# On Windows:
# set MASSIVE_COM_API_KEY=your_api_key_here
```

## 3. Run (1 minute)

```bash
# Analyze default stocks
python main.py

# Or your own stocks
python main.py AAPL MSFT TSLA NVDA
```

## 4. Check Results

Look at `logs/stock_agent.log` for detailed output:
```
Price: $189.45
Sentiment: 0.42
Options: 150 contracts
Technical data points: 252
```

## 5. Run Tests (1 minute)

```bash
pytest
```

---

## What's Happening?

```
Input (Symbols)
    ↓
Data Pipeline fetches:
  - Current prices
  - News & sentiment
  - Options chains
  - Technical data
  ↓
Results displayed
```

## Common Commands

```bash
# See cache stats
python main.py --cache-stats

# Clear cached data
python main.py --clear-cache

# Analyze specific symbols with custom lookback
python main.py AAPL --lookback 365

# Run tests with coverage
pytest --cov=.
```

## File Structure

```
├── main.py              ← Entry point
├── config.yaml          ← Configuration
├── requirements.txt     ← Dependencies
├── data/
│   └── cache/          ← Cached data
├── logs/
│   └── *.log           ← Application logs
└── tests/              ← Unit tests
```

## Troubleshooting

**"No module named pandas"**
```bash
pip install -r requirements.txt
```

**"Invalid API key"**
```bash
# Check your key is set
echo $MASSIVE_COM_API_KEY  # macOS/Linux
echo %MASSIVE_COM_API_KEY%  # Windows
```

**Tests fail**
```bash
# Make sure you're in virtual environment
source venv/bin/activate
pytest
```

## Next Steps

1. Read **README.md** for full documentation
2. Check **SETUP.md** for detailed installation
3. See **PHASE1_SUMMARY.md** for architecture overview
4. Review **config.yaml** for all configuration options

## Code Examples

### Programmatic Use

```python
from main import StockOptionsMLAgent

# Create agent
agent = StockOptionsMLAgent("config.yaml")

# Run analysis
results = agent.run(["AAPL", "MSFT", "GOOGL"])

# Access data
for symbol, data in results.items():
    price = data['price']
    sentiment = data['sentiment']['current_sentiment']
    print(f"{symbol}: ${price:.2f}, Sentiment: {sentiment:.2f}")
```

### Cache Management

```python
from data_cache import DataCache

cache = DataCache()

# Get value
value = cache.get("key")

# Set value
cache.set("key", {"data": "value"})

# Clear all
cache.clear()

# Stats
stats = cache.get_cache_stats()
```

## Performance

- 📊 Fetches 100+ symbols in < 5 minutes
- ⚡ Cached data retrieved in < 100ms
- 🔄 Automatic retry on API failures
- 💾 Smart caching with TTL (1 hour default)

## Key Features (Phase 1)

✅ Multi-source data integration  
✅ Parallel data fetching  
✅ Intelligent caching  
✅ Configuration management  
✅ Comprehensive logging  
✅ Input validation  
✅ Unit tests  
✅ Complete documentation

## Upcoming (Phase 2-7)

📈 Technical Analysis Indicators  
🤖 ML Models (XGBoost, Neural Networks)  
💹 Strategy Engine (8 strategies)  
📊 Risk Management & Greeks  
📉 Backtesting Framework  
📧 Output & Reporting  
🚀 Deployment Setup

---

**You're ready to go!** 🚀

```bash
python main.py AAPL
```

For help: See README.md or SETUP.md

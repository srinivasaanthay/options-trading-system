# S&P 500 Edition - Quick Start (3 minutes)

**Stock Options ML Agent - Exclusive S&P 500 Analysis**

---

## Setup (2 minutes)

```bash
# Create environment
python -m venv venv
source venv/bin/activate  # macOS/Linux: venv\Scripts\activate  Windows

# Install
pip install -r requirements.txt

# Set API key
export MASSIVE_COM_API_KEY="your_key"
```

---

## Run (1 minute)

### Default: Top 5 S&P 500 Stocks

```bash
# AAPL, MSFT, GOOGL, AMZN, TSLA
python main.py
```

### Custom S&P 500 Stocks

```bash
# Your choice of S&P 500 tickers
python main.py NVDA AMD INTEL COSTCO WALMART

# With extended lookback
python main.py AAPL MSFT --lookback 365
```

### Random Sample

```bash
# Random 10 from 500
python main.py --sample 10

# Random 25 from 500
python main.py --sample 25
```

### S&P 500 Info

```bash
# List all 500 tickers
python main.py --list-sp500

# Validate symbols
python main.py --validate AAPL FAKE_TICKER MSFT
```

---

## What You Get

```
✓ Current prices
✓ News sentiment (-1.0 to 1.0)
✓ Options chain data
✓ Technical indicators
✓ 500 S&P 500 constituents to choose from
✓ Automatic validation (invalid symbols filtered)
```

---

## Examples

### Python API

```python
from main import StockOptionsMLAgent

agent = StockOptionsMLAgent()

# Analyze top tech stocks
results = agent.run(["AAPL", "MSFT", "NVDA", "GOOGL"])

for symbol, data in results.items():
    price = data['price']
    sentiment = data['sentiment']['current_sentiment']
    print(f"{symbol}: ${price:.2f}, Sentiment: {sentiment:.2f}")
```

### Check S&P 500 Status

```python
from sp500_tickers import get_sp500_manager

manager = get_sp500_manager()

# Total constituents
print(f"S&P 500: {len(manager)} stocks")

# Validate symbol
print(f"AAPL valid: {manager.is_sp500_ticker('AAPL')}")
print(f"FAKE valid: {manager.is_sp500_ticker('FAKE')}")

# Filter symbols
symbols = ["AAPL", "INVALID", "MSFT"]
valid = manager.filter_sp500(symbols)
print(f"Valid: {valid}")  # ['AAPL', 'MSFT']

# Random sample
sample = manager.get_random_sample(10)
print(f"10 random: {sample}")
```

---

## Available Commands

```bash
# Analyze
python main.py SYMBOL1 SYMBOL2
python main.py --sample 10

# Info
python main.py --list-sp500          # All 500 tickers
python main.py --count-sp500         # Count constituents
python main.py --validate SYM1 SYM2  # Check S&P 500 membership

# Cache
python main.py --cache-stats         # Show cache size
python main.py --clear-cache         # Clear all data
```

---

## Key S&P 500 Stocks by Sector

**Tech** (10 stocks)
```
AAPL, MSFT, NVDA, GOOGL, META, TSLA, QCOM, INTC, AMD, AMAT
```

**Finance** (5 stocks)
```
JPM, BAC, GS, MS, AXP
```

**Healthcare** (5 stocks)
```
JNJ, UNH, MRK, ABBV, VRTX
```

**Consumer** (4 stocks)
```
WMT, HD, COST, MCD
```

---

## Pro Tips

✅ **Start small**: `python main.py AAPL`  
✅ **Test validation**: `python main.py --validate YOUR_SYMBOLS`  
✅ **Use samples**: `python main.py --sample 20` for comprehensive analysis  
✅ **Check cache**: `python main.py --cache-stats` to monitor data  
✅ **Clear if needed**: `python main.py --clear-cache` then retry

---

## Troubleshooting

**"Symbol not in S&P 500"?**
```bash
# Validate your symbols first
python main.py --validate SYMBOL1 SYMBOL2

# Only valid S&P 500 stocks work
python main.py AAPL MSFT GOOGL  # ✓ Works
python main.py MY_COMPANY      # ✗ Not in S&P 500
```

**Import error?**
```bash
# Make sure virtual env is activated
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

**No data returned?**
```bash
# Clear cache and retry
python main.py --clear-cache
python main.py AAPL
```

---

## Next Steps

1. ✓ Run: `python main.py AAPL MSFT GOOGL`
2. ✓ Check logs: `tail -f logs/stock_agent.log`
3. ✓ Read: `SP500_GUIDE.md` for complete documentation
4. ✓ Test: `pytest test_sp500.py`

---

**You're ready! Start analyzing S&P 500 stocks now!** 🚀

```bash
python main.py AAPL MSFT NVDA GOOGL AMZN
```

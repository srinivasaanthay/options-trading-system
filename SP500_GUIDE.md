# Stock Options ML Agent - S&P 500 Implementation Guide

**Focus**: S&P 500 constituents only (500 largest US companies)

---

## Overview

The Stock Options ML Agent is now exclusively focused on analyzing options trading strategies for the 500 largest US companies in the S&P 500 index. All analysis, validation, and predictions are scoped to these constituents.

---

## Key Features

### 1. S&P 500 Ticker Management

**Module**: `sp500_tickers.py`

The system includes a comprehensive S&P 500 ticker list with built-in validation:

- Complete list of 500 S&P 500 constituents
- Automatic caching with 7-day TTL
- Fast validation and filtering
- Sector-based grouping

### 2. Automatic Validation

All input symbols are automatically validated against the S&P 500 list:

```bash
# Analyze only valid S&P 500 stocks
python main.py AAPL MSFT INVALID_TICKER
# Result: Invalid ticker filtered out, only AAPL and MSFT analyzed
```

### 3. Default Symbols

When no symbols are provided, the agent uses these top S&P 500 constituents:

```
AAPL, MSFT, GOOGL, AMZN, TSLA
```

---

## Usage Examples

### Command Line Interface

#### Analyze Specific S&P 500 Stocks

```bash
# Single stock
python main.py AAPL

# Multiple stocks
python main.py AAPL MSFT GOOGL AMZN TSLA

# Multiple stocks with custom lookback
python main.py NVDA AMD INTEL --lookback 365
```

#### Use Random Sample

```bash
# Random sample of 10 stocks
python main.py --sample 10

# Random sample of 25 stocks
python main.py --sample 25

# Random sample of 50 stocks
python main.py --sample 50
```

#### View S&P 500 Information

```bash
# List all 500 tickers
python main.py --list-sp500

# Count total constituents
python main.py --count-sp500

# Validate specific symbols
python main.py --validate AAPL MSFT INVALID GOOGL
```

#### Cache Management

```bash
# Show cache statistics
python main.py --cache-stats

# Clear all cached data
python main.py --clear-cache
```

### Python API

#### Basic Usage

```python
from main import StockOptionsMLAgent

# Initialize agent
agent = StockOptionsMLAgent()

# Analyze specific S&P 500 stocks
results = agent.run(["AAPL", "MSFT", "GOOGL"])

# Results contain price, sentiment, technical data, options chain
for symbol, data in results.items():
    print(f"{symbol}:")
    print(f"  Price: ${data['price']:.2f}")
    print(f"  Sentiment: {data['sentiment']['current_sentiment']:.2f}")
    print(f"  Options contracts: {data['options']['total_contracts']}")
```

#### Use Random Sample

```python
from main import StockOptionsMLAgent

agent = StockOptionsMLAgent()

# Analyze 20 random S&P 500 stocks
results = agent.run(use_sample=True, sample_size=20)
```

#### Check S&P 500 Status

```python
from sp500_tickers import get_sp500_manager

manager = get_sp500_manager()

# Get all tickers
all_tickers = manager.get_all_tickers()
print(f"Total S&P 500 constituents: {len(all_tickers)}")

# Validate a symbol
is_valid = manager.is_sp500_ticker("AAPL")
print(f"AAPL is S&P 500: {is_valid}")

# Filter symbols
symbols = ["AAPL", "INVALID", "MSFT", "FAKE"]
filtered = manager.filter_sp500(symbols)
print(f"Valid S&P 500: {filtered}")  # ['AAPL', 'MSFT']

# Get sector tickers
tech = manager.get_sector_tickers("TECH")
finance = manager.get_sector_tickers("FINANCE")
```

---

## S&P 500 Constituents List

### Top 50 by Inclusion (as of May 2024)

#### Technology (16 stocks)
AAPL, MSFT, NVDA, GOOGL, GOOG, META, TSLA, QCOM, INTC, AMD, AMAT, CDNS, SNPS, LRCX, AVGO, ASML

#### Financials (10 stocks)
JPM, BAC, WFC, GS, MS, AXP, BLK, USB, PNC, CI

#### Healthcare (10 stocks)
JNJ, UNH, MRK, ABBV, VRTX, BMY, AMGN, REGN, BIIB, LLY

#### Consumer (8 stocks)
WMT, HD, COST, TJX, MCD, SBUX, NKE, CMG

#### Industrials (6 stocks)
CAT, BA, HON, GE, MMM, ETN

#### Energy (5 stocks)
XOM, CVX, COP, OKE, EOG

### Complete List

Use `python main.py --list-sp500` to see the complete list of 500 constituents.

---

## Data Flow for S&P 500 Analysis

```
User Input (S&P 500 Symbols)
        ↓
Validation (Against S&P 500 list)
        ↓
Filtering (Remove invalid tickers)
        ↓
Data Pipeline
  ├─ Massive.com API (news, sentiment)
  ├─ Market Data (prices, OHLCV, fundamentals)
  ├─ Options Chain (Greeks, IV, volume)
  └─ Caching (1-hour TTL)
        ↓
Results (price, sentiment, options, technical data)
```

---

## Configuration

### S&P 500 Specific Settings

In `config.yaml`:

```yaml
# S&P 500 Configuration
sp500:
  enabled: true                    # Use S&P 500 validation
  validate_input: true             # Validate all input symbols
  auto_filter: true                # Automatically filter invalid symbols
  default_symbols:                 # Default if none provided
    - AAPL
    - MSFT
    - GOOGL
    - AMZN
    - TSLA
  sample_size: 10                  # Size for random samples
  cache_tickers: true              # Cache ticker list
  cache_ttl: 604800                # 7 days in seconds
```

---

## Input Validation

### How Validation Works

1. **Symbol is provided** → Checked against S&P 500 list
2. **Invalid symbol** → Logged as warning, filtered out
3. **All symbols invalid** → Analysis aborted with error
4. **Mix of valid/invalid** → Only valid symbols analyzed

### Examples

```python
from validators import Validator

# Check single symbol
is_valid = Validator.validate_sp500_symbol("AAPL")      # True
is_valid = Validator.validate_sp500_symbol("INVALID")   # False

# Check multiple symbols
all_valid = Validator.validate_sp500_symbols(["AAPL", "MSFT"])  # True
all_valid = Validator.validate_sp500_symbols(["AAPL", "INVALID"]) # False

# Filter to S&P 500 only
symbols = ["AAPL", "INVALID", "MSFT", "FAKE"]
filtered = Validator.filter_sp500_only(symbols)
# Result: ['AAPL', 'MSFT']
```

---

## Testing

### Run S&P 500 Tests

```bash
# All S&P 500 tests
pytest test_sp500.py -v

# Specific test
pytest test_sp500.py::TestSP500Manager::test_is_sp500_ticker -v

# With coverage
pytest test_sp500.py --cov=sp500_tickers
```

### Test Coverage

- ✅ Ticker validation
- ✅ Symbol filtering
- ✅ Random sampling
- ✅ Sector grouping
- ✅ Caching
- ✅ API integration

---

## Performance

### Analysis Speed (Estimated)

| Symbols | Time | Notes |
|---------|------|-------|
| 5 | < 1 min | Top constituents |
| 10 | 1-2 min | Small sample |
| 25 | 3-5 min | Medium sample |
| 50 | 5-10 min | Large sample |
| 100+ | 10-20 min | Very comprehensive |

### Memory Usage

- **Ticker list**: < 1 MB
- **Cache per symbol**: 500 KB - 2 MB
- **Total for 50 symbols**: 25-100 MB (with cache)

### Network Optimization

- Parallel fetching (4 workers)
- Intelligent caching (1-hour TTL)
- Batch API calls
- Connection pooling

---

## Sector Analysis

### Available Sectors

```python
from sp500_tickers import get_sp500_manager

manager = get_sp500_manager()

# Tech stocks
tech = manager.get_sector_tickers("TECH")

# Finance stocks
finance = manager.get_sector_tickers("FINANCE")

# Healthcare stocks
healthcare = manager.get_sector_tickers("HEALTHCARE")

# Consumer stocks
consumer = manager.get_sector_tickers("CONSUMER")

# Industrial stocks
industrial = manager.get_sector_tickers("INDUSTRIAL")

# Energy stocks
energy = manager.get_sector_tickers("ENERGY")

# Utilities stocks
utilities = manager.get_sector_tickers("UTILITIES")
```

---

## Error Handling

### Common Issues and Solutions

#### Invalid Symbol
```
Error: INVALID is not in S&P 500
Solution: Use valid S&P 500 ticker (python main.py --validate TICKER)
```

#### No Valid Symbols
```
Error: No valid S&P 500 symbols provided
Solution: Provide at least one valid S&P 500 ticker
```

#### API Failures
```
Error: Failed to fetch data
Solution: Check logs, clear cache (python main.py --clear-cache), retry
```

---

## Logging

S&P 500 specific log messages are prefixed with `[S&P500]`:

```
[S&P500] Filtering out 2 non-S&P 500 symbols
[S&P500] Loaded 500 tickers from cache
[S&P500] Validating symbols against S&P 500 list
```

View logs:
```bash
tail -f logs/stock_agent.log | grep S&P500
```

---

## Tips for Best Results

### 1. Start Small
```bash
# Test with top stocks first
python main.py AAPL MSFT GOOGL
```

### 2. Use Samples for Comprehensive Analysis
```bash
# Analyze random 25 from 500
python main.py --sample 25
```

### 3. Monitor Cache
```bash
# Check cache size
python main.py --cache-stats

# Clear if needed
python main.py --clear-cache
```

### 4. Validate Before Analysis
```bash
# Verify your symbols
python main.py --validate AAPL MSFT CUSTOM_TICKER
```

### 5. Use Lookback Period Wisely
```bash
# Default: 252 days (1 year)
python main.py AAPL

# Extended: 2 years
python main.py AAPL --lookback 504

# Short term: 6 months
python main.py AAPL --lookback 126
```

---

## Future Enhancements

### Planned for Phase 2+

- [ ] Sector-based analysis
- [ ] S&P 500 index correlation
- [ ] Market cap weighted sampling
- [ ] Dividend yield filtering
- [ ] PE ratio screening
- [ ] Technical setup screening

---

## Limitations & Notes

1. **Historical Data**: Using YFinance for backtesting (not real-time)
2. **Options Data**: Currently using YFinance (may lack some Greeks)
3. **API Rate Limits**: Massive.com API has rate limits
4. **Cache TTL**: 1 hour default (configurable)
5. **S&P 500 List**: Updated as of May 2024

---

## Support & Resources

### Commands Reference

```bash
# List tickers
python main.py --list-sp500

# Count constituents
python main.py --count-sp500

# Validate symbols
python main.py --validate SYMBOL1 SYMBOL2

# Analyze symbols
python main.py SYMBOL1 SYMBOL2

# Random sample
python main.py --sample N

# Cache management
python main.py --cache-stats
python main.py --clear-cache
```

### Python API Reference

```python
# Import
from sp500_tickers import get_sp500_manager
from validators import Validator

# Manager functions
manager.get_all_tickers()              # All 500
manager.is_sp500_ticker(symbol)        # Single check
manager.filter_sp500(symbols)          # Filter list
manager.validate_tickers(symbols)      # Validate list
manager.get_sector_tickers(sector)     # By sector
manager.get_random_sample(n)           # Random n

# Validator functions
Validator.validate_sp500_symbol(s)     # Single
Validator.validate_sp500_symbols(list) # List
Validator.filter_sp500_only(list)      # Filter
```

---

## Quick Reference

**Total S&P 500 Constituents**: 500  
**Largest Company**: Apple (AAPL)  
**Update Frequency**: As needed (currently May 2024)  
**Cache TTL**: 7 days (ticker list), 1 hour (data)  

---

**Last Updated**: May 2024  
**Status**: ✅ Phase 1 Complete with S&P 500 Focus

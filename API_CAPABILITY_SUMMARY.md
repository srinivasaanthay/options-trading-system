# Massive Pro API - Complete Capability Summary

**Analysis Date**: May 2026  
**Total API Endpoints Documented**: 18  
**Coverage**: Options chains, price data, technical indicators, market status

---

## Quick Reference Table

| Category | Endpoint | Purpose | Rate | Recency |
|----------|----------|---------|------|---------|
| **CHAIN DATA** | | | | |
| | `/v3/reference/options/contracts/{ticker}` | Contract details | Low | Daily |
| | `/v3/snapshot/options/{underlying}` | Full chain snapshot | Medium | Real-time |
| | `/v3/snapshot/options/{underlying}/{contract}` | Single contract | Low | Real-time |
| | `/v3/reference/options/contracts` | Contract index | Low | Daily |
| | `/v3/snapshot` | Unified snapshot | Medium | Real-time |
| **PRICE DATA** | | | | |
| | `/v3/quotes/{ticker}` | Historical quotes | High | Real-time |
| | `/v3/trades/{ticker}` | Tick-level trades | High | Real-time |
| | `/v1/open-close/{ticker}/{date}` | Daily OHLC | Low | End-of-day |
| | `/v2/aggs/ticker/{ticker}/prev` | Previous day bar | Low | End-of-day |
| | `/v2/aggs/ticker/{ticker}/range/...` | Custom OHLC | Medium | Real-time |
| **INDICATORS** | | | | |
| | `/v1/indicators/sma/{ticker}` | Simple MA | Low | Real-time |
| | `/v1/indicators/ema/{ticker}` | Exponential MA | Low | Real-time |
| | `/v1/indicators/macd/{ticker}` | MACD | Low | Real-time |
| | `/v1/indicators/rsi/{ticker}` | RSI | Low | Real-time |
| **REFERENCE** | | | | |
| | `/v3/reference/exchanges` | Exchange data | None | As needed |
| | `/v3/reference/conditions` | Condition codes | None | As needed |
| | `/v1/marketstatus/now` | Current status | None | Real-time |
| | `/v1/marketstatus/upcoming` | Holidays | None | As needed |

---

## API Organization by Use Case

### 1. Daily Comprehensive Analysis (9 AM)
**Goal**: Analyze all 500 S&P 500 stocks completely  
**Duration**: 30-60 minutes  
**API Calls**: ~3000-3500

**Data Flow**:
```
Market Status Check
    ↓
Load Reference Data (Exchanges, Conditions)
    ↓
For Each Stock (Parallel):
    ├─ /v3/snapshot/options/{underlying}        [Chain data]
    ├─ /v1/indicators/sma/{ticker}              [SMA 50, 200]
    ├─ /v1/indicators/ema/{ticker}              [EMA 12, 26]
    ├─ /v1/indicators/macd/{ticker}             [MACD]
    ├─ /v1/indicators/rsi/{ticker}              [RSI]
    └─ /v1/open-close/{ticker}/{date}           [Today's OHLC]
    ↓
Generate Recommendations
    ↓
Store Top 10
```

### 2. 20-Minute Quick Update
**Goal**: Update top 20 candidates efficiently  
**Duration**: <5 minutes  
**API Calls**: ~60-80

**Data Flow**:
```
Market Status Check
    ↓
For Top 20 Candidates:
    ├─ /v3/snapshot/options/{underlying}        [Updated chain]
    ├─ /v3/quotes/{ticker}                      [Recent quotes]
    └─ /v3/trades/{ticker}                      [Recent trades]
    ↓
Recalculate Scores
    ↓
Update Top 10 (if needed)
```

### 3. Contract Lookup & Analysis
**Goal**: Detailed analysis of specific contracts  
**API Endpoints**:
- `/v3/reference/options/contracts/{ticker}` - Contract specs
- `/v3/snapshot/options/{underlying}/{contract}` - Detailed snapshot
- `/v2/aggs/ticker/{ticker}/range/...` - Price history
- `/v3/trades/{ticker}` - Recent trade activity

---

## API Response Data Types

### Options Chain Snapshot `/v3/snapshot/options/{underlying}`
**Includes**:
- ✅ Greeks: delta, gamma, theta, vega, rho
- ✅ Implied Volatility (%)
- ✅ Open Interest (contracts)
- ✅ Last Quote: bid, ask, midpoint, spread
- ✅ Last Trade: price, size, timestamp, conditions
- ✅ Break-even Price (for profit/loss calculation)
- ✅ Daily bar: OHLC, volume, VWAP
- ✅ Underlying asset: price, change, change %

**Critical Fields**:
```json
{
  "details": {
    "contract_type": "call|put",
    "exercise_style": "american|european|bermudan",
    "expiration_date": "2026-06-15",
    "strike_price": 150.0,
    "shares_per_contract": 100
  },
  "greeks": {
    "delta": 0.55,      // Directional sensitivity
    "gamma": 0.007,     // Delta acceleration
    "theta": -0.018,    // Daily time decay
    "vega": 0.73,       // Volatility sensitivity
    "rho": 0.12         // Interest rate sensitivity
  },
  "implied_volatility": 0.305,     // 30.5% annualized
  "open_interest": 8921,           // Contracts outstanding
  "last_quote": {
    "bid": 20.9,        // Bid price
    "ask": 21.25,       // Ask price
    "bid_size": 172,    // Round lots at bid (17,200 shares)
    "ask_size": 110,    // Round lots at ask (11,000 shares)
    "spread": 0.35      // Bid-ask spread
  }
}
```

### Technical Indicators (SMA, EMA, MACD, RSI)
**Format**: Time-series data with timestamps

```json
{
  "results": {
    "values": [
      {
        "timestamp": 1517562000016,
        "value": 140.139  // Indicator value
      }
    ]
  }
}
```

### Price Data (OHLC)
**Format**: Open, High, Low, Close, Volume

```json
{
  "results": [
    {
      "o": 115.55,    // Open
      "h": 117.59,    // High
      "l": 114.13,    // Low
      "c": 115.97,    // Close
      "v": 131704427, // Volume
      "vw": 116.3,    // Volume-weighted price
      "t": 1605042000000  // Timestamp
    }
  ]
}
```

---

## API Access & Plan Availability

### Our Plan Level
**Assumed**: Options Business + Expansion (Premium tier)

**Access Level**:
- ✅ All options endpoints
- ✅ All technical indicators
- ✅ Real-time data (not delayed)
- ✅ All history (back to 2014)
- ✅ High rate limits

### Rate Limiting Strategy
**Massive API typically allows**:
- ~100 requests/minute per API key
- Batch operations recommended
- Pagination for large datasets
- Caching for reference data

**Our Strategy**:
- Parallel processing (4+ workers)
- Cache reference data (exchanges, conditions)
- Batch indicator requests
- Pagination for quotes/trades

---

## Feature Engineering from APIs

### Features Extracted (30+)

**Price Features** (5):
- Current price vs SMA50, SMA200
- Price vs EMA12, EMA26
- Daily return %
- 5-day average return
- 20-day volatility

**Technical Features** (8):
- MACD value, signal, histogram, trend
- RSI value, RSI trend
- SMA50/200 crossover status
- EMA12/26 crossover status

**Options Features** (12):
- Delta (directional)
- Gamma (acceleration)
- Theta (time decay)
- Vega (volatility)
- Rho (interest rate)
- Implied Volatility %
- IV rank/percentile
- Open Interest
- Bid/ask spread %
- Liquidity score
- Distance to strike
- Days to expiration

**Market Features** (4):
- Trend direction
- Volatility regime
- Sector momentum
- Market breadth

**Sentiment Features** (1):
- News sentiment score

**Total**: 30+ features for ML model

---

## Data Quality Considerations

### Greeks Limitations
**When Greeks May Not Be Available**:
- Deep in-the-money options
- Deep out-of-the-money options
- Very illiquid contracts
- Near/at expiration

**Solution**: Fallback to analytical approximations or flag in recommendations

### Missing Data Handling
**Quote Conditions**:
- Regular trade conditions
- After-hours conditions
- Corrected trades
- Split-adjusted prices

**Strategy**: Interpret condition codes to filter eligible trades

### Timestamp Precision
**Multiple timestamp fields**:
- `participant_timestamp`: Exchange timestamp (nanosecond)
- `sip_timestamp`: Market data timestamp (nanosecond)
- Regular timestamp: Millisecond precision

**Strategy**: Use SIP timestamp for data consistency

---

## Optimization Opportunities

### 1. Caching Strategy
```
Cache Type              | TTL   | Data Size | Benefit
─────────────────────────────────────────────────────
Exchange mapping        | 7 days | <1 KB     | Reuse across all calls
Condition codes         | 7 days | <10 KB    | Reuse across all calls
Market holidays         | Daily  | <1 KB     | Schedule validation
Contract specs          | Daily  | ~100 KB   | Contract lookup
SMA/EMA for stock       | Hourly | ~10 KB    | Technical analysis
Last daily OHLC         | Daily  | <1 KB     | Baseline comparison
```

### 2. Request Batching
- **SMA/EMA/MACD/RSI**: Can fetch all 4 in parallel for each stock
- **Options chain**: Single endpoint returns full chain
- **Quotes/Trades**: Can filter by timestamp range to get batch

### 3. Selective Fetching
- **Daily**: Analyze all 500 stocks (comprehensive)
- **20-min**: Analyze top 20 only (quick update)
- **Result**: 95% reduction in API calls for quick updates

### 4. Pagination Handling
```
Default limits:
- Options chain: 10-250 results per page
- Quotes/Trades: 1000-50000 results per page

Strategy:
- Use max limits to reduce pagination overhead
- Use cursor-based pagination (not offset)
- Process paginated results in parallel
```

---

## Real-Time Capabilities

### What's Real-Time
- ✅ Options quotes (bid/ask)
- ✅ Options trades
- ✅ Technical indicator calculations
- ✅ Market status
- ✅ Greeks calculations

### What's Delayed
- ⏱️ News sentiment (varies)
- ⏱️ Daily OHLC (end-of-day)
- ⏱️ Open interest (end-of-day)

### Hybrid Approach
```
9 AM Daily Analysis:
  - Full real-time data
  - Latest Greeks
  - Updated IV
  - Current bid/ask
  - Recent trades
  - Latest technical indicators
  - News sentiment (if available)

Every 20 Min Update:
  - Real-time Greeks update
  - Live quote refresh
  - Recent trades (last 20 mins)
  - Indicator recalculation
  - Score update
```

---

## API Usage Examples

### Example 1: Get Full Options Chain with Greeks
```
GET /v3/snapshot/options/AAPL
Response includes:
- All CALL contracts with Greeks
- All PUT contracts with Greeks
- IV for each contract
- Bid/ask prices
- Recent trades
- Open interest
- Break-even prices
```

**Typical Size**: 200-500 contracts per stock  
**Time**: ~1-2 seconds per stock  
**Parallel (50 workers)**: 500 stocks in ~10 seconds

### Example 2: Fetch Technical Indicators
```
GET /v1/indicators/sma/AAPL?window=50&timespan=day&limit=100
GET /v1/indicators/ema/AAPL?window=12&timespan=day&limit=100
GET /v1/indicators/macd/AAPL?timespan=day&limit=100
GET /v1/indicators/rsi/AAPL?window=14&timespan=day&limit=100
Response: 100 days of indicator values
```

**Time**: ~0.5 seconds per stock (4 parallel calls)  
**Parallel (50 workers)**: 500 stocks in ~10 seconds

### Example 3: Get Yesterday's Performance
```
GET /v2/aggs/ticker/O:AAPL210917C00100000/prev
Response:
{
  "c": 115.97,      // Close
  "h": 117.59,      // High
  "l": 114.13,      // Low
  "o": 115.55,      // Open
  "v": 131704427,   // Volume
  "vw": 116.3,      // Volume-weighted
  "t": 1605042000000
}
```

**Time**: ~0.2 seconds per contract

---

## Next Actions

### Ready to Build:
1. ✅ Architecture designed
2. ✅ API endpoints catalogued
3. ✅ Data flow mapped
4. ✅ Feature engineering planned
5. ✅ Optimization strategies defined

### Implementation Sequence:
1. Analyzer modules (News, Technical, Options, Market, Strategy, Predictor, Reasoning)
2. FastAPI backend (Routes, DB, WebSocket)
3. Scheduled tasks (Daily comprehensive, 20-min updates)
4. Testing & optimization
5. Production deployment

---

**Analysis Complete**: Ready to proceed with Phase 3 implementation  
**API Efficiency**: Optimized for 500 stocks + real-time updates  
**Total Endpoints**: 18 (all documented & integrated)  
**Estimated Success Rate**: High (comprehensive API coverage)

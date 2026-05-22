# Options Trading Recommendation System - Architecture Design

**Status**: Phase 3 Planning  
**Date**: May 2026  
**Foundation**: Phases 1-2 Complete (Foundation + S&P 500)

---

## 1. Executive Summary

This document outlines the complete architecture for a professional options trading recommendation system that analyzes all 500 S&P 500 stocks every 20 minutes and generates Top 10 CALL/PUT recommendations.

**Key Capabilities**:
- ✅ S&P 500 exclusive analysis (500 stocks)
- ✅ HYBRID analysis: Daily comprehensive model (9 AM) + 20-minute quick updates
- ✅ Options strategies: 8+ strategies (Bull Call Spread, Iron Condor, etc.)
- ✅ Top 10 ranking algorithm
- ✅ Human-like reasoning generation
- ✅ FastAPI REST backend with WebSocket support
- ✅ 18 Massive Pro API endpoints optimally leveraged
- ✅ Real-time Greeks, IV, bid/ask analysis
- ✅ Built-in technical indicators from Massive API
- ✅ Database persistence with SQLite
- ✅ JWT authentication & security

---

## 2. Massive Pro API Capabilities Discovered

### A. Options Chain & Contract Data (5 endpoints)
| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `/v3/reference/options/contracts/{ticker}` | Contract details (type, expiry, strike, exercise style) | Contract specification lookup |
| `/v3/snapshot/options/{underlying}` | Full options chain snapshot with Greeks, IV, quotes, trades, open interest | Primary: Daily comprehensive analysis |
| `/v3/snapshot/options/{underlying}/{contract}` | Single contract snapshot with detailed metrics | Trade evaluation & risk assessment |
| `/v3/reference/options/contracts` | Comprehensive contract index (active/expired) | Contract discovery & filtering |
| `/v3/snapshot` | Unified snapshot (stocks, options, forex, crypto) | Cross-asset comparison |

### B. Price & Trade Data (5 endpoints)
| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `/v3/quotes/{ticker}` | Historical quotes (bid/ask prices, sizes, timestamps) | Market depth analysis |
| `/v3/trades/{ticker}` | Tick-level trade data (price, size, exchange, conditions) | Market microstructure analysis |
| `/v1/open-close/{ticker}/{date}` | Daily OHLC + pre/after-hours | Daily performance tracking |
| `/v2/aggs/ticker/{ticker}/prev` | Previous day OHLC bar | Baseline comparison |
| `/v2/aggs/ticker/{ticker}/range/{mult}/{span}/{from}/{to}` | Custom OHLC bars (5-min, hourly, daily) | Technical analysis |

### C. Built-in Technical Indicators (4 endpoints)
| Endpoint | Indicator | Output |
|----------|-----------|--------|
| `/v1/indicators/sma/{ticker}` | Simple Moving Average (customizable window) | Trend analysis, support/resistance |
| `/v1/indicators/ema/{ticker}` | Exponential Moving Average (more responsive) | Dynamic trend detection |
| `/v1/indicators/macd/{ticker}` | MACD (histogram, signal, value) | Momentum confirmation |
| `/v1/indicators/rsi/{ticker}` | RSI (0-100 scale) | Overbought/oversold detection |

### D. Reference Data (4 endpoints)
| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `/v3/reference/exchanges` | Exchange mapping (ID → Name, MIC code) | Quote source interpretation |
| `/v3/reference/conditions` | Trade/quote condition codes | Data quality & validity |
| `/v1/marketstatus/now` | Real-time market status | Scheduling & operation timing |
| `/v1/marketstatus/upcoming` | Market holidays | Holiday handling |

**Total Leveraged**: 18 Massive API endpoints

---

## 3. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANALYSIS ENGINE CORE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  Market Status   │  │  S&P 500 Batch   │  │ Reference   │  │
│  │  Monitor         │  │ Processing       │  │ Data Cache  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
│           │                      │                    │          │
│           └──────────┬───────────┴────────────────────┘          │
│                      ▼                                           │
│           ┌─────────────────────────┐                           │
│           │ Parallel Data Pipeline  │                           │
│           │ (4+ worker threads)     │                           │
│           └────┬────────────────────┘                           │
│                │                                                 │
│      ┌─────────┴──────────┐                                     │
│      ▼                    ▼                                     │
│   ┌──────────────────────────────┐                             │
│   │  Options Data Fetcher        │                             │
│   │ - Chain snapshots            │                             │
│   │ - Greeks, IV, OI             │                             │
│   │ - Quotes, trades             │                             │
│   └──────────┬───────────────────┘                             │
│              │                                                   │
│      ┌───────┴──────────┬──────────────┐                        │
│      ▼                  ▼              ▼                        │
│  ┌────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ News   │  │ Technical    │  │ Options      │               │
│  │Analyzer│  │ Analyzer     │  │ Analyzer     │               │
│  └────┬───┘  └──────┬───────┘  └──────┬───────┘               │
│       │             │                  │                        │
│       └─────────────┼──────────────────┘                        │
│                     ▼                                           │
│       ┌─────────────────────────────┐                          │
│       │ Market Analyzer             │                          │
│       │ (Trend, Volatility, Regime) │                          │
│       └──────────┬──────────────────┘                          │
│                  │                                              │
│      ┌───────────┴────────────────┐                            │
│      ▼                            ▼                            │
│  ┌─────────────────┐  ┌──────────────────────┐                │
│  │ Strategy        │  │ Call/Put Predictor   │                │
│  │ Selector        │  │ (Binary Classifier)  │                │
│  │ (8+ strategies) │  │                      │                │
│  └────────┬────────┘  └──────────┬───────────┘                │
│           │                      │                             │
│           └──────────┬───────────┘                             │
│                      ▼                                          │
│       ┌────────────────────────────┐                           │
│       │ Ranking & Scoring Engine   │                           │
│       │ (Top 10 selection)         │                           │
│       └──────────┬─────────────────┘                           │
│                  │                                              │
│                  ▼                                              │
│       ┌────────────────────────────┐                           │
│       │ Reasoning Generator        │                           │
│       │ (Human-like explanations)  │                           │
│       └──────────┬─────────────────┘                           │
│                  │                                              │
│                  ▼                                              │
│       ┌────────────────────────────┐                           │
│       │ Recommendation Package     │                           │
│       │ (Ready for API/DB)         │                           │
│       └────────────────────────────┘                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI REST BACKEND                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ Auth Routes  │  │ Analysis     │  │ WebSocket        │      │
│  │ (JWT)        │  │ Routes       │  │ Real-time        │      │
│  └──────────────┘  │ (GET/POST)   │  │ Updates          │      │
│                    └──────────────┘  └──────────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ Portfolio    │  │ Watchlist    │  │ Notifications    │      │
│  │ Routes       │  │ Routes       │  │ Routes           │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      SCHEDULED TASKS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────┐                    │
│  │ Daily Task (9:00 AM ET)                │                    │
│  │ - Full news sentiment analysis         │                    │
│  │ - Train ML model                       │                    │
│  │ - 500 stocks comprehensive analysis    │                    │
│  │ Duration: ~30-60 minutes               │                    │
│  └────────────────────────────────────────┘                    │
│                                                                   │
│  ┌────────────────────────────────────────┐                    │
│  │ 20-Minute Quick Analysis               │                    │
│  │ Every 20 mins during trading day       │                    │
│  │ - Fast data fetching                   │                    │
│  │ - Quick scoring                        │                    │
│  │ - Update recommendations               │                    │
│  │ Duration: ~2-5 minutes                 │                    │
│  └────────────────────────────────────────┘                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      DATA PERSISTENCE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SQLite Database Tables:                                        │
│  - recommendations (Top 10 per analysis)                       │
│  - analysis_runs (Execution history)                           │
│  - portfolios (User portfolios)                                │
│  - watchlists (User watchlists)                                │
│  - users (Authentication)                                       │
│  - market_cache (Reference data cache)                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow Strategy

### 4.1 Daily Comprehensive Analysis (9:00 AM ET)

```
START (9:00 AM) ──→ Market Status Check
                    │
                    ├─ If not open: Skip
                    └─ If open: Continue
                         │
                         ▼
                 Load Reference Data
                 (Exchanges, Conditions, Holidays)
                         │
                         ▼
                 Fetch News Sentiment
                 (From Massive API articles)
                         │
                         ▼
                 Train Sentiment Model
                 (Historical + new data)
                         │
                         ▼
            ┌────────────────────────────┐
            │ For Each S&P 500 Stock:    │
            │ (Parallel: 4+ workers)     │
            │                            │
            │ 1. Fetch Options Chain     │
            │    /v3/snapshot/options    │
            │                            │
            │ 2. Fetch Technical Data    │
            │    - SMA (50, 200)         │
            │    - EMA (12, 26)          │
            │    - MACD                  │
            │    - RSI                   │
            │                            │
            │ 3. Get Daily OHLC          │
            │    /v1/open-close          │
            │                            │
            │ 4. Analyze Quotes/Trades   │
            │    - Bid/ask spread        │
            │    - Volume patterns       │
            │                            │
            │ 5. Calculate Greeks Impact │
            │    - Delta, Gamma, Theta   │
            │    - Vega sensitivity      │
            │                            │
            │ 6. Score Each Option       │
            │    - Intrinsic value       │
            │    - Time value            │
            │    - Liquidity             │
            │    - Risk/reward ratio     │
            └────────────────────────────┘
                         │
                         ▼
                 Generate Top 10 List
                 (Combined CALL/PUT)
                         │
                         ▼
                 Store in Database
                 Create API Response
                         │
                         ▼
                    END (~10:00 AM)
```

### 4.2 20-Minute Quick Update (Every 20 mins)

```
START (Every 20 mins) ──→ Market Status Check
                          │
                          ├─ If closed: Skip
                          └─ If open: Continue
                               │
                               ▼
                   Fetch Top 20 Candidates
                   (From last analysis)
                               │
                         ┌─────┴──────┐
                         ▼            ▼
                    Quick Data    Sentiment
                    Fetch         Update
                    - Quotes      (If available)
                    - Trades
                    - Current Greeks
                         │            │
                         └─────┬──────┘
                               ▼
                       Recalculate Scores
                       (New data only)
                               │
                               ▼
                       Update Top 10
                       (Keep best candidates)
                               │
                               ▼
                       Push to WebSocket
                       (Real-time subscribers)
                               │
                               ▼
                          END (~2-5 mins)
```

---

## 5. Module Organization

### 5.1 New `analyzer/` Package Structure

```
analyzer/
├── __init__.py
│
├── news_analyzer.py
│   ├── NewsAnalyzer class
│   ├── Sentiment scoring (positive/negative/neutral)
│   ├── Historical training model
│   ├── Daily retraining logic
│   └── Real-time sentiment updates
│
├── technical_analyzer.py
│   ├── TechnicalAnalyzer class
│   ├── SMA calculations (50, 200 day)
│   ├── EMA calculations (12, 26 day)
│   ├── MACD analysis (value, signal, histogram)
│   ├── RSI analysis (overbought/oversold)
│   ├── Support/resistance detection
│   ├── Trend identification (up/down/sideways)
│   └── Volume analysis
│
├── options_analyzer.py
│   ├── OptionsAnalyzer class
│   ├── Greeks analysis (delta, gamma, theta, vega, rho)
│   ├── Implied Volatility (IV) analysis
│   ├── Bid/ask spread analysis
│   ├── Open interest analysis
│   ├── Liquidity scoring
│   ├── Strike selection logic
│   ├── Expiration selection logic
│   └── Option pricing metrics
│
├── market_analyzer.py
│   ├── MarketAnalyzer class
│   ├── Trend direction (up/down)
│   ├── Volatility regime (low/medium/high)
│   ├── Market breadth analysis
│   ├── Sector momentum
│   ├── VIX impact assessment
│   └── Overall market health score
│
├── strategy_selector.py
│   ├── StrategySelector class
│   ├── Bull Call Spread (bullish, limited risk)
│   ├── Bear Call Spread (bearish, limited risk)
│   ├── Bull Put Spread (income strategy)
│   ├── Bear Put Spread (bullish/income)
│   ├── Iron Condor (low volatility)
│   ├── Long Straddle (high volatility)
│   ├── Long Strangle (high volatility, cheaper)
│   ├── Calendar Spread (sideways markets)
│   └── Strategy selection based on signals
│
├── call_put_predictor.py
│   ├── CallPutPredictor class
│   ├── Feature engineering (30+ features)
│   ├── ML model (trained daily)
│   ├── Binary classification (CALL vs PUT)
│   ├── Confidence scoring
│   ├── Backtesting framework
│   └── Model performance tracking
│
└── reasoning_generator.py
    ├── ReasoningGenerator class
    ├── Template-based explanations
    ├── Data-driven insights
    ├── Risk/reward narratives
    ├── Human-like phrasing
    ├── Strategy justifications
    └── Key catalyst identification
```

### 5.2 Enhanced `api/` Package

```
api/
├── __init__.py
├── routes/
│   ├── __init__.py
│   ├── auth.py (JWT authentication)
│   ├── analysis.py (Analysis endpoints)
│   ├── recommendations.py (GET Top 10, filtered views)
│   ├── portfolio.py (User portfolio management)
│   ├── watchlist.py (Custom watchlist management)
│   ├── notifications.py (Alert management)
│   └── websocket.py (Real-time streaming)
│
├── models/
│   ├── __init__.py
│   ├── recommendation.py (Recommendation schema)
│   ├── user.py (User schema)
│   ├── portfolio.py (Portfolio schema)
│   ├── analysis.py (Analysis metadata)
│   └── notification.py (Alert schema)
│
└── middleware/
    ├── __init__.py
    ├── auth.py (JWT verification)
    ├── rate_limit.py (API throttling)
    └── error_handler.py (Exception handling)
```

### 5.3 Enhanced `scheduler/` Package

```
scheduler/
├── __init__.py
├── tasks.py
│   ├── DailyComprehensiveTask (9:00 AM)
│   ├── QuickUpdateTask (Every 20 mins)
│   ├── NewsUpdateTask (Every hour)
│   ├── MarketStatusTask (Every minute)
│   └── MaintenanceTasks (Cleanup, archiving)
│
└── coordinator.py
    ├── Task orchestration
    ├── Timing management
    ├── Error recovery
    └── Task status monitoring
```

---

## 6. Key Optimization Strategies

### 6.1 API Call Efficiency

| Strategy | Implementation | Benefit |
|----------|-----------------|---------|
| **Batch Processing** | Analyze 500 stocks in parallel (4+ workers) | 10-20x speed improvement |
| **Selective Fetching** | 20-min updates fetch only top 20 candidates | Reduce API calls 95% |
| **Smart Caching** | Cache reference data (exchanges, conditions) | Reuse across all analyses |
| **Lazy Loading** | Fetch technical indicators only when needed | Reduce unnecessary API calls |
| **Pagination** | Use cursor-based pagination for large datasets | Handle high-volume data |
| **Conditional Requests** | Track last_updated timestamps | Avoid duplicate fetches |

### 6.2 Data Pipeline Optimization

```
Performance Targets:
- Daily analysis: 500 stocks in ~30-60 minutes
- Per stock: ~5-10 seconds (parallel)
- 20-minute update: Top 20 in <5 minutes
- API calls per 20-min: ~100-150 (vs ~5000 without optimization)
```

### 6.3 Feature Engineering (30+ Features)

**Price Features**:
- Current price vs SMA50, SMA200
- Price vs EMA12, EMA26
- Daily return %
- 5-day average return

**Technical Features**:
- MACD value, signal, histogram
- RSI value (0-100)
- Bollinger Bands position
- Volume ratio (current vs average)

**Option Features**:
- Delta (directional sensitivity)
- Gamma (acceleration)
- Theta (time decay)
- Vega (volatility sensitivity)
- Implied Volatility %
- Open Interest
- Bid/ask spread %

**Market Features**:
- Trend direction (up/down/sideways)
- Volatility regime (VIX level)
- Sector momentum
- News sentiment score

---

## 7. Massive API Endpoint Usage Plan

### Daily Analysis (9:00 AM)
```
Per Stock (500 total):
1. /v3/snapshot/options/{underlying}      - Full chain snapshot
2. /v1/indicators/sma/{ticker}            - SMA (50, 200)
3. /v1/indicators/ema/{ticker}            - EMA (12, 26)
4. /v1/indicators/macd/{ticker}           - MACD
5. /v1/indicators/rsi/{ticker}            - RSI
6. /v1/open-close/{ticker}/{date}         - Today's OHLC

Shared (Once):
- /v3/reference/exchanges                 - Exchange mapping
- /v3/reference/conditions                - Condition codes
- /v1/marketstatus/now                    - Market status
- /v1/marketstatus/upcoming               - Holidays

Total API calls: ~3000-3500 (manageable with rate limits)
```

### 20-Minute Update (Top 20 only)
```
Per Stock (20 total):
1. /v3/snapshot/options/{underlying}      - Updated chain
2. /v3/quotes/{ticker}                    - Recent quotes
3. /v3/trades/{ticker}                    - Recent trades

Shared:
- /v1/marketstatus/now                    - Quick status check

Total API calls: ~60-80 (very lightweight)
```

---

## 8. Call/Put Prediction Model

### Binary Classification Approach

```
Model: Gradient Boosting (XGBoost/LightGBM)

Target Variable:
- CALL = 1 (Bullish signals)
- PUT = 0 (Bearish signals)

Features (30+ total):
- Technical indicators (SMA, EMA, MACD, RSI)
- Price momentum and trends
- Volatility regime
- Options Greeks
- Open interest dynamics
- News sentiment
- Volume patterns
- Market breadth

Training:
- Daily retraining at 9:00 AM
- Historical data: 2+ years
- Walk-forward validation
- Performance tracking
- Confidence calibration

Output:
- Probability CALL: 0.0-1.0
- Confidence: Low/Medium/High
- Recommendation: CALL/PUT
```

---

## 9. Top 10 Ranking Algorithm

### Multi-Factor Scoring

```
RECOMMENDATION_SCORE = 
    (Technical_Score × 0.30) +
    (Options_Score × 0.35) +
    (Sentiment_Score × 0.15) +
    (Risk_Reward_Score × 0.20)

Technical_Score (0-100):
- Trend strength (0-40)
- Momentum confirmation (0-30)
- Support/resistance (0-30)

Options_Score (0-100):
- Delta appropriateness (0-30)
- IV rank/percentile (0-25)
- Liquidity (0-25)
- Greeks exposure (0-20)

Sentiment_Score (0-100):
- News sentiment (0-60)
- Trend alignment (0-40)

Risk_Reward_Score (0-100):
- Profit/loss ratio (0-50)
- Probability of profit (0-30)
- Max loss (0-20)

Final Selection:
- Top 10 by combined score
- Balanced across CALLS/PUTS
- Diverse underlying stocks
- Mixed strategies
```

---

## 10. Database Schema

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR UNIQUE,
    username VARCHAR UNIQUE,
    password_hash VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE recommendations (
    id INTEGER PRIMARY KEY,
    analysis_run_id INTEGER FOREIGN KEY,
    rank INTEGER (1-10),
    underlying_symbol VARCHAR,
    option_symbol VARCHAR,
    contract_type VARCHAR (CALL/PUT),
    strategy VARCHAR,
    strike_price FLOAT,
    expiration_date DATE,
    current_price FLOAT,
    target_spike_price FLOAT,
    probability_of_profit FLOAT,
    expected_return_percent FLOAT,
    max_risk FLOAT,
    reasoning TEXT,
    confidence_score FLOAT,
    technical_score FLOAT,
    options_score FLOAT,
    sentiment_score FLOAT,
    risk_reward_score FLOAT,
    created_at TIMESTAMP
);

CREATE TABLE analysis_runs (
    id INTEGER PRIMARY KEY,
    run_type VARCHAR (DAILY/QUICK),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    stocks_analyzed INTEGER,
    successful_analyses INTEGER,
    failed_analyses INTEGER,
    total_options_evaluated INTEGER,
    top_10_selected INTEGER,
    model_version VARCHAR,
    performance_metrics JSON
);

CREATE TABLE portfolios (
    id INTEGER PRIMARY KEY,
    user_id INTEGER FOREIGN KEY,
    name VARCHAR,
    description TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE portfolio_positions (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER FOREIGN KEY,
    option_symbol VARCHAR,
    quantity INTEGER,
    entry_price FLOAT,
    entry_date TIMESTAMP,
    exit_price FLOAT NULL,
    exit_date TIMESTAMP NULL,
    status VARCHAR (OPEN/CLOSED)
);

CREATE TABLE watchlists (
    id INTEGER PRIMARY KEY,
    user_id INTEGER FOREIGN KEY,
    name VARCHAR,
    created_at TIMESTAMP
);

CREATE TABLE watchlist_items (
    id INTEGER PRIMARY KEY,
    watchlist_id INTEGER FOREIGN KEY,
    option_symbol VARCHAR,
    added_at TIMESTAMP
);

CREATE TABLE market_cache (
    key VARCHAR PRIMARY KEY,
    value TEXT,
    expires_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## 11. FastAPI Routes

### Authentication
```
POST /api/auth/register          Register new user
POST /api/auth/login             Authenticate & get JWT
POST /api/auth/refresh           Refresh token
GET  /api/auth/me                Current user info
```

### Analysis & Recommendations
```
GET  /api/analysis/latest        Get latest Top 10
GET  /api/analysis/history       Historical analyses
GET  /api/analysis/{id}          Specific analysis
POST /api/analysis/run           Trigger manual analysis
GET  /api/recommendations        Top 10 recommendations
GET  /api/recommendations/CALL   Call recommendations only
GET  /api/recommendations/PUT    Put recommendations only
GET  /api/recommendations/{symbol}  Recommendations for symbol
```

### Portfolio Management
```
POST /api/portfolio              Create portfolio
GET  /api/portfolio              List user portfolios
GET  /api/portfolio/{id}         Portfolio details
POST /api/portfolio/{id}/add     Add position
POST /api/portfolio/{id}/close   Close position
DELETE /api/portfolio/{id}       Delete portfolio
```

### Watchlist Management
```
POST /api/watchlist              Create watchlist
GET  /api/watchlist              List watchlists
POST /api/watchlist/{id}/add     Add item
DELETE /api/watchlist/{id}/remove  Remove item
```

### Notifications
```
POST /api/notification           Set price alert
GET  /api/notification           List notifications
DELETE /api/notification/{id}    Delete alert
```

### WebSocket (Real-time)
```
WS   /ws/recommendations         Real-time Top 10 updates
WS   /ws/symbol/{symbol}         Real-time symbol updates
WS   /ws/portfolio/{id}          Real-time portfolio updates
```

---

## 12. Implementation Phases

### Phase 3a: Core Analyzer Modules (1-2 weeks)
- [ ] Build `news_analyzer.py` with sentiment model
- [ ] Build `technical_analyzer.py` with indicators
- [ ] Build `options_analyzer.py` with Greeks
- [ ] Build `market_analyzer.py` with regime detection
- [ ] Build `strategy_selector.py` with 8+ strategies
- [ ] Build `call_put_predictor.py` with ML model
- [ ] Build `reasoning_generator.py` with explanations

### Phase 3b: FastAPI Backend (1 week)
- [ ] Set up FastAPI application structure
- [ ] Implement authentication & JWT
- [ ] Create database models & migrations
- [ ] Build REST API endpoints (analysis, recommendations)
- [ ] Add portfolio & watchlist management
- [ ] Implement WebSocket support

### Phase 3c: Scheduled Tasks (3-4 days)
- [ ] Build daily comprehensive analysis task
- [ ] Build 20-minute quick update task
- [ ] Implement task orchestration
- [ ] Add error recovery & monitoring
- [ ] Set up database persistence

### Phase 3d: Integration & Testing (3-4 days)
- [ ] End-to-end integration testing
- [ ] Performance optimization
- [ ] Load testing (500 stocks parallel)
- [ ] API testing
- [ ] Documentation & deployment guide

---

## 13. Success Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Analysis Speed (500 stocks) | <1 hour | TBD |
| Per-stock Analysis Time | <10 seconds | TBD |
| 20-minute Update Time | <5 minutes | TBD |
| API Call Efficiency | <150 calls per update | TBD |
| Top 10 Accuracy | >70% win rate | TBD |
| System Uptime | >99.5% | TBD |
| API Response Time | <200ms | TBD |

---

## 14. Risk Management

### Data Quality
- Validate all API responses for required fields
- Handle missing Greeks (for deep ITM options)
- Catch and recover from rate limits
- Implement exponential backoff for retries

### Operational Risk
- Circuit breakers for market anomalies
- Fallback recommendations if analysis fails
- Manual override capabilities
- Audit trail for all recommendations

### Financial Risk
- Always include max loss in recommendations
- Calculate probability of profit
- Position sizing recommendations
- Risk/reward ratio validation

---

## 15. Next Steps

1. **Immediate**: Start Phase 3a analyzer module development
2. **Week 2**: Complete FastAPI backend integration
3. **Week 3**: Implement scheduled tasks & testing
4. **Week 4**: Production deployment & monitoring

---

**Document Status**: Complete & Ready for Implementation  
**Last Updated**: May 2026  
**Next Review**: After Phase 3a completion

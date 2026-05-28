# MCP Agent Design: Stock Analysis & Buy Notifications

## Overview

An MCP (Model Context Protocol) agent that continuously analyzes stock tickers, identifies buy signals using the existing analyzer framework, and sends intelligent notifications across multiple channels (email, Slack, webhooks).

---

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Stock Agent                           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Agent Controller                                    │   │
│  │  - Manages ticker monitoring                         │   │
│  │  - Coordinates analysis pipeline                     │   │
│  │  - Handles user queries                              │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│         ┌────────────────┼────────────────┐                  │
│         │                │                │                  │
│    ┌────▼─────┐    ┌─────▼──────┐   ┌────▼──────┐          │
│    │ Analysis │    │ Notification│   │ Watchlist │          │
│    │ Engine   │    │   System    │   │ Manager   │          │
│    └────┬─────┘    └─────┬──────┘   └────┬──────┘          │
│         │                │                │                  │
│    ┌────▼──────────────────────────────────▼────┐           │
│    │      Existing Analyzers (Phase 3A)        │           │
│    │  - NewsAnalyzer                           │           │
│    │  - TechnicalAnalyzer                      │           │
│    │  - OptionsAnalyzer                        │           │
│    │  - MarketAnalyzer                         │           │
│    │  - StrategySelector                       │           │
│    │  - CallPutPredictor                       │           │
│    │  - ReasoningGenerator                     │           │
│    └─────────────────────────────────────────┘           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐       ┌────▼────┐      ┌────▼────┐
   │  Email  │       │  Slack   │      │ Webhook │
   │  Notify │       │  Notify  │      │ Notify  │
   └─────────┘       └──────────┘      └─────────┘
```

---

## Components

### 1. MCP Agent Core (`mcp_stock_agent.py`)

**Responsibilities:**
- Manage ticker monitoring list
- Coordinate analysis pipeline
- Track analysis history
- Manage notification state
- Handle user interactions

**Key Methods:**
```python
class MCPStockAgent:
    # Core analysis
    async def analyze_ticker(ticker: str, price: float)
    async def analyze_watchlist()
    async def get_ticker_analysis(ticker: str)
    
    # Watchlist management
    async def add_to_watchlist(ticker: str, buy_threshold: float)
    async def remove_from_watchlist(ticker: str)
    async def update_buy_threshold(ticker: str, threshold: float)
    async def get_watchlist()
    
    # Analysis state
    async def get_analysis_history(ticker: str, days: int)
    async def get_trending_opportunities()
    async def get_risk_summary()
    
    # Configuration
    async def set_notification_channels(channels: list)
    async def set_analysis_frequency(frequency: str)
    async def get_configuration()
```

### 2. Analysis Engine (`analysis_engine.py`)

**Responsibilities:**
- Orchestrate all 7 analyzers
- Compile comprehensive analysis
- Score buy signals (0.0 to 1.0)
- Identify risk levels
- Generate recommendations

**Buy Signal Scoring:**
```
Buy Score = (Technical_Score × 0.25) +
            (Sentiment_Score × 0.20) +
            (ML_Prediction × 0.30) +
            (Strategy_Score × 0.15) +
            (Market_Score × 0.10)

Buy Threshold: 0.70 (70% confidence)
```

**Output Format:**
```json
{
  "ticker": "AAPL",
  "timestamp": "2026-05-21T10:30:00Z",
  "price": 150.50,
  
  "analysis": {
    "buy_score": 0.78,
    "buy_signal": true,
    "confidence": "HIGH",
    "risk_level": "MODERATE",
    "recommendation": "STRONG_BUY"
  },
  
  "components": {
    "technical_score": 0.75,
    "sentiment_score": 0.70,
    "ml_prediction": 0.85,
    "strategy_score": 0.72,
    "market_score": 0.65
  },
  
  "reasoning": {
    "thesis": "AAPL showing strong technical setup...",
    "key_factors": [
      "Positive news sentiment",
      "Technical breakout pattern",
      "Bullish ML prediction"
    ],
    "risks": [
      "Market correction risk",
      "Earnings volatility"
    ]
  },
  
  "targets": {
    "entry_price": 150.50,
    "stop_loss": 148.50,
    "profit_target_1": 152.50,
    "profit_target_2": 155.00
  }
}
```

### 3. Notification System (`notification_manager.py`)

**Channels Supported:**
- Email (SMTP)
- Slack (Webhook/Bot)
- Discord (Webhook)
- Telegram (Bot API)
- Webhooks (Custom)
- SMS (Twilio)

**Notification Types:**
```python
# Strong Buy Signal
class BuySignalNotification:
    ticker: str
    score: float
    recommendation: str
    thesis: str
    targets: Dict
    
# Watchlist Alert
class WatchlistAlertNotification:
    ticker: str
    event: str  # "price_drop", "buy_score_high", "risk_alert"
    details: Dict
    
# Daily Digest
class DailyDigestNotification:
    date: str
    opportunities: List[Dict]
    watchlist_status: Dict
    market_summary: Dict
```

**Email Template:**
```
Subject: BUY SIGNAL - AAPL (78% Confidence)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STOCK ANALYSIS REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ticker: AAPL
Current Price: $150.50
Buy Score: 78/100 ✅
Recommendation: STRONG BUY

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS BREAKDOWN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Technical Analysis: 75/100
Sentiment Analysis: 70/100
ML Prediction: 85/100 (Bullish)
Strategy Score: 72/100
Market Environment: 65/100

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INVESTMENT THESIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

We believe AAPL is positioned for upside appreciation based on:
- Positive news sentiment and improving trend
- Technical setup favoring continuation of uptrend
- Strong momentum with bullish divergence
- Market environment remains supportive

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICE TARGETS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Entry: $150.50
Stop Loss: $148.50 (-1.3%)
Target 1: $152.50 (+1.3%)
Target 2: $155.00 (+3.0%)
Risk/Reward Ratio: 2.5:1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY RISKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ Market Correction Risk (Moderate)
⚠️ Earnings Volatility (Upcoming)
⚠️ Macro Environment Changes (Low)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS TIME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generated: 2026-05-21 10:30:00 UTC
Analysis ID: a3f9d8c2
```

### 4. Watchlist Manager (`watchlist_manager.py`)

**Features:**
- Add/remove tickers
- Set custom buy thresholds
- Track analysis history
- Alert on price changes
- Store persistent state

**Data Model:**
```python
@dataclass
class WatchlistItem:
    ticker: str
    added_date: datetime
    buy_threshold: float = 0.70
    max_position_size: float = 1000.0
    notes: str = ""
    notification_settings: Dict = None
    
    # Analysis tracking
    last_analysis: Optional[Analysis] = None
    analysis_history: List[Analysis] = field(default_factory=list)
    buy_signal_count: int = 0
    false_positives: int = 0
```

### 5. Database Models (`db_models.py`)

**Tables:**
- `watchlist_items` - Tracked tickers
- `analysis_results` - Analysis history
- `notifications` - Sent notifications log
- `user_alerts` - Alert preferences
- `performance_tracking` - Buy signal performance

---

## MCP Integration

### MCP Server Setup

```python
# mcp_server.py
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("stock-analysis-agent")
agent = MCPStockAgent()

# Register tools with MCP
@server.call_tool()
async def analyze_ticker(ticker: str, price: float = None):
    """Analyze a ticker and get buy signal"""
    return await agent.analyze_ticker(ticker, price)

@server.call_tool()
async def add_watchlist(ticker: str, buy_threshold: float = 0.70):
    """Add ticker to watchlist"""
    return await agent.add_to_watchlist(ticker, buy_threshold)

@server.call_tool()
async def get_watchlist():
    """Get current watchlist"""
    return await agent.get_watchlist()

@server.call_tool()
async def get_trending_opportunities(min_score: float = 0.75):
    """Get trending buy opportunities"""
    return await agent.get_trending_opportunities(min_score)

@server.call_tool()
async def send_notification(ticker: str, channels: List[str] = None):
    """Send analysis notification"""
    return await agent.send_notification(ticker, channels)

@server.call_tool()
async def get_analysis_history(ticker: str, days: int = 30):
    """Get analysis history for ticker"""
    return await agent.get_analysis_history(ticker, days)
```

### MCP Tools Available

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `analyze_ticker` | ticker, price | Analysis + score | Real-time analysis |
| `add_watchlist` | ticker, threshold | Confirmation | Add to tracking |
| `get_watchlist` | None | List of tickers | View tracked stocks |
| `get_trending` | min_score | List of opportunities | Find good buys |
| `send_notification` | ticker, channels | Notification ID | Alert users |
| `get_history` | ticker, days | Historical data | View trends |
| `set_alerts` | settings | Confirmation | Configure alerts |
| `get_performance` | start_date | Performance metrics | Track success |

---

## Workflow: Monitoring & Analysis

### Real-time Monitoring Loop

```
┌─────────────────────────────────────┐
│   Start Monitoring Loop              │
└─────────┬───────────────────────────┘
          │
          ▼
┌─────────────────────────────────────┐
│   Get Watchlist Items               │
│   (From database or memory)          │
└─────────┬───────────────────────────┘
          │
          ▼
┌─────────────────────────────────────┐
│   For Each Ticker:                  │
│   1. Fetch current price            │
│   2. Get latest market data         │
│   3. Run all 7 analyzers            │
└─────────┬───────────────────────────┘
          │
          ▼
┌─────────────────────────────────────┐
│   Calculate Buy Score               │
│   (Weighted composite)               │
└─────────┬───────────────────────────┘
          │
          ▼
    ┌─────▼──────────┐
    │ Score > 0.70?  │
    └─────┬──────┬───┘
          │      │
      YES │      │ NO
          │      └──────────┐
          ▼                  ▼
    ┌──────────┐    ┌─────────────┐
    │Send Alert│    │Log Analysis │
    └──────────┘    └─────────────┘
          │                 │
          └────────┬────────┘
                   ▼
        ┌─────────────────────┐
        │Save to Database     │
        │Update Watchlist     │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │Wait for Next Cycle  │
        │(Configurable)       │
        └─────────┬───────────┘
                  │
                  ▼
            (Loop back)
```

---

## Buy Signal Decision Logic

### Multi-factor Analysis

```python
def calculate_buy_score(analysis: AnalysisResult) -> float:
    """
    Calculate composite buy score (0.0 to 1.0)
    """
    
    # Factor 1: Technical Analysis (25%)
    # Checks: trend, momentum, support/resistance, chart patterns
    technical_score = analyze_technical_signals(analysis.technical)
    
    # Factor 2: Sentiment Analysis (20%)
    # Checks: news sentiment, trend, recency
    sentiment_score = analyze_sentiment_signals(analysis.sentiment)
    
    # Factor 3: ML Prediction (30%)
    # Uses trained model with 34 features
    ml_score = analysis.ml_prediction.confidence
    
    # Factor 4: Options Strategy (15%)
    # Checks: call/put ratio, IV, Greeks
    strategy_score = analyze_strategy_signals(analysis.options)
    
    # Factor 5: Market Environment (10%)
    # Checks: trend, volatility, breadth, sector
    market_score = analyze_market_signals(analysis.market)
    
    # Composite score
    buy_score = (
        technical_score * 0.25 +
        sentiment_score * 0.20 +
        ml_score * 0.30 +
        strategy_score * 0.15 +
        market_score * 0.10
    )
    
    return min(1.0, max(0.0, buy_score))

def interpret_buy_signal(score: float) -> Dict:
    """
    Interpret buy score into actionable signal
    """
    
    if score >= 0.85:
        return {
            "signal": "STRONG_BUY",
            "confidence": "VERY_HIGH",
            "action": "BUY_AGGRESSIVE",
            "position_size": "LARGE"
        }
    elif score >= 0.75:
        return {
            "signal": "BUY",
            "confidence": "HIGH",
            "action": "BUY",
            "position_size": "MEDIUM"
        }
    elif score >= 0.65:
        return {
            "signal": "ACCUMULATE",
            "confidence": "MODERATE",
            "action": "BUY_SMALL",
            "position_size": "SMALL"
        }
    elif score >= 0.50:
        return {
            "signal": "HOLD",
            "confidence": "NEUTRAL",
            "action": "WAIT",
            "position_size": "NONE"
        }
    else:
        return {
            "signal": "AVOID",
            "confidence": "BEARISH",
            "action": "STAY_OUT",
            "position_size": "NONE"
        }
```

---

## Configuration

### Agent Settings (`config.yaml`)

```yaml
agent:
  name: "Stock Analysis Agent"
  version: "1.0.0"
  
monitoring:
  # Check interval (seconds)
  interval: 300  # 5 minutes
  
  # Maximum concurrent analyses
  max_concurrent: 5
  
  # Watchlist check frequency
  check_frequency: "every_5_minutes"
  
analysis:
  # Buy signal threshold
  buy_threshold: 0.70
  
  # Confidence levels
  confidence_levels:
    very_high: 0.85
    high: 0.75
    moderate: 0.65
    low: 0.50
  
  # Weighting for factors
  weights:
    technical: 0.25
    sentiment: 0.20
    ml_prediction: 0.30
    strategy: 0.15
    market: 0.10

notifications:
  # Channels to notify
  channels:
    - email
    - slack
    - webhook
  
  # Email settings
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    from_address: "alerts@trading-system.com"
    
  # Slack settings
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK_URL}"
    channel: "#trading-alerts"
    
  # Discord settings
  discord:
    enabled: false
    webhook_url: "${DISCORD_WEBHOOK_URL}"
    
  # Custom webhook
  webhook:
    enabled: true
    url: "https://your-api.com/notifications"
    headers:
      Authorization: "Bearer ${WEBHOOK_TOKEN}"

database:
  url: "${DATABASE_URL}"
  
  # Retention policies
  retention:
    analysis_history: 90  # days
    notifications: 30     # days
    performance_data: 365 # days

watchlist:
  # Default watchlist
  tickers:
    - AAPL
    - MSFT
    - GOOGL
    - TSLA
    - NVDA
  
  # Auto-update frequency
  auto_update: true
```

---

## Usage Examples

### Example 1: Add Ticker to Watchlist

```python
# Using MCP Agent
agent = MCPStockAgent()

result = await agent.add_to_watchlist(
    ticker="NVDA",
    buy_threshold=0.75,
    max_position_size=5000.0
)

print(result)
# Output: {"status": "added", "ticker": "NVDA", "threshold": 0.75}
```

### Example 2: Analyze and Get Buy Signal

```python
# Real-time analysis
analysis = await agent.analyze_ticker("NVDA", price=450.25)

print(f"Buy Score: {analysis['buy_score']}")
print(f"Recommendation: {analysis['recommendation']}")
print(f"Thesis: {analysis['reasoning']['thesis']}")
print(f"Price Targets: {analysis['targets']}")

# Output:
# Buy Score: 0.82
# Recommendation: STRONG_BUY
# Thesis: NVDA showing strong technical momentum...
# Price Targets: {'entry': 450.25, 'stop_loss': 445, ...}
```

### Example 3: Get Trending Opportunities

```python
opportunities = await agent.get_trending_opportunities(min_score=0.75)

for opp in opportunities:
    print(f"{opp['ticker']}: {opp['score']:.1%} - {opp['recommendation']}")

# Output:
# NVDA: 82.0% - STRONG_BUY
# AAPL: 78.0% - BUY
# MSFT: 76.0% - BUY
# TSLA: 68.0% - HOLD
```

### Example 4: Send Notifications

```python
# Send to multiple channels
await agent.send_notification(
    ticker="NVDA",
    channels=["email", "slack", "webhook"],
    recipients=["user@example.com"],
    slack_channel="#trading"
)

# Output: Notification sent via email, Slack, and webhook
```

### Example 5: View Analysis History

```python
history = await agent.get_analysis_history("NVDA", days=30)

for analysis in history:
    print(f"{analysis['date']}: {analysis['score']:.1%} - {analysis['signal']}")

# Output:
# 2026-05-21: 82.0% - STRONG_BUY
# 2026-05-20: 79.0% - BUY
# 2026-05-19: 71.0% - ACCUMULATE
```

---

## Integration with Phase 3

### Phase 3B Integration
- Add database models for watchlist & analysis history
- Create API endpoints for agent control
- Build WebSocket for real-time updates

### Phase 3C Integration
- Celery tasks for continuous monitoring
- Scheduled analysis (every 5 minutes)
- Background notification delivery
- Daily digest generation

---

## Security Considerations

1. **API Security**
   - Bearer token authentication
   - Rate limiting per user
   - Input validation

2. **Data Security**
   - Encrypt sensitive config (API keys, passwords)
   - Secure database connections
   - HTTPS only for webhooks

3. **Notification Security**
   - Validate webhook URLs
   - Sign webhook payloads
   - Separate secrets from config

4. **Access Control**
   - User-scoped watchlists
   - Permission-based notifications
   - Audit logging

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Analysis Time | < 2 sec | Per ticker |
| Watchlist Check | < 10 sec | All tickers |
| Notification Delivery | < 5 sec | To all channels |
| Memory Usage | < 500MB | With 100+ tickers |
| Database Queries | < 100ms | Average |

---

## Next Steps

1. **Create MCP server** - `mcp_stock_agent.py`
2. **Build analysis engine** - `analysis_engine.py`
3. **Implement notifications** - `notification_manager.py`
4. **Add database models** - `db_models.py`
5. **Create API endpoints** - Phase 3B integration
6. **Setup monitoring** - Celery tasks (Phase 3C)

---

**Design Status**: ✅ Complete  
**Ready for**: Implementation  
**Estimated LOC**: 1,500-2,000 lines

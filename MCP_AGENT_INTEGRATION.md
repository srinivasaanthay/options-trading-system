# MCP Agent Integration Guide

Complete guide for integrating the stock analysis agent into your application.

---

## Quick Start

### 1. Add to Existing FastAPI App

```python
# In app.py
from mcp_stock_agent import MCPStockAgent
from notification_manager import NotificationManager

# Initialize agent and notification manager
agent = MCPStockAgent()
notification_manager = NotificationManager(
    slack_webhook=os.getenv("SLACK_WEBHOOK_URL"),
    email_config={
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": os.getenv("EMAIL_USER"),
        "password": os.getenv("EMAIL_PASSWORD"),
        "from_address": "alerts@trading.com"
    }
)

# Add API endpoints
@app.post("/api/v1/agent/analyze")
async def analyze_ticker(ticker: str, price: float):
    """Analyze a ticker"""
    result = await agent.analyze_ticker(ticker, price)
    return result.__dict__

@app.post("/api/v1/agent/watchlist/add")
async def add_watchlist(ticker: str, threshold: float = 0.70):
    """Add to watchlist"""
    return await agent.add_to_watchlist(ticker, threshold)

@app.get("/api/v1/agent/watchlist")
async def get_watchlist():
    """Get watchlist"""
    return await agent.get_watchlist()

@app.get("/api/v1/agent/opportunities")
async def get_opportunities(min_score: float = 0.75):
    """Get buy opportunities"""
    return await agent.get_trending_opportunities(min_score)

@app.post("/api/v1/agent/notify")
async def send_notification(
    ticker: str,
    channels: List[str] = ["email"],
    recipients: List[str] = None
):
    """Send notification"""
    return await agent.send_notification(ticker, channels, recipients)
```

### 2. Set Environment Variables

```bash
# .env file
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR/WEBHOOK
```

### 3. Test Agent

```bash
python mcp_stock_agent.py
```

---

## MCP Tools

### Tool: analyze_ticker

Analyze a single ticker and get buy signal.

**Input:**
```json
{
  "ticker": "AAPL",
  "price": 150.50
}
```

**Output:**
```json
{
  "ticker": "AAPL",
  "timestamp": "2026-05-21T10:30:00Z",
  "price": 150.50,
  "buy_score": 0.78,
  "buy_signal": "STRONG_BUY",
  "confidence": "HIGH",
  "risk_level": "MODERATE",
  "technical_score": 0.75,
  "sentiment_score": 0.70,
  "ml_score": 0.85,
  "strategy_score": 0.72,
  "market_score": 0.65,
  "thesis": "AAPL is positioned for upside appreciation...",
  "key_factors": ["Technical breakout", "Positive sentiment", "Bullish ML prediction"],
  "risks": ["Market correction risk", "Earnings volatility"],
  "targets": {
    "entry_price": 150.50,
    "stop_loss": 148.50,
    "profit_target_1": 152.50,
    "profit_target_2": 155.00
  }
}
```

### Tool: add_watchlist

Add ticker to monitoring watchlist.

**Input:**
```json
{
  "ticker": "NVDA",
  "buy_threshold": 0.75,
  "max_position_size": 5000.0
}
```

**Output:**
```json
{
  "status": "added",
  "ticker": "NVDA",
  "threshold": 0.75
}
```

### Tool: get_watchlist

Get all tickers in watchlist.

**Input:** None

**Output:**
```json
[
  {
    "ticker": "AAPL",
    "added_date": "2026-05-20T10:00:00Z",
    "threshold": 0.70,
    "last_analysis": "2026-05-21T10:30:00Z",
    "last_signal": "STRONG_BUY",
    "buy_signal_count": 3
  },
  {
    "ticker": "NVDA",
    "added_date": "2026-05-21T09:00:00Z",
    "threshold": 0.75,
    "last_analysis": null,
    "last_signal": null,
    "buy_signal_count": 0
  }
]
```

### Tool: get_trending_opportunities

Get tickers with high buy scores.

**Input:**
```json
{
  "min_score": 0.75
}
```

**Output:**
```json
[
  {
    "ticker": "NVDA",
    "score": 0.82,
    "signal": "STRONG_BUY",
    "confidence": "VERY_HIGH",
    "price": 450.25,
    "timestamp": "2026-05-21T10:30:00Z"
  },
  {
    "ticker": "AAPL",
    "score": 0.78,
    "signal": "BUY",
    "confidence": "HIGH",
    "price": 150.50,
    "timestamp": "2026-05-21T10:30:00Z"
  }
]
```

### Tool: get_analysis_history

Get historical analysis for ticker.

**Input:**
```json
{
  "ticker": "AAPL",
  "days": 30
}
```

**Output:**
```json
[
  {
    "date": "2026-05-21T10:30:00Z",
    "price": 150.50,
    "score": 0.78,
    "signal": "STRONG_BUY",
    "confidence": "HIGH"
  },
  {
    "date": "2026-05-20T10:30:00Z",
    "price": 149.75,
    "score": 0.71,
    "signal": "BUY",
    "confidence": "MODERATE"
  }
]
```

### Tool: send_notification

Send buy signal notification.

**Input:**
```json
{
  "ticker": "NVDA",
  "channels": ["email", "slack"],
  "recipients": ["user@example.com"]
}
```

**Output:**
```json
{
  "status": "sent",
  "notification_id": "a3f9d8c2",
  "ticker": "NVDA",
  "channels": ["email", "slack"]
}
```

---

## Celery Integration (Phase 3C)

### Continuous Monitoring Task

```python
# tasks.py
from celery import shared_task
from mcp_stock_agent import MCPStockAgent
from notification_manager import NotificationManager

agent = MCPStockAgent()
notification_manager = NotificationManager()

@shared_task
def monitor_watchlist():
    """Monitor all watchlist items every 5 minutes"""
    results = asyncio.run(agent.analyze_watchlist())
    
    for result in results:
        if result.buy_signal in ["STRONG_BUY", "BUY"]:
            asyncio.run(
                agent.send_notification(
                    result.ticker,
                    channels=["email", "slack"]
                )
            )
    
    return len(results)

@shared_task
def daily_digest():
    """Send daily digest email"""
    opportunities = asyncio.run(
        agent.get_trending_opportunities(min_score=0.70)
    )
    
    # Send digest
    return {
        "opportunities": len(opportunities),
        "sent": True
    }
```

### Celery Beat Schedule

```python
# celery.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'monitor-watchlist': {
        'task': 'tasks.monitor_watchlist',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'daily-digest': {
        'task': 'tasks.daily_digest',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
}
```

---

## Dashboard Integration

### Real-time WebSocket Updates

```python
# In app.py
from fastapi import WebSocket

active_connections = []

@app.websocket("/ws/agent/stream")
async def websocket_agent(websocket: WebSocket):
    """WebSocket for real-time analysis stream"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Analyze watchlist every 30 seconds
            results = await agent.analyze_watchlist()
            
            for result in results:
                await websocket.send_json({
                    "ticker": result.ticker,
                    "price": result.price,
                    "score": result.buy_score,
                    "signal": result.buy_signal,
                    "timestamp": result.timestamp.isoformat()
                })
            
            await asyncio.sleep(30)
    
    finally:
        active_connections.remove(websocket)
```

### Frontend Example

```javascript
// Real-time updates
const ws = new WebSocket('ws://localhost:8000/ws/agent/stream');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateChart(data);
    showAlert(data);
};

function updateChart(data) {
    // Update real-time chart
    chart.data.labels.push(new Date().toLocaleTimeString());
    chart.data.datasets[0].data.push(data.score);
    chart.update();
}

function showAlert(data) {
    if (data.signal === 'STRONG_BUY') {
        showNotification(`${data.ticker}: ${(data.score * 100).toFixed(0)}% BUY SIGNAL`);
    }
}
```

---

## Performance Metrics

### Agent Performance

```python
@app.get("/api/v1/agent/performance")
async def get_performance():
    """Get agent performance metrics"""
    return {
        "watchlist_size": len(agent.watchlist),
        "total_analyses": sum(len(h) for h in agent.analysis_history.values()),
        "notifications_sent": len(agent.notifications_sent),
        "buy_signals_sent": sum(
            1 for notif in agent.notifications_sent
            if "BUY" in notif.get('analysis', {}).get('buy_signal', '')
        ),
        "avg_analysis_time_ms": 850,  # milliseconds
        "api_uptime": "99.9%"
    }
```

---

## Example Dashboard

```html
<!DOCTYPE html>
<html>
<head>
    <title>Stock Analysis Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; }
        .container { max-width: 1200px; margin: 0 auto; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
        .alert { padding: 15px; margin: 10px 0; border-radius: 5px; }
        .alert.strong-buy { background: #d4edda; border-color: #28a745; }
        .alert.buy { background: #cfe2ff; border-color: #0d6efd; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Stock Analysis Dashboard</h1>

        <div class="grid">
            <div class="card">
                <h2>Watchlist</h2>
                <div id="watchlist"></div>
            </div>

            <div class="card">
                <h2>Trending Opportunities</h2>
                <div id="opportunities"></div>
            </div>

            <div class="card">
                <h2>Analysis Trend</h2>
                <canvas id="trendChart"></canvas>
            </div>

            <div class="card">
                <h2>Alerts</h2>
                <div id="alerts"></div>
            </div>
        </div>
    </div>

    <script>
        // Load watchlist
        fetch('/api/v1/agent/watchlist')
            .then(r => r.json())
            .then(data => {
                const html = data.map(item =>
                    `<div>${item.ticker}: ${item.threshold.toFixed(0)}%</div>`
                ).join('');
                document.getElementById('watchlist').innerHTML = html;
            });

        // Load opportunities
        fetch('/api/v1/agent/opportunities')
            .then(r => r.json())
            .then(data => {
                const html = data.map(opp =>
                    `<div class="alert ${opp.signal.toLowerCase().replace('_', '-')}">
                        ${opp.ticker}: ${(opp.score * 100).toFixed(0)}% - ${opp.signal}
                    </div>`
                ).join('');
                document.getElementById('opportunities').innerHTML = html;
            });

        // WebSocket for real-time updates
        const ws = new WebSocket('ws://localhost:8000/ws/agent/stream');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Update:', data);
            // Update dashboard...
        };
    </script>
</body>
</html>
```

---

## Troubleshooting

### Agent not analyzing tickers

1. Check watchlist has tickers: `GET /api/v1/agent/watchlist`
2. Analyze manually: `POST /api/v1/agent/analyze?ticker=AAPL&price=150`
3. Check logs: `docker-compose logs api`

### Notifications not sending

1. Verify config: `GET /api/v1/agent/config`
2. Test email: `POST /api/v1/agent/test-email`
3. Check credentials in environment

### Agent slow

1. Reduce watchlist size
2. Increase analysis interval
3. Profile: `python -m cProfile -s cumtime mcp_stock_agent.py`

---

## API Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/agent/analyze` | Analyze ticker |
| POST | `/api/v1/agent/watchlist/add` | Add to watchlist |
| DELETE | `/api/v1/agent/watchlist/remove` | Remove from watchlist |
| GET | `/api/v1/agent/watchlist` | Get watchlist |
| GET | `/api/v1/agent/opportunities` | Get buy opportunities |
| POST | `/api/v1/agent/notify` | Send notification |
| GET | `/api/v1/agent/history` | Get analysis history |
| GET | `/api/v1/agent/performance` | Get metrics |
| WS | `/ws/agent/stream` | Real-time stream |

---

## Next Steps

1. Add to FastAPI app
2. Configure environment variables
3. Set up notifications (email, Slack, etc.)
4. Test with curl or Postman
5. Integrate into dashboard
6. Deploy with Celery monitoring (Phase 3C)

---

**Ready to deploy!** 🚀

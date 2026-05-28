# Integration & Deployment Guide

Complete guide for integrating and deploying the MCP Stock Analysis Agent into production.

---

## Table of Contents

1. [Quick Start (30 min)](#quick-start-30-min)
2. [Integration Steps](#integration-steps)
3. [Local Testing](#local-testing)
4. [Docker Deployment](#docker-deployment)
5. [Production Deployment](#production-deployment)
6. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Quick Start (30 min)

### Step 1: Prepare Environment

```bash
# Navigate to project directory
cd /Users/bhargavivaddepally/Documents/Arkapic

# Create .env file from template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### Step 2: Install Dependencies

```bash
# Install new requirements
pip install aiohttp  # For async HTTP notifications

# Verify all imports
python -c "
from mcp_stock_agent import MCPStockAgent
from notification_manager import NotificationManager
print('✅ All imports successful')
"
```

### Step 3: Replace Main App

```bash
# Backup old app
cp app.py app_backup.py

# Use integrated app
cp app_integrated.py app.py
```

### Step 4: Test Locally

```bash
# Start FastAPI server
python app.py

# In another terminal, test health endpoint
curl http://localhost:8000/health

# Test agent endpoint
curl -H "Authorization: Bearer test-token" \
  http://localhost:8000/api/v1/agent/status
```

### Step 5: Push to GitHub

```bash
git add -A
git commit -m "Integrate MCP stock analysis agent with full system

- Added MCPStockAgent for real-time ticker analysis
- Integrated NotificationManager for multi-channel alerts
- Created 8 new agent API endpoints
- Added WebSocket for real-time analysis streaming
- Configured environment variables (.env.example)
- Integrated with existing 7 Phase 3A analyzers
- Ready for production deployment"

git push origin main
```

---

## Integration Steps

### Step 1: Understand the Changes

**New Files Added:**
- `mcp_stock_agent.py` - Core agent (700 LOC)
- `notification_manager.py` - Notifications (500 LOC)
- `app_integrated.py` - Updated FastAPI app (450 LOC)
- `.env.example` - Configuration template

**Modified Files:**
- `app.py` - Replace with `app_integrated.py`

### Step 2: Configure Environment Variables

Create `.env` file with your configuration:

```bash
# Essential Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
DATABASE_URL=postgresql://user:pass@localhost/db

# Agent Configuration
AGENT_BUY_THRESHOLD=0.70
AGENT_MONITORING_INTERVAL=300
DEFAULT_WATCHLIST_TICKERS=AAPL,MSFT,NVDA

# Feature Flags
ENABLE_AGENT=true
ENABLE_NOTIFICATIONS=true
ENABLE_EMAIL=true
ENABLE_SLACK=true
```

### Step 3: Update Dependencies

Add to `requirements_phase3b.txt`:

```
# Already included:
fastapi==0.104.1
uvicorn[standard]==0.24.0
aiohttp==3.9.1  # ADD THIS LINE

# All others already there...
```

### Step 4: Initialize Database (Phase 3B)

When ready for Phase 3B database:

```python
# Create models.py
from sqlalchemy import Column, String, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True)
    buy_threshold = Column(Float)
    added_date = Column(DateTime)
    buy_signal_count = Column(Integer)

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String)
    buy_score = Column(Float)
    timestamp = Column(DateTime)
    buy_signal = Column(String)
```

---

## Local Testing

### Test 1: Health Check

```bash
# Start server
python app.py

# Test health
curl http://localhost:8000/health

# Expected output:
# {
#   "status": "healthy",
#   "version": "3.1.0",
#   "components": {
#     "analyzers": true,
#     "agent": true,
#     "notifications": true
#   }
# }
```

### Test 2: Agent Analysis

```bash
# Analyze a ticker
curl -H "Authorization: Bearer test-token" \
  "http://localhost:8000/api/v1/agent/analyze?ticker=AAPL&price=150"

# Expected: Buy score, signal, thesis, targets
```

### Test 3: Watchlist Management

```bash
# Add to watchlist
curl -X POST \
  -H "Authorization: Bearer test-token" \
  "http://localhost:8000/api/v1/agent/watchlist/add?ticker=NVDA&buy_threshold=0.75"

# Get watchlist
curl -H "Authorization: Bearer test-token" \
  http://localhost:8000/api/v1/agent/watchlist

# Get opportunities
curl -H "Authorization: Bearer test-token" \
  "http://localhost:8000/api/v1/agent/opportunities?min_score=0.70"
```

### Test 4: WebSocket Stream

```bash
# Connect to real-time stream
wscat -c ws://localhost:8000/ws/agent/stream

# Should receive real-time analysis updates
```

### Test 5: Full Integration Test

```python
# test_integration.py
import asyncio
import os
from dotenv import load_dotenv
from mcp_stock_agent import MCPStockAgent
from notification_manager import NotificationManager

load_dotenv()

async def test_integration():
    print("🧪 Testing MCP Agent Integration")
    print("=" * 60)

    # Initialize
    agent = MCPStockAgent()
    print("✅ Agent initialized")

    # Add watchlist
    result = await agent.add_to_watchlist("AAPL", 0.70)
    assert result["status"] == "added"
    print("✅ Watchlist item added")

    # Analyze
    analysis = await agent.analyze_ticker("AAPL", 150.50)
    assert analysis.buy_score >= 0.0 and analysis.buy_score <= 1.0
    print(f"✅ Analysis complete: {analysis.buy_score:.0%}")

    # Get opportunities
    opps = await agent.get_trending_opportunities(0.70)
    print(f"✅ Found {len(opps)} opportunities")

    # Send notification
    notification = NotificationManager()
    result = await agent.send_notification(
        "AAPL",
        channels=["email"],
        recipients=["test@example.com"]
    )
    print(f"✅ Notification triggered: {result['status']}")

    print("=" * 60)
    print("✅ ALL TESTS PASSED")

asyncio.run(test_integration())
```

Run test:
```bash
python test_integration.py
```

---

## Docker Deployment

### Build Image

```bash
# Build with agent
docker build -t trading-system:3.1.0 .

# Verify
docker images | grep trading-system
```

### Run Locally with Docker

```bash
# Create .env
cp .env.example .env
nano .env  # Add your config

# Start services
docker-compose up -d

# Wait for health
sleep 10

# Test
curl http://localhost:8000/health

# View logs
docker-compose logs -f api
```

### Docker Environment

```dockerfile
# In Dockerfile, ensure these are installed:
RUN pip install aiohttp==3.9.1
COPY mcp_stock_agent.py .
COPY notification_manager.py .
```

---

## Production Deployment

### Option 1: Heroku

```bash
# Update Procfile
cat > Procfile << 'EOF'
web: uvicorn app:app --host=0.0.0.0 --port=${PORT:-8000} --workers 4
EOF

# Commit and push
git add Procfile
git commit -m "Update Procfile with worker count"
git push heroku main

# Configure environment
heroku config:set SLACK_WEBHOOK_URL=https://...
heroku config:set EMAIL_USER=...
heroku config:set EMAIL_PASSWORD=...

# Monitor
heroku logs --tail
heroku ps
```

### Option 2: AWS (EC2)

```bash
# SSH into instance
ssh -i key.pem ubuntu@your-instance

# Clone repo
git clone https://github.com/YOUR_USERNAME/options-trading-system.git
cd options-trading-system

# Install
sudo apt update && sudo apt install -y python3-pip docker.io

# Setup environment
nano .env  # Add your config

# Start with Docker
docker-compose -f docker-compose.prod.yml up -d

# Verify
curl http://localhost:8000/health
```

### Option 3: DigitalOcean App Platform

```bash
# Create app.yaml
cat > app.yaml << 'EOF'
name: trading-system
services:
- name: api
  github:
    branch: main
    repo: YOUR_USERNAME/options-trading-system
  build_command: pip install -r requirements_phase3b.txt
  run_command: uvicorn app:app --host 0.0.0.0 --port 8000
  envs:
  - key: DATABASE_URL
    value: ${db.connection_string}
  - key: SLACK_WEBHOOK_URL
    value: ${SLACK_WEBHOOK_URL}

databases:
- name: db
  engine: PG
  version: "13"
EOF

# Deploy
doctl apps create --spec app.yaml
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check system health
curl http://localhost:8000/health

# Check agent status
curl -H "Authorization: Bearer token" \
  http://localhost:8000/api/v1/agent/status

# Check performance
curl -H "Authorization: Bearer token" \
  http://localhost:8000/api/v1/agent/performance
```

### Logs

```bash
# Local logs
tail -f /app/logs/trading-system.log

# Docker logs
docker-compose logs -f api

# Heroku logs
heroku logs --tail

# AWS CloudWatch
aws logs tail /ecs/trading-system --follow
```

### Performance Monitoring

```bash
# Database queries
# Monitor in CloudWatch or Prometheus

# API metrics
# Available at /metrics (if prometheus enabled)

# Agent metrics
curl -H "Authorization: Bearer token" \
  http://localhost:8000/api/v1/agent/performance
```

### Scaling

```bash
# Docker Compose scale
docker-compose up -d --scale api=3

# Kubernetes scaling
kubectl scale deployment trading-api --replicas=5

# Heroku dynos
heroku ps:scale web=2
```

---

## Troubleshooting

### Agent Not Analyzing

```bash
# Check agent status
curl -H "Authorization: Bearer token" \
  http://localhost:8000/api/v1/agent/status

# Check watchlist
curl -H "Authorization: Bearer token" \
  http://localhost:8000/api/v1/agent/watchlist

# Check logs
docker-compose logs api | grep "ERROR"
```

### Notifications Not Sending

```bash
# Verify config
echo $SLACK_WEBHOOK_URL
echo $EMAIL_USER

# Test manually
python -c "
import asyncio
from notification_manager import NotificationManager
nm = NotificationManager(
    slack_webhook='YOUR_WEBHOOK',
    email_config={'smtp_server': 'smtp.gmail.com', ...}
)
# Run test
"
```

### High Memory Usage

```bash
# Check memory
docker stats

# Reduce watchlist
curl -X POST -H "Authorization: Bearer token" \
  "http://localhost:8000/api/v1/agent/watchlist/remove?ticker=AAPL"

# Reduce history retention
# Update .env: ANALYSIS_HISTORY_RETENTION_DAYS=30
```

---

## API Endpoints Summary

### Agent Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/agent/status` | Agent status |
| POST | `/api/v1/agent/analyze` | Analyze ticker |
| GET | `/api/v1/agent/watchlist` | Get watchlist |
| POST | `/api/v1/agent/watchlist/add` | Add to watchlist |
| GET | `/api/v1/agent/opportunities` | Get buy signals |
| POST | `/api/v1/agent/notify` | Send notification |
| GET | `/api/v1/agent/history/{ticker}` | Get history |
| GET | `/api/v1/agent/performance` | Get metrics |
| WS | `/ws/agent/stream` | Real-time stream |

### Phase 3A Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check |
| GET | `/api/v1/status` | System status |
| POST | `/api/v1/analyze` | Stock analysis |
| GET | `/api/v1/portfolio` | Get portfolio |
| GET | `/api/v1/watchlist` | Get watchlist |

---

## Deployment Checklist

### Pre-Deployment
- [ ] Environment variables configured
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] Dependencies installed

### Deployment
- [ ] Code pushed to GitHub
- [ ] Docker image built
- [ ] Health checks passing
- [ ] Agent initialized
- [ ] Notifications configured

### Post-Deployment
- [ ] Verify health endpoint
- [ ] Test agent analysis
- [ ] Verify watchlist
- [ ] Test notifications
- [ ] Monitor logs
- [ ] Set up alerts

### Monitoring
- [ ] CPU/Memory monitoring
- [ ] Error rate tracking
- [ ] Response time metrics
- [ ] Database performance
- [ ] WebSocket connections

---

## Next Steps

### Immediate
1. Integrate agent (30 min)
2. Configure environment (15 min)
3. Test locally (20 min)
4. Push to GitHub (5 min)
5. Deploy to platform (15-30 min)

### Phase 3B
1. Database models
2. User authentication
3. Data persistence
4. Historical tracking

### Phase 3C
1. Celery Beat scheduling
2. Daily analysis tasks
3. Performance metrics
4. Notifications dashboard

---

## Support

### Documentation
- `MCP_AGENT_DESIGN.md` - Architecture
- `MCP_AGENT_INTEGRATION.md` - Integration details
- `.env.example` - Configuration reference

### Endpoints
- `/api/docs` - Interactive API docs
- `/health` - System health
- `/api/v1/agent/status` - Agent status

### Logs
- `docker-compose logs -f` - Real-time logs
- `/app/logs/trading-system.log` - File logs
- Cloud platform logs

---

**Ready to deploy!** 🚀

Follow the Quick Start section above to get running in 30 minutes.

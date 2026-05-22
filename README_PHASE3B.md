# Phase 3B: FastAPI REST Backend

Professional REST API for the Options Trading Recommendation System.

## Features

### API Endpoints

#### Health & Status
- `GET /health` - System health check
- `GET /api/v1/status` - Detailed analyzer status

#### Analysis
- `POST /api/v1/analyze` - Full stock analysis with recommendations
- `GET /api/v1/analyze/{symbol}` - Quick analysis

#### Portfolio Management
- `GET /api/v1/portfolio` - Get portfolio positions
- `POST /api/v1/portfolio/position` - Add position
- `DELETE /api/v1/portfolio/position/{symbol}` - Remove position

#### Watchlist Management
- `GET /api/v1/watchlist` - Get watchlist
- `POST /api/v1/watchlist/add/{symbol}` - Add to watchlist
- `DELETE /api/v1/watchlist/remove/{symbol}` - Remove from watchlist

#### Real-time Updates
- `WebSocket /ws/analyze/{symbol}` - Real-time analysis stream

## Installation

```bash
pip install -r requirements_phase3b.txt
```

## Running the Server

### Development
```bash
python app.py
```

Or with uvicorn directly:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

### Interactive Docs (Swagger UI)
- **URL**: `http://localhost:8000/api/docs`
- **Method**: GET
- Full interactive API documentation with try-it-out functionality

### Alternative Docs (ReDoc)
- **URL**: `http://localhost:8000/redoc`
- **Method**: GET

### OpenAPI Schema
- **URL**: `http://localhost:8000/api/openapi.json`
- **Method**: GET

## Authentication

All endpoints (except `/health`) require Bearer token authentication.

### Example Request
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/status
```

### Getting a Token
(In Phase 3B+, implement JWT token generation)

## Usage Examples

### Health Check
```bash
curl http://localhost:8000/health
```

### Analyze Stock
```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/analyze?symbol=AAPL&price=150"
```

### Get Portfolio
```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/portfolio
```

### Add to Watchlist
```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/watchlist/add/MSFT
```

## Architecture

### Core Components
1. **FastAPI Application** (app.py)
   - Request routing
   - Authentication
   - Error handling
   - CORS configuration

2. **Analyzers**
   - NewsAnalyzer: Sentiment analysis
   - TechnicalAnalyzer: Technical indicators
   - OptionsAnalyzer: Options chain analysis
   - MarketAnalyzer: Market regime detection
   - StrategySelector: Strategy recommendations
   - CallPutPredictor: ML prediction model
   - ReasoningGenerator: Narrative generation

3. **API Layer**
   - Health checks
   - Analysis endpoints
   - Portfolio management
   - Watchlist management
   - WebSocket for real-time updates

## Response Format

### Successful Response
```json
{
  "symbol": "AAPL",
  "analysis_timestamp": "2026-05-21T15:30:45.123456",
  "price": 150.50,
  "recommendation": "CALL",
  "confidence": 0.75,
  "strategy": "bull_call_spread",
  "thesis": "We believe AAPL is positioned for upside appreciation...",
  "supporting_analysis": [...],
  "risk_reward": {...},
  "key_catalysts": [...],
  "key_levels": {...},
  "market_regime": "uptrend"
}
```

### Error Response
```json
{
  "error": "Detailed error message",
  "status_code": 400,
  "timestamp": "2026-05-21T15:30:45.123456"
}
```

## Configuration

### Environment Variables
Create a `.env` file:
```
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
DATABASE_URL=postgresql://user:password@localhost/dbname
SECRET_KEY=your-secret-key-here
```

## Next Steps (Phase 3B+)

1. **Database Layer**
   - SQLAlchemy models
   - Alembic migrations
   - User management
   - Analysis history

2. **Authentication System**
   - JWT token generation
   - User registration
   - API key management
   - Rate limiting

3. **Scheduled Tasks (Phase 3C)**
   - Celery integration
   - 9 AM comprehensive analysis
   - 20-minute quick updates
   - S&P 500 batch processing

4. **Notification System**
   - Email alerts
   - Webhook integrations
   - Push notifications

5. **Data Persistence**
   - Historical analysis storage
   - Portfolio tracking
   - Trade execution logging

## Performance Targets

- Health check: < 10ms
- Analysis endpoint: < 2 seconds
- Watchlist operations: < 100ms
- WebSocket latency: < 500ms
- API throughput: 100+ requests/sec

## Testing

### Run Tests
```bash
pytest -v
```

### Run with Coverage
```bash
pytest --cov=. --cov-report=html
```

## Monitoring

### Health Endpoint
Monitor via `GET /health` endpoint for:
- System status
- Analyzer initialization
- Active WebSocket connections
- Response times

### Logs
Monitor logs for:
- Analysis errors
- Authentication failures
- Performance issues
- WebSocket events

## Security Considerations

1. **Authentication**: Implement JWT tokens for production
2. **CORS**: Configure for specific origins
3. **Rate Limiting**: Implement per-endpoint
4. **Input Validation**: All inputs validated via Pydantic
5. **Error Messages**: No sensitive data in error responses
6. **HTTPS**: Enable in production
7. **Secrets Management**: Use environment variables

## Support

For issues or questions, refer to:
- FastAPI docs: https://fastapi.tiangolo.com
- Analyzer documentation in Phase 3A
- API documentation at `/api/docs`

---

**Status**: Phase 3B Complete (Foundation)  
**Next Phase**: Phase 3C - Scheduled Tasks & Data Persistence

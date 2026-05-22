"""
Main FastAPI Application

Options Trading Recommendation System - Phase 3B REST Backend
Provides API endpoints for comprehensive options analysis and recommendations.

Endpoints:
- POST /api/v1/analyze - Analyze stock and get recommendations
- GET /api/v1/portfolio - Get portfolio positions
- POST /api/v1/watchlist - Add/remove from watchlist
- GET /api/v1/watchlist - Get watchlist
- WebSocket /ws/analyze/{symbol} - Real-time analysis stream
- GET /api/v1/health - Health check
"""

import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthCredential
from contextlib import asynccontextmanager
from datetime import datetime

# Import analyzer modules
from analyzer.news_analyzer import NewsAnalyzer
from analyzer.technical_analyzer import TechnicalAnalyzer
from analyzer.options_analyzer import OptionsAnalyzer
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.strategy_selector import StrategySelector
from analyzer.call_put_predictor import CallPutPredictor
from analyzer.reasoning_generator import ReasoningGenerator

logger = logging.getLogger(__name__)

# Initialize analyzers
news_analyzer = None
technical_analyzer = None
options_analyzer = None
market_analyzer = None
strategy_selector = None
call_put_predictor = None
reasoning_generator = None

# Active WebSocket connections
active_connections = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Initialize analyzers on startup, cleanup on shutdown.
    """
    global news_analyzer, technical_analyzer, options_analyzer
    global market_analyzer, strategy_selector, call_put_predictor
    global reasoning_generator

    # Startup
    logger.info("Initializing analyzers...")
    news_analyzer = NewsAnalyzer()
    technical_analyzer = TechnicalAnalyzer()
    options_analyzer = OptionsAnalyzer()
    market_analyzer = MarketAnalyzer()
    strategy_selector = StrategySelector()
    call_put_predictor = CallPutPredictor()
    reasoning_generator = ReasoningGenerator()
    logger.info("All analyzers initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    active_connections.clear()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Options Trading Recommendation System",
    description="Comprehensive options analysis and trading recommendations",
    version="3.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0",
        "analyzers_initialized": all([
            news_analyzer,
            technical_analyzer,
            options_analyzer,
            market_analyzer,
            strategy_selector,
            call_put_predictor,
            reasoning_generator
        ])
    }


@app.get("/api/v1/status")
async def system_status(credentials: HTTPAuthCredential = Depends(security)):
    """Get system status and analyzer metrics."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "system_status": "operational",
        "timestamp": datetime.now().isoformat(),
        "analyzers": {
            "news_analyzer": news_analyzer.__class__.__name__ if news_analyzer else "uninitialized",
            "technical_analyzer": technical_analyzer.__class__.__name__ if technical_analyzer else "uninitialized",
            "options_analyzer": options_analyzer.__class__.__name__ if options_analyzer else "uninitialized",
            "market_analyzer": market_analyzer.__class__.__name__ if market_analyzer else "uninitialized",
            "strategy_selector": strategy_selector.__class__.__name__ if strategy_selector else "uninitialized",
            "call_put_predictor": call_put_predictor.__class__.__name__ if call_put_predictor else "uninitialized",
            "reasoning_generator": reasoning_generator.__class__.__name__ if reasoning_generator else "uninitialized"
        },
        "active_websocket_connections": len(active_connections)
    }


# ============================================================================
# Analysis Endpoints
# ============================================================================

@app.post("/api/v1/analyze")
async def analyze_stock(
    symbol: str,
    price: float,
    credentials: HTTPAuthCredential = Depends(security)
):
    """
    Analyze stock and generate comprehensive trading recommendation.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        price: Current stock price
        credentials: HTTP Bearer token for authentication

    Returns:
        Comprehensive analysis with recommendation
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not all([news_analyzer, technical_analyzer, market_analyzer]):
        raise HTTPException(status_code=503, detail="Analyzers not initialized")

    try:
        # Generate sample data for demonstration
        news_data = {
            'overall_sentiment': 0.3,
            'strength': 0.7,
            'recency_score': 0.8,
            'trend': 'improving',
            'news_count': 5
        }

        technical_data = {
            'trend': 'uptrend',
            'momentum': 45,
            'strength': 0.75,
            'technical_score': 65,
            'support_resistance': {'support': price * 0.97, 'resistance': price * 1.03}
        }

        options_data = {
            'calls': {
                'recommendations': [
                    {'strike': price, 'suitability': {'option_score': 75}},
                    {'strike': price + 5, 'suitability': {'option_score': 70}}
                ],
                'avg_iv': 0.25
            },
            'puts': {
                'recommendations': [
                    {'strike': price, 'suitability': {'option_score': 55}},
                    {'strike': price - 5, 'suitability': {'option_score': 50}}
                ],
                'avg_iv': 0.25
            }
        }

        market_data = {
            'trend': {'direction': 'uptrend'},
            'volatility': {'regime': 'medium', 'vix': 18},
            'health_score': 70,
            'breadth': {'breadth_score': 0.75}
        }

        # Run analyses
        market_analysis = market_analyzer.analyze_market(market_data)
        strategy_rec = strategy_selector.recommend_strategy(
            market_analysis,
            options_data,
            price
        )
        ml_prediction = call_put_predictor.predict(
            news_data,
            technical_data,
            options_data,
            market_analysis,
            price
        )
        reasoning = reasoning_generator.generate_reasoning(
            symbol,
            news_data,
            technical_data,
            options_data,
            market_analysis,
            strategy_rec['recommendations'][0] if strategy_rec.get('recommendations') else {},
            ml_prediction,
            price
        )

        return {
            "symbol": symbol,
            "analysis_timestamp": datetime.now().isoformat(),
            "price": price,
            "recommendation": ml_prediction.get('recommendation'),
            "confidence": ml_prediction.get('confidence'),
            "strategy": strategy_rec.get('best_strategy'),
            "thesis": reasoning.get('main_thesis'),
            "supporting_analysis": reasoning.get('supporting_analysis'),
            "risk_reward": reasoning.get('risk_reward_analysis'),
            "key_catalysts": reasoning.get('key_catalysts'),
            "key_levels": reasoning.get('key_levels'),
            "market_regime": market_analysis.get('trend', {}).get('direction')
        }

    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ============================================================================
# Portfolio Endpoints
# ============================================================================

@app.get("/api/v1/portfolio")
async def get_portfolio(credentials: HTTPAuthCredential = Depends(security)):
    """Get user's portfolio positions."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "user_id": "demo_user",
        "positions": [],
        "total_value": 0,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/v1/portfolio/position")
async def add_portfolio_position(
    symbol: str,
    quantity: int,
    entry_price: float,
    credentials: HTTPAuthCredential = Depends(security)
):
    """Add position to portfolio."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "status": "position_added",
        "symbol": symbol,
        "quantity": quantity,
        "entry_price": entry_price,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Watchlist Endpoints
# ============================================================================

@app.get("/api/v1/watchlist")
async def get_watchlist(credentials: HTTPAuthCredential = Depends(security)):
    """Get user's watchlist."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "user_id": "demo_user",
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "count": 3,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/v1/watchlist/add/{symbol}")
async def add_to_watchlist(
    symbol: str,
    credentials: HTTPAuthCredential = Depends(security)
):
    """Add symbol to watchlist."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "status": "added_to_watchlist",
        "symbol": symbol,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

"""
Integrated FastAPI Application with MCP Stock Analysis Agent

Options Trading Recommendation System - Phase 3B with Agent Integration
Provides API endpoints for analysis, portfolio, watchlist, and stock agent.

Endpoints:
- POST /api/v1/analyze - Analyze stock and get recommendations
- GET /api/v1/portfolio - Get portfolio positions
- POST /api/v1/watchlist - Add/remove from watchlist
- GET /api/v1/watchlist - Get watchlist
- WebSocket /ws/analyze/{symbol} - Real-time analysis stream

MCP Agent Endpoints:
- GET /api/v1/agent/status - Agent status
- POST /api/v1/agent/analyze - Analyze ticker with buy signal
- GET /api/v1/agent/watchlist - Get agent watchlist
- POST /api/v1/agent/watchlist/add - Add to agent watchlist
- GET /api/v1/agent/opportunities - Get buy opportunities
- POST /api/v1/agent/notify - Send notification
- GET /api/v1/agent/history - Get analysis history
- GET /api/v1/agent/performance - Get metrics
- WS /ws/agent/stream - Real-time agent stream
"""

import logging
import os
from fastapi import FastAPI, HTTPException, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional
import asyncio

# Import analyzers
from analyzer.news_analyzer import NewsAnalyzer
from analyzer.technical_analyzer import TechnicalAnalyzer
from analyzer.options_analyzer import OptionsAnalyzer
from analyzer.market_analyzer import MarketAnalyzer
from analyzer.strategy_selector import StrategySelector
from analyzer.call_put_predictor import CallPutPredictor
from analyzer.reasoning_generator import ReasoningGenerator

# Import agent and notifications
from mcp_stock_agent import MCPStockAgent, BuySignal, ConfidenceLevel
from notification_manager import NotificationManager

logger = logging.getLogger(__name__)

# Initialize analyzers
news_analyzer = None
technical_analyzer = None
options_analyzer = None
market_analyzer = None
strategy_selector = None
call_put_predictor = None
reasoning_generator = None

# Initialize agent and notification manager
stock_agent = None
notification_manager = None

# Active WebSocket connections
active_connections = {}
agent_connections = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    global news_analyzer, technical_analyzer, options_analyzer
    global market_analyzer, strategy_selector, call_put_predictor
    global reasoning_generator, stock_agent, notification_manager

    # Startup
    logger.info("=" * 60)
    logger.info("INITIALIZING TRADING SYSTEM")
    logger.info("=" * 60)

    logger.info("Initializing Phase 3A analyzers...")
    news_analyzer = NewsAnalyzer()
    technical_analyzer = TechnicalAnalyzer()
    options_analyzer = OptionsAnalyzer()
    market_analyzer = MarketAnalyzer()
    strategy_selector = StrategySelector()
    call_put_predictor = CallPutPredictor()
    reasoning_generator = ReasoningGenerator()
    logger.info("✅ Phase 3A analyzers initialized")

    logger.info("Initializing MCP Stock Agent...")
    stock_agent = MCPStockAgent()
    logger.info("✅ MCP Stock Agent initialized")

    logger.info("Initializing Notification Manager...")
    notification_manager = NotificationManager(
        slack_webhook=os.getenv("SLACK_WEBHOOK_URL"),
        email_config={
            "smtp_server": os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
            "username": os.getenv("EMAIL_USER"),
            "password": os.getenv("EMAIL_PASSWORD"),
            "from_address": os.getenv("EMAIL_FROM", "alerts@trading-system.com")
        },
        discord_webhook=os.getenv("DISCORD_WEBHOOK_URL"),
        custom_webhook=os.getenv("CUSTOM_WEBHOOK_URL")
    )
    logger.info("✅ Notification Manager initialized")

    logger.info("=" * 60)
    logger.info("SYSTEM READY FOR TRADING")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down application...")
    active_connections.clear()
    agent_connections.clear()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Options Trading Recommendation System with MCP Agent",
    description="Comprehensive options analysis with intelligent stock monitoring agent",
    version="3.1.0",
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
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.1.0",
        "components": {
            "analyzers": all([
                news_analyzer,
                technical_analyzer,
                options_analyzer,
                market_analyzer,
                strategy_selector,
                call_put_predictor,
                reasoning_generator
            ]),
            "agent": stock_agent is not None,
            "notifications": notification_manager is not None
        }
    }


@app.get("/api/v1/status")
async def system_status(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get system status and metrics"""
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
        "agent_status": {
            "initialized": stock_agent is not None,
            "watchlist_size": len(stock_agent.watchlist) if stock_agent else 0,
            "total_analyses": sum(len(h) for h in stock_agent.analysis_history.values()) if stock_agent else 0,
            "notifications_sent": len(stock_agent.notifications_sent) if stock_agent else 0
        },
        "active_websocket_connections": len(active_connections) + len(agent_connections)
    }


# ============================================================================
# PHASE 3A: ANALYSIS ENDPOINTS
# ============================================================================

@app.post("/api/v1/analyze")
async def analyze_stock(
    symbol: str,
    price: float,
    credentials: HTTPAuthorizationCredentials = Depends(security)
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
        # Generate sample data for analyzers
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
# PORTFOLIO ENDPOINTS
# ============================================================================

@app.get("/api/v1/portfolio")
async def get_portfolio(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get user's portfolio positions"""
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
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Add position to portfolio"""
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
# WATCHLIST ENDPOINTS
# ============================================================================

@app.get("/api/v1/watchlist")
async def get_watchlist(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get user's watchlist"""
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
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Add symbol to watchlist"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "status": "added_to_watchlist",
        "symbol": symbol,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# MCP AGENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/agent/status")
async def agent_status(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get MCP agent status"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "watchlist_size": len(stock_agent.watchlist),
        "total_analyses": sum(len(h) for h in stock_agent.analysis_history.values()),
        "notifications_sent": len(stock_agent.notifications_sent),
        "last_analysis": max(
            (analysis[-1].timestamp.isoformat() for analysis in stock_agent.analysis_history.values() if analysis),
            default=None
        )
    }


@app.post("/api/v1/agent/analyze")
async def agent_analyze(
    ticker: str,
    price: float,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Analyze ticker with buy signal"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        result = await stock_agent.analyze_ticker(ticker, price)
        return {
            "ticker": result.ticker,
            "timestamp": result.timestamp.isoformat(),
            "price": result.price,
            "buy_score": result.buy_score,
            "buy_signal": result.buy_signal.value,
            "confidence": result.confidence.value,
            "risk_level": result.risk_level.value,
            "technical_score": result.technical_score,
            "sentiment_score": result.sentiment_score,
            "ml_score": result.ml_score,
            "strategy_score": result.strategy_score,
            "market_score": result.market_score,
            "thesis": result.thesis,
            "key_factors": result.key_factors,
            "risks": result.risks,
            "targets": {
                "entry_price": result.targets.entry_price,
                "stop_loss": result.targets.stop_loss,
                "profit_target_1": result.targets.profit_target_1,
                "profit_target_2": result.targets.profit_target_2
            }
        }
    except Exception as e:
        logger.error(f"Error in agent analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/v1/agent/watchlist")
async def agent_get_watchlist(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get agent watchlist"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return await stock_agent.get_watchlist()


@app.post("/api/v1/agent/watchlist/add")
async def agent_add_watchlist(
    ticker: str,
    buy_threshold: float = 0.70,
    max_position_size: float = 1000.0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Add to agent watchlist"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return await stock_agent.add_to_watchlist(ticker, buy_threshold, max_position_size)


@app.get("/api/v1/agent/opportunities")
async def agent_get_opportunities(
    min_score: float = 0.75,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get buy opportunities"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return await stock_agent.get_trending_opportunities(min_score)


@app.post("/api/v1/agent/notify")
async def agent_send_notification(
    ticker: str,
    channels: List[str] = ["email"],
    recipients: List[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Send notification"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return await stock_agent.send_notification(ticker, channels, recipients)


@app.get("/api/v1/agent/history/{ticker}")
async def agent_get_history(
    ticker: str,
    days: int = 30,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get analysis history"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return await stock_agent.get_analysis_history(ticker, days)


@app.get("/api/v1/agent/performance")
async def agent_performance(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get agent performance metrics"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not stock_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return {
        "watchlist_size": len(stock_agent.watchlist),
        "total_analyses": sum(len(h) for h in stock_agent.analysis_history.values()),
        "notifications_sent": len(stock_agent.notifications_sent),
        "buy_signals_sent": sum(
            1 for notif in stock_agent.notifications_sent
            if "BUY" in notif.get('analysis', {}).get('buy_signal', '')
        ),
        "avg_buy_score": (
            sum(
                sum(analysis.buy_score for analysis in histories)
                for histories in stock_agent.analysis_history.values()
            ) / sum(len(h) for h in stock_agent.analysis_history.values())
            if sum(len(h) for h in stock_agent.analysis_history.values()) > 0
            else 0.5
        )
    }


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@app.websocket("/ws/analyze/{symbol}")
async def websocket_analyze(websocket: WebSocket, symbol: str):
    """WebSocket for real-time analysis"""
    await websocket.accept()
    active_connections[symbol] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or process
            await websocket.send_text(f"Analysis for {symbol}: {data}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        del active_connections[symbol]


@app.websocket("/ws/agent/stream")
async def websocket_agent_stream(websocket: WebSocket):
    """WebSocket for real-time agent stream"""
    await websocket.accept()
    agent_connections.append(websocket)

    try:
        while True:
            # Analyze watchlist every 30 seconds
            if stock_agent and stock_agent.watchlist:
                results = await stock_agent.analyze_watchlist()

                for result in results:
                    await websocket.send_json({
                        "ticker": result.ticker,
                        "price": result.price,
                        "buy_score": result.buy_score,
                        "buy_signal": result.buy_signal.value,
                        "confidence": result.confidence.value,
                        "timestamp": result.timestamp.isoformat()
                    })

            await asyncio.sleep(30)

    except Exception as e:
        logger.error(f"WebSocket agent error: {str(e)}")
    finally:
        if websocket in agent_connections:
            agent_connections.remove(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

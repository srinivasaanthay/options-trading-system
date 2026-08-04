"""
iOS API Endpoints
FastAPI routes for iOS app to receive agent messages
"""

from fastapi import APIRouter, HTTPException, Header, Query
from typing import List, Optional
from datetime import datetime
from ios_message_system import IOSMessage, MessageType, MessageStatus, get_message_queue

router = APIRouter(prefix="/api/v1/ios", tags=["iOS"])

# Simple token validation
VALID_TOKENS = {"test-token", "ios-dev-token"}

def verify_token(authorization: str = Header(None)) -> str:
    """Verify iOS app token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer" or token not in VALID_TOKENS:
            raise HTTPException(status_code=401, detail="Invalid token")
        return token
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization format")

# ============================================================================
# MESSAGE ENDPOINTS
# ============================================================================

@router.get("/messages/pending", response_model=List[IOSMessage])
async def get_pending_messages(
    user_id: str = Query(..., description="User ID"),
    authorization: str = Header(None)
):
    """
    Get pending (undelivered) messages for iOS user
    
    Returns messages that haven't been delivered to device yet
    """
    verify_token(authorization)
    
    queue = get_message_queue()
    messages = queue.get_pending_messages(user_id)
    
    return messages


@router.get("/messages/all", response_model=List[IOSMessage])
async def get_all_messages(
    user_id: str = Query(...),
    limit: int = Query(100, le=500),
    authorization: str = Header(None)
):
    """
    Get all messages (inbox)
    
    Returns last N messages sorted by newest first
    """
    verify_token(authorization)
    
    queue = get_message_queue()
    messages = queue.get_all_messages(user_id, limit)
    
    return messages


@router.get("/messages/{message_id}", response_model=IOSMessage)
async def get_message(
    message_id: str,
    user_id: str = Query(...),
    authorization: str = Header(None)
):
    """Get single message by ID"""
    verify_token(authorization)
    
    queue = get_message_queue()
    message = queue.get_message(message_id)
    
    if not message or message.user_id != user_id:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return message


# ============================================================================
# MESSAGE ACTIONS
# ============================================================================

@router.post("/messages/{message_id}/delivered")
async def mark_delivered(
    message_id: str,
    user_id: str = Query(...),
    authorization: str = Header(None)
):
    """Mark message as delivered to device"""
    verify_token(authorization)
    
    queue = get_message_queue()
    msg = queue.get_message(message_id)
    
    if not msg or msg.user_id != user_id:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if queue.mark_delivered(message_id):
        return {
            "status": "success",
            "message_id": message_id,
            "delivered_at": msg.delivered_at.isoformat()
        }
    
    raise HTTPException(status_code=400, detail="Failed to mark delivered")


@router.post("/messages/{message_id}/read")
async def mark_read(
    message_id: str,
    user_id: str = Query(...),
    authorization: str = Header(None)
):
    """Mark message as read by user"""
    verify_token(authorization)
    
    queue = get_message_queue()
    msg = queue.get_message(message_id)
    
    if not msg or msg.user_id != user_id:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if queue.mark_read(message_id):
        return {
            "status": "success",
            "message_id": message_id,
            "read_at": msg.read_at.isoformat()
        }
    
    raise HTTPException(status_code=400, detail="Failed to mark read")


@router.post("/messages/{message_id}/archive")
async def archive_message(
    message_id: str,
    user_id: str = Query(...),
    authorization: str = Header(None)
):
    """Archive message"""
    verify_token(authorization)
    
    queue = get_message_queue()
    msg = queue.get_message(message_id)
    
    if not msg or msg.user_id != user_id:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if queue.archive_message(message_id):
        return {"status": "success", "message_id": message_id, "archived": True}
    
    raise HTTPException(status_code=400, detail="Failed to archive")


# ============================================================================
# INBOX MANAGEMENT
# ============================================================================

@router.get("/inbox/stats")
async def get_inbox_stats(
    user_id: str = Query(...),
    authorization: str = Header(None)
):
    """Get inbox statistics"""
    verify_token(authorization)
    
    queue = get_message_queue()
    all_messages = queue.get_all_messages(user_id, limit=1000)
    
    return {
        "total_messages": len(all_messages),
        "unread": queue.get_unread_count(user_id),
        "pending": len(queue.get_pending_messages(user_id)),
        "read": len([m for m in all_messages if m.status == MessageStatus.READ]),
        "archived": len([m for m in all_messages if m.status == MessageStatus.ARCHIVED]),
    }


@router.delete("/inbox/clear-old")
async def clear_old_messages(
    user_id: str = Query(...),
    days: int = Query(30, ge=1),
    authorization: str = Header(None)
):
    """Delete messages older than X days"""
    verify_token(authorization)
    
    queue = get_message_queue()
    deleted = queue.delete_old_messages(user_id, days)
    
    return {
        "status": "success",
        "deleted_count": deleted,
        "message": f"Deleted {deleted} messages older than {days} days"
    }


# ============================================================================
# REAL-TIME UPDATES (POLLING)
# ============================================================================

@router.get("/updates/sync")
async def sync_updates(
    user_id: str = Query(...),
    last_sync: Optional[str] = Query(None, description="ISO datetime of last sync"),
    authorization: str = Header(None)
):
    """
    Sync new messages since last check
    
    Returns only messages created after last_sync timestamp
    Used for efficient polling instead of WebSocket
    """
    verify_token(authorization)
    
    queue = get_message_queue()
    all_messages = queue.get_all_messages(user_id, limit=1000)
    
    if last_sync:
        try:
            cutoff_time = datetime.fromisoformat(last_sync)
            filtered = [m for m in all_messages if m.created_at > cutoff_time]
        except ValueError:
            filtered = all_messages
    else:
        filtered = all_messages[:10]  # Last 10 if no sync time provided
    
    return {
        "status": "success",
        "new_messages": len(filtered),
        "messages": filtered,
        "sync_time": datetime.utcnow().isoformat(),
        "next_sync_in_seconds": 60  # Poll every 60 seconds
    }


# ============================================================================
# AGENT INTEGRATION - Send Message from Agent
# ============================================================================

@router.post("/messages/send")
async def send_agent_message(
    user_id: str = Query(...),
    ticker: str = Query(...),
    buy_score: float = Query(..., ge=0, le=1),
    buy_signal: str = Query(...),
    thesis: str = Query(...),
    key_factors: List[str] = Query(...),
    confidence: str = Query(...),
    targets: Optional[dict] = None,
    authorization: str = Header(None)
):
    """
    Send message from agent to iOS user
    
    Called by agent when it finds a buy opportunity
    """
    verify_token(authorization)
    
    queue = get_message_queue()
    
    # Create signal emoji based on signal type
    signal_emoji = "🔴" if buy_signal == "STRONG_BUY" else "🟠" if buy_signal == "BUY" else "🟡"
    
    message = IOSMessage(
        id="",  # Will be set by queue
        user_id=user_id,
        ticker=ticker,
        message_type=MessageType.BUY_SIGNAL,
        buy_score=buy_score,
        buy_signal=buy_signal,
        title=f"{signal_emoji} {ticker} - {buy_signal}",
        body=f"{ticker} shows {buy_score:.0%} confidence for {buy_signal}",
        thesis=thesis,
        key_factors=key_factors,
        targets=targets,
        confidence=confidence,
        created_at=datetime.utcnow()
    )
    
    msg_id = queue.add_message(user_id, message)
    
    return {
        "status": "success",
        "message_id": msg_id,
        "ticker": ticker,
        "buy_signal": buy_signal,
        "created_at": message.created_at.isoformat()
    }


# ============================================================================
# WATCHLIST
# ============================================================================

@router.get("/watchlist")
async def get_watchlist(
    user_id: str = Query(...),
    authorization: str = Header(None)
):
    """Get user's watchlist (from messages)"""
    verify_token(authorization)
    
    queue = get_message_queue()
    messages = queue.get_all_messages(user_id, limit=1000)
    
    # Extract unique tickers from messages
    tickers = sorted(list(set([m.ticker for m in messages])))
    
    return {
        "watchlist": tickers,
        "count": len(tickers)
    }


# ============================================================================
# ANALYTICS
# ============================================================================

@router.get("/analytics/top-signals")
async def get_top_signals(
    user_id: str = Query(...),
    limit: int = Query(10, le=50),
    authorization: str = Header(None)
):
    """Get top buy signals by score"""
    verify_token(authorization)
    
    queue = get_message_queue()
    messages = queue.get_all_messages(user_id, limit=500)
    
    # Filter and sort by buy score
    signals = [m for m in messages if m.message_type == MessageType.BUY_SIGNAL]
    top_signals = sorted(signals, key=lambda x: x.buy_score, reverse=True)[:limit]
    
    return {
        "top_signals": top_signals,
        "count": len(top_signals)
    }


@router.get("/analytics/signal-summary")
async def get_signal_summary(
    user_id: str = Query(...),
    authorization: str = Header(None)
):
    """Get summary of all signals"""
    verify_token(authorization)
    
    queue = get_message_queue()
    messages = queue.get_all_messages(user_id, limit=1000)
    
    signals = [m for m in messages if m.message_type == MessageType.BUY_SIGNAL]
    
    strong_buy = len([m for m in signals if m.buy_signal == "STRONG_BUY"])
    buy = len([m for m in signals if m.buy_signal == "BUY"])
    hold = len([m for m in signals if m.buy_signal == "HOLD"])
    
    avg_score = sum([m.buy_score for m in signals]) / len(signals) if signals else 0
    
    return {
        "total_signals": len(signals),
        "strong_buy": strong_buy,
        "buy": buy,
        "hold": hold,
        "average_score": round(avg_score, 2),
        "unique_tickers": len(set([m.ticker for m in signals]))
    }

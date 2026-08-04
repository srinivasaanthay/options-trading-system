"""
iOS Message System
Stores and delivers agent recommendations directly to iOS app
"""

from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel
from enum import Enum
import json
from collections import defaultdict

class MessageType(str, Enum):
    BUY_SIGNAL = "buy_signal"
    ANALYSIS = "analysis"
    ALERT = "alert"
    WATCHLIST_UPDATE = "watchlist_update"

class MessageStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    READ = "read"
    ARCHIVED = "archived"

class IOSMessage(BaseModel):
    """iOS Message Model"""
    id: str
    user_id: str
    ticker: str
    message_type: MessageType
    buy_score: float
    buy_signal: str
    title: str
    body: str
    thesis: str
    key_factors: List[str]
    targets: Optional[Dict] = None
    confidence: str
    status: MessageStatus = MessageStatus.PENDING
    created_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg_123",
                "user_id": "user_1",
                "ticker": "AAPL",
                "message_type": "buy_signal",
                "buy_score": 0.85,
                "buy_signal": "STRONG_BUY",
                "title": "🔴 AAPL - STRONG BUY",
                "body": "Apple shows strong momentum with positive sentiment",
                "thesis": "Technical breakout with institutional buying",
                "key_factors": ["Strong technical breakout", "Positive sentiment", "Record volume"],
                "targets": {"upside": 180, "downside": 170},
                "confidence": "VERY_HIGH",
                "status": "delivered",
                "created_at": "2026-05-27T14:30:00Z"
            }
        }

class IOSMessageQueue:
    """In-memory message queue (replace with database in Phase 3B)"""
    
    def __init__(self):
        self.messages: Dict[str, List[IOSMessage]] = defaultdict(list)
        self.message_index: Dict[str, IOSMessage] = {}
        self.counter = 0
    
    def add_message(self, user_id: str, message: IOSMessage) -> str:
        """Add message to queue"""
        msg_id = f"msg_{self.counter}"
        self.counter += 1
        
        message.id = msg_id
        self.messages[user_id].append(message)
        self.message_index[msg_id] = message
        
        return msg_id
    
    def get_pending_messages(self, user_id: str) -> List[IOSMessage]:
        """Get undelivered messages"""
        return [m for m in self.messages[user_id] 
                if m.status in [MessageStatus.PENDING, MessageStatus.DELIVERED]]
    
    def get_all_messages(self, user_id: str, limit: int = 100) -> List[IOSMessage]:
        """Get all messages (paginated)"""
        return sorted(
            self.messages[user_id], 
            key=lambda x: x.created_at, 
            reverse=True
        )[:limit]
    
    def mark_delivered(self, message_id: str) -> bool:
        """Mark message as delivered"""
        if message_id in self.message_index:
            msg = self.message_index[message_id]
            msg.status = MessageStatus.DELIVERED
            msg.delivered_at = datetime.utcnow()
            return True
        return False
    
    def mark_read(self, message_id: str) -> bool:
        """Mark message as read"""
        if message_id in self.message_index:
            msg = self.message_index[message_id]
            msg.status = MessageStatus.READ
            msg.read_at = datetime.utcnow()
            return True
        return False
    
    def archive_message(self, message_id: str) -> bool:
        """Archive message"""
        if message_id in self.message_index:
            msg = self.message_index[message_id]
            msg.status = MessageStatus.ARCHIVED
            return True
        return False
    
    def get_message(self, message_id: str) -> Optional[IOSMessage]:
        """Get single message"""
        return self.message_index.get(message_id)
    
    def get_unread_count(self, user_id: str) -> int:
        """Get unread message count"""
        return len([m for m in self.messages[user_id] 
                   if m.status == MessageStatus.PENDING])
    
    def delete_old_messages(self, user_id: str, days: int = 30):
        """Delete messages older than X days"""
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        original_count = len(self.messages[user_id])
        self.messages[user_id] = [
            m for m in self.messages[user_id] 
            if m.created_at > cutoff_date
        ]
        deleted = original_count - len(self.messages[user_id])
        
        return deleted

# Global message queue instance
message_queue = IOSMessageQueue()

def get_message_queue() -> IOSMessageQueue:
    """Get global message queue"""
    return message_queue

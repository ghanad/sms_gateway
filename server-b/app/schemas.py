from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    tracking_id: str
    client_key: str
    to: str
    text: str
    providers: List[str] = Field(default_factory=list)
    policy: str = "prioritized"
    send_attempts: int = 0
    ttl_seconds: int = 3600
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MessageStatusOut(BaseModel):
    tracking_id: str
    status: str
    provider_final: Optional[str]
    to: str
    text: str


class EventOut(BaseModel):
    event_type: str
    provider: Optional[str]
    details: dict
    created_at: datetime


class MessageWithEventsOut(MessageStatusOut):
    events: List[EventOut]

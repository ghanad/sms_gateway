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


class UserBase(BaseModel):
    name: str
    username: str
    daily_quota: int
    api_key: str
    note: Optional[str] = None
    active: bool = True


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int


class UserUpdate(BaseModel):
    name: Optional[str] = None
    daily_quota: Optional[int] = None
    api_key: Optional[str] = None
    note: Optional[str] = None
    active: Optional[bool] = None


class PasswordChange(BaseModel):
    password: str

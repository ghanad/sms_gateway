from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageOut(BaseModel):
    id: int
    to: str
    text: str
    provider: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    items: List[MessageOut]
    total: int


class MessageFilters(BaseModel):
    to: Optional[str] = None
    provider: Optional[str] = None
    status: Optional[str] = None
    limit: int = 10
    offset: int = 0


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    providers: List[str] = []

    class Config:
        from_attributes = True


class AssociationIn(BaseModel):
    provider: str


class ProviderInfo(BaseModel):
    name: str
    message_count: int


class ProvidersResponse(BaseModel):
    providers: List[ProviderInfo]


class SummaryResponse(BaseModel):
    total_messages: int
    total_users: int

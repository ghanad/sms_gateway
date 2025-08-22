import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

class SendSmsRequest(BaseModel):
    to: str = Field(..., description="Recipient's phone number in E.164 format.")
    text: str = Field(..., max_length=1000, description="The content of the SMS message.")
    providers: Optional[List[str]] = Field(
        None,
        description="Optional list of preferred providers. If empty, smart selection will be used."
    )
    ttl_seconds: Optional[int] = Field(
        3600, ge=10, le=86400, description="Time-to-live for the message in seconds. Default is 3600 (1 hour)."
    )

    @validator('to')
    def validate_e164(cls, v):
        # E.164 format: starts with +, followed by 1 to 15 digits.
        if not re.fullmatch(r"^\+\d{1,15}$", v):
            raise ValueError("Phone number must be in E.164 format (e.g., +1234567890).")
        return v

class SendSmsResponse(BaseModel):
    success: bool = Field(..., description="True if the request was accepted for processing.")
    message: str = Field(..., description="A human-readable message regarding the request status.")
    tracking_id: UUID = Field(..., description="Unique identifier for the SMS request.")

class ErrorResponse(BaseModel):
    error_code: str = Field(..., description="A unique code identifying the error type.")
    message: str = Field(..., description="A human-readable error message.")
    details: Optional[Dict[str, Any]] = Field(None, description="Optional additional error details.")
    tracking_id: Optional[UUID] = Field(None, description="The tracking ID if generated before the error.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of when the error occurred.")
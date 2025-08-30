import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

class SendSmsRequest(BaseModel):
    to: str = Field(
        ...,
        description=(
            "Recipient phone number. Accepts local Iran mobile format (e.g., 0912xxxxxxx) "
            "and normalizes to E.164 (+98912xxxxxxx), or a valid E.164 directly."
        ),
    )
    text: str = Field(..., max_length=1000, description="The content of the SMS message.")
    providers: Optional[List[str]] = Field(
        None,
        description="Optional list of preferred providers. If empty, smart selection will be used."
    )
    ttl_seconds: Optional[int] = Field(
        3600, ge=10, le=86400, description="Time-to-live for the message in seconds. Default is 3600 (1 hour)."
    )

    @validator('to', pre=True)
    def normalize_and_validate_phone(cls, v):
        if not isinstance(v, str):
            raise ValueError("Phone number must be a string.")

        v = v.strip()

        e164_regex = r"^\+\d{1,15}$"
        if v.startswith('+'):
            if re.fullmatch(e164_regex, v):
                return v
            raise ValueError("Phone must be valid E.164 like +98912xxxxxxx.")

        compact = re.sub(r"[\s\-()]+", "", v)

        # Accept local Iran mobile numbers and normalize to +98...
        if re.fullmatch(r"^09\d{9}$", compact):
            return "+98" + compact[1:]
        if re.fullmatch(r"^9\d{9}$", compact):
            return "+98" + compact

        raise ValueError("Phone must be 0912xxxxxxx or valid E.164 like +98912xxxxxxx.")

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

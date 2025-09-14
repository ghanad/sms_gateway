import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from dataclasses import dataclass, field

@dataclass
class SendSmsRequest:
    to: str
    text: str
    providers: Optional[List[str]] = None
    ttl_seconds: Optional[int] = 3600

    def validate_phone(self):
        if not isinstance(self.to, str):
            raise ValueError("Phone number must be a string.")

        v = self.to.strip()

        e164_regex = r"^\+\d{1,15}$"
        if v.startswith('+'):
            if re.fullmatch(e164_regex, v):
                self.to = v
                return
            raise ValueError("Phone must be valid E.164 like +98912xxxxxxx.")

        compact = re.sub(r"[\s\-()]+", "", v)

        # Accept local Iran mobile numbers and normalize to +98...
        if re.fullmatch(r"^09\d{9}$", compact):
            self.to = "+98" + compact[1:]
            return
        if re.fullmatch(r"^9\d{9}$", compact):
            self.to = "+98" + compact
            return

        raise ValueError("Phone must be 0912xxxxxxx or valid E.164 like +98912xxxxxxx.")

@dataclass
class SendSmsResponse:
    success: bool
    message: str
    tracking_id: UUID

@dataclass
class ErrorResponse:
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    tracking_id: Optional[UUID] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
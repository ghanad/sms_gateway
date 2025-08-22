import enum
from dataclasses import dataclass


class SendStatus(enum.Enum):
    SUCCESS = "success"
    TEMP_FAILURE = "temp_failure"
    PERM_FAILURE = "perm_failure"


@dataclass
class SendResult:
    status: SendStatus
    details: dict | None = None


class BaseProvider:
    name: str

    async def send_sms(self, to: str, text: str) -> SendResult:  # pragma: no cover - interface
        raise NotImplementedError

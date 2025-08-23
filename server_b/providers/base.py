from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class SendResult:
    ok: bool
    http_status: int | None = None
    provider_message_id: Any | None = None
    retryable: bool = False
    raw: Any | None = None
    error: str | None = None

class ProviderInterface:
    def send(self, message: Dict[str, Any], cfg: Dict[str, Any]) -> SendResult:
        raise NotImplementedError

    def get_balance(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        return {'ok': False, 'error': 'NOT_SUPPORTED'}

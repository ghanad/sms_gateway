import httpx
from .base import BaseProvider, SendResult, SendStatus


class ProviderA(BaseProvider):
    name = "provider_a"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient()

    async def send_sms(self, to: str, text: str) -> SendResult:
        resp = await self.client.post("https://provider-a.example/send", json={"to": to, "text": text})
        if resp.status_code == 200:
            return SendResult(SendStatus.SUCCESS, resp.json())
        if resp.status_code >= 500:
            return SendResult(SendStatus.TEMP_FAILURE, {"status_code": resp.status_code})
        return SendResult(SendStatus.PERM_FAILURE, {"status_code": resp.status_code})

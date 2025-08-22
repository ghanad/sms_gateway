from .base import BaseProvider, SendResult, SendStatus


class LocalSMS(BaseProvider):
    name = "local_sms"

    async def send_sms(self, to: str, text: str) -> SendResult:
        return SendResult(SendStatus.SUCCESS, {"echo": text})

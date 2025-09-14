import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field

def normalize_provider_key(name: str) -> str:
    """Normalize provider names by stripping non-alphanumeric characters and lowering case."""
    return ''.join(ch for ch in name.lower() if ch.isalnum())

@dataclass
class ClientConfig:
    user_id: int
    username: str
    is_active: bool = True
    daily_quota: int = 1000

@dataclass
class ProviderConfig:
    is_active: bool
    is_operational: bool
    aliases: Optional[List[str]] = None
    note: Optional[str] = None

class Settings:
    def __init__(self, **kwargs):
        self.app_name: str = os.getenv("APP_NAME", "SMS Gateway - Server A")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.rabbit_host: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.rabbit_port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.rabbit_user: str = os.getenv("RABBITMQ_USER", "guest")
        self.rabbit_pass: str = os.getenv("RABBITMQ_PASS", "guest")
        self.outbound_sms_exchange: str = os.getenv("OUTBOUND_SMS_EXCHANGE", "sms_outbound_exchange")
        self.outbound_sms_queue: str = os.getenv("OUTBOUND_SMS_QUEUE", "sms_outbound_queue")
        self.idempotency_ttl_seconds: int = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))
        self.heartbeat_interval_seconds: int = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "60"))
        self.PROVIDER_GATE_ENABLED: bool = os.getenv("PROVIDER_GATE_ENABLED", "True").lower() in ("true", "1", "t")
        self.QUOTA_PREFIX: str = os.getenv("QUOTA_PREFIX", "quota")
        self.CLIENT_CONFIG: str = os.getenv("CLIENT_CONFIG", "{}")
        self.PROVIDERS_CONFIG: str = os.getenv("PROVIDERS_CONFIG", "{}")

        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def RABBITMQ_URL(self) -> str:
        if hasattr(self, '_RABBITMQ_URL'):
            return self._RABBITMQ_URL
        return f"amqp://{self.rabbit_user}:{self.rabbit_pass}@{self.rabbit_host}:{self.rabbit_port}/"

    @RABBITMQ_URL.setter
    def RABBITMQ_URL(self, value):
        self._RABBITMQ_URL = value

_settings = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
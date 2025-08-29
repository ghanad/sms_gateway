from typing import Dict, List, Optional
from pydantic import Field, BaseModel, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_provider_key(name: str) -> str:
    """Normalize provider names by stripping non-alphanumeric characters and lowering case."""
    return ''.join(ch for ch in name.lower() if ch.isalnum())

class ClientConfig(BaseModel):
    user_id: int
    username: str
    is_active: bool = True
    daily_quota: int = 1000

class ProviderConfig(BaseModel):
    is_active: bool
    is_operational: bool
    aliases: Optional[List[str]] = None
    note: Optional[str] = None

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")

    app_name: str = Field("SMS Gateway - Server A", env="APP_NAME")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    redis_url: str = Field("redis://redis:6379/0", env="REDIS_URL")
    rabbit_host: str = Field("rabbitmq", env="RABBITMQ_HOST")
    rabbit_port: int = Field(5672, env="RABBITMQ_PORT")
    rabbit_user: str = Field("guest", env="RABBITMQ_USER")
    rabbit_pass: str = Field("guest", env="RABBITMQ_PASS")
    outbound_sms_exchange: str = Field("sms_outbound_exchange", env="OUTBOUND_SMS_EXCHANGE")
    outbound_sms_queue: str = Field("sms_outbound_queue", env="OUTBOUND_SMS_QUEUE")
    idempotency_ttl_seconds: int = Field(86400, env="IDEMPOTENCY_TTL_SECONDS")
    heartbeat_interval_seconds: int = Field(60, env="HEARTBEAT_INTERVAL_SECONDS")
    PROVIDER_GATE_ENABLED: bool = Field(True, env="PROVIDER_GATE_ENABLED")
    QUOTA_PREFIX: str = Field("quota", env="QUOTA_PREFIX")

    @computed_field
    @property
    def RABBITMQ_URL(self) -> str:
        return f"amqp://{self.rabbit_user}:{self.rabbit_pass}@{self.rabbit_host}:{self.rabbit_port}/"

def get_settings() -> Settings:
    return Settings()

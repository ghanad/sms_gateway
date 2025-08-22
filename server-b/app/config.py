import json
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = Field("server-b", env="SERVICE_NAME")
    host: str = Field("0.0.0.0", env="SERVER_B_HOST")
    port: int = Field(9000, env="SERVER_B_PORT")

    rabbitmq_url: str = Field("amqp://guest:guest@rabbitmq:5672/", env="RABBITMQ_URL")
    rabbitmq_queue_outbound: str = Field("sms.outbound", env="RABBITMQ_QUEUE_OUTBOUND")
    rabbitmq_queue_heartbeat: str = Field("a.heartbeat", env="RABBITMQ_QUEUE_HEARTBEAT")
    rabbitmq_prefetch: int = Field(32, env="RABBITMQ_PREFETCH")

    database_url: str = Field(..., env="DATABASE_URL")

    allowed_origins: Union[List[str], str] = Field(default_factory=list, env="ALLOWED_ORIGINS")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse ALLOWED_ORIGINS from env or input.

        The env value may be provided as a JSON array or as a comma-separated
        string. This validator normalizes both formats into a list of strings
        and gracefully handles empty or missing values.
        """
        if v is None or v == "":
            return []
        if isinstance(v, str):
            v = v.strip()
            # Try to interpret the string as JSON first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
            # Fallback: treat as comma-separated list
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return v
        raise TypeError("allowed_origins must be a string or list")

    max_send_attempts: int = Field(10, env="MAX_SEND_ATTEMPTS")
    default_ttl_seconds: int = Field(3600, env="DEFAULT_TTL_SECONDS")
    min_ttl_seconds: int = Field(10, env="MIN_TTL_SECONDS")
    max_ttl_seconds: int = Field(86400, env="MAX_TTL_SECONDS")

    smart_selection_strategy: str = Field("priority", env="SMART_SELECTION_STRATEGY")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

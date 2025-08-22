from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    service_name: str = Field("server-b", env="SERVICE_NAME")
    host: str = Field("0.0.0.0", env="SERVER_B_HOST")
    port: int = Field(9000, env="SERVER_B_PORT")

    rabbitmq_url: str = Field("amqp://guest:guest@rabbitmq:5672/", env="RABBITMQ_URL")
    rabbitmq_queue_outbound: str = Field("sms.outbound", env="RABBITMQ_QUEUE_OUTBOUND")
    rabbitmq_queue_heartbeat: str = Field("a.heartbeat", env="RABBITMQ_QUEUE_HEARTBEAT")
    rabbitmq_prefetch: int = Field(32, env="RABBITMQ_PREFETCH")

    database_url: str = Field(..., env="DATABASE_URL")

    max_send_attempts: int = Field(10, env="MAX_SEND_ATTEMPTS")
    default_ttl_seconds: int = Field(3600, env="DEFAULT_TTL_SECONDS")
    min_ttl_seconds: int = Field(10, env="MIN_TTL_SECONDS")
    max_ttl_seconds: int = Field(86400, env="MAX_TTL_SECONDS")

    smart_selection_strategy: str = Field("priority", env="SMART_SELECTION_STRATEGY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

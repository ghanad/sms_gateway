import json
import hashlib
from typing import Dict, List, Optional
from pydantic import Field, BaseModel, ValidationError, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class ClientConfig(BaseModel):
    name: str
    is_active: bool
    daily_quota: int

class ProviderConfig(BaseModel):
    is_active: bool
    is_operational: bool
    aliases: Optional[List[str]] = None
    note: Optional[str] = None

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    SERVICE_NAME: str = "server-a"
    SERVER_A_HOST: str = "0.0.0.0"
    SERVER_A_PORT: int = 8000
    REDIS_URL: str = "redis://redis:6379/0"
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    PROVIDER_GATE_ENABLED: bool = True
    IDEMPOTENCY_TTL_SECONDS: int = 86400
    QUOTA_PREFIX: str = "quota"
    HEARTBEAT_INTERVAL_SECONDS: int = 60
    CLIENT_CONFIG: str
    PROVIDERS_CONFIG: str

    @computed_field
    @property
    def clients(self) -> Dict[str, ClientConfig]:
        try:
            data = json.loads(self.CLIENT_CONFIG)
            return {k: ClientConfig(**v) for k, v in data.items()}
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Invalid CLIENT_CONFIG JSON: {e}") from e

    @computed_field
    @property
    def providers(self) -> Dict[str, ProviderConfig]:
        try:
            data = json.loads(self.PROVIDERS_CONFIG)
            return {k: ProviderConfig(**v) for k, v in data.items()}
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Invalid PROVIDERS_CONFIG JSON: {e}") from e

    @computed_field
    @property
    def client_config_fingerprint(self) -> str:
        return hashlib.sha256(self.CLIENT_CONFIG.encode('utf-8')).hexdigest()

    @computed_field
    @property
    def providers_config_fingerprint(self) -> str:
        return hashlib.sha256(self.PROVIDERS_CONFIG.encode('utf-8')).hexdigest()

    @computed_field
    @property
    def provider_alias_map(self) -> Dict[str, str]:
        alias_map: Dict[str, str] = {}
        for provider_name, provider_config in self.providers.items():
            # Add canonical name itself to the map
            canonical_name_lower = provider_name.lower()
            if canonical_name_lower in alias_map and alias_map[canonical_name_lower] != provider_name:
                raise ValueError(f"Alias collision: '{canonical_name_lower}' already maps to '{alias_map[canonical_name_lower]}', cannot map to '{provider_name}'")
            alias_map[canonical_name_lower] = provider_name

            if provider_config.aliases:
                for alias in provider_config.aliases:
                    alias_lower = alias.lower()
                    if alias_lower in alias_map and alias_map[alias_lower] != provider_name:
                        raise ValueError(f"Alias collision: '{alias_lower}' already maps to '{alias_map[alias_lower]}', cannot map to '{provider_name}'")
                    alias_map[alias_lower] = provider_name
        return alias_map

@lru_cache
def get_settings() -> Settings:
    return Settings()

# Validate settings on startup
try:
    settings = get_settings()
    # Access computed fields to trigger validation
    _ = settings.clients
    _ = settings.providers
    _ = settings.provider_alias_map
except ValueError as e:
    print(f"Configuration Error: {e}")
    import sys
    sys.exit(1)
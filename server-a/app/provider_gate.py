import logging
from typing import List, Optional, Tuple
from fastapi import HTTPException, status, Request

from app.config import get_settings, ProviderConfig
from app.metrics import (
    SMS_REQUEST_REJECTED_UNKNOWN_PROVIDER_TOTAL,
    SMS_REQUEST_REJECTED_PROVIDER_DISABLED_TOTAL,
    SMS_REQUEST_REJECTED_NO_PROVIDER_AVAILABLE_TOTAL
)

logger = logging.getLogger(__name__)
settings = get_settings()

class ProviderGate:
    def __init__(self):
        self.settings = get_settings()
        self.provider_alias_map = self.settings.provider_alias_map
        self.providers_config = self.settings.providers

    def _get_canonical_provider_name(self, provider_name: str) -> Optional[str]:
        """Returns the canonical provider name, case-insensitively."""
        return self.provider_alias_map.get(provider_name.lower())

    def _is_provider_active_and_operational(self, canonical_name: str) -> bool:
        """Checks if a provider is active and operational."""
        config = self.providers_config.get(canonical_name)
        return config is not None and config.is_active and config.is_operational

    def process_providers(self, request: Request, requested_providers: Optional[List[str]]) -> List[str]:
        """
        Validates and filters the list of requested providers based on configuration and rules.
        Emits metrics and logs for rejections.
        """
        client_api_key = getattr(request.state, 'client', None).api_key if hasattr(request.state, 'client') else "unknown"

        if not self.settings.PROVIDER_GATE_ENABLED:
            logger.info("Provider Gate is disabled. Bypassing provider validation.")
            # If disabled, and providers were requested, map them to canonical names without further validation
            if requested_providers:
                effective_providers = []
                for p in requested_providers:
                    canonical_name = self._get_canonical_provider_name(p)
                    if canonical_name:
                        effective_providers.append(canonical_name)
                    else:
                        logger.warning(
                            "Provider Gate disabled, but unknown provider requested.",
                            extra={"client_api_key": client_api_key, "provider": p}
                        )
                return effective_providers
            return [] # If disabled and no providers requested, return empty list for smart selection

        if not requested_providers:
            # Smart Selection
            active_operational_providers = [
                name for name, config in self.providers_config.items()
                if config.is_active and config.is_operational
            ]
            if not active_operational_providers:
                SMS_REQUEST_REJECTED_NO_PROVIDER_AVAILABLE_TOTAL.labels(client=client_api_key).inc()
                logger.warning(
                    "Provider Gate rejected: No active and operational providers available for smart selection.",
                    extra={"client_api_key": client_api_key, "error_code": "NO_PROVIDER_AVAILABLE"}
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"error_code": "NO_PROVIDER_AVAILABLE", "message": "No SMS providers are currently available."}
                )
            logger.info(
                "Provider Gate: Smart selection will be used.",
                extra={"client_api_key": client_api_key, "effective_providers": active_operational_providers}
            )
            return [] # An empty list signifies smart selection for Server B

        # Process explicitly requested providers
        effective_providers: List[str] = []
        unknown_providers: List[str] = []
        disabled_providers: List[str] = []

        for provider_alias in requested_providers:
            canonical_name = self._get_canonical_provider_name(provider_alias)
            if not canonical_name:
                unknown_providers.append(provider_alias)
            else:
                if self._is_provider_active_and_operational(canonical_name):
                    effective_providers.append(canonical_name)
                else:
                    disabled_providers.append(canonical_name)

        if unknown_providers:
            allowed_names = sorted(list(self.providers_config.keys()))
            SMS_REQUEST_REJECTED_UNKNOWN_PROVIDER_TOTAL.labels(client=client_api_key).inc()
            logger.warning(
                "Provider Gate rejected: Unknown provider(s) requested.",
                extra={"client_api_key": client_api_key, "unknown_providers": unknown_providers, "error_code": "UNKNOWN_PROVIDER"}
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "UNKNOWN_PROVIDER",
                    "message": f"Unknown provider(s): {', '.join(unknown_providers)}. Allowed providers are: {', '.join(allowed_names)}."
                }
            )

        if len(requested_providers) == 1:
            # Exclusive Selection
            if disabled_providers:
                provider_name = disabled_providers[0]
                SMS_REQUEST_REJECTED_PROVIDER_DISABLED_TOTAL.labels(client=client_api_key, provider=provider_name).inc()
                logger.warning(
                    "Provider Gate rejected: Exclusive provider is disabled or not operational.",
                    extra={"client_api_key": client_api_key, "provider": provider_name, "error_code": "PROVIDER_DISABLED"}
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error_code": "PROVIDER_DISABLED", "message": f"Provider '{provider_name}' is currently disabled or not operational."}
                )
            # If it reaches here, the single provider is active and operational, so it's in effective_providers
            logger.info(
                "Provider Gate: Exclusive selection successful.",
                extra={"client_api_key": client_api_key, "effective_providers": effective_providers}
            )
            return effective_providers
        else:
            # Prioritized Failover (more than one requested)
            if disabled_providers:
                for p_name in disabled_providers:
                    SMS_REQUEST_REJECTED_PROVIDER_DISABLED_TOTAL.labels(client=client_api_key, provider=p_name).inc()
                logger.info(
                    "Provider Gate: Filtering out disabled/non-operational providers from prioritized list.",
                    extra={"client_api_key": client_api_key, "disabled_providers": disabled_providers, "effective_providers_before_filter": requested_providers}
                )

            if not effective_providers:
                SMS_REQUEST_REJECTED_NO_PROVIDER_AVAILABLE_TOTAL.labels(client=client_api_key).inc() # Re-using this metric for "all disabled"
                logger.warning(
                    "Provider Gate rejected: All requested providers are disabled or not operational.",
                    extra={"client_api_key": client_api_key, "requested_providers": requested_providers, "error_code": "ALL_PROVIDERS_DISABLED"}
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error_code": "ALL_PROVIDERS_DISABLED", "message": "All requested providers are currently disabled or not operational."}
                )
            logger.info(
                "Provider Gate: Prioritized failover selection successful.",
                extra={"client_api_key": client_api_key, "effective_providers": effective_providers}
            )
            return effective_providers

provider_gate = ProviderGate()
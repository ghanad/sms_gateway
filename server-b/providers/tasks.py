import logging
from typing import Any

from celery import shared_task

from providers.adapters import get_provider_adapter
from providers.models import SmsProvider
from sms_gateway_project.metrics import SMS_PROVIDER_BALANCE_GAUGE


logger = logging.getLogger(__name__)


def _provider_label(provider: SmsProvider) -> str:
    slug = getattr(provider, "slug", None)
    if slug:
        return str(slug)
    name = getattr(provider, "name", None)
    return str(name) if name else "unknown"


def _coerce_balance_value(payload: Any) -> float | None:
    if isinstance(payload, dict):
        for key in ("balance", "credit", "credits"):
            if key in payload:
                candidate = payload[key]
                break
        else:
            candidate = None
    else:
        candidate = payload

    if candidate is None:
        return None

    try:
        return float(candidate)
    except (TypeError, ValueError):
        return None


@shared_task
def update_provider_balance_metrics() -> None:
    """Update the balance gauge for each active provider."""

    providers = SmsProvider.objects.filter(is_active=True)

    for provider in providers:
        provider_label = _provider_label(provider)

        try:
            adapter = get_provider_adapter(provider)
        except Exception:  # pragma: no cover - defensive guard
            logger.exception(
                "Failed to load adapter for provider %s", provider_label
            )
            continue

        try:
            balance_payload = adapter.get_balance()
        except Exception:  # pragma: no cover - defensive guard
            logger.warning(
                "Balance retrieval failed for provider %s", provider_label
            )
            continue

        balance_value = _coerce_balance_value(balance_payload)
        if balance_value is None:
            logger.debug(
                "Provider %s returned non-numeric balance payload: %r",
                provider_label,
                balance_payload,
            )
            continue

        SMS_PROVIDER_BALANCE_GAUGE.labels(provider=provider_label).set(balance_value)

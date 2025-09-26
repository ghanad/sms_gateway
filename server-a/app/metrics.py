from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
from prometheus_client.core import CollectorRegistry
from fastapi import Response
from typing import Dict, Any
import logging

from app.cache import PROVIDER_CONFIG_CACHE

logger = logging.getLogger(__name__)

# Custom registry for FastAPI to avoid conflicts with default registry if other libraries use it
# and to have full control over what metrics are exposed.
APP_REGISTRY = CollectorRegistry()

# Define metrics
SMS_PROVIDERS_CONFIG_TOTAL = Gauge(
    'sms_providers_config_total',
    'Total number of SMS providers configured.',
    registry=APP_REGISTRY
)
SMS_PROVIDER_ACTIVE = Gauge(
    'sms_provider_active',
    'Whether an SMS provider is active (1) or not (0).',
    ['provider'],
    registry=APP_REGISTRY
)
SMS_PROVIDER_OPERATIONAL = Gauge(
    'sms_provider_operational',
    'Whether an SMS provider is operational (1) or not (0).',
    ['provider'],
    registry=APP_REGISTRY
)
SMS_REQUEST_REJECTED_UNKNOWN_PROVIDER_TOTAL = Counter(
    'sms_request_rejected_unknown_provider_total',
    'Total number of SMS requests rejected due to unknown provider.',
    ['client'],
    registry=APP_REGISTRY
)
SMS_REQUEST_REJECTED_PROVIDER_DISABLED_TOTAL = Counter(
    'sms_request_rejected_provider_disabled_total',
    'Total number of SMS requests rejected due to disabled provider.',
    ['client', 'provider'],
    registry=APP_REGISTRY
)
SMS_REQUEST_REJECTED_NO_PROVIDER_AVAILABLE_TOTAL = Counter(
    'sms_request_rejected_no_provider_available_total',
    'Total number of SMS requests rejected due to no provider available.',
    ['client'],
    registry=APP_REGISTRY
)
SMS_CONFIG_FINGERPRINT_MISMATCH_TOTAL = Counter(
    'sms_config_fingerprint_mismatch_total',
    'Total number of times a configuration fingerprint mismatch was detected.',
    ['kind'],
    registry=APP_REGISTRY
)

# Metrics for /api/v1/sms/send endpoint
SMS_SEND_REQUESTS_TOTAL = Counter(
    'sms_send_requests_total',
    'Total number of SMS send requests.',
    registry=APP_REGISTRY
)
SMS_SEND_REQUEST_LATENCY_SECONDS = Histogram(
    'sms_send_request_latency_seconds',
    'Latency of SMS send requests in seconds.',
    registry=APP_REGISTRY
)
SMS_SEND_REQUEST_SUCCESS_TOTAL = Counter(
    'sms_send_request_success_total',
    'Total number of successful SMS send requests.',
    registry=APP_REGISTRY
)
SMS_SEND_REQUEST_ERROR_TOTAL = Counter(
    'sms_send_request_error_total',
    'Total number of failed SMS send requests.',
    registry=APP_REGISTRY
)

def initialize_provider_metrics():
    """Initializes provider-specific gauges based on current cache state."""
    providers_config = PROVIDER_CONFIG_CACHE
    SMS_PROVIDERS_CONFIG_TOTAL.set(len(providers_config))

    for provider_name, config in providers_config.items():
        SMS_PROVIDER_ACTIVE.labels(provider=provider_name).set(1 if config.is_active else 0)
        SMS_PROVIDER_OPERATIONAL.labels(provider=provider_name).set(1 if config.is_operational else 0)
    logger.info("Provider metrics initialized.")

def metrics_content() -> Response:
    """Returns Prometheus metrics in the OpenMetrics text exposition format."""
    payload = generate_latest(APP_REGISTRY)
    return Response(
        content=payload,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )

# Initialize metrics on startup
initialize_provider_metrics()

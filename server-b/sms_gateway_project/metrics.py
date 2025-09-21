"""Prometheus metrics helpers and HTTP endpoint for the Django project."""

from __future__ import annotations

import os
from typing import Final

from django.http import HttpRequest, HttpResponse, HttpResponseServerError
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

# ---------------------------------------------------------------------------
# Shared metrics definitions
# ---------------------------------------------------------------------------

SMS_MESSAGES_PROCESSED_TOTAL: Final[Counter] = Counter(
    "sms_messages_processed_total",
    "Total number of SMS messages processed by Celery tasks.",
)


SMS_MESSAGES_PENDING_GAUGE: Final[Gauge] = Gauge(
    "sms_messages_pending_gauge",
    "Current number of SMS messages waiting to be processed.",
    multiprocess_mode="livesum",
)


SMS_MESSAGE_FINAL_STATUS_TOTAL: Final[Counter] = Counter(
    "sms_message_final_status_total",
    "Total number of SMS messages that reached a final status.",
    labelnames=("status",),
)


SMS_PROCESSING_DURATION_SECONDS: Final[Histogram] = Histogram(
    "sms_processing_duration_seconds",
    "Time taken for an SMS message to reach a final status.",
)


SMS_PROVIDER_SEND_ATTEMPTS_TOTAL: Final[Counter] = Counter(
    "sms_provider_send_attempts_total",
    "Total number of provider send attempts, grouped by outcome.",
    labelnames=("provider", "outcome"),
)


SMS_PROVIDER_SEND_LATENCY_SECONDS: Final[Histogram] = Histogram(
    "sms_provider_send_latency_seconds",
    "Latency of provider API calls when sending SMS messages.",
    labelnames=("provider",),
)


SMS_CELERY_TASK_RETRIES_TOTAL: Final[Counter] = Counter(
    "sms_celery_task_retries_total",
    "Total number of retries of the send_sms_with_failover task.",
)


SMS_DLQ_MESSAGES_TOTAL: Final[Counter] = Counter(
    "sms_dlq_messages_total",
    "Total number of SMS messages published to the DLQ.",
)


# ---------------------------------------------------------------------------
# HTTP endpoint
# ---------------------------------------------------------------------------

def metrics_view(request: HttpRequest) -> HttpResponse:
    """Expose aggregated Prometheus metrics for all server-b processes."""

    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir:
        return HttpResponseServerError(
            "PROMETHEUS_MULTIPROC_DIR environment variable is not configured."
        )

    if not os.path.isdir(multiproc_dir):
        return HttpResponseServerError(
            f"Configured PROMETHEUS_MULTIPROC_DIR '{multiproc_dir}' does not exist."
        )

    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    payload = generate_latest(registry)
    return HttpResponse(payload, content_type=CONTENT_TYPE_LATEST)


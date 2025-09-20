"""Prometheus metrics helpers and HTTP endpoint for the Django project."""

from __future__ import annotations

import os
from typing import Final

from django.http import HttpRequest, HttpResponse, HttpResponseServerError
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
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


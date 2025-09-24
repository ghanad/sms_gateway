"""Celery tasks for the user_management application."""

from __future__ import annotations

import hashlib
import json

from celery import shared_task

from sms_gateway_project.metrics import (
    EXPECTED_CONFIG_FINGERPRINT,
    EXPECTED_CONFIG_FINGERPRINT_SERVICE_LABEL_VALUE,
)

from .utils import generate_server_a_config_data

_last_fingerprint: str | None = None


@shared_task
def update_expected_config_fingerprint_metric() -> None:
    """Compute and publish the expected configuration fingerprint metric."""
    global _last_fingerprint

    config_payload = generate_server_a_config_data()
    
    serialized = json.dumps(config_payload, sort_keys=True, separators=(",", ":"))
    current_fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    labels = {
        "service": EXPECTED_CONFIG_FINGERPRINT_SERVICE_LABEL_VALUE,
        "fingerprint": current_fingerprint,
    }

    if _last_fingerprint and _last_fingerprint != current_fingerprint:
        EXPECTED_CONFIG_FINGERPRINT.labels(
            service=EXPECTED_CONFIG_FINGERPRINT_SERVICE_LABEL_VALUE,
            fingerprint=_last_fingerprint,
        ).set(0)

    if _last_fingerprint != current_fingerprint:
        EXPECTED_CONFIG_FINGERPRINT.labels(**labels).set(1)
        _last_fingerprint = current_fingerprint

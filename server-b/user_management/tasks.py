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


@shared_task
def update_expected_config_fingerprint_metric() -> None:
    """Compute and publish the expected configuration fingerprint metric."""

    config_payload = generate_server_a_config_data()
    serialized = json.dumps(config_payload, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    EXPECTED_CONFIG_FINGERPRINT.info(
        {
            "fingerprint": fingerprint,
            "service": EXPECTED_CONFIG_FINGERPRINT_SERVICE_LABEL_VALUE,
        }
    )

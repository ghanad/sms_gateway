"""Prometheus metrics for the SMS gateway messaging pipeline."""

from prometheus_client import Counter


# Permanent errors that end up in the DLQ (either via DLX or manual publish).
sms_permanent_errors_total = Counter(
    "sms_permanent_errors_total",
    "Total count of messages routed to the permanent DLQ",
)

# Total publishes to the wait/backoff queue for transient errors.
sms_waitqueue_publish_total = Counter(
    "sms_waitqueue_publish_total",
    "Total count of messages published to the wait queue for retry",
)

# Number of times the consumer observed a retry attempt (message left the wait queue).
sms_waitqueue_retry_total = Counter(
    "sms_waitqueue_retry_total",
    "Total count of retry attempts observed by the consumer",
)

# Bad payloads routed to the dedicated DLQ.
sms_bad_payload_total = Counter(
    "sms_bad_payload_total",
    "Total count of malformed payloads routed to the bad-payload DLQ",
)

# Publisher confirms that were nacked by RabbitMQ.
sms_publisher_confirm_nacks_total = Counter(
    "sms_publisher_confirm_nacks_total",
    "Total count of publisher confirm failures when publishing to RabbitMQ",
)


# RabbitMQ Consumer Error Handling

## Overview
The `server-b` Django service ingests outbound SMS requests from RabbitMQ via the `consume_sms_queue` management command. The consumer persists each envelope to the relational database before acknowledging the delivery and classifies failures into three buckets:

* **Bad payloads** – undecodable JSON or schema violations. These are routed to a dedicated bad-payload dead-letter queue (DLQ) and acknowledged immediately.
* **Permanent business failures** – for example, `User.DoesNotExist` or exceeding the retry budget. These are rejected without requeue so RabbitMQ’s dead-letter exchange (DLX) moves the message to a single permanent DLQ.
* **Transient infrastructure failures** – database hiccups, temporary network issues, etc. These are republished to a wait queue with bounded retry metadata and acknowledged only after the publish succeeds.

The design emphasises idempotency, atomicity, and observability. Messages are durable end-to-end, publisher confirms protect manual publishes, structured logging captures correlation identifiers, and Prometheus counters expose error pathways.

## Queue Topology

| Purpose | Queue / Setting | Notes |
| --- | --- | --- |
| Primary work queue | `RABBITMQ_SMS_QUEUE` (default `sms_outbound_queue`) | Durable queue consumed with `prefetch_count=1`. Messages are published with `delivery_mode=2` for persistence. |
| Permanent DLQ | `RABBITMQ_SMS_DLQ_PERMANENT` (default `sms_permanent_dlq`) | Declared durable. The main queue includes `x-dead-letter-exchange=""` and `x-dead-letter-routing-key=<permanent DLQ>` so a `basic_reject(requeue=False)` automatically moves the message. |
| Wait/backoff queue | `RABBITMQ_SMS_WAIT_QUEUE` (default `sms_retry_wait_queue`) | Durable queue declared with `x-message-ttl` (`RABBITMQ_SMS_WAIT_QUEUE_TTL_MS`) and `x-dead-letter-routing-key` pointing back to the main queue. Used only for transient failures. |
| Bad payload DLQ | `RABBITMQ_SMS_DLQ_BAD_PAYLOAD` (default `sms_bad_payload_dlq`) | Durable quarantine for malformed or schema-invalid envelopes. |

All queues are declared by the consumer (and by Celery when publishing to the DLQ) so deployments remain idempotent. The wait queue automatically redelivers to the primary queue once the TTL expires, eliminating custom sleep loops.

## Message Flow and Classification

1. **Decode & schema validation.** Bodies must be valid UTF-8 JSON and contain `tracking_id`, `user_id`, `to`, and `text`. Invalid payloads are published to the bad-payload DLQ with diagnostic headers and then acknowledged. When the feature flag `FEATURE_BAD_PAYLOAD_DLQ` is disabled the message is simply acknowledged to mirror legacy behaviour.
2. **Idempotency check.** Messages are keyed by `tracking_id`. Existing deliveries are acknowledged without side effects. Integrity errors (unique constraint violations) are treated as duplicates and acknowledged.
3. **Database persistence.** New messages are written inside a transaction. If the transaction succeeds the delivery is acknowledged.
4. **Permanent errors.** If the associated user cannot be found—or the retry budget is exceeded—the consumer logs the failure, increments `sms_permanent_errors_total`, and rejects the delivery with `requeue=False`. RabbitMQ’s DLX immediately routes the original message to the permanent DLQ. When the feature flag `FEATURE_USE_DLX_FOR_PERM_ERRORS` is disabled, the consumer falls back to publishing to `RABBITMQ_SMS_DLQ_FALLBACK` (defaulting to the legacy `sms_dlq_user_not_found`).
5. **Transient errors.** Operational errors (database/network) are republished to the wait queue. Messages preserve all headers and correlation identifiers and add:
   * `x-retry-count` / `retry_count` – incremented on each retry.
   * `error_type` – reason for the retry.
   * `first_seen_ts` / `last_attempt_ts` – ISO-8601 timestamps.
   Publishes use RabbitMQ publisher confirms. On success the original delivery is acknowledged and `sms_waitqueue_publish_total` is incremented. If the broker nacks the publish, `sms_publisher_confirm_nacks_total` is incremented and the delivery is negatively acknowledged with `requeue=True` to avoid loss.
6. **Bounded retries.** The maximum number of retries is controlled by `SMS_RETRY_MAX_ATTEMPTS` (default 5). When the observed `x-retry-count` equals or exceeds this value the consumer treats the failure as permanent and rejects it, sending the message to the permanent DLQ.

## Celery Alignment
The Celery task `publish_to_dlq` now publishes to `RABBITMQ_SMS_DLQ_PERMANENT` with publisher confirms, persistent messages, and diagnostic headers. This keeps manual DLQ inspection consistent regardless of whether a message originated from the real-time consumer or a background task. Failures increment the shared `sms_publisher_confirm_nacks_total` counter for alerting.

## Observability

The consumer and Celery path share Prometheus counters exposed via `messaging.metrics`:

* `sms_permanent_errors_total` – messages routed to the permanent DLQ.
* `sms_waitqueue_publish_total` – successful publishes to the wait queue.
* `sms_waitqueue_retry_total` – retry attempts observed (messages leaving the wait queue).
* `sms_bad_payload_total` – payloads routed to the bad-payload DLQ.
* `sms_publisher_confirm_nacks_total` – publisher confirm failures.

Structured logs include the tracking ID, correlation ID, retry count, and error type for each branch. These logs are suitable for ingestion by centralized logging platforms and correlate directly with the metrics above.

## Configuration Summary

| Environment Variable | Default | Purpose |
| --- | --- | --- |
| `RABBITMQ_SMS_QUEUE` | `sms_outbound_queue` | Primary work queue. |
| `RABBITMQ_SMS_DLQ_PERMANENT` | `sms_permanent_dlq` | Permanent DLQ routed to via DLX. |
| `RABBITMQ_SMS_DLQ_BAD_PAYLOAD` | `sms_bad_payload_dlq` | DLQ for malformed payloads. |
| `RABBITMQ_SMS_WAIT_QUEUE` | `sms_retry_wait_queue` | Wait/backoff queue for transient failures. |
| `RABBITMQ_SMS_WAIT_QUEUE_TTL_MS` | `5000` | Milliseconds to wait between retry attempts. |
| `SMS_RETRY_MAX_ATTEMPTS` | `5` | Maximum retry attempts before treating as permanent failure. |
| `FEATURE_USE_DLX_FOR_PERM_ERRORS` | `True` | Toggle for DLX-based routing (disable to revert to manual publishing). |
| `FEATURE_BAD_PAYLOAD_DLQ` | `True` | Toggle for bad-payload DLQ. When disabled, bad payloads are simply acknowledged. |

## Testing Strategy

* **Unit tests** – `server-b/messaging/tests.py` covers success paths, duplicate handling, DLX routing, wait-queue retries, bounded retries, and bad-payload classification with and without feature flags. `server-b/tests/test_messaging_tasks.py` verifies Celery uses publisher confirms and the configured queue names.
* **Integration tests** – `server-b/tests/test_rabbitmq_integration.py` exercises a Docker-hosted RabbitMQ broker. Enable by setting `ENABLE_RABBITMQ_INTEGRATION_TESTS=1` and ensuring the `docker` CLI is available. The tests assert DLX routing, wait queue TTL redelivery, and message durability across broker restarts.

## Operational Runbook

| Scenario | Symptoms | Operator Actions |
| --- | --- | --- |
| **Permanent DLQ growth** | `sms_permanent_errors_total` spike, backlog visible in `sms_permanent_dlq` | Inspect messages for `error_type`. Resolve underlying user/provider issue and replay manually. If spike coincides with infrastructure failure, consider temporarily disabling DLX (`FEATURE_USE_DLX_FOR_PERM_ERRORS=False`) to revert to manual publish while investigating. |
| **Bad payload DLQ growth** | Increasing `sms_bad_payload_total`, backlog in `sms_bad_payload_dlq` | Payloads contain invalid JSON or schema mismatches. Coordinate with upstream producers to fix payloads. Messages retain full body and headers for debugging. |
| **Wait queue backlog** | `sms_waitqueue_publish_total` increasing faster than `sms_waitqueue_retry_total` | Indicates ongoing transient failures. Check database connectivity, RabbitMQ health, and downstream rate limits. Consider increasing `RABBITMQ_SMS_WAIT_QUEUE_TTL_MS` or temporarily pausing the consumer if downstream systems are overloaded. |
| **Publisher confirm failures** | `sms_publisher_confirm_nacks_total` > 0, logs showing "Failed to publish" | RabbitMQ is overwhelmed or connection unstable. The consumer nacks the original delivery so the broker can redeliver once healthy. Investigate broker health and network latency. |

## Migration Plan

1. **Provision queues and permissions.** Create `sms_permanent_dlq`, `sms_bad_payload_dlq`, and ensure `sms_retry_wait_queue` exists with the desired TTL. Leave the legacy `sms_dlq_user_not_found` intact for rollback.
2. **Deploy application code.** Roll out the updated consumer and Celery worker with default feature flags (`FEATURE_USE_DLX_FOR_PERM_ERRORS=True`, `FEATURE_BAD_PAYLOAD_DLQ=True`). Confirm that both services start cleanly and redeclare queues without errors.
3. **Verify metrics and behaviour.** Trigger controlled permanent, transient, and bad-payload scenarios in a staging environment. Confirm metrics increment as expected and the new DLQs receive the right messages.
4. **Decommission legacy queue.** Once satisfied, purge and delete the `sms_dlq_user_not_found` queue and remove any automation depending on it.

### Rollback Plan

* Set `FEATURE_USE_DLX_FOR_PERM_ERRORS=False` and (optionally) `FEATURE_BAD_PAYLOAD_DLQ=False` to revert to the pre-DLX behaviour. Recreate the legacy `sms_dlq_user_not_found` queue if it has been deleted.
* Redeploy the consumer/Celery worker so they reconfigure queues accordingly.
* Remove the new DLQs from monitoring only after traffic stabilises on the fallback path.

This plan ensures the migration can progress gradually without risking message loss. All new queues are durable and safe to pre-provision, so switching features on/off merely changes routing decisions inside the consumer.

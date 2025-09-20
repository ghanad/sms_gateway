# RabbitMQ Consumer Error Handling

## Overview
The `server-b` Django service ingests outbound SMS requests from RabbitMQ via the `consume_sms_queue` management command. The
consumer guarantees that messages are persisted to the relational database before acknowledging them and includes layered error
handling to prevent infinite retry loops while avoiding data loss. This document explains the queue topology, processing flow,
and operational considerations introduced by the robust error-handling strategy.

## Queue Topology
| Purpose | Queue / Setting | Notes |
| --- | --- | --- |
| Primary work queue | `RABBITMQ_SMS_QUEUE` | Carries outbound SMS envelopes produced by `server-a`. Declared durable and consumed with `prefetch_count=1` to keep processing sequential. |
| Dead-letter queue for missing users | `RABBITMQ_SMS_DLQ_USER_NOT_FOUND` | Durable quarantine for messages whose `user_id` cannot be resolved. Operators should inspect and reconcile these payloads manually. |
| Retry wait queue | `RABBITMQ_SMS_RETRY_WAIT_QUEUE` | Durable buffer with `x-message-ttl=RABBITMQ_SMS_RETRY_WAIT_TTL_MS` and `x-dead-letter-routing-key` pointing back to the primary queue. Used when DLQ publishing fails or when unexpected exceptions occur so retries are delayed and non-blocking. |

All three queue names and the wait-queue TTL are configurable through environment variables surfaced in `sms_gateway_project.settings`. The wait queue automatically re-routes its messages to the main queue once the TTL expires, eliminating the need for
consumer-controlled sleep loops.

## Processing Flow
1. **Decode and validate JSON.** Invalid payloads are logged and acknowledged to avoid poison messages.
2. **Idempotency guard.** The consumer ignores envelopes whose `tracking_id` already exists in the database.
3. **Persist message transactionally.** A new `Message` row is created while the RabbitMQ delivery remains unacknowledged. On
commit success the message is acknowledged.
4. **Handle `User.DoesNotExist`.**
   - Publish the original message to the durable DLQ.
   - On publish success, acknowledge the delivery so the main queue keeps flowing.
   - If the DLQ publish fails (for example, broker blip), publish to the retry wait queue instead. Only acknowledge after the wait
queue accepts the payload; otherwise, `basic_nack` with `requeue=True` so RabbitMQ can retry later.
5. **Handle unexpected exceptions.** Transient database or broker errors also send the message to the retry wait queue. If that
publish fails, the delivery is negatively acknowledged and requeued, preserving the payload for a later attempt.

This layered approach isolates permanent data issues, prevents hot loops when RabbitMQ or the database is briefly unavailable,
and still guarantees eventual processing once dependencies recover.

## Operational Runbook
- **Monitor the DLQ.** Messages in `sms_dlq_user_not_found` indicate missing user records or integration mismatches. Investigate
and either create the missing user, replay the message manually, or archive it after analysis.
- **Retry wait queue visibility.** Short TTL values (default 5000 ms) mean this queue should normally be empty. Sustained backlog
suggests the DLQ or downstream database is unavailable.
- **Configuration changes.** Adjust the wait queue TTL if you need a longer cool-down between retries. Any change requires
redeploying the consumer so it redeclares the queue with the new arguments.
- **Testing.** `server-b/messaging/tests.py` contains unit tests that document the expected behaviors for DLQ routing and wait
queue fallbacks. Extend these tests when changing queue semantics.

## Future Enhancements
- **Automated DLQ tooling.** Add a management command to list, replay, or purge DLQ messages once the underlying issue is fixed.
- **Metrics & Alerts.** Emit Prometheus counters for DLQ and wait-queue publishes to catch anomalies early.
- **Message annotations.** Enrich DLQ payloads with the exception string and timestamp so analysts have more context during
triage.
- **Configurable DLQs per failure type.** If additional permanent failure modes appear, consider parameterizing extra DLQs and
routing rules to keep diagnostic streams separate.

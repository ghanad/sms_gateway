# Server A - SMS API Gateway

This is the API Gateway component of the internal SMS gateway system. It handles incoming SMS send requests, performs authentication, validation, provider routing, and quota management, then enqueues messages to RabbitMQ for Server B to process.

## Features

*   **FastAPI Framework:** Built with Python 3.12 and FastAPI for high performance and ease of development.
*   **Authentication:** API Key-based authentication against a configured client list.
*   **Request Validation:** Pydantic models for robust input validation, including E.164 format for phone numbers.
*   **Idempotency:** Supports `Idempotency-Key` header to prevent duplicate processing of requests, caching both success and error responses.
*   **Provider Gate:** Smart routing and filtering of SMS providers based on their active and operational status, with fast-fail mechanisms.
*   **Daily Quota:** Enforces per-client daily SMS quotas using Redis atomic counters.
*   **RabbitMQ Integration:** Publishes durable SMS message envelopes to RabbitMQ for asynchronous processing by Server B.
*   **Heartbeat:** A background task sends periodic heartbeats to RabbitMQ, including configuration fingerprints.
*   **Structured Logging:** JSON-formatted logs with `tracking_id` and `client_api_key` for better observability.
*   **Prometheus Metrics:** Exposes a `/metrics` endpoint with detailed application and business-level metrics.
*   **Health Checks:** `/healthz` (liveness) and `/readyz` (readiness, checks Redis and RabbitMQ connectivity) endpoints.

## Setup and Environment Variables

This service relies on environment variables for configuration. A `.env.example` file is provided at the monorepo root. Copy it to `.env` and adjust as needed.

Key environment variables:

*   `SERVICE_NAME`: Name of the service (default: `server-a`).
*   `SERVER_A_HOST`: Host for the FastAPI application (default: `0.0.0.0`).
*   `SERVER_A_PORT`: Port for the FastAPI application (default: `8000`).
*   `REDIS_URL`: Connection string for Redis (e.g., `redis://redis:6379/0`).
*   `RABBITMQ_URL`: Connection string for RabbitMQ (e.g., `amqp://guest:guest@rabbitmq:5672/`).
*   `PROVIDER_GATE_ENABLED`: `true` or `false` to enable/disable the provider gate logic.
*   `IDEMPOTENCY_TTL_SECONDS`: Time-to-live for idempotency keys in Redis (e.g., `86400` for 24 hours).
*   `QUOTA_PREFIX`: Prefix for Redis keys used for daily quotas (e.g., `quota`).
*   `HEARTBEAT_INTERVAL_SECONDS`: Interval in seconds for sending heartbeat messages.
*   `CLIENT_CONFIG`: JSON string mapping API keys to client configurations (name, is\_active, daily\_quota).
*   `PROVIDERS_CONFIG`: JSON string mapping provider names to their configurations (is\_active, is\_operational, aliases, note).

## Run Commands (using top-level Makefile)

From the repository root:

*   **Build Docker image:** `make build`
*   **Start services (Server A, Redis, RabbitMQ):** `make up`
*   **Stop services:** `make down`
*   **View Server A logs:** `make logs`
*   **Run tests:** `make test`
*   **Lint code:** `make lint`
*   **Format code:** `make fmt`

## API Examples

### `POST /api/v1/sms/send`

Sends an SMS message.

**Headers:**

*   `API-Key`: Your client API key (required).
*   `Idempotency-Key`: A unique key for idempotent requests (optional, but recommended).

**Request Body (application/json):**

```json
{
  "to": "+1234567890",
  "text": "Your message content here.",
  "providers": ["ProviderA", "ProviderD"],
  "ttl_seconds": 3600
}
```

**Successful Response (202 Accepted):**

```json
{
  "success": true,
  "message": "Request accepted for processing.",
  "tracking_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

### Error Responses

All error responses follow the `ErrorResponse` schema:

```json
{
  "error_code": "ERROR_CODE",
  "message": "Human-readable error message.",
  "details": { /* optional additional details */ },
  "tracking_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "timestamp": "2023-10-27T10:00:00.000000"
}
```

**Common Error Codes:**

*   `UNAUTHORIZED` (HTTP 401): Missing or invalid API key, or inactive client.
*   `INVALID_PAYLOAD` (HTTP 422): Request body validation failed (e.g., invalid `to` format, `text` too long).
*   `UNKNOWN_PROVIDER` (HTTP 422): One or more requested providers are not configured.
*   `PROVIDER_DISABLED` (HTTP 409): The exclusively requested provider is disabled or not operational.
*   `ALL_PROVIDERS_DISABLED` (HTTP 409): All requested providers in a prioritized list are disabled or not operational.
*   `NO_PROVIDER_AVAILABLE` (HTTP 503): No active and operational providers are available for smart selection.
*   `TOO_MANY_REQUESTS` (HTTP 429): Client has exceeded their daily SMS quota.
*   `INTERNAL_ERROR` (HTTP 500): An unexpected server-side error occurred.

## Metrics

Prometheus metrics are exposed at `GET /metrics`.

Key metrics include:

*   `sms_providers_config_total`: Total number of SMS providers configured.
*   `sms_provider_active{provider}`: Gauge (0/1) indicating if a provider is active.
*   `sms_provider_operational{provider}`: Gauge (0/1) indicating if a provider is operational.
*   `sms_request_rejected_unknown_provider_total{client}`: Counter for requests rejected due to unknown providers.
*   `sms_request_rejected_provider_disabled_total{client,provider}`: Counter for requests rejected due to disabled providers.
*   `sms_request_rejected_no_provider_available_total{client}`: Counter for requests rejected due to no providers available.
*   `sms_config_fingerprint_mismatch_total{kind}`: Counter for configuration fingerprint mismatches.
*   `sms_send_requests_total`: Total number of `/api/v1/sms/send` requests.
*   `sms_send_request_latency_seconds`: Histogram for latency of `/api/v1/sms/send` requests.
*   `sms_send_request_success_total`: Total successful `/api/v1/sms/send` requests.
*   `sms_send_request_error_total`: Total failed `/api/v1/sms/send` requests.
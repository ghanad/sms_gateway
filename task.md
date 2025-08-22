
# LLM Implementation Prompt — **Server B** (Code-Only Output)

**Context:** Implement the **Server B (Processing Backend)** of the SMS API Gateway according to the design doc (v1.5). Server B consumes messages from RabbitMQ (produced by Server A), applies sending policies (Exclusive / Prioritized Failover / Smart Selection), integrates with provider adapters, persists state in PostgreSQL, exposes status & webhook endpoints, emits Prometheus metrics, and logs in JSON.

**Important constraints:**

* You **cannot** use a CLI or write files to disk.
* Output **all source files** as code blocks using the exact format below.
* **If you add or modify any functionality, you must also include tests for it.**

---

## Output Format (strict)

Produce code as a sequence of files, each in its own fenced code block:

```
# FILE: path/to/file.ext
<file content>
```

* Output **only files** (no prose between blocks).
* Include **every** file needed to run & test Server B inside a monorepo.
* Do **not** omit supporting files (Dockerfile, pyproject, alembic, compose updates, etc.).
* Keep filenames and paths exactly as specified below.

---

## Monorepo Layout (implement **server-b** fully; others placeholders if needed)

```
repo-root/
  server-a/                    # already exists (leave untouched)
  server-b/
    app/
      __init__.py
      main.py
      config.py
      logging.py
      metrics.py
      db.py
      models.py
      schemas.py
      repositories.py
      rabbit_consumer.py
      policy_engine.py
      provider_registry.py
      providers/
        __init__.py
        base.py
        provider_a.py
        local_sms.py
      webhooks.py
      status_api.py
      heartbeat_consumer.py
      utils.py
    migrations/
      env.py
      versions/               # include initial migration file(s)
    tests/
      test_policy_engine.py
      test_consumer_flow.py
      test_webhooks.py
      test_status_api.py
      conftest.py
    Dockerfile
    pyproject.toml
    README.md
  frontend/
    README.md                  # placeholder
  docker-compose.yml           # include server-b + postgres services
  .env.example                 # extend with SERVER_B_* and DB vars
  Makefile                     # targets for server-b (optional but preferred)
  README.md                    # repo overview (update if necessary)
```

> If a file already exists in your mental model, **output it anyway** (overwrite). This is a code-only environment; the consumer will create files from your blocks.

---

## Dependencies (keep minimal)

* Web/API: `fastapi`, `uvicorn[standard]`
* Async AMQP: `aio-pika`
* DB/ORM/Migrations: `SQLAlchemy[asyncio]`, `asyncpg`, `alembic`
* HTTP client for providers: `httpx`
* Observability: `prometheus-client`, `python-json-logger`
* Dev/test: `pytest`, `pytest-asyncio`

No unnecessary extras.

---

## Environment Variables (in `.env.example` at repo root)

```
# Server B
SERVICE_NAME=server-b
SERVER_B_HOST=0.0.0.0
SERVER_B_PORT=9000

# Rabbit
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
RABBITMQ_QUEUE_OUTBOUND=sms.outbound
RABBITMQ_QUEUE_HEARTBEAT=a.heartbeat
RABBITMQ_PREFETCH=32

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/smsgw

# Policy & TTL
MAX_SEND_ATTEMPTS=10
DEFAULT_TTL_SECONDS=3600
MIN_TTL_SECONDS=10
MAX_TTL_SECONDS=86400

# Provider selection
SMART_SELECTION_STRATEGY=priority    # priority | round_robin
PROVIDER_DEFAULT_PRIORITY=100

# Optional baseline fingerprints (for heartbeat comparison)
EXPECTED_CLIENTS_FINGERPRINT=
EXPECTED_PROVIDERS_FINGERPRINT=
```

---

## Functional Requirements

### Messaging & Processing

* Consume JSON envelopes from `RABBITMQ_QUEUE_OUTBOUND` with fields:

  * `tracking_id`, `client_key`, `to`, `text`, `ttl_seconds`,
  * `providers_original?`, `providers_effective?`,
  * `config_fingerprint: {clients, providers}`, `created_at` (ISO8601).
* **Policy Engine:**

  * If `providers_effective` provided:

    * **Exclusive**: exactly one entry; if disabled → **fail** (do not override).
    * **Prioritized**: ordered list; skip disabled; if empty → **fail**.
  * Else **Smart Selection**: choose among enabled providers by **priority** (or round\_robin if configured).
  * Enforce TTL: if expired → mark **FAILED (expired)**.
  * Respect `MAX_SEND_ATTEMPTS` using Rabbit’s `x-death` (or header) for attempt count.
* Provider adapters:

  * `providers/base.py` defines async interface + result model.
  * `provider_a.py`: sample HTTP adapter (read API base/key from env; mockable).
  * `local_sms.py`: simulated success adapter (offline).
* On temporary failures: schedule retry with **exponential backoff** via DLX/TTL or requeue strategy; on permanent failure, switch provider (prioritized) or mark FAILED.
* Persist states/events in PostgreSQL (`messages`, `message_events`).

### HTTP API

* `GET /api/status/{tracking_id}`: return status + recent events.
* `POST /webhooks/delivery-report/{provider}`: accept DLR, map to internal events, update `DELIVERED`/`FAILED`.
* `GET /metrics`: Prometheus metrics.
* `GET /healthz`, `GET /readyz`: liveness/readiness (DB reachable).

### Observability

* **JSON logs** (python-json-logger) with `service`, `timestamp`, `level`, and when available: `tracking_id`, `provider`, `client_key`.
* **Prometheus metrics:**

  * `sms_messages_total{status}`
  * `sms_processing_latency_seconds`
  * `sms_provider_attempts_total{provider,outcome}`
  * `sms_provider_switch_total{from,to}`
  * `sms_retry_scheduled_total`
  * `sms_config_fingerprint_mismatch_total{kind}`
  * `server_a_heartbeat_last_ts` (gauge)
  * `db_write_errors_total`, `db_latency_seconds`

### Heartbeat

* Consumer for `RABBITMQ_QUEUE_HEARTBEAT` to read heartbeats from A, compare fingerprints if `EXPECTED_*` envs provided, update metric & log warning on mismatch.

### Database (async SQLAlchemy + Alembic)

* `messages`:

  * `id` (PK), `tracking_id` (UUID unique), `client_key`, `to`, `text`, `ttl_seconds`,
  * `provider_final` (nullable), `status` (ENUM: QUEUED, PROCESSING, SENT, FAILED, DELIVERED),
  * `created_at`, `updated_at`
* `message_events`:

  * `id` (PK), `tracking_id` (FK), `event_type` (PROCESSING, SENT, FAILED, DELIVERED, PROVIDER\_SWITCHED, RETRY\_SCHEDULED),
  * `provider`, `details` (JSON), `created_at`
* Include Alembic env + initial migration(s).

### Dockerization & Compose

* `server-b/Dockerfile` (python:3.12-slim).
* Extend top-level `docker-compose.yml`: add **postgres** & **server-b** services (ports 5432 & 9000).
* Ensure graceful startup/shutdown.

---

## Tests (mandatory)

For **every new or changed module/function**, include tests. Provide at least:

1. **Policy Engine** (`test_policy_engine.py`)

   * Exclusive disabled → immediate fail.
   * Prioritized: skip disabled, preserve order; if empty → fail.
   * Smart selection (priority & round\_robin).
   * TTL expiry → fail (expired).

2. **Consumer Flow** (`test_consumer_flow.py`)

   * Mock provider adapters & AMQP channel; on temp fail schedule retry; on success → SENT; on permanent failure with prioritized → switch then finalize.

3. **Webhooks** (`test_webhooks.py`)

   * Normalize provider payload → update `DELIVERED`.

4. **Status API** (`test_status_api.py`)

   * Return status & ordered events.

5. **DB & Migrations** (in tests or fixture)

   * Apply migrations to a test DB (sqlite in-memory for unit tests, or mark async postgres tests and mock DB layer).

> Tests must be runnable without external internet; **mock outbound HTTP** (provider\_a).

---

## Acceptance Criteria

* Code compiles and is importable.
* All endpoints present and wired.
* Consumer consumes messages, applies policies, persists states, and handles retries/backoff.
* Metrics exposed and counters updated on key events.
* Logs are structured JSON with context fields.
* Tests cover core logic and any added functionality.

---

## Deliverables (print ALL these files)

You **must** output all of the following (filled with working code):

1. `server-b/pyproject.toml`
2. `server-b/Dockerfile`
3. `server-b/app/__init__.py`
4. `server-b/app/main.py`
5. `server-b/app/config.py`
6. `server-b/app/logging.py`
7. `server-b/app/metrics.py`
8. `server-b/app/db.py`
9. `server-b/app/models.py`
10. `server-b/app/schemas.py`
11. `server-b/app/repositories.py`
12. `server-b/app/policy_engine.py`
13. `server-b/app/provider_registry.py`
14. `server-b/app/providers/__init__.py`
15. `server-b/app/providers/base.py`
16. `server-b/app/providers/provider_a.py`
17. `server-b/app/providers/local_sms.py`
18. `server-b/app/rabbit_consumer.py`
19. `server-b/app/webhooks.py`
20. `server-b/app/status_api.py`
21. `server-b/app/heartbeat_consumer.py`
22. `server-b/app/utils.py`
23. `server-b/migrations/env.py`
24. `server-b/migrations/versions/<timestamp>_initial.py` (use any timestamp prefix)
25. `server-b/tests/conftest.py`
26. `server-b/tests/test_policy_engine.py`
27. `server-b/tests/test_consumer_flow.py`
28. `server-b/tests/test_webhooks.py`
29. `server-b/tests/test_status_api.py`
30. `server-b/README.md`
31. Root `docker-compose.yml` (with postgres & server-b services)
32. Root `.env.example` (extended with SERVER\_B\_\* and DB vars)
33. Root `README.md` (updated overview)
34. Root `Makefile` (optional but preferred: logs-b, test-b targets)

If you introduce any extra helper modules or configs, **also** provide corresponding tests.

---

## Notes

* Use **UUID v4** for `tracking_id` (do not regenerate if provided).
* Backoff can be a simple exponential formula; document it in code comments.
* Keep adapters minimal but testable; no real internet in tests—**mock httpx**.
* Keep interfaces clean so real providers can be added later without changing core logic.


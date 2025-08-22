

# LLM Implementation Prompt — **Server A** of SMS API Gateway

**Context:** Implement the **Server A (API Gateway)** component in Python/FastAPI based on the architecture spec. The system is an internal SMS gateway with strict network isolation. **Only Server A** is in scope now; create minimal placeholders for **Server B** and **Frontend** so the repo is a monorepo. Provide Docker/Compose to run Server A with Redis & RabbitMQ locally.

## Output Format (important)

Produce code as a sequence of files, each in its own fenced code block:

```
# FILE: path/to/file.ext
<file content>
```

Only include files you create. No explanations between files.

---

## Global Constraints

* **Language/Framework:** Python 3.12, FastAPI, Uvicorn.
* **Dependencies (keep minimal):**
  `fastapi`, `uvicorn[standard]`, `pydantic`, `redis>=5,<6` (async), `aio-pika`, `prometheus-client`, `python-json-logger`, `python-dotenv` (load .env in dev).
  *Avoid extra libs beyond these.*
* **Architecture truths:**

  * Server A is in the **internal network** and has **no direct internet** dependency in production.
  * Communication with Server B is **one-way** via RabbitMQ (A → B).
* **Behavioral priorities:** Fast-Fail, Idempotency, Daily Quota, Provider Gate rules, JSON logs with `tracking_id`, Prometheus metrics.
* **Do not** implement Server B logic or any outbound HTTP to providers; only enqueue to RabbitMQ.
* **Testing:** Use `pytest` with realistic unit tests for core logic.
* **Style:** Type hints everywhere, PEP8, modular structure.

---

## Repository Layout (monorepo)

Create this tree; **fully implement only `server-a`**. Others are placeholders:

```
repo-root/
  server-a/
    app/
      __init__.py
      main.py
      config.py
      logging.py
      metrics.py
      auth.py
      schemas.py
      provider_gate.py
      quota.py
      idempotency.py
      rabbit.py
      heartbeat.py
      utils.py
    tests/
      test_provider_gate.py
      test_idempotency.py
      test_quota.py
      test_send_endpoint.py
    Dockerfile
    pyproject.toml
    README.md
  server-b/
    README.md
  frontend/
    README.md
  docker-compose.yml
  .env.example
  Makefile
  README.md
```

---

## Task 0 — Bootstrap Monorepo

* Create the structure above.
* Top-level `README.md` with quickstart and repository overview.
* Top-level `Makefile` targets: `build`, `up`, `down`, `logs`, `lint`, `fmt`, `test`.
* `docker-compose.yml` to run:

  * `server-a` (built from `server-a/Dockerfile`)
  * `redis`
  * `rabbitmq` (management UI enabled on 15672)
* `.env.example` at repo root with all variables Server A needs.

---

## Task 1 — Configuration & Fingerprints

* Implement `app/config.py` to load **environment variables** (from `.env` in dev):

  * `SERVICE_NAME=server-a`
  * `SERVER_A_HOST=0.0.0.0`
  * `SERVER_A_PORT=8000`
  * `REDIS_URL=redis://redis:6379/0`
  * `RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/`
  * `PROVIDER_GATE_ENABLED=true`
  * `IDEMPOTENCY_TTL_SECONDS=86400` (24h)
  * `QUOTA_PREFIX=quota`
  * `HEARTBEAT_INTERVAL_SECONDS=60`
  * `CLIENT_CONFIG` — JSON string mapping api\_key → { name, is\_active, daily\_quota }
  * `PROVIDERS_CONFIG` — JSON string mapping provider name → { is\_active, is\_operational, aliases?, note? }
* Parse JSON into Pydantic models. **Fail fast on startup** if invalid.
* Compute **fingerprints**: SHA-256 of the **raw JSON strings** for `CLIENT_CONFIG` and `PROVIDERS_CONFIG`; expose in config.
* Build a **case-insensitive alias map** for providers; reject alias collisions.

---

## Task 2 — Logging (JSON) & Metrics

* `app/logging.py`: configure `python-json-logger` for structured logs; always include fields:

  * `service`, `level`, `timestamp`, `message`, and if available `tracking_id`, `client_api_key`.
* `app/metrics.py`: expose Prometheus metrics at `GET /metrics`.
  Define counters/gauges (names exact):

  * `sms_providers_config_total`
  * `sms_provider_active{provider}` (0/1 gauge)
  * `sms_provider_operational{provider}` (0/1 gauge)
  * `sms_request_rejected_unknown_provider_total{client}`
  * `sms_request_rejected_provider_disabled_total{client,provider}`
  * `sms_request_rejected_no_provider_available_total{client}`
  * `sms_config_fingerprint_mismatch_total{kind}` (placeholder increment; B will actually compare)
  * Plus: request counters and latency summary for `/api/v1/sms/send`.

---

## Task 3 — Authentication (API Key)

* `app/auth.py`: FastAPI dependency that:

  * Reads `API-Key` header.
  * Looks up in loaded `CLIENT_CONFIG`.
  * If missing/invalid or `is_active=false` → `401 Unauthorized`.
  * On success, attach `client` context (name, key, daily\_quota) to request state.

---

## Task 4 — Request Schema & Validation

* `app/schemas.py` define:

  * `SendSmsRequest` with fields:
    `to: str`, `text: str`, `providers: list[str] | None = None`, `ttl_seconds: int | None = None`

    * Validate `to` with E.164 (accept +98… etc.).
    * `text` max length (e.g., 1000).
    * `ttl_seconds`: min 10, max 86400; default 3600 if not provided.
  * `SendSmsResponse`: `{ success: bool, message: str, tracking_id: str }`
  * `ErrorResponse` schema: `{ error_code, message, details?, tracking_id?, timestamp }`

---

## Task 5 — Idempotency (Redis)

* `app/idempotency.py`:

  * Read `Idempotency-Key` header (optional but recommended).
  * If present:

    * On first successful processing: **cache the full HTTP response** body + status for **TTL=IDEMPOTENCY\_TTL\_SECONDS**.
    * On subsequent identical key: **return cached response** (success or error) without reprocessing.
  * Must be safe for concurrent requests (use Redis SETNX or Lua script semantics).
  * Key space: `idem:{api_key}:{idempotency_key}`.

---

## Task 6 — Provider Gate (Fast-Fail) **(critical)**

* `app/provider_gate.py`:

  * Map input `providers` (case-insensitive) to canonical names via aliases; **unknown** → HTTP 422 with `error_code="UNKNOWN_PROVIDER"` and allowed names list.
  * **Smart Selection** (no providers provided):

    * If **no provider** with `is_active && is_operational` exists in config → HTTP 503 with `error_code="NO_PROVIDER_AVAILABLE"`. Otherwise pass through (effective list stays empty; B will choose later).
  * **Exclusive** (exactly one):

    * If that provider not `(is_active && is_operational)` → HTTP 409 with `error_code="PROVIDER_DISABLED"`.
  * **Prioritized Failover** (more than one):

    * Filter out providers not `(is_active && is_operational)` preserving order.
    * If resulting list is empty → HTTP 409 with `error_code="ALL_PROVIDERS_DISABLED"`.
* **Placement in pipeline:** Run **before quota** to avoid consuming quota for doomed requests.
* Emit metrics and a structured log event `provider_gate.blocked` for rejections.

---

## Task 7 — Quota (Daily, Redis)

* `app/quota.py`:

  * After Provider Gate, enforce per-client **daily quota** using Redis atomic counters.
  * Key: `{QUOTA_PREFIX}:{client_key}:{YYYY-MM-DD}`
  * If exceeding `daily_quota` → HTTP 429 Too Many Requests.
  * Counters expire automatically after 24h.
  * Ensure **requests rejected by Provider Gate do not consume quota**.

---

## Task 8 — RabbitMQ Publishing (A → B)

* `app/rabbit.py`:

  * Use `aio-pika` to publish **durable** messages with `delivery_mode=2`.
  * Declare an exchange/queue pair for outbound messages (simple default direct or use default exchange and named queue).
  * **Envelope** (JSON) must include:

    * `tracking_id` (uuid4)
    * `client_key`
    * `to`, `text`
    * `ttl_seconds`
    * `providers_original` (if user provided)
    * `providers_effective` (filtered; empty list means Smart Selection)
    * `config_fingerprint`: `{ clients: <sha256>, providers: <sha256> }`
    * `created_at` (UTC ISO8601)
* Do **not** access internet or provider APIs here.

---

## Task 9 — Heartbeat (A → B)

* `app/heartbeat.py`:

  * Background task sending a small message to a dedicated heartbeat queue every `HEARTBEAT_INTERVAL_SECONDS` with:

    * `service="server-a"`, `ts`, `config_fingerprint.clients`, `config_fingerprint.providers`.
  * If publish fails, log error (JSON) and continue retrying with backoff internally.

---

## Task 10 — HTTP API (Server A)

* `app/main.py`:

  * Router: `POST /api/v1/sms/send`

    1. **Idempotency pre-check** (short-circuit on cached response).
    2. **Authentication** (API-Key).
    3. **Payload validation** (Pydantic model).
    4. **Provider Gate** (fast-fail).
    5. **Quota** check (increment on success path).
    6. Generate `tracking_id` (uuid4).
    7. Publish envelope to RabbitMQ.
    8. **Store response** for idempotency if key present.
    9. Return **202 Accepted** with body:

       ```json
       { "success": true, "message": "Request accepted for processing.", "tracking_id": "<uuid>" }
       ```
  * Health endpoints:

    * `GET /healthz` (liveness: returns 200 if app thread alive).
    * `GET /readyz` (readiness: verify Redis and RabbitMQ connections).
  * `GET /metrics` (Prometheus via `metrics.py`).
* **Error model:** Always return structured error JSON:

  * `error_code` ∈ { `UNKNOWN_PROVIDER`, `PROVIDER_DISABLED`, `ALL_PROVIDERS_DISABLED`, `NO_PROVIDER_AVAILABLE`, `UNAUTHORIZED`, `TOO_MANY_REQUESTS`, `INVALID_PAYLOAD`, `INTERNAL_ERROR` }
  * Include `tracking_id` **if it was generated**.

---

## Task 11 — Dockerization & Compose

* `server-a/Dockerfile`:

  * Base `python:3.12-slim`, install build deps minimally, add non-root user.
  * Copy `pyproject.toml` (or `requirements.txt`) then `pip install`.
  * Copy app, set working dir, `uvicorn app.main:app --host 0.0.0.0 --port ${SERVER_A_PORT}` as CMD.
* Top-level `docker-compose.yml`:

  * `server-a` service uses `.env` from repo root.
  * `redis` service.
  * `rabbitmq` service with management UI (ports 5672, 15672).
* Ensure **graceful shutdown** (SIGTERM) and fast startup checks.

---

## Task 12 — Testing (pytest)

Create tests to cover:

1. **Provider Gate:**

   * Unknown provider → 422 `UNKNOWN_PROVIDER`.
   * Smart Selection with no active providers → 503 `NO_PROVIDER_AVAILABLE`.
   * Exclusive disabled → 409 `PROVIDER_DISABLED`.
   * Prioritized mix → correct filtered order; empty after filter → 409 `ALL_PROVIDERS_DISABLED`.
2. **Idempotency:**

   * First call stores response; second call with same `Idempotency-Key` returns exact cached response (both success and error paths).
3. **Quota:**

   * Enforce daily quota; ensure Provider Gate rejections do **not** increment quota.
4. **Send Endpoint end-to-end (without real B):**

   * Publishes a message to RabbitMQ (use a test queue or mock `aio-pika`).
   * Returns 202 with `tracking_id`.
5. **Health/Readiness**:

   * Ready only when Redis & Rabbit are reachable.

---

## Task 13 — Documentation

* `server-a/README.md`: setup, environment variables, run commands, error codes, metrics list, and API examples.
* Top-level `README.md`: monorepo overview, how to add Server B & Frontend later.

---

## Task 14 — Makefile & Dev Ergonomics

* `Makefile` targets:

  * `build`: `docker compose build`
  * `up`: `docker compose up -d`
  * `down`: `docker compose down -v`
  * `logs`: `docker compose logs -f server-a`
  * `test`: run pytest inside container or via `docker compose run --rm server-a pytest`
  * `fmt`: run `python -m pip install ruff black && ruff check --fix . && black .` (optional if you add these in dev only)
  * `lint`: run `ruff check .`
* (Optional) dev-only dependencies for lint/format can be added to `pyproject.toml` under extras.

---

## Acceptance Criteria

* Running `docker compose up --build` starts `server-a`, `redis`, `rabbitmq`.
* `POST /api/v1/sms/send`:

  * Applies Idempotency → Auth → Validation → **Provider Gate** → **Quota** → Publish → 202.
  * Returns structured JSON with `tracking_id`.
* Provider Gate enforces:

  * Smart Selection requires at least one **active & operational** provider in config.
  * Exclusive rejects disabled providers.
  * Prioritized removes disabled providers, preserves order, rejects if empty.
* Redis used for both **idempotency** and **daily quota**.
* RabbitMQ publishes **durable** messages with the specified **envelope**.
* Logs are **JSON** and include `tracking_id` when available.
* `/metrics` exposes Prometheus metrics including the ones listed.
* Tests cover key paths and pass locally.
* No extra dependencies beyond those listed.

---

## Seed `.env.example` (place at repo root)

```
SERVICE_NAME=server-a
SERVER_A_HOST=0.0.0.0
SERVER_A_PORT=8000
REDIS_URL=redis://redis:6379/0
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
PROVIDER_GATE_ENABLED=true
IDEMPOTENCY_TTL_SECONDS=86400
QUOTA_PREFIX=quota
HEARTBEAT_INTERVAL_SECONDS=60
CLIENT_CONFIG={"api_key_for_service_A":{"name":"Financial Service","is_active":true,"daily_quota":1000}}
PROVIDERS_CONFIG={
  "Provider-A":{"is_active":true,"is_operational":true,"aliases":["provider-a","PROVIDER_A"],"note":"active"},
  "Provider-B":{"is_active":false,"is_operational":false,"note":"disabled"},
  "Local-SMS":{"is_active":true,"is_operational":true,"note":"offline module"}
}
```

---

## Notes for the LLM

* **Do not** implement Server B or Frontend; just provide simple `README.md` placeholders there.
* Remember: **requests rejected by Provider Gate must not consume quota**.
* For **idempotency**, cache **both** success and error responses.
* Use **UUID v4** for `tracking_id`.
* Ensure all error responses follow the unified error schema and use appropriate HTTP status codes:

  * 422 `UNKNOWN_PROVIDER`
  * 409 `PROVIDER_DISABLED` / `ALL_PROVIDERS_DISABLED`
  * 503 `NO_PROVIDER_AVAILABLE`
  * 401 `UNAUTHORIZED`
  * 429 `TOO_MANY_REQUESTS`
  * 400 `INVALID_PAYLOAD`
  * 500 `INTERNAL_ERROR`


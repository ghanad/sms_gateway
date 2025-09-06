# SMS API Gateway Monorepo

This repository contains a complete, scalable, and reliable SMS API Gateway system. It is designed with a microservices architecture to decouple the API ingress from the core message processing logic, ensuring high availability and zero message loss.

## Architecture Overview

The system consists of two primary services that communicate asynchronously via a message broker. This design ensures that incoming requests are handled quickly while the actual sending of the SMS is performed reliably in the background.

1.  **Server A (API Gateway)**: A high-performance gateway built with **FastAPI**. It is responsible for handling all incoming API requests. Its duties include authentication, request validation, idempotency checks, quota enforcement, and publishing messages to a **RabbitMQ** queue.
2.  **Server B (Backend Worker)**: A robust backend built with **Django** and **Celery**. It consumes messages from the queue, persists them to a **PostgreSQL** database, applies provider selection and failover logic, and sends the SMS through the appropriate provider adapter. It also exposes APIs for message status and webhooks.


## Key Features

*   **High Performance**: Asynchronous API gateway built on FastAPI for fast request handling.
*   **Reliable Processing**: Guaranteed message delivery with a transactional hand-off from the message queue to the database.
*   **Scalable Workers**: Background processing is handled by Celery workers, which can be scaled independently.
*   **Provider Abstraction**: Easily integrate new SMS providers by creating simple adapter classes.
*   **Authentication & Quotas**: Secure API endpoints with API Key authentication and per-client daily quotas.
*   **Idempotency**: Prevents duplicate message processing with `Idempotency-Key` header support, powered by Redis.
*   **Smart Routing & Failover**: Intelligently selects the best provider or follows a user-defined priority list, with built-in retries for transient failures.
*   **Observability**: Structured JSON logging and Prometheus metrics for monitoring.
*   **Web Interface**: A simple web UI for managing users, providers, and viewing message history.

## Getting Started

### Prerequisites

*   Docker
*   Docker Compose
*   `make` (optional, for convenience)

### 1. Configuration

Copy the example environment file and customize it if needed. The default values are configured to work out-of-the-box with Docker Compose.

```bash
cp .env.example .env
```

### 2. Build and Run

Use the Makefile to build the Docker images and start all services in detached mode.

```bash
make up
```

This command will start:
*   `server-a` (API Gateway) on `http://localhost:8001`
*   `server-b` (Django Backend) on `http://localhost:9000`
*   `rabbitmq` with management UI on `http://localhost:15672`
*   `redis` on `localhost:6379`
*   `postgres` on `localhost:5432`

### 3. Accessing Services

*   **API Gateway (Server A)**: `http://localhost:8001`
*   **Backend UI (Server B)**: `http://localhost:9000`
*   **RabbitMQ Management**: `http://localhost:15672` (user: `guest`, pass: `guest`)

## Usage Example

A Python script `send_sms.py` is provided in the root directory to demonstrate how to send an SMS through the gateway.

1.  **Configure the script**: Open `send_sms.py` and set the `API_KEY`. The default key for the bootstrapped user is `b57410a7-ea73-4b3d-811f-daa0bb565500`.

    ```python
    # send_sms.py
    SERVER_A_URL = 'http://localhost:8001'
    API_KEY = 'b57410a7-ea73-4b3d-811f-daa0bb565500'
    ```

2.  **Run the script**:

    ```bash
    python send_sms.py
    ```

You will see a confirmation that the request was accepted, along with a `tracking_id` which you can use to trace the message.

## Makefile Commands

The `Makefile` provides several useful commands for managing the project:

| Command      | Description                                                    |
| :----------- | :------------------------------------------------------------- |
| `make build` | Builds all necessary Docker images.                            |
| `make up`    | Starts all services in detached mode.                          |
| `make down`  | Stops and removes all services, containers, and networks.      |
| `make logs`  | Tails the logs for `server-a`.                                 |
| `make logs-b`| Tails the logs for `server-b`.                                 |
| `make test`  | Runs the test suite for `server-a`.                            |
| `make test-b`| Runs the test suite for `server-b`.                            |
| `make lint`  | Lints the Python code in `server-a`.                           |
| `make fmt`   | Formats the Python code in `server-a`.                         |

## API Error Reference

All error responses from Server A follow a standard format. The `tracking_id` field will be included if the request processing reached a point where it was generated.

```json
{
  "error_code": "ERROR_CODE",
  "message": "Human-readable error message.",
  "details": { /* optional additional details */ },
  "tracking_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "timestamp": "2023-10-27T10:00:00.000000"
}
```

Here is a list of common error codes:

| Error Code               | HTTP Status | Description                                                                                             |
| :----------------------- | :---------- | :------------------------------------------------------------------------------------------------------ |
| `UNAUTHORIZED`           | 401         | The `API-Key` header is missing, invalid, or the client account is inactive.                            |
| `INVALID_PAYLOAD`        | 422         | The request body failed validation (e.g., invalid phone number format, text is too long).               |
| `UNKNOWN_PROVIDER`       | 422         | One or more of the requested providers in the `providers` list are not configured in the system.        |
| `PROVIDER_DISABLED`      | 409         | The exclusively requested provider is currently disabled or not operational.                            |
| `ALL_PROVIDERS_DISABLED` | 409         | All providers in the prioritized list are disabled or not operational.                                  |
| `NO_PROVIDER_AVAILABLE`  | 503         | No active and operational providers are available for smart selection (when `providers` list is empty). |
| `TOO_MANY_REQUESTS`      | 429         | The client has exceeded their configured daily SMS quota.                                               |
| `INTERNAL_ERROR`         | 500         | An unexpected server-side error occurred.                                                               |

## Further Reading

For more detailed technical information, please refer to the documents in the `/docs` directory:
*   **Provider Integration**: A guide on how to add a new SMS provider to the system.
*   **SMS Processing Architecture**: A deep dive into the message lifecycle and failure handling logic.
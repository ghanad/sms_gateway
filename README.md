# SMS API Gateway Monorepo

This repository contains the components for an internal SMS API Gateway.

## Components

* **server-a**: API Gateway (FastAPI) that enqueues messages to RabbitMQ.
* **server-b**: Backend worker that consumes messages, applies provider policies, persists state in PostgreSQL and exposes status and webhook APIs.
* **frontend**: Placeholder for future interface.

## Quickstart

1. **Prerequisites:** Docker and Docker Compose.
2. **Environment Variables:**
   ```bash
   cp .env.example .env
   ```
3. **Build and Run:**
   ```bash
   make up
   ```
   This starts Server A, Server B, Redis, RabbitMQ and PostgreSQL.

## Makefile Targets

* `build`: Builds Docker images.
* `up`: Starts services in detached mode.
* `down`: Stops and removes services.
* `logs`: Follows Server A logs.
* `logs-b`: Follows Server B logs.
* `lint`: Lints Server A.
* `fmt`: Formats Server A.
* `test`: Runs Server A tests.
* `test-b`: Runs Server B tests.

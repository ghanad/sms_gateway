# SMS API Gateway Monorepo

This repository contains the components for an internal SMS API Gateway.

## Components

* **server-a**: API Gateway (FastAPI) that enqueues messages to RabbitMQ.
* **server-b**: Backend worker that consumes messages, applies provider policies, persists state in PostgreSQL and exposes status and webhook APIs.
* **frontend**: React + Vite web interface.

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
   This starts Server A, Server B, the Frontend, Redis, RabbitMQ and PostgreSQL.

## Using Your Server IP

Services listen on `0.0.0.0` by default, so you can access them from other machines by using the server's IP address.

1. Ensure `.env` contains `SERVER_A_HOST=0.0.0.0` and `SERVER_B_HOST=0.0.0.0` (these are the defaults).
2. Start the stack with `make up`.
3. From your client or browser, replace `localhost` with the server's IP:

   ```text
   http://<your-server-ip>:8000  # Server A API
   http://<your-server-ip>:9000  # Server B API
   ```

   If you run the frontend separately, set `VITE_API_BASE_URL` to `http://<your-server-ip>:9000` before building or running it.

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

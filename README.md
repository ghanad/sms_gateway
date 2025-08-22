# SMS API Gateway Monorepo

This repository contains the components for an internal SMS API Gateway.

## Components

*   **server-a**: The API Gateway component (FastAPI). Handles incoming SMS requests, authentication, validation, provider routing, quota management, and enqueues messages to RabbitMQ for Server B.
*   **server-b**: (Placeholder) The backend worker that processes messages from RabbitMQ and dispatches them to external SMS providers.
*   **frontend**: (Placeholder) A potential future web interface for managing the SMS gateway.

## Quickstart

To get Server A, Redis, and RabbitMQ running locally using Docker Compose:

1.  **Prerequisites:** Ensure Docker and Docker Compose are installed.
2.  **Environment Variables:** Copy `.env.example` to `.env` and adjust as needed.
    ```bash
    cp .env.example .env
    ```
3.  **Build and Run:**
    ```bash
    make up
    ```
    This will build the `server-a` Docker image and start all services.

## Makefile Targets

*   `build`: Builds the Docker images.
*   `up`: Starts the Docker Compose services in detached mode.
*   `down`: Stops and removes the Docker Compose services and volumes.
*   `logs`: Follows the logs of the `server-a` service.
*   `lint`: Runs linting checks on `server-a`.
*   `fmt`: Formats the code for `server-a`.
*   `test`: Runs tests for `server-a`.

## Adding Server B & Frontend

*   **Server B:** To implement Server B, create a new directory `server-b/app` and add your Python/FastAPI application logic there. Update `docker-compose.yml` to include Server B as a service.
*   **Frontend:** To implement the Frontend, create your web application files in the `frontend/` directory. You may need to add a new service to `docker-compose.yml` if it requires a build step or a specific server.
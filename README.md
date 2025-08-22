# SMS API Gateway Monorepo

This repository contains the components for an internal SMS API Gateway.

## Components

- **server-a**: FastAPI gateway handling incoming SMS requests and queuing.
- **server-b**: Placeholder backend worker.
- **frontend**: React + Vite web interface for administration.

## Quickstart

1. Copy `.env.example` to `.env` and adjust values.
2. Build and run services:

```bash
make up
```

The compose stack includes Server A, Redis, RabbitMQ, Server B placeholder, and the frontend.

## Makefile Targets

- `build`: Builds the Docker images.
- `up`: Starts the Docker Compose services in detached mode.
- `down`: Stops and removes the services and volumes.
- `logs`: Follows Server A logs.
- `lint`: Runs linting for Server A.
- `fmt`: Formats Server A code.
- `test`: Runs Server A tests.

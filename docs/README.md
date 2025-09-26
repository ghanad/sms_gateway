# SMS API Gateway Monorepo

## 1. Overview

This repository contains a complete, scalable, and highly reliable SMS API Gateway system. It is designed with a decoupled, microservices-based architecture to ensure high availability, fault tolerance, and zero message loss.

The system separates the high-throughput API ingress from the complex, stateful logic of message processing and delivery. Communication between services is handled asynchronously via a message broker, ensuring that API requests are processed swiftly while the actual SMS dispatch is performed reliably in the background.

## 2. Architecture

The system consists of two primary services, **Server A** and **Server B**, which operate independently and communicate through **RabbitMQ**. This design pattern isolates responsibilities, enhances scalability, and improves resilience.

**Important Note**: Server B does not have direct access to Server A. Communication is unidirectional from Server A to Server B via RabbitMQ.


*(A conceptual diagram representing the flow: Client -> Server A -> RabbitMQ -> Server B -> SMS Provider)*

*   **Server A (API Gateway)**: A high-performance, stateless gateway built with **FastAPI**. It serves as the single entry point for all incoming API requests. Its sole responsibility is to validate requests, enforce security policies, and quickly publish a message to the broker.
*   **RabbitMQ (Message Broker)**: The central message bus that decouples the two services. It guarantees that messages from Server A are durably queued until they can be safely consumed by Server B.
*   **Server B (Backend Worker & State Manager)**: A robust, stateful backend built with **Django** and **Celery**. It consumes messages from the queue, persists them to a **PostgreSQL** database (the single source of truth), and manages the entire lifecycle of sending the SMS. This includes provider selection, failover logic, and executing retries for transient failures. It also provides a web interface for administration.
*   **PostgreSQL (Database)**: The primary data store for all messages, user accounts, and provider configurations.
*   **Redis**: Used for caching, idempotency checks, and managing daily client quotas.

## 3. Core Features

*   **High Performance**: Asynchronous API gateway built on FastAPI for non-blocking I/O and rapid request handling.
*   **Guaranteed Message Delivery**: A message is only acknowledged and removed from RabbitMQ *after* it has been successfully committed to the PostgreSQL database, eliminating the risk of message loss.
*   **Scalable Workers**: Background processing is handled by Celery workers, which can be scaled horizontally and independently of the API gateway to handle varying loads.
*   **Abstracted Provider Layer**: Easily integrate new SMS providers by creating simple adapter classes without altering core business logic.
*   **Smart Routing & Failover**:
    *   If a user specifies a list of providers, the system honors that list exclusively.
    *   If no providers are specified, the system performs "smart selection," attempting delivery across all active providers based on a predefined priority.
    *   Built-in retry mechanism with exponential backoff for transient provider failures.
*   **Robust Security**:
    *   **Authentication**: Secure API endpoints with `API-Key` authentication.
    *   **Quotas**: Enforces per-client daily SMS quotas using Redis for high-speed atomic operations.
*   **Idempotency**: Prevents duplicate message processing for safe API retries via the `Idempotency-Key` header, backed by Redis.
*   **Full Observability**:
    *   **Structured Logging**: All logs are in JSON format, enriched with a `tracking_id` for easy tracing across services.
    *   **Prometheus Metrics**: Both services expose a `/metrics` endpoint for detailed monitoring of application health and business KPIs.
*   **Web Interface**: A simple Django-based UI for managing users, configuring SMS providers, and viewing message history.

## 4. Technology Stack

*   **Backend**: Python 3.12
*   **API Gateway (Server A)**: FastAPI, Uvicorn
*   **Backend Worker (Server B)**: Django, Celery, Gunicorn
*   **Message Broker**: RabbitMQ
*   **Database**: PostgreSQL
*   **In-Memory Cache**: Redis
*   **Containerization**: Docker, Docker Compose
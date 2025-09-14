import logging
import asyncio
import json
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional
from uuid import uuid4, UUID
import dataclasses
import os # Import os module

import aio_pika
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, Body
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from prometheus_client import Summary

from app.config import get_settings
from app.logging import setup_logging
from app.metrics import (
    metrics_content,
    SMS_SEND_REQUESTS_TOTAL,
    SMS_SEND_REQUEST_LATENCY_SECONDS,
    SMS_SEND_REQUEST_SUCCESS_TOTAL,
    SMS_SEND_REQUEST_ERROR_TOTAL
)
from app.auth import get_client_context, ClientContext
from app.schemas import SendSmsRequest, SendSmsResponse, ErrorResponse
from app.idempotency import idempotency_middleware, get_redis_client
from app.provider_gate import provider_gate
from app.quota import enforce_daily_quota
from app.rabbit import publish_sms_message, get_rabbitmq_connection, RABBITMQ_QUEUE_NAME, RABBITMQ_EXCHANGE_NAME
from app.consumers import consume_config_state
from app.cache import load_state_from_file, apply_state, save_state_to_file
from app.heartbeat import start_heartbeat_task, HEARTBEAT_QUEUE_NAME, HEARTBEAT_EXCHANGE_NAME

# Setup logging as early as possible
setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

# Global Redis and RabbitMQ connections
redis_client: Optional[Redis] = None
rabbitmq_connection: Optional[aio_pika.Connection] = None
rabbitmq_channel: Optional[aio_pika.Channel] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, rabbitmq_connection, rabbitmq_channel

    logger.info("Starting up Server A application...")

    # Log environment variables used by Settings
    logger.info(f"APP_NAME: {os.getenv('APP_NAME')}")
    logger.info(f"LOG_LEVEL: {os.getenv('LOG_LEVEL')}")
    logger.info(f"REDIS_URL: {os.getenv('REDIS_URL')}")
    logger.info(f"RABBITMQ_HOST: {os.getenv('RABBITMQ_HOST')}")
    logger.info(f"RABBITMQ_PORT: {os.getenv('RABBITMQ_PORT')}")
    logger.info(f"RABBITMQ_USER: {os.getenv('RABBITMQ_USER')}")
    logger.info(f"RABBITMQ_PASS: {os.getenv('RABBITMQ_PASS')}")
    logger.info(f"IDEMPOTENCY_TTL_SECONDS: {os.getenv('IDEMPOTENCY_TTL_SECONDS')}")
    logger.info(f"HEARTBEAT_INTERVAL_SECONDS: {os.getenv('HEARTBEAT_INTERVAL_SECONDS')}")
    logger.info(f"PROVIDER_GATE_ENABLED: {os.getenv('PROVIDER_GATE_ENABLED')}")
    logger.info(f"QUOTA_PREFIX: {os.getenv('QUOTA_PREFIX')}")


    # Initialize Redis
    try:
        logger.info(f"Attempting to connect to Redis at {settings.redis_url}...")
        redis_client = await get_redis_client()
        await redis_client.ping()
        logger.info("Redis client initialized and connected successfully.")
    except Exception as e:
        logger.critical(f"Failed to connect to Redis on startup: {e}", exc_info=True)
        raise

    # Initialize RabbitMQ
    try:
        logger.info(f"Attempting to connect to RabbitMQ at {settings.rabbit_host}:{settings.rabbit_port}...")
        rabbitmq_connection = await get_rabbitmq_connection()
        rabbitmq_channel = await rabbitmq_connection.channel()
        await rabbitmq_channel.declare_exchange(RABBITMQ_EXCHANGE_NAME, aio_pika.ExchangeType.DIRECT, durable=True)
        queue = await rabbitmq_channel.declare_queue(RABBITMQ_QUEUE_NAME, durable=True)
        await queue.bind(RABBITMQ_EXCHANGE_NAME, routing_key=RABBITMQ_QUEUE_NAME)
        # Declare heartbeat queue as well
        await rabbitmq_channel.declare_exchange(HEARTBEAT_EXCHANGE_NAME, aio_pika.ExchangeType.DIRECT, durable=True)
        heartbeat_queue = await rabbitmq_channel.declare_queue(HEARTBEAT_QUEUE_NAME, durable=True)
        await heartbeat_queue.bind(HEARTBEAT_EXCHANGE_NAME, routing_key=HEARTBEAT_QUEUE_NAME)

        logger.info("RabbitMQ connection and channel initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to connect to RabbitMQ on startup: {e}", exc_info=True)
        raise

    # Start heartbeat task
    asyncio.create_task(start_heartbeat_task())
    logger.info("Heartbeat task started.")

    # Warm caches from local file before starting consumer
    if load_state_from_file():
        logger.info("Configuration cache warmed from local file.")
    else:
        logger.warning("No valid configuration cache found. Attempting to load from environment variables.")
        try:
            client_config = json.loads(settings.CLIENT_CONFIG)
            providers_config = json.loads(settings.PROVIDERS_CONFIG)
            initial_state = {"users": client_config, "providers": providers_config}
            apply_state(initial_state)
            save_state_to_file(initial_state) # Persist for subsequent restarts
            logger.info("Successfully loaded and applied initial config from environment.")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse initial config from environment: {e}. Server will start with empty config and wait for broadcast.")

    asyncio.create_task(consume_config_state())
    logger.info("Configuration state consumer started.")

    yield

    logger.info("Shutting down Server A application...")
    # Close RabbitMQ connection
    if rabbitmq_connection:
        await rabbitmq_connection.close()
        logger.info("RabbitMQ connection closed.")
    # Close Redis connection
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed.")

def custom_json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

app = FastAPI(
    title="SMS API Gateway - Server A",
    description="Internal API Gateway for SMS sending.",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=JSONResponse
)
app.json_encoder = custom_json_serializer

# Add idempotency middleware
app.middleware("http")(idempotency_middleware)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    tracking_id = getattr(request.state, "tracking_id", None)
    error_response = ErrorResponse(
        error_code=exc.detail.get("error_code", "INTERNAL_ERROR"),
        message=exc.detail.get("message", "An unexpected error occurred."),
        details=exc.detail.get("details"),
        tracking_id=tracking_id
    )
    logger.error(
        f"HTTP Exception: {exc.status_code} - {error_response.error_code}",
        extra={
            "tracking_id": tracking_id,
            "client_api_key": getattr(request.state, 'client', None).api_key if hasattr(request.state, 'client') and request.state.client else None,
            "error_details": exc.detail
        }
    )
    # Manually serialize the content to handle datetime objects
    content = json.loads(json.dumps(dataclasses.asdict(error_response), default=custom_json_serializer))
    content = {k: v for k, v in content.items() if v is not None}
    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    tracking_id = getattr(request.state, "tracking_id", None)
    error_response = ErrorResponse(
        error_code="INVALID_PAYLOAD",
        message="Invalid request payload.",
        details={"errors": jsonable_encoder(exc.errors())},
        tracking_id=tracking_id
    )
    content = json.loads(json.dumps(dataclasses.asdict(error_response), default=custom_json_serializer))
    content = {k: v for k, v in content.items() if v is not None}
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)

async def get_client_context_dep() -> ClientContext:
    return await get_client_context()


@app.post("/api/v1/sms/send", status_code=status.HTTP_202_ACCEPTED)
async def send_sms(
    request: Request,
    payload: dict = Body(...),
    client: ClientContext = Depends(get_client_context)
):
    start_time = asyncio.get_event_loop().time()
    SMS_SEND_REQUESTS_TOTAL.inc()
    tracking_id = uuid4()
    request.state.tracking_id = tracking_id # Attach tracking_id to request state for logging/error handling

    try:
        sms_request = SendSmsRequest(**payload)
        sms_request.validate_phone()
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "INVALID_PAYLOAD", "message": str(e)}
        )

    logger.info(
        "Received SMS send request.",
        extra={"tracking_id": str(tracking_id), "client_api_key": client.api_key, "to": sms_request.to}
    )

    try:
        # 4. Provider Gate (fast-fail)
        effective_providers = provider_gate.process_providers(request, sms_request.providers)

        # 5. Quota check (increment on success path)
        await enforce_daily_quota(request)

        # 7. Publish envelope to RabbitMQ
        await publish_sms_message(
            user_id=client.user_id,
            client_key=client.api_key,
            to=sms_request.to,
            text=sms_request.text,
            ttl_seconds=sms_request.ttl_seconds,
            providers_original=sms_request.providers,
            providers_effective=effective_providers,
            tracking_id=tracking_id
        )

        response_content = SendSmsResponse(
            success=True,
            message="Request accepted for processing.",
            tracking_id=tracking_id
        )
        response_content = json.loads(json.dumps(dataclasses.asdict(response_content), default=custom_json_serializer))

        SMS_SEND_REQUEST_SUCCESS_TOTAL.inc()
        return JSONResponse(content=response_content, status_code=status.HTTP_202_ACCEPTED)

    except HTTPException as e:
        SMS_SEND_REQUEST_ERROR_TOTAL.inc()
        raise e # Re-raise to be caught by the custom exception handler
    except Exception as e:
        SMS_SEND_REQUEST_ERROR_TOTAL.inc()
        logger.exception(
            "Internal server error during SMS send.",
            extra={"tracking_id": str(tracking_id), "client_api_key": client.api_key, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "INTERNAL_ERROR", "message": "An internal server error occurred."}
        )
    finally:
        end_time = asyncio.get_event_loop().time()
        latency = end_time - start_time
        SMS_SEND_REQUEST_LATENCY_SECONDS.observe(latency)
        logger.info(
            "SMS send request processed.",
            extra={"tracking_id": str(tracking_id), "client_api_key": client.api_key, "latency_seconds": latency}
        )


@app.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz():
    """Liveness probe: returns 200 if the application thread is alive."""
    return {"status": "ok"}

@app.get("/readyz", status_code=status.HTTP_200_OK)
async def readyz():
    """Readiness probe: verifies Redis and RabbitMQ connections."""
    try:
        if not redis_client or not await redis_client.ping():
            raise ConnectionError("Redis not reachable")
        if not rabbitmq_connection or rabbitmq_connection.is_closed:
            raise ConnectionError("RabbitMQ not connected")
        # Optionally, check if a channel can be opened/used
        async with rabbitmq_connection.channel() as channel:
            await channel.declare_queue(RABBITMQ_QUEUE_NAME, passive=True) # passive=True checks existence without creating
        logger.debug("Readiness check passed: Redis and RabbitMQ are reachable.")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "SERVICE_UNAVAILABLE", "message": f"Dependency not ready: {e}"}
        )

@app.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics():
    """Exposes Prometheus metrics."""
    return metrics_content()
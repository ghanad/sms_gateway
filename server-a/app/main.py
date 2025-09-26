# server-a/app/main.py

import logging
import asyncio
import json
import secrets
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional
from uuid import uuid4, UUID
import dataclasses
import os

import aio_pika
from fastapi import FastAPI, Depends, HTTPException, status, Request, Body
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from prometheus_client import Summary
from fastapi.security import HTTPBasic, HTTPBasicCredentials

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
from app.rabbit import publish_sms_message, get_rabbitmq_connection
from app.consumers import consume_config_state
from app.cache import load_state_from_file, apply_state, save_state_to_file
from app.heartbeat import start_heartbeat_task

# Setup logging as early as possible
setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

# Global Redis and RabbitMQ connections
redis_client: Optional[Redis] = None
rabbitmq_connection: Optional[aio_pika.Connection] = None
rabbitmq_channel: Optional[aio_pika.Channel] = None

def start_config_state_consumer_if_enabled() -> Optional[asyncio.Task]:
    """Start background consumer when remote config sync is enabled."""

    if settings.CONFIG_STATE_SYNC_ENABLED:
        task = asyncio.create_task(
            consume_config_state(),
            name="config-state-consumer",
        )
        logger.info("Configuration state consumer started.")
        return task

    logger.info(
        "Remote configuration sync disabled. Using local configuration bootstrap only."
    )
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, rabbitmq_connection, rabbitmq_channel

    logger.info("Starting up Server A application...")

    # Initialize Redis
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        logger.info("Redis client initialized and connected.")
    except Exception as e:
        logger.critical(f"Failed to connect to Redis on startup: {e}", exc_info=True)
        raise

    # Initialize RabbitMQ
    try:
        rabbitmq_connection = await get_rabbitmq_connection()
        rabbitmq_channel = await rabbitmq_connection.channel()
        await rabbitmq_channel.declare_exchange(settings.outbound_sms_exchange, aio_pika.ExchangeType.TOPIC, durable=True)
        

        await rabbitmq_channel.declare_exchange(settings.heartbeat_exchange_name, aio_pika.ExchangeType.DIRECT, durable=True)
        await rabbitmq_channel.declare_queue(settings.heartbeat_queue_name, durable=True)
        logger.info("RabbitMQ connection and channel initialized.")
    except Exception as e:
        logger.critical(f"Failed to connect to RabbitMQ on startup: {e}", exc_info=True)
        raise

    background_tasks: List[asyncio.Task] = []

    # Start background tasks
    heartbeat_task = asyncio.create_task(
        start_heartbeat_task(),
        name="heartbeat-task",
    )
    background_tasks.append(heartbeat_task)
    logger.info("Heartbeat task started.")

    # Warm caches from local file OR bootstrap from environment variables
    if load_state_from_file():
        logger.info("Configuration cache warmed from local file.")
    else:
        logger.warning("No valid local cache file found. Attempting to bootstrap from environment variables.")
        try:
            client_config = json.loads(settings.CLIENT_CONFIG)
            providers_config = json.loads(settings.PROVIDERS_CONFIG)
            if client_config and providers_config:
                initial_state = {"users": client_config, "providers": providers_config}
                apply_state(initial_state)
                save_state_to_file(initial_state)
                logger.info("Successfully bootstrapped initial config from environment.")
            else:
                logger.warning("Initial configs in environment are empty. Waiting for state broadcast.")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse initial config from environment: {e}. Waiting for state broadcast.")

    config_consumer_task = start_config_state_consumer_if_enabled()
    if config_consumer_task:
        background_tasks.append(config_consumer_task)

    try:
        yield
    finally:
        logger.info("Shutting down Server A application...")

        for task in background_tasks:
            task.cancel()

        for task in background_tasks:
            task_name = task.get_name()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Background task '%s' cancelled.", task_name)
            except Exception:
                logger.exception(
                    "Background task '%s' raised an error during shutdown.",
                    task_name,
                )

        if rabbitmq_connection:
            await rabbitmq_connection.close()
            logger.info("RabbitMQ connection closed.")
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

app.middleware("http")(idempotency_middleware)

security = HTTPBasic()


def require_metrics_auth(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    """Ensure that requests to the metrics endpoint provide valid Basic Auth credentials."""
    if not settings.metrics_username or not settings.metrics_password:
        logger.error("Metrics authentication credentials are not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "message": "Metrics authentication is not configured.",
            },
        )

    username_valid = secrets.compare_digest(credentials.username, settings.metrics_username)
    password_valid = secrets.compare_digest(credentials.password, settings.metrics_password)

    if not (username_valid and password_valid):
        logger.warning("Metrics authentication failed for provided credentials.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "UNAUTHORIZED",
                "message": "Invalid authentication credentials.",
            },
            headers={"WWW-Authenticate": "Basic"},
        )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    tracking_id = getattr(request.state, "tracking_id", None)
    if isinstance(exc.detail, dict):
        detail_payload = exc.detail
    else:
        fallback_error_code = (
            "UNAUTHORIZED"
            if exc.status_code == status.HTTP_401_UNAUTHORIZED
            else "INTERNAL_ERROR"
        )
        detail_payload = {
            "error_code": fallback_error_code,
            "message": str(exc.detail) if exc.detail else "An unexpected error occurred.",
        }
    error_response = ErrorResponse(
        error_code=detail_payload.get("error_code", "INTERNAL_ERROR"),
        message=detail_payload.get("message", "An unexpected error occurred."),
        details=detail_payload.get("details"),
        tracking_id=tracking_id
    )
    logger.error(
        f"HTTP Exception: {exc.status_code} - {error_response.error_code}",
        extra={
            "tracking_id": tracking_id,
            "client_api_key": getattr(request.state, 'client', None).api_key if hasattr(request.state, 'client') and request.state.client else None,
            "error_details": detail_payload
        }
    )
    content = json.loads(json.dumps(dataclasses.asdict(error_response), default=custom_json_serializer))
    content = {k: v for k, v in content.items() if v is not None}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

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

@app.post("/api/v1/sms/send", status_code=status.HTTP_202_ACCEPTED)
async def send_sms(
    request: Request,
    payload: dict = Body(...),
    client: ClientContext = Depends(get_client_context)
):
    start_time = asyncio.get_event_loop().time()
    SMS_SEND_REQUESTS_TOTAL.inc()
    tracking_id = uuid4()
    request.state.tracking_id = tracking_id

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
        effective_providers = provider_gate.process_providers(request, sms_request.providers)
        await enforce_daily_quota(request)
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
        raise e
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
    return {"status": "ok"}

@app.get("/readyz", status_code=status.HTTP_200_OK)
async def readyz():
    try:
        if not redis_client or not await redis_client.ping():
            raise ConnectionError("Redis not reachable")
        if not rabbitmq_connection or rabbitmq_connection.is_closed:
            raise ConnectionError("RabbitMQ not connected")
        
        logger.debug("Readiness check passed: Redis and RabbitMQ are reachable.")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "SERVICE_UNAVAILABLE", "message": f"Dependency not ready: {e}"}
        )

@app.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics(_: None = Depends(require_metrics_auth)):
    return metrics_content()

import logging
import json
from typing import Optional
from redis.asyncio import Redis
from fastapi import Request, Response, HTTPException, status, Header
from app.config import get_settings
from app.schemas import ErrorResponse
from datetime import datetime

logger = logging.getLogger(__name__)
settings = get_settings()

async def get_redis_client() -> Redis:
    """Dependency to get a Redis client instance."""
    # In a real application, this would be managed by a connection pool
    # and injected via FastAPI's dependency injection.
    # For simplicity, we'll create a new client for now.
    return Redis.from_url(settings.REDIS_URL)

async def idempotency_middleware(request: Request, call_next):
    idempotency_key: Optional[str] = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return await call_next(request)

    client_api_key: Optional[str] = request.headers.get("API-Key")

    # If API-Key is missing, the request will be rejected by auth later.
    # The idempotency check is skipped for such invalid requests.
    if not client_api_key:
        return await call_next(request)
    redis_key = f"idem:{client_api_key}:{idempotency_key}"
    redis_client = await get_redis_client()

    # Try to get cached response
    cached_response_str = await redis_client.get(redis_key)
    if cached_response_str:
        cached_data = json.loads(cached_response_str)
        logger.info(
            "Returning cached response for idempotency key.",
            extra={"idempotency_key": idempotency_key, "client_api_key": client_api_key, "cached_status_code": cached_data['status_code']}
        )
        if cached_data['status_code'] >= 400:
            await redis_client.expire(redis_key, settings.IDEMPOTENCY_TTL_SECONDS)
        return Response(
            content=cached_data['body'],
            status_code=cached_data['status_code'],
            media_type=cached_data.get('media_type', 'application/json')
        )

    # If no cached response, proceed with the request
    response = await call_next(request)

    # Cache the response if it's a successful or error response that should be idempotent
    # We cache all responses (success or error) that pass through the main logic
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    # Re-create response to be able to read body again
    response = Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type
    )

    cache_data = {
        "status_code": response.status_code,
        "body": response_body.decode('utf-8'),
        "media_type": response.media_type,
        "cached_at": datetime.utcnow().isoformat()
    }

    # Use SETNX to ensure atomicity and prevent race conditions
    # If SETNX returns 1, it means the key was set (first request).
    # If SETNX returns 0, it means the key already existed (concurrent request).
    # In a concurrent scenario, the first request to set the key will succeed,
    # and subsequent concurrent requests will find the key and return the cached response.
    # We set the TTL regardless of SETNX result to ensure expiration.
    await redis_client.set(
        redis_key,
        json.dumps(cache_data),
        ex=settings.IDEMPOTENCY_TTL_SECONDS,
        nx=True # Only set if key does not exist
    )
    # If the key was already set by a concurrent request, we still want to update its TTL
    # to ensure it respects the configured IDEMPOTENCY_TTL_SECONDS.
    # This handles cases where a concurrent request might have set it with a default/short TTL.
    await redis_client.expire(redis_key, settings.IDEMPOTENCY_TTL_SECONDS)

    logger.info(
        "Cached response for idempotency key.",
        extra={"idempotency_key": idempotency_key, "client_api_key": client_api_key, "status_code": response.status_code}
    )

    return response

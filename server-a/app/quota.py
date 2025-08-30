import logging
from datetime import datetime, timedelta
from redis.asyncio import Redis
from fastapi import HTTPException, status, Request

from app.config import get_settings
from app.auth import ClientContext

logger = logging.getLogger(__name__)
settings = get_settings()

async def get_redis_client() -> Redis:
    """Dependency to get a Redis client instance."""
    return Redis.from_url(settings.redis_url)

async def enforce_daily_quota(request: Request):
    """
    FastAPI dependency to enforce per-client daily quota using Redis atomic counters.
    This should be called AFTER Provider Gate to ensure doomed requests do not consume quota.
    """
    client: ClientContext = request.state.client
    client_api_key = client.api_key
    daily_quota = client.daily_quota

    if daily_quota <= 0:
        logger.debug(
            "Client has unlimited quota (daily_quota <= 0). Skipping quota enforcement.",
            extra={"client_api_key": client_api_key}
        )
        return

    redis_client = await get_redis_client()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    quota_key = f"{settings.QUOTA_PREFIX}:{client_api_key}:{today_str}"

    # Increment the counter and get the new value
    current_usage = await redis_client.incr(quota_key)

    # Set expiration for the key if it's new (or ensure it's set)
    # The key should expire at the end of the current day UTC
    if current_usage == 1:
        # Calculate seconds until the end of the current day UTC
        now_utc = datetime.utcnow()
        end_of_day_utc = now_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        seconds_until_eod = int((end_of_day_utc - now_utc).total_seconds()) + 1 # +1 to ensure it covers the whole second

        # Ensure TTL is at least 24 hours to cover edge cases around midnight
        # and to align with the task requirement "Counters expire automatically after 24h."
        # A simple 24h expiration is safer than calculating to end of day,
        # as it avoids complex timezone issues and ensures a consistent window.
        # The task states "Counters expire automatically after 24h."
        await redis_client.expire(quota_key, settings.idempotency_ttl_seconds) # Re-using IDEMPOTENCY_TTL_SECONDS for 24h

    if current_usage > daily_quota:
        logger.warning(
            "Quota enforcement rejected: Client exceeded daily quota.",
            extra={"client_api_key": client_api_key, "current_usage": current_usage, "daily_quota": daily_quota, "error_code": "TOO_MANY_REQUESTS"}
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error_code": "TOO_MANY_REQUESTS", "message": "Daily SMS quota exceeded."}
        )

    logger.info(
        "Quota check passed.",
        extra={"client_api_key": client_api_key, "current_usage": current_usage, "daily_quota": daily_quota}
    )

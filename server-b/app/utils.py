from datetime import datetime, timedelta


def is_expired(created_at: datetime, ttl_seconds: int, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return created_at + timedelta(seconds=ttl_seconds) < now


def compute_backoff(attempt: int) -> int:
    """Simple exponential backoff in seconds."""
    return 2 ** attempt

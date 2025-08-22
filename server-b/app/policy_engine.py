from datetime import datetime
from typing import List
from .utils import is_expired


class PolicyError(Exception):
    pass


def select_providers(
    *,
    providers: List[str],
    policy: str,
    registry,
    created_at: datetime,
    ttl_seconds: int,
    send_attempts: int,
    strategy: str = "priority",
    now: datetime | None = None,
) -> List[str]:
    if is_expired(created_at, ttl_seconds, now):
        raise PolicyError("message expired")

    active = [p for p in providers if registry.is_enabled(p)]

    if policy == "exclusive":
        if not active:
            raise PolicyError("exclusive provider disabled")
        return [active[0]]

    if policy == "prioritized":
        if not active:
            raise PolicyError("no providers available")
        return active

    if policy == "smart":
        if not active:
            raise PolicyError("no providers available")
        if strategy == "round_robin":
            idx = send_attempts % len(active)
            return active[idx:] + active[:idx]
        return active

    raise PolicyError("unknown policy")

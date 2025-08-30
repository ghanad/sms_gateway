import json
from pathlib import Path
from typing import Dict

from app.config import ClientConfig, ProviderConfig, normalize_provider_key

# In-memory caches populated from configuration state broadcasts
CLIENT_CONFIG_CACHE: Dict[str, ClientConfig] = {}
PROVIDER_CONFIG_CACHE: Dict[str, ProviderConfig] = {}
PROVIDER_ALIAS_MAP_CACHE: Dict[str, str] = {}

# Path to the local on-disk cache used for warm starts
CONFIG_CACHE_PATH = Path(__file__).resolve().parent / "state" / "config_cache.json"
CONFIG_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _build_provider_alias_map(providers: Dict[str, ProviderConfig]) -> Dict[str, str]:
    """Create a mapping of normalized provider aliases to canonical names.

    Raises:
        ValueError: if two providers share the same alias.
    """

    alias_map: Dict[str, str] = {}
    for name, cfg in providers.items():
        aliases = [name] + (cfg.aliases or [])
        for alias in aliases:
            key = normalize_provider_key(alias)
            existing = alias_map.get(key)
            if existing and existing != name:
                raise ValueError(
                    f"Alias collision: '{alias.lower()}' already maps to '{existing.lower()}', cannot map to '{name.lower()}'"
                )
            alias_map[key] = name
    return alias_map


def apply_state(state: Dict) -> None:
    """Replace all in-memory caches with the given state.

    Accepts either canonical shape:
      {"users": {API_KEY: {..}}, "providers": {NAME: {..}}}

    Or server-b broadcast shape:
      {"timestamp": ..., "data": {"users": [{"api_key": ..., ...}], "providers": [{"name": ..., ...}]}}
    """

    # Unwrap nested data if present
    raw = state.get("data", state)

    users = raw.get("users", {})
    providers = raw.get("providers", {})

    # Normalize users to dict keyed by api_key
    if isinstance(users, list):
        users_dict = {}
        for u in users:
            api_key = str(u.get("api_key", "")).strip()
            if not api_key:
                continue
            # Map expected fields for ClientConfig
            users_dict[api_key] = {
                "user_id": u.get("user_id"),
                "username": u.get("username", ""),
                "is_active": bool(u.get("is_active", True)),
                "daily_quota": int(u.get("daily_quota", 0)),
            }
        users = users_dict

    # Normalize providers to dict keyed by name
    if isinstance(providers, list):
        providers_dict = {}
        for p in providers:
            name = p.get("name") or p.get("slug")
            if not name:
                continue
            providers_dict[name] = {
                "is_active": bool(p.get("is_active", True)),
                "is_operational": bool(p.get("is_operational", True)),
                "aliases": p.get("aliases") or [],
                "note": p.get("note"),
            }
        providers = providers_dict

    new_client_cache = {k: ClientConfig(**v) for k, v in users.items()}
    new_provider_cache = {k: ProviderConfig(**v) for k, v in providers.items()}
    new_alias_map = _build_provider_alias_map(new_provider_cache)

    CLIENT_CONFIG_CACHE.clear()
    CLIENT_CONFIG_CACHE.update(new_client_cache)

    PROVIDER_CONFIG_CACHE.clear()
    PROVIDER_CONFIG_CACHE.update(new_provider_cache)

    PROVIDER_ALIAS_MAP_CACHE.clear()
    PROVIDER_ALIAS_MAP_CACHE.update(new_alias_map)


def save_state_to_file(state: Dict) -> None:
    """Persist the raw state to the local cache file."""
    with CONFIG_CACHE_PATH.open("w") as f:
        json.dump(state, f)


def load_state_from_file() -> bool:
    """Load state from disk into caches.

    Returns True on success, False otherwise.
    """

    try:
        with CONFIG_CACHE_PATH.open("r") as f:
            state = json.load(f)
        apply_state(state)
        return True
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return False


# Expose helper for tests
build_provider_alias_map = _build_provider_alias_map

import json

import pytest

from app import cache
from app.config import ClientConfig, ProviderConfig


@pytest.fixture(autouse=True)
def reset_caches():
    cache.CLIENT_CONFIG_CACHE.clear()
    cache.PROVIDER_CONFIG_CACHE.clear()
    cache.PROVIDER_ALIAS_MAP_CACHE.clear()
    yield
    cache.CLIENT_CONFIG_CACHE.clear()
    cache.PROVIDER_CONFIG_CACHE.clear()
    cache.PROVIDER_ALIAS_MAP_CACHE.clear()


@pytest.fixture
def temp_cache_file(tmp_path, monkeypatch):
    config_path = tmp_path / "config_cache.json"
    monkeypatch.setattr(cache, "CONFIG_CACHE_PATH", config_path, raising=False)
    cache.CONFIG_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return config_path


def test_build_provider_alias_map_normalizes_and_includes_canonical():
    providers = {
        "Twilio": ProviderConfig(
            is_active=True,
            is_operational=True,
            aliases=["Twilio SMS", " twi-lio "],
            note="primary",
        )
    }

    alias_map = cache.build_provider_alias_map(providers)

    assert alias_map == {
        "twilio": "Twilio",
        "twiliosms": "Twilio",
    }


def test_build_provider_alias_map_raises_on_collision():
    providers = {
        "Alpha": ProviderConfig(is_active=True, is_operational=True, aliases=["Beta"]),
        "Gamma": ProviderConfig(is_active=True, is_operational=True, aliases=["B-eta"]),
    }

    with pytest.raises(ValueError) as exc:
        cache.build_provider_alias_map(providers)

    assert "Alias collision" in str(exc.value)


def test_apply_state_with_canonical_shape_populates_caches():
    state = {
        "users": {
            "api-key-1": {
                "user_id": 1,
                "username": "alice",
                "is_active": False,
                "daily_quota": 5,
            }
        },
        "providers": {
            "Twilio": {
                "is_active": True,
                "is_operational": True,
                "aliases": ["TWI-LIO"],
                "note": "primary",
            },
            "Backup": {
                "is_active": True,
                "is_operational": False,
                "aliases": None,
                "note": None,
            },
        },
    }

    cache.apply_state(state)

    assert cache.CLIENT_CONFIG_CACHE["api-key-1"] == ClientConfig(
        user_id=1, username="alice", is_active=False, daily_quota=5
    )
    assert cache.PROVIDER_CONFIG_CACHE["Twilio"] == ProviderConfig(
        is_active=True, is_operational=True, aliases=["TWI-LIO"], note="primary"
    )
    assert cache.PROVIDER_CONFIG_CACHE["Backup"] == ProviderConfig(
        is_active=True, is_operational=False, aliases=None, note=None
    )
    assert cache.PROVIDER_ALIAS_MAP_CACHE == {"twilio": "Twilio", "backup": "Backup"}


def test_apply_state_with_broadcast_shape_normalizes_entries():
    state = {
        "data": {
            "users": [
                {"api_key": " key1 ", "user_id": 10, "username": "Alice", "is_active": 0, "daily_quota": "15"},
                {"user_id": 11},  # Missing api_key should be ignored
            ],
            "providers": [
                {
                    "name": "Twilio",
                    "is_active": True,
                    "is_operational": True,
                    "aliases": ["Alpha"],
                    "note": "primary",
                },
                {
                    "slug": "NoName",
                    "is_active": False,
                    "is_operational": True,
                    "aliases": [],
                },
                {
                    "is_active": True,
                },  # Missing name/slug should be ignored
            ],
        }
    }

    cache.apply_state(state)

    assert cache.CLIENT_CONFIG_CACHE == {
        "key1": ClientConfig(user_id=10, username="Alice", is_active=False, daily_quota=15)
    }
    assert cache.PROVIDER_CONFIG_CACHE == {
        "Twilio": ProviderConfig(is_active=True, is_operational=True, aliases=["Alpha"], note="primary"),
        "NoName": ProviderConfig(is_active=False, is_operational=True, aliases=[], note=None),
    }
    assert cache.PROVIDER_ALIAS_MAP_CACHE["alpha"] == "Twilio"


def test_apply_state_raises_and_leaves_caches_on_alias_collision():
    cache.CLIENT_CONFIG_CACHE["existing"] = ClientConfig(user_id=1, username="existing")
    cache.PROVIDER_CONFIG_CACHE["Existing"] = ProviderConfig(is_active=True, is_operational=True)
    cache.PROVIDER_ALIAS_MAP_CACHE["existing"] = "Existing"

    state = {
        "providers": {
            "Alpha": {"is_active": True, "is_operational": True, "aliases": ["Shared"]},
            "Beta": {"is_active": True, "is_operational": True, "aliases": ["Shared"]},
        }
    }

    with pytest.raises(ValueError):
        cache.apply_state(state)

    assert cache.CLIENT_CONFIG_CACHE == {"existing": ClientConfig(user_id=1, username="existing")}
    assert cache.PROVIDER_CONFIG_CACHE == {"Existing": ProviderConfig(is_active=True, is_operational=True)}
    assert cache.PROVIDER_ALIAS_MAP_CACHE == {"existing": "Existing"}


def test_save_and_load_state_round_trip(temp_cache_file):
    state = {
        "users": {
            "key": {
                "user_id": 42,
                "username": "tester",
                "is_active": True,
                "daily_quota": 7,
            }
        },
        "providers": {
            "Twilio": {"is_active": True, "is_operational": True, "aliases": []}
        },
    }

    cache.save_state_to_file(state)

    assert temp_cache_file.exists()
    with temp_cache_file.open("r") as f:
        assert json.load(f) == state

    # Clear caches then load from file
    cache.CLIENT_CONFIG_CACHE.clear()
    cache.PROVIDER_CONFIG_CACHE.clear()
    cache.PROVIDER_ALIAS_MAP_CACHE.clear()

    assert cache.load_state_from_file() is True
    assert cache.CLIENT_CONFIG_CACHE["key"].user_id == 42
    assert "twilio" in cache.PROVIDER_ALIAS_MAP_CACHE


def test_load_state_from_missing_file_returns_false(temp_cache_file):
    # Ensure file does not exist
    if temp_cache_file.exists():
        temp_cache_file.unlink()

    assert cache.load_state_from_file() is False
    assert cache.CLIENT_CONFIG_CACHE == {}
    assert cache.PROVIDER_CONFIG_CACHE == {}
    assert cache.PROVIDER_ALIAS_MAP_CACHE == {}


def test_load_state_from_file_with_invalid_json_returns_false(temp_cache_file):
    temp_cache_file.write_text("not valid json")

    assert cache.load_state_from_file() is False
    assert cache.CLIENT_CONFIG_CACHE == {}
    assert cache.PROVIDER_CONFIG_CACHE == {}
    assert cache.PROVIDER_ALIAS_MAP_CACHE == {}


def test_load_state_from_file_when_apply_state_raises_returns_false(temp_cache_file):
    invalid_state = {
        "providers": {
            "Alpha": {"is_active": True, "is_operational": True, "aliases": ["Shared"]},
            "Beta": {"is_active": True, "is_operational": True, "aliases": ["Shared"]},
        }
    }
    temp_cache_file.write_text(json.dumps(invalid_state))

    cache.CLIENT_CONFIG_CACHE["existing"] = ClientConfig(user_id=1, username="existing")

    assert cache.load_state_from_file() is False
    assert cache.CLIENT_CONFIG_CACHE == {"existing": ClientConfig(user_id=1, username="existing")}
    assert cache.PROVIDER_CONFIG_CACHE == {}
    assert cache.PROVIDER_ALIAS_MAP_CACHE == {}

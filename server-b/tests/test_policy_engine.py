from datetime import datetime, timedelta
import pytest
from app import policy_engine
from app.provider_registry import ProviderRegistry
from app.providers.local_sms import LocalSMS


def make_registry(enabled: dict[str, bool]) -> ProviderRegistry:
    reg = ProviderRegistry()
    for name, is_enabled in enabled.items():
        reg.register(name, LocalSMS(), enabled=is_enabled)
    return reg


def test_exclusive_disabled():
    reg = make_registry({"p1": False})
    with pytest.raises(policy_engine.PolicyError):
        policy_engine.select_providers(
            providers=["p1"],
            policy="exclusive",
            registry=reg,
            created_at=datetime.utcnow(),
            ttl_seconds=60,
            send_attempts=0,
        )


def test_prioritized_skip_and_fail_empty():
    reg = make_registry({"a": True, "b": False})
    providers = policy_engine.select_providers(
        providers=["a", "b"],
        policy="prioritized",
        registry=reg,
        created_at=datetime.utcnow(),
        ttl_seconds=60,
        send_attempts=0,
    )
    assert providers == ["a"]

    reg2 = make_registry({"a": False})
    with pytest.raises(policy_engine.PolicyError):
        policy_engine.select_providers(
            providers=["a"],
            policy="prioritized",
            registry=reg2,
            created_at=datetime.utcnow(),
            ttl_seconds=60,
            send_attempts=0,
        )


def test_smart_selection_priority_and_round_robin():
    reg = make_registry({"a": True, "b": True})
    msg_created = datetime.utcnow()
    providers_priority = policy_engine.select_providers(
        providers=["a", "b"],
        policy="smart",
        registry=reg,
        created_at=msg_created,
        ttl_seconds=60,
        send_attempts=0,
        strategy="priority",
    )
    assert providers_priority == ["a", "b"]

    providers_rr = policy_engine.select_providers(
        providers=["a", "b"],
        policy="smart",
        registry=reg,
        created_at=msg_created,
        ttl_seconds=60,
        send_attempts=1,
        strategy="round_robin",
    )
    assert providers_rr == ["b", "a"]


def test_ttl_expiry():
    reg = make_registry({"a": True})
    past = datetime.utcnow() - timedelta(seconds=120)
    with pytest.raises(policy_engine.PolicyError):
        policy_engine.select_providers(
            providers=["a"],
            policy="prioritized",
            registry=reg,
            created_at=past,
            ttl_seconds=60,
            send_attempts=0,
        )

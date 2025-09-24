"""Utility helpers for the user_management application."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import User

from providers.models import SmsProvider


def generate_server_a_config_data() -> dict[str, dict[str, Any]]:
    """Build the configuration payload consumed by Server A."""

    users: dict[str, dict[str, Any]] = {}
    for user in User.objects.select_related("profile").all():
        profile = getattr(user, "profile", None)
        api_key = getattr(profile, "api_key", None)
        if not api_key:
            continue
        users[str(api_key)] = {
            "user_id": user.id,
            "username": user.username,
            "is_active": user.is_active,
            "daily_quota": getattr(profile, "daily_quota", 0) or 0,
        }

    providers: dict[str, dict[str, Any]] = {}
    for provider in SmsProvider.objects.all():
        aliases = list(getattr(provider, "aliases", []) or [])
        slug = getattr(provider, "slug", "")
        if slug and slug not in aliases:
            aliases.append(slug)

        provider_payload: dict[str, Any] = {
            "is_active": provider.is_active,
            "is_operational": getattr(provider, "is_operational", True),
            "aliases": aliases,
        }

        note = getattr(provider, "note", None)
        if note:
            provider_payload["note"] = note

        providers[provider.name] = provider_payload

    return {"users": users, "providers": providers}

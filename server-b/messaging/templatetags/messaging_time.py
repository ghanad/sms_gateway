from __future__ import annotations

from datetime import date, datetime, time, timezone as dt_timezone

from django import template
from django.utils import timezone
from django.utils.dateparse import parse_datetime

register = template.Library()


@register.filter
def coerce_datetime(value):
    """Return a timezone-aware ``datetime`` for template-friendly formatting."""

    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, dt_timezone.utc)
        return value

    if isinstance(value, date) and not isinstance(value, datetime):
        combined = datetime.combine(value, time.min)
        return timezone.make_aware(combined, dt_timezone.utc)

    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, dt_timezone.utc)
            return parsed

    return None

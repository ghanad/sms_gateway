from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter
def format_currency(value):
    """Format a Rial-based amount for display in Tomans with an IRT suffix."""

    if value in (None, ""):
        return "N/A"

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "N/A"

    toman_value = amount / Decimal("10")

    if toman_value == toman_value.to_integral_value():
        formatted_number = f"{int(toman_value):,}"
    else:
        rounded_value = toman_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        formatted_number = f"{rounded_value:,}"

    return f"{formatted_number} IRT"

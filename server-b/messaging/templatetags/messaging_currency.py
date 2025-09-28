"""Template filters for handling currency display.

All message costs are normalised and stored in Iranian rials (IRR).
Use the ``rial_to_toman`` filter to present costs in tomans (IRT).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN

from django import template

register = template.Library()

_IRR_TO_TOMAN_FACTOR = Decimal("10")


@register.filter
def rial_to_toman(value: Decimal | int | float | str | None) -> str:
    """Convert an IRR amount to a toman (IRT) string without decimals.

    All downstream code assumes costs are persisted in IRR. Dividing by 10
    converts the amount to tomans. We round down to avoid over-reporting the
    amount charged while still presenting an integer-only display value.
    """

    if value in (None, ""):
        return ""

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return ""

    toman_amount = (amount / _IRR_TO_TOMAN_FACTOR).quantize(Decimal("1"), rounding=ROUND_DOWN)
    return format(toman_amount, "f")

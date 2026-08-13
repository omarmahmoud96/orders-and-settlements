"""Money helpers. Every monetary value in this project is a 2dp Decimal, never a float."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value) -> Decimal:
    """
    Coerce ``value`` to a 2dp Decimal, rounding half away from zero.

    Accepts Decimal, int, str, or float. Floats are routed through ``str`` so
    that ``to_money(0.1)`` yields ``Decimal("0.10")`` rather than the binary
    approximation.
    """
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, int):
        candidate = Decimal(value)
    else:
        try:
            candidate = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"{value!r} is not a valid monetary amount.") from exc

    if not candidate.is_finite():
        raise ValueError(f"{value!r} is not a valid monetary amount.")

    return candidate.quantize(CENTS, rounding=ROUND_HALF_UP)


def format_money(value) -> str:
    """Render an amount for inclusion in a human-facing error message."""
    return f"${to_money(value):,.2f}"

"""Presentation only: currency-specific half-even money rounding."""

from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from .finance.currencies import CURRENCIES
from .finance.savings import PRECISION


def rounded_amount(value: Decimal, currency: str) -> Decimal:
    with localcontext(Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)):
        rounded = value.quantize(Decimal(1).scaleb(-CURRENCIES[currency].minor_digits))
        return rounded.copy_abs() if rounded == 0 else rounded


def amount_text(value: Decimal, currency: str, *, grouped: bool = False) -> str:
    rounded = rounded_amount(value, currency)
    digits = CURRENCIES[currency].minor_digits
    return format(rounded, f",.{digits}f" if grouped else f".{digits}f")


def money_text(value: Decimal, currency: str) -> str:
    rounded = rounded_amount(value, currency)
    sign = "−" if rounded < 0 else ""
    return sign + CURRENCIES[currency].symbol + amount_text(rounded.copy_abs(), currency, grouped=True)

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation

from app.domain.errors import InvalidAmountError

CENT = Decimal("0.01")
# Largest absolute value that fits in NUMERIC(12, 2)
MAX_AMOUNT = Decimal("9999999999.99")


def to_money(value: Decimal | int | str) -> Decimal:
    """Convert a value to an exact amount with 2 decimals.

    Floats are rejected on purpose: 0.1 + 0.2 != 0.3 in binary floating point,
    so money must come in as Decimal, int or a decimal string.
    """
    if isinstance(value, bool | float):
        raise InvalidAmountError(f"Money must be Decimal, int or str, not {type(value).__name__}")

    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise InvalidAmountError(f"Invalid amount: {value!r}") from exc

    if not amount.is_finite():
        raise InvalidAmountError(f"Invalid amount: {value!r}")
    if amount != amount.quantize(CENT):
        raise InvalidAmountError(f"Amount has more than 2 decimals: {value!r}")
    if abs(amount) > MAX_AMOUNT:
        raise InvalidAmountError(f"Amount is too large: {value!r}")

    return amount.quantize(CENT)


def ceil_to_multiple(amount: Decimal, multiple: int) -> Decimal:
    """Round up to a whole multiple: 387.56 with 10 is 390.00; 390 stays 390.00."""
    step = Decimal(multiple)
    return to_money((amount / step).to_integral_value(ROUND_CEILING) * step)


def floor_to_multiple(amount: Decimal, multiple: int) -> Decimal:
    """Round down to a whole multiple: 10,164.67 with 10 is 10,160.00."""
    step = Decimal(multiple)
    return to_money((amount / step).to_integral_value(ROUND_FLOOR) * step)

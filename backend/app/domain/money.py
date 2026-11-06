from decimal import Decimal, InvalidOperation

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

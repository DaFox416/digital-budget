from decimal import Decimal

import pytest

from app.domain.errors import InvalidAmountError
from app.domain.money import to_money


def test_to_money_returns_two_decimals() -> None:
    assert to_money("10") == Decimal("10.00")
    assert to_money(Decimal("0.1")).as_tuple().exponent == -2


def test_to_money_rejects_float() -> None:
    with pytest.raises(InvalidAmountError, match="not float"):
        to_money(0.1)  # type: ignore[arg-type]


def test_to_money_rejects_more_than_two_decimals() -> None:
    with pytest.raises(InvalidAmountError, match="more than 2 decimals"):
        to_money("12.345")


def test_to_money_rejects_non_numbers() -> None:
    with pytest.raises(InvalidAmountError):
        to_money("NaN")


def test_to_money_rejects_amounts_that_dont_fit_numeric_12_2() -> None:
    with pytest.raises(InvalidAmountError, match="too large"):
        to_money("10000000000.00")

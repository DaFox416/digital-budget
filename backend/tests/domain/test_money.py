from decimal import Decimal

import pytest

from app.domain.errors import InvalidAmountError
from app.domain.money import to_money


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("387.56", Decimal("387.56")),
        ("10", Decimal("10.00")),
        (500, Decimal("500.00")),
        (Decimal("0.1"), Decimal("0.10")),
        ("-634", Decimal("-634.00")),
        ("9999999999.99", Decimal("9999999999.99")),
    ],
)
def test_to_money_returns_two_decimals(value: Decimal | int | str, expected: Decimal) -> None:
    result = to_money(value)

    assert result == expected
    assert result.as_tuple().exponent == -2


def test_to_money_rejects_float() -> None:
    with pytest.raises(InvalidAmountError, match="not float"):
        to_money(0.1)  # type: ignore[arg-type]


def test_to_money_rejects_bool() -> None:
    with pytest.raises(InvalidAmountError):
        to_money(True)


@pytest.mark.parametrize("value", ["12.345", "0.001", Decimal("1.999")])
def test_to_money_rejects_more_than_two_decimals(value: Decimal | str) -> None:
    with pytest.raises(InvalidAmountError, match="more than 2 decimals"):
        to_money(value)


@pytest.mark.parametrize("value", ["abc", "", "NaN", "Infinity"])
def test_to_money_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidAmountError):
        to_money(value)


def test_to_money_rejects_amounts_that_dont_fit_numeric_12_2() -> None:
    with pytest.raises(InvalidAmountError, match="too large"):
        to_money("10000000000.00")

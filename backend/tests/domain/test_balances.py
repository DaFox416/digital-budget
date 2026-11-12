from decimal import Decimal

import pytest

from app.domain.balances import account_balance, check_credit_limit, credit_debt
from app.domain.errors import CreditLimitExceededError


def test_balance_adds_signed_movements() -> None:
    # Real amounts from the savings-mode example in docs/PLANEACION.md (debit account)
    movements = [
        Decimal("-387.56"),  # movie theater
        Decimal("10164.67"),  # paycheck
        Decimal("-487.00"),  # electricity bill
        Decimal("-634.00"),  # credit card payment (transfer out)
    ]

    assert account_balance(Decimal("5000.00"), movements) == Decimal("13656.11")


def test_credit_card_balance_is_negative_when_there_is_debt() -> None:
    movements = [Decimal("-634.00"), Decimal("-1200.50")]  # two purchases

    balance = account_balance(Decimal("0.00"), movements)

    assert balance == Decimal("-1834.50")
    assert credit_debt(balance) == Decimal("1834.50")


def test_purchase_can_use_all_the_available_credit_but_not_a_cent_more() -> None:
    check_credit_limit(Decimal("1500.00"), Decimal("1500.00"))

    with pytest.raises(CreditLimitExceededError) as error:
        check_credit_limit(Decimal("1500.01"), Decimal("1500.00"))
    assert error.value.excess == Decimal("0.01")

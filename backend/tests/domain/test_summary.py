from decimal import Decimal

from app.domain.enums import AccountType
from app.domain.summary import summary_totals


def test_real_balance_is_debit_plus_cash_without_savings() -> None:
    result = summary_totals(
        [
            (AccountType.DEBIT, Decimal("14290.11")),
            (AccountType.CASH, Decimal("500.00")),
            (AccountType.SAVINGS, Decimal("196.11")),
        ]
    )

    assert result.real_balance == Decimal("14790.11")
    assert result.card_debt == Decimal("0.00")


def test_card_debt_is_positive_and_adds_up() -> None:
    result = summary_totals(
        [(AccountType.CREDIT, Decimal("-634.00")), (AccountType.CREDIT, Decimal("-12000.00"))]
    )

    assert result.card_debt == Decimal("12634.00")
    assert result.real_balance == Decimal("0.00")


def test_a_card_with_a_credit_in_your_favor_subtracts() -> None:
    result = summary_totals(
        [(AccountType.CREDIT, Decimal("-634.00")), (AccountType.CREDIT, Decimal("100.00"))]
    )

    assert result.card_debt == Decimal("534.00")

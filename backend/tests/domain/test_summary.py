from decimal import Decimal

from app.domain.enums import AccountType
from app.domain.summary import summary_totals


def test_no_accounts_is_all_zero() -> None:
    result = summary_totals([])

    assert result.real_balance == Decimal("0.00")
    assert result.card_debt == Decimal("0.00")


def test_real_balance_is_debit_plus_cash() -> None:
    result = summary_totals(
        [
            (AccountType.DEBIT, Decimal("14290.11")),
            (AccountType.CASH, Decimal("500.00")),
        ]
    )

    assert result.real_balance == Decimal("14790.11")


def test_savings_accounts_dont_count() -> None:
    result = summary_totals(
        [(AccountType.DEBIT, Decimal("5000.00")), (AccountType.SAVINGS, Decimal("196.11"))]
    )

    assert result.real_balance == Decimal("5000.00")
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


def test_a_negative_debit_balance_lowers_the_real_balance() -> None:
    result = summary_totals(
        [(AccountType.DEBIT, Decimal("1000.00")), (AccountType.DEBIT, Decimal("-200.00"))]
    )

    assert result.real_balance == Decimal("800.00")

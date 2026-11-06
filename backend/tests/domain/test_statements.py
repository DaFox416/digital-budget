from decimal import Decimal

from app.domain.statements import payment_for_no_interest


def test_charges_plus_installments() -> None:
    assert payment_for_no_interest(
        Decimal("634.00"), Decimal("1000.00"), Decimal("0.00")
    ) == Decimal("1634.00")


def test_payments_after_the_cutoff_reduce_it() -> None:
    assert payment_for_no_interest(
        Decimal("634.00"), Decimal("1000.00"), Decimal("634.00")
    ) == Decimal("1000.00")


def test_never_negative_when_you_pay_more() -> None:
    assert payment_for_no_interest(
        Decimal("634.00"), Decimal("0.00"), Decimal("700.00")
    ) == Decimal("0.00")


def test_empty_cycle() -> None:
    assert payment_for_no_interest(Decimal("0"), Decimal("0"), Decimal("0")) == Decimal("0.00")

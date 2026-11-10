import uuid
from decimal import Decimal

import pytest

from app.domain.enums import AccountType, MovementType
from app.domain.errors import InvalidAmountError, InvalidMovementError
from app.domain.movements import (
    AccountRef,
    SignedAmounts,
    edit_amounts,
    edit_transfer_amounts,
    plan_transfer,
    signed_amounts,
)


class TestSignedAmounts:
    def test_expense_is_negative_and_accounting_defaults_to_real(self) -> None:
        result = signed_amounts(MovementType.EXPENSE, AccountType.DEBIT, "387.56")

        assert result.real_amount == Decimal("-387.56")
        assert result.accounting_amount == Decimal("-387.56")

    def test_accounting_amount_gets_the_same_sign(self) -> None:
        result = signed_amounts(MovementType.EXPENSE, AccountType.DEBIT, "387.56", "400")

        assert result.real_amount == Decimal("-387.56")
        assert result.accounting_amount == Decimal("-400.00")

    def test_rejects_non_positive_amount(self) -> None:
        with pytest.raises(InvalidAmountError, match="greater than zero"):
            signed_amounts(MovementType.EXPENSE, AccountType.DEBIT, "0")

    def test_rejects_negative_accounting_amount(self) -> None:
        with pytest.raises(InvalidAmountError, match="can't be negative"):
            signed_amounts(MovementType.EXPENSE, AccountType.DEBIT, "100", "-100")

    def test_rejects_savings_account(self) -> None:
        with pytest.raises(InvalidMovementError, match="savings"):
            signed_amounts(MovementType.EXPENSE, AccountType.SAVINGS, "100")


def account(account_type: AccountType) -> AccountRef:
    return AccountRef(id=uuid.uuid4(), type=account_type)


class TestPlanTransfer:
    def test_debit_to_debit_is_a_transfer(self) -> None:
        plan = plan_transfer(account(AccountType.DEBIT), account(AccountType.DEBIT), "2000")

        assert plan.movement_type is MovementType.TRANSFER
        assert plan.source_amount == Decimal("-2000.00")
        assert plan.destination_amount == Decimal("2000.00")

    def test_debit_to_credit_is_a_card_payment(self) -> None:
        plan = plan_transfer(account(AccountType.DEBIT), account(AccountType.CREDIT), "634")

        assert plan.movement_type is MovementType.CARD_PAYMENT
        assert plan.source_amount == Decimal("-634.00")
        assert plan.destination_amount == Decimal("634.00")

    def test_rejects_same_account(self) -> None:
        same = account(AccountType.DEBIT)

        with pytest.raises(InvalidMovementError, match="different accounts"):
            plan_transfer(same, same, "100")

    def test_rejects_credit_source(self) -> None:
        with pytest.raises(InvalidMovementError, match="Can't transfer from"):
            plan_transfer(account(AccountType.CREDIT), account(AccountType.DEBIT), "100")


class TestEditAmounts:
    # Cine con débito en modo ahorro: real -387.56, contable -400.00
    CURRENT = SignedAmounts(real_amount=Decimal("-387.56"), accounting_amount=Decimal("-400.00"))

    def test_only_amount_resets_accounting_to_it(self) -> None:
        result = edit_amounts(MovementType.EXPENSE, AccountType.DEBIT, self.CURRENT, amount="450")

        assert result.real_amount == Decimal("-450.00")
        assert result.accounting_amount == Decimal("-450.00")

    def test_only_accounting_keeps_real_amount(self) -> None:
        result = edit_amounts(
            MovementType.EXPENSE, AccountType.DEBIT, self.CURRENT, accounting_amount="390"
        )

        assert result.real_amount == Decimal("-387.56")
        assert result.accounting_amount == Decimal("-390.00")

    def test_rejects_negative_accounting_amount(self) -> None:
        with pytest.raises(InvalidAmountError, match="can't be negative"):
            edit_amounts(
                MovementType.EXPENSE, AccountType.DEBIT, self.CURRENT, accounting_amount="-1"
            )


def test_edited_transfer_legs_get_opposite_amounts() -> None:
    plan = edit_transfer_amounts(MovementType.CARD_PAYMENT, "634")

    assert plan.movement_type is MovementType.CARD_PAYMENT
    assert plan.source_amount == Decimal("-634.00")
    assert plan.destination_amount == Decimal("634.00")

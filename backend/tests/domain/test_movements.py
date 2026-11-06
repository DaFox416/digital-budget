import uuid
from decimal import Decimal

import pytest

from app.domain.enums import AccountType, MovementType
from app.domain.errors import InvalidAmountError, InvalidMovementError
from app.domain.movements import AccountRef, plan_transfer, signed_amounts


class TestSignedAmounts:
    def test_expense_is_negative(self) -> None:
        result = signed_amounts(MovementType.EXPENSE, AccountType.DEBIT, "387.56")

        assert result.real_amount == Decimal("-387.56")
        assert result.accounting_amount == Decimal("-387.56")

    def test_income_is_positive(self) -> None:
        result = signed_amounts(MovementType.INCOME, AccountType.DEBIT, "10164.67")

        assert result.real_amount == Decimal("10164.67")
        assert result.accounting_amount == Decimal("10164.67")

    def test_accounting_amount_defaults_to_real_amount(self) -> None:
        result = signed_amounts(MovementType.EXPENSE, AccountType.CASH, "90")

        assert result.accounting_amount == result.real_amount

    def test_accounting_amount_gets_the_same_sign(self) -> None:
        result = signed_amounts(MovementType.EXPENSE, AccountType.DEBIT, "387.56", "400")

        assert result.real_amount == Decimal("-387.56")
        assert result.accounting_amount == Decimal("-400.00")

    def test_expense_on_credit_card_is_allowed(self) -> None:
        result = signed_amounts(MovementType.EXPENSE, AccountType.CREDIT, "634")

        assert result.real_amount == Decimal("-634.00")

    @pytest.mark.parametrize("amount", ["0", "-10"])
    def test_rejects_non_positive_amount(self, amount: str) -> None:
        with pytest.raises(InvalidAmountError, match="greater than zero"):
            signed_amounts(MovementType.EXPENSE, AccountType.DEBIT, amount)

    def test_rejects_negative_accounting_amount(self) -> None:
        with pytest.raises(InvalidAmountError, match="can't be negative"):
            signed_amounts(MovementType.EXPENSE, AccountType.DEBIT, "100", "-100")

    def test_rejects_savings_account(self) -> None:
        with pytest.raises(InvalidMovementError, match="savings"):
            signed_amounts(MovementType.EXPENSE, AccountType.SAVINGS, "100")

    @pytest.mark.parametrize("movement_type", [MovementType.TRANSFER, MovementType.CARD_PAYMENT])
    def test_rejects_transfer_types(self, movement_type: MovementType) -> None:
        with pytest.raises(InvalidMovementError, match="plan_transfer"):
            signed_amounts(movement_type, AccountType.DEBIT, "100")


def account(account_type: AccountType) -> AccountRef:
    return AccountRef(id=uuid.uuid4(), type=account_type)


class TestPlanTransfer:
    def test_debit_to_debit_is_a_transfer(self) -> None:
        plan = plan_transfer(account(AccountType.DEBIT), account(AccountType.DEBIT), "2000")

        assert plan.movement_type is MovementType.TRANSFER
        assert plan.source_amount == Decimal("-2000.00")
        assert plan.destination_amount == Decimal("2000.00")

    def test_cash_to_debit_is_a_transfer(self) -> None:
        plan = plan_transfer(account(AccountType.CASH), account(AccountType.DEBIT), "500")

        assert plan.movement_type is MovementType.TRANSFER

    def test_debit_to_credit_is_a_card_payment(self) -> None:
        plan = plan_transfer(account(AccountType.DEBIT), account(AccountType.CREDIT), "634")

        assert plan.movement_type is MovementType.CARD_PAYMENT
        assert plan.source_amount == Decimal("-634.00")
        assert plan.destination_amount == Decimal("634.00")

    def test_legs_always_cancel_out(self) -> None:
        plan = plan_transfer(account(AccountType.DEBIT), account(AccountType.CASH), "123.45")

        assert plan.source_amount + plan.destination_amount == Decimal("0")

    def test_rejects_same_account(self) -> None:
        same = account(AccountType.DEBIT)

        with pytest.raises(InvalidMovementError, match="different accounts"):
            plan_transfer(same, same, "100")

    @pytest.mark.parametrize("source_type", [AccountType.CREDIT, AccountType.SAVINGS])
    def test_rejects_invalid_source(self, source_type: AccountType) -> None:
        with pytest.raises(InvalidMovementError, match="Can't transfer from"):
            plan_transfer(account(source_type), account(AccountType.DEBIT), "100")

    def test_rejects_savings_destination(self) -> None:
        with pytest.raises(InvalidMovementError, match="Can't transfer to"):
            plan_transfer(account(AccountType.DEBIT), account(AccountType.SAVINGS), "100")

    @pytest.mark.parametrize("amount", ["0", "-50"])
    def test_rejects_non_positive_amount(self, amount: str) -> None:
        with pytest.raises(InvalidAmountError, match="greater than zero"):
            plan_transfer(account(AccountType.DEBIT), account(AccountType.CASH), amount)

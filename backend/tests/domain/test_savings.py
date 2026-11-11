from dataclasses import dataclass, field, replace
from decimal import Decimal

import pytest

from app.domain.enums import AccountType, MovementType, WarningLevel
from app.domain.errors import InvalidAmountError
from app.domain.savings import (
    AccountTotals,
    SavingsFigures,
    SavingsInputs,
    commitment_payment_accounting,
    cost_to_available,
    installment_accounting,
    releasable_leftover,
    savings_figures,
    suggest_accounting,
    validate_leftover_release,
)
from app.domain.warnings import (
    PurchaseWarning,
    installment_purchase_warning,
    purchase_warning,
)


def d(value: str) -> Decimal:
    return Decimal(value)


@dataclass
class Ledger:
    """Accumulates movements the way the database totals do, to walk through a scenario."""

    accounts: dict[str, AccountTotals] = field(default_factory=dict)
    commitments_pending: Decimal = d("0")
    installments_charged_accounting: Decimal = d("0")
    installments_pending: Decimal = d("0")
    leftover_released: Decimal = d("0")

    def open(self, name: str, type: AccountType, initial: str = "0") -> None:
        self.accounts[name] = AccountTotals(type, d(initial), d(initial))

    def move(self, name: str, real: str, accounting: str | None = None) -> None:
        current = self.accounts[name]
        self.accounts[name] = replace(
            current,
            balance=current.balance + d(real),
            accounting_balance=current.accounting_balance + d(accounting or real),
        )

    def figures(self) -> SavingsFigures:
        result = savings_figures(
            SavingsInputs(
                accounts=list(self.accounts.values()),
                installments_charged_accounting=self.installments_charged_accounting,
                installments_pending=self.installments_pending,
                commitments_pending=self.commitments_pending,
                leftover_released=self.leftover_released,
            )
        )
        assert result.invariant_holds(), result
        return result


def test_example_from_the_plan_step_by_step() -> None:
    """The savings mode table of docs/PLANEACION.md, checking the invariant after each step."""
    ledger = Ledger()
    ledger.open("BBVA", AccountType.DEBIT, "5000")
    ledger.open("TDC Oro", AccountType.CREDIT)
    ledger.open("Sobrante", AccountType.SAVINGS)  # Doesn't count anywhere
    ledger.commitments_pending = d("500")  # Luz

    def check(real: str, debt: str, available: str, leftover: str) -> None:
        result = ledger.figures()
        assert (result.real_balance, result.card_debt, result.available, result.leftover) == (
            d(real),
            d(debt),
            d(available),
            d(leftover),
        )

    check("5000.00", "0.00", "4500.00", "0.00")

    ledger.move("BBVA", "-387.56", "-400")  # Cine
    check("4612.44", "0.00", "4100.00", "12.44")

    ledger.move("TDC Oro", "-634", "-640")  # Despensa
    check("4612.44", "634.00", "3460.00", "18.44")

    ledger.move("BBVA", "10164.67", "10000")  # Quincena
    check("14777.11", "634.00", "13460.00", "183.11")

    ledger.move("BBVA", "-487", "-500")  # Luz: consumes the commitment
    ledger.commitments_pending = d("0")
    check("14290.11", "634.00", "13460.00", "196.11")

    ledger.move("BBVA", "-634")  # Card payment, both legs
    ledger.move("TDC Oro", "634")
    check("13656.11", "0.00", "13460.00", "196.11")

    # Laptop at 12 MSI: the debt takes the total, "available" only the first installment
    ledger.move("TDC Oro", "-12000", "0")
    ledger.installments_charged_accounting = d("1000")
    ledger.installments_pending = d("11000")
    check("13656.11", "12000.00", "12460.00", "196.11")

    ledger.leftover_released = d("190")
    check("13656.11", "12000.00", "12650.00", "6.11")


def test_rounding_of_a_charged_installment_goes_to_the_leftover() -> None:
    ledger = Ledger()
    ledger.open("BBVA", AccountType.DEBIT, "5000")
    ledger.open("TDC Oro", AccountType.CREDIT)
    # 1,000 at 3 MSI: first installment 333.33, charged as 340
    ledger.move("TDC Oro", "-1000", "0")
    ledger.installments_charged_accounting = d("340")
    ledger.installments_pending = d("666.67")

    result = ledger.figures()

    assert result.available == d("4660.00")
    assert result.leftover == d("6.67")


class TestLeftoverRelease:
    def test_releasable_is_whole_multiples_of_the_rounding(self) -> None:
        assert releasable_leftover(d("196.11"), 10) == d("190.00")
        assert releasable_leftover(d("-5.00"), 10) == d("0.00")

    def test_rejects_non_multiples_and_more_than_the_leftover(self) -> None:
        assert validate_leftover_release("190", d("196.11"), 10) == d("190.00")
        with pytest.raises(InvalidAmountError, match="multiple of 10"):
            validate_leftover_release("195", d("196.11"), 10)
        with pytest.raises(InvalidAmountError, match="more than the leftover"):
            validate_leftover_release("200", d("196.11"), 10)


def test_commitment_payment_accounting_is_the_larger_amount() -> None:
    # Luz with 500 set aside: costs 487 -> 500; costs 520 -> 520 (the extra 20 leaves available)
    assert commitment_payment_accounting(d("487"), d("500")) == d("500.00")
    assert commitment_payment_accounting(d("520"), d("500")) == d("520.00")


class TestWarnings:
    # Real balance 4,612.44 and available 3,460 (after the despensa in the plan's example)
    def test_no_warning_within_available(self) -> None:
        assert purchase_warning(d("400"), d("387.56"), d("3460"), d("4612.44"), True) is None

    def test_level_1_over_available_only_in_savings_mode(self) -> None:
        warning = purchase_warning(d("4000"), d("3990"), d("3460"), d("4612.44"), True)

        assert warning == PurchaseWarning(WarningLevel.OVER_AVAILABLE, d("540.00"))
        assert purchase_warning(d("4000"), d("3990"), d("3460"), d("4612.44"), False) is None

    def test_level_2_wins_over_level_1_in_every_mode(self) -> None:
        expected = PurchaseWarning(WarningLevel.OVER_REAL_BALANCE, d("387.56"))
        for savings_mode in (True, False):
            warning = purchase_warning(d("5000"), d("5000"), d("3460"), d("4612.44"), savings_mode)
            assert warning == expected

    def test_msi_compares_first_installment_and_total(self) -> None:
        # 12,000 at 12: the first 1,000 fits in available, but the total is over the real balance
        warning = installment_purchase_warning(d("1000"), d("12000"), d("3460"), d("4612.44"), True)
        assert warning is not None and warning.level is WarningLevel.OVER_REAL_BALANCE
        # 3,600 at 3: 1,200 fits, the total fits in the real balance
        assert (
            installment_purchase_warning(d("1200"), d("3600"), d("3460"), d("4612.44"), True)
            is None
        )


class TestRounding:
    def test_suggestion_rounds_expenses_up_and_income_down(self) -> None:
        assert suggest_accounting(MovementType.EXPENSE, d("387.56"), 10) == d("390.00")
        assert suggest_accounting(MovementType.INCOME, d("10164.67"), 10) == d("10160.00")
        # Already a multiple: no difference for the leftover
        assert suggest_accounting(MovementType.EXPENSE, d("390"), 10) == d("390.00")

    def test_installments_round_up_each_one(self) -> None:
        # 1,000 at 3 MSI: 333.33, 333.33 and 333.34, each one takes 340 from "available"
        assert [installment_accounting(d(a), 10) for a in ("333.33", "333.34")] == [
            d("340.00"),
            d("340.00"),
        ]

    def test_paying_a_commitment_only_costs_what_goes_over_it(self) -> None:
        assert cost_to_available(d("520"), d("500")) == d("20.00")
        assert cost_to_available(d("500"), d("500")) == d("0.00")
        assert cost_to_available(d("400"), None) == d("400.00")

from datetime import date
from decimal import Decimal

import pytest

from app.domain.cycles import CreditCycleConfig
from app.domain.enums import AccountType, PaymentDueRule
from app.domain.errors import InvalidAmountError, InvalidInstallmentPlanError
from app.domain.installments import (
    ScheduledInstallment,
    installment_schedule,
    pending_to_charge,
    split_installments,
    validate_installment_account,
)

CUTOFF_15 = CreditCycleConfig(
    cutoff_day=15, payment_due_rule=PaymentDueRule.FIXED_DAY, payment_due_value=5
)


class TestSplitInstallments:
    def test_last_installment_absorbs_the_difference(self) -> None:
        assert split_installments("1000", 3) == [
            Decimal("333.33"),
            Decimal("333.33"),
            Decimal("333.34"),
        ]

    def test_rounds_down_so_the_last_is_never_negative(self) -> None:
        # Rounding half up would give 0.03 x 47 = 1.41 > 1.20 and a negative last installment
        installments = split_installments("1.20", 48)

        assert installments[:47] == [Decimal("0.02")] * 47
        assert installments[47] == Decimal("0.26")

    def test_installments_add_up_exactly_to_the_total(self) -> None:
        installments = split_installments("9999.99", 7)

        assert len(installments) == 7
        assert sum(installments) == Decimal("9999.99")

    def test_accepts_the_limits_and_rejects_beyond(self) -> None:
        assert len(split_installments("1000", 3)) == 3
        assert len(split_installments("1000", 48)) == 48
        with pytest.raises(InvalidInstallmentPlanError):
            split_installments("1000", 49)

    def test_rejects_a_total_smaller_than_one_cent_per_month(self) -> None:
        with pytest.raises(InvalidAmountError):
            split_installments("0.02", 3)


class TestInstallmentSchedule:
    def test_first_installment_is_in_the_purchase_cycle_and_charged_that_day(self) -> None:
        schedule = installment_schedule("12000", 12, date(2026, 11, 10), CUTOFF_15)

        assert schedule[0] == ScheduledInstallment(
            number=1,
            amount=Decimal("1000.00"),
            cutoff=date(2026, 11, 15),
            charged_on=date(2026, 11, 10),
        )

    def test_following_installments_are_charged_the_day_after_each_cutoff(self) -> None:
        schedule = installment_schedule("12000", 12, date(2026, 11, 10), CUTOFF_15)

        assert [(i.cutoff, i.charged_on) for i in schedule[1:3]] == [
            (date(2026, 12, 15), date(2026, 11, 16)),
            (date(2027, 1, 15), date(2026, 12, 16)),
        ]
        assert schedule[-1].cutoff == date(2027, 10, 15)

    def test_purchase_on_the_cutoff_day(self) -> None:
        schedule = installment_schedule("1000", 3, date(2026, 11, 15), CUTOFF_15)

        assert [i.cutoff for i in schedule] == [
            date(2026, 11, 15),
            date(2026, 12, 15),
            date(2027, 1, 15),
        ]
        assert schedule[1].charged_on == date(2026, 11, 16)

    def test_cutoff_on_the_31st_through_february(self) -> None:
        config = CreditCycleConfig(
            cutoff_day=31, payment_due_rule=PaymentDueRule.DAYS_AFTER_CUTOFF, payment_due_value=20
        )

        schedule = installment_schedule("900", 3, date(2027, 1, 20), config)

        assert [(i.cutoff, i.charged_on) for i in schedule] == [
            (date(2027, 1, 31), date(2027, 1, 20)),
            (date(2027, 2, 28), date(2027, 2, 1)),
            (date(2027, 3, 31), date(2027, 3, 1)),
        ]


class TestPendingToCharge:
    def test_example_with_4000_at_12_months(self) -> None:
        # From the planning discussion: first installment charged, 3,666.67 still pending
        schedule = installment_schedule("4000", 12, date(2026, 11, 10), CUTOFF_15)

        assert pending_to_charge(schedule, date(2026, 11, 10)) == Decimal("3666.67")

    def test_on_the_first_day_of_the_next_cycle_the_second_is_charged(self) -> None:
        schedule = installment_schedule("1000", 3, date(2026, 11, 10), CUTOFF_15)

        assert pending_to_charge(schedule, date(2026, 11, 15)) == Decimal("666.67")
        assert pending_to_charge(schedule, date(2026, 11, 16)) == Decimal("333.34")


def test_only_credit_cards_take_installment_plans() -> None:
    validate_installment_account(AccountType.CREDIT)
    with pytest.raises(InvalidInstallmentPlanError):
        validate_installment_account(AccountType.DEBIT)

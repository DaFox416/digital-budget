from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.balances import credit_available
from app.domain.cycles import (
    CardCycle,
    CreditCycleConfig,
    cycle_for,
    day_in_month,
    last_closed_cycle,
    next_payment_cycle,
    payment_due_date,
    updated_cycle_config,
)
from app.domain.enums import PaymentDueRule
from app.domain.errors import InvalidCreditConfigError

FIXED = PaymentDueRule.FIXED_DAY
DAYS_AFTER = PaymentDueRule.DAYS_AFTER_CUTOFF


def config(cutoff_day: int, rule: PaymentDueRule = FIXED, value: int = 5) -> CreditCycleConfig:
    return CreditCycleConfig(cutoff_day=cutoff_day, payment_due_rule=rule, payment_due_value=value)


class TestDayInMonth:
    def test_day_31_in_a_30_day_month_is_the_last_day(self) -> None:
        assert day_in_month(2026, 11, 31) == date(2026, 11, 30)

    def test_february_in_a_leap_year(self) -> None:
        assert day_in_month(2028, 2, 31) == date(2028, 2, 29)


class TestCycleFor:
    def test_example_from_the_plan_with_cutoff_on_the_15th(self) -> None:
        cycle = cycle_for(date(2026, 11, 10), config(15))

        assert cycle == CardCycle(
            start=date(2026, 10, 16), cutoff=date(2026, 11, 15), payment_due=date(2026, 12, 5)
        )

    def test_purchase_on_the_cutoff_day_belongs_to_that_cycle(self) -> None:
        # Confirmed with two real statements from different banks
        assert cycle_for(date(2026, 11, 15), config(15)).cutoff == date(2026, 11, 15)

    def test_purchase_the_day_after_cutoff_goes_to_the_next_cycle(self) -> None:
        cycle = cycle_for(date(2026, 11, 16), config(15))

        assert cycle.start == date(2026, 11, 16)
        assert cycle.cutoff == date(2026, 12, 15)

    def test_cutoff_on_the_31st_uses_the_last_day_of_short_months(self) -> None:
        cycle = cycle_for(date(2026, 11, 20), config(31))

        assert cycle.start == date(2026, 11, 1)  # October 31 was the previous cutoff
        assert cycle.cutoff == date(2026, 11, 30)

    def test_cutoff_on_the_30th_in_february(self) -> None:
        cycle = cycle_for(date(2027, 2, 28), config(30))

        assert cycle.start == date(2027, 1, 31)
        assert cycle.cutoff == date(2027, 2, 28)

    def test_purchase_after_the_december_cutoff_goes_to_january(self) -> None:
        cycle = cycle_for(date(2026, 12, 20), config(15))

        assert cycle.start == date(2026, 12, 16)
        assert cycle.cutoff == date(2027, 1, 15)

    def test_every_day_falls_in_a_contiguous_cycle(self) -> None:
        # Two years, including the leap February of 2028
        for cutoff_day in (15, 31):
            day = date(2027, 1, 1)
            while day < date(2029, 1, 1):
                cycle = cycle_for(day, config(cutoff_day))
                assert cycle.contains(day)
                next_start = cycle.cutoff + timedelta(days=1)
                assert cycle_for(next_start, config(cutoff_day)).start == next_start
                day += timedelta(days=1)


class TestPaymentDueDate:
    def test_fixed_day_in_the_next_month(self) -> None:
        assert payment_due_date(date(2026, 11, 15), FIXED, 5) == date(2026, 12, 5)

    def test_fixed_day_that_doesnt_exist_uses_the_last_day(self) -> None:
        assert payment_due_date(date(2027, 1, 31), FIXED, 30) == date(2027, 2, 28)

    def test_clamped_cutoff_and_fixed_day_on_the_same_date_moves_to_next_month(self) -> None:
        # Cutoff 31 becomes November 30; payment day 30 must not be the same day
        assert payment_due_date(date(2026, 11, 30), FIXED, 30) == date(2026, 12, 30)

    def test_days_after_cutoff(self) -> None:
        assert payment_due_date(date(2026, 11, 15), DAYS_AFTER, 20) == date(2026, 12, 5)

    def test_days_after_cutoff_crosses_the_year(self) -> None:
        assert payment_due_date(date(2026, 12, 25), DAYS_AFTER, 20) == date(2027, 1, 14)


class TestLastClosedCycle:
    def test_before_the_cutoff_it_is_the_previous_cycle(self) -> None:
        cycle = last_closed_cycle(date(2026, 11, 6), config(15))

        assert cycle.cutoff == date(2026, 10, 15)
        assert cycle.payment_due == date(2026, 11, 5)

    def test_on_the_cutoff_day_it_is_the_cycle_closing_today(self) -> None:
        assert last_closed_cycle(date(2026, 11, 15), config(15)).cutoff == date(2026, 11, 15)


class TestNextPaymentCycle:
    # Cutoff on the 15th, payment on the 5th
    NOV_15 = CardCycle(date(2026, 10, 16), date(2026, 11, 15), date(2026, 12, 5))
    DEC_15 = CardCycle(date(2026, 11, 16), date(2026, 12, 15), date(2027, 1, 5))

    def test_after_the_cutoff_is_the_closed_statement(self) -> None:
        result = next_payment_cycle(date(2026, 11, 20), config(15))

        assert result.cycle == self.NOV_15
        assert result.is_closed

    def test_the_due_date_still_counts(self) -> None:
        result = next_payment_cycle(date(2026, 12, 5), config(15))

        assert result.cycle == self.NOV_15
        assert result.is_closed

    def test_after_the_due_date_is_the_open_cycle(self) -> None:
        result = next_payment_cycle(date(2026, 12, 6), config(15))

        assert result.cycle == self.DEC_15
        assert not result.is_closed

    def test_with_long_days_after_cutoff_the_older_statement_comes_first(self) -> None:
        # 45 days after the cutoff: the Nov 15 statement is due Dec 30, after the Dec 15 cutoff
        result = next_payment_cycle(date(2026, 12, 20), config(15, DAYS_AFTER, 45))

        assert result.cycle.cutoff == date(2026, 11, 15)
        assert result.cycle.payment_due == date(2026, 12, 30)
        assert result.is_closed


class TestUpdatedCycleConfig:
    CURRENT = config(15, FIXED, 5)

    def test_only_the_cutoff_day(self) -> None:
        assert updated_cycle_config(self.CURRENT, cutoff_day=20) == config(20, FIXED, 5)

    def test_only_the_rule_keeps_a_value_that_still_fits(self) -> None:
        result = updated_cycle_config(self.CURRENT, payment_due_rule=DAYS_AFTER)

        assert result == config(15, DAYS_AFTER, 5)

    def test_rejects_a_current_value_that_doesnt_fit_the_new_rule(self) -> None:
        current = config(15, DAYS_AFTER, 45)

        with pytest.raises(InvalidCreditConfigError, match="Payment day"):
            updated_cycle_config(current, payment_due_rule=FIXED)


class TestConfigValidation:
    def test_rejects_invalid_cutoff_day(self) -> None:
        with pytest.raises(InvalidCreditConfigError):
            config(32)

    def test_accepts_the_limits(self) -> None:
        config(31, FIXED, 31)
        config(1, DAYS_AFTER, 60)


class TestCreditAvailable:
    def test_limit_minus_debt(self) -> None:
        assert credit_available(Decimal("20000.00"), Decimal("-634.00")) == Decimal("19366.00")

    def test_credit_in_your_favor_adds_to_it(self) -> None:
        assert credit_available(Decimal("20000.00"), Decimal("150.00")) == Decimal("20150.00")

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.balances import credit_available
from app.domain.cycles import (
    CardCycle,
    CreditCycleConfig,
    cutoff_for,
    cycle_for,
    day_in_month,
    last_closed_cycle,
    payment_due_date,
)
from app.domain.enums import PaymentDueRule
from app.domain.errors import InvalidCreditConfigError

FIXED = PaymentDueRule.FIXED_DAY
DAYS_AFTER = PaymentDueRule.DAYS_AFTER_CUTOFF


def config(cutoff_day: int, rule: PaymentDueRule = FIXED, value: int = 5) -> CreditCycleConfig:
    return CreditCycleConfig(cutoff_day=cutoff_day, payment_due_rule=rule, payment_due_value=value)


class TestDayInMonth:
    def test_existing_day_is_kept(self) -> None:
        assert day_in_month(2026, 11, 15) == date(2026, 11, 15)

    def test_day_31_in_a_30_day_month_is_the_last_day(self) -> None:
        assert day_in_month(2026, 11, 31) == date(2026, 11, 30)

    def test_february_in_a_common_year(self) -> None:
        assert day_in_month(2027, 2, 30) == date(2027, 2, 28)

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

    def test_purchase_on_the_first_day_of_the_cycle(self) -> None:
        assert cycle_for(date(2026, 10, 16), config(15)).cutoff == date(2026, 11, 15)

    def test_cutoff_on_the_31st_uses_the_last_day_of_short_months(self) -> None:
        cycle = cycle_for(date(2026, 11, 20), config(31))

        assert cycle.start == date(2026, 11, 1)  # October 31 was the previous cutoff
        assert cycle.cutoff == date(2026, 11, 30)

    def test_cutoff_on_the_31st_after_a_short_month(self) -> None:
        # November 30 was the cutoff, so December's cycle starts on December 1
        cycle = cycle_for(date(2026, 12, 1), config(31))

        assert cycle.start == date(2026, 12, 1)
        assert cycle.cutoff == date(2026, 12, 31)

    def test_cutoff_on_the_30th_in_february(self) -> None:
        cycle = cycle_for(date(2027, 2, 28), config(30))

        assert cycle.start == date(2027, 1, 31)
        assert cycle.cutoff == date(2027, 2, 28)

    def test_march_cycle_after_a_clamped_february_cutoff(self) -> None:
        cycle = cycle_for(date(2027, 3, 1), config(30))

        assert cycle.start == date(2027, 3, 1)
        assert cycle.cutoff == date(2027, 3, 30)

    def test_leap_year_february(self) -> None:
        cycle = cycle_for(date(2028, 2, 29), config(31))

        assert cycle.start == date(2028, 2, 1)
        assert cycle.cutoff == date(2028, 2, 29)

    def test_purchase_after_the_december_cutoff_goes_to_january(self) -> None:
        cycle = cycle_for(date(2026, 12, 20), config(15))

        assert cycle.start == date(2026, 12, 16)
        assert cycle.cutoff == date(2027, 1, 15)

    def test_january_cycle_starts_in_december(self) -> None:
        cycle = cycle_for(date(2027, 1, 3), config(10))

        assert cycle.start == date(2026, 12, 11)
        assert cycle.cutoff == date(2027, 1, 10)

    def test_cutoff_on_the_first_of_the_month(self) -> None:
        cycle = cycle_for(date(2026, 11, 2), config(1))

        assert cycle.start == date(2026, 11, 2)
        assert cycle.cutoff == date(2026, 12, 1)

    @pytest.mark.parametrize("cutoff_day", [1, 15, 28, 29, 30, 31])
    def test_every_day_falls_in_a_cycle_that_contains_it(self, cutoff_day: int) -> None:
        # Two years, including the leap February of 2028
        day = date(2027, 1, 1)
        while day < date(2029, 1, 1):
            cycle = cycle_for(day, config(cutoff_day))
            assert cycle.contains(day)
            # Cycles are contiguous: the day after the cutoff starts the next one
            assert cycle_for(cycle.cutoff + timedelta(days=1), config(cutoff_day)).start == (
                cycle.cutoff + timedelta(days=1)
            )
            day += timedelta(days=1)

    def test_cutoff_for_matches_cycle_for(self) -> None:
        assert cutoff_for(date(2026, 11, 16), 15) == date(2026, 12, 15)


class TestPaymentDueDate:
    def test_fixed_day_in_the_next_month(self) -> None:
        assert payment_due_date(date(2026, 11, 15), FIXED, 5) == date(2026, 12, 5)

    def test_fixed_day_later_in_the_same_month(self) -> None:
        assert payment_due_date(date(2026, 11, 3), FIXED, 23) == date(2026, 11, 23)

    def test_fixed_day_equal_to_the_cutoff_day_is_next_month(self) -> None:
        assert payment_due_date(date(2026, 11, 15), FIXED, 15) == date(2026, 12, 15)

    def test_fixed_day_that_doesnt_exist_uses_the_last_day(self) -> None:
        assert payment_due_date(date(2027, 1, 31), FIXED, 30) == date(2027, 2, 28)

    def test_fixed_day_crosses_the_year(self) -> None:
        assert payment_due_date(date(2026, 12, 15), FIXED, 5) == date(2027, 1, 5)

    def test_clamped_cutoff_and_fixed_day_on_the_same_date_moves_to_next_month(self) -> None:
        # Cutoff 31 becomes November 30; payment day 30 must not be the same day
        assert payment_due_date(date(2026, 11, 30), FIXED, 30) == date(2026, 12, 30)

    def test_days_after_cutoff(self) -> None:
        assert payment_due_date(date(2026, 11, 15), DAYS_AFTER, 20) == date(2026, 12, 5)

    def test_days_after_cutoff_crosses_february_and_the_year(self) -> None:
        assert payment_due_date(date(2027, 2, 10), DAYS_AFTER, 20) == date(2027, 3, 2)
        assert payment_due_date(date(2026, 12, 25), DAYS_AFTER, 20) == date(2027, 1, 14)

    def test_cycle_uses_the_configured_rule(self) -> None:
        cycle = cycle_for(date(2026, 11, 10), config(15, DAYS_AFTER, 20))

        assert cycle.payment_due == date(2026, 12, 5)


class TestLastClosedCycle:
    def test_before_the_cutoff_it_is_the_previous_cycle(self) -> None:
        cycle = last_closed_cycle(date(2026, 11, 6), config(15))

        assert cycle.cutoff == date(2026, 10, 15)
        assert cycle.payment_due == date(2026, 11, 5)

    def test_on_the_cutoff_day_it_is_the_cycle_closing_today(self) -> None:
        assert last_closed_cycle(date(2026, 11, 15), config(15)).cutoff == date(2026, 11, 15)

    def test_the_day_after_the_cutoff(self) -> None:
        assert last_closed_cycle(date(2026, 11, 16), config(15)).cutoff == date(2026, 11, 15)


class TestConfigValidation:
    @pytest.mark.parametrize("cutoff_day", [0, 32])
    def test_rejects_invalid_cutoff_day(self, cutoff_day: int) -> None:
        with pytest.raises(InvalidCreditConfigError):
            config(cutoff_day)

    @pytest.mark.parametrize("day", [0, 32])
    def test_rejects_invalid_fixed_payment_day(self, day: int) -> None:
        with pytest.raises(InvalidCreditConfigError):
            config(15, FIXED, day)

    @pytest.mark.parametrize("days", [0, 61])
    def test_rejects_invalid_days_after_cutoff(self, days: int) -> None:
        with pytest.raises(InvalidCreditConfigError):
            config(15, DAYS_AFTER, days)

    def test_accepts_the_limits(self) -> None:
        config(31, FIXED, 31)
        config(1, DAYS_AFTER, 60)


class TestCreditAvailable:
    def test_limit_minus_debt(self) -> None:
        assert credit_available(Decimal("20000.00"), Decimal("-634.00")) == Decimal("19366.00")

    def test_without_debt_it_is_the_limit(self) -> None:
        assert credit_available(Decimal("20000.00"), Decimal("0.00")) == Decimal("20000.00")

    def test_credit_in_your_favor_adds_to_it(self) -> None:
        assert credit_available(Decimal("20000.00"), Decimal("150.00")) == Decimal("20150.00")

    def test_can_be_negative_when_over_the_limit(self) -> None:
        assert credit_available(Decimal("1000.00"), Decimal("-1200.00")) == Decimal("-200.00")

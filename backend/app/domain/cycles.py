"""Credit card billing cycles: cutoff dates, cycle ranges and payment due dates.

Rules (docs/PLANEACION.md, "Modelo de dominio y reglas de negocio"):

- A cycle runs from the day after the previous cutoff up to the cutoff day, inclusive:
  a purchase made on the cutoff day belongs to the cycle that closes that day.
- If the cutoff or payment day doesn't exist in a month (e.g. 31 in November),
  the last day of the month is used.
- The payment due date is either a fixed day of the month (the first one after the
  cutoff) or a number of calendar days after the cutoff, depending on the bank.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.enums import PaymentDueRule
from app.domain.errors import InvalidCreditConfigError

MAX_DAYS_AFTER_CUTOFF = 60


@dataclass(frozen=True)
class CreditCycleConfig:
    cutoff_day: int
    payment_due_rule: PaymentDueRule
    # Day of the month for FIXED_DAY, number of days for DAYS_AFTER_CUTOFF
    payment_due_value: int

    def __post_init__(self) -> None:
        validate_cycle_config(self.cutoff_day, self.payment_due_rule, self.payment_due_value)


@dataclass(frozen=True)
class CardCycle:
    start: date  # day after the previous cutoff
    cutoff: date  # last day of the cycle, inclusive
    payment_due: date

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.cutoff


def validate_cycle_config(cutoff_day: int, payment_due_rule: PaymentDueRule, value: int) -> None:
    if not 1 <= cutoff_day <= 31:
        raise InvalidCreditConfigError("Cutoff day must be between 1 and 31")
    if payment_due_rule is PaymentDueRule.FIXED_DAY and not 1 <= value <= 31:
        raise InvalidCreditConfigError("Payment day must be between 1 and 31")
    if payment_due_rule is PaymentDueRule.DAYS_AFTER_CUTOFF and not (
        1 <= value <= MAX_DAYS_AFTER_CUTOFF
    ):
        raise InvalidCreditConfigError(
            f"Days after cutoff must be between 1 and {MAX_DAYS_AFTER_CUTOFF}"
        )


def day_in_month(year: int, month: int, day: int) -> date:
    """The given day of the month, or the month's last day if it doesn't exist."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _shift_month(year: int, month: int, months: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + months
    return index // 12, index % 12 + 1


def cutoff_for(day: date, cutoff_day: int) -> date:
    """Cutoff date of the cycle that contains `day` (the cutoff on or after it)."""
    cutoff = day_in_month(day.year, day.month, cutoff_day)
    if day <= cutoff:
        return cutoff
    year, month = _shift_month(day.year, day.month, 1)
    return day_in_month(year, month, cutoff_day)


def previous_cutoff(cutoff: date, cutoff_day: int) -> date:
    year, month = _shift_month(cutoff.year, cutoff.month, -1)
    return day_in_month(year, month, cutoff_day)


def payment_due_date(cutoff: date, rule: PaymentDueRule, value: int) -> date:
    """Last day to pay the statement that closes on `cutoff`."""
    if rule is PaymentDueRule.DAYS_AFTER_CUTOFF:
        return cutoff + timedelta(days=value)

    # FIXED_DAY: the first date with that day of the month strictly after the cutoff
    due = day_in_month(cutoff.year, cutoff.month, value)
    if due > cutoff:
        return due
    year, month = _shift_month(cutoff.year, cutoff.month, 1)
    return day_in_month(year, month, value)


def cycle_for(day: date, config: CreditCycleConfig) -> CardCycle:
    """The billing cycle a purchase made on `day` belongs to."""
    cutoff = cutoff_for(day, config.cutoff_day)
    start = previous_cutoff(cutoff, config.cutoff_day) + timedelta(days=1)
    return CardCycle(
        start=start,
        cutoff=cutoff,
        payment_due=payment_due_date(cutoff, config.payment_due_rule, config.payment_due_value),
    )


def last_closed_cycle(today: date, config: CreditCycleConfig) -> CardCycle:
    """The most recent cycle whose cutoff already passed (or is today).

    This is the statement the user has to pay next.
    """
    current = cycle_for(today, config)
    if today == current.cutoff:
        return current
    return cycle_for(current.start - timedelta(days=1), config)


@dataclass(frozen=True)
class NextPayment:
    cycle: CardCycle
    # False when the last statement's due date already passed and the open cycle is shown:
    # its amount is what was charged so far, not a final statement
    is_closed: bool


def next_payment_cycle(today: date, config: CreditCycleConfig) -> NextPayment:
    """The statement to pay next.

    The earliest closed cycle whose due date hasn't passed (the due date itself still counts).
    If every closed cycle is past due, the open cycle: with cutoff on the 15th and payment
    on the 5th, from Dec 6 to Dec 15 that's the cycle that closes on Dec 15.
    An unpaid past-due statement isn't carried over (known limit of rule 8, reviewed in v1).
    """
    candidate = last_closed_cycle(today, config)
    if candidate.payment_due < today:
        return NextPayment(cycle_for(today, config), is_closed=False)

    # With a long "days after cutoff" rule an older statement may still be due before this one
    while True:
        previous = cycle_for(candidate.start - timedelta(days=1), config)
        if previous.payment_due < today:
            return NextPayment(candidate, is_closed=True)
        candidate = previous

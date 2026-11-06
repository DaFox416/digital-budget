"""Interest-free installment plans (MSI, "meses sin intereses").

Rules (docs/PLANEACION.md):

- A purchase in installments uses the card's full credit right away: it's recorded as one
  expense for the total. Only each installment counts towards the payment of its cycle.
- Installment = total / months rounded to cents; the last one absorbs the difference so the
  sum is exact. Amounts are rounded down, so the last installment is never the smallest
  one and can't turn negative (1,000 / 3 = 333.33 + 333.33 + 333.34).
- The first installment falls in the purchase's cycle; each following one, in the next cycle.
- Installments reduce the user's "available" money one at a time: the first on the purchase
  date and the rest on the first day of their cycle (the day after the previous cutoff).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal

from app.domain.cycles import CreditCycleConfig, cycle_for
from app.domain.errors import InvalidAmountError, InvalidInstallmentPlanError
from app.domain.money import CENT, to_money

MIN_MONTHS = 3
MAX_MONTHS = 48


@dataclass(frozen=True)
class ScheduledInstallment:
    number: int  # 1-based
    amount: Decimal
    cutoff: date  # cutoff of the statement it's billed in
    charged_on: date  # when it reduces the user's available money


def validate_months(months: int) -> None:
    if not MIN_MONTHS <= months <= MAX_MONTHS:
        raise InvalidInstallmentPlanError(f"Months must be between {MIN_MONTHS} and {MAX_MONTHS}")


def split_installments(total: Decimal | int | str, months: int) -> list[Decimal]:
    """Split a total into `months` installments that add up exactly to it."""
    validate_months(months)
    amount = to_money(total)
    if amount <= 0:
        raise InvalidAmountError("Total must be greater than zero")

    base = (amount / months).quantize(CENT, rounding=ROUND_DOWN)
    if base == 0:
        raise InvalidAmountError(f"Total is too small for {months} installments")

    last = amount - base * (months - 1)
    return [base] * (months - 1) + [last]


def installment_schedule(
    total: Decimal | int | str, months: int, purchased_on: date, config: CreditCycleConfig
) -> list[ScheduledInstallment]:
    """Installments with the cycle each one is billed in and the day it's charged."""
    schedule: list[ScheduledInstallment] = []
    cycle = cycle_for(purchased_on, config)

    for number, amount in enumerate(split_installments(total, months), start=1):
        charged_on = purchased_on if number == 1 else cycle.start
        schedule.append(ScheduledInstallment(number, amount, cycle.cutoff, charged_on))
        cycle = cycle_for(cycle.cutoff + timedelta(days=1), config)

    return schedule


def pending_to_charge(installments: Iterable[ScheduledInstallment], on: date) -> Decimal:
    """MSI por cargar: installments not yet charged to the available money on `on`.

    This part of the card's debt doesn't reduce "available" yet.
    """
    return to_money(sum((i.amount for i in installments if i.charged_on > on), Decimal("0")))

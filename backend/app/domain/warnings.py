"""Warnings before saving a credit card purchase (docs/PLANEACION.md).

They never block the purchase. If both levels apply, only level 2 is shown. Level 2 (more
than the real balance) applies in every mode; level 1 (more than "available") only in savings
mode, since simple mode doesn't show "available".
"""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import WarningLevel
from app.domain.money import to_money


@dataclass(frozen=True)
class PurchaseWarning:
    level: WarningLevel
    # How much the purchase goes over the figure it's compared with
    excess: Decimal


def purchase_warning(
    accounting_amount: Decimal,
    real_amount: Decimal,
    available: Decimal,
    real_balance: Decimal,
    savings_mode: bool,
) -> PurchaseWarning | None:
    """Amounts are positive magnitudes. Level 2 if the real amount is more than every debit and
    cash account holds; level 1 if the accounting amount is more than "available"."""
    if real_amount > real_balance:
        return PurchaseWarning(WarningLevel.OVER_REAL_BALANCE, to_money(real_amount - real_balance))
    if savings_mode and accounting_amount > available:
        return PurchaseWarning(WarningLevel.OVER_AVAILABLE, to_money(accounting_amount - available))
    return None


def installment_purchase_warning(
    first_installment_accounting: Decimal,
    total: Decimal,
    available: Decimal,
    real_balance: Decimal,
    savings_mode: bool,
) -> PurchaseWarning | None:
    """An MSI purchase only takes its first installment from "available" today, but uses the
    full total of credit: level 1 compares the first installment, level 2 the total."""
    return purchase_warning(
        first_installment_accounting, total, available, real_balance, savings_mode
    )

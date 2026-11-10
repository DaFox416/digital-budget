"""Warnings before saving a credit card purchase in savings mode (docs/PLANEACION.md).

They never block the purchase. If both levels apply, only level 2 is shown.
"""

from decimal import Decimal

from app.domain.enums import WarningLevel


def purchase_warning(
    accounting_amount: Decimal, real_amount: Decimal, available: Decimal, real_balance: Decimal
) -> WarningLevel | None:
    """Amounts are positive magnitudes. Level 2 if the real amount is more than every debit and
    cash account holds; level 1 if the accounting amount is more than "available"."""
    if real_amount > real_balance:
        return WarningLevel.OVER_REAL_BALANCE
    if accounting_amount > available:
        return WarningLevel.OVER_AVAILABLE
    return None


def installment_purchase_warning(
    first_installment_accounting: Decimal,
    total: Decimal,
    available: Decimal,
    real_balance: Decimal,
) -> WarningLevel | None:
    """An MSI purchase only takes its first installment from "available" today, but uses the
    full total of credit: level 1 compares the first installment, level 2 the total."""
    return purchase_warning(first_installment_accounting, total, available, real_balance)

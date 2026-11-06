"""Credit card statement amounts."""

from decimal import Decimal

from app.domain.money import to_money


def payment_for_no_interest(
    regular_charges: Decimal, installments_due: Decimal, payments_after_cutoff: Decimal
) -> Decimal:
    """Rule 8: what to pay by the due date so the closed cycle doesn't generate interest.

    regular_charges: net charges of the cycle without MSI purchases (purchases - refunds).
    installments_due: MSI installments billed in the cycle.
    payments_after_cutoff: card payments made after the cutoff.

    All three are positive magnitudes. Never negative: paying more leaves a credit in your
    favor on the card, not a negative payment.
    """
    due = regular_charges + installments_due - payments_after_cutoff
    return to_money(max(due, Decimal("0")))

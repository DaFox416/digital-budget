from decimal import Decimal


class DomainError(Exception):
    """A business rule was violated. The API turns these into 422 responses."""


class InvalidAmountError(DomainError):
    pass


class InvalidMovementError(DomainError):
    pass


class InvalidCreditConfigError(DomainError):
    pass


class InvalidInstallmentPlanError(DomainError):
    pass


class InvalidPreferencesError(DomainError):
    pass


class InvalidCommitmentError(DomainError):
    pass


class CreditLimitExceededError(DomainError):
    """A card purchase would go over the card's available credit. Never allowed, not even
    with a warning (docs/PLANEACION.md, 2026-11-11)."""

    def __init__(self, excess: Decimal) -> None:
        self.excess = excess
        super().__init__(f"The purchase goes over the card's available credit by ${excess:,.2f}")

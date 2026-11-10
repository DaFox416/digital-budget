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

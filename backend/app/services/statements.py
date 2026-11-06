import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.cycles import CardCycle, cycle_for, last_closed_cycle
from app.domain.enums import AccountType
from app.domain.money import to_money
from app.domain.statements import payment_for_no_interest
from app.models import Installment, InstallmentPlan
from app.repositories import accounts as accounts_repo
from app.repositories import statements as statements_repo
from app.services.accounts import cycle_config
from app.services.clock import today
from app.services.errors import NotFoundError


@dataclass(frozen=True)
class Statement:
    account_id: uuid.UUID
    cycle: CardCycle
    regular_charges: Decimal
    installments: list[tuple[Installment, InstallmentPlan]]
    installments_due: Decimal
    payments_after_cutoff: Decimal
    payment_for_no_interest: Decimal


def get_statement(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID, on: date | None = None
) -> Statement:
    """Statement of the cycle that contains `on`, or of the last closed cycle by default."""
    account = accounts_repo.get(session, user_id, account_id)
    if account is None or account.type is not AccountType.CREDIT:
        raise NotFoundError(f"Credit card {account_id} not found")
    assert account.credit_config is not None
    rules = cycle_config(account.credit_config)
    cycle = cycle_for(on, rules) if on is not None else last_closed_cycle(today(), rules)

    # Charges are negative on a card; flip them to positive magnitudes
    regular_charges = to_money(
        -statements_repo.regular_movements_total(
            session, user_id, account_id, cycle.start, cycle.cutoff
        )
    )
    installments = statements_repo.installments_billed_on(
        session, user_id, account_id, cycle.cutoff
    )
    installments_due = to_money(sum((i.amount for i, _ in installments), Decimal("0")))
    payments = to_money(
        statements_repo.payments_total(
            session, user_id, account_id, cycle.cutoff, cycle.payment_due
        )
    )

    return Statement(
        account_id=account_id,
        cycle=cycle,
        regular_charges=regular_charges,
        installments=installments,
        installments_due=installments_due,
        payments_after_cutoff=payments,
        payment_for_no_interest=payment_for_no_interest(
            regular_charges, installments_due, payments
        ),
    )

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.balances import credit_debt
from app.domain.cycles import CardCycle, next_payment_cycle
from app.domain.installments import ScheduledInstallment, pending_to_charge
from app.domain.savings import SavingsFigures
from app.repositories import installments as installments_repo
from app.services import savings as savings_service
from app.services import statements as statements_service
from app.services.accounts import cycle_config, list_accounts
from app.services.clock import today


@dataclass(frozen=True)
class NextPaymentSummary:
    cycle: CardCycle
    amount: Decimal
    is_closed: bool


@dataclass(frozen=True)
class CardSummary:
    account_id: uuid.UUID
    name: str
    debt: Decimal
    installments_pending: Decimal
    next_payment: NextPaymentSummary


@dataclass(frozen=True)
class Summary:
    on: date
    figures: SavingsFigures
    leftover_releasable: Decimal
    cards: list[CardSummary]


def get_summary(session: Session, user_id: uuid.UUID) -> Summary:
    """The seven savings mode figures and each card's next payment."""
    on = today()
    accounts = list_accounts(session, user_id)

    pending_by_card: defaultdict[uuid.UUID, list[ScheduledInstallment]] = defaultdict(list)
    for account_id, installment in installments_repo.list_pending(session, user_id, on):
        pending_by_card[account_id].append(
            ScheduledInstallment(
                installment.number,
                installment.amount,
                installment.cutoff_date,
                installment.charged_on,
            )
        )

    cards: list[CardSummary] = []
    for item in accounts:
        config = item.account.credit_config
        if config is None:
            continue
        next_payment = next_payment_cycle(on, cycle_config(config))
        # A few queries per card: fine for a handful of cards; optimize if it ever matters
        statement = statements_service.get_statement(
            session, user_id, item.account.id, next_payment.cycle.cutoff
        )
        cards.append(
            CardSummary(
                account_id=item.account.id,
                name=item.account.name,
                debt=credit_debt(item.balance),
                installments_pending=pending_to_charge(pending_by_card[item.account.id], on),
                next_payment=NextPaymentSummary(
                    cycle=next_payment.cycle,
                    amount=statement.payment_for_no_interest,
                    is_closed=next_payment.is_closed,
                ),
            )
        )

    current = savings_service.current_figures(session, user_id, on)
    return Summary(
        on=on,
        figures=current.figures,
        leftover_releasable=current.leftover_releasable,
        cards=cards,
    )

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.balances import account_balance, credit_available
from app.domain.cycles import CardCycle, CreditCycleConfig, cycle_for, last_closed_cycle
from app.domain.money import to_money
from app.models import Account, CreditConfig
from app.repositories import accounts as accounts_repo
from app.schemas.accounts import AccountCreate
from app.services.clock import today
from app.services.errors import ConflictError


@dataclass(frozen=True)
class CreditSummary:
    config: CreditConfig
    available: Decimal
    current_cycle: CardCycle
    last_statement: CardCycle


@dataclass(frozen=True)
class AccountWithBalance:
    account: Account
    balance: Decimal
    # Credit accounts only. None for credit accounts created before credit configs existed.
    credit: CreditSummary | None


def _cycle_config(config: CreditConfig) -> CreditCycleConfig:
    return CreditCycleConfig(
        cutoff_day=config.cutoff_day,
        payment_due_rule=config.payment_due_rule,
        payment_due_value=config.payment_due_value,
    )


def _with_balance(account: Account, balance: Decimal, on: date) -> AccountWithBalance:
    config = account.credit_config
    if config is None:
        return AccountWithBalance(account, balance, credit=None)

    cycle_config = _cycle_config(config)
    credit = CreditSummary(
        config=config,
        available=credit_available(config.credit_limit, balance),
        current_cycle=cycle_for(on, cycle_config),
        last_statement=last_closed_cycle(on, cycle_config),
    )
    return AccountWithBalance(account, balance, credit)


def list_accounts(session: Session, user_id: uuid.UUID) -> list[AccountWithBalance]:
    on = today()
    return [
        _with_balance(account, account_balance(account.initial_balance, [movements_total]), on)
        for account, movements_total in accounts_repo.list_with_movement_totals(session, user_id)
    ]


def create_account(session: Session, user_id: uuid.UUID, data: AccountCreate) -> AccountWithBalance:
    if accounts_repo.get_by_name(session, user_id, data.name) is not None:
        raise ConflictError(f"An account named {data.name!r} already exists")

    account = Account(
        user_id=user_id,
        type=data.type,
        name=data.name,
        initial_balance=to_money(data.initial_balance),
        color=data.color,
        # New accounts go last
        position=accounts_repo.count(session, user_id),
    )
    if data.credit is not None:
        # Raises InvalidCreditConfigError (422) if the payment value doesn't fit the rule
        CreditCycleConfig(
            cutoff_day=data.credit.cutoff_day,
            payment_due_rule=data.credit.payment_due_rule,
            payment_due_value=data.credit.payment_due_value,
        )
        account.credit_config = CreditConfig(
            user_id=user_id,
            credit_limit=to_money(data.credit.credit_limit),
            cutoff_day=data.credit.cutoff_day,
            payment_due_rule=data.credit.payment_due_rule,
            payment_due_value=data.credit.payment_due_value,
        )
    # Account and credit config are saved in the same transaction
    session.add(account)
    session.commit()

    return _with_balance(account, account_balance(account.initial_balance, []), today())

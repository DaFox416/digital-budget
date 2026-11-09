import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.balances import account_balance, credit_available
from app.domain.cycles import (
    CardCycle,
    CreditCycleConfig,
    cycle_for,
    last_closed_cycle,
    updated_cycle_config,
)
from app.domain.errors import InvalidCreditConfigError
from app.domain.installments import installment_schedule
from app.domain.money import to_money
from app.models import Account, CreditConfig
from app.repositories import accounts as accounts_repo
from app.repositories import installments as installments_repo
from app.schemas.accounts import AccountCreate, AccountUpdate, CreditConfigUpdate
from app.services.clock import today
from app.services.errors import ConflictError, NotFoundError


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
    # Credit accounts only (their config is required); None for debit and cash
    credit: CreditSummary | None


def cycle_config(config: CreditConfig) -> CreditCycleConfig:
    return CreditCycleConfig(
        cutoff_day=config.cutoff_day,
        payment_due_rule=config.payment_due_rule,
        payment_due_value=config.payment_due_value,
    )


def _with_balance(account: Account, balance: Decimal, on: date) -> AccountWithBalance:
    config = account.credit_config
    if config is None:
        return AccountWithBalance(account, balance, credit=None)

    rules = cycle_config(config)
    credit = CreditSummary(
        config=config,
        available=credit_available(config.credit_limit, balance),
        current_cycle=cycle_for(on, rules),
        last_statement=last_closed_cycle(on, rules),
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


def update_account(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID, data: AccountUpdate
) -> AccountWithBalance:
    """Edit an account and its credit config in one transaction.

    Changing the cutoff day recalculates the cutoff and charge dates of every MSI installment
    of the card. Amounts don't change: they only depend on the total and the months.
    """
    account = accounts_repo.get(session, user_id, account_id)
    if account is None:
        raise NotFoundError(f"Account {account_id} not found")

    # Validate everything before touching the account: a rejected edit must change nothing
    new_name = data.name if data.name != account.name else None
    if new_name is not None and accounts_repo.get_by_name(session, user_id, new_name) is not None:
        raise ConflictError(f"An account named {new_name!r} already exists")
    rules = _validated_cycle_config(account, data.credit) if data.credit is not None else None

    if new_name is not None:
        account.name = new_name
    if data.initial_balance is not None:
        account.initial_balance = to_money(data.initial_balance)
    # Sent as null removes the color; left out keeps it
    if "color" in data.model_fields_set:
        account.color = data.color
    if data.credit is not None and rules is not None:
        _apply_credit_config(session, user_id, account, data.credit, rules)

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    total = accounts_repo.movements_total(session, user_id, account.id)
    return _with_balance(account, account_balance(account.initial_balance, [total]), today())


def _validated_cycle_config(account: Account, credit: CreditConfigUpdate) -> CreditCycleConfig:
    """The merged cycle config. Raises InvalidCreditConfigError (422) if it isn't valid."""
    if account.credit_config is None:
        raise InvalidCreditConfigError(f"A {account.type} account can't have a credit config")
    return updated_cycle_config(
        cycle_config(account.credit_config),
        credit.cutoff_day,
        credit.payment_due_rule,
        credit.payment_due_value,
    )


def _apply_credit_config(
    session: Session,
    user_id: uuid.UUID,
    account: Account,
    credit: CreditConfigUpdate,
    rules: CreditCycleConfig,
) -> None:
    config = account.credit_config
    assert config is not None  # checked by _validated_cycle_config
    current = cycle_config(config)
    if credit.credit_limit is not None:
        config.credit_limit = to_money(credit.credit_limit)
    config.cutoff_day = rules.cutoff_day
    config.payment_due_rule = rules.payment_due_rule
    config.payment_due_value = rules.payment_due_value

    if rules.cutoff_day == current.cutoff_day:
        # Due dates aren't stored, so a new payment rule needs nothing else
        return
    for plan in installments_repo.list_plans_for_account(session, user_id, account.id):
        schedule = installment_schedule(plan.total, plan.months, plan.purchased_on, rules)
        # Both are ordered by number (the relationship orders installments by it)
        for installment, item in zip(plan.installments, schedule, strict=True):
            installment.cutoff_date = item.cutoff
            installment.charged_on = item.charged_on

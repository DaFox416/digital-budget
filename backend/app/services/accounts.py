import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.balances import account_balance
from app.domain.money import to_money
from app.models import Account
from app.repositories import accounts as accounts_repo
from app.schemas.accounts import AccountCreate
from app.services.errors import ConflictError


@dataclass(frozen=True)
class AccountWithBalance:
    account: Account
    balance: Decimal


def list_accounts(session: Session, user_id: uuid.UUID) -> list[AccountWithBalance]:
    return [
        AccountWithBalance(account, account_balance(account.initial_balance, [movements_total]))
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
    session.add(account)
    session.commit()

    return AccountWithBalance(account, account_balance(account.initial_balance, []))

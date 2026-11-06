from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.accounts import AccountCreate, AccountRead
from app.services import accounts as accounts_service
from app.services.accounts import AccountWithBalance

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _to_read(item: AccountWithBalance) -> AccountRead:
    account = item.account
    return AccountRead(
        id=account.id,
        type=account.type,
        name=account.name,
        initial_balance=account.initial_balance,
        balance=item.balance,
        color=account.color,
        position=account.position,
    )


@router.get("")
def list_accounts(session: SessionDep, user_id: CurrentUserId) -> list[AccountRead]:
    """Active accounts with their current balance."""
    return [_to_read(item) for item in accounts_service.list_accounts(session, user_id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, session: SessionDep, user_id: CurrentUserId) -> AccountRead:
    return _to_read(accounts_service.create_account(session, user_id, data))

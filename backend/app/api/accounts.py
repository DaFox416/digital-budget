from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, SessionDep
from app.domain.cycles import CardCycle
from app.schemas.accounts import AccountCreate, AccountRead, CardCycleRead, CreditRead
from app.services import accounts as accounts_service
from app.services.accounts import AccountWithBalance, CreditSummary

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _cycle_read(cycle: CardCycle) -> CardCycleRead:
    return CardCycleRead(start=cycle.start, cutoff=cycle.cutoff, payment_due=cycle.payment_due)


def _credit_read(credit: CreditSummary | None) -> CreditRead | None:
    if credit is None:
        return None
    config = credit.config
    return CreditRead(
        credit_limit=config.credit_limit,
        cutoff_day=config.cutoff_day,
        payment_due_rule=config.payment_due_rule,
        payment_due_value=config.payment_due_value,
        available=credit.available,
        current_cycle=_cycle_read(credit.current_cycle),
        last_statement=_cycle_read(credit.last_statement),
    )


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
        credit=_credit_read(item.credit),
    )


@router.get("")
def list_accounts(session: SessionDep, user_id: CurrentUserId) -> list[AccountRead]:
    """Active accounts with their current balance."""
    return [_to_read(item) for item in accounts_service.list_accounts(session, user_id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, session: SessionDep, user_id: CurrentUserId) -> AccountRead:
    return _to_read(accounts_service.create_account(session, user_id, data))

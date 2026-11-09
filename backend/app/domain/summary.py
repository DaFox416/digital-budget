"""Main figures of the home screen (savings mode figures arrive on day 10)."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from app.domain.balances import credit_debt
from app.domain.enums import AccountType
from app.domain.money import to_money

REAL_BALANCE_ACCOUNT_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH})


@dataclass(frozen=True)
class SummaryTotals:
    # What's in debit and cash accounts; savings accounts (Sobrante, goals) don't count
    real_balance: Decimal
    # What's owed on every card; a card with a credit in your favor subtracts
    card_debt: Decimal


def summary_totals(balances: Iterable[tuple[AccountType, Decimal]]) -> SummaryTotals:
    """Totals from (account type, balance) pairs of the user's active accounts."""
    real_balance = Decimal("0")
    card_debt = Decimal("0")
    for account_type, balance in balances:
        if account_type in REAL_BALANCE_ACCOUNT_TYPES:
            real_balance += balance
        elif account_type is AccountType.CREDIT:
            card_debt += credit_debt(balance)
    return SummaryTotals(real_balance=to_money(real_balance), card_debt=to_money(card_debt))

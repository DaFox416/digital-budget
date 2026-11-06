from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import MovementType
from app.domain.movements import TransferPlan
from app.models import Movement
from app.services import movements as movements_service
from tests.api.helpers import balances, create_account


def post_transfer(client: TestClient, source: str, destination: str, amount: str) -> Any:
    return client.post(
        "/api/v1/transfers",
        json={"source_account_id": source, "destination_account_id": destination, "amount": amount},
    )


def test_transfer_between_debit_accounts(client: TestClient) -> None:
    bbva = create_account(client, "BBVA", initial_balance="5000")
    nu = create_account(client, "Nu")

    response = post_transfer(client, bbva["id"], nu["id"], "2000")

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "transfer"
    assert body["source"]["real_amount"] == "-2000.00"
    assert body["destination"]["real_amount"] == "2000.00"
    # Both legs share the group id
    assert body["source"]["transfer_group_id"] == body["transfer_group_id"]
    assert body["destination"]["transfer_group_id"] == body["transfer_group_id"]
    assert balances(client) == {"BBVA": "3000.00", "Nu": "2000.00"}


def test_paying_a_credit_card_is_a_card_payment(client: TestClient) -> None:
    bbva = create_account(client, "BBVA", initial_balance="14777.11")
    card = create_account(client, "TDC Oro", type="credit", initial_balance="-634")

    response = post_transfer(client, bbva["id"], card["id"], "634")

    assert response.status_code == 201
    assert response.json()["type"] == "card_payment"
    # Real balance and debt drop by the same amount
    assert balances(client) == {"BBVA": "14143.11", "TDC Oro": "0.00"}


def test_transfer_to_the_same_account_is_rejected(client: TestClient) -> None:
    bbva = create_account(client, "BBVA")

    response = post_transfer(client, bbva["id"], bbva["id"], "100")

    assert response.status_code == 422
    assert "different accounts" in response.json()["detail"]


def test_transfer_from_a_credit_card_is_rejected(client: TestClient) -> None:
    card = create_account(client, "TDC Oro", type="credit")
    bbva = create_account(client, "BBVA")

    response = post_transfer(client, card["id"], bbva["id"], "100")

    assert response.status_code == 422


def test_transfer_appears_in_both_accounts(client: TestClient) -> None:
    bbva = create_account(client, "BBVA", initial_balance="1000")
    cash = create_account(client, "Efectivo", type="cash")
    post_transfer(client, bbva["id"], cash["id"], "300")

    cash_movements = client.get("/api/v1/movements", params={"account_id": cash["id"]}).json()

    assert [m["real_amount"] for m in cash_movements] == ["300.00"]


def test_transfer_saves_both_legs_or_neither(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the second leg fails at the database, the first one must not be saved either."""
    bbva = create_account(client, "BBVA", initial_balance="1000")
    nu = create_account(client, "Nu")
    # A broken plan whose destination leg violates the CHECK (real_amount <> 0) in Postgres
    broken_plan = TransferPlan(MovementType.TRANSFER, Decimal("-100.00"), Decimal("0.00"))
    monkeypatch.setattr(movements_service, "plan_transfer", lambda *_: broken_plan)

    with pytest.raises(IntegrityError):
        post_transfer(client, bbva["id"], nu["id"], "100")

    saved = db_session.scalar(select(func.count()).select_from(Movement))
    assert saved == 0
    assert balances(client) == {"BBVA": "1000.00", "Nu": "0.00"}

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services import movements as movements_service
from tests.api.helpers import balances, create_account


def post_movement(client: TestClient, **fields: object) -> dict[str, object]:
    response = client.post("/api/v1/movements", json=fields)
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def test_expense_is_stored_negative_and_lowers_the_balance(client: TestClient) -> None:
    account = create_account(client, "BBVA", initial_balance="5000")

    movement = post_movement(
        client, account_id=account["id"], type="expense", amount="387.56", description="Cine"
    )

    assert movement["real_amount"] == "-387.56"
    assert movement["accounting_amount"] == "-387.56"
    assert movement["description"] == "Cine"
    assert balances(client)["BBVA"] == "4612.44"


def test_income_raises_the_balance(client: TestClient) -> None:
    account = create_account(client, "BBVA", initial_balance="4612.44")

    post_movement(client, account_id=account["id"], type="income", amount="10164.67")

    assert balances(client)["BBVA"] == "14777.11"


def test_accounting_amount_can_differ_in_savings_mode(client: TestClient) -> None:
    account = create_account(client, "BBVA")

    movement = post_movement(
        client, account_id=account["id"], type="expense", amount="387.56", accounting_amount="400"
    )

    assert movement["real_amount"] == "-387.56"
    assert movement["accounting_amount"] == "-400.00"


def test_expense_on_credit_card_creates_debt(client: TestClient) -> None:
    card = create_account(client, "TDC Oro", type="credit")

    post_movement(client, account_id=card["id"], type="expense", amount="634")

    assert balances(client)["TDC Oro"] == "-634.00"


def test_movement_with_category(client: TestClient) -> None:
    account = create_account(client, "BBVA")
    categories = client.get("/api/v1/categories").json()
    food = next(category for category in categories if category["name"] == "Comida")

    movement = post_movement(
        client, account_id=account["id"], type="expense", amount="350", category_id=food["id"]
    )

    assert movement["category_id"] == food["id"]


def test_date_defaults_to_today_in_mexico(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(movements_service, "today", lambda: date(2026, 11, 5))
    account = create_account(client, "BBVA")

    movement = post_movement(client, account_id=account["id"], type="expense", amount="90")

    assert movement["occurred_on"] == "2026-11-05"


def test_unknown_account_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/movements",
        json={"account_id": str(uuid.uuid4()), "type": "expense", "amount": "10"},
    )

    assert response.status_code == 404


def test_unknown_category_returns_404(client: TestClient) -> None:
    account = create_account(client, "BBVA")

    response = client.post(
        "/api/v1/movements",
        json={
            "account_id": account["id"],
            "type": "expense",
            "amount": "10",
            "category_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 404


@pytest.mark.parametrize("amount", ["0", "-10", "1.999"])
def test_rejects_invalid_amounts(client: TestClient, amount: str) -> None:
    account = create_account(client, "BBVA")

    response = client.post(
        "/api/v1/movements", json={"account_id": account["id"], "type": "expense", "amount": amount}
    )

    assert response.status_code == 422


def test_transfer_type_is_not_accepted_here(client: TestClient) -> None:
    account = create_account(client, "BBVA")

    response = client.post(
        "/api/v1/movements",
        json={"account_id": account["id"], "type": "transfer", "amount": "10"},
    )

    assert response.status_code == 422


def test_list_movements_newest_first_and_by_account(client: TestClient) -> None:
    bbva = create_account(client, "BBVA")
    cash = create_account(client, "Efectivo", type="cash")
    post_movement(
        client, account_id=bbva["id"], type="expense", amount="1", occurred_on="2026-11-01"
    )
    post_movement(
        client, account_id=bbva["id"], type="expense", amount="2", occurred_on="2026-11-03"
    )
    post_movement(
        client, account_id=cash["id"], type="expense", amount="3", occurred_on="2026-11-02"
    )

    all_amounts = [m["real_amount"] for m in client.get("/api/v1/movements").json()]
    bbva_amounts = [
        m["real_amount"]
        for m in client.get("/api/v1/movements", params={"account_id": bbva["id"]}).json()
    ]

    assert all_amounts == ["-2.00", "-3.00", "-1.00"]
    assert bbva_amounts == ["-2.00", "-1.00"]

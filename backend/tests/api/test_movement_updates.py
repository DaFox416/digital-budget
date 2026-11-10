from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import balances, create_account


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("accounts", "installments", "statements", "movements"):
        monkeypatch.setattr(f"app.services.{module}.today", lambda: date(2026, 11, 20))


def post(client: TestClient, path: str, **fields: Any) -> dict[str, Any]:
    response = client.post(f"/api/v1/{path}", json=fields)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def patch(client: TestClient, movement_id: str, **fields: Any) -> Any:
    return client.patch(f"/api/v1/movements/{movement_id}", json=fields)


def category_ids(client: TestClient) -> list[str]:
    return [str(category["id"]) for category in client.get("/api/v1/categories").json()]


@pytest.fixture
def cine(client: TestClient) -> dict[str, Any]:
    """Cine con débito en modo ahorro: real 387.56, contable 400."""
    bbva = create_account(client, "BBVA", initial_balance="5000")
    return post(
        client,
        "movements",
        account_id=bbva["id"],
        type="expense",
        amount="387.56",
        accounting_amount="400",
        description="Cine",
        category_id=category_ids(client)[0],
        occurred_on="2026-11-10",
    )


class TestExpensesAndIncome:
    def test_edits_amount_and_balance_follows(
        self, client: TestClient, cine: dict[str, Any]
    ) -> None:
        response = patch(client, cine["id"], amount="450")

        assert response.status_code == 200
        body = response.json()
        assert body["real_amount"] == "-450.00"
        # Only the amount: accounting resets to it
        assert body["accounting_amount"] == "-450.00"
        assert balances(client)["BBVA"] == "4550.00"

    def test_edits_date_and_description(self, client: TestClient, cine: dict[str, Any]) -> None:
        body = patch(client, cine["id"], occurred_on="2026-11-11", description="Cine IMAX").json()

        assert body["occurred_on"] == "2026-11-11"
        assert body["description"] == "Cine IMAX"
        # Fields left out don't change
        assert body["real_amount"] == "-387.56"
        assert body["accounting_amount"] == "-400.00"
        assert body["category_id"] == cine["category_id"]

    def test_changing_the_type_is_rejected(self, client: TestClient, cine: dict[str, Any]) -> None:
        response = patch(client, cine["id"], type="income")

        assert response.status_code == 422
        movement = client.get("/api/v1/movements").json()[0]
        assert (movement["account_id"], movement["type"]) == (cine["account_id"], "expense")


class TestTransfers:
    @pytest.fixture
    def transfer(self, client: TestClient) -> dict[str, Any]:
        bbva = create_account(client, "BBVA", initial_balance="5000")
        nu = create_account(client, "Nu")
        return post(
            client,
            "transfers",
            source_account_id=bbva["id"],
            destination_account_id=nu["id"],
            amount="2000",
            description="Ahorro",
        )

    def test_editing_one_leg_changes_both(
        self, client: TestClient, transfer: dict[str, Any]
    ) -> None:
        response = patch(
            client,
            transfer["destination"]["id"],
            amount="1500",
            occurred_on="2026-11-12",
            description="Mes",
        )

        assert response.status_code == 200
        legs = {
            movement["id"]: movement
            for movement in client.get("/api/v1/movements").json()
            if movement["transfer_group_id"] == transfer["transfer_group_id"]
        }
        source = legs[transfer["source"]["id"]]
        destination = legs[transfer["destination"]["id"]]
        assert (source["real_amount"], source["accounting_amount"]) == ("-1500.00", "-1500.00")
        assert (destination["real_amount"], destination["accounting_amount"]) == (
            "1500.00",
            "1500.00",
        )
        assert {source["occurred_on"], destination["occurred_on"]} == {"2026-11-12"}
        assert {source["description"], destination["description"]} == {"Mes"}
        assert balances(client) == {"BBVA": "3500.00", "Nu": "1500.00"}

    def test_accounting_amount_is_rejected(
        self, client: TestClient, transfer: dict[str, Any]
    ) -> None:
        response = patch(client, transfer["source"]["id"], accounting_amount="1000")

        assert response.status_code == 422
        assert "accounting_amount" in response.json()["detail"]
        assert balances(client) == {"BBVA": "3000.00", "Nu": "2000.00"}


class TestNotEditable:
    def test_msi_purchase_is_a_conflict(self, client: TestClient) -> None:
        card = create_account(client, "TDC Oro", type="credit")
        plan = post(client, "installment-plans", account_id=card["id"], total="12000", months=12)

        response = patch(client, plan["movement_id"], description="Laptop")

        assert response.status_code == 409
        assert "MSI" in response.json()["detail"]

    def test_deleted_movement(self, client: TestClient, cine: dict[str, Any]) -> None:
        assert client.delete(f"/api/v1/movements/{cine['id']}").status_code == 204

        assert patch(client, cine["id"], description="x").status_code == 404


def test_moving_a_card_expense_to_the_next_cycle(client: TestClient) -> None:
    card = create_account(client, "TDC Oro", type="credit")
    despensa = post(
        client,
        "movements",
        account_id=card["id"],
        type="expense",
        amount="634",
        occurred_on="2026-11-15",
    )

    def regular_charges(cycle: str) -> str:
        response = client.get(f"/api/v1/cards/{card['id']}/statement", params={"cycle": cycle})
        assert response.status_code == 200, response.text
        return str(response.json()["regular_charges"])

    # Cutoff on the 15th: the 15th closes this cycle, the 16th starts the next one
    assert regular_charges("2026-11-15") == "634.00"

    assert patch(client, despensa["id"], occurred_on="2026-11-16").status_code == 200

    assert regular_charges("2026-11-15") == "0.00"
    assert regular_charges("2026-12-15") == "634.00"

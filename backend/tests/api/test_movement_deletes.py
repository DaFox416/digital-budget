import uuid
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


def delete(client: TestClient, movement_id: str) -> Any:
    return client.delete(f"/api/v1/movements/{movement_id}")


def restore(client: TestClient, movement_id: str) -> Any:
    return client.post(f"/api/v1/movements/{movement_id}/restore")


def listed_ids(client: TestClient) -> set[str]:
    return {movement["id"] for movement in client.get("/api/v1/movements").json()}


class TestExpenses:
    @pytest.fixture
    def cine(self, client: TestClient) -> dict[str, Any]:
        bbva = create_account(client, "BBVA", initial_balance="5000")
        return post(client, "movements", account_id=bbva["id"], type="expense", amount="387.56")

    def test_delete_hides_it_and_restores_the_balance(
        self, client: TestClient, cine: dict[str, Any]
    ) -> None:
        response = delete(client, cine["id"])

        assert response.status_code == 204
        assert response.content == b""
        assert cine["id"] not in listed_ids(client)
        assert balances(client)["BBVA"] == "5000.00"

    def test_restore_brings_it_back(self, client: TestClient, cine: dict[str, Any]) -> None:
        delete(client, cine["id"])

        response = restore(client, cine["id"])

        assert response.status_code == 200
        assert response.json()["id"] == cine["id"]
        assert response.json()["real_amount"] == "-387.56"
        assert cine["id"] in listed_ids(client)
        assert balances(client)["BBVA"] == "4612.44"

    def test_deleting_twice_is_not_found(self, client: TestClient, cine: dict[str, Any]) -> None:
        delete(client, cine["id"])

        assert delete(client, cine["id"]).status_code == 404

    def test_restoring_an_active_movement_is_a_conflict(
        self, client: TestClient, cine: dict[str, Any]
    ) -> None:
        response = restore(client, cine["id"])

        assert response.status_code == 409
        assert "isn't deleted" in response.json()["detail"]

    def test_unknown_movement(self, client: TestClient) -> None:
        movement_id = str(uuid.uuid4())

        assert delete(client, movement_id).status_code == 404
        assert restore(client, movement_id).status_code == 404


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
        )

    @pytest.mark.parametrize(
        ("deleted", "restored"), [("source", "destination"), ("destination", "source")]
    )
    def test_both_legs_go_and_come_back_together(
        self, client: TestClient, transfer: dict[str, Any], deleted: str, restored: str
    ) -> None:
        legs = {transfer["source"]["id"], transfer["destination"]["id"]}

        assert delete(client, transfer[deleted]["id"]).status_code == 204

        assert not legs & listed_ids(client)
        assert balances(client) == {"BBVA": "5000.00", "Nu": "0.00"}

        # Undo from the other leg
        assert restore(client, transfer[restored]["id"]).status_code == 200

        assert legs <= listed_ids(client)
        assert balances(client) == {"BBVA": "3000.00", "Nu": "2000.00"}

    def test_card_payment(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA", initial_balance="14777.11")
        card = create_account(client, "TDC Oro", type="credit", initial_balance="-634")
        payment = post(
            client,
            "transfers",
            source_account_id=bbva["id"],
            destination_account_id=card["id"],
            amount="634",
        )

        delete(client, payment["source"]["id"])

        assert balances(client) == {"BBVA": "14777.11", "TDC Oro": "-634.00"}


class TestInstallmentPurchases:
    @pytest.fixture
    def card(self, client: TestClient) -> dict[str, Any]:
        return create_account(client, "TDC Oro", type="credit")

    @pytest.fixture
    def laptop(self, client: TestClient, card: dict[str, Any]) -> dict[str, Any]:
        return post(
            client,
            "installment-plans",
            account_id=card["id"],
            total="12000",
            months=12,
            purchased_on="2026-11-10",
        )

    def statement(self, client: TestClient, card: dict[str, Any]) -> dict[str, Any]:
        response = client.get(
            f"/api/v1/cards/{card['id']}/statement", params={"cycle": "2026-11-15"}
        )
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    def available_credit(self, client: TestClient, card: dict[str, Any]) -> str:
        accounts = client.get("/api/v1/accounts").json()
        account = next(item for item in accounts if item["id"] == card["id"])
        return str(account["credit"]["available"])

    def test_delete_takes_it_off_the_statement_and_frees_the_credit(
        self, client: TestClient, card: dict[str, Any], laptop: dict[str, Any]
    ) -> None:
        assert self.statement(client, card)["installments_due"] == "1000.00"
        assert self.available_credit(client, card) == "8000.00"

        assert delete(client, laptop["movement_id"]).status_code == 204

        result = self.statement(client, card)
        assert result["installments"] == []
        assert result["installments_due"] == "0.00"
        assert self.available_credit(client, card) == "20000.00"

    def test_restore_puts_it_back_on_the_statement(
        self, client: TestClient, card: dict[str, Any], laptop: dict[str, Any]
    ) -> None:
        delete(client, laptop["movement_id"])

        assert restore(client, laptop["movement_id"]).status_code == 200

        result = self.statement(client, card)
        assert [item["number"] for item in result["installments"]] == [1]
        assert result["installments_due"] == "1000.00"
        assert self.available_credit(client, card) == "8000.00"

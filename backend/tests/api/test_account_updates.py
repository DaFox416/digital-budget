from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import create_account


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("accounts", "installments", "statements", "movements", "summary"):
        monkeypatch.setattr(f"app.services.{module}.today", lambda: date(2026, 11, 20))


def patch(client: TestClient, account_id: str, **fields: Any) -> Any:
    return client.patch(f"/api/v1/accounts/{account_id}", json=fields)


def summary(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/v1/summary")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


class TestAccountFields:
    def test_rename(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA")

        response = patch(client, bbva["id"], name="BBVA Nómina")

        assert response.status_code == 200
        assert response.json()["name"] == "BBVA Nómina"

    def test_duplicate_name_is_a_conflict(self, client: TestClient) -> None:
        create_account(client, "Nu")
        bbva = create_account(client, "BBVA")

        response = patch(client, bbva["id"], name="Nu")

        assert response.status_code == 409

    def test_set_and_remove_the_color(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA")

        assert patch(client, bbva["id"], color="#1A73E8").json()["color"] == "#1A73E8"
        # Left out keeps it
        assert patch(client, bbva["id"], name="BBVA 2").json()["color"] == "#1A73E8"
        assert patch(client, bbva["id"], color=None).json()["color"] is None

    def test_fixing_the_initial_balance_updates_every_figure(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA", initial_balance="500")
        client.post(
            "/api/v1/movements",
            json={"account_id": bbva["id"], "type": "expense", "amount": "387.56"},
        )

        body = patch(client, bbva["id"], initial_balance="5000").json()

        assert body["initial_balance"] == "5000.00"
        assert body["balance"] == "4612.44"
        assert summary(client)["real_balance"] == "4612.44"

    def test_the_type_is_not_editable(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA")

        assert patch(client, bbva["id"], type="cash").status_code == 422
        account = client.get("/api/v1/accounts").json()[0]
        assert (account["type"], account["position"]) == ("debit", 0)


class TestCreditConfig:
    @pytest.fixture
    def card(self, client: TestClient) -> dict[str, Any]:
        # Cutoff on the 15th, payment on the 5th, limit 20,000
        return create_account(client, "TDC Oro", type="credit")

    def test_raising_the_limit_raises_available_credit(
        self, client: TestClient, card: dict[str, Any]
    ) -> None:
        credit = patch(client, card["id"], credit={"credit_limit": "35000"}).json()["credit"]

        assert credit["credit_limit"] == "35000.00"
        assert credit["available"] == "35000.00"
        # The rest of the config is kept
        assert (credit["cutoff_day"], credit["payment_due_value"]) == (15, 5)

    def test_changing_the_payment_rule_moves_the_due_date(
        self, client: TestClient, card: dict[str, Any]
    ) -> None:
        credit = patch(
            client,
            card["id"],
            credit={"payment_due_rule": "days_after_cutoff", "payment_due_value": 25},
        ).json()["credit"]

        assert credit["payment_due_rule"] == "days_after_cutoff"
        # Nov 15 + 25 days
        assert credit["last_statement"]["payment_due"] == "2026-12-10"
        assert summary(client)["cards"][0]["next_payment"]["payment_due"] == "2026-12-10"

    def test_a_rejected_edit_changes_nothing(
        self, client: TestClient, card: dict[str, Any]
    ) -> None:
        response = patch(client, card["id"], name="Oro", credit={"payment_due_value": 45})

        assert response.status_code == 422
        account = client.get("/api/v1/accounts").json()[0]
        assert account["name"] == "TDC Oro"
        assert account["credit"]["payment_due_value"] == 5


class TestCutoffChangeWithMsi:
    """Fixing the cutoff from the 15th to the 20th on a card with a 12 MSI laptop."""

    @pytest.fixture
    def card(self, client: TestClient) -> dict[str, Any]:
        card = create_account(client, "TDC Oro", type="credit")
        response = client.post(
            "/api/v1/installment-plans",
            json={
                "account_id": card["id"],
                "total": "12000",
                "months": 12,
                "purchased_on": "2026-11-10",
            },
        )
        assert response.status_code == 201, response.text
        return card

    def statement(self, client: TestClient, card: dict[str, Any], cycle: str) -> dict[str, Any]:
        response = client.get(f"/api/v1/cards/{card['id']}/statement", params={"cycle": cycle})
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    def test_installments_move_to_the_new_cutoffs(
        self, client: TestClient, card: dict[str, Any]
    ) -> None:
        # With the 15th, installment 2 was charged on Nov 16: 10,000 pending on Nov 20
        assert summary(client)["installments_pending"] == "10000.00"

        response = patch(client, card["id"], credit={"cutoff_day": 20})

        assert response.status_code == 200
        november = self.statement(client, card, "2026-11-20")
        assert november["cutoff"] == "2026-11-20"
        assert [item["number"] for item in november["installments"]] == [1]
        december = self.statement(client, card, "2026-12-20")
        assert [item["number"] for item in december["installments"]] == [2]
        # Installment 2 is now charged on Nov 21, the day after the new cutoff
        assert summary(client)["installments_pending"] == "11000.00"
        # Amounts and debt don't change
        assert november["installments_due"] == "1000.00"
        assert summary(client)["card_debt"] == "12000.00"

    def test_deleted_purchases_are_rescheduled_too(
        self, client: TestClient, card: dict[str, Any]
    ) -> None:
        movement_id = client.get("/api/v1/movements").json()[0]["id"]
        assert client.delete(f"/api/v1/movements/{movement_id}").status_code == 204

        patch(client, card["id"], credit={"cutoff_day": 20})
        assert client.post(f"/api/v1/movements/{movement_id}/restore").status_code == 200

        november = self.statement(client, card, "2026-11-20")
        assert [item["number"] for item in november["installments"]] == [1]

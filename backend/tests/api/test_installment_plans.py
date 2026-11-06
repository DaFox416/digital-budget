from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import balances, create_account


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("accounts", "installments", "statements", "movements"):
        monkeypatch.setattr(f"app.services.{module}.today", lambda: date(2026, 11, 20))


def post_plan(client: TestClient, account_id: str, total: str, months: int, **fields: Any) -> Any:
    return client.post(
        "/api/v1/installment-plans",
        json={"account_id": account_id, "total": total, "months": months, **fields},
    )


def post_movement(client: TestClient, account_id: str, type: str, amount: str, on: str) -> None:
    response = client.post(
        "/api/v1/movements",
        json={"account_id": account_id, "type": type, "amount": amount, "occurred_on": on},
    )
    assert response.status_code == 201, response.text


def pay_card(client: TestClient, source_id: str, card_id: str, amount: str, on: str) -> None:
    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source_id,
            "destination_account_id": card_id,
            "amount": amount,
            "occurred_on": on,
        },
    )
    assert response.status_code == 201, response.text


def statement(client: TestClient, card_id: str, cycle: str | None = None) -> dict[str, Any]:
    params = {"cycle": cycle} if cycle else {}
    response = client.get(f"/api/v1/cards/{card_id}/statement", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


class TestCreatePlan:
    def test_creates_the_installments(self, client: TestClient) -> None:
        card = create_account(client, "TDC Oro", type="credit")

        response = post_plan(
            client, card["id"], "12000", 12, purchased_on="2026-11-10", description="Laptop"
        )

        assert response.status_code == 201
        plan = response.json()
        assert plan["total"] == "12000.00"
        assert len(plan["installments"]) == 12
        assert plan["installments"][0] == {
            "number": 1,
            "amount": "1000.00",
            "accounting_amount": "1000.00",
            "cutoff_date": "2026-11-15",
            "charged_on": "2026-11-10",
        }
        assert plan["installments"][1]["charged_on"] == "2026-11-16"
        assert plan["installments"][-1]["cutoff_date"] == "2027-10-15"

    def test_last_installment_absorbs_the_difference(self, client: TestClient) -> None:
        card = create_account(client, "TDC Oro", type="credit")

        plan = post_plan(client, card["id"], "1000", 3).json()

        assert [i["amount"] for i in plan["installments"]] == ["333.33", "333.33", "333.34"]

    def test_uses_the_full_credit_at_once(self, client: TestClient) -> None:
        card = create_account(client, "TDC Oro", type="credit")

        post_plan(client, card["id"], "12000", 12)

        assert balances(client)["TDC Oro"] == "-12000.00"
        account = client.get("/api/v1/accounts").json()[0]
        assert account["credit"]["available"] == "8000.00"

    def test_the_expense_has_zero_accounting_amount(self, client: TestClient) -> None:
        card = create_account(client, "TDC Oro", type="credit")
        plan = post_plan(client, card["id"], "12000", 12, description="Laptop").json()

        movements = client.get("/api/v1/movements").json()

        assert len(movements) == 1
        assert movements[0]["id"] == plan["movement_id"]
        assert movements[0]["real_amount"] == "-12000.00"
        assert movements[0]["accounting_amount"] == "0.00"
        assert movements[0]["description"] == "Laptop"

    def test_defaults_to_today(self, client: TestClient) -> None:
        card = create_account(client, "TDC Oro", type="credit")

        plan = post_plan(client, card["id"], "1000", 3).json()

        assert plan["purchased_on"] == "2026-11-20"
        assert plan["installments"][0]["cutoff_date"] == "2026-12-15"

    def test_only_credit_cards(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA")

        response = post_plan(client, bbva["id"], "1000", 3)

        assert response.status_code == 422
        assert client.get("/api/v1/movements").json() == []

    @pytest.mark.parametrize("months", [2, 49])
    def test_months_between_3_and_48(self, client: TestClient, months: int) -> None:
        card = create_account(client, "TDC Oro", type="credit")

        assert post_plan(client, card["id"], "1000", months).status_code == 422

    def test_unknown_account(self, client: TestClient) -> None:
        response = post_plan(client, "00000000-0000-0000-0000-000000000099", "1000", 3)

        assert response.status_code == 404


class TestStatement:
    def test_cycle_with_charges_installments_refunds_and_payments(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA", initial_balance="20000")
        card = create_account(client, "TDC Oro", type="credit")
        pay_card(client, bbva["id"], card["id"], "300", "2026-11-01")  # pays the previous cycle
        post_movement(client, card["id"], "expense", "634", "2026-11-05")
        post_plan(client, card["id"], "12000", 12, purchased_on="2026-11-10", description="Laptop")
        post_movement(client, card["id"], "income", "100", "2026-11-12")  # refund
        post_movement(client, card["id"], "expense", "200", "2026-11-16")  # next cycle
        pay_card(client, bbva["id"], card["id"], "500", "2026-11-20")

        result = statement(client, card["id"], "2026-11-15")

        assert result["start"] == "2026-10-16"
        assert result["cutoff"] == "2026-11-15"
        assert result["payment_due"] == "2026-12-05"
        assert result["regular_charges"] == "534.00"
        assert result["installments_due"] == "1000.00"
        assert result["installments"] == [
            {
                "plan_id": result["installments"][0]["plan_id"],
                "description": "Laptop",
                "number": 1,
                "months": 12,
                "amount": "1000.00",
            }
        ]
        assert result["payments_after_cutoff"] == "500.00"
        # 534 + 1,000 - 500
        assert result["payment_for_no_interest"] == "1034.00"

    def test_next_cycle_has_the_second_installment(self, client: TestClient) -> None:
        card = create_account(client, "TDC Oro", type="credit")
        post_plan(client, card["id"], "12000", 12, purchased_on="2026-11-10")
        post_movement(client, card["id"], "expense", "200", "2026-11-16")

        result = statement(client, card["id"], "2026-12-01")

        assert result["cutoff"] == "2026-12-15"
        assert result["regular_charges"] == "200.00"
        assert result["installments"][0]["number"] == 2
        assert result["payment_for_no_interest"] == "1200.00"

    def test_defaults_to_the_last_closed_cycle(self, client: TestClient) -> None:
        card = create_account(client, "TDC Oro", type="credit")

        # Today is November 20: the last cutoff was November 15
        assert statement(client, card["id"])["cutoff"] == "2026-11-15"

    def test_paying_more_than_due_leaves_nothing_to_pay(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA", initial_balance="5000")
        card = create_account(client, "TDC Oro", type="credit")
        post_movement(client, card["id"], "expense", "634", "2026-11-05")
        pay_card(client, bbva["id"], card["id"], "1000", "2026-11-18")

        assert statement(client, card["id"], "2026-11-15")["payment_for_no_interest"] == "0.00"

    def test_only_credit_cards_have_statements(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA")

        response = client.get(f"/api/v1/cards/{bbva['id']}/statement")

        assert response.status_code == 404

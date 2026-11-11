from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import create_account
from tests.api.test_savings import figures, post


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    modules = ("accounts", "installments", "statements", "movements", "summary", "savings")
    for module in modules:
        monkeypatch.setattr(f"app.services.{module}.today", lambda: date(2026, 11, 20))


def savings_mode(client: TestClient) -> None:
    response = client.patch("/api/v1/preferences", json={"mode": "savings"})
    assert response.status_code == 200, response.text


def preview(client: TestClient, account: dict[str, Any], amount: str, **fields: Any) -> Any:
    response = client.post(
        "/api/v1/movements/preview",
        json={"account_id": account["id"], "type": "expense", "amount": amount, **fields},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_savings_mode_suggests_rounding_and_warns_over_available(client: TestClient) -> None:
    create_account(client, "BBVA", initial_balance="500")
    card = create_account(client, "TDC Oro", type="credit")
    luz = post(client, "commitments", name="Luz", amount="200")
    savings_mode(client)
    # Real balance 500, available 300

    assert preview(client, card, "387.56") == {
        "suggested_accounting_amount": "390.00",
        "first_installment": None,
        "warning": {"level": "over_available", "excess": "90.00"},
    }
    # Paying the Luz commitment only takes 187.56 from "available"
    paying = preview(client, card, "387.56", commitment_id=luz["id"])
    assert (paying["suggested_accounting_amount"], paying["warning"]) == ("387.56", None)
    # Nothing is stored
    assert client.get("/api/v1/movements").json() == []


def test_simple_mode_only_warns_over_the_real_balance(client: TestClient) -> None:
    create_account(client, "BBVA", initial_balance="500")
    card = create_account(client, "TDC Oro", type="credit")
    post(client, "commitments", name="Luz", amount="200")

    # Over "available" (300), but simple mode doesn't show it
    assert preview(client, card, "400") == {
        "suggested_accounting_amount": "400.00",
        "first_installment": None,
        "warning": None,
    }
    over = preview(client, card, "600")
    assert over["warning"] == {"level": "over_real_balance", "excess": "100.00"}


def test_msi_preview_shows_the_rounded_first_installment(client: TestClient) -> None:
    create_account(client, "BBVA", initial_balance="500")
    card = create_account(client, "TDC Oro", type="credit")
    savings_mode(client)

    assert preview(client, card, "1000", months=3) == {
        "suggested_accounting_amount": None,
        "first_installment": {"amount": "333.33", "accounting_amount": "340.00"},
        "warning": {"level": "over_real_balance", "excess": "500.00"},
    }


def test_msi_installments_round_up_in_savings_mode(client: TestClient) -> None:
    create_account(client, "BBVA", initial_balance="5000")
    card = create_account(client, "TDC Oro", type="credit")
    savings_mode(client)

    plan = post(client, "installment-plans", account_id=card["id"], total="1000", months=3)

    assert [(i["amount"], i["accounting_amount"]) for i in plan["installments"]] == [
        ("333.33", "340.00"),
        ("333.33", "340.00"),
        ("333.34", "340.00"),
    ]
    # The first one is charged today: 340 from "available", 6.67 to the leftover
    result = figures(client)
    assert (
        result["card_debt"],
        result["available"],
        result["leftover"],
        result["installments_pending"],
    ) == ("1000.00", "4660.00", "6.67", "666.67")

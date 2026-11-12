"""A card purchase can never go over the card's available credit (docs/PLANEACION.md,
2026-11-11). Card payments and refunds aren't limited."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import DEFAULT_CREDIT, balances, create_account
from tests.api.test_movement_deletes import delete, post, restore


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    modules = ("accounts", "installments", "statements", "movements", "summary", "savings")
    for module in modules:
        monkeypatch.setattr(f"app.services.{module}.today", lambda: date(2026, 11, 20))


@pytest.fixture
def card(client: TestClient) -> dict[str, Any]:
    return create_account(
        client, "TDC Oro", type="credit", credit={**DEFAULT_CREDIT, "credit_limit": "1000"}
    )


def purchase(client: TestClient, card: dict[str, Any], amount: str) -> Any:
    return client.post(
        "/api/v1/movements", json={"account_id": card["id"], "type": "expense", "amount": amount}
    )


def test_purchase_over_the_available_credit_is_rejected(
    client: TestClient, card: dict[str, Any]
) -> None:
    assert purchase(client, card, "1000").status_code == 201

    response = purchase(client, card, "0.01")
    assert response.status_code == 422
    assert "by $0.01" in response.json()["detail"]
    assert balances(client)["TDC Oro"] == "-1000.00"


def test_msi_purchase_compares_its_total(client: TestClient, card: dict[str, Any]) -> None:
    response = client.post(
        "/api/v1/installment-plans",
        json={"account_id": card["id"], "total": "1000.01", "months": 3},
    )

    assert response.status_code == 422
    assert client.get("/api/v1/movements").json() == []


def test_editing_a_purchase_counts_its_current_amount_as_available(
    client: TestClient, card: dict[str, Any]
) -> None:
    first = purchase(client, card, "600").json()
    purchase(client, card, "300")
    edit_url = f"/api/v1/movements/{first['id']}"

    # 100 still available, plus the 600 already in the debt
    assert client.patch(edit_url, json={"amount": "700"}).status_code == 200
    rejected = client.patch(edit_url, json={"amount": "700.01"})
    assert rejected.status_code == 422
    assert balances(client)["TDC Oro"] == "-1000.00"


def test_restoring_over_the_limit_explains_the_manual_fix(
    client: TestClient, card: dict[str, Any]
) -> None:
    original = purchase(client, card, "600").json()
    assert delete(client, original["id"]).status_code == 204
    purchase(client, card, "500")

    response = restore(client, original["id"])
    assert response.status_code == 409
    assert "delete the later purchases" in response.json()["detail"]
    assert balances(client)["TDC Oro"] == "-500.00"


def test_preview_gives_the_excess_instead_of_a_warning(
    client: TestClient, card: dict[str, Any]
) -> None:
    # No money in debit: without the limit it would be a level 2 warning
    create_account(client, "BBVA")
    post(client, "movements", account_id=card["id"], type="expense", amount="900")

    def preview(**fields: Any) -> Any:
        response = client.post(
            "/api/v1/movements/preview",
            json={"account_id": card["id"], "type": "expense", **fields},
        )
        assert response.status_code == 200, response.text
        return response.json()

    over = preview(amount="150")
    assert (over["credit_limit_excess"], over["warning"]) == ("50.00", None)
    msi = preview(amount="130", months=3)
    assert (msi["credit_limit_excess"], msi["warning"]) == ("30.00", None)
    within = preview(amount="100")
    assert within["credit_limit_excess"] is None
    assert within["warning"]["level"] == "over_real_balance"

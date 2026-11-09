from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import create_account

SERVICES_WITH_TODAY = ("accounts", "installments", "statements", "movements", "summary")


def set_today(monkeypatch: pytest.MonkeyPatch, day: date) -> None:
    for module in SERVICES_WITH_TODAY:
        monkeypatch.setattr(f"app.services.{module}.today", lambda: day)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    set_today(monkeypatch, date(2026, 11, 20))


def post(client: TestClient, path: str, **fields: Any) -> dict[str, Any]:
    response = client.post(f"/api/v1/{path}", json=fields)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def summary(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/v1/summary")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def expense(client: TestClient, account_id: str, amount: str, on: str) -> dict[str, Any]:
    return post(
        client, "movements", account_id=account_id, type="expense", amount=amount, occurred_on=on
    )


def laptop(client: TestClient, card_id: str) -> dict[str, Any]:
    """12,000 at 12 MSI bought on Nov 10 (cutoff on the 15th)."""
    return post(
        client,
        "installment-plans",
        account_id=card_id,
        total="12000",
        months=12,
        purchased_on="2026-11-10",
    )


def test_no_accounts(client: TestClient) -> None:
    assert summary(client) == {
        "on": "2026-11-20",
        "real_balance": "0.00",
        "card_debt": "0.00",
        "installments_pending": "0.00",
        "cards": [],
    }


def test_real_balance_adds_debit_and_cash(client: TestClient) -> None:
    # Savings accounts can't be created through the API yet; the domain tests leave them out
    create_account(client, "BBVA", initial_balance="14290.11")
    create_account(client, "Cartera", type="cash", initial_balance="500")

    result = summary(client)

    assert result["real_balance"] == "14790.11"
    assert result["card_debt"] == "0.00"


def test_card_with_msi_purchase(client: TestClient) -> None:
    card = create_account(client, "TDC Oro", type="credit")
    expense(client, card["id"], "634", "2026-11-05")
    laptop(client, card["id"])

    result = summary(client)

    # The debt includes the full MSI total
    assert result["card_debt"] == "12634.00"
    # Installment 1 was charged on Nov 10 and installment 2 on Nov 16 (start of its cycle)
    assert result["installments_pending"] == "10000.00"
    assert result["cards"] == [
        {
            "account_id": card["id"],
            "name": "TDC Oro",
            "debt": "12634.00",
            "installments_pending": "10000.00",
            "next_payment": {
                "cutoff": "2026-11-15",
                "payment_due": "2026-12-05",
                # 634 + the first installment
                "amount": "1634.00",
                "is_closed": True,
            },
        }
    ]


def test_deleted_msi_purchase_is_left_out(client: TestClient) -> None:
    card = create_account(client, "TDC Oro", type="credit")
    plan = laptop(client, card["id"])

    assert client.delete(f"/api/v1/movements/{plan['movement_id']}").status_code == 204

    result = summary(client)
    assert result["card_debt"] == "0.00"
    assert result["installments_pending"] == "0.00"
    assert result["cards"][0]["next_payment"]["amount"] == "0.00"


def test_after_the_due_date_shows_the_open_cycle(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = create_account(client, "TDC Oro", type="credit")
    laptop(client, card["id"])
    expense(client, card["id"], "200", "2026-11-25")
    set_today(monkeypatch, date(2026, 12, 10))

    next_payment = summary(client)["cards"][0]["next_payment"]

    assert next_payment == {
        "cutoff": "2026-12-15",
        "payment_due": "2027-01-05",
        # Charged so far in the open cycle: 200 + the second installment
        "amount": "1200.00",
        "is_closed": False,
    }


def test_payments_after_the_cutoff_lower_the_next_payment(client: TestClient) -> None:
    bbva = create_account(client, "BBVA", initial_balance="5000")
    card = create_account(client, "TDC Oro", type="credit")
    expense(client, card["id"], "634", "2026-11-05")
    post(
        client,
        "transfers",
        source_account_id=bbva["id"],
        destination_account_id=card["id"],
        amount="300",
        occurred_on="2026-11-18",
    )

    result = summary(client)

    assert result["real_balance"] == "4700.00"
    assert result["card_debt"] == "334.00"
    assert result["cards"][0]["next_payment"]["amount"] == "334.00"


def test_totals_add_up_every_card(client: TestClient) -> None:
    oro = create_account(client, "TDC Oro", type="credit")
    nu = create_account(client, "TDC Nu", type="credit", initial_balance="100")
    expense(client, oro["id"], "634", "2026-11-05")
    laptop(client, nu["id"])

    result = summary(client)

    # Oro owes 634; Nu owes 12,000 minus its 100 in your favor
    assert [card["debt"] for card in result["cards"]] == ["634.00", "11900.00"]
    assert result["card_debt"] == "12534.00"
    assert result["installments_pending"] == "10000.00"

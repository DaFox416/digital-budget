from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import DEFAULT_CREDIT, create_account


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.accounts.today", lambda: date(2026, 11, 10))


def post_account(client: TestClient, **fields: Any) -> Any:
    return client.post("/api/v1/accounts", json={"name": "TDC Oro", "type": "credit", **fields})


def test_credit_account_returns_its_config_and_cycles(client: TestClient) -> None:
    card = create_account(client, "TDC Oro", type="credit", initial_balance="-634")

    assert card["credit"] == {
        "credit_limit": "20000.00",
        "cutoff_day": 15,
        "payment_due_rule": "fixed_day",
        "payment_due_value": 5,
        "available": "19366.00",
        "current_cycle": {
            "start": "2026-10-16",
            "cutoff": "2026-11-15",
            "payment_due": "2026-12-05",
        },
        "last_statement": {
            "start": "2026-09-16",
            "cutoff": "2026-10-15",
            "payment_due": "2026-11-05",
        },
    }


def test_credit_account_requires_its_config(client: TestClient) -> None:
    response = post_account(client)

    assert response.status_code == 422
    assert "credit config" in response.text


def test_debit_account_rejects_a_credit_config(client: TestClient) -> None:
    response = client.post(
        "/api/v1/accounts", json={"name": "BBVA", "type": "debit", "credit": DEFAULT_CREDIT}
    )

    assert response.status_code == 422

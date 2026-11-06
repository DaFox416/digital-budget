from typing import Any

from fastapi.testclient import TestClient

# Cutoff on the 15th, pay on the 5th: the example used throughout docs/PLANEACION.md
DEFAULT_CREDIT = {
    "credit_limit": "20000",
    "cutoff_day": 15,
    "payment_due_rule": "fixed_day",
    "payment_due_value": 5,
}


def create_account(
    client: TestClient,
    name: str,
    type: str = "debit",
    initial_balance: str = "0.00",
    credit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "type": type, "initial_balance": initial_balance}
    if type == "credit":
        payload["credit"] = credit or DEFAULT_CREDIT
    response = client.post("/api/v1/accounts", json=payload)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def balances(client: TestClient) -> dict[str, str]:
    """Account name -> balance, as returned by the API."""
    return {
        account["name"]: account["balance"] for account in client.get("/api/v1/accounts").json()
    }

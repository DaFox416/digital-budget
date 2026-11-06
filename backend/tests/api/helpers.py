from typing import Any

from fastapi.testclient import TestClient


def create_account(
    client: TestClient, name: str, type: str = "debit", initial_balance: str = "0.00"
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/accounts", json={"name": name, "type": type, "initial_balance": initial_balance}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def balances(client: TestClient) -> dict[str, str]:
    """Account name -> balance, as returned by the API."""
    return {
        account["name"]: account["balance"] for account in client.get("/api/v1/accounts").json()
    }

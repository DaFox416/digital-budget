from fastapi.testclient import TestClient

from tests.api.helpers import create_account


def test_create_account_returns_it_with_its_balance(client: TestClient) -> None:
    account = create_account(client, "BBVA", initial_balance="5000")

    assert account["name"] == "BBVA"
    assert account["type"] == "debit"
    # Money is serialized as a string with 2 decimals, never as a float
    assert account["initial_balance"] == "5000.00"
    assert account["balance"] == "5000.00"


def test_list_accounts_in_creation_order(client: TestClient) -> None:
    create_account(client, "BBVA")
    create_account(client, "Efectivo", type="cash")
    create_account(client, "TDC Oro", type="credit")

    accounts = client.get("/api/v1/accounts").json()

    assert [account["name"] for account in accounts] == ["BBVA", "Efectivo", "TDC Oro"]
    assert [account["position"] for account in accounts] == [0, 1, 2]


def test_account_names_are_unique_per_user(client: TestClient) -> None:
    create_account(client, "BBVA")

    response = client.post("/api/v1/accounts", json={"name": "BBVA", "type": "cash"})

    assert response.status_code == 409


def test_lists_default_categories(client: TestClient) -> None:
    names = [category["name"] for category in client.get("/api/v1/categories").json()]

    assert "Comida" in names
    assert "Nómina" in names
    assert len(names) == 11

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.helpers import create_account


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    modules = ("accounts", "installments", "statements", "movements", "summary", "savings")
    for module in modules:
        monkeypatch.setattr(f"app.services.{module}.today", lambda: date(2026, 11, 20))


def post(client: TestClient, path: str, **fields: Any) -> dict[str, Any]:
    response = client.post(f"/api/v1/{path}", json=fields)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def figures(client: TestClient) -> dict[str, str]:
    """The seven figures, checking the invariant on every call."""
    response = client.get("/api/v1/summary")
    assert response.status_code == 200, response.text
    body = response.json()
    real = Decimal(body["real_balance"])
    parts = sum(
        Decimal(body[name])
        for name in ("available", "set_aside", "card_debt", "savings_goals", "leftover")
    )
    assert real == parts - Decimal(body["installments_pending"]), body
    return {name: value for name, value in body.items() if name not in ("on", "cards")}


def test_example_from_the_plan(client: TestClient) -> None:
    """The savings mode table of docs/PLANEACION.md through the API, then a 12 MSI laptop."""
    bbva = create_account(client, "BBVA", initial_balance="5000")
    card = create_account(client, "TDC Oro", type="credit")
    luz = post(client, "commitments", name="Luz", amount="500")

    def expense(account: dict[str, Any], amount: str, accounting: str, **extra: Any) -> None:
        post(
            client,
            "movements",
            account_id=account["id"],
            type="expense",
            amount=amount,
            accounting_amount=accounting,
            **extra,
        )

    expense(bbva, "387.56", "400")  # Cine
    expense(card, "634", "640")  # Despensa
    post(
        client,
        "movements",
        account_id=bbva["id"],
        type="income",
        amount="10164.67",
        accounting_amount="10000",
    )
    # Luz: without an accounting amount, it consumes the 500 set aside
    post(
        client,
        "movements",
        account_id=bbva["id"],
        type="expense",
        amount="487",
        commitment_id=luz["id"],
    )
    post(
        client,
        "transfers",
        source_account_id=bbva["id"],
        destination_account_id=card["id"],
        amount="634",
    )

    assert figures(client) == {
        "real_balance": "13656.11",
        "available": "13460.00",
        "set_aside": "0.00",
        "card_debt": "0.00",
        "savings_goals": "0.00",
        "leftover": "196.11",
        "leftover_releasable": "190.00",
        "installments_pending": "0.00",
    }

    # Bought on Nov 10: installments 1 and 2 are already charged on Nov 20
    post(
        client,
        "installment-plans",
        account_id=card["id"],
        total="12000",
        months=12,
        purchased_on="2026-11-10",
    )
    result = figures(client)
    assert (result["card_debt"], result["available"], result["installments_pending"]) == (
        "12000.00",
        "11460.00",
        "10000.00",
    )


class TestCommitments:
    def test_create_list_and_edit(self, client: TestClient) -> None:
        post(client, "commitments", name="Internet", amount="600")
        luz = post(client, "commitments", name="Luz", amount="500", expected_on="2026-11-25")

        response = client.patch(f"/api/v1/commitments/{luz['id']}", json={"amount": "520"})

        assert response.status_code == 200
        listed = client.get("/api/v1/commitments").json()
        # Pending ones by expected date; no date goes last
        assert [(item["name"], item["amount"]) for item in listed] == [
            ("Luz", "520.00"),
            ("Internet", "600.00"),
        ]
        assert figures(client)["set_aside"] == "1120.00"

    def test_deleting_the_payment_sets_it_aside_again(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA", initial_balance="5000")
        luz = post(client, "commitments", name="Luz", amount="500")
        payment = post(
            client,
            "movements",
            account_id=bbva["id"],
            type="expense",
            amount="487",
            commitment_id=luz["id"],
        )

        assert payment["accounting_amount"] == "-500.00"
        assert client.get("/api/v1/commitments").json()[0]["paid_by_movement_id"] == payment["id"]
        assert figures(client)["leftover"] == "13.00"
        # A paid commitment can't be edited or paid twice
        assert (
            client.patch(f"/api/v1/commitments/{luz['id']}", json={"amount": "1"}).status_code
            == 409
        )
        second = client.post(
            "/api/v1/movements",
            json={
                "account_id": bbva["id"],
                "type": "expense",
                "amount": "10",
                "commitment_id": luz["id"],
            },
        )
        assert second.status_code == 409

        assert client.delete(f"/api/v1/movements/{payment['id']}").status_code == 204

        assert client.get("/api/v1/commitments").json()[0]["paid_by_movement_id"] is None
        result = figures(client)
        assert (result["available"], result["set_aside"], result["leftover"]) == (
            "4500.00",
            "500.00",
            "0.00",
        )

    def test_delete_and_restore_a_pending_one(self, client: TestClient) -> None:
        bbva = create_account(client, "BBVA", initial_balance="5000")
        luz = post(client, "commitments", name="Luz", amount="500")
        payment = post(
            client,
            "movements",
            account_id=bbva["id"],
            type="expense",
            amount="487",
            commitment_id=luz["id"],
        )
        # Paid: delete the payment first
        assert client.delete(f"/api/v1/commitments/{luz['id']}").status_code == 409
        client.delete(f"/api/v1/movements/{payment['id']}")

        assert client.delete(f"/api/v1/commitments/{luz['id']}").status_code == 204

        assert client.get("/api/v1/commitments").json() == []
        assert figures(client)["available"] == "5000.00"
        # Its payment can't come back while it's deleted
        assert client.post(f"/api/v1/movements/{payment['id']}/restore").status_code == 409

        assert client.post(f"/api/v1/commitments/{luz['id']}/restore").status_code == 200
        assert figures(client)["set_aside"] == "500.00"

    def test_moving_a_payment_to_another_commitment_and_unlinking_it(
        self, client: TestClient
    ) -> None:
        bbva = create_account(client, "BBVA", initial_balance="5000")
        luz = post(client, "commitments", name="Luz", amount="500")
        agua = post(client, "commitments", name="Agua", amount="300")
        payment = post(
            client,
            "movements",
            account_id=bbva["id"],
            type="expense",
            amount="487",
            commitment_id=agua["id"],
        )

        def relink(commitment_id: str | None) -> dict[str, Any]:
            response = client.patch(
                f"/api/v1/movements/{payment['id']}", json={"commitment_id": commitment_id}
            )
            assert response.status_code == 200, response.text
            body: dict[str, Any] = response.json()
            return body

        # It was really the electricity: max(487, 500)
        assert relink(luz["id"])["accounting_amount"] == "-500.00"
        result = figures(client)
        assert (result["set_aside"], result["leftover"]) == ("300.00", "13.00")

        # Not a commitment payment after all: accounting equals real again
        assert relink(None)["accounting_amount"] == "-487.00"
        result = figures(client)
        assert (result["set_aside"], result["leftover"]) == ("800.00", "0.00")


def test_undoing_a_leftover_release(client: TestClient) -> None:
    bbva = create_account(client, "BBVA", initial_balance="5000")
    post(
        client,
        "movements",
        account_id=bbva["id"],
        type="expense",
        amount="387.56",
        accounting_amount="400",
    )
    release = post(client, "leftover-releases", amount="10")

    assert client.delete(f"/api/v1/leftover-releases/{release['id']}").status_code == 204

    result = figures(client)
    assert (result["available"], result["leftover"]) == ("4600.00", "12.44")
    assert client.delete(f"/api/v1/leftover-releases/{release['id']}").status_code == 404


def test_preferences_default_and_update(client: TestClient) -> None:
    assert client.get("/api/v1/preferences").json() == {"mode": "simple", "rounding_multiple": 10}

    response = client.patch("/api/v1/preferences", json={"mode": "savings"})

    assert response.json() == {"mode": "savings", "rounding_multiple": 10}
    assert client.patch("/api/v1/preferences", json={"rounding_multiple": 0}).status_code == 422


def test_releasing_leftover_respects_the_rounding(client: TestClient) -> None:
    bbva = create_account(client, "BBVA", initial_balance="5000")
    post(
        client,
        "movements",
        account_id=bbva["id"],
        type="expense",
        amount="387.56",
        accounting_amount="400",
    )
    assert figures(client)["leftover_releasable"] == "10.00"  # Leftover 12.44

    rejected = client.post("/api/v1/leftover-releases", json={"amount": "12.44"})
    assert rejected.status_code == 422
    assert "multiple of 10" in rejected.json()["detail"]

    post(client, "leftover-releases", amount="10")

    result = figures(client)
    assert (result["available"], result["leftover"]) == ("4610.00", "2.44")

"""
Tests for restocking order API endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def reset_restocking_orders():
    """Restocking orders are stored in a module-level list, so clear it between tests."""
    main.restocking_orders.clear()
    yield
    main.restocking_orders.clear()


class TestDemandRestockingFields:
    """Test suite for the pricing fields restocking relies on."""

    def test_demand_forecasts_have_cost_and_lead_time(self, client):
        """Test that every demand forecast has a unit cost and lead time."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        for forecast in response.json():
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["lead_time_days"] > 0


class TestRestockingOrderEndpoints:
    """Test suite for restocking order endpoints."""

    def test_get_restocking_orders_empty(self, client):
        """Test that no restocking orders exist initially."""
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restocking_order(self, client):
        """Test submitting a restocking order."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"item_sku": "WDG-001", "quantity": 10}],
            "budget": 1000
        })
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["budget"] == 1000
        assert len(order["items"]) == 1

        line = order["items"][0]
        assert line["item_sku"] == "WDG-001"
        assert line["item_name"] == "Industrial Widget Type A"
        assert line["quantity"] == 10
        assert abs(line["line_total"] - 125.0) < 0.01

    def test_restocking_order_total_calculation(self, client):
        """Test that the order total is the sum of server-priced line totals."""
        demand = {f["item_sku"]: f for f in client.get("/api/demand").json()}

        response = client.post("/api/restocking-orders", json={
            "items": [
                {"item_sku": "WDG-001", "quantity": 4},
                {"item_sku": "GSK-203", "quantity": 20}
            ]
        })
        assert response.status_code == 201

        order = response.json()
        expected = 4 * demand["WDG-001"]["unit_cost"] + 20 * demand["GSK-203"]["unit_cost"]
        assert abs(order["total_cost"] - expected) < 0.01

        for line in order["items"]:
            assert line["unit_cost"] == demand[line["item_sku"]]["unit_cost"]

    def test_restocking_order_lead_time_is_max_of_items(self, client):
        """Test that order lead time is the slowest item's lead time."""
        demand = {f["item_sku"]: f for f in client.get("/api/demand").json()}

        response = client.post("/api/restocking-orders", json={
            "items": [
                {"item_sku": "FLT-405", "quantity": 1},
                {"item_sku": "MTR-304", "quantity": 1}
            ]
        })
        order = response.json()

        expected = max(demand["FLT-405"]["lead_time_days"], demand["MTR-304"]["lead_time_days"])
        assert order["lead_time_days"] == expected

    def test_restocking_order_dates_format(self, client):
        """Test that expected delivery is submission date plus lead time."""
        from datetime import datetime, timedelta

        order = client.post("/api/restocking-orders", json={
            "items": [{"item_sku": "VLV-506", "quantity": 2}]
        }).json()

        submitted = datetime.fromisoformat(order["submitted_date"])
        expected_delivery = datetime.fromisoformat(order["expected_delivery"])
        assert "T" in order["submitted_date"]
        assert expected_delivery - submitted == timedelta(days=order["lead_time_days"])

    def test_get_restocking_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        first = client.post("/api/restocking-orders", json={
            "items": [{"item_sku": "WDG-001", "quantity": 1}]
        }).json()
        second = client.post("/api/restocking-orders", json={
            "items": [{"item_sku": "BRG-102", "quantity": 1}]
        }).json()

        response = client.get("/api/restocking-orders")
        assert response.status_code == 200

        ids = [o["id"] for o in response.json()]
        assert ids == [second["id"], first["id"]]
        assert first["order_number"] != second["order_number"]

    def test_restocking_order_over_budget(self, client):
        """Test that an order exceeding the budget is rejected."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"item_sku": "MTR-304", "quantity": 10}],
            "budget": 100
        })
        assert response.status_code == 400
        assert "exceeds budget" in response.json()["detail"]
        assert client.get("/api/restocking-orders").json() == []

    def test_restocking_order_unknown_sku(self, client):
        """Test that an unknown SKU is rejected."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"item_sku": "NOPE-999", "quantity": 1}]
        })
        assert response.status_code == 400
        assert "NOPE-999" in response.json()["detail"]

    def test_restocking_order_duplicate_sku(self, client):
        """Test that the same SKU twice in one order is rejected."""
        response = client.post("/api/restocking-orders", json={
            "items": [
                {"item_sku": "WDG-001", "quantity": 1},
                {"item_sku": "WDG-001", "quantity": 2}
            ]
        })
        assert response.status_code == 400
        assert "duplicate" in response.json()["detail"].lower()

    @pytest.mark.parametrize("payload", [
        {"items": []},
        {"items": [{"item_sku": "WDG-001", "quantity": 0}]},
        {"items": [{"item_sku": "WDG-001", "quantity": -5}]},
        {"items": [{"item_sku": "WDG-001", "quantity": 1}], "budget": -1},
        {}
    ])
    def test_restocking_order_invalid_payload(self, client, payload):
        """Test that malformed requests fail validation."""
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 422

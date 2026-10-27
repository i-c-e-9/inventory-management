"""
Tests for reports API endpoints.
"""
import pytest


FILTER_CASES = [
    "warehouse=Tokyo",
    "category=Sensors",
    "status=Delivered",
    "month=2025-03",
    "month=Q2-2025",
    "warehouse=London&category=Circuit Boards&status=Shipped",
]


class TestReportsEndpoints:
    """Test suite for quarterly and monthly report endpoints."""

    def test_get_quarterly_reports(self, client):
        """Test getting quarterly reports without filters."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        for field in ["quarter", "total_orders", "total_revenue", "delivered_orders",
                      "avg_order_value", "fulfillment_rate"]:
            assert field in first

    def test_get_monthly_trends(self, client):
        """Test getting monthly trends without filters."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        for field in ["month", "order_count", "revenue", "delivered_count"]:
            assert field in first

    def test_reports_sorted(self, client):
        """Test that both reports are sorted chronologically."""
        quarters = [q["quarter"] for q in client.get("/api/reports/quarterly").json()]
        months = [m["month"] for m in client.get("/api/reports/monthly-trends").json()]
        assert quarters == sorted(quarters)
        assert months == sorted(months)

    def test_report_revenue_is_rounded(self, client):
        """Test that revenue totals have no floating point artifacts."""
        for q in client.get("/api/reports/quarterly").json():
            assert round(q["total_revenue"], 2) == q["total_revenue"]
        for m in client.get("/api/reports/monthly-trends").json():
            assert round(m["revenue"], 2) == m["revenue"]

    @pytest.mark.parametrize("query", FILTER_CASES)
    def test_monthly_trends_match_filtered_orders(self, client, query):
        """Test that monthly trends aggregate exactly the orders the same filters return."""
        orders = client.get(f"/api/orders?{query}").json()
        trends = client.get(f"/api/reports/monthly-trends?{query}").json()

        assert sum(m["order_count"] for m in trends) == len(orders)
        assert abs(sum(m["revenue"] for m in trends) - sum(o["total_value"] for o in orders)) < 0.05
        assert sum(m["delivered_count"] for m in trends) == sum(
            1 for o in orders if o["status"] == "Delivered"
        )

    @pytest.mark.parametrize("query", FILTER_CASES)
    def test_quarterly_reports_match_filtered_orders(self, client, query):
        """Test that quarterly reports aggregate exactly the orders the same filters return."""
        orders = client.get(f"/api/orders?{query}").json()
        quarters = client.get(f"/api/reports/quarterly?{query}").json()

        assert sum(q["total_orders"] for q in quarters) == len(orders)
        assert abs(sum(q["total_revenue"] for q in quarters) - sum(o["total_value"] for o in orders)) < 0.05

    def test_month_filter_limits_trends_to_that_month(self, client):
        """Test that a month filter returns only that month."""
        data = client.get("/api/reports/monthly-trends?month=2025-03").json()
        assert [m["month"] for m in data] == ["2025-03"]

    def test_quarter_filter_limits_quarterly_report(self, client):
        """Test that a quarter filter returns only that quarter."""
        data = client.get("/api/reports/quarterly?month=Q2-2025").json()
        assert [q["quarter"] for q in data] == ["Q2-2025"]

    def test_all_filter_values_return_unfiltered_data(self, client):
        """Test that 'all' filter values behave like no filters."""
        query = "warehouse=all&category=all&status=all&month=all"
        assert client.get(f"/api/reports/monthly-trends?{query}").json() == \
            client.get("/api/reports/monthly-trends").json()
        assert client.get(f"/api/reports/quarterly?{query}").json() == \
            client.get("/api/reports/quarterly").json()

    def test_filter_with_no_matches_returns_empty_list(self, client):
        """Test that filters matching no orders return empty lists, not errors."""
        for path in ["/api/reports/quarterly", "/api/reports/monthly-trends"]:
            response = client.get(f"{path}?warehouse=Nowhere")
            assert response.status_code == 200
            assert response.json() == []

    def test_quarterly_derived_values_calculation(self, client):
        """Test average order value and fulfillment rate calculations."""
        for q in client.get("/api/reports/quarterly").json():
            assert abs(q["avg_order_value"] - q["total_revenue"] / q["total_orders"]) < 0.01
            expected_rate = q["delivered_orders"] / q["total_orders"] * 100
            assert abs(q["fulfillment_rate"] - expected_rate) < 0.1
            assert 0 <= q["fulfillment_rate"] <= 100

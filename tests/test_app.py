"""HTTP smoke tests and API integration tests for the dashboard."""
import app as app_module


def test_health_endpoint_returns_dashboard_stage():
    client = app_module.app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "project": "Blockchain Money Tracer",
        "stage": "dashboard",
    }


def test_homepage_renders_interactive_dashboard():
    client = app_module.app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Blockchain Money Tracer" in html
    assert "Start Trace" in html
    assert "dashboard.js" in html
    assert "Transaction ledger" in html


def test_dashboard_javascript_asset_is_served_locally():
    client = app_module.app.test_client()

    response = client.get("/static/js/dashboard.js")

    assert response.status_code == 200
    assert "api/trace" in response.get_data(as_text=True)


def test_overview_returns_fixed_local_scenario_metadata():
    client = app_module.app.test_client()

    response = client.get("/api/overview")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["initial_amount"] == 100
    assert payload["asset"] == "USDT"
    assert payload["transaction_count"] == 15
    assert payload["wallet_count"] == 11
    assert payload["simulation_only"] is True


def test_trace_api_returns_graph_paths_risk_and_conservation():
    client = app_module.app.test_client()

    response = client.post("/api/trace")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload["graph"]["nodes"]) == 11
    assert len(payload["graph"]["edges"]) == 15
    assert len(payload["trace"]["paths"]) == 7
    assert payload["summary"]["source_amount"] == 100.0
    assert payload["summary"]["tracked_terminal_amount"] == 100.0
    assert payload["summary"]["conservation_passed"] is True
    assert payload["summary"]["terminal_balances"] == {
        "EXCHANGE-A": 50.0,
        "SERVICE-X": 20.0,
        "EXCHANGE-B": 30.0,
    }
    service_x = next(item for item in payload["risk_scores"] if item["wallet_id"] == "SERVICE-X")
    assert service_x["score"] == 70
    assert "not probabilities" in payload["disclaimer"]

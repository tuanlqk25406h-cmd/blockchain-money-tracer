"""Tests for source-to-terminal trace output."""
from decimal import Decimal

from tracer.data_loader import load_demo_data
from tracer.tracing import trace_from_source


def test_trace_returns_reachable_wallets_and_terminal_paths():
    scenario, wallets = load_demo_data()

    result = trace_from_source(scenario, wallets)

    assert result["source_wallet"] == "WALLET-A"
    assert result["source_amount"] == 100.0
    assert result["transaction_count"] == 15
    assert result["reachable_wallet_count"] == 11
    assert result["money_conservation"]["passed"] is True
    assert result["money_conservation"]["difference"] == 0.0
    assert len(result["paths"]) == 7
    assert sum(Decimal(str(path["amount"])) for path in result["paths"]) == Decimal("100")


def test_every_reported_path_starts_at_source_and_ends_at_terminal():
    scenario, wallets = load_demo_data()
    wallet_by_id = {wallet["id"]: wallet for wallet in wallets}

    result = trace_from_source(scenario, wallets)

    for path in result["paths"]:
        assert path["wallet_path"][0] == scenario["source_wallet"]
        assert path["wallet_path"][-1] == path["terminal_wallet"]
        assert wallet_by_id[path["terminal_wallet"]]["is_terminal"] is True
        assert len(path["transaction_ids"]) == len(path["wallet_path"]) - 1

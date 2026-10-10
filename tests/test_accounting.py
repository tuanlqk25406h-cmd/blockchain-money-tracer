"""Tests for conservation rules and FIFO flow allocation."""
from copy import deepcopy
from decimal import Decimal

import pytest

from tracer.accounting import (
    ScenarioValidationError,
    allocate_flow_lots,
    validate_scenario,
)
from tracer.data_loader import load_demo_data


def test_scenario_conserves_100_usdt_at_all_intermediate_wallets():
    scenario, wallets = load_demo_data()

    assert validate_scenario(scenario, wallets) == []


def test_fifo_allocation_preserves_terminal_total_and_expected_sinks():
    scenario, wallets = load_demo_data()

    result = allocate_flow_lots(scenario, wallets)

    assert result["conserved"] is True
    assert result["initial_amount"] == 100.0
    assert result["tracked_terminal_amount"] == 100.0
    assert result["terminal_balances"] == {
        "EXCHANGE-A": 50.0,
        "SERVICE-X": 20.0,
        "EXCHANGE-B": 30.0,
    }
    assert sum(Decimal(str(path["amount"])) for path in result["terminal_paths"]) == Decimal("100")


def test_every_transaction_amount_is_fully_allocated_once():
    scenario, wallets = load_demo_data()

    result = allocate_flow_lots(scenario, wallets)
    allocated_by_transaction = {}

    for allocation in result["transaction_allocations"]:
        tx_id = allocation["transaction_id"]
        allocated_by_transaction[tx_id] = (
            allocated_by_transaction.get(tx_id, Decimal("0"))
            + Decimal(str(allocation["amount"]))
        )

    assert set(allocated_by_transaction) == {
        transaction["transaction_id"] for transaction in scenario["transactions"]
    }
    for transaction in scenario["transactions"]:
        assert allocated_by_transaction[transaction["transaction_id"]] == Decimal(
            str(transaction["amount"])
        )


def test_fifo_makes_h_aggregation_attribution_deterministic():
    scenario, wallets = load_demo_data()

    result = allocate_flow_lots(scenario, wallets)
    exchange_a_paths = [
        path for path in result["terminal_paths"]
        if path["terminal_wallet"] == "EXCHANGE-A"
    ]
    service_x_paths = [
        path for path in result["terminal_paths"]
        if path["terminal_wallet"] == "SERVICE-X"
    ]

    assert any(path["wallet_path"] == ["WALLET-A", "WALLET-B", "WALLET-E", "WALLET-H", "EXCHANGE-A"]
               and path["amount"] == 25.0 for path in exchange_a_paths)
    assert any(path["wallet_path"] == ["WALLET-A", "WALLET-C", "WALLET-F", "WALLET-H", "SERVICE-X"]
               and path["amount"] == 5.0 for path in service_x_paths)
    assert "classroom assumption" in result["allocation_policy"]


def test_unbalanced_transaction_is_rejected():
    scenario, wallets = load_demo_data()
    bad_scenario = deepcopy(scenario)
    bad_scenario["transactions"][2]["amount"] = 34

    errors = validate_scenario(bad_scenario, wallets)

    assert any("WALLET-B" in error and "conserve flow" in error for error in errors)
    with pytest.raises(ScenarioValidationError):
        allocate_flow_lots(bad_scenario, wallets)


def test_unknown_wallet_is_rejected():
    scenario, wallets = load_demo_data()
    bad_scenario = deepcopy(scenario)
    bad_scenario["transactions"][0]["to_wallet"] = "UNKNOWN-WALLET"

    errors = validate_scenario(bad_scenario, wallets)

    assert any("unknown sender or receiver" in error for error in errors)


def test_wallet_cannot_spend_value_before_it_arrives():
    scenario, wallets = load_demo_data()
    bad_scenario = deepcopy(scenario)
    bad_scenario["transactions"][2]["timestamp"] = "2026-10-09T09:59:00+07:00"

    errors = validate_scenario(bad_scenario, wallets)

    assert any("TX-003" in error and "before they are available" in error for error in errors)
    with pytest.raises(ScenarioValidationError):
        allocate_flow_lots(bad_scenario, wallets)

"""Tests for local synthetic scenario loading and validation."""
from tracer.accounting import validate_scenario
from tracer.data_loader import load_demo_data


def test_demo_data_loads_and_validates():
    scenario, wallets = load_demo_data()

    assert scenario["source_wallet"] == "WALLET-A"
    assert scenario["initial_amount"] == 100
    assert scenario["asset"] == "USDT"
    assert len(scenario["transactions"]) == 15
    assert len(wallets) == 11
    assert validate_scenario(scenario, wallets) == []

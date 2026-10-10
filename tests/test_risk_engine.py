"""Tests for explainable rule-based risk scoring."""
from tracer.data_loader import load_demo_data
from tracer.risk_engine import calculate_risk_scores, risk_level


def test_service_x_gets_high_demo_score_for_explicit_reasons():
    scenario, wallets = load_demo_data()

    scores = calculate_risk_scores(scenario, wallets)
    service_x = next(result for result in scores if result["wallet_id"] == "SERVICE-X")

    assert service_x["score"] == 70
    assert service_x["level"] == "high"
    assert {signal["code"] for signal in service_x["signals"]} == {
        "simulated_risk_tag",
        "branching_pattern",
        "multi_hop_exposure",
    }
    assert all(signal["reason"] for signal in service_x["signals"])


def test_wallet_h_is_scored_once_for_branching_even_when_it_both_aggregates_and_splits():
    scenario, wallets = load_demo_data()

    scores = calculate_risk_scores(scenario, wallets)
    wallet_h = next(result for result in scores if result["wallet_id"] == "WALLET-H")

    assert wallet_h["score"] == 45
    assert [signal["code"] for signal in wallet_h["signals"]].count("branching_pattern") == 1
    assert any(signal["code"] == "rapid_forwarding" for signal in wallet_h["signals"])
    assert any(signal["code"] == "multi_hop_exposure" for signal in wallet_h["signals"])


def test_source_wallet_is_flagged_for_splitting_but_not_rapid_forwarding():
    scenario, wallets = load_demo_data()

    scores = calculate_risk_scores(scenario, wallets)
    source = next(result for result in scores if result["wallet_id"] == "WALLET-A")

    assert source["score"] == 20
    assert any(signal["code"] == "branching_pattern" for signal in source["signals"])
    assert all(signal["code"] != "rapid_forwarding" for signal in source["signals"])


def test_rapid_transfer_threshold_is_configurable():
    scenario, wallets = load_demo_data()

    default_scores = calculate_risk_scores(scenario, wallets)
    strict_scores = calculate_risk_scores(scenario, wallets, rapid_transfer_seconds=20)

    default_h = next(result for result in default_scores if result["wallet_id"] == "WALLET-H")
    strict_h = next(result for result in strict_scores if result["wallet_id"] == "WALLET-H")

    assert default_h["score"] == 45
    assert strict_h["score"] == 30
    assert all(signal["code"] != "rapid_forwarding" for signal in strict_h["signals"])


def test_score_bands_are_only_display_categories():
    assert risk_level(0) == "low"
    assert risk_level(29) == "low"
    assert risk_level(30) == "medium"
    assert risk_level(59) == "medium"
    assert risk_level(60) == "high"
    assert risk_level(100) == "high"

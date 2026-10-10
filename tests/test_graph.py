"""Tests for transaction graph helpers."""
from tracer.data_loader import load_demo_data
from tracer.graph import build_adjacency, has_cycle, shortest_path_depths


def test_demo_graph_has_expected_shortest_hop_depths():
    scenario, wallets = load_demo_data()

    depths = shortest_path_depths(
        scenario["transactions"],
        scenario["source_wallet"],
        [wallet["id"] for wallet in wallets],
    )

    assert len(depths) == 11
    assert depths["WALLET-A"] == 0
    assert depths["WALLET-B"] == 1
    assert depths["WALLET-D"] == 2
    assert depths["WALLET-H"] == 3
    assert depths["SERVICE-X"] == 3


def test_adjacency_indexes_outgoing_transactions():
    scenario, wallets = load_demo_data()
    adjacency = build_adjacency(
        scenario["transactions"],
        [wallet["id"] for wallet in wallets],
    )

    assert len(adjacency["WALLET-A"]) == 2
    assert [tx["transaction_id"] for tx in adjacency["WALLET-A"]] == [
        "TX-001",
        "TX-002",
    ]
    assert len(adjacency["WALLET-H"]) == 2


def test_cycle_detector_handles_cycle_and_acyclic_graph():
    acyclic = [
        {"transaction_id": "1", "from_wallet": "A", "to_wallet": "B", "timestamp": "2026-10-09T10:00:00+07:00"},
        {"transaction_id": "2", "from_wallet": "B", "to_wallet": "C", "timestamp": "2026-10-09T10:01:00+07:00"},
    ]
    cyclic = acyclic + [
        {"transaction_id": "3", "from_wallet": "C", "to_wallet": "A", "timestamp": "2026-10-09T10:02:00+07:00"},
    ]

    assert has_cycle(acyclic, ["A", "B", "C"]) is False
    assert has_cycle(cyclic, ["A", "B", "C"]) is True

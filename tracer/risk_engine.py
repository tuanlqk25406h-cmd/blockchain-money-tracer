"""Rule-based and explainable risk indicators for the synthetic demo."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from tracer.accounting import ScenarioValidationError, validate_scenario
from tracer.graph import parse_timestamp, shortest_path_depths


DEFAULT_RAPID_TRANSFER_SECONDS = 120
DEFAULT_MULTI_HOP_THRESHOLD = 3


def risk_level(score: int) -> str:
    """Map a demo score to a display band (not a probability or legal finding)."""
    if score < 30:
        return "low"
    if score < 60:
        return "medium"
    return "high"


def calculate_risk_scores(
    scenario: dict[str, Any],
    wallets: list[dict[str, Any]],
    rapid_transfer_seconds: int = DEFAULT_RAPID_TRANSFER_SECONDS,
    multi_hop_threshold: int = DEFAULT_MULTI_HOP_THRESHOLD,
) -> list[dict[str, Any]]:
    """Score wallets with transparent rules and human-readable reasons.

    Points are classroom demonstration weights, not calibrated AML thresholds.
    Each rule is applied at most once per wallet for one analysis run.
    """
    errors = validate_scenario(scenario, wallets)
    if errors:
        raise ScenarioValidationError(errors)
    if rapid_transfer_seconds < 0:
        raise ValueError("rapid_transfer_seconds must be non-negative")
    if multi_hop_threshold < 1:
        raise ValueError("multi_hop_threshold must be at least 1")

    wallet_by_id = {wallet["id"]: wallet for wallet in wallets}
    source_wallet = scenario["source_wallet"]
    depths = shortest_path_depths(
        scenario["transactions"],
        source_wallet,
        wallet_by_id.keys(),
    )

    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for transaction in scenario["transactions"]:
        outgoing[transaction["from_wallet"]].append(transaction)
        incoming[transaction["to_wallet"]].append(transaction)

    results: list[dict[str, Any]] = []
    for wallet in wallets:
        wallet_id = wallet["id"]
        in_edges = incoming[wallet_id]
        out_edges = outgoing[wallet_id]
        signals: list[dict[str, Any]] = []
        score = 0

        risk_tags = wallet.get("risk_tags") or []
        if risk_tags:
            labels = [tag.get("label", tag.get("code", "Risk tag")) for tag in risk_tags]
            score += 40
            signals.append(
                {
                    "code": "simulated_risk_tag",
                    "label": "Simulated risk label",
                    "points": 40,
                    "reason": (
                        "Entity metadata contains a synthetic classroom risk label: "
                        + ", ".join(labels)
                        + ". This is not a real-world attribution."
                    ),
                }
            )

        splitting = len(out_edges) >= 2
        aggregation = len(in_edges) >= 2
        if splitting or aggregation:
            patterns: list[str] = []
            if splitting:
                patterns.append(f"splitting across {len(out_edges)} outgoing transactions")
            if aggregation:
                patterns.append(f"aggregation from {len(in_edges)} incoming transactions")
            score += 20
            signals.append(
                {
                    "code": "branching_pattern",
                    "label": "Splitting / aggregation pattern",
                    "points": 20,
                    "reason": "The graph shows " + " and ".join(patterns) + ".",
                }
            )

        if wallet_id != source_wallet and in_edges and out_edges:
            latest_inbound: datetime = max(
                parse_timestamp(transaction["timestamp"]) for transaction in in_edges
            )
            earliest_outbound: datetime = min(
                parse_timestamp(transaction["timestamp"]) for transaction in out_edges
            )
            gap_seconds = (earliest_outbound - latest_inbound).total_seconds()
            if 0 <= gap_seconds <= rapid_transfer_seconds:
                score += 15
                signals.append(
                    {
                        "code": "rapid_forwarding",
                        "label": "Rapid forwarding",
                        "points": 15,
                        "reason": (
                            f"The gap between the latest inbound and earliest outbound "
                            f"transaction is {int(gap_seconds)} seconds, within the "
                            f"configured {rapid_transfer_seconds}-second demo threshold."
                        ),
                    }
                )

        depth = depths.get(wallet_id)
        if depth is not None and depth >= multi_hop_threshold:
            score += 10
            signals.append(
                {
                    "code": "multi_hop_exposure",
                    "label": "Multi-hop exposure",
                    "points": 10,
                    "reason": (
                        f"The wallet is at least {multi_hop_threshold} transaction hops "
                        f"from the source (shortest path: {depth} hops)."
                    ),
                }
            )

        score = min(100, score)
        results.append(
            {
                "wallet_id": wallet_id,
                "label": wallet.get("label", wallet_id),
                "kind": wallet.get("kind", "wallet"),
                "score": score,
                "level": risk_level(score),
                "shortest_path_depth": depth,
                "signals": signals,
            }
        )

    return sorted(results, key=lambda result: (-result["score"], result["wallet_id"]))

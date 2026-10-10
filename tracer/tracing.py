"""Source-to-terminal trace orchestration for the synthetic scenario."""
from __future__ import annotations

from typing import Any

from tracer.accounting import allocate_flow_lots
from tracer.graph import shortest_path_depths


def trace_from_source(
    scenario: dict[str, Any],
    wallets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return reachable wallets and deterministic source-origin terminal paths."""
    flow = allocate_flow_lots(scenario, wallets)
    source_wallet = scenario["source_wallet"]
    wallet_by_id = {wallet["id"]: wallet for wallet in wallets}
    depths = shortest_path_depths(
        scenario["transactions"],
        source_wallet,
        wallet_by_id.keys(),
    )

    reachable_wallets = [
        {
            "wallet_id": wallet_id,
            "label": wallet_by_id[wallet_id].get("label", wallet_id),
            "kind": wallet_by_id[wallet_id].get("kind", "wallet"),
            "depth": depth,
            "is_terminal": bool(wallet_by_id[wallet_id].get("is_terminal", False)),
        }
        for wallet_id, depth in sorted(depths.items(), key=lambda item: (item[1], item[0]))
    ]

    initial_amount = float(scenario["initial_amount"])
    terminal_amount = float(flow["tracked_terminal_amount"])
    difference = round(initial_amount - terminal_amount, 8)

    return {
        "scenario_id": scenario.get("scenario_id", "synthetic-scenario"),
        "title": scenario.get("title", "Synthetic tracing scenario"),
        "asset": scenario.get("asset", "USDT"),
        "source_wallet": source_wallet,
        "source_amount": initial_amount,
        "transaction_count": len(scenario["transactions"]),
        "reachable_wallet_count": len(reachable_wallets),
        "reachable_wallets": reachable_wallets,
        "paths": flow["terminal_paths"],
        "terminal_totals": flow["terminal_balances"],
        "tracked_terminal_amount": terminal_amount,
        "flow_method": flow["method"],
        "flow_method_note": flow["allocation_policy"],
        "money_conservation": {
            "source_amount": initial_amount,
            "terminal_amount": terminal_amount,
            "difference": difference,
            "passed": flow["conserved"] and difference == 0,
        },
    }

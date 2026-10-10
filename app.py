"""Local Flask application for the Blockchain Money Tracer dashboard."""
from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, render_template

from tracer.accounting import ScenarioValidationError
from tracer.data_loader import load_demo_data
from tracer.risk_engine import calculate_risk_scores
from tracer.tracing import trace_from_source

app = Flask(__name__)


def build_dashboard_payload() -> dict[str, Any]:
    """Compose graph, trace, risk, and summary data from local JSON only."""
    scenario, wallets = load_demo_data()
    trace = trace_from_source(scenario, wallets)
    risk_scores = calculate_risk_scores(scenario, wallets)
    risk_by_wallet = {item["wallet_id"]: item for item in risk_scores}

    nodes = []
    for wallet in wallets:
        risk = risk_by_wallet[wallet["id"]]
        nodes.append(
            {
                **wallet,
                "score": risk["score"],
                "risk_level": risk["level"],
                "risk_signals": risk["signals"],
                "shortest_path_depth": risk["shortest_path_depth"],
            }
        )

    edges = [
        {
            "transaction_id": transaction["transaction_id"],
            "source": transaction["from_wallet"],
            "target": transaction["to_wallet"],
            "from_wallet": transaction["from_wallet"],
            "to_wallet": transaction["to_wallet"],
            "amount": transaction["amount"],
            "asset": transaction["asset"],
            "timestamp": transaction["timestamp"],
        }
        for transaction in scenario["transactions"]
    ]

    terminal_balances = trace["terminal_totals"]
    highest_risk = risk_scores[:3]

    return {
        "scenario": {
            "scenario_id": scenario["scenario_id"],
            "title": scenario["title"],
            "asset": scenario["asset"],
            "source_wallet": scenario["source_wallet"],
            "initial_amount": scenario["initial_amount"],
            "transaction_count": len(scenario["transactions"]),
            "wallet_count": len(wallets),
        },
        "graph": {"nodes": nodes, "edges": edges, "directed": True},
        "trace": trace,
        "risk_scores": risk_scores,
        "summary": {
            "source_amount": trace["source_amount"],
            "tracked_terminal_amount": trace["tracked_terminal_amount"],
            "conservation_passed": trace["money_conservation"]["passed"],
            "wallet_count": trace["reachable_wallet_count"],
            "transaction_count": trace["transaction_count"],
            "path_count": len(trace["paths"]),
            "terminal_balances": terminal_balances,
            "high_risk_wallet_count": sum(1 for item in risk_scores if item["level"] == "high"),
            "highest_risk": highest_risk,
        },
        "disclaimer": (
            "Synthetic classroom scenario only. Risk scores are explainable review "
            "priorities, not probabilities of criminal activity or legal conclusions. "
            "FIFO flow attribution is a deterministic teaching assumption."
        ),
    }


@app.get("/")
def index():
    """Render the local interactive dashboard."""
    return render_template("index.html")


@app.get("/health")
def health():
    """Provide a lightweight local health check."""
    return jsonify(
        {
            "status": "ok",
            "project": "Blockchain Money Tracer",
            "stage": "dashboard",
        }
    )


@app.get("/api/overview")
def overview():
    """Return fixed scenario metadata for the initial dashboard state."""
    try:
        scenario, wallets = load_demo_data()
        return jsonify(
            {
                "scenario_id": scenario["scenario_id"],
                "title": scenario["title"],
                "asset": scenario["asset"],
                "source_wallet": scenario["source_wallet"],
                "initial_amount": scenario["initial_amount"],
                "transaction_count": len(scenario["transactions"]),
                "wallet_count": len(wallets),
                "simulation_only": True,
            }
        )
    except (ValueError, KeyError) as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/trace")
def run_trace():
    """Run a trace over the bundled local scenario; no external calls are made."""
    try:
        return jsonify(build_dashboard_payload())
    except ScenarioValidationError as exc:
        return jsonify({"error": str(exc), "details": exc.errors}), 422
    except (ValueError, KeyError, OSError) as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    # Bind to loopback only. The classroom demo does not expose a public server.
    app.run(host="127.0.0.1", port=5000, debug=False)

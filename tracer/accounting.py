"""Scenario validation and deterministic flow-lot accounting.

FIFO attribution is a classroom assumption for showing one reproducible
provenance path when value is pooled at an intermediate wallet. It is not
proof of the real-world identity of individual fungible tokens.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from tracer.graph import has_cycle, parse_timestamp, shortest_path_depths


class ScenarioValidationError(ValueError):
    """Raised when a synthetic transaction scenario violates its data rules."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Invalid tracing scenario: " + "; ".join(errors))


def _as_decimal(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"not a valid decimal amount: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"amount must be finite: {value!r}")
    return amount


def _as_number(value: Decimal) -> float:
    """Convert internal decimal money values to JSON-friendly numeric values."""
    return float(value)


def validate_scenario(
    scenario: dict[str, Any],
    wallets: list[dict[str, Any]],
) -> list[str]:
    """Return all detectable structural, temporal and conservation errors."""
    errors: list[str] = []
    if not isinstance(scenario, dict):
        return ["scenario must be a JSON object"]
    if not isinstance(wallets, list):
        return ["wallet/entity metadata must be a list"]

    raw_wallet_ids = [
        wallet.get("id")
        for wallet in wallets
        if isinstance(wallet, dict) and isinstance(wallet.get("id"), str) and wallet.get("id")
    ]
    if len(raw_wallet_ids) != len(wallets):
        errors.append("every wallet/entity must have a non-empty string id")
    if len(raw_wallet_ids) != len(set(raw_wallet_ids)):
        errors.append("wallet/entity ids must be unique")

    wallet_by_id = {
        wallet["id"]: wallet
        for wallet in wallets
        if isinstance(wallet, dict) and isinstance(wallet.get("id"), str) and wallet.get("id")
    }
    source_wallet = scenario.get("source_wallet")
    if not isinstance(source_wallet, str) or source_wallet not in wallet_by_id:
        errors.append("source_wallet must reference a known wallet/entity")
    elif wallet_by_id[source_wallet].get("kind") != "source":
        errors.append("source_wallet entity must have kind='source'")

    try:
        initial_amount = _as_decimal(scenario.get("initial_amount"))
        if initial_amount <= 0:
            errors.append("initial_amount must be greater than zero")
    except ValueError:
        initial_amount = Decimal("0")
        errors.append("initial_amount must be a valid finite decimal number")

    scenario_asset = scenario.get("asset")
    if not isinstance(scenario_asset, str) or not scenario_asset:
        errors.append("scenario asset must be a non-empty string")

    raw_transactions = scenario.get("transactions")
    if not isinstance(raw_transactions, list) or not raw_transactions:
        return errors + ["scenario must contain a non-empty transactions list"]

    seen_tx_ids: set[str] = set()
    valid_for_balance: list[dict[str, Any]] = []
    valid_for_graph: list[dict[str, Any]] = []
    amount_by_tx_id: dict[str, Decimal] = {}

    for index, transaction in enumerate(raw_transactions):
        prefix = f"transaction at index {index}"
        if not isinstance(transaction, dict):
            errors.append(f"{prefix} must be an object")
            continue

        tx_id = transaction.get("transaction_id")
        if not isinstance(tx_id, str) or not tx_id:
            errors.append(f"{prefix} must have a non-empty transaction_id")
        elif tx_id in seen_tx_ids:
            errors.append(f"transaction_id {tx_id!r} is duplicated")
        else:
            seen_tx_ids.add(tx_id)

        sender = transaction.get("from_wallet")
        receiver = transaction.get("to_wallet")
        endpoints_valid = (
            isinstance(sender, str)
            and sender in wallet_by_id
            and isinstance(receiver, str)
            and receiver in wallet_by_id
        )
        if not endpoints_valid:
            errors.append(f"{prefix} references an unknown sender or receiver wallet")
        elif sender == receiver:
            errors.append(f"{prefix} cannot send to the same wallet")

        try:
            amount = _as_decimal(transaction.get("amount"))
            if amount <= 0:
                errors.append(f"{prefix} amount must be greater than zero")
                amount_valid = False
            else:
                amount_valid = True
        except ValueError:
            amount = Decimal("0")
            amount_valid = False
            errors.append(f"{prefix} amount must be a valid finite decimal number")

        try:
            parse_timestamp(transaction.get("timestamp"))
            timestamp_valid = True
        except (ValueError, TypeError):
            timestamp_valid = False
            errors.append(f"{prefix} timestamp must be ISO-8601 with a timezone offset")

        if transaction.get("asset") != scenario_asset:
            errors.append(f"{prefix} asset must match scenario asset")

        if endpoints_valid:
            if wallet_by_id[sender].get("is_terminal", False):
                errors.append(f"{prefix} sends from a terminal wallet/entity")
            if receiver == source_wallet:
                errors.append(f"{prefix} sends value back into the source wallet")

        if endpoints_valid and amount_valid and timestamp_valid:
            valid_for_graph.append(transaction)
            valid_for_balance.append(transaction)
            if isinstance(tx_id, str):
                amount_by_tx_id[tx_id] = amount

    wallet_ids = list(wallet_by_id)
    if valid_for_graph and has_cycle(valid_for_graph, wallet_ids):
        errors.append("transaction graph must be acyclic for this tracing model")

    if isinstance(source_wallet, str) and source_wallet in wallet_by_id:
        depths = shortest_path_depths(valid_for_graph, source_wallet, wallet_ids)
        unreachable = sorted(set(wallet_ids) - set(depths))
        if unreachable:
            errors.append("wallets/entities are not reachable from the source: " + ", ".join(unreachable))

    incoming: dict[str, Decimal] = defaultdict(Decimal)
    outgoing: dict[str, Decimal] = defaultdict(Decimal)
    for transaction in valid_for_balance:
        sender = transaction["from_wallet"]
        receiver = transaction["to_wallet"]
        amount = amount_by_tx_id.get(transaction.get("transaction_id"))
        if amount is None:
            continue
        outgoing[sender] += amount
        incoming[receiver] += amount

    if isinstance(source_wallet, str) and source_wallet in wallet_by_id:
        if incoming[source_wallet] != 0:
            errors.append("source wallet must not receive funds in the demo scenario")
        if initial_amount > 0 and outgoing[source_wallet] != initial_amount:
            errors.append(
                f"source outgoing total ({outgoing[source_wallet]}) must equal "
                f"initial_amount ({initial_amount})"
            )

    terminal_ids = {
        wallet_id
        for wallet_id, wallet in wallet_by_id.items()
        if bool(wallet.get("is_terminal", False))
    }
    if not terminal_ids:
        errors.append("scenario must define at least one terminal wallet/entity")

    for wallet_id, wallet in wallet_by_id.items():
        if wallet_id == source_wallet:
            continue
        if wallet.get("is_terminal", False):
            if outgoing[wallet_id] != 0:
                errors.append(f"terminal wallet/entity {wallet_id} must not have outgoing transactions")
            if incoming[wallet_id] <= 0:
                errors.append(f"terminal wallet/entity {wallet_id} must receive a positive amount")
        elif incoming[wallet_id] != outgoing[wallet_id]:
            errors.append(
                f"intermediate wallet {wallet_id} must conserve flow: "
                f"incoming={incoming[wallet_id]}, outgoing={outgoing[wallet_id]}"
            )

    terminal_total = sum((incoming[wallet_id] for wallet_id in terminal_ids), Decimal("0"))
    if initial_amount > 0 and terminal_total != initial_amount:
        errors.append(
            f"terminal received total ({terminal_total}) must equal initial_amount ({initial_amount})"
        )

    # Aggregate balance checks alone do not catch a wallet spending funds
    # before those funds arrive. Simulate available balances in chronological
    # order so the fixed demo cannot imply impossible transaction timing.
    if (
        isinstance(source_wallet, str)
        and source_wallet in wallet_by_id
        and initial_amount > 0
    ):
        available: dict[str, Decimal] = defaultdict(Decimal)
        available[source_wallet] = initial_amount
        ordered_transactions = sorted(
            valid_for_balance,
            key=lambda transaction: (
                parse_timestamp(transaction["timestamp"]),
                str(transaction.get("transaction_id", "")),
            ),
        )
        for transaction in ordered_transactions:
            sender = transaction["from_wallet"]
            receiver = transaction["to_wallet"]
            amount = _as_decimal(transaction["amount"])
            if available[sender] < amount:
                errors.append(
                    f"transaction {transaction.get('transaction_id', '<unknown>')} "
                    f"spends funds before they are available at {sender}: "
                    f"available={available[sender]}, amount={amount}"
                )
                continue
            available[sender] -= amount
            available[receiver] += amount

    return errors


def allocate_flow_lots(
    scenario: dict[str, Any],
    wallets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Trace source-origin value through transactions using deterministic FIFO lots."""
    errors = validate_scenario(scenario, wallets)
    if errors:
        raise ScenarioValidationError(errors)

    wallet_by_id = {wallet["id"]: wallet for wallet in wallets}
    source_wallet = scenario["source_wallet"]
    initial_amount = _as_decimal(scenario["initial_amount"])
    lots_by_wallet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    lots_by_wallet[source_wallet].append(
        {
            "amount": initial_amount,
            "wallet_path": [source_wallet],
            "transaction_ids": [],
        }
    )

    transactions = sorted(
        scenario["transactions"],
        key=lambda tx: (parse_timestamp(tx["timestamp"]), tx["transaction_id"]),
    )
    transaction_allocations: list[dict[str, Any]] = []
    terminal_paths: list[dict[str, Any]] = []

    for transaction in transactions:
        sender = transaction["from_wallet"]
        receiver = transaction["to_wallet"]
        transaction_id = transaction["transaction_id"]
        required = _as_decimal(transaction["amount"])
        sender_lots = lots_by_wallet[sender]
        new_receiver_lots: list[dict[str, Any]] = []

        while required > 0:
            if not sender_lots:
                raise ScenarioValidationError(
                    [f"{transaction_id} attempts to spend more source-origin value than available"]
                )

            lot = sender_lots[0]
            allocated = min(lot["amount"], required)
            wallet_path = list(lot["wallet_path"]) + [receiver]
            transaction_ids = list(lot["transaction_ids"]) + [transaction_id]
            amount_number = _as_number(allocated)

            allocation = {
                "transaction_id": transaction_id,
                "from_wallet": sender,
                "to_wallet": receiver,
                "amount": amount_number,
                "wallet_path": wallet_path,
                "transaction_ids": transaction_ids,
            }
            transaction_allocations.append(allocation)

            new_receiver_lots.append(
                {
                    "amount": allocated,
                    "wallet_path": wallet_path,
                    "transaction_ids": transaction_ids,
                }
            )

            if wallet_by_id[receiver].get("is_terminal", False):
                terminal_paths.append(
                    {
                        "terminal_wallet": receiver,
                        "amount": amount_number,
                        "wallet_path": wallet_path,
                        "transaction_ids": transaction_ids,
                    }
                )

            lot["amount"] -= allocated
            required -= allocated
            if lot["amount"] == 0:
                sender_lots.pop(0)

        lots_by_wallet[receiver].extend(new_receiver_lots)

    terminal_ids = [
        wallet["id"] for wallet in wallets if wallet.get("is_terminal", False)
    ]
    terminal_balances_decimal = {
        terminal_id: sum(
            (lot["amount"] for lot in lots_by_wallet[terminal_id]),
            Decimal("0"),
        )
        for terminal_id in terminal_ids
    }
    terminal_total = sum(terminal_balances_decimal.values(), Decimal("0"))

    non_terminal_leftovers = {
        wallet_id: sum((lot["amount"] for lot in lots), Decimal("0"))
        for wallet_id, lots in lots_by_wallet.items()
        if not wallet_by_id[wallet_id].get("is_terminal", False)
        and sum((lot["amount"] for lot in lots), Decimal("0")) != 0
    }
    if non_terminal_leftovers:
        raise ScenarioValidationError(
            [f"non-terminal wallets retain value after all transactions: {non_terminal_leftovers}"]
        )
    if terminal_total != initial_amount:
        raise ScenarioValidationError(
            [f"terminal flow total {terminal_total} does not equal initial amount {initial_amount}"]
        )

    path_total = sum((_as_decimal(path["amount"]) for path in terminal_paths), Decimal("0"))
    if path_total != terminal_total:
        raise ScenarioValidationError(
            [f"terminal path total {path_total} does not equal terminal total {terminal_total}"]
        )

    return {
        "method": "deterministic_fifo",
        "allocation_policy": (
            "FIFO attribution by transaction timestamp and transaction ID. "
            "This is a reproducible classroom assumption for pooled value, not proof "
            "of real-world token identity."
        ),
        "transaction_allocations": transaction_allocations,
        "terminal_paths": terminal_paths,
        "terminal_balances": {
            wallet_id: _as_number(amount)
            for wallet_id, amount in terminal_balances_decimal.items()
        },
        "tracked_terminal_amount": _as_number(terminal_total),
        "initial_amount": _as_number(initial_amount),
        "conserved": terminal_total == initial_amount and path_total == terminal_total,
    }

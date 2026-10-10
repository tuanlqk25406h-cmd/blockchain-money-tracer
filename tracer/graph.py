"""Graph utilities for the synthetic transaction network."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Iterable


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and require an explicit timezone."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp must include a timezone offset: {value!r}")
    return parsed


def _tx_id(transaction: dict[str, Any]) -> str:
    return str(transaction.get("transaction_id", ""))


def build_adjacency(
    transactions: Iterable[dict[str, Any]],
    wallet_ids: Iterable[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build a deterministic outgoing-edge index keyed by sender wallet."""
    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if wallet_ids is not None:
        for wallet_id in wallet_ids:
            adjacency[str(wallet_id)]

    for transaction in transactions:
        sender = transaction.get("from_wallet")
        if isinstance(sender, str) and sender:
            adjacency[sender].append(transaction)

    for outgoing in adjacency.values():
        outgoing.sort(key=lambda tx: (parse_timestamp(tx["timestamp"]), _tx_id(tx)))
    return dict(adjacency)


def shortest_path_depths(
    transactions: Iterable[dict[str, Any]],
    source_wallet: str,
    wallet_ids: Iterable[str] | None = None,
) -> dict[str, int]:
    """Return shortest transaction-hop distance from source using breadth-first search."""
    transaction_list = list(transactions)
    adjacency = build_adjacency(transaction_list, wallet_ids)
    depths = {source_wallet: 0}
    queue: deque[str] = deque([source_wallet])

    while queue:
        wallet_id = queue.popleft()
        for transaction in adjacency.get(wallet_id, []):
            receiver = transaction.get("to_wallet")
            if not isinstance(receiver, str) or not receiver:
                continue
            if receiver not in depths:
                depths[receiver] = depths[wallet_id] + 1
                queue.append(receiver)

    return depths


def has_cycle(
    transactions: Iterable[dict[str, Any]],
    wallet_ids: Iterable[str] | None = None,
) -> bool:
    """Return True if the directed transaction graph contains a cycle."""
    transaction_list = list(transactions)
    node_ids = set(str(wallet_id) for wallet_id in (wallet_ids or []))
    adjacency: dict[str, list[str]] = defaultdict(list)

    for transaction in transaction_list:
        sender = transaction.get("from_wallet")
        receiver = transaction.get("to_wallet")
        if isinstance(sender, str) and sender and isinstance(receiver, str) and receiver:
            node_ids.add(sender)
            node_ids.add(receiver)
            adjacency[sender].append(receiver)

    indegree = {node_id: 0 for node_id in node_ids}
    for sender, receivers in adjacency.items():
        for receiver in receivers:
            indegree[receiver] = indegree.get(receiver, 0) + 1

    queue: deque[str] = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    visited_count = 0

    while queue:
        current = queue.popleft()
        visited_count += 1
        for receiver in adjacency.get(current, []):
            indegree[receiver] -= 1
            if indegree[receiver] == 0:
                queue.append(receiver)

    return visited_count != len(indegree)


def build_graph(
    wallets: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a simple graph payload suitable for later dashboard integration."""
    wallet_ids = [wallet["id"] for wallet in wallets]
    return {
        "nodes": wallets,
        "edges": transactions,
        "adjacency": build_adjacency(transactions, wallet_ids),
        "has_cycle": has_cycle(transactions, wallet_ids),
    }

"""Load the local synthetic scenario and wallet/entity metadata."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def load_demo_data(data_dir: str | Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load the fixed demo scenario and entity metadata from local JSON files.

    No network or external service is used.
    """
    directory = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    scenario_path = directory / "simulated_transactions.json"
    entities_path = directory / "entities.json"

    try:
        with scenario_path.open("r", encoding="utf-8") as file:
            scenario = json.load(file)
        with entities_path.open("r", encoding="utf-8") as file:
            entities = json.load(file)
    except OSError as exc:
        raise ValueError(f"Could not read local demo data in {directory}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in local demo data: {exc}") from exc

    if not isinstance(scenario, dict):
        raise ValueError("Scenario JSON must contain an object.")
    if not isinstance(entities, list):
        raise ValueError("Entities JSON must contain a list.")

    return scenario, entities

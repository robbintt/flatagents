"""Execution helpers for Anything Agent."""
from __future__ import annotations

import json
from typing import Any

import yaml


def load_machine_config(machine_yaml: str) -> dict:
    """Load machine config from YAML/JSON string."""
    config = yaml.safe_load(machine_yaml) or {}
    if not isinstance(config, dict):
        raise ValueError("Machine config must be a mapping")
    return config


def apply_snapshot(machine_config: dict, snapshot: dict) -> dict:
    """Apply snapshot state/context to machine config for resume."""
    data = machine_config.get("data", {})
    states = data.get("states", {})
    target_state = snapshot.get("state")

    if target_state and target_state in states:
        for state_name, state in states.items():
            if state.get("type") == "initial":
                state.pop("type", None)
        states[target_state]["type"] = "initial"
    elif target_state:
        # Fallback to default initial state if snapshot state is missing
        pass

    data["context"] = snapshot.get("context", {})
    machine_config["data"] = data
    return machine_config


def serialize_snapshot(output: Any | None = None) -> str:
    payload = {"state": "done", "output": output}
    return json.dumps(payload)

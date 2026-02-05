"""Execution helpers for Anything Agent."""
from __future__ import annotations

import json
from pathlib import Path
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

    data["context"] = _escape_jinja(snapshot.get("context", {}))
    machine_config["data"] = data
    return machine_config


def _escape_jinja(value: Any) -> Any:
    if isinstance(value, str):
        if value.startswith("{% raw %}") and value.endswith("{% endraw %}"):
            return value
        if "{{" in value or "{%" in value or "{#" in value:
            return f"{{% raw %}}{value}{{% endraw %}}"
        return value
    if isinstance(value, dict):
        return {k: _escape_jinja(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_escape_jinja(v) for v in value]
    return value


def serialize_snapshot(output: Any | None = None) -> str:
    payload = {"state": "done", "output": output}
    return json.dumps(payload)


def get_log_root() -> Path:
    return Path(__file__).parent.parent.parent / "logs"


def get_session_log_dir(session_id: str) -> Path:
    root = get_log_root()
    root.mkdir(parents=True, exist_ok=True)
    session_dir = root / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_execution_log_path(session_id: str, execution_id: str) -> Path:
    return get_session_log_dir(session_id) / f"execution_{execution_id}.log"

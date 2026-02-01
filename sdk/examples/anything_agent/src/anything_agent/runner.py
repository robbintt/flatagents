"""Run an execution from the Anything Agent database."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flatagents import FlatMachine, setup_logging, get_logger

from .execution import apply_snapshot, load_machine_config, serialize_snapshot, get_session_log_dir
from .hooks import AnythingAgentHooks, AwaitingApproval
from .invoker import AnythingAgentSubprocessInvoker


def _resolve_config_dir(machine_config: dict, fallback: Path) -> Path:
    data = machine_config.get("data", {})
    config_dir = data.pop("_config_dir", None)
    return Path(config_dir) if config_dir else fallback


def _load_execution(db_path: str, execution_id: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT execution_id, session_id, machine_yaml, snapshot FROM executions WHERE execution_id = ?",
        (execution_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise ValueError(f"Execution {execution_id} not found")

    return dict(row)


def _update_status(db_path: str, execution_id: str, status: str, snapshot: str | None = None):
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()
    terminated_at = now if status in ("terminated", "failed") else None

    if snapshot is not None:
        conn.execute(
            "UPDATE executions SET status = ?, snapshot = ?, terminated_at = ? WHERE execution_id = ?",
            (status, snapshot, terminated_at, execution_id),
        )
    else:
        conn.execute(
            "UPDATE executions SET status = ?, terminated_at = ? WHERE execution_id = ?",
            (status, terminated_at, execution_id),
        )
    conn.commit()
    conn.close()


async def run_execution(db_path: str, execution_id: str):
    row = _load_execution(db_path, execution_id)
    session_id = row["session_id"]
    snapshot = json.loads(row["snapshot"]) if row.get("snapshot") else None

    session_log_dir = get_session_log_dir(session_id)
    os.environ.setdefault("FLATAGENTS_LOG_DIR", str(session_log_dir))
    os.environ.setdefault("FLATAGENTS_LOG_LEVEL", "DEBUG")
    os.environ.setdefault("FLATAGENTS_LOG_FORMAT", "standard")
    os.environ.setdefault("FLATAGENTS_METRICS_ENABLED", "true")
    os.environ.setdefault("OTEL_METRICS_EXPORTER", "console")
    os.environ.setdefault("OTEL_SERVICE_NAME", "anything_agent")
    setup_logging(level=os.environ.get("FLATAGENTS_LOG_LEVEL"), format=os.environ.get("FLATAGENTS_LOG_FORMAT"), force=True)
    logger = get_logger(__name__)

    machine_yaml = row.get("machine_yaml")
    if not machine_yaml:
        machine_yaml = (Path(__file__).parent / "machines" / "core.yml").read_text()

    machine_config = load_machine_config(machine_yaml)
    base_dir = Path(__file__).parent / "machines"
    config_dir = _resolve_config_dir(machine_config, base_dir)

    input_data = {"session_id": session_id, "db_path": db_path}
    if snapshot and snapshot.get("state") and snapshot.get("context"):
        machine_config = apply_snapshot(machine_config, snapshot)
        input_data = {}
    elif snapshot and snapshot.get("input"):
        input_data = snapshot["input"] or {}
        input_data.setdefault("session_id", session_id)
        input_data.setdefault("db_path", db_path)

    invoker = AnythingAgentSubprocessInvoker(db_path=db_path, working_dir=str(config_dir))
    hooks = AnythingAgentHooks(db_path, session_id, execution_id)

    machine = FlatMachine(
        config_dict=machine_config,
        hooks=hooks,
        _config_dir=str(config_dir),
        invoker=invoker,
        profiles_file=str(Path(__file__).parent.parent.parent / "config" / "profiles.yml"),
    )

    _update_status(db_path, execution_id, "running")

    try:
        result = await machine.execute(input=input_data)
        snapshot_payload = serialize_snapshot(result)
        _update_status(db_path, execution_id, "terminated", snapshot_payload)
    except AwaitingApproval:
        _update_status(db_path, execution_id, "suspended")
    except Exception as exc:
        logger.exception("Execution failed: %s", exc)
        _update_status(db_path, execution_id, "failed")
        raise


def main():
    parser = argparse.ArgumentParser(description="Anything Agent Runner")
    parser.add_argument("--db", default="./anything_agent.db")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    asyncio.run(run_execution(args.db, args.execution_id))


if __name__ == "__main__":
    main()

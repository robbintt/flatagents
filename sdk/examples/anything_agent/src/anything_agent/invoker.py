"""Subprocess invoker that runs machines via anything_agent.runner."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import yaml
from flatagents.actions import MachineInvoker

from .execution import get_execution_log_path


def _extract_machine_type(config: Dict[str, Any]) -> str:
    metadata = config.get("data", {}).get("metadata", {})
    return metadata.get("type") or config.get("data", {}).get("name", "machine")


def _extract_tags(config: Dict[str, Any]) -> str:
    metadata = config.get("data", {}).get("metadata", {})
    tags = metadata.get("tags", [])
    return json.dumps(tags or [])


def _inject_config_dir(config: Dict[str, Any], config_dir: str | None) -> Dict[str, Any]:
    if not config_dir:
        return config
    data = config.setdefault("data", {})
    data["_config_dir"] = config_dir
    return config


class AnythingAgentSubprocessInvoker(MachineInvoker):
    """Launch machines in subprocesses using anything_agent.runner."""

    def __init__(self, db_path: str, working_dir: str | None = None):
        self.db_path = db_path
        self.working_dir = working_dir

    async def invoke(
        self,
        caller_machine: "FlatMachine",
        target_config: Dict[str, Any],
        input_data: Dict[str, Any],
        execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not execution_id:
            execution_id = str(uuid.uuid4())

        await self.launch(caller_machine, target_config, input_data, execution_id)
        return await self._wait_for_completion(execution_id)

    async def launch(
        self,
        caller_machine: "FlatMachine",
        target_config: Dict[str, Any],
        input_data: Dict[str, Any],
        execution_id: str,
    ) -> None:
        session_id = input_data.get("session_id")
        db_path = input_data.get("db_path") or self.db_path

        if not session_id:
            raise ValueError("session_id required to launch machine")
        if not db_path:
            raise ValueError("db_path required to launch machine")

        config_dir = getattr(caller_machine, "_config_dir", None)
        target_config = _inject_config_dir(target_config, config_dir)

        machine_yaml = yaml.safe_dump(target_config, sort_keys=False)
        now = datetime.now().isoformat()
        machine_type = _extract_machine_type(target_config)
        tags = _extract_tags(target_config)
        snapshot = json.dumps({"input": input_data})

        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR IGNORE INTO executions (execution_id, session_id, parent_id, machine_type, tags, machine_yaml, snapshot, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?)",
            (
                execution_id,
                session_id,
                caller_machine.execution_id,
                machine_type,
                tags,
                machine_yaml,
                snapshot,
                now,
            ),
        )
        conn.execute(
            "UPDATE executions SET snapshot = ?, status = 'running' WHERE execution_id = ?",
            (snapshot, execution_id),
        )
        conn.commit()
        conn.close()

        cmd = [
            sys.executable,
            "-m",
            "anything_agent.runner",
            "--db",
            db_path,
            "--execution-id",
            execution_id,
        ]
        log_path = get_execution_log_path(session_id, execution_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "a", encoding="utf-8")

        subprocess.Popen(
            cmd,
            cwd=self.working_dir,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
        log_file.close()

    async def _wait_for_completion(self, execution_id: str, poll_interval: float = 0.5) -> Dict[str, Any]:
        while True:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT status, snapshot FROM executions WHERE execution_id = ?",
                (execution_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return {"_error": "execution not found"}

            status = row["status"]
            if status == "terminated":
                snapshot = row["snapshot"]
                if snapshot:
                    try:
                        payload = json.loads(snapshot)
                        return payload.get("output", {}) or {}
                    except json.JSONDecodeError:
                        return {}
                return {}

            if status in ("failed", "stopped"):
                return {"_error": f"execution {status}"}

            await asyncio.sleep(poll_interval)

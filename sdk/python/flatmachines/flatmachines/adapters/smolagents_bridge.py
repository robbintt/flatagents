"""smolagents adapter using a Python subprocess runner (cross-process bridge).

Mirrors the pi-agent bridge pattern: the FlatMachine orchestrator spawns a
separate Python process that loads a smolagents factory and runs the agent.
This avoids importing smolagents into the orchestrator's process and makes
the approach symmetric with the pi-agent Node.js bridge.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

from ..agents import AgentAdapter, AgentAdapterContext, AgentExecutor, AgentRef, AgentResult


class SmolagentsBridgeExecutor(AgentExecutor):
    def __init__(
        self,
        ref: str,
        config: Optional[Dict[str, Any]],
        runner_path: str,
        python_path: str,
        cwd: str,
        env: Dict[str, str],
        timeout: Optional[float],
    ):
        self._ref = ref
        self._config = config or {}
        self._runner_path = runner_path
        self._python_path = python_path
        self._cwd = cwd
        self._env = env
        self._timeout = timeout

    @property
    def metadata(self) -> Dict[str, Any]:
        return {}

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        request = {
            "ref": self._ref,
            "config": self._config,
            "input": input_data,
            "cwd": self._cwd,
        }
        payload = json.dumps(request)

        proc = await asyncio.create_subprocess_exec(
            self._python_path,
            self._runner_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
            env=self._env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(payload.encode()), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError("smolagents runner timed out")

        if proc.returncode != 0:
            raise RuntimeError(
                f"smolagents runner failed ({proc.returncode}): {stderr.decode().strip()}"
            )

        if not stdout:
            return AgentResult()

        try:
            result = json.loads(stdout.decode())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from smolagents runner: {stdout.decode()}") from exc

        return AgentResult(
            output=result.get("output"),
            content=result.get("content"),
            raw=result.get("raw"),
            usage=result.get("usage"),
            cost=result.get("cost"),
            metadata=result.get("metadata"),
        )


class SmolagentsBridgeAdapter(AgentAdapter):
    type_name = "smolagents-bridge"

    def create_executor(
        self,
        *,
        agent_name: str,
        agent_ref: AgentRef,
        context: AgentAdapterContext,
    ) -> AgentExecutor:
        if not agent_ref.ref:
            raise ValueError(
                f"smolagents-bridge reference missing ref for agent '{agent_name}'"
            )

        settings = context.settings.get("agent_runners", {}).get("smolagents", {})
        config = agent_ref.config or {}

        runner_path = config.get("runner") or settings.get("runner")
        if not runner_path:
            runner_path = os.path.join(os.path.dirname(__file__), "smolagents_runner.py")
        elif not os.path.isabs(runner_path):
            runner_path = os.path.join(context.config_dir, runner_path)

        python_path = config.get("python") or settings.get("python") or sys.executable
        timeout = config.get("timeout") or settings.get("timeout")
        cwd = config.get("cwd") or settings.get("cwd") or context.config_dir

        env = dict(os.environ)
        env.update(settings.get("env", {}) if isinstance(settings.get("env"), dict) else {})
        env.update(config.get("env", {}) if isinstance(config.get("env"), dict) else {})

        return SmolagentsBridgeExecutor(
            ref=agent_ref.ref,
            config=config.get("agent_config") or config.get("config") or {},
            runner_path=runner_path,
            python_path=python_path,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )

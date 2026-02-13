"""
Lifecycle management for FlatMachine checkpoint and restore.

Provides three complementary methods for managing the checkpoint/restore
lifecycle generically across backends:

1. ExecutionStore     - Backend-agnostic execution index with list/query/delete.
2. ExecutionManager   - Central lifecycle manager with run/resume/list/cleanup.
3. supervised_run()   - Simple convenience function for auto-retry on failure.

These abstractions free users from manually tracking execution IDs, detecting
crashes, and orchestrating resume logic.
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from .persistence import (
    PersistenceBackend,
    LocalFileBackend,
    MemoryBackend,
    CheckpointManager,
    MachineSnapshot,
)
from .locking import ExecutionLock, LocalFileLock, NoOpLock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Execution status and record
# ---------------------------------------------------------------------------

class ExecutionStatus(str, Enum):
    """Status of a tracked execution."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class ExecutionRecord:
    """Metadata for a tracked execution.

    Derived from the latest checkpoint snapshot.  The record is a lightweight
    view — it does **not** contain the full context.
    """
    execution_id: str
    machine_name: str
    status: ExecutionStatus
    current_state: str
    step: int
    created_at: str
    event: Optional[str] = None
    total_api_calls: int = 0
    total_cost: float = 0.0
    parent_execution_id: Optional[str] = None
    has_output: bool = False


def _record_from_snapshot(snapshot: MachineSnapshot) -> ExecutionRecord:
    """Build an ExecutionRecord from a MachineSnapshot."""
    if snapshot.event == "machine_end":
        status = ExecutionStatus.COMPLETED
    else:
        status = ExecutionStatus.UNKNOWN  # May be running or failed
    return ExecutionRecord(
        execution_id=snapshot.execution_id,
        machine_name=snapshot.machine_name,
        status=status,
        current_state=snapshot.current_state,
        step=snapshot.step,
        created_at=snapshot.created_at,
        event=snapshot.event,
        total_api_calls=snapshot.total_api_calls or 0,
        total_cost=snapshot.total_cost or 0.0,
        parent_execution_id=snapshot.parent_execution_id,
        has_output=snapshot.output is not None,
    )


# ---------------------------------------------------------------------------
# Method 1 – ExecutionStore
# ---------------------------------------------------------------------------

class ExecutionStore(ABC):
    """Backend-agnostic execution index.

    The store records which execution IDs exist and their latest snapshot
    metadata.  Concrete implementations wrap the underlying persistence
    backend with listing and querying capabilities that the base
    ``PersistenceBackend`` interface does not provide.
    """

    @abstractmethod
    async def record(self, snapshot: MachineSnapshot) -> None:
        """Record or update an execution from its latest snapshot."""

    @abstractmethod
    async def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Return the record for *execution_id*, or ``None``."""

    @abstractmethod
    async def list(
        self,
        *,
        status: Optional[ExecutionStatus] = None,
        machine_name: Optional[str] = None,
    ) -> List[ExecutionRecord]:
        """List executions, optionally filtered by status or machine name."""

    @abstractmethod
    async def delete(self, execution_id: str) -> None:
        """Remove all stored data for an execution."""


class LocalExecutionStore(ExecutionStore):
    """File-based execution store backed by a JSON index file.

    Stores a lightweight ``_index.json`` alongside checkpoint data in the
    same *base_dir* used by :class:`LocalFileBackend`.
    """

    def __init__(self, base_dir: str = ".checkpoints"):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._base_dir / "_index.json"
        self._index: Optional[Dict[str, dict]] = None

    # -- internal helpers ---------------------------------------------------

    async def _load_index(self) -> Dict[str, dict]:
        if self._index is not None:
            return self._index
        if self._index_path.exists():
            raw = self._index_path.read_text(encoding="utf-8")
            self._index = json.loads(raw)
        else:
            self._index = {}
        return self._index

    async def _save_index(self) -> None:
        idx = await self._load_index()
        tmp = self._index_path.parent / f".{self._index_path.name}.tmp"
        tmp.write_text(json.dumps(idx, indent=2), encoding="utf-8")
        tmp.replace(self._index_path)

    # -- public API ---------------------------------------------------------

    async def record(self, snapshot: MachineSnapshot) -> None:
        idx = await self._load_index()
        rec = _record_from_snapshot(snapshot)
        idx[snapshot.execution_id] = asdict(rec)
        await self._save_index()

    async def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        idx = await self._load_index()
        data = idx.get(execution_id)
        if data is None:
            return None
        data["status"] = ExecutionStatus(data["status"])
        return ExecutionRecord(**data)

    async def list(
        self,
        *,
        status: Optional[ExecutionStatus] = None,
        machine_name: Optional[str] = None,
    ) -> List[ExecutionRecord]:
        idx = await self._load_index()
        results: List[ExecutionRecord] = []
        for data in idx.values():
            data = dict(data)  # shallow copy
            data["status"] = ExecutionStatus(data["status"])
            rec = ExecutionRecord(**data)
            if status is not None and rec.status != status:
                continue
            if machine_name is not None and rec.machine_name != machine_name:
                continue
            results.append(rec)
        return results

    async def delete(self, execution_id: str) -> None:
        idx = await self._load_index()
        idx.pop(execution_id, None)
        await self._save_index()
        # Also remove checkpoint directory
        exec_dir = self._base_dir / execution_id
        if exec_dir.exists() and exec_dir.is_dir():
            import shutil
            shutil.rmtree(exec_dir)


class MemoryExecutionStore(ExecutionStore):
    """In-memory execution store for testing and ephemeral workloads."""

    def __init__(self) -> None:
        self._records: Dict[str, ExecutionRecord] = {}

    async def record(self, snapshot: MachineSnapshot) -> None:
        self._records[snapshot.execution_id] = _record_from_snapshot(snapshot)

    async def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        return self._records.get(execution_id)

    async def list(
        self,
        *,
        status: Optional[ExecutionStatus] = None,
        machine_name: Optional[str] = None,
    ) -> List[ExecutionRecord]:
        results: List[ExecutionRecord] = []
        for rec in self._records.values():
            if status is not None and rec.status != status:
                continue
            if machine_name is not None and rec.machine_name != machine_name:
                continue
            results.append(rec)
        return results

    async def delete(self, execution_id: str) -> None:
        self._records.pop(execution_id, None)


# ---------------------------------------------------------------------------
# Method 2 – ExecutionManager
# ---------------------------------------------------------------------------

class ExecutionManager:
    """Central lifecycle manager for FlatMachine executions.

    Wraps machine creation, execution, automatic retry on failure, execution
    listing, and checkpoint cleanup into a single cohesive API.  Works with
    any ``PersistenceBackend`` and ``ExecutionStore`` combination.

    Basic usage::

        manager = ExecutionManager(
            backend=LocalFileBackend(),
            store=LocalExecutionStore(),
        )

        # Run with automatic retry
        result = await manager.run(
            config_dict=my_config,
            input={"query": "hello"},
            max_retries=3,
        )

        # List all executions
        records = await manager.list_executions()

        # Resume a specific failed execution
        result = await manager.resume(execution_id)

        # Clean up old data
        await manager.cleanup(older_than=timedelta(days=7))
    """

    def __init__(
        self,
        backend: Optional[PersistenceBackend] = None,
        store: Optional[ExecutionStore] = None,
        lock: Optional[ExecutionLock] = None,
    ) -> None:
        self.backend = backend or LocalFileBackend()
        self.store = store or (
            LocalExecutionStore()
            if isinstance(self.backend, LocalFileBackend)
            else MemoryExecutionStore()
        )
        self.lock = lock

    # -- run ----------------------------------------------------------------

    async def run(
        self,
        *,
        config_file: Optional[str] = None,
        config_dict: Optional[Dict] = None,
        hooks=None,
        input: Optional[Dict[str, Any]] = None,
        max_steps: int = 1000,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        hooks_factory: Optional[Callable] = None,
        **machine_kwargs,
    ) -> Dict[str, Any]:
        """Execute a machine with optional automatic retry on failure.

        On each failure the latest checkpoint is used to resume, so work
        already completed is not repeated.

        Args:
            config_file: Path to machine YAML/JSON config.
            config_dict: Inline machine config dict.
            hooks: MachineHooks instance (reused across retries unless
                *hooks_factory* is provided).
            input: Input dict passed to the initial execution.
            max_steps: Maximum state transitions per attempt.
            max_retries: Number of retry attempts after the initial run.
                ``0`` means no retries (fail immediately).
            retry_delay: Seconds to wait between retries.
            hooks_factory: Optional callable returning a fresh hooks
                instance for each attempt (useful when hooks carry state).
            **machine_kwargs: Extra keyword arguments forwarded to
                ``FlatMachine.__init__``.

        Returns:
            The final output dict from the machine.

        Raises:
            The last exception if all retries are exhausted.
        """
        from .flatmachine import FlatMachine

        execution_id: Optional[str] = None
        last_error: Optional[Exception] = None

        for attempt in range(1 + max_retries):
            current_hooks = hooks_factory() if hooks_factory else hooks
            machine = FlatMachine(
                config_file=config_file,
                config_dict=config_dict,
                hooks=current_hooks,
                persistence=self.backend,
                lock=self.lock,
                **machine_kwargs,
            )

            if execution_id is None:
                execution_id = machine.execution_id

            try:
                if attempt == 0:
                    result = await machine.execute(
                        input=input, max_steps=max_steps,
                    )
                else:
                    result = await machine.execute(
                        input=input, max_steps=max_steps,
                        resume_from=execution_id,
                    )

                # Record successful completion
                snapshot = await CheckpointManager(
                    self.backend, execution_id
                ).load_latest()
                if snapshot:
                    await self.store.record(snapshot)

                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Execution %s attempt %d/%d failed: %s",
                    execution_id, attempt + 1, 1 + max_retries, exc,
                )

                # Record the failure in the store
                snapshot = await CheckpointManager(
                    self.backend, execution_id
                ).load_latest()
                if snapshot:
                    rec = _record_from_snapshot(snapshot)
                    rec.status = ExecutionStatus.FAILED
                    # Store directly since we built the record manually
                    await self.store.record(snapshot)

                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        raise last_error  # type: ignore[misc]

    # -- resume -------------------------------------------------------------

    async def resume(
        self,
        execution_id: str,
        *,
        config_file: Optional[str] = None,
        config_dict: Optional[Dict] = None,
        hooks=None,
        max_steps: int = 1000,
        **machine_kwargs,
    ) -> Dict[str, Any]:
        """Resume a previously failed or incomplete execution.

        Args:
            execution_id: The execution ID to resume.
            config_file: Path to machine config (must match original).
            config_dict: Inline machine config dict.
            hooks: MachineHooks instance.
            max_steps: Maximum state transitions.
            **machine_kwargs: Extra keyword arguments for FlatMachine.

        Returns:
            The final output dict.
        """
        from .flatmachine import FlatMachine

        machine = FlatMachine(
            config_file=config_file,
            config_dict=config_dict,
            hooks=hooks,
            persistence=self.backend,
            lock=self.lock,
            **machine_kwargs,
        )
        result = await machine.execute(
            max_steps=max_steps, resume_from=execution_id,
        )

        # Update store
        snapshot = await CheckpointManager(
            self.backend, execution_id
        ).load_latest()
        if snapshot:
            await self.store.record(snapshot)

        return result

    # -- list / get ---------------------------------------------------------

    async def list_executions(
        self,
        *,
        status: Optional[ExecutionStatus] = None,
        machine_name: Optional[str] = None,
    ) -> List[ExecutionRecord]:
        """List tracked executions with optional filters."""
        return await self.store.list(status=status, machine_name=machine_name)

    async def get_execution(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Get the record for a single execution."""
        return await self.store.get(execution_id)

    # -- cleanup ------------------------------------------------------------

    async def cleanup(
        self,
        *,
        older_than: Optional[timedelta] = None,
        status: Optional[ExecutionStatus] = None,
    ) -> List[str]:
        """Remove executions matching the given criteria.

        Args:
            older_than: Remove executions created before ``now - older_than``.
            status: Only remove executions with this status.

        Returns:
            List of removed execution IDs.
        """
        records = await self.store.list(status=status)
        cutoff = (
            datetime.now(timezone.utc) - older_than
            if older_than is not None
            else None
        )
        removed: List[str] = []
        for rec in records:
            if cutoff is not None:
                try:
                    created = datetime.fromisoformat(rec.created_at)
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    if created >= cutoff:
                        continue
                except (ValueError, TypeError):
                    pass  # Can't parse — skip time filter
            await self.store.delete(rec.execution_id)
            removed.append(rec.execution_id)
            logger.info("Cleaned up execution %s", rec.execution_id)
        return removed


# ---------------------------------------------------------------------------
# Method 3 – supervised_run()
# ---------------------------------------------------------------------------

async def supervised_run(
    *,
    config_file: Optional[str] = None,
    config_dict: Optional[Dict] = None,
    hooks=None,
    input: Optional[Dict[str, Any]] = None,
    max_steps: int = 1000,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    hooks_factory: Optional[Callable] = None,
    backend: Optional[PersistenceBackend] = None,
    lock: Optional[ExecutionLock] = None,
    **machine_kwargs,
) -> Dict[str, Any]:
    """Run a machine with automatic checkpoint-based retry.

    A thin convenience wrapper around :class:`ExecutionManager` for the
    common case where you simply want resilient execution without managing
    an explicit manager instance.

    Example::

        result = await supervised_run(
            config_file="machine.yml",
            input={"query": "hello"},
            max_retries=3,
        )

    Args:
        config_file: Path to machine YAML/JSON config.
        config_dict: Inline machine config dict.
        hooks: MachineHooks instance.
        input: Input dict for the machine.
        max_steps: Max state transitions per attempt.
        max_retries: Retries after initial failure (default 3).
        retry_delay: Seconds between retries (default 1.0).
        hooks_factory: Callable returning fresh hooks per attempt.
        backend: Persistence backend (default: ``LocalFileBackend``).
        lock: Execution lock (default: inferred from backend).
        **machine_kwargs: Extra keyword arguments for FlatMachine.

    Returns:
        The final output dict from the machine.
    """
    manager = ExecutionManager(backend=backend, lock=lock)
    return await manager.run(
        config_file=config_file,
        config_dict=config_dict,
        hooks=hooks,
        input=input,
        max_steps=max_steps,
        max_retries=max_retries,
        retry_delay=retry_delay,
        hooks_factory=hooks_factory,
        **machine_kwargs,
    )


__all__ = [
    "ExecutionStatus",
    "ExecutionRecord",
    "ExecutionStore",
    "LocalExecutionStore",
    "MemoryExecutionStore",
    "ExecutionManager",
    "supervised_run",
]

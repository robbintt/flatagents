"""
Integration tests for FlatMachine lifecycle management.

Tests the three lifecycle abstractions:
1. ExecutionStore  — list, get, delete execution records
2. ExecutionManager — run with auto-retry, resume, cleanup
3. supervised_run() — convenience wrapper
"""

import asyncio
import os
import shutil
import pytest
from datetime import timedelta

from flatmachines import (
    FlatMachine,
    MachineHooks,
    LocalFileBackend,
    MemoryBackend,
)
from flatmachines.lifecycle import (
    ExecutionStatus,
    ExecutionRecord,
    ExecutionStore,
    LocalExecutionStore,
    MemoryExecutionStore,
    ExecutionManager,
    supervised_run,
)


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

class CounterHooks(MachineHooks):
    """Hooks that increment a counter and optionally crash."""

    def __init__(self, crash_at: int = None, crash_count: int = 1):
        self.crash_at = crash_at
        self.crash_count = crash_count
        self._crashes = 0

    def on_action(self, action_name, context):
        if action_name == "increment":
            context["count"] = context.get("count", 0) + 1
            if (
                self.crash_at
                and context["count"] == self.crash_at
                and self._crashes < self.crash_count
            ):
                self._crashes += 1
                raise RuntimeError(f"Simulated crash at count {self.crash_at}")
        return context


def get_counter_config():
    """Simple counter machine config with persistence enabled."""
    return {
        "spec": "flatmachine",
        "spec_version": "0.1.0",
        "data": {
            "name": "counter",
            "context": {"count": 0},
            "persistence": {"enabled": True, "backend": "local"},
            "states": {
                "start": {
                    "type": "initial",
                    "transitions": [{"to": "count_up"}],
                },
                "count_up": {
                    "action": "increment",
                    "transitions": [
                        {"condition": "context.count >= 5", "to": "end"},
                        {"to": "count_up"},
                    ],
                },
                "end": {
                    "type": "final",
                    "output": {"final_count": "{{ context.count }}"},
                },
            },
        },
    }


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up checkpoint and lock directories before and after tests."""
    for dir_name in [".checkpoints", ".locks"]:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    yield
    for dir_name in [".checkpoints", ".locks"]:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)


# ---------------------------------------------------------------------------
# ExecutionStore tests
# ---------------------------------------------------------------------------

class TestMemoryExecutionStore:
    """Tests for the in-memory execution store."""

    @pytest.mark.asyncio
    async def test_record_and_get(self):
        """Record a snapshot and retrieve its record."""
        from flatmachines.persistence import MachineSnapshot

        store = MemoryExecutionStore()
        snapshot = MachineSnapshot(
            execution_id="test-1",
            machine_name="counter",
            spec_version="0.1.0",
            current_state="end",
            context={"count": 5},
            step=6,
            event="machine_end",
            output={"final_count": 5},
        )
        await store.record(snapshot)

        rec = await store.get("test-1")
        assert rec is not None
        assert rec.execution_id == "test-1"
        assert rec.status == ExecutionStatus.COMPLETED
        assert rec.machine_name == "counter"
        assert rec.has_output is True

    @pytest.mark.asyncio
    async def test_get_missing(self):
        """Get returns None for unknown execution."""
        store = MemoryExecutionStore()
        assert await store.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self):
        """List filters by status."""
        from flatmachines.persistence import MachineSnapshot

        store = MemoryExecutionStore()
        # Completed
        await store.record(MachineSnapshot(
            execution_id="done-1", machine_name="counter",
            spec_version="0.1.0", current_state="end", context={},
            step=5, event="machine_end", output={"x": 1},
        ))
        # In-progress (not machine_end)
        await store.record(MachineSnapshot(
            execution_id="wip-1", machine_name="counter",
            spec_version="0.1.0", current_state="count_up", context={},
            step=2, event="state_enter",
        ))

        completed = await store.list(status=ExecutionStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].execution_id == "done-1"

    @pytest.mark.asyncio
    async def test_list_filter_by_machine_name(self):
        """List filters by machine name."""
        from flatmachines.persistence import MachineSnapshot

        store = MemoryExecutionStore()
        await store.record(MachineSnapshot(
            execution_id="a-1", machine_name="alpha",
            spec_version="0.1.0", current_state="end", context={},
            step=1, event="machine_end", output={},
        ))
        await store.record(MachineSnapshot(
            execution_id="b-1", machine_name="beta",
            spec_version="0.1.0", current_state="end", context={},
            step=1, event="machine_end", output={},
        ))

        alpha = await store.list(machine_name="alpha")
        assert len(alpha) == 1
        assert alpha[0].execution_id == "a-1"

    @pytest.mark.asyncio
    async def test_delete(self):
        """Delete removes a record."""
        from flatmachines.persistence import MachineSnapshot

        store = MemoryExecutionStore()
        await store.record(MachineSnapshot(
            execution_id="del-1", machine_name="counter",
            spec_version="0.1.0", current_state="end", context={},
            step=1, event="machine_end", output={},
        ))
        await store.delete("del-1")
        assert await store.get("del-1") is None


class TestLocalExecutionStore:
    """Tests for the file-based execution store."""

    @pytest.mark.asyncio
    async def test_record_and_get(self):
        """Record and retrieve from file-based store."""
        from flatmachines.persistence import MachineSnapshot

        store = LocalExecutionStore(base_dir=".checkpoints")
        snapshot = MachineSnapshot(
            execution_id="local-1", machine_name="counter",
            spec_version="0.1.0", current_state="end", context={},
            step=5, event="machine_end", output={"final_count": 5},
        )
        await store.record(snapshot)

        rec = await store.get("local-1")
        assert rec is not None
        assert rec.execution_id == "local-1"
        assert rec.status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self):
        """Index survives store re-instantiation."""
        from flatmachines.persistence import MachineSnapshot

        store1 = LocalExecutionStore(base_dir=".checkpoints")
        await store1.record(MachineSnapshot(
            execution_id="persist-1", machine_name="counter",
            spec_version="0.1.0", current_state="end", context={},
            step=5, event="machine_end", output={},
        ))

        # New instance, same directory
        store2 = LocalExecutionStore(base_dir=".checkpoints")
        rec = await store2.get("persist-1")
        assert rec is not None
        assert rec.execution_id == "persist-1"

    @pytest.mark.asyncio
    async def test_delete_removes_record_and_directory(self):
        """Delete removes index entry and checkpoint directory."""
        from flatmachines.persistence import MachineSnapshot

        store = LocalExecutionStore(base_dir=".checkpoints")
        await store.record(MachineSnapshot(
            execution_id="del-local-1", machine_name="counter",
            spec_version="0.1.0", current_state="end", context={},
            step=1, event="machine_end", output={},
        ))

        # Create a checkpoint directory to simulate real data
        exec_dir = store._base_dir / "del-local-1"
        exec_dir.mkdir(parents=True, exist_ok=True)
        (exec_dir / "step_000001_machine_end.json").write_text("{}")

        await store.delete("del-local-1")
        assert await store.get("del-local-1") is None
        assert not exec_dir.exists()


# ---------------------------------------------------------------------------
# ExecutionManager tests
# ---------------------------------------------------------------------------

class TestExecutionManager:
    """Tests for the central lifecycle manager."""

    @pytest.mark.asyncio
    async def test_run_no_retry(self):
        """Simple run completes without retry."""
        config = get_counter_config()
        manager = ExecutionManager(
            backend=LocalFileBackend(),
            store=MemoryExecutionStore(),
        )
        result = await manager.run(
            config_dict=config, hooks=CounterHooks(), input={},
        )
        assert int(result["final_count"]) == 5

    @pytest.mark.asyncio
    async def test_run_with_retry_recovers(self):
        """Run auto-retries and resumes from checkpoint on crash."""
        config = get_counter_config()
        manager = ExecutionManager(
            backend=LocalFileBackend(),
            store=MemoryExecutionStore(),
        )
        # Shared hooks instance: crash_count=1 means after the first crash,
        # the instance remembers and won't crash again on retry.
        hooks = CounterHooks(crash_at=3, crash_count=1)
        result = await manager.run(
            config_dict=config,
            hooks=hooks,
            input={},
            max_retries=2,
            retry_delay=0.01,
        )
        assert int(result["final_count"]) == 5

    @pytest.mark.asyncio
    async def test_run_exhausts_retries(self):
        """All retries exhausted raises the last error."""
        config = get_counter_config()
        manager = ExecutionManager(
            backend=LocalFileBackend(),
            store=MemoryExecutionStore(),
        )
        with pytest.raises(RuntimeError, match="Simulated crash"):
            await manager.run(
                config_dict=config,
                # crash_count=10 means it always crashes
                hooks_factory=lambda: CounterHooks(crash_at=3, crash_count=10),
                input={},
                max_retries=1,
                retry_delay=0.01,
            )

    @pytest.mark.asyncio
    async def test_list_executions_after_run(self):
        """Completed executions appear in the store."""
        config = get_counter_config()
        store = MemoryExecutionStore()
        manager = ExecutionManager(
            backend=LocalFileBackend(), store=store,
        )
        await manager.run(config_dict=config, hooks=CounterHooks(), input={})

        records = await manager.list_executions()
        assert len(records) == 1
        assert records[0].status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_resume_from_manager(self):
        """Resume a crashed execution via the manager."""
        config = get_counter_config()
        backend = LocalFileBackend()
        store = MemoryExecutionStore()

        # Run 1: crash
        machine = FlatMachine(
            config_dict=config,
            hooks=CounterHooks(crash_at=3),
            persistence=backend,
        )
        execution_id = machine.execution_id
        with pytest.raises(RuntimeError):
            await machine.execute()

        # Resume via manager
        manager = ExecutionManager(backend=backend, store=store)
        result = await manager.resume(
            execution_id, config_dict=config, hooks=CounterHooks(),
        )
        assert int(result["final_count"]) == 5

        # Store should record it
        rec = await store.get(execution_id)
        assert rec is not None
        assert rec.status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cleanup_by_status(self):
        """Cleanup removes completed executions."""
        from flatmachines.persistence import MachineSnapshot

        store = MemoryExecutionStore()
        manager = ExecutionManager(
            backend=MemoryBackend(), store=store,
        )
        # Manually add records
        await store.record(MachineSnapshot(
            execution_id="old-1", machine_name="counter",
            spec_version="0.1.0", current_state="end", context={},
            step=1, event="machine_end", output={},
            created_at="2020-01-01T00:00:00+00:00",
        ))
        await store.record(MachineSnapshot(
            execution_id="old-2", machine_name="counter",
            spec_version="0.1.0", current_state="count_up", context={},
            step=2, event="state_enter",
            created_at="2020-01-01T00:00:00+00:00",
        ))

        # Cleanup only completed
        removed = await manager.cleanup(status=ExecutionStatus.COMPLETED)
        assert "old-1" in removed
        assert "old-2" not in removed

    @pytest.mark.asyncio
    async def test_cleanup_by_age(self):
        """Cleanup removes old executions."""
        from flatmachines.persistence import MachineSnapshot

        store = MemoryExecutionStore()
        manager = ExecutionManager(
            backend=MemoryBackend(), store=store,
        )
        await store.record(MachineSnapshot(
            execution_id="ancient", machine_name="counter",
            spec_version="0.1.0", current_state="end", context={},
            step=1, event="machine_end", output={},
            created_at="2020-01-01T00:00:00+00:00",
        ))

        removed = await manager.cleanup(older_than=timedelta(days=1))
        assert "ancient" in removed


# ---------------------------------------------------------------------------
# supervised_run() tests
# ---------------------------------------------------------------------------

class TestSupervisedRun:
    """Tests for the supervised_run convenience function."""

    @pytest.mark.asyncio
    async def test_supervised_run_success(self):
        """supervised_run completes a simple machine."""
        config = get_counter_config()
        result = await supervised_run(
            config_dict=config, hooks=CounterHooks(), input={},
        )
        assert int(result["final_count"]) == 5

    @pytest.mark.asyncio
    async def test_supervised_run_with_retry(self):
        """supervised_run retries on transient failure."""
        config = get_counter_config()
        # Shared hooks instance: crash_count=1 means first crash is
        # remembered, so the retry succeeds.
        hooks = CounterHooks(crash_at=3, crash_count=1)
        result = await supervised_run(
            config_dict=config,
            hooks=hooks,
            input={},
            max_retries=2,
            retry_delay=0.01,
        )
        assert int(result["final_count"]) == 5

    @pytest.mark.asyncio
    async def test_supervised_run_with_memory_backend(self):
        """supervised_run works with an explicit memory backend."""
        config = get_counter_config()
        config["data"]["persistence"]["backend"] = "memory"
        result = await supervised_run(
            config_dict=config,
            hooks=CounterHooks(),
            input={},
            backend=MemoryBackend(),
        )
        assert int(result["final_count"]) == 5

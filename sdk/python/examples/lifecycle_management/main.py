"""
Lifecycle Management Example

Demonstrates the three lifecycle management methods:

1. ExecutionStore     — Track and query executions
2. ExecutionManager   — Run/resume/list/cleanup with auto-retry
3. supervised_run()   — Simple one-shot resilient execution

Run:
    pip install flatmachines
    python main.py
"""

import asyncio
import os
import shutil
from datetime import timedelta

from flatmachines import (
    FlatMachine,
    MachineHooks,
    LocalFileBackend,
    MemoryBackend,
    setup_logging,
)
from flatmachines.lifecycle import (
    ExecutionStatus,
    ExecutionManager,
    LocalExecutionStore,
    MemoryExecutionStore,
    supervised_run,
)


# ---------------------------------------------------------------------------
# Hooks for the data pipeline machine
# ---------------------------------------------------------------------------

class PipelineHooks(MachineHooks):
    """Simulates a data pipeline that may encounter transient failures."""

    def __init__(self, fail_at: int = None, fail_count: int = 1):
        self.fail_at = fail_at
        self.fail_count = fail_count
        self._failures = 0

    def on_action(self, action_name, context):
        if action_name == "process_item":
            context["items_processed"] = context.get("items_processed", 0) + 1
            item_num = context["items_processed"]

            # Simulate a transient failure
            if (
                self.fail_at
                and item_num == self.fail_at
                and self._failures < self.fail_count
            ):
                self._failures += 1
                raise RuntimeError(
                    f"Transient failure processing item {item_num}"
                )

            print(f"  ✅ Processed item {item_num}")

        elif action_name == "build_summary":
            total = context.get("items_processed", 0)
            context["summary"] = f"Pipeline completed: {total} items processed"
            print(f"  📊 {context['summary']}")

        return context


# ---------------------------------------------------------------------------
# Example 1: supervised_run() — Simple resilient execution
# ---------------------------------------------------------------------------

async def example_supervised_run():
    """Use supervised_run() for simple fire-and-forget resilient execution."""
    print("\n" + "=" * 60)
    print("Example 1: supervised_run() — Simple Resilient Execution")
    print("=" * 60)

    config = {
        "spec": "flatmachine",
        "spec_version": "1.1.1",
        "data": {
            "name": "simple_pipeline",
            "context": {"items_processed": 0, "errors": 0},
            "persistence": {"enabled": True, "backend": "memory"},
            "states": {
                "start": {"type": "initial", "transitions": [{"to": "process"}]},
                "process": {
                    "action": "process_item",
                    "transitions": [
                        {"condition": "context.items_processed >= 3", "to": "end"},
                        {"to": "process"},
                    ],
                },
                "end": {
                    "type": "final",
                    "output": {"total": "{{ context.items_processed }}"},
                },
            },
        },
    }

    # The pipeline crashes on item 2, but supervised_run retries automatically.
    # Using a shared hooks instance so the crash counter persists across retries.
    hooks = PipelineHooks(fail_at=2, fail_count=1)
    result = await supervised_run(
        config_dict=config,
        hooks=hooks,
        input={},
        max_retries=3,
        retry_delay=0.1,
        backend=MemoryBackend(),
    )

    print(f"\n  Result: {result}")
    print("  ✅ supervised_run() handled the transient failure automatically!\n")


# ---------------------------------------------------------------------------
# Example 2: ExecutionManager — Full lifecycle management
# ---------------------------------------------------------------------------

async def example_execution_manager():
    """Use ExecutionManager for complete lifecycle control."""
    print("\n" + "=" * 60)
    print("Example 2: ExecutionManager — Full Lifecycle Management")
    print("=" * 60)

    config = {
        "spec": "flatmachine",
        "spec_version": "1.1.1",
        "data": {
            "name": "managed_pipeline",
            "context": {"items_processed": 0, "errors": 0},
            "persistence": {"enabled": True, "backend": "local"},
            "states": {
                "start": {"type": "initial", "transitions": [{"to": "process"}]},
                "process": {
                    "action": "process_item",
                    "transitions": [
                        {"condition": "context.items_processed >= 5", "to": "summarize"},
                        {"to": "process"},
                    ],
                },
                "summarize": {
                    "action": "build_summary",
                    "transitions": [{"to": "end"}],
                },
                "end": {
                    "type": "final",
                    "output": {
                        "total": "{{ context.items_processed }}",
                        "summary": "{{ context.summary }}",
                    },
                },
            },
        },
    }

    backend = LocalFileBackend()
    store = LocalExecutionStore()
    manager = ExecutionManager(backend=backend, store=store)

    # --- Run with auto-retry ---
    print("\n  📌 Running pipeline with auto-retry...")
    hooks = PipelineHooks(fail_at=3, fail_count=1)
    result = await manager.run(
        config_dict=config,
        hooks=hooks,
        input={},
        max_retries=2,
        retry_delay=0.1,
    )
    print(f"\n  Result: {result}")

    # --- List all executions ---
    print("\n  📌 Listing all executions...")
    records = await manager.list_executions()
    for rec in records:
        print(
            f"    ID={rec.execution_id[:12]}...  "
            f"status={rec.status.value}  "
            f"machine={rec.machine_name}  "
            f"step={rec.step}"
        )

    # --- Run a second pipeline ---
    print("\n  📌 Running a second pipeline (no failures)...")
    result2 = await manager.run(
        config_dict=config,
        hooks=PipelineHooks(),
        input={},
    )
    print(f"  Result: {result2}")

    # --- List completed executions ---
    print("\n  📌 Listing completed executions...")
    completed = await manager.list_executions(status=ExecutionStatus.COMPLETED)
    print(f"    Found {len(completed)} completed execution(s)")

    # --- Cleanup old executions ---
    print("\n  📌 Cleaning up executions older than 1 second...")
    await asyncio.sleep(1.1)  # Wait so they become "old"
    removed = await manager.cleanup(older_than=timedelta(seconds=1))
    print(f"    Removed {len(removed)} execution(s)")

    remaining = await manager.list_executions()
    print(f"    {len(remaining)} execution(s) remaining")
    print()


# ---------------------------------------------------------------------------
# Example 3: ExecutionStore — Direct execution tracking
# ---------------------------------------------------------------------------

async def example_execution_store():
    """Use ExecutionStore directly for custom execution tracking."""
    print("\n" + "=" * 60)
    print("Example 3: ExecutionStore — Direct Execution Tracking")
    print("=" * 60)

    config = {
        "spec": "flatmachine",
        "spec_version": "1.1.1",
        "data": {
            "name": "tracked_pipeline",
            "context": {"items_processed": 0},
            "persistence": {"enabled": True, "backend": "local"},
            "states": {
                "start": {"type": "initial", "transitions": [{"to": "process"}]},
                "process": {
                    "action": "process_item",
                    "transitions": [
                        {"condition": "context.items_processed >= 3", "to": "end"},
                        {"to": "process"},
                    ],
                },
                "end": {
                    "type": "final",
                    "output": {"total": "{{ context.items_processed }}"},
                },
            },
        },
    }

    store = MemoryExecutionStore()
    backend = LocalFileBackend()

    # Run a machine and manually track it
    machine = FlatMachine(config_dict=config, hooks=PipelineHooks(), persistence=backend)
    execution_id = machine.execution_id
    print(f"\n  📌 Running machine {execution_id[:12]}...")

    result = await machine.execute(input={})
    print(f"  Result: {result}")

    # Load the latest snapshot and record it
    from flatmachines.persistence import CheckpointManager

    snapshot = await CheckpointManager(backend, execution_id).load_latest()
    if snapshot:
        await store.record(snapshot)

    # Query the store
    print("\n  📌 Querying execution store...")
    rec = await store.get(execution_id)
    if rec:
        print(f"    Execution: {rec.execution_id[:12]}...")
        print(f"    Status:    {rec.status.value}")
        print(f"    Machine:   {rec.machine_name}")
        print(f"    Step:      {rec.step}")
        print(f"    Has output: {rec.has_output}")

    # List all
    all_records = await store.list()
    print(f"\n  📌 Total executions in store: {len(all_records)}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    setup_logging(level="WARNING")

    print("\n🚀 FlatMachines Lifecycle Management Examples")
    print("=" * 60)

    await example_supervised_run()
    await example_execution_manager()
    await example_execution_store()

    print("✅ All examples completed successfully!")

    # Cleanup
    for d in [".checkpoints", ".locks"]:
        if os.path.exists(d):
            shutil.rmtree(d)


if __name__ == "__main__":
    asyncio.run(main())

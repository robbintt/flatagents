"""
Integration test for distributed backends.

This single test verifies that all distributed backend imports work
and basic operations can be performed.
"""

import pytest
import tempfile
import os


@pytest.mark.asyncio
async def test_distributed_backends_basic():
    """Verify all imports work and basic operations succeed."""
    # Test imports
    from flatagents import (
        WorkerRegistration,
        WorkerRecord,
        WorkerFilter,
        WorkItem,
        RegistrationBackend,
        WorkBackend,
        WorkPool,
        MemoryRegistrationBackend,
        MemoryWorkBackend,
        SQLiteRegistrationBackend,
        SQLiteWorkBackend,
        create_registration_backend,
        create_work_backend,
    )
    
    # Test factory functions
    mem_reg = create_registration_backend("memory")
    mem_work = create_work_backend("memory")
    assert mem_reg is not None
    assert mem_work is not None
    
    # Test memory registration backend
    worker = WorkerRegistration(worker_id="test-worker-1", host="localhost", pid=12345)
    record = await mem_reg.register(worker)
    assert record.worker_id == "test-worker-1"
    assert record.status == "active"
    
    # Test heartbeat
    await mem_reg.heartbeat("test-worker-1")
    
    # Test memory work backend
    pool = mem_work.pool("test-pool")
    item_id = await pool.push({"task": "test-task"})
    assert item_id is not None
    
    # Test claim
    claimed = await pool.claim("test-worker-1")
    assert claimed is not None
    assert claimed.data == {"task": "test-task"}
    
    # Test complete
    await pool.complete(claimed.id)
    
    # Verify pool is empty
    size = await pool.size()
    assert size == 0
    
    # Test SQLite backends with temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite")
        
        sqlite_reg = create_registration_backend("sqlite", db_path=db_path)
        sqlite_work = create_work_backend("sqlite", db_path=db_path)
        
        # Register worker
        worker2 = WorkerRegistration(worker_id="sqlite-worker", host="localhost")
        record2 = await sqlite_reg.register(worker2)
        assert record2.worker_id == "sqlite-worker"
        
        # Push and claim work
        pool2 = sqlite_work.pool("sqlite-pool")
        item_id2 = await pool2.push({"data": "test"}, {"max_retries": 5})
        claimed2 = await pool2.claim("sqlite-worker")
        assert claimed2 is not None
        assert claimed2.max_retries == 5
        
        # Complete and verify
        await pool2.complete(claimed2.id)
        assert await pool2.size() == 0
    
    print("✅ All distributed backend tests passed!")


@pytest.mark.asyncio
async def test_subprocess_support_imports():
    """Verify subprocess support imports work."""
    from flatagents import SubprocessInvoker, launch_machine
    
    # Verify classes/functions exist
    assert SubprocessInvoker is not None
    assert launch_machine is not None
    assert callable(launch_machine)
    
    # Verify SubprocessInvoker can be instantiated
    invoker = SubprocessInvoker(working_dir="/tmp")
    assert invoker.working_dir == "/tmp"
    
    print("✅ Subprocess support imports verified!")

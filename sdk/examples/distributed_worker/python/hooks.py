"""
Custom hooks for the distributed worker example.

Provides action handlers for:
- get_pool_state: Query queue depth and active workers
- claim_job: Atomically claim next job from pool
- complete_job: Mark job as done
- fail_job: Mark job as failed (will retry or poison)
- register_worker: Register worker with lifecycle backend
- list_stale_workers: Find workers past heartbeat threshold
- reap_worker: Mark worker lost and release their jobs
"""

import os
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

from flatagents import (
    MachineHooks,
    SQLiteRegistrationBackend,
    SQLiteWorkBackend,
    WorkerRegistration,
)


# Default database path (relative to example directory)
DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "worker.sqlite")


class DistributedWorkerHooks(MachineHooks):
    """
    Hooks for distributed worker machines.
    
    All actions interact with the shared SQLite database for
    work distribution and worker lifecycle management.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("WORKER_DB_PATH", DEFAULT_DB_PATH)
        
        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize backends
        self._registration = SQLiteRegistrationBackend(db_path=self.db_path)
        self._work = SQLiteWorkBackend(db_path=self.db_path)
    
    async def on_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Route action names to handler methods."""
        
        handlers = {
            "get_pool_state": self._get_pool_state,
            "claim_job": self._claim_job,
            "complete_job": self._complete_job,
            "fail_job": self._fail_job,
            "register_worker": self._register_worker,
            "deregister_worker": self._deregister_worker,
            "heartbeat": self._heartbeat,
            "list_stale_workers": self._list_stale_workers,
            "reap_worker": self._reap_worker,
            "echo_delay": self._echo_delay,
        }
        
        handler = handlers.get(action)
        if handler:
            return await handler(context)
        
        # Fall through to default behavior
        return context
    
    # -------------------------------------------------------------------------
    # Pool State Actions (for parallelization checker)
    # -------------------------------------------------------------------------
    
    async def _get_pool_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get current pool depth and active worker count."""
        pool_id = context.get("pool_id", "default")
        
        pool = self._work.pool(pool_id)
        workers = await self._registration.list({"status": "active"})
        
        return {
            "queue_depth": await pool.size(),
            "active_workers": len(workers),
        }
    
    # -------------------------------------------------------------------------
    # Job Actions (for job workers)
    # -------------------------------------------------------------------------
    
    async def _claim_job(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Atomically claim the next available job."""
        pool_id = context.get("pool_id", "default")
        worker_id = context.get("worker_id")
        
        if not worker_id:
            raise ValueError("worker_id is required for claim_job")
        
        pool = self._work.pool(pool_id)
        item = await pool.claim(worker_id)
        
        if item:
            return {
                "job": item.data,
                "job_id": item.id,
            }
        else:
            return {
                "job": None,
                "job_id": None,
            }
    
    async def _complete_job(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mark job as successfully completed."""
        pool_id = context.get("pool_id", "default")
        job_id = context.get("job_id")
        result = context.get("result")
        
        if not job_id:
            raise ValueError("job_id is required for complete_job")
        
        pool = self._work.pool(pool_id)
        await pool.complete(job_id, result)
        
        return context
    
    async def _fail_job(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mark job as failed. Will retry or poison based on attempts."""
        pool_id = context.get("pool_id", "default")
        job_id = context.get("job_id")
        error = context.get("error")
        
        if not job_id:
            raise ValueError("job_id is required for fail_job")
        
        pool = self._work.pool(pool_id)
        await pool.fail(job_id, error)
        
        return context
    
    # -------------------------------------------------------------------------
    # Worker Lifecycle Actions
    # -------------------------------------------------------------------------
    
    async def _register_worker(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new worker."""
        import socket
        import os
        
        worker_id = context.get("worker_id")
        if not worker_id:
            raise ValueError("worker_id is required for register_worker")
        
        registration = WorkerRegistration(
            worker_id=worker_id,
            host=socket.gethostname(),
            pid=os.getpid(),
            capabilities=context.get("capabilities", []),
        )
        
        record = await self._registration.register(registration)
        
        return {
            "worker_id": record.worker_id,
            "status": record.status,
            "registered_at": record.started_at,
        }
    
    async def _deregister_worker(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mark worker as terminated (clean shutdown)."""
        worker_id = context.get("worker_id")
        if not worker_id:
            raise ValueError("worker_id is required for deregister_worker")
        
        await self._registration.update_status(worker_id, "terminated")
        
        return context
    
    async def _heartbeat(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Send heartbeat for a worker."""
        worker_id = context.get("worker_id")
        if not worker_id:
            raise ValueError("worker_id is required for heartbeat")
        
        await self._registration.heartbeat(worker_id)
        
        return context
    
    # -------------------------------------------------------------------------
    # Reaper Actions
    # -------------------------------------------------------------------------
    
    async def _list_stale_workers(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Find workers that have missed heartbeat threshold."""
        threshold = context.get("stale_threshold_seconds", 60)
        
        workers = await self._registration.list({
            "status": "active",
            "stale_threshold_seconds": threshold,
        })
        
        return {
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "last_heartbeat": w.last_heartbeat,
                    "host": w.host,
                }
                for w in workers
            ],
        }
    
    async def _reap_worker(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mark worker as lost and release their claimed jobs."""
        worker = context.get("worker")
        pool_id = context.get("pool_id", "default")
        
        if not worker:
            raise ValueError("worker is required for reap_worker")
        
        worker_id = worker.get("worker_id")
        
        # Mark as lost
        await self._registration.update_status(worker_id, "lost")
        
        # Release any jobs claimed by this worker
        pool = self._work.pool(pool_id)
        released = await pool.release_by_worker(worker_id)
        
        return {
            "worker_id": worker_id,
            "jobs_released": released,
        }
    
    # -------------------------------------------------------------------------
    # Echo Processor Actions
    # -------------------------------------------------------------------------
    
    async def _echo_delay(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate processing with a delay (for echo_processor)."""
        delay = context.get("delay_seconds", 1)
        
        # Actually wait
        await asyncio.sleep(delay)
        
        return {
            "processed": True,
            "delay_applied": delay,
        }


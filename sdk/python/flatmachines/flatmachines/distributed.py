"""
Distributed backends for FlatAgents worker orchestration.

This module provides backends for work distribution and worker lifecycle management
across ephemeral machines. These backends enable decentralized autoscaling patterns
where workers claim jobs, process them, and exit.

Backends:
- RegistrationBackend: Worker lifecycle (register, heartbeat, status)
- WorkBackend: Work distribution via named pools with atomic claiming

Implementations:
- SQLite: Single-file database, suitable for local/container deployments
- Memory: In-memory storage, suitable for testing and single-process scenarios
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================

@dataclass
class WorkerRegistration:
    """Information for registering a new worker."""
    worker_id: str
    host: Optional[str] = None
    pid: Optional[int] = None
    capabilities: Optional[List[str]] = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass  
class WorkerRecord:
    """Complete worker record including status and heartbeat."""
    worker_id: str
    status: str  # "active", "terminating", "terminated", "lost"
    last_heartbeat: str
    host: Optional[str] = None
    pid: Optional[int] = None
    capabilities: Optional[List[str]] = None
    started_at: Optional[str] = None
    current_task_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerRecord":
        return cls(**data)


@dataclass
class WorkerFilter:
    """Filter criteria for listing workers."""
    status: Optional[str] = None
    capability: Optional[str] = None
    stale_threshold_seconds: Optional[int] = None


@dataclass
class WorkItem:
    """A claimed work item from a pool."""
    id: str
    data: Any
    claimed_by: Optional[str] = None
    attempts: int = 0
    max_retries: int = 3
    status: str = "pending"  # "pending", "claimed", "completed", "failed", "poisoned"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    claimed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Registration Backend Protocol & Implementations
# =============================================================================

@runtime_checkable
class RegistrationBackend(Protocol):
    """
    Protocol for worker lifecycle management.
    
    Workers register themselves, send periodic heartbeats, and update status.
    The backend tracks worker liveness for stale detection.
    """
    
    async def register(self, worker: WorkerRegistration) -> WorkerRecord:
        """Register a new worker.
        
        Args:
            worker: Worker registration information
            
        Returns:
            Complete worker record with initial status
        """
        ...
    
    async def heartbeat(
        self, 
        worker_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update worker's last heartbeat timestamp.
        
        Args:
            worker_id: ID of the worker
            metadata: Optional metadata to update
        """
        ...
    
    async def update_status(self, worker_id: str, status: str) -> None:
        """Update worker status.
        
        Args:
            worker_id: ID of the worker
            status: New status (active, terminating, terminated, lost)
        """
        ...
    
    async def get(self, worker_id: str) -> Optional[WorkerRecord]:
        """Get worker by ID.
        
        Args:
            worker_id: ID of the worker
            
        Returns:
            Worker record or None if not found
        """
        ...
    
    async def list(self, filter: Optional[WorkerFilter] = None) -> List[WorkerRecord]:
        """List workers matching filter.
        
        Args:
            filter: Optional filter criteria
            
        Returns:
            List of matching worker records
        """
        ...


class MemoryRegistrationBackend:
    """In-memory registration backend for testing and single-process scenarios."""
    
    def __init__(self):
        self._workers: Dict[str, WorkerRecord] = {}
        self._lock = asyncio.Lock()
    
    async def register(self, worker: WorkerRegistration) -> WorkerRecord:
        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            record = WorkerRecord(
                worker_id=worker.worker_id,
                status="active",
                last_heartbeat=now,
                host=worker.host,
                pid=worker.pid,
                capabilities=worker.capabilities,
                started_at=worker.started_at,
            )
            self._workers[worker.worker_id] = record
            logger.debug(f"RegistrationBackend: registered worker {worker.worker_id}")
            return record
    
    async def heartbeat(
        self, 
        worker_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        async with self._lock:
            if worker_id not in self._workers:
                raise KeyError(f"Worker {worker_id} not found")
            record = self._workers[worker_id]
            record.last_heartbeat = datetime.now(timezone.utc).isoformat()
            if metadata:
                record.metadata = {**(record.metadata or {}), **metadata}
            logger.debug(f"RegistrationBackend: heartbeat for {worker_id}")
    
    async def update_status(self, worker_id: str, status: str) -> None:
        async with self._lock:
            if worker_id not in self._workers:
                raise KeyError(f"Worker {worker_id} not found")
            self._workers[worker_id].status = status
            logger.debug(f"RegistrationBackend: {worker_id} status -> {status}")
    
    async def get(self, worker_id: str) -> Optional[WorkerRecord]:
        return self._workers.get(worker_id)
    
    async def list(self, filter: Optional[WorkerFilter] = None) -> List[WorkerRecord]:
        workers = list(self._workers.values())
        
        if filter:
            if filter.status:
                workers = [w for w in workers if w.status == filter.status]
            if filter.capability:
                workers = [
                    w for w in workers 
                    if w.capabilities and filter.capability in w.capabilities
                ]
            if filter.stale_threshold_seconds:
                cutoff = datetime.now(timezone.utc) - timedelta(
                    seconds=filter.stale_threshold_seconds
                )
                workers = [
                    w for w in workers
                    if datetime.fromisoformat(w.last_heartbeat.replace('Z', '+00:00')) < cutoff
                ]
        
        return workers


class SQLiteRegistrationBackend:
    """SQLite-based registration backend for local/container deployments."""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS worker_registry (
        worker_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'active',
        last_heartbeat TEXT NOT NULL,
        host TEXT,
        pid INTEGER,
        capabilities TEXT,  -- JSON array
        started_at TEXT,
        current_task_id TEXT,
        metadata TEXT  -- JSON object
    );
    
    CREATE INDEX IF NOT EXISTS idx_worker_status ON worker_registry(status);
    CREATE INDEX IF NOT EXISTS idx_worker_heartbeat ON worker_registry(last_heartbeat);
    """
    
    def __init__(self, db_path: str = "workers.sqlite"):
        self.db_path = Path(db_path)
        self._lock = asyncio.Lock()
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _row_to_record(self, row: sqlite3.Row) -> WorkerRecord:
        capabilities = json.loads(row["capabilities"]) if row["capabilities"] else None
        metadata = json.loads(row["metadata"]) if row["metadata"] else None
        return WorkerRecord(
            worker_id=row["worker_id"],
            status=row["status"],
            last_heartbeat=row["last_heartbeat"],
            host=row["host"],
            pid=row["pid"],
            capabilities=capabilities,
            started_at=row["started_at"],
            current_task_id=row["current_task_id"],
            metadata=metadata,
        )
    
    async def register(self, worker: WorkerRegistration) -> WorkerRecord:
        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            capabilities_json = json.dumps(worker.capabilities) if worker.capabilities else None
            
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO worker_registry 
                    (worker_id, status, last_heartbeat, host, pid, capabilities, started_at)
                    VALUES (?, 'active', ?, ?, ?, ?, ?)
                    """,
                    (worker.worker_id, now, worker.host, worker.pid, 
                     capabilities_json, worker.started_at)
                )
            
            logger.debug(f"RegistrationBackend: registered worker {worker.worker_id}")
            return WorkerRecord(
                worker_id=worker.worker_id,
                status="active",
                last_heartbeat=now,
                host=worker.host,
                pid=worker.pid,
                capabilities=worker.capabilities,
                started_at=worker.started_at,
            )
    
    async def heartbeat(
        self, 
        worker_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            with self._get_conn() as conn:
                if metadata:
                    # Merge metadata
                    cursor = conn.execute(
                        "SELECT metadata FROM worker_registry WHERE worker_id = ?",
                        (worker_id,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise KeyError(f"Worker {worker_id} not found")
                    existing = json.loads(row["metadata"]) if row["metadata"] else {}
                    merged = {**existing, **metadata}
                    conn.execute(
                        """
                        UPDATE worker_registry 
                        SET last_heartbeat = ?, metadata = ?
                        WHERE worker_id = ?
                        """,
                        (now, json.dumps(merged), worker_id)
                    )
                else:
                    result = conn.execute(
                        "UPDATE worker_registry SET last_heartbeat = ? WHERE worker_id = ?",
                        (now, worker_id)
                    )
                    if result.rowcount == 0:
                        raise KeyError(f"Worker {worker_id} not found")
            
            logger.debug(f"RegistrationBackend: heartbeat for {worker_id}")
    
    async def update_status(self, worker_id: str, status: str) -> None:
        async with self._lock:
            with self._get_conn() as conn:
                result = conn.execute(
                    "UPDATE worker_registry SET status = ? WHERE worker_id = ?",
                    (status, worker_id)
                )
                if result.rowcount == 0:
                    raise KeyError(f"Worker {worker_id} not found")
            
            logger.debug(f"RegistrationBackend: {worker_id} status -> {status}")
    
    async def get(self, worker_id: str) -> Optional[WorkerRecord]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM worker_registry WHERE worker_id = ?",
                (worker_id,)
            )
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    async def list(self, filter: Optional[WorkerFilter] = None) -> List[WorkerRecord]:
        query = "SELECT * FROM worker_registry WHERE 1=1"
        params: List[Any] = []
        
        if filter:
            if filter.status:
                query += " AND status = ?"
                params.append(filter.status)
            if filter.capability:
                # JSON contains check
                query += " AND capabilities LIKE ?"
                params.append(f'%"{filter.capability}"%')
            if filter.stale_threshold_seconds:
                cutoff = (
                    datetime.now(timezone.utc) - 
                    timedelta(seconds=filter.stale_threshold_seconds)
                ).isoformat()
                query += " AND last_heartbeat < ?"
                params.append(cutoff)
        
        with self._get_conn() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_record(row) for row in cursor.fetchall()]


# =============================================================================
# Work Backend Protocol & Implementations
# =============================================================================

@runtime_checkable
class WorkPool(Protocol):
    """
    Protocol for a named work pool with atomic claiming.
    
    Workers claim items atomically, process them, and mark complete or failed.
    """
    
    async def push(self, item: Any, options: Optional[Dict[str, Any]] = None) -> str:
        """Add work item to pool.
        
        Args:
            item: Work item data (must be JSON-serializable)
            options: Optional settings like max_retries
            
        Returns:
            Generated item ID
        """
        ...
    
    async def claim(self, worker_id: str) -> Optional[WorkItem]:
        """Atomically claim next available item.
        
        Args:
            worker_id: ID of the claiming worker
            
        Returns:
            Claimed work item or None if pool is empty
        """
        ...
    
    async def complete(self, item_id: str, result: Optional[Any] = None) -> None:
        """Mark item as completed and remove from pool.
        
        Args:
            item_id: ID of the work item
            result: Optional result data
        """
        ...
    
    async def fail(self, item_id: str, error: Optional[str] = None) -> None:
        """Mark item as failed. Returns to pool for retry or marks as poisoned.
        
        Args:
            item_id: ID of the work item
            error: Optional error message
        """
        ...
    
    async def size(self) -> int:
        """Get number of unclaimed items in pool."""
        ...
    
    async def release_by_worker(self, worker_id: str) -> int:
        """Release all items claimed by a worker (for stale worker cleanup).
        
        Args:
            worker_id: ID of the worker whose items to release
            
        Returns:
            Number of items released
        """
        ...


@runtime_checkable
class WorkBackend(Protocol):
    """Protocol for work distribution across named pools."""
    
    def pool(self, name: str) -> WorkPool:
        """Get a named work pool.
        
        Args:
            name: Pool name (e.g., "paper_analysis", "image_processing")
            
        Returns:
            WorkPool instance for the named pool
        """
        ...


class MemoryWorkPool:
    """In-memory work pool implementation."""
    
    def __init__(self, name: str):
        self.name = name
        self._items: Dict[str, WorkItem] = {}
        self._lock = asyncio.Lock()
    
    async def push(self, item: Any, options: Optional[Dict[str, Any]] = None) -> str:
        async with self._lock:
            item_id = str(uuid.uuid4())
            max_retries = (options or {}).get("max_retries", 3)
            work_item = WorkItem(
                id=item_id,
                data=item,
                max_retries=max_retries,
            )
            self._items[item_id] = work_item
            logger.debug(f"WorkPool[{self.name}]: pushed item {item_id}")
            return item_id
    
    async def claim(self, worker_id: str) -> Optional[WorkItem]:
        async with self._lock:
            # Find first pending item
            for item in self._items.values():
                if item.status == "pending":
                    item.status = "claimed"
                    item.claimed_by = worker_id
                    item.claimed_at = datetime.now(timezone.utc).isoformat()
                    item.attempts += 1
                    logger.debug(f"WorkPool[{self.name}]: {worker_id} claimed {item.id}")
                    return item
            return None
    
    async def complete(self, item_id: str, result: Optional[Any] = None) -> None:
        async with self._lock:
            if item_id not in self._items:
                raise KeyError(f"Work item {item_id} not found")
            # Remove completed items
            del self._items[item_id]
            logger.debug(f"WorkPool[{self.name}]: completed {item_id}")
    
    async def fail(self, item_id: str, error: Optional[str] = None) -> None:
        async with self._lock:
            if item_id not in self._items:
                raise KeyError(f"Work item {item_id} not found")
            item = self._items[item_id]
            
            if item.attempts >= item.max_retries:
                item.status = "poisoned"
                logger.warning(
                    f"WorkPool[{self.name}]: {item_id} poisoned after {item.attempts} attempts"
                )
            else:
                item.status = "pending"
                item.claimed_by = None
                item.claimed_at = None
                logger.debug(
                    f"WorkPool[{self.name}]: {item_id} failed, returning to pool "
                    f"(attempt {item.attempts}/{item.max_retries})"
                )
    
    async def size(self) -> int:
        return sum(1 for item in self._items.values() if item.status == "pending")
    
    async def release_by_worker(self, worker_id: str) -> int:
        async with self._lock:
            released = 0
            for item in self._items.values():
                if item.claimed_by == worker_id and item.status == "claimed":
                    item.status = "pending"
                    item.claimed_by = None
                    item.claimed_at = None
                    released += 1
            logger.debug(f"WorkPool[{self.name}]: released {released} items from {worker_id}")
            return released


class MemoryWorkBackend:
    """In-memory work backend with named pools."""
    
    def __init__(self):
        self._pools: Dict[str, MemoryWorkPool] = {}
    
    def pool(self, name: str) -> MemoryWorkPool:
        if name not in self._pools:
            self._pools[name] = MemoryWorkPool(name)
        return self._pools[name]


class SQLiteWorkPool:
    """SQLite-based work pool implementation."""
    
    def __init__(self, name: str, db_path: Path, lock: asyncio.Lock):
        self.name = name
        self.db_path = db_path
        self._lock = lock
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _row_to_item(self, row: sqlite3.Row) -> WorkItem:
        return WorkItem(
            id=row["item_id"],
            data=json.loads(row["data"]),
            claimed_by=row["claimed_by"],
            attempts=row["attempts"],
            max_retries=row["max_retries"],
            status=row["status"],
            created_at=row["created_at"],
            claimed_at=row["claimed_at"],
        )
    
    async def push(self, item: Any, options: Optional[Dict[str, Any]] = None) -> str:
        async with self._lock:
            item_id = str(uuid.uuid4())
            max_retries = (options or {}).get("max_retries", 3)
            now = datetime.now(timezone.utc).isoformat()
            
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO work_pool 
                    (item_id, pool_name, data, status, attempts, max_retries, created_at)
                    VALUES (?, ?, ?, 'pending', 0, ?, ?)
                    """,
                    (item_id, self.name, json.dumps(item), max_retries, now)
                )
            
            logger.debug(f"WorkPool[{self.name}]: pushed item {item_id}")
            return item_id
    
    async def claim(self, worker_id: str) -> Optional[WorkItem]:
        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            
            with self._get_conn() as conn:
                # Atomic claim: select and update in transaction
                cursor = conn.execute(
                    """
                    SELECT item_id FROM work_pool 
                    WHERE pool_name = ? AND status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (self.name,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                
                item_id = row["item_id"]
                conn.execute(
                    """
                    UPDATE work_pool 
                    SET status = 'claimed', claimed_by = ?, claimed_at = ?, 
                        attempts = attempts + 1
                    WHERE item_id = ?
                    """,
                    (worker_id, now, item_id)
                )
                
                # Fetch the updated item
                cursor = conn.execute(
                    "SELECT * FROM work_pool WHERE item_id = ?",
                    (item_id,)
                )
                row = cursor.fetchone()
            
            logger.debug(f"WorkPool[{self.name}]: {worker_id} claimed {item_id}")
            return self._row_to_item(row) if row else None
    
    async def complete(self, item_id: str, result: Optional[Any] = None) -> None:
        async with self._lock:
            with self._get_conn() as conn:
                # Store result and mark completed (or just delete)
                result = conn.execute(
                    "DELETE FROM work_pool WHERE item_id = ?",
                    (item_id,)
                )
                if result.rowcount == 0:
                    raise KeyError(f"Work item {item_id} not found")
            
            logger.debug(f"WorkPool[{self.name}]: completed {item_id}")
    
    async def fail(self, item_id: str, error: Optional[str] = None) -> None:
        async with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT attempts, max_retries FROM work_pool WHERE item_id = ?",
                    (item_id,)
                )
                row = cursor.fetchone()
                if not row:
                    raise KeyError(f"Work item {item_id} not found")
                
                attempts = row["attempts"]
                max_retries = row["max_retries"]
                
                if attempts >= max_retries:
                    conn.execute(
                        "UPDATE work_pool SET status = 'poisoned' WHERE item_id = ?",
                        (item_id,)
                    )
                    logger.warning(
                        f"WorkPool[{self.name}]: {item_id} poisoned after {attempts} attempts"
                    )
                else:
                    conn.execute(
                        """
                        UPDATE work_pool 
                        SET status = 'pending', claimed_by = NULL, claimed_at = NULL
                        WHERE item_id = ?
                        """,
                        (item_id,)
                    )
                    logger.debug(
                        f"WorkPool[{self.name}]: {item_id} failed, returning to pool "
                        f"(attempt {attempts}/{max_retries})"
                    )
    
    async def size(self) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM work_pool WHERE pool_name = ? AND status = 'pending'",
                (self.name,)
            )
            return cursor.fetchone()["cnt"]
    
    async def release_by_worker(self, worker_id: str) -> int:
        async with self._lock:
            with self._get_conn() as conn:
                result = conn.execute(
                    """
                    UPDATE work_pool 
                    SET status = 'pending', claimed_by = NULL, claimed_at = NULL
                    WHERE pool_name = ? AND claimed_by = ? AND status = 'claimed'
                    """,
                    (self.name, worker_id)
                )
                released = result.rowcount
            
            logger.debug(f"WorkPool[{self.name}]: released {released} items from {worker_id}")
            return released


class SQLiteWorkBackend:
    """SQLite-based work backend with named pools."""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS work_pool (
        item_id TEXT PRIMARY KEY,
        pool_name TEXT NOT NULL,
        data TEXT NOT NULL,  -- JSON
        status TEXT NOT NULL DEFAULT 'pending',  -- pending, claimed, completed, failed, poisoned
        claimed_by TEXT,
        claimed_at TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        created_at TEXT NOT NULL,
        error TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_work_pool_name ON work_pool(pool_name);
    CREATE INDEX IF NOT EXISTS idx_work_status ON work_pool(status);
    CREATE INDEX IF NOT EXISTS idx_work_claimed_by ON work_pool(claimed_by);
    """
    
    def __init__(self, db_path: str = "workers.sqlite"):
        self.db_path = Path(db_path)
        self._pools: Dict[str, SQLiteWorkPool] = {}
        self._lock = asyncio.Lock()
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
    
    def pool(self, name: str) -> SQLiteWorkPool:
        if name not in self._pools:
            self._pools[name] = SQLiteWorkPool(name, self.db_path, self._lock)
        return self._pools[name]


# =============================================================================
# Factory Functions
# =============================================================================

def create_registration_backend(
    backend_type: str = "memory",
    **kwargs: Any
) -> RegistrationBackend:
    """Create a registration backend by type.
    
    Args:
        backend_type: "memory" or "sqlite"
        **kwargs: Backend-specific options (e.g., db_path for sqlite)
        
    Returns:
        RegistrationBackend instance
    """
    if backend_type == "memory":
        return MemoryRegistrationBackend()
    elif backend_type == "sqlite":
        db_path = kwargs.get("db_path", "workers.sqlite")
        return SQLiteRegistrationBackend(db_path=db_path)
    else:
        raise ValueError(f"Unknown registration backend type: {backend_type}")


def create_work_backend(
    backend_type: str = "memory",
    **kwargs: Any
) -> WorkBackend:
    """Create a work backend by type.
    
    Args:
        backend_type: "memory" or "sqlite"
        **kwargs: Backend-specific options (e.g., db_path for sqlite)
        
    Returns:
        WorkBackend instance
    """
    if backend_type == "memory":
        return MemoryWorkBackend()
    elif backend_type == "sqlite":
        db_path = kwargs.get("db_path", "workers.sqlite")
        return SQLiteWorkBackend(db_path=db_path)
    else:
        raise ValueError(f"Unknown work backend type: {backend_type}")


__all__ = [
    # Types
    "WorkerRegistration",
    "WorkerRecord",
    "WorkerFilter",
    "WorkItem",
    # Protocols
    "RegistrationBackend",
    "WorkPool",
    "WorkBackend",
    # Memory implementations
    "MemoryRegistrationBackend",
    "MemoryWorkPool",
    "MemoryWorkBackend",
    # SQLite implementations
    "SQLiteRegistrationBackend",
    "SQLiteWorkPool",
    "SQLiteWorkBackend",
    # Factory functions
    "create_registration_backend",
    "create_work_backend",
]

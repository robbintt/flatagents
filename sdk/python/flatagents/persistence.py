import json
import fcntl
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict, field
from pathlib import Path
from datetime import datetime, timezone
import aiofiles

logger = logging.getLogger(__name__)

@dataclass
class MachineSnapshot:
    """Wire format for machine checkpoints."""
    execution_id: str
    machine_name: str
    spec_version: str
    current_state: str
    context: Dict[str, Any]
    step: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event: Optional[str] = None  # The event that triggered this checkpoint (machine_start, etc)
    output: Optional[Dict[str, Any]] = None  # Output if captured at state_exit/machine_end

class PersistenceBackend(ABC):
    """Abstract storage backend for checkpoints."""
    
    @abstractmethod
    async def save(self, key: str, value: bytes) -> None:
        pass
    
    @abstractmethod
    async def load(self, key: str) -> Optional[bytes]:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

class LocalFileBackend(PersistenceBackend):
    """File-based persistence backend."""
    
    def __init__(self, base_dir: str = ".checkpoints"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    async def save(self, key: str, value: bytes) -> None:
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, 'wb') as f:
            await f.write(value)
    
    async def load(self, key: str) -> Optional[bytes]:
        path = self.base_dir / key
        if not path.exists():
            return None
        async with aiofiles.open(path, 'rb') as f:
            return await f.read()
            
    async def delete(self, key: str) -> None:
        path = self.base_dir / key
        if path.exists():
            path.unlink()

class MemoryBackend(PersistenceBackend):
    """In-memory backend for ephemeral executions."""
    
    def __init__(self):
        self._store: Dict[str, bytes] = {}
        
    async def save(self, key: str, value: bytes) -> None:
        self._store[key] = value
        
    async def load(self, key: str) -> Optional[bytes]:
        return self._store.get(key)
        
    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

class CheckpointManager:
    """Manages saving and loading machine snapshots."""
    
    def __init__(self, backend: PersistenceBackend, execution_id: str):
        self.backend = backend
        self.execution_id = execution_id
        
    def _snapshot_key(self, event: str, step: int) -> str:
        """Generate key for specific snapshot."""
        return f"{self.execution_id}/step_{step:06d}_{event}.json"
        
    def _latest_pointer_key(self) -> str:
        """Key that points to the latest snapshot."""
        return f"{self.execution_id}/latest"

    def _safe_serialize(self, data: Dict[str, Any]) -> str:
        """Safely serialize data to JSON, handling non-serializable objects."""
        try:
            return json.dumps(data)
        except (TypeError, OverflowError):
            # Fallback: stringify values if strict dumped fails
            # This is a basic safety net, can be improved in v2
            logger.warning("Context not fully JSON serializable, falling back to string conversion")
            safe_data = {}
            for k, v in data.items():
                try:
                    json.dumps({k: v})
                    safe_data[k] = v
                except (TypeError, OverflowError):
                    safe_data[k] = str(v)
            return json.dumps(safe_data)

    async def save_checkpoint(self, snapshot: MachineSnapshot) -> None:
        """Save a snapshot and update latest pointer."""
        data = asdict(snapshot)
        json_bytes = self._safe_serialize(data).encode('utf-8')
        
        # Save the immutable snapshot
        key = self._snapshot_key(snapshot.event or "unknown", snapshot.step)
        await self.backend.save(key, json_bytes)
        
        # Update pointer to this key
        await self.backend.save(self._latest_pointer_key(), key.encode('utf-8'))
        
    async def load_latest(self) -> Optional[MachineSnapshot]:
        """Load the latest snapshot."""
        # Get pointer
        ptr_bytes = await self.backend.load(self._latest_pointer_key())
        if not ptr_bytes:
            return None
            
        # Get snapshot
        key = ptr_bytes.decode('utf-8')
        data_bytes = await self.backend.load(key)
        if not data_bytes:
            return None
            
        data = json.loads(data_bytes.decode('utf-8'))
        return MachineSnapshot(**data)

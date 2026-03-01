import fcntl
import asyncio
import os
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path
import contextlib

class ExecutionLock(ABC):
    """Abstract interface for concurrency control."""
    
    @abstractmethod
    async def acquire(self, key: str) -> bool:
        """Acquire lock for key. Returns True if successful."""
        pass
        
    @abstractmethod
    async def release(self, key: str) -> None:
        """Release lock for key."""
        pass

class LocalFileLock(ExecutionLock):
    """
    File-based lock using fcntl.flock.
    Works on local filesystems and NFS (mostly).
    NOT suited for distributed cloud storage (S3/GCS).
    """
    
    def __init__(self, lock_dir: str = ".locks"):
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._files = {}
        
    async def acquire(self, key: str) -> bool:
        """Attempts to acquire a non-blocking exclusive lock."""
        path = self.lock_dir / f"{key}.lock"
        
        try:
            # Keep file handle open while locked
            f = open(path, 'a+')
            try:
                # LOCK_EX | LOCK_NB = Exclusive, Non-Blocking
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._files[key] = f
                return True
            except (IOError, OSError):
                f.close()
                return False
        except Exception:
            return False
            
    async def release(self, key: str) -> None:
        if key in self._files:
            f = self._files.pop(key)
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            finally:
                f.close()
                # Optional: unlink file? Usually simpler to leave it empty
                # Path(f.name).unlink(missing_ok=True)

class NoOpLock(ExecutionLock):
    """Used when concurrency control is disabled or managed externally."""
    
    async def acquire(self, key: str) -> bool:
        return True
        
    async def release(self, key: str) -> None:
        pass

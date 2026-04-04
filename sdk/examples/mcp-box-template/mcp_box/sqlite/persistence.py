"""
SQLite Persistence for MCP-Box.

Provides persistent storage for:
- MCP Box metadata
- Task execution runs
- Success/failure metrics
"""

import sqlite3
import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

if TYPE_CHECKING:
    from mcp_box.schemas.mcp_box import MCPBox


@dataclass
class Run:
    """A task execution run record."""
    id: Optional[int] = None
    box_name: str = ""
    task_id: str = ""
    task_data: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None


@dataclass
class Metric:
    """A metric record."""
    id: Optional[int] = None
    box_name: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None


class MCPBoxDatabase:
    """
    SQLite database for MCP-Box persistence.
    
    Schema includes:
    - mcp_boxes: Box metadata storage
    - runs: Task execution logs
    - metrics: Success rate and other metrics
    
    Usage:
        db = MCPBoxDatabase("mcp_box.db")
        db.save_box(mcp_box)
        db.log_run(run)
        success_rate = db.get_success_rate("my-box")
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS mcp_boxes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        version TEXT NOT NULL,
        description TEXT,
        config TEXT NOT NULL,
        tool_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        box_name TEXT NOT NULL,
        task_id TEXT,
        task_data TEXT,
        success BOOLEAN NOT NULL,
        result TEXT,
        error TEXT,
        execution_time REAL DEFAULT 0,
        tool_calls TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (box_name) REFERENCES mcp_boxes(name)
    );
    
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        box_name TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        metric_value REAL NOT NULL,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (box_name) REFERENCES mcp_boxes(name)
    );
    
    CREATE INDEX IF NOT EXISTS idx_runs_box_name ON runs(box_name);
    CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
    CREATE INDEX IF NOT EXISTS idx_metrics_box_name ON metrics(box_name);
    CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
    """
    
    def __init__(self, db_path: str = "mcp_box.db"):
        self.db_path = db_path
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        conn.executescript(self.SCHEMA)
        conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    # -------------------------------------------------------------------------
    # Box Operations
    # -------------------------------------------------------------------------
    
    def save_box(self, mcp_box: "MCPBox") -> int:
        """
        Save an MCPBox to the database.
        
        Args:
            mcp_box: MCPBox instance to save
            
        Returns:
            Row ID of saved/updated box
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        config = mcp_box.to_json()
        
        cursor.execute("""
            INSERT INTO mcp_boxes (name, version, description, config, tool_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                version = excluded.version,
                description = excluded.description,
                config = excluded.config,
                tool_count = excluded.tool_count,
                updated_at = CURRENT_TIMESTAMP
        """, (
            mcp_box.name,
            mcp_box.version,
            mcp_box.description,
            config,
            len(mcp_box.tools),
        ))
        
        conn.commit()
        # Return lastrowid, defaulting to 0 only if None
        return cursor.lastrowid if cursor.lastrowid is not None else 0
    
    def get_box(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get an MCPBox by name.
        
        Args:
            name: Box name
            
        Returns:
            Box configuration dict or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT config FROM mcp_boxes WHERE name = ?",
            (name,)
        )
        row = cursor.fetchone()
        
        if row:
            return json.loads(row["config"])
        return None
    
    def list_boxes(self) -> List[Dict[str, Any]]:
        """
        List all saved MCPBoxes.
        
        Returns:
            List of box metadata dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, version, description, tool_count, created_at, updated_at
            FROM mcp_boxes
            ORDER BY updated_at DESC
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_box(self, name: str) -> bool:
        """
        Delete an MCPBox by name.
        
        Args:
            name: Box name
            
        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM mcp_boxes WHERE name = ?", (name,))
        conn.commit()
        
        return cursor.rowcount > 0
    
    # -------------------------------------------------------------------------
    # Run Operations
    # -------------------------------------------------------------------------
    
    def log_run(self, run: Run) -> int:
        """
        Log a task execution run.
        
        Args:
            run: Run record to log
            
        Returns:
            Row ID of logged run
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO runs (
                box_name, task_id, task_data, success, result,
                error, execution_time, tool_calls
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run.box_name,
            run.task_id,
            json.dumps(run.task_data),
            run.success,
            json.dumps(run.result) if run.result else None,
            run.error,
            run.execution_time,
            json.dumps(run.tool_calls),
        ))
        
        conn.commit()
        return cursor.lastrowid if cursor.lastrowid is not None else 0
    
    def get_runs(
        self,
        box_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Run]:
        """
        Get runs for a box.
        
        Args:
            box_name: Box name to filter by
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of Run records
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM runs
            WHERE box_name = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (box_name, limit, offset))
        
        runs = []
        for row in cursor.fetchall():
            runs.append(Run(
                id=row["id"],
                box_name=row["box_name"],
                task_id=row["task_id"] or "",
                task_data=json.loads(row["task_data"]) if row["task_data"] else {},
                success=bool(row["success"]),
                result=json.loads(row["result"]) if row["result"] else None,
                error=row["error"],
                execution_time=row["execution_time"] or 0.0,
                tool_calls=json.loads(row["tool_calls"]) if row["tool_calls"] else [],
                created_at=row["created_at"],
            ))
        
        return runs
    
    def get_run_count(self, box_name: str) -> Dict[str, int]:
        """
        Get run counts for a box.
        
        Args:
            box_name: Box name
            
        Returns:
            Dict with total, success, and failure counts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failure_count
            FROM runs
            WHERE box_name = ?
        """, (box_name,))
        
        row = cursor.fetchone()
        return {
            "total": row["total"] or 0,
            "success": row["success_count"] or 0,
            "failure": row["failure_count"] or 0,
        }
    
    # -------------------------------------------------------------------------
    # Metrics Operations
    # -------------------------------------------------------------------------
    
    def log_metric(self, metric: Metric) -> int:
        """
        Log a metric.
        
        Args:
            metric: Metric record to log
            
        Returns:
            Row ID of logged metric
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO metrics (box_name, metric_name, metric_value, metadata)
            VALUES (?, ?, ?, ?)
        """, (
            metric.box_name,
            metric.metric_name,
            metric.metric_value,
            json.dumps(metric.metadata),
        ))
        
        conn.commit()
        return cursor.lastrowid if cursor.lastrowid is not None else 0
    
    def get_success_rate(self, box_name: str) -> float:
        """
        Calculate success rate for a box.
        
        Args:
            box_name: Box name
            
        Returns:
            Success rate as float (0.0 to 1.0)
        """
        counts = self.get_run_count(box_name)
        if counts["total"] == 0:
            return 0.0
        return counts["success"] / counts["total"]
    
    def get_metrics(
        self,
        box_name: str,
        metric_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Metric]:
        """
        Get metrics for a box.
        
        Args:
            box_name: Box name
            metric_name: Optional metric name filter
            limit: Maximum number of results
            
        Returns:
            List of Metric records
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if metric_name:
            cursor.execute("""
                SELECT * FROM metrics
                WHERE box_name = ? AND metric_name = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (box_name, metric_name, limit))
        else:
            cursor.execute("""
                SELECT * FROM metrics
                WHERE box_name = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (box_name, limit))
        
        metrics = []
        for row in cursor.fetchall():
            metrics.append(Metric(
                id=row["id"],
                box_name=row["box_name"],
                metric_name=row["metric_name"],
                metric_value=row["metric_value"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                created_at=row["created_at"],
            ))
        
        return metrics
    
    def get_average_metric(self, box_name: str, metric_name: str) -> float:
        """
        Get average value for a metric.
        
        Args:
            box_name: Box name
            metric_name: Metric name
            
        Returns:
            Average metric value
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT AVG(metric_value) as avg_value
            FROM metrics
            WHERE box_name = ? AND metric_name = ?
        """, (box_name, metric_name))
        
        row = cursor.fetchone()
        return row["avg_value"] or 0.0

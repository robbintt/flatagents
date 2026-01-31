"""Token estimation, history compression, guidance loading."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any

def load_guidance() -> str:
    """Load GUIDANCE.md (~400 tokens)."""
    path = Path(__file__).parent.parent.parent / "GUIDANCE.md"
    return path.read_text()

def estimate_tokens(text: str) -> dict:
    """Estimate tokens using tiktoken + char ratio."""
    char_estimate = len(text) // 4
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        tiktoken_estimate = len(enc.encode(text))
    except ImportError:
        tiktoken_estimate = None
    return {
        "char_estimate": char_estimate,
        "tiktoken_estimate": tiktoken_estimate,
        "used": tiktoken_estimate or char_estimate
    }

def compress_history(milestones: list) -> list:
    """Logarithmic compression: recent=detailed, old=summarized."""
    if len(milestones) <= 5:
        return milestones
    
    recent = milestones[-5:]
    older = milestones[:-5]
    
    # Summarize older into one entry
    if older:
        summary = {
            "timestamp": older[0].get("timestamp", ""),
            "description": f"[{len(older)} earlier steps]",
            "source": "compressed"
        }
        return [summary] + recent
    return recent

def fetch_ledger(db_path: str, session_id: str) -> dict:
    """Fetch ledger from SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM ledger WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"goal": "", "progress": [], "techniques": [], "failed_approaches": [], "human_notes": []}
    
    return {
        "goal": row["goal"],
        "progress": json.loads(row["progress"] or "[]"),
        "techniques": json.loads(row["techniques"] or "[]"),
        "failed_approaches": json.loads(row["failed_approaches"] or "[]"),
        "human_notes": json.loads(row["human_notes"] or "[]"),
    }

def serialize_ledger(ledger: dict) -> str:
    """Serialize ledger for token counting."""
    return json.dumps(ledger, indent=2)

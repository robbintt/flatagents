"""Anything Agent entry point."""
import argparse
import asyncio
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger (
    session_id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    progress TEXT NOT NULL DEFAULT '[]',
    techniques TEXT NOT NULL DEFAULT '[]',
    failed_approaches TEXT NOT NULL DEFAULT '[]',
    human_notes TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    parent_id TEXT,
    machine_type TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    machine_yaml TEXT NOT NULL,
    agent_yamls TEXT NOT NULL DEFAULT '{}',
    snapshot TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    terminated_at TEXT
);
CREATE TABLE IF NOT EXISTS pending_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    state_name TEXT NOT NULL,
    context_json TEXT NOT NULL,
    proposed_transition TEXT NOT NULL,
    status TEXT NOT NULL,
    human_note TEXT,
    created_at TEXT NOT NULL,
    responded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_session ON executions(session_id);
CREATE INDEX IF NOT EXISTS idx_pending ON pending_approvals(status);
"""

def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

def start_goal(goal: str, db_path: str):
    """Start new session with goal."""
    session_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    machine_path = Path(__file__).parent / "machines" / "core.yml"
    machine_yaml = machine_path.read_text()
    
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO sessions (session_id, goal, status, created_at, updated_at) VALUES (?, ?, 'active', ?, ?)",
        (session_id, goal, now, now)
    )
    conn.execute(
        "INSERT INTO ledger (session_id, goal, updated_at) VALUES (?, ?, ?)",
        (session_id, goal, now)
    )
    conn.execute(
        "INSERT INTO executions (execution_id, session_id, machine_type, tags, machine_yaml, status, created_at) VALUES (?, ?, 'core', '[\"initial\"]', ?, 'pending', ?)",
        (execution_id, session_id, machine_yaml, now)
    )
    conn.commit()
    conn.close()
    
    print(f"🚀 Session {session_id[:8]}... created")
    print(f"   Goal: {goal}")
    print(f"   Run './run.sh observe' to approve transitions")

def resolve_session_id(db_path: str, session_id: str) -> str | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT session_id FROM sessions WHERE session_id = ? OR session_id LIKE ? ORDER BY created_at DESC",
        (session_id, f"{session_id}%")
    )
    rows = [r["session_id"] for r in cursor.fetchall()]
    conn.close()

    if not rows:
        print(f"❌ No session matches '{session_id}'.")
        return None

    if session_id in rows:
        return session_id

    if len(rows) > 1:
        matches = ", ".join(r[:8] for r in rows[:5])
        suffix = "..." if len(rows) > 5 else ""
        print(f"❌ Session id '{session_id}' is ambiguous: {matches}{suffix}")
        return None

    return rows[0]

def resume_session(session_id: str, db_path: str) -> str | None:
    resolved = resolve_session_id(db_path, session_id)
    if not resolved:
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT execution_id, status FROM executions WHERE session_id = ? AND status != 'terminated' ORDER BY created_at DESC LIMIT 1",
        (resolved,)
    )
    row = cursor.fetchone()

    if not row:
        cursor = conn.execute(
            "SELECT execution_id, status FROM executions WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (resolved,)
        )
        last = cursor.fetchone()
        conn.close()
        if last:
            print(f"ℹ️  Session {resolved[:8]}... already completed (last execution terminated).")
        else:
            print(f"❌ No executions found for session {resolved[:8]}...")
        return None

    execution_id = row["execution_id"]
    status = row["status"]
    now = datetime.now().isoformat()

    if status in ("suspended", "running"):
        conn.execute("UPDATE executions SET status = 'pending' WHERE execution_id = ?", (execution_id,))
        action = "requeued"
    elif status == "pending":
        action = "already pending"
    else:
        action = f"status={status}"

    conn.execute(
        "UPDATE sessions SET status = 'active', updated_at = ? WHERE session_id = ?",
        (now, resolved)
    )
    conn.commit()
    conn.close()

    print(f"▶️  Session {resolved[:8]}... {action}")
    return resolved

def list_sessions(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("No sessions yet.")
        return
    
    print(f"{'Session':<40} {'Status':<20} {'Goal'}")
    print("-" * 60)
    for r in rows:
        print(f"{r['session_id']:<40}.. {r['status']:<20} {r['goal'][:40]}")

def main():
    parser = argparse.ArgumentParser(description="Anything Agent")
    parser.add_argument("command", choices=["run", "resume", "list", "observe"])
    parser.add_argument("--goal", help="Goal for new run")
    parser.add_argument("--session", help="Session ID to resume")
    parser.add_argument("--db", default="./anything_agent.db")
    args = parser.parse_args()
    
    init_db(args.db)
    
    if args.command == "run":
        if not args.goal:
            parser.error("--goal required")
        start_goal(args.goal, args.db)
    elif args.command == "resume":
        if not args.session:
            parser.error("--session required")
        from .observer import run_loop
        resolved = resume_session(args.session, args.db)
        if resolved:
            asyncio.run(run_loop(args.db, resolved))
    elif args.command == "list":
        list_sessions(args.db)
    elif args.command == "observe":
        from .observer import run_loop
        asyncio.run(run_loop(args.db))

if __name__ == "__main__":
    main()

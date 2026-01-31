"""CLI observer for human approval."""
import sqlite3
import json
import asyncio
from datetime import datetime
from pathlib import Path

import yaml
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML

from flatagents import FlatMachine
from .hooks import AnythingAgentHooks, AwaitingApproval

session = PromptSession()

async def run_loop(db_path: str):
    """Main observer loop."""
    print(f"🔍 Anything Agent Observer")
    print(f"📁 Database: {db_path}")
    print("Commands: [a]pprove, [n]ote, [s]top, [q]uit")
    print("-" * 60)
    
    while True:
        pending = get_pending_approvals(db_path)
        
        if not pending:
            pending_exec = get_pending_execution(db_path)
            if pending_exec:
                print(f"\n⏳ Starting {pending_exec['execution_id'][:8]}...")
                await run_execution(pending_exec, db_path)
            else:
                await asyncio.sleep(1)
            continue
        
        approval = pending[0]
        display_approval(approval)
        
        try:
            response = await session.prompt_async(HTML('<b>Decision [a/n/s/q]: </b>'))
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye")
            break
        
        response = response.strip().lower()
        
        if response in ('a', 'approve', ''):
            approve(db_path, approval['id'], approval['session_id'])
            print("✅ Approved")
            await restore_and_continue(approval, db_path)
        elif response in ('n', 'note'):
            note = await session.prompt_async(HTML('<b>Note: </b>'))
            approve(db_path, approval['id'], approval['session_id'], note.strip())
            print(f"✅ Approved with note")
            await restore_and_continue(approval, db_path)
        elif response in ('s', 'stop'):
            stop(db_path, approval['id'])
            print("🛑 Stopped")
        elif response in ('q', 'quit'):
            print("👋 Goodbye")
            break

async def restore_and_continue(approval: dict, db_path: str):
    """Restore from snapshot and continue."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM executions WHERE execution_id = ?", (approval['execution_id'],))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        await run_execution(dict(row), db_path)

async def run_execution(row: dict, db_path: str):
    """Run machine from execution row."""
    execution_id = row['execution_id']
    session_id = row['session_id']
    snapshot = json.loads(row['snapshot']) if row.get('snapshot') else None
    
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE executions SET status = 'running' WHERE execution_id = ?", (execution_id,))
    conn.commit()
    conn.close()
    
    hooks = AnythingAgentHooks(db_path, session_id, execution_id)
    
    # Use file path for proper relative path resolution
    machine_path = Path(__file__).parent / "machines" / "core.yml"
    profiles_path = Path(__file__).parent.parent.parent / "config" / "profiles.yml"
    machine = FlatMachine(config_file=str(machine_path), hooks=hooks, profiles_file=str(profiles_path))
    
    try:
        # If we have a snapshot with context, use it as input
        input_data = {"session_id": session_id, "db_path": db_path}
        if snapshot and 'context' in snapshot:
            input_data.update(snapshot['context'])
        
        result = await machine.execute(input=input_data)
        print(f"✅ Complete: {result}")
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE executions SET status = 'terminated' WHERE execution_id = ?", (execution_id,))
        conn.commit()
        conn.close()
    except AwaitingApproval as e:
        print(f"⏸️  Paused: {e.from_state} → {e.to_state}")

def display_approval(approval: dict):
    print(f"\n{'═' * 60}")
    print(f"📋 Execution: {approval['execution_id'][:8]}...")
    print(f"   Transition: {approval['state_name']} → {approval['proposed_transition']}")
    context = json.loads(approval['context_json'])
    if 'ledger' in context and 'goal' in context['ledger']:
        print(f"   Goal: {context['ledger']['goal'][:50]}")
    print('═' * 60)

def get_pending_approvals(db_path: str) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at LIMIT 1")
    result = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return result

def get_pending_execution(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM executions WHERE status = 'pending' ORDER BY created_at LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def approve(db_path: str, approval_id: int, session_id: str, note: str = None):
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()
    conn.execute("UPDATE pending_approvals SET status = 'approved', human_note = ?, responded_at = ? WHERE id = ?",
                (note, now, approval_id))
    if note:
        cursor = conn.execute("SELECT human_notes FROM ledger WHERE session_id = ?", (session_id,))
        notes = json.loads(cursor.fetchone()[0] or "[]")
        notes.append({"timestamp": now, "note": note})
        conn.execute("UPDATE ledger SET human_notes = ?, updated_at = ? WHERE session_id = ?",
                    (json.dumps(notes), now, session_id))
    conn.commit()
    conn.close()

def stop(db_path: str, approval_id: int):
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE pending_approvals SET status = 'stopped' WHERE id = ?", (approval_id,))
    cursor = conn.execute("SELECT execution_id FROM pending_approvals WHERE id = ?", (approval_id,))
    exec_id = cursor.fetchone()[0]
    conn.execute("UPDATE executions SET status = 'suspended' WHERE execution_id = ?", (exec_id,))
    conn.commit()
    conn.close()

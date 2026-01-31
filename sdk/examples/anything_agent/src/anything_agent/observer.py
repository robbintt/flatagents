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

async def run_loop(db_path: str, session_id: str | None = None):
    """Main observer loop."""
    print(f"🔍 Anything Agent Observer")
    print(f"📁 Database: {db_path}")
    if session_id:
        print(f"🎯 Session: {session_id[:8]}...")
    print("Commands: [a]pprove, [n]ote (approve + add note), [s]top, [q]uit")
    print("Idle: [l]ist stopped, [r]eopen stopped, [q]uit")
    print("-" * 60)
    
    while True:
        pending = get_pending_approvals(db_path, session_id)
        
        if not pending:
            pending_exec = get_pending_execution(db_path, session_id)
            if pending_exec:
                print(f"\n⏳ Starting {pending_exec['execution_id'][:8]}...")
                await run_execution(pending_exec, db_path)
                continue

            try:
                response = await session.prompt_async(HTML('<b>Idle [l]ist/[r]eopen/[q]uit: </b>'))
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Goodbye")
                break

            response = response.strip().lower()
            if not response:
                continue

            parts = response.split()
            command = parts[0]
            arg = parts[1] if len(parts) > 1 else None

            if command in ('q', 'quit'):
                print("👋 Goodbye")
                break
            if command in ('l', 'list'):
                list_stopped_approvals(db_path, session_id)
                continue
            if command in ('r', 'resume', 'reopen', 'unstop'):
                reopened = reopen_stopped_approval(db_path, session_id, arg)
                if reopened:
                    print(f"♻️  Reopened approval {reopened['id']} for {reopened['execution_id'][:8]}...")
                continue

            print("❓ Unknown command. Use [l]ist, [r]eopen, or [q]uit.")
            continue
        
        approval = pending[0]
        display_approval(approval, db_path)
        
        try:
            response = await session.prompt_async(HTML('<b>Decision [a]pprove/[n]ote (approve + note)/[s]top/[q]uit: </b>'))
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

    machine = None
    input_data = {"session_id": session_id, "db_path": db_path}

    if snapshot and snapshot.get("state") and snapshot.get("context"):
        machine_yaml = row.get("machine_yaml")
        if not machine_yaml:
            machine_yaml = machine_path.read_text()
        machine_config = yaml.safe_load(machine_yaml) or {}
        machine_config = _apply_snapshot(machine_config, snapshot)
        machine = FlatMachine(
            config_dict=machine_config,
            hooks=hooks,
            profiles_file=str(profiles_path),
            _config_dir=str(machine_path.parent),
        )
        input_data = {}
    else:
        machine = FlatMachine(config_file=str(machine_path), hooks=hooks, profiles_file=str(profiles_path))
        if snapshot and 'context' in snapshot:
            input_data.update(snapshot['context'])
    
    try:
        result = await machine.execute(input=input_data)
        print(f"✅ Complete: {result}")
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE executions SET status = 'terminated' WHERE execution_id = ?", (execution_id,))
        conn.commit()
        conn.close()
    except AwaitingApproval as e:
        print(f"⏸️  Paused: {e.from_state} → {e.to_state}")

def _apply_snapshot(machine_config: dict, snapshot: dict) -> dict:
    data = machine_config.get("data", {})
    states = data.get("states", {})
    target_state = snapshot.get("state")

    if target_state and target_state in states:
        for state_name, state in states.items():
            if state.get("type") == "initial":
                state.pop("type", None)
        states[target_state]["type"] = "initial"
    else:
        print(f"⚠️  Snapshot state '{target_state}' not found. Starting from default initial state.")

    data["context"] = snapshot.get("context", {})
    machine_config["data"] = data
    return machine_config

def display_approval(approval: dict, db_path: str):
    print(f"\n{'═' * 60}")
    print(f"📋 Execution: {approval['execution_id'][:8]}...")
    print(f"   Transition: {approval['state_name']} → {approval['proposed_transition']}")

    context = json.loads(approval['context_json'])
    if 'ledger' in context and 'goal' in context['ledger']:
        print(f"   Goal: {context['ledger']['goal'][:50]}")

    machine_yaml = None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT machine_yaml FROM executions WHERE execution_id = ?",
        (approval['execution_id'],)
    )
    row = cursor.fetchone()
    conn.close()
    if row and row["machine_yaml"]:
        machine_yaml = row["machine_yaml"]

    if machine_yaml:
        machine = yaml.safe_load(machine_yaml)
        data = (machine or {}).get("data", {})
        states = data.get("states", {})
        from_state = states.get(approval["state_name"], {})
        to_state = states.get(approval["proposed_transition"], {})

        print("\n🧠 Machine data:")
        machine_header = {
            "name": data.get("name"),
            "context": data.get("context"),
            "agents": data.get("agents"),
        }
        print(yaml.safe_dump(machine_header, sort_keys=False).strip())

        print("\n➡️  From state definition:")
        print(yaml.safe_dump(from_state or {"missing": True}, sort_keys=False).strip())

        print("\n✅ To state definition:")
        print(yaml.safe_dump(to_state or {"missing": True}, sort_keys=False).strip())

    session_id = approval.get("session_id")
    if session_id:
        ledger = fetch_ledger(db_path, session_id)
        if ledger:
            print("\n🧾 Ledger (db):")
            print(yaml.safe_dump(ledger, sort_keys=False).strip())

    print("\n📦 Context snapshot:")
    print(json.dumps(context, indent=2, sort_keys=True))
    print('═' * 60)

def get_pending_approvals(db_path: str, session_id: str | None = None) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if session_id:
        cursor = conn.execute(
            "SELECT * FROM pending_approvals WHERE status = 'pending' AND session_id = ? ORDER BY created_at LIMIT 1",
            (session_id,)
        )
    else:
        cursor = conn.execute("SELECT * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at LIMIT 1")
    result = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return result

def get_pending_execution(db_path: str, session_id: str | None = None) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if session_id:
        cursor = conn.execute(
            "SELECT * FROM executions WHERE status = 'pending' AND session_id = ? ORDER BY created_at LIMIT 1",
            (session_id,)
        )
    else:
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

def fetch_ledger(db_path: str, session_id: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT goal, progress, techniques, failed_approaches, human_notes FROM ledger WHERE session_id = ?",
        (session_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "goal": row["goal"],
        "progress": json.loads(row["progress"] or "[]"),
        "techniques": json.loads(row["techniques"] or "[]"),
        "failed_approaches": json.loads(row["failed_approaches"] or "[]"),
        "human_notes": json.loads(row["human_notes"] or "[]"),
    }

def get_stopped_approvals(db_path: str, session_id: str | None = None) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if session_id:
        cursor = conn.execute(
            "SELECT * FROM pending_approvals WHERE status = 'stopped' AND session_id = ? ORDER BY created_at DESC",
            (session_id,)
        )
    else:
        cursor = conn.execute("SELECT * FROM pending_approvals WHERE status = 'stopped' ORDER BY created_at DESC")
    result = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return result

def list_stopped_approvals(db_path: str, session_id: str | None = None):
    stopped = get_stopped_approvals(db_path, session_id)
    if not stopped:
        print("ℹ️  No stopped approvals.")
        return

    print("\n🧯 Stopped approvals:")
    for approval in stopped[:10]:
        print(
            f"  {approval['id']:>4}  {approval['execution_id'][:8]}... "
            f"{approval['state_name']} → {approval['proposed_transition']}"
        )
    if len(stopped) > 10:
        print(f"  ... and {len(stopped) - 10} more")

def reopen_stopped_approval(db_path: str, session_id: str | None = None, approval_id: str | None = None) -> dict | None:
    stopped = get_stopped_approvals(db_path, session_id)
    if not stopped:
        print("ℹ️  No stopped approvals to reopen.")
        return None

    target = None
    if approval_id:
        try:
            approval_id_int = int(approval_id)
        except ValueError:
            print("❌ Approval id must be a number.")
            return None

        for approval in stopped:
            if approval["id"] == approval_id_int:
                target = approval
                break
        if not target:
            print(f"❌ No stopped approval with id {approval_id_int}.")
            return None
    else:
        target = stopped[0]

    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE pending_approvals SET status = 'pending', responded_at = NULL, human_note = NULL WHERE id = ?",
        (target["id"],)
    )
    conn.execute("UPDATE executions SET status = 'pending' WHERE execution_id = ?", (target["execution_id"],))
    conn.commit()
    conn.close()
    return target

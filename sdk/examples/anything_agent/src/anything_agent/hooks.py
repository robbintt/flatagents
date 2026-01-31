"""Hooks for Anything Agent."""
import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, Any
from flatagents import MachineHooks
from .context import load_guidance, estimate_tokens, compress_history, fetch_ledger, serialize_ledger

class AwaitingApproval(Exception):
    """Raised to exit and await human approval."""
    def __init__(self, execution_id: str, from_state: str, to_state: str):
        self.execution_id = execution_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Awaiting: {from_state} → {to_state}")

class AnythingAgentHooks(MachineHooks):
    def __init__(self, db_path: str, session_id: str, execution_id: str = None):
        self.db_path = db_path
        self.session_id = session_id
        self.execution_id = execution_id or str(uuid.uuid4())
    
    def on_transition(self, from_state: str, to_state: str, context: Dict[str, Any]) -> str:
        """Check approval, snapshot if needed, exit if not approved."""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        
        # Check if this exact transition was already approved
        cursor = conn.execute(
            "SELECT id, status FROM pending_approvals WHERE execution_id = ? AND state_name = ? AND proposed_transition = ? ORDER BY id DESC LIMIT 1",
            (self.execution_id, from_state, to_state)
        )
        row = cursor.fetchone()
        
        if row and row[1] == 'approved':
            # Consume approval so loops require fresh approval next time
            conn.execute("UPDATE pending_approvals SET status = 'consumed' WHERE id = ?", (row[0],))
            conn.commit()
            conn.close()
            return to_state
        
        if row and row[1] == 'pending':
            # Already pending, just wait
            conn.close()
            raise AwaitingApproval(self.execution_id, from_state, to_state)
        
        # New transition, needs approval
        # Serialize context, handling non-serializable items
        ctx_copy = {}
        for k, v in context.items():
            try:
                json.dumps(v)
                ctx_copy[k] = v
            except (TypeError, ValueError):
                ctx_copy[k] = str(v)
        
        snapshot = {"state": to_state, "context": ctx_copy}
        conn.execute("UPDATE executions SET snapshot = ? WHERE execution_id = ?",
                    (json.dumps(snapshot), self.execution_id))
        conn.execute(
            "INSERT INTO pending_approvals (execution_id, session_id, state_name, context_json, proposed_transition, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (self.execution_id, self.session_id, from_state, json.dumps(ctx_copy), to_state, now)
        )
        conn.commit()
        conn.close()
        raise AwaitingApproval(self.execution_id, from_state, to_state)
    
    def on_action(self, action_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if action_name == "load_context":
            return self._load_context(context)
        elif action_name == "cleanup_context":
            return self._cleanup_context(context)
        elif action_name == "save_ledger":
            return self._save_ledger(context)
        return context
    
    def _load_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load ledger, prune to budget."""
        model_limit = context.get("model_token_limit", 200000)
        target_pct = context.get("context_target_pct", 0.20)
        minimum = context.get("context_minimum", 12000)
        budget = max(int(model_limit * target_pct), minimum)
        
        guidance = load_guidance()
        guidance_tokens = estimate_tokens(guidance)["used"]
        ledger_budget = budget - guidance_tokens
        
        ledger = fetch_ledger(self.db_path, self.session_id)
        ledger["progress"] = compress_history(ledger["progress"])
        
        tokens = estimate_tokens(serialize_ledger(ledger))
        while tokens["used"] > ledger_budget and len(ledger["progress"]) > 1:
            ledger["progress"] = ledger["progress"][1:]
            tokens = estimate_tokens(serialize_ledger(ledger))
        
        context["guidance"] = guidance
        context["ledger"] = ledger
        context["token_estimate"] = tokens
        context["token_budget"] = budget
        
        total = tokens["used"] + guidance_tokens
        print(f"📊 Context: {total:,}/{budget:,} tokens (ledger: {tokens['used']:,}, guidance: {guidance_tokens})")
        return context
    
    def _cleanup_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Clear intermediate fields, log failures."""
        if context.get("work_result") and context.get("work_success") == False:
            failure_line = str(context["work_result"])[:100].replace('\n', ' ')
            print(f"❌ Failed: {failure_line}")
            if "ledger_update" not in context:
                context["ledger_update"] = {}
            context["ledger_update"]["new_failure"] = {
                "approach": context.get("action_detail", "unknown")[:50],
                "reason": failure_line,
                "timestamp": datetime.now().isoformat()
            }
        
        for field in ["work_result", "work_success", "action_detail", "leaf_result"]:
            context[field] = None
        return context
    
    def _save_ledger(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Persist ledger updates."""
        update = context.get("ledger_update", {})
        if not update:
            return context
        
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        
        for key, field in [("new_milestone", "progress"), ("new_failure", "failed_approaches"), ("new_technique", "techniques")]:
            if key in update:
                cursor = conn.execute(f"SELECT {field} FROM ledger WHERE session_id = ?", (self.session_id,))
                items = json.loads(cursor.fetchone()[0] or "[]")
                items.append(update[key])
                conn.execute(f"UPDATE ledger SET {field} = ?, updated_at = ? WHERE session_id = ?",
                            (json.dumps(items), now, self.session_id))
        
        conn.commit()
        conn.close()
        context["ledger_update"] = {}
        return context

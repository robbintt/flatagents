"""Hooks for Anything Agent."""
import sqlite3
import json
import uuid
import subprocess
import io
import contextlib
import traceback
from datetime import datetime
from typing import Dict, Any

import yaml
from flatagents import MachineHooks, validate_flatagent_config, validate_flatmachine_config

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
            conn.execute(
                "UPDATE executions SET status = 'suspended' WHERE execution_id = ?",
                (self.execution_id,)
            )
            conn.commit()
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
        conn.execute(
            "UPDATE executions SET status = 'suspended' WHERE execution_id = ?",
            (self.execution_id,)
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
        elif action_name == "run_shell":
            return self._run_shell(context)
        elif action_name == "run_python":
            return self._run_python(context)
        elif action_name == "validate_specs":
            return self._validate_specs(context)
        elif action_name == "validate_decision":
            return self._validate_decision(context)
        elif action_name == "spawn_leaf":
            return self._spawn_leaf(context)
        elif action_name == "spawn_self":
            return self._spawn_self(context)
        elif action_name == "return_to_core":
            return self._return_to_core(context)
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

        self_machine_yaml = None
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT machine_yaml FROM executions WHERE execution_id = ?",
            (self.execution_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            self_machine_yaml = row[0]
        
        context["guidance"] = guidance
        context["ledger"] = ledger
        context["token_estimate"] = tokens
        context["token_budget"] = budget
        context["self_machine_yaml"] = self_machine_yaml
        
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

    def _run_shell(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run a shell command from context.shell_command or context.command."""
        command = context.get("shell_command") or context.get("command")
        if not command:
            context["shell_success"] = False
            context["shell_error"] = "shell_command missing"
            return context

        try:
            if isinstance(command, list):
                cmd = command
                shell = False
            else:
                cmd = command
                shell = True
            result = subprocess.run(
                cmd,
                shell=shell,
                text=True,
                capture_output=True,
            )
            context["shell_stdout"] = result.stdout
            context["shell_stderr"] = result.stderr
            context["shell_exit_code"] = result.returncode
            context["shell_success"] = result.returncode == 0
        except Exception as exc:
            context["shell_success"] = False
            context["shell_error"] = str(exc)
        return context

    def _run_python(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute python code from context.python_code or context.code."""
        code = context.get("python_code") or context.get("code")
        if not code:
            context["python_success"] = False
            context["python_error"] = "python_code missing"
            return context

        stdout = io.StringIO()
        stderr = io.StringIO()
        namespace: Dict[str, Any] = {}
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, namespace, namespace)
            context["python_success"] = True
            context["python_stdout"] = stdout.getvalue()
            context["python_stderr"] = stderr.getvalue()
            context["python_result"] = namespace.get("result")
        except Exception:
            context["python_success"] = False
            context["python_stdout"] = stdout.getvalue()
            context["python_stderr"] = stderr.getvalue()
            context["python_error"] = traceback.format_exc()
        return context

    def _validate_specs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generated machine specs and inline agents."""
        validation_kind = context.get("validation_kind") or ""
        machine_yaml = None
        if validation_kind == "leaf":
            machine_yaml = context.get("leaf_machine_yaml")
        elif validation_kind == "self":
            machine_yaml = context.get("self_machine_yaml")
        else:
            machine_yaml = context.get("leaf_machine_yaml") or context.get("self_machine_yaml")

        errors: list[str] = []
        machine_config = None

        if not machine_yaml:
            errors.append("machine_yaml missing")
        else:
            try:
                machine_config = yaml.safe_load(machine_yaml) or {}
            except Exception as exc:
                errors.append(f"machine_yaml parse error: {exc}")

        if machine_config:
            errors.extend(validate_flatmachine_config(machine_config, warn=False, strict=False))

            data = machine_config.get("data", {})
            if data.get("hooks"):
                errors.append("machine config must not define hooks (hooks are injected by runner)")

            agents = data.get("agents", {})
            for name, agent_ref in agents.items():
                if isinstance(agent_ref, dict):
                    errors.extend(
                        f"agent '{name}': {err}" for err in validate_flatagent_config(agent_ref, warn=False, strict=False)
                    )

            if validation_kind == "leaf":
                states = data.get("states", {})
                has_return = any(state.get("action") == "return_to_core" for state in states.values())
                if not has_return:
                    errors.append("leaf machine must include an action: return_to_core")

            if validation_kind == "self":
                states = data.get("states", {})
                has_driver = any(state.get("agent") == "driver" for state in states.values())
                if not has_driver:
                    errors.append("self machine must include an agent: driver")

        context["validation_passed"] = len(errors) == 0
        context["validation_errors"] = errors
        context["candidate_machine_yaml"] = machine_yaml or ""
        return context

    def _validate_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate driver decision before attempting to spawn machines."""
        action = context.get("next_action")
        errors: list[str] = []

        if action not in ("delegate", "spawn_self", "done"):
            errors.append("decision.action must be delegate, spawn_self, or done")

        if action == "delegate" and not context.get("leaf_machine_yaml"):
            errors.append("leaf_machine_yaml required for delegate")

        if action == "spawn_self" and not context.get("self_machine_yaml"):
            errors.append("self_machine_yaml required for spawn_self")

        context["decision_valid"] = len(errors) == 0
        if errors:
            context["validation_errors"] = errors
            context["candidate_machine_yaml"] = (
                context.get("leaf_machine_yaml")
                or context.get("self_machine_yaml")
                or ""
            )
        else:
            context["validation_errors"] = []
        return context

    def _spawn_leaf(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Spawn a leaf execution from context.leaf_machine_yaml."""
        machine_yaml = context.get("leaf_machine_yaml")
        if not machine_yaml:
            context["spawn_error"] = "leaf_machine_yaml missing"
            return context

        return_machine_yaml = context.get("self_machine_yaml")
        input_data = {
            "session_id": self.session_id,
            "db_path": self.db_path,
            "return_machine_yaml": return_machine_yaml,
        }
        return self._spawn_execution(context, machine_yaml, input_data, machine_type="leaf")

    def _spawn_self(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Spawn a new self execution from context.self_machine_yaml."""
        machine_yaml = context.get("self_machine_yaml")
        if not machine_yaml:
            context["spawn_error"] = "self_machine_yaml missing"
            return context

        input_data = {
            "session_id": self.session_id,
            "db_path": self.db_path,
        }
        return self._spawn_execution(context, machine_yaml, input_data, machine_type="core")

    def _return_to_core(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Leaf action: spawn a new core execution with leaf_result."""
        machine_yaml = context.get("return_machine_yaml") or context.get("self_machine_yaml")
        if not machine_yaml:
            context["spawn_error"] = "return_machine_yaml missing"
            return context

        input_data = {
            "session_id": context.get("session_id", self.session_id),
            "db_path": context.get("db_path", self.db_path),
            "leaf_result": context.get("leaf_result", ""),
        }
        return self._spawn_execution(context, machine_yaml, input_data, machine_type="core")

    def _spawn_execution(
        self,
        context: Dict[str, Any],
        machine_yaml: str,
        input_data: Dict[str, Any],
        machine_type: str = "machine",
    ) -> Dict[str, Any]:
        execution_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO executions (execution_id, session_id, parent_id, machine_type, tags, machine_yaml, snapshot, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (
                execution_id,
                self.session_id,
                self.execution_id,
                machine_type,
                "[]",
                machine_yaml,
                json.dumps({"input": input_data}),
                now,
            ),
        )
        conn.commit()
        conn.close()

        context["spawn_execution_id"] = execution_id
        return context

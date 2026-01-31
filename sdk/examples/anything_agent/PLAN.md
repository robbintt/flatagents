# Anything Agent: Inverted Control Architecture

## Overview

An autonomous agent system where machines dynamically launch successor machines with specific capabilities for the goal and tasks. Human oversight via SQLite-based approval with snapshot/restore—no long-running processes.

**Core Principle**: Inversion of control. Machine decides what to do next—continue working, launch a successor with different capabilities, or terminate. No automatic cycling; each machine is self-contained.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI (observer.py)                          │
│   Polls pending_approvals, displays context, writes decisions        │
│   On approve: restores machine from snapshot, continues execution    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SQLite Database                              │
│  Tables:                                                             │
│   - lineage (execution_id, machine_yaml, agent_yamls, snapshot)     │
│   - pending_approvals (execution_id, state, context, transition_to) │
└─────────────────────────────────────────────────────────────────────┘
```

**Key insight**: No long-running machine process. Every human decision point:
1. Snapshot machine state to `lineage`
2. Insert `pending_approvals` row
3. Exit process
4. CLI polls, human approves → CLI restores from snapshot, continues

---

## Data Model

```sql
-- Sessions: group of machines working toward one goal
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,              -- active | paused | completed | failed
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Ledger: structured context that persists across machines in a session
CREATE TABLE ledger (
    session_id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    progress TEXT NOT NULL DEFAULT '', -- Structured milestones, not raw history
    techniques TEXT NOT NULL DEFAULT '',
    failed_approaches TEXT NOT NULL DEFAULT '',
    human_notes TEXT NOT NULL DEFAULT '', -- Timestamped human observer notes
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Machine executions: full audit trail, queryable by future machines
CREATE TABLE executions (
    execution_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    parent_id TEXT,                    -- Parent execution (for delegation chains)
    machine_type TEXT NOT NULL,        -- core | leaf | planner | task | custom
    tags TEXT NOT NULL DEFAULT '[]',   -- JSON array of tags for filtering
    machine_yaml TEXT NOT NULL,
    agent_yamls TEXT NOT NULL,         -- JSON: {name: yaml}
    snapshot TEXT,                     -- JSON: MachineSnapshot for resume
    status TEXT NOT NULL,              -- pending | running | suspended | terminated
    input_tokens INTEGER,              -- Total input tokens used
    output_tokens INTEGER,             -- Total output tokens used
    created_at TEXT NOT NULL,
    terminated_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Leaf results: stored separately, queryable, can be pruned
CREATE TABLE leaf_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    result_type TEXT NOT NULL,         -- web_search | code_exec | file_read | etc.
    result_json TEXT NOT NULL,
    token_count INTEGER,               -- Estimated tokens if stringified
    created_at TEXT NOT NULL,
    pruned INTEGER DEFAULT 0,          -- 1 if pruned from active context
    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
);

-- Pending approvals with human input field
CREATE TABLE pending_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    state_name TEXT NOT NULL,
    context_json TEXT NOT NULL,
    proposed_transition TEXT NOT NULL,
    status TEXT NOT NULL,              -- pending | approved | stopped
    human_note TEXT,                   -- Optional note from human on approval
    created_at TEXT NOT NULL,
    responded_at TEXT,
    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
);

CREATE TABLE validation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    errors_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX idx_executions_session ON executions(session_id);
CREATE INDEX idx_executions_type ON executions(machine_type);
CREATE INDEX idx_leaf_results_session ON leaf_results(session_id);
CREATE INDEX idx_pending_session ON pending_approvals(session_id, status);
```

### Ledger Schema

The ledger is the structured context that flows between machines. Clear fields, not freeform:

```python
@dataclass
class Ledger:
    goal: str                          # Original objective
    progress: list[Milestone]          # Structured milestones
    techniques: list[Technique]        # What works
    failed_approaches: list[Failure]   # What to avoid
    human_notes: list[HumanNote]       # Timestamped observer notes

@dataclass
class Milestone:
    timestamp: str
    description: str
    source: str                        # execution_id that produced this

@dataclass
class Technique:
    name: str
    description: str
    success_count: int

@dataclass
class Failure:
    approach: str
    reason: str
    timestamp: str

@dataclass
class HumanNote:
    timestamp: str
    note: str
    execution_id: str                  # Which execution it was added to
```

---

## Machine Pattern

### Two-Tier Hierarchy

**Core Machine** (goal-driven, self-improving)
```
┌─────────────────────────────────────────────────────────────┐
│  Context accumulates:                                        │
│   - goal (original objective)                               │
│   - progress (what's been done)                             │
│   - techniques (what's working)                             │
│   - failed_approaches (what to avoid)                       │
│   - leaf_results (outputs from delegated work)              │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Decision loop:                                              │
│   1. Assess: What's needed next for goal?                   │
│   2. Can I do it with my actions? → Do it, update progress  │
│   3. Need external capability? → Delegate to leaf           │
│   4. Goal complete? → Done                                  │
└─────────────────────────────────────────────────────────────┘
```

**Leaf Machine** (stateless worker)
```
┌─────────────────────────────────────────────────────────────┐
│  Single task: web_search, code_exec, file_ops, etc.         │
│  Input: task spec from core                                 │
│  Output: result                                             │
│  On complete: launches stored core copy with result         │
└─────────────────────────────────────────────────────────────┘
```

### Delegation Flow

```
Core Machine                         Leaf Machine
────────────                         ────────────
1. Working on goal
2. Need web search (not in my actions)
3. Store self (core copy + current context)
4. Generate leaf spec for web_search
5. Launch leaf with {task, core_copy}
6. Terminate
                                     7. Do web search
                                     8. Launch core_copy with {leaf_result}
                                     9. Terminate

Core Machine Copy Launched
──────────────────────────
10. Resume with leaf_result in context
11. Continue toward goal...
```

### Aggressive Context Management

**Target: <20% of model context**. Models perform better with lean context. Prune proactively, not reactively.

```
┌─────────────────────────────────────────────────────────────┐
│  load_context action (non-LLM):                              │
│   1. Fetch ledger from SQLite                               │
│   2. Estimate tokens (tiktoken + char ratio)                │
│   3. Apply logarithmic history compression                  │
│   4. Prune aggressively to stay under 20% budget            │
│   5. Return lean context                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  cleanup_context action (after each agent call):             │
│   1. Check result usefulness                                │
│   2. If useless: log one-line to failures, clear result     │
│   3. del/clear intermediate fields before next call         │
│   4. Keep only what's needed for next step                  │
└─────────────────────────────────────────────────────────────┘
```

### Logarithmic History Compression

History grows but stays bounded. Recent = detailed, old = summarized.

```python
def compress_history(milestones: list[Milestone], execution_count: int) -> list[Milestone]:
    """
    Keep history logarithmic against execution count.
    
    Example with 100 executions:
    - Last 5: full detail
    - Previous 10: summarized to 3 entries  
    - Previous 25: summarized to 2 entries
    - Everything before: single "early progress" entry
    """
    if len(milestones) <= 5:
        return milestones
    
    recent = milestones[-5:]                    # Last 5: keep full
    older = milestones[:-5]
    
    # Compress older into buckets
    compressed = []
    bucket_sizes = [10, 25, 50]  # Logarithmic buckets
    
    for bucket_size in bucket_sizes:
        if len(older) <= bucket_size:
            # Summarize remaining into one entry
            if older:
                compressed.append(Milestone(
                    timestamp=older[0].timestamp,
                    description=f"[{len(older)} steps] " + "; ".join(m.description[:30] for m in older[:3]) + "...",
                    source="compressed"
                ))
            break
        else:
            # Take bucket, summarize, continue
            bucket = older[:bucket_size]
            older = older[bucket_size:]
            compressed.append(Milestone(
                timestamp=bucket[0].timestamp,
                description=f"[{len(bucket)} steps] " + "; ".join(m.description[:30] for m in bucket[:2]) + "...",
                source="compressed"
            ))
    
    return compressed + recent
```

### Token Estimation

Use multiple methods, log both:

```python
# context.py

from pathlib import Path

def load_guidance() -> str:
    """Load GUIDANCE.md (~400 tokens)."""
    guidance_path = Path(__file__).parent.parent.parent / "GUIDANCE.md"
    return guidance_path.read_text()

def estimate_tokens(text: str) -> dict:
    """Estimate tokens using multiple methods."""
    # Character ratio (~4 chars/token, rough)
    char_estimate = len(text) // 4
    
    # tiktoken (accurate, if available)
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

# Logging example:
# 📊 Context: 12,345/40,000 tokens (tiktoken: 12,345, char: 12,890)
# 📋 Guidance: 317 tokens
```

### Context Loading

```python
def load_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """Non-LLM action: load ledger, prune aggressively."""
    session_id = context["session_id"]
    
    # GLM 4.7 via Cerebras: 200K context
    # Target 20% = 40K tokens
    # Minimum 12K (model needs 8-11K for thinking)
    model_limit = 200000
    target_pct = 0.20
    budget = max(int(model_limit * target_pct), 12000)  # 40K target, 12K floor
    
    # Load GUIDANCE.md (~400 tokens, always included)
    guidance = load_guidance()
    guidance_tokens = estimate_tokens(guidance)["used"]
    
    # Remaining budget for ledger
    ledger_budget = budget - guidance_tokens
    
    # Fetch and compress
    ledger = self._fetch_ledger(session_id)
    ledger.progress = compress_history(ledger.progress)
    
    tokens = estimate_tokens(self._serialize_ledger(ledger))
    
    # Prune if over ledger budget
    while tokens["used"] > ledger_budget and len(ledger.progress) > 1:
        ledger.progress = ledger.progress[1:]
        tokens = estimate_tokens(self._serialize_ledger(ledger))
    
    context["guidance"] = guidance
    context["ledger"] = ledger
    context["token_estimate"] = tokens
    context["token_budget"] = budget
    context["guidance_tokens"] = guidance_tokens
    
    total = tokens["used"] + guidance_tokens
    print(f"📊 Context: {total:,}/{budget:,} tokens "
          f"(ledger: {tokens['used']:,}, guidance: {guidance_tokens})")
    return context
```

### Agent Prompts

Non-leaf agents include GUIDANCE.md in system prompt:

```yaml
# agents/thinker.yml
spec: flatagent
spec_version: "0.9.0"

data:
  name: thinker
  model: default
  
  system: |
    {{ context.guidance }}
    
    ---
    
    Goal: {{ context.ledger.goal }}
    
    Progress ({{ context.ledger.progress | length }} milestones):
    {% for m in context.ledger.progress[-5:] %}
    - {{ m.description }}
    {% endfor %}
    
    Techniques: {% for t in context.ledger.techniques %}{{ t.name }}; {% endfor %}
    
    Avoid: {% for f in context.ledger.failed_approaches[-3:] %}{{ f.approach }}; {% endfor %}
    
    Human notes: {% for n in context.ledger.human_notes[-3:] %}{{ n.note }}; {% endfor %}
    
    Tokens: {{ context.token_estimate.used }}/{{ context.token_budget }}
  
  user: |
    What's the next step toward the goal?
  
  output:
    action:
      type: str
      enum: ["work", "delegate", "done"]
    detail:
      type: str
      description: "What to do, or why done"
    new_technique:
      type: object
      required: false
      properties:
        name: { type: str }
        description: { type: str }
```

Leaf agents do NOT include GUIDANCE.md—they're stateless workers:

```yaml
# agents/executor.yml (leaf)
spec: flatagent
spec_version: "0.9.0"

data:
  name: executor
  model: default
  
  system: |
    Execute the task. Return the result. Be concise.
  
  user: |
    Task: {{ input.task }}
  
  output:
    result:
      type: str
```

### Core Machine Template

```yaml
spec: flatmachine
spec_version: "0.9.0"

data:
  name: core
  
  # Machine classification
  metadata:
    type: core
    tags: ["goal-driven", "self-improving"]
  
  context:
    session_id: "{{ input.session_id }}"
    db_path: "{{ input.db_path }}"
    model_token_limit: 200000     # GLM 4.7 via Cerebras
    context_target_pct: 0.20      # Target 20% = 40K
    context_minimum: 12000        # Floor (model needs 8-11K for thinking)
    leaf_result: "{{ input.leaf_result | default(none) }}"
  
  agents:
    thinker: ./thinker.yml
    worker: ./worker.yml
    planner: ./planner.yml
    reflector: ./reflector.yml
  
  states:
    start:
      type: initial
      transitions:
        - to: load_context

    # Token-aware context loading (non-LLM)
    load_context:
      action: load_context
      # Fetches ledger, prunes to fit token budget
      transitions:
        - condition: "context.leaf_result != none"
          to: process_leaf_result
        - to: think

    process_leaf_result:
      agent: reflector
      input:
        leaf_result: "{{ context.leaf_result }}"
        ledger: "{{ context.ledger }}"
      output_to_context:
        ledger_update: "{{ output.ledger_update }}"
      transitions:
        - to: save_ledger_after_leaf

    save_ledger_after_leaf:
      action: save_ledger
      transitions:
        - to: think

    think:
      agent: thinker
      input:
        ledger: "{{ context.ledger }}"
        token_budget: "{{ context.token_budget }}"
      output_to_context:
        next_action: "{{ output.action }}"        # work | delegate | done
        action_detail: "{{ output.detail }}"
      transitions:
        - condition: "context.next_action == 'done'"
          to: save_and_done
        - condition: "context.next_action == 'delegate'"
          to: plan_leaf
        - to: work

    work:
      agent: worker
      input:
        task: "{{ context.action_detail }}"
        ledger: "{{ context.ledger }}"
      output_to_context:
        work_result: "{{ output.result }}"
        work_success: "{{ output.success }}"
      transitions:
        - to: cleanup_after_work

    # Aggressive cleanup: clear useless results immediately
    cleanup_after_work:
      action: cleanup_context
      # If work_result useless: log one-line failure, clear it
      # Clear action_detail, intermediate fields
      transitions:
        - to: reflect

    reflect:
      agent: reflector
      input:
        work_result: "{{ context.work_result }}"
        work_success: "{{ context.work_success }}"
        ledger: "{{ context.ledger }}"
      output_to_context:
        ledger_update: "{{ output.ledger_update }}"
      transitions:
        - to: cleanup_after_reflect

    cleanup_after_reflect:
      action: cleanup_context
      # Clear work_result, work_success after reflection extracted value
      transitions:
        - to: save_ledger

    save_ledger:
      action: save_ledger
      # Persists ledger_update to SQLite
      transitions:
        - to: load_context  # Reload with compression

    plan_leaf:
      agent: planner
      input:
        task: "{{ context.action_detail }}"
        ledger: "{{ context.ledger }}"
      output_to_context:
        leaf_spec: "{{ output.machine_yaml }}"
        leaf_agents: "{{ output.agent_yamls }}"
        leaf_tags: "{{ output.tags }}"            # e.g., ["web_search", "research"]
      transitions:
        - to: validate_leaf

    validate_leaf:
      action: validate_specs
      transitions:
        - condition: "context.validation_passed"
          to: delegate_to_leaf
        - to: plan_leaf

    delegate_to_leaf:
      action: delegate_to_leaf
      transitions:
        - to: suspended

    suspended:
      type: final
      output:
        status: "delegated"
        leaf_id: "{{ context.leaf_id }}"

    save_and_done:
      action: save_ledger
      transitions:
        - to: done

    done:
      type: final
      output:
        status: "completed"
```

### Leaf Machine Template

```yaml
spec: flatmachine
spec_version: "0.9.0"

data:
  name: leaf_worker
  
  # Machine classification (planner sets these)
  metadata:
    type: leaf
    tags: []  # e.g., ["web_search", "research"]
  
  context:
    session_id: "{{ input.session_id }}"
    db_path: "{{ input.db_path }}"
    task: "{{ input.task }}"
    core_copy_id: "{{ input.core_copy_id }}"
    result_type: "{{ input.result_type }}"  # web_search | code_exec | etc.
  
  agents:
    executor: ./executor.yml  # Task-specific agent
  
  states:
    start:
      type: initial
      transitions:
        - to: execute

    execute:
      agent: executor
      input:
        task: "{{ context.task }}"
      output_to_context:
        result: "{{ output.result }}"
      transitions:
        - to: save_result

    save_result:
      action: save_leaf_result
      # Stores result in leaf_results table with token estimate
      transitions:
        - to: return_to_core

    return_to_core:
      action: launch_core_with_result
      transitions:
        - to: done

    done:
      type: final
      output:
        status: "returned"
```

### Machine Types

Machines self-classify via `metadata.type`:

| Type | Purpose |
|------|---------|
| `core` | Goal-driven, accumulates context, delegates |
| `leaf` | Stateless worker, single task, returns result |
| `planner` | Generates machine specs (could be leaf or standalone) |
| `task` | Simple task wrapper (like leaf but doesn't return to core) |

Tags are freeform for filtering: `["web_search", "research", "code", "file_ops"]`

Future machines can query past executions:
```sql
SELECT * FROM executions 
WHERE session_id = ? AND tags LIKE '%"web_search"%'
ORDER BY created_at DESC LIMIT 5;
```

---

## Hooks Implementation

```python
# hooks.py
import sqlite3
import json
import uuid
from typing import Dict, Any
from flatagents import MachineHooks

class AnythingAgentHooks(MachineHooks):
    """
    Hooks for Anything Agent.
    
    Every transition snapshots to DB, inserts pending_approval, exits.
    CLI polls and restores on approval.
    """
    
    def __init__(self, db_path: str, execution_id: str = None):
        self.db_path = db_path
        self.execution_id = execution_id or str(uuid.uuid4())
    
    def on_transition(
        self,
        from_state: str,
        to_state: str,
        context: Dict[str, Any],
        machine  # FlatMachine instance for snapshot
    ) -> bool:
        """
        Snapshot state, insert pending approval, raise to exit.
        CLI will restore and continue after human approves.
        """
        conn = sqlite3.connect(self.db_path)
        
        # Update snapshot in lineage
        snapshot = machine.get_snapshot()
        conn.execute("""
            UPDATE lineage SET snapshot = ? WHERE execution_id = ?
        """, (json.dumps(snapshot), self.execution_id))
        
        # Insert pending approval
        conn.execute("""
            INSERT INTO pending_approvals 
            (execution_id, state_name, context_json, proposed_transition, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', datetime('now'))
        """, (
            self.execution_id,
            from_state,
            json.dumps(context),
            to_state
        ))
        
        conn.commit()
        conn.close()
        
        # Exit - CLI will restore after approval
        raise AwaitingApproval(self.execution_id, from_state, to_state)
    
    def on_action(self, action_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if action_name == "load_context":
            return self._load_context(context)
        elif action_name == "cleanup_context":
            return self._cleanup_context(context)
        elif action_name == "save_ledger":
            return self._save_ledger(context)
        elif action_name == "validate_specs":
            return self._validate_specs(context)
        elif action_name == "delegate_to_leaf":
            return self._delegate_to_leaf(context)
        elif action_name == "launch_core_with_result":
            return self._launch_core_with_result(context)
        return context
    
    def _load_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load ledger, compress history, stay under 20% budget."""
        from .context import fetch_ledger, compress_history, estimate_tokens
        
        session_id = context["session_id"]
        model_limit = context.get("model_token_limit", 8192)
        target_pct = context.get("context_target_pct", 0.20)
        budget = int(model_limit * target_pct)
        
        ledger = fetch_ledger(self.db_path, session_id)
        ledger["progress"] = compress_history(ledger["progress"])
        
        tokens = estimate_tokens(json.dumps(ledger))
        
        # Prune until under budget
        while tokens["used"] > budget and len(ledger["progress"]) > 1:
            ledger["progress"] = ledger["progress"][1:]
            tokens = estimate_tokens(json.dumps(ledger))
        
        context["ledger"] = ledger
        context["token_estimate"] = tokens
        context["token_budget"] = budget
        
        print(f"📊 Context: {tokens['used']}/{budget} tokens "
              f"(tiktoken: {tokens.get('tiktoken_estimate', 'N/A')}, "
              f"char: {tokens['char_estimate']})")
        return context
    
    def _cleanup_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Aggressive cleanup: clear intermediate fields, log failures."""
        # Check if work_result is useless
        work_result = context.get("work_result")
        if work_result and context.get("work_success") == False:
            # Log one-line failure, then clear
            failure_line = str(work_result)[:100].replace('\n', ' ')
            print(f"❌ Useless result logged: {failure_line}")
            # Add to ledger failures (will be saved on next save_ledger)
            if "ledger_update" not in context:
                context["ledger_update"] = {}
            context["ledger_update"]["new_failure"] = {
                "approach": context.get("action_detail", "unknown")[:50],
                "reason": failure_line,
                "timestamp": datetime.now().isoformat()
            }
        
        # Clear intermediate fields
        for field in ["work_result", "work_success", "action_detail", "leaf_result"]:
            if field in context and context[field] is not None:
                context[field] = None
        
        return context
    
    def _save_ledger(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Persist ledger updates to SQLite."""
        session_id = context["session_id"]
        update = context.get("ledger_update", {})
        
        if not update:
            return context
        
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        
        # Apply updates
        if "new_milestone" in update:
            cursor = conn.execute("SELECT progress FROM ledger WHERE session_id = ?", (session_id,))
            progress = json.loads(cursor.fetchone()[0] or "[]")
            progress.append(update["new_milestone"])
            conn.execute("UPDATE ledger SET progress = ?, updated_at = ? WHERE session_id = ?",
                        (json.dumps(progress), now, session_id))
        
        if "new_failure" in update:
            cursor = conn.execute("SELECT failed_approaches FROM ledger WHERE session_id = ?", (session_id,))
            failures = json.loads(cursor.fetchone()[0] or "[]")
            failures.append(update["new_failure"])
            conn.execute("UPDATE ledger SET failed_approaches = ?, updated_at = ? WHERE session_id = ?",
                        (json.dumps(failures), now, session_id))
        
        if "new_technique" in update:
            cursor = conn.execute("SELECT techniques FROM ledger WHERE session_id = ?", (session_id,))
            techniques = json.loads(cursor.fetchone()[0] or "[]")
            techniques.append(update["new_technique"])
            conn.execute("UPDATE ledger SET techniques = ?, updated_at = ? WHERE session_id = ?",
                        (json.dumps(techniques), now, session_id))
        
        conn.commit()
        conn.close()
        
        context["ledger_update"] = {}  # Clear after save
        return context
    
    def _validate_specs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generated specs, return errors in context."""
        from .validators import SpecValidator
        
        validator = SpecValidator()
        errors = []
        
        spec_key = "leaf_spec" if "leaf_spec" in context else "successor_spec"
        agents_key = "leaf_agents" if "leaf_agents" in context else "successor_agents"
        
        errors.extend(validator.validate_machine(context.get(spec_key, "")))
        for name, yaml_str in context.get(agents_key, {}).items():
            errors.extend(validator.validate_agent(yaml_str))
        
        if errors:
            self._log_validation(errors)
        
        context["validation_passed"] = len(errors) == 0
        context["validation_errors"] = [{"path": e.path, "msg": e.message} for e in errors]
        return context
    
    def _delegate_to_leaf(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store core copy, launch leaf with reference to core.
        Leaf will relaunch core with result.
        """
        leaf_id = str(uuid.uuid4())
        core_copy_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.db_path)
        
        # Get current core spec
        cursor = conn.execute(
            "SELECT machine_yaml, agent_yamls FROM lineage WHERE execution_id = ?",
            (self.execution_id,)
        )
        row = cursor.fetchone()
        core_yaml, core_agents = row[0], row[1]
        
        # Store core copy (with current context as input for relaunch)
        core_input = {
            "goal": context.get("goal"),
            "progress": context.get("progress"),
            "techniques": context.get("techniques"),
            "failed_approaches": context.get("failed_approaches"),
            # leaf_result will be added by leaf when relaunching
        }
        conn.execute("""
            INSERT INTO lineage 
            (execution_id, parent_id, machine_yaml, agent_yamls, snapshot, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'stored', datetime('now'))
        """, (
            core_copy_id,
            self.execution_id,
            core_yaml,
            core_agents,
            json.dumps({"input": core_input})  # Store input for relaunch
        ))
        
        # Launch leaf with task + core_copy reference
        conn.execute("""
            INSERT INTO lineage 
            (execution_id, parent_id, machine_yaml, agent_yamls, snapshot, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'))
        """, (
            leaf_id,
            self.execution_id,
            context["leaf_spec"],
            json.dumps(context["leaf_agents"]),
            json.dumps({"input": {
                "task": context["action_detail"],
                "core_copy_id": core_copy_id,
                "db_path": context["db_path"]
            }})
        ))
        
        # Mark self as terminated
        conn.execute("""
            UPDATE lineage SET status = 'terminated' WHERE execution_id = ?
        """, (self.execution_id,))
        
        conn.commit()
        conn.close()
        
        context["leaf_id"] = leaf_id
        context["core_copy_id"] = core_copy_id
        return context
    
    def _launch_core_with_result(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Leaf completes: launch stored core copy with leaf result.
        """
        core_copy_id = context["core_copy_id"]
        new_core_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.db_path)
        
        # Get stored core copy
        cursor = conn.execute(
            "SELECT machine_yaml, agent_yamls, snapshot FROM lineage WHERE execution_id = ?",
            (core_copy_id,)
        )
        row = cursor.fetchone()
        core_yaml, core_agents, core_snapshot = row[0], row[1], row[2]
        
        # Parse stored input, add leaf result
        stored = json.loads(core_snapshot)
        stored["input"]["leaf_result"] = context["result"]
        
        # Launch new core instance
        conn.execute("""
            INSERT INTO lineage 
            (execution_id, parent_id, machine_yaml, agent_yamls, snapshot, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'))
        """, (
            new_core_id,
            core_copy_id,
            core_yaml,
            core_agents,
            json.dumps(stored)
        ))
        
        # Mark leaf as terminated
        conn.execute("""
            UPDATE lineage SET status = 'terminated' WHERE execution_id = ?
        """, (self.execution_id,))
        
        conn.commit()
        conn.close()
        
        context["new_core_id"] = new_core_id
        return context


class AwaitingApproval(Exception):
    """Raised to exit process and await human approval."""
    def __init__(self, execution_id: str, from_state: str, to_state: str):
        self.execution_id = execution_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Awaiting approval: {from_state} → {to_state}")
```

---

## CLI (Observer + Runner)

```python
# observer.py
"""
CLI that polls for pending approvals and restores machines on approval.
Based on human-in-the-loop pattern with prompt_toolkit.
"""
import sqlite3
import json
import asyncio
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML

from flatagents import FlatMachine
from .hooks import AnythingAgentHooks, AwaitingApproval

session = PromptSession()

async def run_loop(db_path: str):
    """Main CLI loop: poll, display, approve/stop, restore, repeat."""
    print(f"🔍 Anything Agent Observer")
    print(f"📁 Database: {db_path}")
    print("Commands: [a]pprove, [s]top, [q]uit, [n]ote (approve with note)")
    print("-" * 60)
    
    while True:
        # Check for pending approvals
        pending = get_pending(db_path)
        
        if not pending:
            # Check for pending executions (from launches)
            pending_exec = get_pending_execution(db_path)
            if pending_exec:
                print(f"\n⏳ Starting pending execution {pending_exec['execution_id'][:8]}...")
                await run_execution(pending_exec, db_path)
            else:
                await asyncio.sleep(1)
            continue
        
        # Display and get decision
        approval = pending[0]
        display_approval(approval)
        
        response = await session.prompt_async(HTML('<b>Decision [a/s/n/q]: </b>'))
        response = response.strip().lower()
        
        if response in ('a', 'approve', ''):
            approve(db_path, approval['id'], approval['session_id'])
            print("✅ Approved. Restoring machine...")
            await restore_and_continue(approval['execution_id'], db_path)
        elif response in ('n', 'note'):
            note = await session.prompt_async(HTML('<b>Note: </b>'))
            note = note.strip()
            if note:
                approve(db_path, approval['id'], approval['session_id'], note)
                print(f"✅ Approved with note. Restoring machine...")
            else:
                approve(db_path, approval['id'], approval['session_id'])
                print("✅ Approved. Restoring machine...")
            await restore_and_continue(approval['execution_id'], db_path)
        elif response in ('s', 'stop'):
            stop(db_path, approval['id'])
            print("🛑 Stopped. Session paused.")
        elif response in ('q', 'quit'):
            print("Goodbye.")
            break

async def restore_and_continue(execution_id: str, db_path: str):
    """Restore machine from snapshot and continue execution."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM lineage WHERE execution_id = ?", 
        (execution_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row or not row['snapshot']:
        print(f"❌ No snapshot for {execution_id}")
        return
    
    await run_execution(dict(row), db_path)

async def run_execution(row: dict, db_path: str):
    """Run a machine from lineage row."""
    import yaml
    
    execution_id = row['execution_id']
    machine_config = yaml.safe_load(row['machine_yaml'])
    snapshot = json.loads(row['snapshot']) if row.get('snapshot') else None
    
    # Mark as running
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE lineage SET status = 'running' WHERE execution_id = ?", (execution_id,))
    conn.commit()
    conn.close()
    
    hooks = AnythingAgentHooks(db_path, execution_id)
    machine = FlatMachine(config=machine_config, hooks=hooks)
    
    try:
        if snapshot:
            result = await machine.execute(resume_from_snapshot=snapshot)
        else:
            result = await machine.execute(input={"db_path": db_path})
        print(f"✅ Execution complete: {result}")
    except AwaitingApproval as e:
        print(f"⏸️  Paused at {e.from_state} → {e.to_state}. Awaiting approval...")

def display_approval(approval: dict):
    """Display pending approval."""
    print(f"\n{'═' * 60}")
    print(f"Pending: {approval['execution_id'][:8]}...")
    print(f"State: {approval['state_name']} → {approval['proposed_transition']}")
    print(f"\nContext:")
    context = json.loads(approval['context_json'])
    for k, v in list(context.items())[:10]:  # Limit display
        print(f"  {k}: {str(v)[:80]}")
    print('═' * 60)

def get_pending(db_path: str) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at"
    )
    result = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return result

def get_pending_execution(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM lineage WHERE status = 'pending' ORDER BY created_at LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def approve(db_path: str, approval_id: int, session_id: str, note: str = None):
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()
    
    # Update approval
    conn.execute("""
        UPDATE pending_approvals 
        SET status = 'approved', human_note = ?, responded_at = ?
        WHERE id = ?
    """, (note, now, approval_id))
    
    # If note provided, append to ledger.human_notes
    if note:
        cursor = conn.execute(
            "SELECT human_notes FROM ledger WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        notes = json.loads(row[0]) if row and row[0] else []
        notes.append({
            "timestamp": now,
            "note": note,
            "approval_id": approval_id
        })
        conn.execute("""
            UPDATE ledger SET human_notes = ?, updated_at = ?
            WHERE session_id = ?
        """, (json.dumps(notes), now, session_id))
    
    conn.commit()
    conn.close()

def stop(db_path: str, approval_id: int):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE pending_approvals SET status = 'stopped' WHERE id = ?",
        (approval_id,)
    )
    # Also mark lineage as suspended
    cursor = conn.execute(
        "SELECT execution_id FROM pending_approvals WHERE id = ?",
        (approval_id,)
    )
    exec_id = cursor.fetchone()[0]
    conn.execute(
        "UPDATE lineage SET status = 'suspended' WHERE execution_id = ?",
        (exec_id,)
    )
    conn.commit()
    conn.close()
```

---

## Entry Point

```python
# main.py
import argparse
import asyncio
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flatagents import FlatMachine
from .hooks import AnythingAgentHooks, AwaitingApproval
from .observer import run_loop

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
    agent_yamls TEXT NOT NULL,
    snapshot TEXT,
    status TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at TEXT NOT NULL,
    terminated_at TEXT
);

CREATE TABLE IF NOT EXISTS leaf_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    result_type TEXT NOT NULL,
    result_json TEXT NOT NULL,
    token_count INTEGER,
    created_at TEXT NOT NULL,
    pruned INTEGER DEFAULT 0
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

CREATE TABLE IF NOT EXISTS validation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    errors_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_executions_session ON executions(session_id);
CREATE INDEX IF NOT EXISTS idx_pending_session ON pending_approvals(session_id, status);
"""

def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

async def start_goal(goal: str, db_path: str):
    """Start new session with goal."""
    session_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    bootstrap_path = Path(__file__).parent / "machines" / "core.yml"
    with open(bootstrap_path) as f:
        machine_yaml = f.read()
    
    conn = sqlite3.connect(db_path)
    
    # Create session
    conn.execute("""
        INSERT INTO sessions (session_id, goal, status, created_at, updated_at)
        VALUES (?, ?, 'active', ?, ?)
    """, (session_id, goal, now, now))
    
    # Initialize ledger
    conn.execute("""
        INSERT INTO ledger (session_id, goal, updated_at)
        VALUES (?, ?, ?)
    """, (session_id, goal, now))
    
    # Create initial execution
    conn.execute("""
        INSERT INTO executions 
        (execution_id, session_id, machine_type, tags, machine_yaml, agent_yamls, status, created_at)
        VALUES (?, ?, 'core', '["initial"]', ?, '{}', 'pending', ?)
    """, (execution_id, session_id, machine_yaml, now))
    
    conn.commit()
    conn.close()
    
    print(f"🚀 Session {session_id[:8]}... created")
    print(f"   Goal: {goal}")
    print(f"   Run './run.sh observe' to approve transitions")

async def resume_session(session_id: str, db_path: str):
    """Resume a paused session."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE sessions SET status = 'active', updated_at = ? WHERE session_id = ?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()
    conn.close()
    print(f"▶️  Session {session_id[:8]}... resumed")

def list_sessions(db_path: str):
    """List all sessions."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT session_id, goal, status, created_at 
        FROM sessions ORDER BY created_at DESC LIMIT 20
    """)
    rows = cursor.fetchall()
    conn.close()
    
    print(f"{'Session':<12} {'Status':<10} {'Goal':<40} {'Created'}")
    print("-" * 80)
    for r in rows:
        print(f"{r['session_id'][:10]}.. {r['status']:<10} {r['goal'][:38]:<40} {r['created_at'][:16]}")

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
        asyncio.run(start_goal(args.goal, args.db))
    elif args.command == "resume":
        if not args.session:
            parser.error("--session required")
        asyncio.run(resume_session(args.session, args.db))
    elif args.command == "list":
        list_sessions(args.db)
    elif args.command == "observe":
        asyncio.run(run_loop(args.db))

if __name__ == "__main__":
    main()
```

---

## Run Script

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

case ${1:-observe} in
    run)
        python -m anything_agent.main run --goal "$2"
        ;;
    resume)
        python -m anything_agent.main resume --session "$2"
        ;;
    list)
        python -m anything_agent.main list
        ;;
    observe)
        python -m anything_agent.main observe
        ;;
    status)
        echo "=== Sessions ==="
        sqlite3 -header -column ./anything_agent.db \
            "SELECT session_id, status, goal FROM sessions ORDER BY created_at DESC LIMIT 5"
        echo ""
        echo "=== Recent Executions ==="
        sqlite3 -header -column ./anything_agent.db \
            "SELECT execution_id, machine_type, status FROM executions ORDER BY created_at DESC LIMIT 10"
        ;;
    *)
        echo "Usage: ./run.sh [run 'goal'|resume <session>|list|observe|status]"
        ;;
esac
```

---

## Model Configuration

Single model: **GLM 4.7 via Cerebras**

```yaml
# config/profiles.yml
spec: flatprofiles
spec_version: "0.9.0"

data:
  model_profiles:
    default:
      provider: cerebras
      name: zai-glm-4.7
      temperature: 0.9
      top_p: 0.95
      max_tokens: 2048

  default: default
```

- Context limit: 200K tokens
- Target: 20% = 40K tokens
- Minimum: 12K tokens (model needs 8-11K for thinking)
- GUIDANCE.md: ~400 tokens, always included in non-leaf agents

---

## File Structure

```
anything_agent/
├── PLAN.md
├── GUIDANCE.md          # ~400 tokens, hardcoded into non-leaf agents
├── run.sh
├── pyproject.toml
├── src/anything_agent/
│   ├── __init__.py
│   ├── main.py          # Entry: run/observe
│   ├── hooks.py         # AnythingAgentHooks
│   ├── observer.py      # CLI with prompt_toolkit
│   ├── validators.py    # Spec validation
│   ├── context.py       # Token estimation, compression, guidance loading
│   └── machines/
│       └── core.yml
└── config/
    └── profiles.yml
```

---

## Summary

1. **Sessions**: Each goal is a session. Pause with Ctrl+C, resume later.

2. **Lean Context**: Target 20% of 200K = 40K tokens. Minimum 12K (model needs 8-11K for thinking).

3. **GUIDANCE.md**: ~400 token guidance hardcoded into all non-leaf agents. Goals, limitations, patterns.

4. **Logarithmic History**: Recent = detailed, old = compressed. Bounded growth.

5. **Immediate Cleanup**: Useless results → one-line failure log → clear before next call.

6. **Single Model**: GLM 4.7 via Cerebras, temp 0.9, top_p 0.95.

7. **Two-Tier Machines**:
   - **Core**: Goal-driven, includes GUIDANCE.md, reads/writes ledger
   - **Leaf**: Stateless worker, no guidance, single task

8. **Human Notes**: Every approval can include a note, added to ledger.

9. **Token Estimation**: Both tiktoken and char ratio, log both.

---

## Design Decisions

### Context Budget
**Decision**: 200K context, target 20% = 40K tokens. Minimum 12K floor (model needs 8-11K for thinking). Model can increase its cap if it explains why.

### GUIDANCE.md
**Decision**: ~400 token guidance document hardcoded into all non-leaf agents. Contains goals, limitations, patterns. LLM could drop it but human would stop execution.

### Aggressive Cleanup
**Decision**: After each agent call, `cleanup_context` action clears intermediate fields. Useless results → one-line failure log → delete immediately.

### Logarithmic History
**Decision**: History compresses as it ages. Last 5 milestones full detail, older buckets summarized. Bounded growth.

### Token Estimation
**Decision**: Both tiktoken (accurate) and char ratio (~4 chars/token). Log both estimates.

### Single Model
**Decision**: GLM 4.7 via Cerebras only. temp=0.9, top_p=0.95, max_tokens=2048.

### Human Input
**Decision**: Every approval can include a note. Timestamped, added to `ledger.human_notes`.

---

## Open Questions

### Technique Learning

How does reflector identify novel techniques?

Options:
1. **Explicit output**: Reflector outputs `new_technique: {name, description}` or null
2. **Human-guided**: Human notes flag techniques ("technique: X works for Y")

### Leaf Machine Library

Should there be predefined leaf templates?

Options:
1. **Generated only**: Planner generates from scratch each time
2. **Hybrid**: Query past successful leaves by tag, reuse or customize

---

## Implementation Order

1. **Schema + CLI**: SQLite schema, observer CLI with human notes
2. **Context module**: `estimate_tokens` (tiktoken + char), `compress_history` (logarithmic)
3. **Context actions**: `load_context`, `cleanup_context`, `save_ledger`
4. **Core machine**: thinker, worker, reflector agents + cleanup cycle
5. **Delegation**: `delegate_to_leaf` + `launch_core_with_result`
6. **Leaf template**: executor + `save_leaf_result` + return-to-core
7. **Validation**: Spec validators, self-correction loop
8. **Profiles**: Single GLM 4.7 profile

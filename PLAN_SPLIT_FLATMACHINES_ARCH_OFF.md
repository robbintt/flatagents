# Architectural Decoupling Analysis for FlatAgents SDK

## Executive Summary

This document analyzes the `flatagents` Python SDK to determine optimal architectural boundaries for separating the **Agent Execution Layer** (`flatagents`) from the **Orchestration Layer** (`flatmachines`).

**Key Finding**: The hypothesis that `flatmachines` is orthogonal to `flatagents` is **validated**. The codebase has a clear conceptual separation, but there are specific coupling points that require refactoring for a clean split.

---

## 1. Current Architecture Overview

### Python SDK Module Structure

```
sdk/python/flatagents/
├── __init__.py          # Package exports (mixed Agent + Machine exports)
├── flatagent.py         # FlatAgent class - single LLM call
├── flatmachine.py       # FlatMachine class - state machine orchestration
├── baseagent.py         # Base classes: LLMBackend, Extractor, MCPToolProvider
├── profiles.py          # Model profile resolution (shared)
├── validation.py        # Schema validation for both specs (shared)
├── monitoring.py        # Logging and metrics (shared)
├── utils.py             # Utility functions (shared)
├── expressions/         # Expression engines (Machine-only)
│   ├── __init__.py
│   ├── simple.py
│   └── cel.py
├── execution.py         # Execution types: Default, Retry, Parallel, MDAP (Agent-level)
├── hooks.py             # MachineHooks base class (Machine-only)
├── actions.py           # Actions and Invokers (Machine-only)
├── backends.py          # Result backends for inter-machine communication (Machine-only)
├── persistence.py       # Checkpointing: MachineSnapshot, PersistenceBackend (Machine-only)
├── locking.py           # Concurrency control (Machine-only)
├── distributed.py       # Worker orchestration backends (Machine-only)
├── distributed_hooks.py # Distributed worker hooks (Machine-only)
└── assets/              # Bundled JSON schemas (shared)
```

### Layer Classification

| Layer | Modules | Purpose |
|-------|---------|---------|
| **Agent Layer** | `flatagent.py`, `baseagent.py` | Single LLM call, prompt templating, output schema |
| **Machine Layer** | `flatmachine.py`, `hooks.py`, `actions.py`, `backends.py`, `persistence.py`, `locking.py`, `expressions/`, `distributed.py`, `distributed_hooks.py` | State machine orchestration, transitions, checkpointing |
| **Shared** | `profiles.py`, `validation.py`, `monitoring.py`, `utils.py`, `execution.py` | Common utilities used by both layers |

---

## 2. Dependency Graph

### Current Import Relationships

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              flatagents/__init__.py                         │
│  (Exports from ALL modules - Agent, Machine, and Shared)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   flatagent.py  │         │ flatmachine.py  │         │    hooks.py     │
│  (Agent Layer)  │         │ (Machine Layer) │         │ (Machine Layer) │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         ▼                           ▼                           │
┌─────────────────┐         ┌─────────────────┐                  │
│  baseagent.py   │◄────────│  IMPORTS FROM   │                  │
│  (Agent Layer)  │         │  flatagent.py   │◄─────────────────┘
└────────┬────────┘         │                 │
         │                  │  - FlatAgent    │
         │                  │  (line 33)      │
         │                  └────────┬────────┘
         │                           │
         ▼                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SHARED MODULES                            │
│  profiles.py, validation.py, monitoring.py, utils.py            │
└─────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MACHINE-ONLY MODULES                          │
│  expressions/, execution.py, backends.py, persistence.py,       │
│  locking.py, actions.py, distributed.py, distributed_hooks.py   │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Coupling Point

**`flatmachine.py` line 33**: 
```python
from .flatagent import FlatAgent
```

This is the **ONLY direct import** from Machine → Agent layer. The Machine uses FlatAgent to execute agent calls within states.

---

## 3. Agent Verification Logic Analysis

### Current Location of Verification

| Verification Type | Location | Layer | Notes |
|-------------------|----------|-------|-------|
| Spec validation (`spec: flatagent`) | `flatagent.py:_validate_spec()` | Agent | Checks envelope format |
| Schema validation (JSON Schema) | `validation.py:validate_flatagent_config()` | Shared | Uses bundled schemas |
| Version check | `utils.py:check_spec_version()` | Shared | Warns on mismatch |
| Model profile resolution | `profiles.py:resolve_model_config()` | Shared | Resolves profile names |
| Runtime model detection | `flatagent.py:_auto_detect_backend()` | Agent | Detects litellm/aisuite |

### Finding: Verification is Already Agent-Layer

All agent verification logic is contained within the Agent layer or shared utilities. There is **NO verification logic that has migrated to the Machine layer**. The Machine layer simply instantiates `FlatAgent` objects and calls them.

**Evidence from `flatmachine.py:_get_agent()`** (lines 425-447):
```python
def _get_agent(self, agent_name: str) -> FlatAgent:
    """Get or load an agent by name."""
    if agent_name in self._agents:
        return self._agents[agent_name]

    if agent_name not in self.agent_refs:
        raise ValueError(f"Unknown agent: {agent_name}")

    agent_ref = self.agent_refs[agent_name]

    # Handle file path reference
    if isinstance(agent_ref, str):
        if not os.path.isabs(agent_ref):
            agent_ref = os.path.join(self._config_dir, agent_ref)
        agent = FlatAgent(config_file=agent_ref, profiles_dict=self._profiles_dict)
    # Handle inline config (dict)
    elif isinstance(agent_ref, dict):
        agent = FlatAgent(config_dict=agent_ref, profiles_dict=self._profiles_dict)
    else:
        raise ValueError(f"Invalid agent reference: {agent_ref}")

    self._agents[agent_name] = agent
    return agent
```

The Machine simply creates FlatAgent instances - all validation happens in the FlatAgent constructor.

---

## 4. Checkpointing & Persistence Analysis

### Confirmation: Persistence is Machine-Layer Only

| Component | Module | Description |
|-----------|--------|-------------|
| `MachineSnapshot` | `persistence.py` | Wire format for checkpoints |
| `PersistenceBackend` | `persistence.py` | Abstract storage interface |
| `LocalFileBackend` | `persistence.py` | File-based persistence |
| `MemoryBackend` | `persistence.py` | In-memory persistence |
| `CheckpointManager` | `persistence.py` | Manages save/load operations |
| `checkpoint_events` | `flatmachine.py` | Configures when to checkpoint |

**Agent Layer is Stateless**: The `FlatAgent` class maintains only call-level state (`total_cost`, `total_api_calls`) that is reset between calls. It has no knowledge of:
- Execution history
- Previous states
- Checkpoint/resume
- Execution IDs

---

## 5. Execution Flow: Cutting Point Identification

### Machine → Agent Execution Trace

```
1. FlatMachine.execute(input)
   │
2. └─► _execute_state(state_name, context)
       │
3.     └─► Check state config for 'agent' key
           │
4.         └─► _get_agent(agent_name)              ┐
               │                                   │
5.             └─► FlatAgent(config_file/dict)     │ CUTTING POINT
               │                                   │
6.         └─► execution_type.execute(agent, input)│
               │                                   ┘
7.             └─► agent.call(**input)
                   │
8.                 └─► LLM call via litellm/aisuite
```

**The Cutting Point** is between steps 4-6:
- Step 4: Machine resolves agent reference to config
- Step 5: FlatAgent is instantiated (Agent layer takes over)
- Step 6: ExecutionType wraps the agent call (Machine-layer retry/parallel logic)

---

## 6. Proposed Cutting Points: 3 Implementation Options

### Option A: Conservative Split (Recommended)

**Philosophy**: Minimal disruption. Keep `execution.py` in the Agent layer as it wraps agent calls.

```
flatagents/                      flatmachines/
├── __init__.py                  ├── __init__.py
├── flatagent.py                 ├── flatmachine.py
├── baseagent.py                 ├── hooks.py
├── profiles.py                  ├── actions.py
├── validation.py                ├── backends.py
├── monitoring.py                ├── persistence.py
├── utils.py                     ├── locking.py
├── execution.py                 ├── expressions/
└── assets/                      ├── distributed.py
    ├── flatagent.schema.json    ├── distributed_hooks.py
    └── profiles.schema.json     └── assets/
                                     └── flatmachine.schema.json
```

**Dependency**: `flatmachines` depends on `flatagents`

**Pro**: 
- Execution types (retry, parallel, MDAP) stay with Agent since they wrap `agent.call()`
- Clean API: `from flatagents import FlatAgent`, `from flatmachines import FlatMachine`

**Con**:
- Two packages to maintain

### Option B: Aggressive Split

**Philosophy**: Only raw LLM calling in Agent layer. All orchestration concepts move to Machine.

```
flatagents-core/                 flatmachines/
├── __init__.py                  ├── __init__.py
├── flatagent.py                 ├── flatmachine.py
├── baseagent.py                 ├── hooks.py
└── assets/                      ├── actions.py
                                 ├── backends.py
                                 ├── persistence.py
                                 ├── locking.py
                                 ├── expressions/
                                 ├── execution.py  # Moved here
                                 ├── profiles.py   # Moved here
                                 ├── validation.py # Moved here
                                 ├── monitoring.py # Moved here
                                 ├── utils.py      # Moved here
                                 ├── distributed.py
                                 └── distributed_hooks.py
```

**Pro**:
- `flatagents-core` is extremely minimal
- All complexity in one package

**Con**:
- Profiles and validation are duplicated or Machine-specific
- Harder for users who just want a simple agent

### Option C: Interface-Based Split (Plugin Architecture)

**Philosophy**: Define an abstract `AgentExecutor` protocol that Machine uses. Allows swapping agent implementations.

```python
# flatagents/protocols.py
from typing import Protocol, Dict, Any

class AgentExecutor(Protocol):
    """Protocol for executing agents. FlatMachine depends on this, not FlatAgent."""
    
    async def execute(
        self, 
        config: Dict[str, Any], 
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        ...

# flatagents/flatagent.py
class FlatAgent:
    """Concrete implementation of AgentExecutor."""
    ...

# flatmachines/flatmachine.py
class FlatMachine:
    def __init__(self, ..., agent_executor: AgentExecutor = None):
        self._agent_executor = agent_executor or FlatAgentExecutor()
```

**Pro**:
- Loose coupling via protocol
- Easy to swap agent implementations (e.g., mock agents for testing)
- Future-proof for alternative executors

**Con**:
- More complex
- Requires careful protocol design

---

## 7. Coupling Analysis: Shared Code Inventory

### Shared Utilities (Must Be Handled)

| Module | Current Users | Recommendation |
|--------|---------------|----------------|
| `profiles.py` | FlatAgent, FlatMachine | Keep in `flatagents`, import in `flatmachines` |
| `validation.py` | FlatAgent, FlatMachine | Keep in `flatagents`, `flatmachines` adds its own |
| `monitoring.py` | All modules | Keep in `flatagents`, import in `flatmachines` |
| `utils.py` | FlatAgent, FlatMachine | Keep in `flatagents`, import in `flatmachines` |

### Execution Types (Special Case)

`execution.py` contains:
- `ExecutionType` base class
- `DefaultExecution` - single call
- `RetryExecution` - retry with backoff
- `ParallelExecution` - N parallel calls
- `MDAPVotingExecution` - multi-sample voting

**Current Usage**: Only called from `flatmachine.py:_execute_state()` (line 1024):
```python
execution_config = state.get('execution')
execution_type = get_execution_type(execution_config)
output = await execution_type.execute(agent, agent_input)
```

**Recommendation**: Keep in Agent layer as these wrap `agent.call()` directly.

### MCP Configuration

MCP appears in both schemas:
- `flatagent.d.ts`: `MCPConfig`, `MCPServerDef`, `ToolFilter`
- Used only in `flatagent.py` for tool discovery

**Conclusion**: MCP is Agent-layer only. No action needed.

---

## 8. Refactoring Strategy

### Phase 1: Create `flatagents` as Standalone Package

1. **Extract Agent-Layer Modules**:
   ```
   flatagents/
   ├── __init__.py           # Export: FlatAgent, LLMBackend, Extractor, etc.
   ├── flatagent.py
   ├── baseagent.py
   ├── profiles.py
   ├── validation.py
   ├── monitoring.py
   ├── utils.py
   ├── execution.py
   └── assets/
       ├── flatagent.schema.json
       └── profiles.schema.json
   ```

2. **Define Public API**:
   ```python
   # flatagents/__init__.py
   from .flatagent import FlatAgent
   from .baseagent import (
       LLMBackend, LiteLLMBackend, AISuiteBackend,
       Extractor, FreeExtractor, StructuredExtractor, ToolsExtractor,
       MCPToolProvider, ToolCall, AgentResponse
   )
   from .profiles import ProfileManager, resolve_model_config
   from .validation import validate_flatagent_config, get_flatagent_schema
   from .monitoring import setup_logging, get_logger, get_meter, AgentMonitor
   from .execution import ExecutionType, DefaultExecution, RetryExecution, ...
   ```

3. **Create `pyproject.toml`**:
   ```toml
   [project]
   name = "flatagents"
   version = "0.9.0"
   dependencies = ["pyyaml", "jinja2", "aiofiles", "httpx"]
   
   [project.optional-dependencies]
   litellm = ["litellm"]
   aisuite = ["aisuite[all]"]
   ```

### Phase 2: Create `flatmachines` Package

1. **Extract Machine-Layer Modules**:
   ```
   flatmachines/
   ├── __init__.py           # Export: FlatMachine, MachineHooks, etc.
   ├── flatmachine.py
   ├── hooks.py
   ├── actions.py
   ├── backends.py
   ├── persistence.py
   ├── locking.py
   ├── expressions/
   ├── distributed.py
   ├── distributed_hooks.py
   ├── validation.py         # Machine-specific validation
   └── assets/
       └── flatmachine.schema.json
   ```

2. **Update Imports**:
   ```python
   # flatmachines/flatmachine.py
   from flatagents import FlatAgent  # External import
   from flatagents.profiles import resolve_model_config
   from flatagents.monitoring import get_logger
   ```

3. **Create `pyproject.toml`**:
   ```toml
   [project]
   name = "flatmachines"
   version = "0.9.0"
   dependencies = ["flatagents>=0.9.0"]  # Depends on flatagents
   
   [project.optional-dependencies]
   cel = ["cel-python"]
   ```

### Phase 3: Verify Standalone Agent Usage

Test that `flatagents` works without `flatmachines`:

```python
# Standalone agent usage (no flatmachines dependency)
from flatagents import FlatAgent

agent = FlatAgent(config_file="agent.yml")
result = await agent.call(name="Alice")
print(result.output)
```

---

## 9. Migration Path: Inline Agents to Separate Files

### Current: Inline Agent in Machine YAML

```yaml
# machine.yml
spec: flatmachine
spec_version: "0.9.0"
data:
  name: my-workflow
  agents:
    writer:
      spec: flatagent
      spec_version: "0.9.0"
      data:
        name: writer
        model:
          provider: openai
          name: gpt-4
        system: "You are a writer."
        user: "Write about {{ input.topic }}"
        output:
          text: { type: str }
  states:
    write:
      agent: writer
      ...
```

### After: Extracted to Separate File

```yaml
# machine.yml
spec: flatmachine
spec_version: "0.9.0"
data:
  name: my-workflow
  agents:
    writer: ./agents/writer.yml  # Reference to external file
  states:
    write:
      agent: writer
      ...
```

```yaml
# agents/writer.yml
spec: flatagent
spec_version: "0.9.0"
data:
  name: writer
  model:
    provider: openai
    name: gpt-4
  system: "You are a writer."
  user: "Write about {{ input.topic }}"
  output:
    text: { type: str }
```

### Migration Script

```python
#!/usr/bin/env python3
"""Extract inline agents from machine.yml to separate files."""

import os
import yaml
from pathlib import Path

def extract_inline_agents(machine_file: str, agents_dir: str = "./agents"):
    with open(machine_file) as f:
        machine = yaml.safe_load(f)
    
    agents = machine.get('data', {}).get('agents', {})
    extracted = {}
    
    os.makedirs(agents_dir, exist_ok=True)
    
    for name, config in agents.items():
        if isinstance(config, dict):  # Inline config
            agent_file = f"{agents_dir}/{name}.yml"
            with open(agent_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            extracted[name] = agent_file
            print(f"Extracted: {name} -> {agent_file}")
        else:  # Already a file reference
            extracted[name] = config
    
    # Update machine config
    machine['data']['agents'] = extracted
    
    with open(machine_file, 'w') as f:
        yaml.dump(machine, f, default_flow_style=False)
    
    print(f"Updated: {machine_file}")

if __name__ == "__main__":
    import sys
    extract_inline_agents(sys.argv[1])
```

---

## 10. Implementation Recommendation

### Recommended Approach: Option A (Conservative Split)

**Rationale**:
1. Minimal code changes required
2. Clear separation of concerns
3. Allows `flatagents` to be used standalone
4. `flatmachines` is a pure orchestration layer

### Package Structure

```
pypi/
├── flatagents/              # pip install flatagents
│   ├── flatagent.py
│   ├── baseagent.py
│   ├── profiles.py
│   ├── validation.py
│   ├── monitoring.py
│   ├── utils.py
│   ├── execution.py
│   └── assets/
│
└── flatmachines/            # pip install flatmachines
    ├── flatmachine.py       # imports from flatagents
    ├── hooks.py
    ├── actions.py
    ├── backends.py
    ├── persistence.py
    ├── locking.py
    ├── expressions/
    ├── distributed.py
    ├── distributed_hooks.py
    └── assets/
```

### Success Criteria Validation

✅ **User can install and use `flatagents` standalone**:
```bash
pip install flatagents
```

```python
from flatagents import FlatAgent

agent = FlatAgent(config_file="greeter.yml")
result = await agent.call(name="Alice")
# Works without any flatmachines dependency
```

✅ **User can install `flatmachines` for orchestration**:
```bash
pip install flatmachines  # Also installs flatagents
```

```python
from flatmachines import FlatMachine

machine = FlatMachine(config_file="workflow.yml")
result = await machine.execute(input={"topic": "AI"})
# Uses flatagents under the hood
```

---

## 11. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing imports | High | Maintain backwards-compatible wrapper package |
| Version drift between packages | Medium | Use lockstep versioning (both at 0.9.x) |
| Shared utility changes | Medium | Careful API design for shared modules |
| Test coverage gaps | Low | Run full test suite against split packages |

---

## 12. Appendix: File-by-File Classification

| File | Current Package | Target Package | Notes |
|------|-----------------|----------------|-------|
| `flatagent.py` | flatagents | flatagents | Core agent class |
| `baseagent.py` | flatagents | flatagents | LLM backends, extractors |
| `flatmachine.py` | flatagents | flatmachines | Core machine class |
| `profiles.py` | flatagents | flatagents | Shared, imported by machines |
| `validation.py` | flatagents | Both | Split: agent schema in agents, machine in machines |
| `monitoring.py` | flatagents | flatagents | Shared utility |
| `utils.py` | flatagents | flatagents | Shared utility |
| `execution.py` | flatagents | flatagents | Wraps agent.call() |
| `hooks.py` | flatagents | flatmachines | Machine-specific |
| `actions.py` | flatagents | flatmachines | Machine-specific |
| `backends.py` | flatagents | flatmachines | Inter-machine communication |
| `persistence.py` | flatagents | flatmachines | Checkpointing |
| `locking.py` | flatagents | flatmachines | Concurrency control |
| `expressions/` | flatagents | flatmachines | Transition conditions |
| `distributed.py` | flatagents | flatmachines | Worker backends |
| `distributed_hooks.py` | flatagents | flatmachines | Worker hooks |

---

## 13. Conclusion

The FlatAgents SDK is **well-suited for architectural decoupling**. The Agent layer is already largely independent of the Machine layer, with only a single direct import creating coupling. The recommended Conservative Split (Option A) provides:

1. **Clean separation**: Agent = LLM calling, Machine = orchestration
2. **Minimal refactoring**: Only module reorganization, no logic changes
3. **Backward compatibility**: Existing code continues to work
4. **Future extensibility**: Protocol-based integration possible (Option C) as future enhancement

**Estimated Effort**: 2-3 days for initial split, 1-2 weeks for full testing and documentation.

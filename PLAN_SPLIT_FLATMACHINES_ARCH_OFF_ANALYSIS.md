# PLAN_SPLIT_FLATMACHINES_ARCH_OFF — Deep Analysis & Issues

> Goal focus: **(1) FlatAgents must be useful standalone** and **(2) FlatMachines must be usable with other agent frameworks.**
> This document substantiates the draft, cross-checks the current SDK, and identifies design gaps and required corrections.

---

## 1. Reality Check vs Draft (What’s Actually in the SDK)

**Current version**: `0.10.0` (not `0.9.0`). The draft uses `0.9.0` repeatedly (examples, pyproject snippets, migration notes). This matters because version alignment is a hard requirement (lockstep versioning in `AGENTS.md`).

**Actual package layout** (from `sdk/python/flatagents`):
- `flatagent.py` is agent-only and cleanly independent.
- `flatmachine.py`, `actions.py`, `backends.py`, `persistence.py`, `locking.py`, `expressions/`, `distributed*.py`, and `run.py` are all machine-only.
- `execution.py` is **machine-only** in practice: it is only used by `FlatMachine` (see `flatmachine.py`), and its docstring explicitly says “Execution Types for FlatMachine.”
- `validation.py` bundles **both** schemas (`flatagent.schema.json` and `flatmachine.schema.json`) inside `flatagents/assets`. This will block a clean split unless the assets and validation are separated.

**Meaning**: the draft’s “only one coupling point” is too optimistic. While there is only one direct `import FlatAgent` in `flatmachine.py`, there are **multiple implicit couplings** that block a true “agent-agnostic” orchestration layer:
- `execution.py` assumes a `FlatAgent` interface and a `FlatAgent`-style response (e.g., `result.output`, `result.content`).
- `FlatMachine` aggregates `total_api_calls` and `total_cost` based on `FlatAgent` behavior.
- `FlatMachine` loads and resolves **model profiles** (`profiles.py`) even though model profiles are an agent-layer concept.
- `validation.py` hard-bundles machine schemas in the agent package.

---

## 2. Standalone FlatAgents: What Must Be True (and What the Draft Misses)

### ✅ What already works
- `FlatAgent` is self-contained and relies only on agent-layer modules (`baseagent.py`, `utils.py`, `monitoring.py`, `profiles.py`, `validation.py`).
- There is no import from machine-layer modules into `flatagent.py`.

### ❌ What blocks “useful on its own” today
1. **`flatagents/__init__.py` exports machine APIs**
   - `FlatMachine`, `MachineHooks`, `ExecutionType`, `distributed` classes, persistence, etc.
   - This makes the package “look like a monolith,” and forces machine imports even when they aren’t needed.

2. **Machine-only optional dependencies live in the agent package**
   - `cel-python` is a machine-only dependency (expression engine).
   - `jsonschema`, `opentelemetry`, and other options are bundled in `flatagents` but are not strictly required for agent-only usage.

3. **Machine schema is bundled in `flatagents/assets`**
   - `validation.py` loads `flatmachine.schema.json` from the agent package.
   - This means “agent-only” installs still carry machine assets.

4. **CLI runner is machine-specific**
   - `flatagents/run.py` executes `FlatMachine`. It should move to the machine package.

### Required corrections for standalone usefulness
- `flatagents` exports only agent-layer types (`FlatAgent`, `LLMBackend`, extractors, MCP types, validation for flatagent, profiles, monitoring).
- Move machine-only extras (`cel`, `validation` for machine, persistence, distributed hooks, etc.) out of the agent package.
- Provide a clean “agent-only” dependency graph (no `cel-python`, no machine schemas).
- Optional: keep a tiny CLI runner for agents only (if desired), but do **not** ship machine runner in the agent-only package.

---

## 3. FlatMachines With Other Agent Frameworks — Draft Gaps

The draft’s **Option A** (“flatmachines depends on flatagents”) **does not satisfy** the requirement that FlatMachines work with other agent frameworks. It keeps tight coupling to:
- `FlatAgent` config format
- `FlatAgent` response shape
- `FlatAgent` metrics API
- `profiles.py` model resolution
- `execution.py` semantics (built around `FlatAgent.call()`)

### Current coupling points in code
| Area | Coupling | Impact |
|------|----------|--------|
| `flatmachine._get_agent` | Always instantiates `FlatAgent` from dict/path | Impossible to use other agent frameworks without forking `FlatMachine` |
| `execution.py` | `execute(agent, input)` assumes `FlatAgent` interface | Locks orchestration to FlatAgent |
| Metrics aggregation | `total_api_calls`, `total_cost` assumed | No standard interface for other frameworks |
| `profiles.py` | Loaded in `FlatMachine` constructor | Adds agent-level assumption to orchestration core |
| Validation | Uses bundled schemas with flatagent-only agent definitions | Schema prohibits non-flatagent agents |

### Result: FlatMachines is **not** currently framework-agnostic
Even with a package split, **`flatmachines` would still be FlatAgents-first**. A different agent framework (LangChain, PydanticAI, DSPy, etc.) would need to spoof a `FlatAgent` config and result to run at all.

---

## 4. What “Agent-Agnostic FlatMachines” Actually Requires

### 4.1 Introduce a formal Agent Executor Protocol
**Required abstraction**: A protocol that `FlatMachine` uses instead of `FlatAgent`.

```python
class AgentExecutor(Protocol):
    async def execute(self, input_data: dict) -> "AgentResult":
        ...

@dataclass
class AgentResult:
    output: dict | None
    content: str | None
    raw: Any | None
    usage: dict | None
    cost: float | None
```

**Why**: The orchestration layer needs a stable contract that multiple frameworks can implement.

### 4.2 Pluggable Agent Resolution
The machine config needs to resolve agents via plugins, not hardcoded `FlatAgent` loaders.

**Proposed spec shape**:
```yaml
agents:
  writer:
    type: flatagent
    ref: ./agents/writer.yml
  reviewer:
    type: langgraph
    ref: ./graphs/reviewer.json
```

And in code:
```python
FlatMachine(..., agent_resolver=ResolverRegistry(...))
```

### 4.3 Execution Types must be agent-agnostic
`execution.py` should accept `AgentExecutor` (not `FlatAgent`). The execution layer is orchestration logic; it belongs in the machine package or a shared core, not in flatagents.

### 4.4 Profiles must be optional
Model profiles are tied to `FlatAgent`. If `flatmachines` is to be generic, profile loading must be:
- **optional**, or
- delegated to the agent adapter layer.

### 4.5 Standardized Metrics Interface
Aggregation in `FlatMachine` (`total_cost`, `total_api_calls`) is currently hard-coded to FlatAgent. Provide a minimal `AgentMetrics` interface so other frameworks can report usage.

---

## 5. Draft Problems & Inconsistencies

### ❌ “Only one coupling point” is inaccurate
- `execution.py` depends on FlatAgent behavior.
- `FlatMachine` expects FlatAgent response shape.
- Profiles are resolved within the machine layer.

### ❌ Option A violates the “other frameworks” requirement
It guarantees **flatmachines depends on flatagents**, which prevents using alternative agent stacks without pulling flatagents as a dependency.

### ❌ Option B in draft makes agents too thin
It strips shared utilities from flatagents and moves them into flatmachines, which makes the standalone agent package less useful (violates requirement #1).

### ❌ Draft assumes single “shared module” placement works
Realistically, `monitoring`, `validation`, and `utils` are cross-cutting and should move to a shared “core” package or be duplicated. The draft does not resolve this.

---

## 6. Recommended Architecture (Meets Both Requirements)

### ✅ Core Principle
- **FlatAgents is a standalone agent SDK.**
- **FlatMachines is a standalone orchestration SDK** that can run FlatAgents *or* other agent frameworks.

### Proposed packages
```
flatagents/                # agent-only
  - flatagent.py
  - baseagent.py
  - profiles.py
  - validation (agent only)
  - monitoring
  - utils
  - assets/flatagent.schema.json

flatmachines/              # orchestration-only
  - flatmachine.py
  - execution.py
  - hooks.py
  - actions.py
  - persistence.py
  - locking.py
  - expressions/
  - distributed*.py
  - validation (machine only)
  - assets/flatmachine.schema.json

flatmachines-flatagents/   # optional adapter (or flatmachines[flatagents] extra)
  - FlatAgentAdapter implements AgentExecutor
  - Agent resolver for flatagent configs
  - Profile loading adapter
```

### Why this works
- **FlatAgents** stays useful with no machine dependencies.
- **FlatMachines** does not depend on FlatAgents and can be used with any framework implementing the `AgentExecutor` protocol.
- The FlatAgent integration is delivered as an adapter module or optional extra, not as a hard dependency.

---

## 7. Concrete Refactor Requirements (Beyond the Draft)

1. **Move `execution.py` to flatmachines**
   - It is orchestration logic and should not live in the agent SDK.

2. **Replace `FlatAgent` with `AgentExecutor` inside `FlatMachine`**
   - Plug-in architecture for agent resolution and execution.

3. **Split `validation.py` and assets**
   - FlatAgents validates only flatagent schema.
   - FlatMachines validates only flatmachine schema.

4. **Decouple profiles from FlatMachine**
   - Load profiles only in the FlatAgent adapter layer.

5. **Normalize agent result shape**
   - Introduce `AgentResult` (output/content/usage/cost) for cross-framework compatibility.

6. **Preserve backwards compatibility**
   - Provide a compatibility package (or shim) that exports the old `flatagents.FlatMachine` path.
   - Alternatively, `flatagents` could become a meta-package that depends on both `flatagents-core` + `flatmachines`.

---

## 8. Additional Subtle Issues the Draft Doesn’t Address

- **Schema alignment with new agent types**: `flatmachine.schema.json` currently assumes `flatagent` config format in `agents`. This must be loosened for multi-framework support.
- **`run.py` location**: move to `flatmachines` or a CLI package.
- **Imports inside actions/backends**: these currently assume `flatmachine` import paths within a single package. Split requires careful path rewrites and lazy imports.
- **Version lockstep**: both packages must share the same version, but this should not force a dependency between them.
- **Docs & examples**: all examples referencing `from flatagents import FlatMachine` must be updated or redirected to the compatibility layer.

---

## 9. Bottom Line

The draft is a solid first pass, but **Option A (recommended in the draft) fails the key requirement**: FlatMachines must be usable with **other agent frameworks**, which requires a real adapter/Executor abstraction and removal of the hard `flatagents` dependency.

**If the end state must satisfy both requirements**, the split needs:
- An agent-agnostic `flatmachines` core
- A `flatagents` package that stands alone
- A clean adapter layer that bridges them

Only that architecture ensures:
- **Standalone FlatAgents is genuinely useful**, and
- **FlatMachines can orchestrate any agent framework, not just FlatAgents.**

---

## 10. Immediate Draft Fixes (Summary)

- Update all versions to `0.10.0`.
- Move `execution.py` to the machine layer.
- Remove `flatmachine.schema.json` from the agent package.
- Define an `AgentExecutor` protocol and `AgentResult` structure.
- Add a resolver registry to `FlatMachine`.
- Make FlatAgent integration an adapter, not a hard dependency.

---

If you want, I can next create a concrete adapter interface proposal + example config edits, but this analysis already exposes the key structural problems and required course corrections.
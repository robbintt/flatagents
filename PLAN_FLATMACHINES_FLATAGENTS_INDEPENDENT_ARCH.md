# PLAN_FLATMACHINES_FLATAGENTS_INDEPENDENT_ARCH

> Objective: architect a clean split where **FlatAgents is useful standalone** and **FlatMachines is framework-agnostic**, validated against **smolagents (Python)** and **pi-mono (JavaScript)**. This plan is detailed and self-contained to support execution without further approvals.

---

## 1. Goals & Non‑Goals

### Goals
1. **FlatAgents standalone value**: `flatagents` must contain only agent-layer code and dependencies, usable without orchestration.
2. **FlatMachines independence**: `flatmachines` must not depend on `flatagents` or a specific agent framework.
3. **Multi-framework orchestration**: The same machine spec must orchestrate:
   - FlatAgent
   - smolagents (Python)
   - pi-mono Agent (JavaScript)
4. **Cross-runtime viability**: Python FlatMachines can invoke pi-mono agents via a JS bridge (Node subprocess/RPC) without requiring a JS FlatMachines runtime.
5. **Lockstep versioning**: All packages align to the same `spec_version` and SDK version (currently `0.10.0`).

### Non‑Goals
- Implementing new agent features inside smolagents or pi-mono.
- Overhauling FlatMachine semantics (states, transitions, persistence). We retain existing runtime behaviors.

---

## 2. Target Framework Profiles (Constraints We Must Support)

### smolagents (Python)
- **Agent types**: `MultiStepAgent` subclasses like `CodeAgent` and `ToolCallingAgent`.
- **Execution API**: `agent.run(task: str, ...)` returns either output or a `RunResult` (if `return_full_result=True`).
- **RunResult**: `output`, `state`, `steps`, `token_usage` and `timing`.
- **Implication**: FlatMachine adapter must translate `input` → `task`, and normalize output + usage.

### pi-mono (JavaScript)
- **Agent type**: `Agent` from `@mariozechner/pi-agent-core`.
- **Execution API**: `agent.prompt(...)` returns `Promise<void>`, results are read from `agent.state.messages` or `agent` events.
- **Usage data**: usage is embedded in assistant messages (`message.usage`) when available.
- **Implication**: Python adapter must launch a Node-based wrapper that:
  - maps `FlatMachine` input to `agent.prompt(...)`
  - collects the final assistant message as `output`
  - returns usage/cost via JSON back to Python

---

## 3. Key Architectural Decisions

### 3.1 Split Packages and Responsibilities

```
flatagents/                # Agent SDK only
  - flatagent.py
  - baseagent.py
  - profiles.py
  - validation (agent-only)
  - monitoring
  - utils
  - assets/flatagent.schema.json

flatmachines/              # Orchestration core only (no agent dependencies)
  - flatmachine.py
  - execution.py
  - hooks.py
  - actions.py
  - persistence.py
  - locking.py
  - expressions/
  - distributed*.py
  - validation (machine-only)
  - assets/flatmachine.schema.json

flatmachines-adapters/     # Adapter layer (language-specific)
  - flatagents_adapter (Python)
  - smolagents_adapter (Python)
  - pi_agent_bridge (Python → Node subprocess)
```

### 3.2 Define a Language‑Neutral Agent Executor Contract

Add to `flatagents-runtime.d.ts` (or new `flatmachines-runtime.d.ts`):

```ts
export interface AgentExecutor {
  execute(input: Record<string, any>, context?: Record<string, any>): Promise<AgentResult>;
}

export interface AgentResult {
  output?: Record<string, any> | null;   // structured output for output_to_context
  content?: string | null;               // primary text output
  raw?: any;                              // raw framework result
  usage?: Record<string, any> | null;     // token usage or equivalent
  cost?: number | null;                   // optional cost
  metadata?: Record<string, any> | null;  // optional framework metadata
}
```

**Key decision**: `FlatMachine` executes agents through `AgentExecutor`, not `FlatAgent`.

### 3.3 Adapter Registry & Agent Resolution

Add a registry to resolve agent definitions by `type`:

```yaml
agents:
  writer:
    type: flatagent
    ref: ./agents/writer.yml
  reviewer:
    type: smolagents
    ref: ./agents/reviewer.py#build_agent
  judge:
    type: pi-agent
    ref: ./agents/judge.ts#buildAgent
```

`FlatMachine` will delegate the `agents.*` config to the adapter corresponding to `type`.

---

## 4. Spec & Schema Updates (Required)

### 4.1 Update `flatmachine.d.ts`

Define a new `AgentRef` object:

```ts
type AgentRef =
  | string  // legacy flatagent file path
  | {
      type: string;              // adapter key, e.g. flatagent | smolagents | pi-agent
      ref?: string;              // file path or module#factory
      config?: Record<string, any>; // adapter-specific inline config
    };

agents: Record<string, AgentRef>;
```

### 4.2 Update JSON Schema & Validation
- Move `flatmachine.schema.json` into the machine package.
- Update validation rules for `agents` to accept `AgentRef` objects.
- Preserve legacy behavior: if `agents[name]` is a string or flatagent object → `flatagent` adapter.

### 4.3 Update runtime spec
- Add `AgentExecutor` & `AgentResult` definitions.
- Update `ExecutionType.execute()` to accept an async function rather than a `FlatAgent` object.

---

## 5. FlatMachines Core Changes (Python)

### 5.1 Replace Direct FlatAgent Usage
- `FlatMachine._get_agent()` becomes `FlatMachine._get_executor()` and returns `AgentExecutor`.
- Remove all direct `FlatAgent` imports from `flatmachine.py`.

### 5.2 Execution Types Become Framework‑Agnostic
- `execution.py` should call `executor.execute(input_data)` and return `AgentResult`.
- `DefaultExecution`, `RetryExecution`, `ParallelExecution`, `MDAPVotingExecution` operate on closures or `AgentExecutor`.

### 5.3 Metrics and Cost Aggregation
- Replace `total_api_calls` and `total_cost` accumulation with adapter-reported metrics.
- Introduce `AgentResult.usage` & `AgentResult.cost` standard fields.

---

## 6. Adapter Implementations

### 6.1 FlatAgent Adapter (Python)
**Purpose**: preserve current behavior without coupling `flatmachines` to `flatagents`.

**Adapter interface**:
- `FlatAgentExecutor.execute(input)` → calls `FlatAgent.call(**input)`
- `AgentResult.output` = `result.output`
- `AgentResult.content` = `result.content`
- `AgentResult.usage` = `result.usage` if present
- `AgentResult.cost` = `result.cost` if present

**Loading**:
- `ref` can be YAML path or inline dict, same as today.

### 6.2 Smolagents Adapter (Python)
**Executor**: wraps a `MultiStepAgent` instance.

**Input mapping**:
- `input.task` → `agent.run(task)`
- `input.additional_args` → `agent.run(additional_args=...)`
- `input.max_steps` → `agent.run(max_steps=...)`
- `input.return_full_result` → `agent.run(return_full_result=...)`

**Output mapping**:
- If `RunResult` → `AgentResult.output = run.output`
- Else → `AgentResult.output = {"content": run}`
- `AgentResult.usage = run.token_usage.dict()` when available

**Agent construction** (`ref` patterns):
- `ref: ./agents/my_smolagent.py#build_agent` returning a `MultiStepAgent`.
- `config` passed to factory as kwargs.

### 6.3 pi-mono Adapter (Python → JS bridge)
**Executor**: Python adapter spawns a Node runner that loads `@mariozechner/pi-agent-core` and executes a JS factory to build the agent.

**Invocation protocol** (default): JSON over stdin/stdout (single request/response per call).
- **Request**: `{ ref, config, input, context }`
- **Response**: `{ output, content, usage, cost, raw, metadata }`

**Input mapping** (inside JS runner):
- If `input` has `message`/`messages`: `agent.prompt(messages)`.
- Else if `input.task` or `input.prompt`: `agent.prompt(task)`.
- `input.images` → `agent.prompt(task, images)`.

**Output mapping** (inside JS runner):
- Final assistant message from `agent.state.messages`.
- `content` = concatenated assistant text content.
- `output = { content }` by default.
- `usage` from assistant message usage fields.

**Agent construction** (`ref` patterns):
- `ref: ./agents/buildAgent.ts#buildAgent` returning a configured `Agent` instance.
- `config` passed to factory, resolved relative to the machine config directory.

**Packaging**:
- Node runner can live in `flatmachines-adapters` and be invoked as `node <runner> --ref ...`.
- Alternatively, ship a small CLI in pi-mono and call it from the Python adapter.

---

## 7. Cross‑Runtime Execution (Python FlatMachines → JS pi-mono)

### 7.1 Node Runner Contract
- Provide a minimal Node CLI ("pi-agent-runner") that:
  - Loads a JS/TS factory from `ref` (e.g., `./agents/buildAgent.ts#buildAgent`).
  - Accepts a single JSON request via stdin (or args) and returns a single JSON response on stdout.
  - Uses stderr for logs and non-zero exit codes for failures.

### 7.2 Python Adapter Behavior
- Spawn the Node runner via `asyncio.create_subprocess_exec`.
- Send `{ ref, config, input, context }` as JSON to stdin.
- Parse `{ output, content, usage, cost, raw, metadata }` from stdout.
- Map failures into `on_error` with `_error` and `_error_type`.

### 7.3 Deployment & Configuration
- Require Node.js runtime + pi-mono dependencies installed.
- Configure runner path and Node binary in machine settings (e.g., `settings.agent_runners.pi_agent`).
- Support `cwd`/`env` overrides so relative `ref` paths resolve from the machine config directory.

### 7.4 Streaming (Optional, Future)
- If streaming is needed, extend protocol to JSONL events with a final result.
- Keep default as single request/response for deterministic orchestration.

---

## 8. Backwards Compatibility Strategy

1. **Compatibility shim**:
   - A `flatagents` meta-package (or `flatagents.compat`) that re-exports `FlatMachine` from `flatmachines` with the default `flatagent` adapter.
2. **Legacy agent refs**:
   - A string value in `agents.*` is treated as `type: flatagent`.
3. **Deprecation plan**:
   - Emit warnings when `flatagents.FlatMachine` is used directly, guiding users to `flatmachines`.

---

## 9. Testing & Validation Plan

### Python
- Unit tests for adapter registry and executor protocol.
- Integration tests:
  - FlatAgent adapter: existing machine YAMLs run unchanged.
  - smolagents adapter: machine with `type: smolagents` executes and maps output.

### Cross‑Runtime (Python → Node)
- Integration tests that spawn the Node runner and execute a pi-mono agent factory.
- Golden tests: deterministic Node runner outputs → same context/output mapping as FlatAgent.
- Failure-path tests: non-zero exit, malformed JSON, timeout.

### Cross‑Language Validation
- Use a machine that calls both a FlatAgent and a pi-mono agent in one run.
- Verify combined `context` + `output` are stable across runs.

---

## 10. Work Phases (Execution Order)

### Phase 1 — Spec & API Contracts
1. Update `flatmachine.d.ts` with `AgentRef`.
2. Add `AgentExecutor` & `AgentResult` to runtime spec.
3. Regenerate JSON schemas.

### Phase 2 — Python Core Refactor
1. Split packages (`flatagents` vs `flatmachines`).
2. Refactor `execution.py` to be executor‑based.
3. Replace `_get_agent` with adapter registry.
4. Move `flatmachine.schema.json` out of agent package.

### Phase 3 — Python Adapters
1. Implement FlatAgent adapter.
2. Implement smolagents adapter.
3. Add adapter config validation rules.

### Phase 4 — Cross‑Runtime pi-mono Bridge
1. Implement the Node runner CLI ("pi-agent-runner") for pi-mono.
2. Implement the Python `pi-agent` adapter using subprocess IPC.
3. Integrate with pi-mono build + cross-runtime tests.

### Phase 5 — Docs & Examples
1. Update README usage: `flatmachines` vs `flatagents`.
2. Add example machines for smolagents and pi-mono.

---

## 11. Open Questions / Issues (for Review)

1. **Adapter registration mechanism**: Python entrypoints vs manual registry config?
2. **Templating parity**: Jinja2 vs JS templating compatibility. Should we define a canonical subset?
3. **Node runner protocol**: stdin/stdout vs HTTP? per-call spawn vs long-lived worker? how to stream partial events if needed?
4. **Metrics normalization**: Do we need a spec for `usage` and `cost` formats across frameworks?
5. **Streaming support**: Should FlatMachine expose streaming events from agents (especially pi-mono)?
6. **Security of `ref` factories**: Do we allow arbitrary module execution, or require signed adapters?
7. **Schema evolution**: How do we keep agent-agnostic config without breaking existing flatagent files?

---

## 12. Success Criteria

- `flatagents` can be installed and used without any `flatmachines` dependencies.
- `flatmachines` can run machines that use **flatagent**, **smolagents**, or **pi-agent** without importing each other.
- Python FlatMachines can execute a pi-mono agent via the Node runner using the same `flatmachine` YAML spec.
- Existing FlatAgents workflows continue to work with minimal config changes.

---

If accepted, next step is to turn this plan into actionable tasks and draft adapter interfaces in code (without modifying any other files yet).
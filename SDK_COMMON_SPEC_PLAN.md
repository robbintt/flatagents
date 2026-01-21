# SDK Common Spec Requirements Plan

> **Purpose:** Define common requirements for FlatAgents SDK implementations across languages and runtimes.
> **Status:** Planning Document
> **Spec Version:** 0.7.7

## Executive Summary

This document outlines requirements for a unified SDK specification that enables:
1. Cross-language SDK compatibility (Python, JavaScript, Rust/WASM)
2. Distributed systems deployment (k8s, cloud functions, ECS, edge, browser)
3. Formal verification readiness (ACL2-compatible design)

---

## 1. Core Spec Files (Source of Truth)

| File | Purpose | Status |
|------|---------|--------|
| `flatagent.d.ts` | Agent configuration schema | ✅ Complete |
| `flatmachine.d.ts` | Machine orchestration schema | ✅ Complete |
| `profiles.d.ts` | Model profile configuration | ✅ Complete |
| `flatagents-runtime.d.ts` | SDK runtime interfaces | ✅ Initial draft |

---

## 2. Required Runtime Interfaces

### 2.1 Execution Locking (`ExecutionLock`)

**Purpose:** Prevent concurrent execution of the same machine instance.

| Implementation | Requirement | Use Case |
|----------------|-------------|----------|
| `NoOpLock` | MUST | External locking / disabled |
| `LocalFileLock` | SHOULD | Single-node deployments |
| `RedisLock` | MAY | Distributed deployments |
| `ConsulLock` | MAY | Service mesh environments |

**Formal Verification Notes:**
- Lock acquisition is a boolean predicate: `acquire(key) → bool`
- Lock must satisfy mutual exclusion property
- ACL2: Model as state transition with mutex invariant

### 2.2 Persistence Backend (`PersistenceBackend`)

**Purpose:** Durable storage for machine checkpoints.

| Implementation | Requirement | Use Case |
|----------------|-------------|----------|
| `MemoryBackend` | MUST | Testing, ephemeral runs |
| `LocalFileBackend` | SHOULD | Local durable storage |
| `RedisBackend` | MAY | Distributed cache |
| `PostgresBackend` | MAY | Relational durability |
| `S3Backend` | MAY | Cloud object storage |

**Interface Requirements:**
```typescript
interface PersistenceBackend {
  save(key: string, snapshot: MachineSnapshot): Promise<void>;  // Atomic
  load(key: string): Promise<MachineSnapshot | null>;
  delete(key: string): Promise<void>;
  list(prefix: string): Promise<string[]>;  // Lexicographic order
}
```

**Formal Verification Notes:**
- `save` must be atomic (all-or-nothing)
- `list` must return deterministic ordering
- ACL2: Model as key-value store with append-only history

### 2.3 Result Backend (`ResultBackend`)

**Purpose:** Inter-machine communication via URI-addressed results.

**URI Scheme:** `flatagents://{execution_id}/{path}`
- `/checkpoint` - Machine state for resume
- `/result` - Final output after completion

| Implementation | Requirement | Use Case |
|----------------|-------------|----------|
| `InMemoryResultBackend` | MUST | Single-process |
| `RedisResultBackend` | MAY | Distributed |

**Interface Requirements:**
```typescript
interface ResultBackend {
  write(uri: string, data: any): Promise<void>;  // Notify blocked readers
  read(uri: string, options?: { block?: boolean; timeout?: number }): Promise<any>;
  exists(uri: string): Promise<boolean>;
  delete(uri: string): Promise<void>;
}
```

**Formal Verification Notes:**
- Write must happen-before read can return data
- Blocking reads must eventually terminate (timeout or data arrival)
- ACL2: Model as message queue with ordering guarantees

### 2.4 Execution Types (`ExecutionConfig`)

| Type | Requirement | Behavior |
|------|-------------|----------|
| `default` | MUST | Single call, no retry |
| `retry` | MUST | Configurable backoffs with jitter |
| `parallel` | MUST | N samples, return all successes |
| `mdap_voting` | MUST | Multi-sample with consensus |

**Formal Verification Notes:**
- Retry backoff sequence must be monotonic
- Jitter must be bounded: `actual_wait in [base * (1-jitter), base * (1+jitter)]`
- MDAP voting: k_margin consensus is well-defined for n >= k

### 2.5 Machine Hooks (`MachineHooks`)

All hooks are optional. SDKs must support both sync and async implementations.

| Hook | Signature | Purpose |
|------|-----------|---------|
| `onMachineStart` | `(context) → context` | Modify initial context |
| `onMachineEnd` | `(context, output) → output` | Modify final output |
| `onStateEnter` | `(state, context) → context` | Pre-state modifications |
| `onStateExit` | `(state, context, output) → output` | Post-state modifications |
| `onTransition` | `(from, to, context) → to` | Redirect transitions |
| `onError` | `(state, error, context) -> state or null` | Error recovery |
| `onAction` | `(action, context) → context` | Custom action handlers |

---

## 3. Distributed Systems Requirements

### 3.1 Deployment Targets

| Environment | Considerations | Priority |
|-------------|----------------|----------|
| Kubernetes Pods | Stateless pods, external state | HIGH |
| Kubernetes Jobs | Batch processing, completion tracking | HIGH |
| Cloud Functions (AWS Lambda, GCP, Azure) | Cold starts, timeouts, stateless | HIGH |
| ECS Tasks | Container orchestration, service mesh | MEDIUM |
| Edge Functions (Cloudflare Workers, Vercel) | Size limits, restricted APIs | MEDIUM |
| Browser (Rust/WASM) | No filesystem, async-only, sandboxed | MEDIUM |

### 3.2 Stateless Execution Model

**Requirement:** SDKs MUST support fully stateless execution:
1. All state externalized to persistence backend
2. Checkpoint-resume semantics for any interruption
3. No in-memory state between invocations

**Machine Snapshot Wire Format:**
```typescript
interface MachineSnapshot {
  execution_id: string;
  machine_name: string;
  spec_version: string;
  current_state: string;
  context: Record<string, any>;
  step: number;
  created_at: string;
  event?: string;
  output?: Record<string, any>;
  total_api_calls?: number;
  total_cost?: number;
  parent_execution_id?: string;
  pending_launches?: LaunchIntent[];
}
```

### 3.3 Launch Intent / Outbox Pattern

**Purpose:** Ensure exactly-once semantics for machine launches.

**Mechanism:**
1. Record launch intent in checkpoint before launching
2. On resume, check if launched machine exists before re-launching
3. Use `pending_launches` array in `MachineSnapshot`

```typescript
interface LaunchIntent {
  execution_id: string;
  machine: string;
  input: Record<string, any>;
  launched: boolean;
}
```

### 3.4 Timeout and Cancellation

**Requirements:**
- State-level `timeout` in seconds (0 = forever)
- Graceful cancellation with checkpoint preservation
- Timeout errors must be catchable via `on_error`

### 3.5 Parallel Execution Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `settled` | Wait for all to complete | All results needed |
| `any` | Return on first success | Fastest response wins |

**Distributed Considerations:**
- Fan-out to multiple workers
- Result aggregation at parent
- Partial failure handling

---

## 4. Rust/WASM Runtime Requirements

### 4.1 Compilation Targets

| Target | Use Case | API Restrictions |
|--------|----------|------------------|
| `wasm32-unknown-unknown` | Browser, Cloudflare Workers | No filesystem, no threads |
| `wasm32-wasi` | Node.js, Deno, edge runtimes | WASI filesystem, limited threads |
| Native (Linux/macOS/Windows) | CLI, server applications | Full API access |

### 4.2 WASM-Specific Constraints

**No Filesystem Access:**
- `LocalFileBackend` unavailable
- `LocalFileLock` unavailable
- Must use in-memory or remote backends

**No Native Threads:**
- Use `async`/`await` throughout
- Web Workers for parallelism in browser
- Consider `rayon` for WASI targets only

**Size Budget:**
- Target < 500KB gzipped for browser
- Tree-shaking for unused backends
- Optional features via Cargo features

### 4.3 WASM Backend Implementations

| Backend | WASM Strategy |
|---------|---------------|
| `MemoryBackend` | ✅ Direct implementation |
| `LocalFileBackend` | ❌ Not available |
| `IndexedDBBackend` | Browser persistence |
| `LocalStorageBackend` | Browser (small data) |
| `FetchBackend` | HTTP-based remote storage |

### 4.4 JavaScript/TypeScript Interop

**Binding Strategy:**
- Use `wasm-bindgen` for browser/Node.js
- Export `FlatAgent` and `FlatMachine` classes
- Async methods return `Promise<T>`
- JSON serialization for config/context

**API Surface:**
```typescript
// Generated from Rust via wasm-bindgen
export class FlatAgent {
  constructor(config: AgentWrapper);
  call(input: Record<string, any>): Promise<AgentResult>;
}

export class FlatMachine {
  constructor(config: MachineWrapper);
  execute(input: Record<string, any>): Promise<MachineResult>;
  resume(execution_id: string): Promise<MachineResult>;
}
```

---

## 5. Formal Verification (ACL2) Considerations

### 5.1 Design Principles for Verifiability

**Pure Functions Where Possible:**
- Expression evaluation (simple mode)
- Transition condition checking
- Context merging
- Input/output mapping

**Explicit State Transitions:**
- Machine states are finite and enumerable
- Transitions are deterministic given context
- Side effects isolated to backends

**Invariants to Verify:**

| Invariant | Description |
|-----------|-------------|
| Progress | Machine eventually reaches final state or error |
| Determinism | Same input + context → same transition |
| Checkpoint Consistency | Resume from checkpoint == original execution |
| Mutual Exclusion | Lock prevents concurrent execution |
| Outbox Exactly-Once | Each LaunchIntent executed exactly once |

### 5.2 ACL2 Modeling Strategy

**Approach:** Model core state machine logic, not I/O:

1. **State Machine Model:**
   ```lisp
   (defun transition (state context config)
     "Returns (next-state . updated-context) or :error"
     ...)
   ```

2. **Expression Evaluator Model:**
   ```lisp
   (defun eval-expr (expr context)
     "Evaluates simple-mode expression in context"
     ...)
   ```

3. **Checkpoint/Resume Model:**
   ```lisp
   (defun checkpoint-equiv (snapshot execution-trace)
     "Proves resuming from snapshot continues correctly"
     ...)
   ```

### 5.3 Implementation Recommendations

**Keep Verifiable Core Small:**
- Extract pure logic into separate modules
- Use types that map cleanly to ACL2 (no complex generics)
- Document invariants in code comments

**Property-Based Testing Bridge:**
- Use property-based tests (Hypothesis, fast-check) as executable specs
- Same properties can guide ACL2 theorems

**Avoid:**
- Complex type hierarchies
- Dynamic dispatch in core logic
- Implicit state mutations

---

## 6. Cross-SDK Compatibility Checklist

### 6.1 Configuration Parsing

| Requirement | Python | JavaScript | Rust |
|-------------|--------|------------|------|
| YAML parsing | ✅ | ✅ | TODO |
| JSON Schema validation | ✅ | ✅ | TODO |
| Jinja2 template rendering | ✅ | ✅ | TODO |
| Profile resolution | ✅ | ✅ | TODO |

### 6.2 Runtime Interfaces

| Interface | Python | JavaScript | Rust |
|-----------|--------|------------|------|
| `NoOpLock` | ✅ | ✅ | TODO |
| `LocalFileLock` | ✅ | ✅ | TODO |
| `MemoryBackend` | ✅ | ✅ | TODO |
| `LocalFileBackend` | ✅ | ✅ | TODO |
| `InMemoryResultBackend` | ✅ | ✅ | TODO |

### 6.3 Execution Types

| Type | Python | JavaScript | Rust |
|------|--------|------------|------|
| `default` | ✅ | ✅ | TODO |
| `retry` | ✅ | ✅ | TODO |
| `parallel` | ✅ | ✅ | TODO |
| `mdap_voting` | ✅ | ✅ | TODO |

### 6.4 Expression Engines

| Engine | Python | JavaScript | Rust |
|--------|--------|------------|------|
| `simple` | ✅ | ✅ | TODO |
| `cel` | ✅ | Partial | TODO |

---

## 7. Testing Requirements

### 7.1 Conformance Test Suite

**Purpose:** Ensure SDKs behave identically for the same inputs.

**Test Categories:**
1. **Agent Tests:** Single LLM call, output parsing, template rendering
2. **Machine Tests:** State transitions, loops, error handling
3. **Parallel Tests:** Machine arrays, foreach, launch
4. **Persistence Tests:** Checkpoint/resume, crash recovery
5. **Expression Tests:** Simple mode evaluation, edge cases

**Test Format:** JSON test cases executable by any SDK:
```json
{
  "name": "simple_transition",
  "machine": { "spec": "flatmachine", ... },
  "input": { "query": "test" },
  "expected_states": ["start", "process", "done"],
  "expected_output": { "result": "processed" }
}
```

### 7.2 Property-Based Tests

**Properties to Test:**
- Checkpoint-resume equivalence
- Expression evaluation determinism
- Transition function totality
- Error handler completeness

---

## 8. Implementation Roadmap

### Phase 1: Spec Finalization
- [ ] Finalize `flatagents-runtime.d.ts` interface definitions
- [ ] Generate JSON Schema from TypeScript definitions
- [ ] Create conformance test suite (JSON format)
- [ ] Document all invariants for formal verification

### Phase 2: SDK Alignment
- [ ] Audit Python SDK against spec
- [ ] Audit JavaScript SDK against spec
- [ ] Identify and resolve behavioral differences
- [ ] Implement missing features in both SDKs

### Phase 3: Rust/WASM Implementation
- [ ] Core state machine logic (no I/O)
- [ ] Memory backend implementation
- [ ] WASM bindings via wasm-bindgen
- [ ] Browser-specific backends (IndexedDB, LocalStorage)
- [ ] Size optimization (< 500KB gzipped)

### Phase 4: Distributed Backends
- [ ] Redis persistence backend
- [ ] Redis result backend
- [ ] Redis distributed lock
- [ ] Cloud function examples (Lambda, GCP, Azure)

### Phase 5: Formal Verification
- [ ] ACL2 model of state machine core
- [ ] Prove progress invariant
- [ ] Prove checkpoint-resume equivalence
- [ ] Prove mutual exclusion for locks

---

## 9. Open Questions

1. **CEL Expression Engine:** Full CEL support in JavaScript and Rust?
2. **Hook Serialization:** How to serialize hooks for distributed execution?
3. **WASM LLM Backends:** Direct API calls from WASM or proxy through host?
4. **Cost Tracking:** Standardize cost calculation across providers?
5. **Observability:** Common tracing/metrics format (OpenTelemetry)?

---

## Appendix A: Current SDK File Mapping

| Component | Python | JavaScript |
|-----------|--------|------------|
| Agent | `flatagent.py` | `flatagent.ts` |
| Machine | `flatmachine.py` | `flatmachine.ts` |
| Profiles | `profiles.py` | `profiles.ts` |
| Execution | `execution.py` | `execution.ts` |
| Expressions | `expressions/` | `expression.ts` |
| Persistence | `persistence.py` | `persistence.ts` |
| Locking | `locking.py` | `locking.ts` |
| Hooks | `hooks.py` | `hooks.ts` |
| LLM Backends | `backends.py` | `llm/` |

## Appendix B: URI Scheme Reference

```
flatagents://{execution_id}/{path}

Paths:
  /checkpoint   - Machine state for resume
  /result       - Final output after completion

Examples:
  flatagents://550e8400-e29b-41d4-a716-446655440000/checkpoint
  flatagents://550e8400-e29b-41d4-a716-446655440000/result
```

## Appendix C: Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.7.7 | Current | Initial SDK common spec plan |

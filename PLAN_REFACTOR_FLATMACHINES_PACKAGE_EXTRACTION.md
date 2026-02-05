# PLAN_REFACTOR_FLATMACHINES_PACKAGE_EXTRACTION.md

> **Purpose**: Document findings from the analysis of the attempted split between `flatagents` and `flatmachines` packages, identify remaining issues, and provide a corrected implementation task list.

---

## 1. Executive Summary

An attempt was made to split the Python SDK into two independent packages: `flatagents` (agent-only) and `flatmachines` (orchestration). However, **the split was incomplete** — the `flatagents` package still contains significant flatmachine-related code that violates the architectural goal stated in PLAN_FLATMACHINES_FLATAGENTS_INDEPENDENT_ARCH.md:

> **Goal**: "FlatAgents standalone value: `flatagents` must contain only agent-layer code and dependencies, usable without orchestration."

The current state creates confusion about package boundaries and defeats the purpose of the split.

---

## 2. Current State Analysis

### 2.1 Package Locations

```
sdk/python/
├── flatagents/              # Agent SDK package
│   ├── flatagents/          # Python module
│   └── pyproject.toml
└── flatmachines/            # Orchestration package
    ├── flatmachines/        # Python module
    └── pyproject.toml
```

### 2.2 Files in `flatagents` That Are Actually Machine Concerns

The following files exist in `sdk/python/flatagents/flatagents/` but belong in `flatmachines`:

| File | Description | Should Be In |
|------|-------------|--------------|
| `flatmachine.py` | Compatibility wrapper that imports from flatmachines | **Remove or convert to pure re-export stub** |
| `execution.py` | ExecutionType classes (Default, Parallel, Retry, MDAP) for machine state execution | `flatmachines` |
| `hooks.py` | MachineHooks, LoggingHooks, MetricsHooks, CompositeHooks, WebhookHooks | `flatmachines` |
| `actions.py` | Action base class, HookAction, MachineInvoker, InlineInvoker, QueueInvoker, SubprocessInvoker, launch_machine | `flatmachines` |
| `persistence.py` | MachineSnapshot, PersistenceBackend, LocalFileBackend, MemoryBackend, CheckpointManager | `flatmachines` |
| `locking.py` | ExecutionLock, LocalFileLock, NoOpLock | `flatmachines` |
| `backends.py` | ResultBackend, InMemoryResultBackend, LaunchIntent for inter-machine communication | `flatmachines` |
| `distributed.py` | WorkerRegistration, WorkerRecord, WorkItem, RegistrationBackend, WorkBackend, SQLiteRegistrationBackend, etc. | `flatmachines` |
| `distributed_hooks.py` | DistributedWorkerHooks for worker patterns | `flatmachines` |
| `expressions/` | Expression engine (simple.py, cel.py) for machine condition evaluation | `flatmachines` |
| `run.py` | Compatibility wrapper for CLI runner | **Remove or convert to pure re-export stub** |

### 2.3 Assets Duplication

Both packages contain identical asset files in their `assets/` directories:

```
flatagents/flatagents/assets/
├── flatagent.d.ts
├── flatagent.schema.json
├── flatmachine.d.ts         # ← Should NOT be in flatagents
├── flatmachine.schema.json  # ← Should NOT be in flatagents
├── profiles.d.ts
├── profiles.schema.json
├── flatagents-runtime.d.ts
├── flatagents-runtime.schema.json
└── MACHINES.md              # ← Should NOT be in flatagents
```

The `flatmachine.*` files and `MACHINES.md` should only exist in the `flatmachines` package.

### 2.4 `__init__.py` Exports Analysis

**flatagents/__init__.py** exports agent-only code properly, but then includes a large `try/except` block (lines 79-179) that re-exports **all** flatmachine classes from `flatmachines`:

```python
# Optional compatibility exports for machine orchestration
try:
    from flatmachines import (
        FlatMachine,
        MachineHooks,
        LoggingHooks,
        # ... 40+ machine-related symbols
    )
    __all__.extend([...])
except ImportError:
    pass
```

This design choice is problematic because:
1. It blurs the package boundary
2. Users importing from `flatagents` get machine code unexpectedly
3. It encourages coupling rather than clean separation

### 2.5 pyproject.toml Dependencies

**flatagents/pyproject.toml** has:
```toml
[project.optional-dependencies]
orchestration = ["flatmachines>=0.10.0"]
```

This is acceptable as an optional dependency, but the re-exporting in `__init__.py` goes too far.

**flatmachines/pyproject.toml** has:
```toml
[project.optional-dependencies]
flatagents = ["flatagents>=0.10.0"]
```

This is correct — flatmachines can optionally use flatagents via an adapter.

---

## 3. Root Cause Analysis

The split was approached as a **copy-then-modify** operation rather than a clean extraction:

1. **Code duplication**: Machine-related files were copied to `flatmachines` but **not removed** from `flatagents`
2. **Compatibility over separation**: The `flatagents` package was kept as a "kitchen sink" that re-exports everything
3. **Incomplete refactoring**: The `flatmachines` package was created correctly, but `flatagents` wasn't cleaned up

---

## 4. Corrected Architecture

### 4.1 Target State

```
flatagents/                    # Agent SDK only
├── flatagents/
│   ├── __init__.py           # Agent-only exports
│   ├── baseagent.py          # Base agent classes, extractors
│   ├── flatagent.py          # FlatAgent implementation
│   ├── profiles.py           # Model profile management
│   ├── validation.py         # Agent config validation
│   ├── monitoring.py         # Logging and observability
│   ├── utils.py              # Shared utilities (if agent-specific)
│   └── assets/
│       ├── flatagent.d.ts
│       ├── flatagent.schema.json
│       ├── profiles.d.ts
│       └── profiles.schema.json
└── pyproject.toml

flatmachines/                  # Orchestration only (current state is correct)
├── flatmachines/
│   ├── __init__.py
│   ├── flatmachine.py
│   ├── execution.py
│   ├── hooks.py
│   ├── actions.py
│   ├── persistence.py
│   ├── locking.py
│   ├── backends.py
│   ├── distributed.py
│   ├── distributed_hooks.py
│   ├── expressions/
│   ├── validation.py
│   ├── monitoring.py
│   ├── utils.py
│   ├── run.py
│   ├── agents.py             # AgentExecutor, AgentAdapter framework
│   └── adapters/
│       └── flatagent.py      # Optional FlatAgent adapter
│   └── assets/
│       ├── flatmachine.d.ts
│       ├── flatmachine.schema.json
│       ├── flatagents-runtime.d.ts
│       ├── flatagents-runtime.schema.json
│       └── MACHINES.md
└── pyproject.toml
```

### 4.2 Dependency Direction

```
flatagents  ←───optional───  flatmachines
   │                              │
   │ (no deps)                    │ (optional: flatagents, smolagents)
   ▼                              ▼
 LLM APIs                     Agent Adapters
```

- `flatagents` has **zero** orchestration dependencies
- `flatmachines` **optionally** depends on `flatagents` for the FlatAgent adapter

---

## 5. Migration Strategy

### 5.1 Approach: Clean Removal

The `flatmachines` package already has the correct implementation. The task is to **remove duplicate/machine code from flatagents**, not to change flatmachines.

### 5.2 Backwards Compatibility

For users who were importing machine classes from `flatagents`:

**Option A: Hard Break (Recommended)**
- Remove all machine exports from `flatagents`
- Users must update imports to `from flatmachines import FlatMachine, ...`
- Add deprecation notice in release notes

**Option B: Soft Deprecation**
- Keep re-exports in `flatagents` but emit `DeprecationWarning`
- Remove after 2 minor versions
- More work, delays the clean split

**Recommendation**: Option A (Hard Break) since we're at version 1.0.0 and the split is a major architectural change.

---

## 6. Task List for Corrected Implementation

### Phase 1: Clean Up flatagents Package

- [ ] **1.1** Delete `sdk/python/flatagents/flatagents/flatmachine.py`
- [ ] **1.2** Delete `sdk/python/flatagents/flatagents/execution.py`
- [ ] **1.3** Delete `sdk/python/flatagents/flatagents/hooks.py`
- [ ] **1.4** Delete `sdk/python/flatagents/flatagents/actions.py`
- [ ] **1.5** Delete `sdk/python/flatagents/flatagents/persistence.py`
- [ ] **1.6** Delete `sdk/python/flatagents/flatagents/locking.py`
- [ ] **1.7** Delete `sdk/python/flatagents/flatagents/backends.py`
- [ ] **1.8** Delete `sdk/python/flatagents/flatagents/distributed.py`
- [ ] **1.9** Delete `sdk/python/flatagents/flatagents/distributed_hooks.py`
- [ ] **1.10** Delete `sdk/python/flatagents/flatagents/expressions/` directory
- [ ] **1.11** Delete `sdk/python/flatagents/flatagents/run.py`

### Phase 2: Clean Up flatagents Assets

- [ ] **2.1** Delete `sdk/python/flatagents/flatagents/assets/flatmachine.d.ts`
- [ ] **2.2** Delete `sdk/python/flatagents/flatagents/assets/flatmachine.schema.json`
- [ ] **2.3** Delete `sdk/python/flatagents/flatagents/assets/flatmachine.slim.d.ts`
- [ ] **2.4** Delete `sdk/python/flatagents/flatagents/assets/flatagents-runtime.d.ts`
- [ ] **2.5** Delete `sdk/python/flatagents/flatagents/assets/flatagents-runtime.schema.json`
- [ ] **2.6** Delete `sdk/python/flatagents/flatagents/assets/flatagents-runtime.slim.d.ts`
- [ ] **2.7** Delete `sdk/python/flatagents/flatagents/assets/MACHINES.md`

### Phase 3: Update flatagents/__init__.py

- [ ] **3.1** Remove the entire `try/except` block that re-exports from flatmachines (lines 79-180)
- [ ] **3.2** Update `__all__` to only include agent-related exports
- [ ] **3.3** Verify no imports reference deleted modules

### Phase 4: Update flatagents/pyproject.toml

- [ ] **4.1** Remove `orchestration` optional dependency (or make it a pure re-export with deprecation warning if using Option B)
- [ ] **4.2** Remove flatmachines from `local` and `all` optional dependencies
- [ ] **4.3** Remove flatmachines from `gcp` optional dependencies

### Phase 5: Documentation Updates

- [ ] **5.1** Delete `sdk/python/flatagents/MACHINES.md` (machine docs should only be in flatmachines)
- [ ] **5.2** Update `sdk/python/flatagents/README.md` to clarify agent-only scope
- [ ] **5.3** Add migration guide for users importing machine code from flatagents

### Phase 6: Test Updates

- [ ] **6.1** Update/remove any tests in flatagents that test machine functionality
- [ ] **6.2** Ensure flatagents tests pass without flatmachines installed
- [ ] **6.3** Ensure flatmachines tests pass (they should already)

### Phase 7: GCP Module Review

- [ ] **7.1** Review `sdk/python/flatagents/flatagents/gcp/` directory
- [ ] **7.2** Determine if GCP backends are agent-specific or machine-specific
- [ ] **7.3** Move machine-specific GCP code to flatmachines if needed

### Phase 8: Validation

- [ ] **8.1** Install flatagents in isolation, verify it works for agent-only use cases
- [ ] **8.2** Install flatmachines with flatagents adapter, verify machine orchestration works
- [ ] **8.3** Run full test suite for both packages

---

## 7. Files to Keep in flatagents

After cleanup, `sdk/python/flatagents/flatagents/` should contain only:

```
flatagents/
├── __init__.py              # Clean agent-only exports
├── baseagent.py             # Base agent classes, extractors, LLM backends
├── flatagent.py             # FlatAgent implementation
├── profiles.py              # Model profile management
├── validation.py            # Agent config validation only
├── monitoring.py            # Logging and observability (shared is OK)
├── utils.py                 # Utilities (review for machine-specific code)
├── gcp/                     # Review - may contain machine code
│   └── ...
└── assets/
    ├── __init__.py
    ├── flatagent.d.ts
    ├── flatagent.schema.json
    ├── flatagent.slim.d.ts
    ├── profiles.d.ts
    ├── profiles.schema.json
    ├── profiles.slim.d.ts
    └── README.md
```

---

## 8. Open Questions

1. **Shared monitoring.py**: Both packages have a monitoring.py. Should this be a shared dependency, or is duplication acceptable?

2. **utils.py review**: Need to verify `flatagents/utils.py` doesn't contain machine-specific utilities.

3. **GCP backends**: The `gcp/` directory needs review to determine if it contains FlatMachine persistence backends that should move to flatmachines.

4. **Version synchronization**: Should both packages maintain lockstep versioning (1.0.0) or can they version independently after the split?

---

## 9. Success Criteria

After implementing this plan:

1. ✅ `flatagents` can be installed and used without any `flatmachines` code or dependencies
2. ✅ `flatmachines` can be installed with or without `flatagents` 
3. ✅ `from flatagents import FlatMachine` raises `ImportError` (clean break)
4. ✅ `from flatmachines import FlatMachine` works correctly
5. ✅ Users importing FlatAgent adapter: `from flatmachines.adapters import FlatAgentAdapter`
6. ✅ All tests pass for both packages independently

---

## 10. Estimated Effort

| Phase | Effort |
|-------|--------|
| Phase 1: Clean up files | 30 min |
| Phase 2: Clean up assets | 15 min |
| Phase 3-4: Update __init__ and pyproject | 30 min |
| Phase 5: Documentation | 1 hour |
| Phase 6: Test updates | 1-2 hours |
| Phase 7: GCP review | 30 min |
| Phase 8: Validation | 1 hour |
| **Total** | **4-5 hours** |

---

## Appendix A: Current File Inventory

### Files in flatagents that should be REMOVED (machine concerns):

```
sdk/python/flatagents/flatagents/
├── flatmachine.py           # DELETE
├── execution.py             # DELETE
├── hooks.py                 # DELETE
├── actions.py               # DELETE
├── persistence.py           # DELETE
├── locking.py               # DELETE
├── backends.py              # DELETE
├── distributed.py           # DELETE
├── distributed_hooks.py     # DELETE
├── run.py                   # DELETE
└── expressions/             # DELETE (entire directory)
    ├── __init__.py
    ├── cel.py
    └── simple.py

sdk/python/flatagents/flatagents/assets/
├── flatmachine.d.ts         # DELETE
├── flatmachine.schema.json  # DELETE
├── flatmachine.slim.d.ts    # DELETE
├── flatagents-runtime.d.ts  # DELETE (this is runtime contract for machines)
├── flatagents-runtime.schema.json  # DELETE
├── flatagents-runtime.slim.d.ts    # DELETE
└── MACHINES.md              # DELETE
```

### Files in flatagents that should REMAIN (agent concerns):

```
sdk/python/flatagents/flatagents/
├── __init__.py              # KEEP (but clean up)
├── baseagent.py             # KEEP
├── flatagent.py             # KEEP
├── profiles.py              # KEEP
├── validation.py            # KEEP
├── monitoring.py            # KEEP
├── utils.py                 # KEEP (review)
└── gcp/                     # REVIEW

sdk/python/flatagents/flatagents/assets/
├── __init__.py              # KEEP
├── flatagent.d.ts           # KEEP
├── flatagent.schema.json    # KEEP
├── flatagent.slim.d.ts      # KEEP
├── profiles.d.ts            # KEEP
├── profiles.schema.json     # KEEP
├── profiles.slim.d.ts       # KEEP
└── README.md                # KEEP
```

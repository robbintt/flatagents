# Decentralized Autoscaling for FlatAgents

## Overview

A decentralized autoscaling architecture for FlatAgents that enables work distribution across ephemeral worker machines without daemons or central orchestrators.

**Core principles**:
- **No daemons**: All machines are ephemeral
- **Job pool pattern**: Workers claim a single job, process, exit
- **Trigger-based activation**: External cues spawn parallelization checker
- **New runtime backends**: `RegistrationBackend`, `WorkBackend`

**Goals**:
- Add work distribution to FlatAgents runtime spec
- Support local (SQLite) and distributed (Redis, etc.) backends
- Enable autoscaling via trigger-based parallelization checks
- Keep workers stateless and short-lived

---

## Runtime Spec Extensions

### 1. `RegistrationBackend` (First-class)

```typescript
export interface RegistrationBackend {
  register(worker: WorkerRegistration): Promise<WorkerRecord>;
  heartbeat(worker_id: string, metadata?: Record<string, any>): Promise<void>;
  updateStatus(worker_id: string, status: string): Promise<void>;
  get(worker_id: string): Promise<WorkerRecord | null>;
  list(filter?: WorkerFilter): Promise<WorkerRecord[]>;
}

// Status values (string, not enum for extensibility):
// - "active": Worker is running and healthy
// - "terminating": Worker received shutdown signal
// - "terminated": Worker exited cleanly
// - "lost": Worker failed heartbeat, presumed dead

interface WorkerRegistration {
  worker_id: string;
  host?: string;
  pid?: number;
  capabilities?: string[];  // e.g., ["gpu", "paper-analysis"]
  started_at: string;
}

interface WorkerRecord extends WorkerRegistration {
  status: string;  // see status values above
  last_heartbeat: string;
  current_task_id?: string;
}

interface WorkerFilter {
  status?: string | string[];
  capability?: string;
  stale_threshold_seconds?: number;
}

// Implementation notes:
// - Time units: Python reference SDK uses seconds for all interval values
// - Stale threshold: SDKs SHOULD default to 2× heartbeat_interval if not specified
```

### 2. Heartbeat vs Timeout (Separate Concerns)

| Concept | Scope | Purpose |
|---------|-------|---------|
| `timeout` (existing) | Per-state | "This state must complete in N seconds" |
| `heartbeat_interval` | Per-worker | "Worker must signal alive every N seconds" |

Heartbeat lives in `RegistrationBackend` semantics, configured per-worker-machine:

```yaml
# worker_machine.yml
data:
  settings:
    heartbeat_interval: 30  # seconds
```

### 3. Work Backend (Simplified)

**Design principle**: Start simple, don't overengineer. SQLite table as first backend.

**Avoid**: "Channel" (Kafka semantic overlap), separate Queue/Message (premature)

**Decision**: Use `WorkBackend` — a minimal interface for work distribution.

```typescript
export interface WorkBackend {
  /** Get a named work pool */
  pool(name: string): WorkPool;
}

export interface WorkPool {
  /** Add work item. Returns item ID. */
  push(item: any, options?: { max_retries?: number }): Promise<string>;
  
  /** Atomically claim next item. Returns null if empty. */
  claim(worker_id: string): Promise<WorkItem | null>;
  
  /** Mark complete. Removes from pool (or marks done). */
  complete(item_id: string, result?: any): Promise<void>;
  
  /** 
   * Mark failed. Increments attempts.
   * If attempts >= max_retries, marks as "poisoned" instead of returning to pool.
   */
  fail(item_id: string, error?: string): Promise<void>;
  
  /** Pool depth (unclaimed items). */
  size(): Promise<number>;
  
  /** Release jobs claimed by a specific worker (for stale worker cleanup). */
  releaseByWorker(worker_id: string): Promise<number>;
}

interface WorkItem {
  id: string;
  data: any;
  claimed_by?: string;
  attempts: number;
  max_retries: number;  // default: 3
}

// Job status values (string):
// - "pending": Available for claim
// - "claimed": Currently being processed
// - "done": Successfully completed
// - "poisoned": Failed max_retries times, will not be retried

// Implementation notes:
// - Atomic claim: SDKs MUST ensure no two workers can claim the same job
// - Test requirements: Include concurrent claim race condition tests
```

**SQLite implementation**: Single table with `status` column (`pending`/`claimed`/`done`/`poisoned`).

**Future (v2)**: Job visibility timeout (auto-release if not completed within N seconds).

---

## Architecture: Trigger-Based Parallelization

### The Problem
We need to scale workers up/down based on queue depth, but we don't want daemons.

### The Solution: Trigger-Registered Parallelization Checker

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Trigger-Based Scaling (No Daemons)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    spawn     ┌─────────────────────┐                  │
│  │   Trigger    │─────────────▶│ Parallelization     │                  │
│  │  (external)  │              │    Checker          │                  │
│  └──────────────┘              └─────────┬───────────┘                  │
│        ▲                                 │                               │
│        │                    ┌────────────┴────────────┐                 │
│        │                    ▼                         ▼                  │
│  ┌─────┴──────┐      ┌──────────────┐         ┌──────────────┐          │
│  │ Trigger    │      │  launch N    │         │   do nothing │          │
│  │ Registry   │      │  workers     │         │   (at limit) │          │
│  └────────────┘      └──────┬───────┘         └──────────────┘          │
│                             │                                            │
│                    ┌────────┴────────┐                                  │
│                    ▼        ▼        ▼                                  │
│              ┌─────────┐ ┌─────────┐ ┌─────────┐                        │
│              │ Worker  │ │ Worker  │ │ Worker  │                        │
│              │ Machine │ │ Machine │ │ Machine │                        │
│              └────┬────┘ └────┬────┘ └────┬────┘                        │
│                   │          │          │                               │
│                   ▼          ▼          ▼                               │
│              ┌─────────────────────────────────┐                        │
│              │         Job Queue               │                        │
│              │  (claim 1, process, exit)       │                        │
│              └─────────────────────────────────┘                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Trigger Types

| Type | Execution | When to Use |
|------|-----------|-------------|
| Cron | External cron spawns machine | Periodic checks, no infra |
| Webhook | HTTP handler spawns machine | Push on job insert |
| Lambda/K3s | Serverless trigger | Cloud deployments |
| Local subprocess | Python spawns process | Local dev/test |
| In-loop (non-blocking) | Machine runs inline | Single-process mode |

```yaml
# trigger_registry.yml
triggers:
  - name: cron_5min
    type: cron
    schedule: "*/5 * * * *"
    machine: parallelization_checker
    input:
      pool_id: paper_analysis

  - name: local_subprocess
    type: subprocess
    on: work_added  # event name
    machine: parallelization_checker
```

**Local execution modes**:
- **Subprocess**: Spawn parallelization checker as new Python process (non-blocking)
- **In-loop**: Run checker inline (breaks blocking execution, needs test suite)

> [!NOTE]
> In-loop mode means `machine.execute()` can't block on result. Requires async handling pattern and full unit/integration test coverage.

### Parallelization Checker Machine

```yaml
spec: flatmachine
spec_version: "0.8.3"

data:
  name: parallelization_checker
  
  context:
    pool_id: "{{ input.pool_id }}"
    max_workers: "{{ input.max_workers | default(10) }}"
  
  states:
    start:
      type: initial
      transitions:
        - to: check_state
    
    check_state:
      action: get_pool_state  # Hook reads queue + registry
      output_to_context:
        queue_depth: "{{ output.queue_depth }}"
        active_workers: "{{ output.active_workers }}"
        workers_to_spawn: "{{ [output.queue_depth - output.active_workers, context.max_workers - output.active_workers, 0] | max }}"
      transitions:
        - condition: "context.workers_to_spawn > 0"
          to: spawn_workers
        - to: done
    
    spawn_workers:
      foreach: "{{ range(context.workers_to_spawn) }}"
      launch: job_worker
      launch_input:
        pool_id: "{{ context.pool_id }}"
      transitions:
        - to: done
    
    done:
      type: final
      output:
        spawned: "{{ context.workers_to_spawn }}"
```

### Job Worker Machine (Ephemeral)

```yaml
spec: flatmachine
spec_version: "0.8.3"

data:
  name: job_worker
  
  settings:
    heartbeat_interval: 30
  
  context:
    pool_id: "{{ input.pool_id }}"
  
  states:
    start:
      type: initial
      transitions:
        - to: claim_job
    
    claim_job:
      action: claim_job  # Atomic claim via WorkBackend
      output_to_context:
        job: "{{ output.job }}"
        job_id: "{{ output.job_id }}"
      transitions:
        - condition: "context.job == null"
          to: no_work
        - to: process_job
    
    process_job:
      machine: actual_job_processor  # Your paper_analyzer, etc.
      input:
        job: "{{ context.job }}"
      output_to_context:
        result: "{{ output }}"
      on_error: job_failed
      transitions:
        - to: complete_job
    
    complete_job:
      action: complete_job
      transitions:
        - to: done
    
    job_failed:
      action: fail_job  # Increments attempts, may poison job
      transitions:
        - to: done
    
    no_work:
      type: final
      output:
        status: "no_work_available"
    
    done:
      type: final
      output:
        job_id: "{{ context.job_id }}"
        result: "{{ context.result }}"
```

### Stale Worker Reaper Machine (Dedicated)

Separate concern from parallelization checker. Cleans up lost workers and releases their jobs.

```yaml
spec: flatmachine
spec_version: "0.8.3"

data:
  name: stale_worker_reaper
  
  context:
    pool_id: "{{ input.pool_id }}"
    stale_threshold_seconds: "{{ input.stale_threshold_seconds | default(60) }}"
  
  states:
    start:
      type: initial
      transitions:
        - to: find_stale_workers
    
    find_stale_workers:
      action: list_stale_workers  # Hook queries registry with stale filter
      output_to_context:
        stale_workers: "{{ output.workers }}"
      transitions:
        - condition: "context.stale_workers | length == 0"
          to: done
        - to: reap_workers
    
    reap_workers:
      foreach: "{{ context.stale_workers }}"
      as: worker
      action: reap_worker  # Mark lost, release jobs, drop any late results
      transitions:
        - to: done
    
    done:
      type: final
      output:
        reaped_count: "{{ context.stale_workers | length }}"
```

**Reaper behavior**:
1. Query workers where `(now - last_heartbeat) > stale_threshold`
2. For each stale worker:
   - Mark status as "lost"
   - Call `WorkPool.releaseByWorker(worker_id)` to return claimed jobs
   - If worker sends results after being reaped, ignore them (worker_id no longer valid)


---

## FlatAgents SDK Implementation

### Spec Changes: `flatagents-runtime.d.ts`

| Change | Description |
|--------|-------------|
| Add `RegistrationBackend` interface | Worker lifecycle, heartbeat, status |
| Add `WorkBackend` interface | Work pool with atomic claim |
| Add `WorkerStatus` type | `"active" \| "terminating" \| "terminated" \| "lost"` |
| Add `WorkerRegistration` interface | Worker identity fields |
| Add `WorkerRecord` interface | Registration + runtime state |
| Add `WorkItem` interface | Job data + claim metadata |
| Extend `BackendConfig` | Add `registration`, `work` selectors |
| Extend `SDKRuntimeWrapper` | Add `registration_backend`, `work_backend` |

### SDK Implementation Requirements

SDKs MUST implement:

| Backend | Required Implementations |
|---------|-------------------------|
| `RegistrationBackend` | `SQLiteRegistrationBackend` (MUST), `MemoryRegistrationBackend` (SHOULD) |
| `WorkBackend` | `SQLiteWorkBackend` (MUST), `MemoryWorkBackend` (SHOULD) |

### Machine YAML Additions

```yaml
# New settings for worker machines
data:
  settings:
    heartbeat_interval: 30  # seconds, enables heartbeat
    worker_pool: "my_pool"  # optional, for worker grouping
```

### Hook Integration

Machines with `heartbeat_interval` setting trigger automatic hook behavior:

| Lifecycle Event | Hook Called | Backend Method |
|-----------------|-------------|----------------|
| Machine start | `on_machine_start` | `registration.register()` |
| State transition | (internal) | `registration.heartbeat()` |
| Machine end (success) | `on_machine_end` | `registration.updateStatus("terminated")` |
| Machine end (error) | `on_error` | `registration.updateStatus("lost")` |

### Custom Hook Actions

For work distribution, hooks implement custom actions:

```python
class DistributedWorkerHooks(MachineHooks):
    def on_action(self, action: str, context: dict) -> dict:
        if action == "get_pool_state":
            pool = self.work_backend.pool(context["pool_id"])
            registry = self.registration_backend
            return {
                "queue_depth": pool.size(),
                "active_workers": len(registry.list(status="active"))
            }
        
        if action == "claim_job":
            pool = self.work_backend.pool(context["pool_id"])
            item = pool.claim(context["worker_id"])
            return {"job": item.data if item else None, "job_id": item.id if item else None}
        
        if action == "complete_job":
            pool = self.work_backend.pool(context["pool_id"])
            pool.complete(context["job_id"], context.get("result"))
            return context
        
        if action == "fail_job":
            pool = self.work_backend.pool(context["pool_id"])
            pool.fail(context["job_id"], context.get("error"))
            return context
        
        return context
```

### Launch Subprocess Support

For local trigger execution, SDK must support subprocess launching:

```python
# In parallelization checker, foreach+launch spawns workers
# SDK implementation of launch: for local backend

def launch_machine(machine_name: str, input: dict) -> str:
    """Fire-and-forget machine execution via subprocess."""
    execution_id = generate_execution_id()
    subprocess.Popen([
        sys.executable, "-m", "flatagents.run",
        "--machine", machine_name,
        "--input", json.dumps(input),
        "--execution-id", execution_id
    ])
    return execution_id
```

### Backend Configuration in YAML

```yaml
# machine.yml
data:
  settings:
    backends:
      registration: sqlite     # or: memory, redis
      work: sqlite             # or: memory, redis
      registration_path: ./data/workers.sqlite
      work_path: ./data/workers.sqlite  # can share DB
```

### SQLite Schema for Backends

```sql
-- worker_registry table (RegistrationBackend)
CREATE TABLE IF NOT EXISTS worker_registry (
    worker_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    host TEXT,
    pid INTEGER,
    capabilities TEXT,  -- JSON array
    pool_id TEXT,
    started_at TEXT NOT NULL,
    last_heartbeat TEXT NOT NULL,
    current_task_id TEXT
);

-- work_pool table (WorkBackend)
CREATE TABLE IF NOT EXISTS work_pool (
    id TEXT PRIMARY KEY,
    pool_name TEXT NOT NULL,
    data TEXT NOT NULL,  -- JSON
    status TEXT NOT NULL DEFAULT 'pending',
    claimed_by TEXT,
    claimed_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    result TEXT,  -- JSON
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_work_pool_status ON work_pool(pool_name, status);
CREATE INDEX IF NOT EXISTS idx_worker_registry_status ON worker_registry(status);
```

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| **Backend naming** | `WorkBackend` (simple, SQLite first). Add `MessageBackend` later if needed. |
| **Job:Machine mapping** | 1:1. Job type maps directly to machine type. No capability routing. |
| **Trigger execution** | Config-based registry. Local: subprocess or in-loop. Cloud: cron/lambda/webhook. |

## Implementation Sequence

### Phase 0: FlatAgents SDK Extensions

Location: `~/code/flatagents/`

Before the dummy can use distributed backends, the SDK must support them.

**Tasks**:

1. **Update `flatagents-runtime.d.ts`** ✅
   - [x] Add `RegistrationBackend` interface
   - [x] Add `WorkBackend` interface
   - [x] Add `WorkerStatus`, `WorkerRegistration`, `WorkerRecord`, `WorkItem` types
   - [x] Extend `BackendConfig` with `registration`, `work` selectors
   - [x] Extend `SDKRuntimeWrapper` with `registration_backend`, `work_backend`

2. **Python SDK implementation** (`sdk/python/`) ✅
   - [x] `SQLiteRegistrationBackend` class
   - [x] `SQLiteWorkBackend` class
   - [x] `MemoryRegistrationBackend` class (for tests)
   - [x] `MemoryWorkBackend` class (for tests)
   - [x] Backend factory to instantiate from config
   - [x] Integration test passing

3. **Launch subprocess support** (`sdk/python/`) ✅
   - [x] `SubprocessInvoker` class for fire-and-forget execution
   - [x] `launch_machine()` standalone utility function
   - [x] `run.py` CLI entry point module

4. **Machine settings parsing** (Deferred to Phase 1)
   - [ ] Parse `heartbeat_interval` from settings (implement when building worker example)
   - [ ] Wire automatic heartbeat calls (implement when building worker example)

**Deliverable**: SDK can instantiate `RegistrationBackend` and `WorkBackend` from machine config.

---

### Phase 1: Dummy Example (Full Distributed Properties)

Location: `sdk/examples/distributed_worker/`

The dummy proves all distributed patterns with a trivial job processor.

```
sdk/examples/distributed_worker/
├── python/
│   ├── work_pool.py              # SQLiteWorkBackend implementation
│   ├── worker_registry.py        # SQLiteRegistrationBackend implementation
│   ├── hooks.py                  # claim_job, complete_job, get_pool_state, register_worker, reap_worker
│   ├── run_checker.py            # CLI: run parallelization checker (cron/manual)
│   ├── run_reaper.py             # CLI: run stale worker reaper
│   ├── run_worker.py             # CLI: run single worker
│   └── seed_jobs.py              # CLI: add test jobs to pool
├── config/
│   ├── parallelization_checker.yml
│   ├── stale_worker_reaper.yml   # Dedicated reaper machine
│   ├── job_worker.yml
│   ├── echo_processor.yml        # Trivial: echoes input after delay
│   └── profiles.yml
├── data/
│   └── worker.sqlite             # Work pool + worker registry
└── README.md
```

**What the dummy proves**:

| Component | Implementation |
|-----------|----------------|
| `WorkBackend` | SQLite `work_pool` table |
| `RegistrationBackend` | SQLite `worker_registry` table |
| `WorkPool.claim()` | Atomic `UPDATE ... WHERE status='pending' LIMIT 1` |
| Parallelization checker | Full machine with `foreach` + `launch` |
| Stale worker reaper | Dedicated cleanup machine |
| Job worker | Full machine with heartbeat setting |
| Trigger: cron | Manual CLI simulating cron |
| Trigger: subprocess | Python subprocess spawn |

**What makes it "dummy"**: The job processor (`echo_processor.yml`) is trivial — it just echoes input after a configurable delay.

---

### Phase 2: Real Workload (research_paper_analysis)

Location: `~/code/research_crawler/research_paper_analysis/`

Same patterns, real workload.

| Dummy Component | Real Equivalent |
|-----------------|-----------------|
| `work_pool` table | `arxiv_crawler.paper_queue` table |
| `worker_registry` table | New table in same DB |
| `echo_processor.yml` | `analyzer_machine.yml` |
| `seed_jobs.py` | Existing crawler pipeline |
| `run_checker.py` | Cron job or webhook trigger |

**Additions for real**:
- Hooks integrate with existing `research_paper_analysis.hooks.JsonValidationHooks`
- Results written to `paper_queue.summary_path`
- Error handling writes to `paper_queue.error`

---

## Phase 1 Checklist (Dummy Requirements) ✅

The dummy is NOT simplified. Every distributed property must be present:

- [x] `WorkBackend` with SQLite implementation (via `distributed.py`)
- [x] `RegistrationBackend` with SQLite implementation (via `distributed.py`)
- [x] `WorkPool.claim()` is atomic (no race conditions)
- [x] `WorkPool.fail()` increments attempts, poisons after max_retries
- [x] `WorkPool.releaseByWorker()` returns claimed jobs to pool
- [x] `parallelization_checker.yml` reads pool depth + active workers
- [x] `parallelization_checker.yml` uses `foreach` + `launch`
- [x] `stale_worker_reaper.yml` marks stale workers as lost
- [x] `stale_worker_reaper.yml` releases jobs from stale workers
- [x] `job_worker.yml` has `heartbeat_interval` setting
- [x] `job_worker.yml` registers on start, deregisters on end
- [ ] Cron trigger tested (manual CLI) - **Ready for manual testing**
- [ ] Subprocess trigger tested - **Ready for manual testing**
- [ ] Multiple concurrent workers tested (no race conditions) - **Ready for manual testing**

---

## Verification Plan

> [!CAUTION]
> **DO NOT DO - NOT READY**: Automated tests require concurrent claim race condition tests. These are complex to implement correctly. Manual verification only for now.

### Dummy Verification (Manual)

1. **Seed 10 jobs**: `python seed_jobs.py --count 10`
2. **Run checker**: `python run_checker.py --max-workers 3`
3. **Observe**: 3 workers spawn, claim jobs, process, exit
4. **Run checker again**: Spawns more workers for remaining jobs
5. **Verify**: All 10 jobs complete, no duplicates, no races
6. **Kill a worker mid-job**: Simulate stale worker
7. **Run reaper**: `python run_reaper.py`
8. **Verify**: Job returned to pool, worker marked lost
9. **Fail a job max_retries times**: Verify it becomes poisoned

### Real Verification (Manual)

1. **Migrate hooks**: Add distributed hooks to `research_paper_analysis`
2. **Run with paper_queue**: Process real papers from arxiv crawler
3. **Verify**: Summaries written, errors handled, no orphaned workers

### Future: Automated Tests

When ready, add:
- Concurrent claim race condition tests (spawn N workers, verify no duplicate claims)
- Stale worker detection tests (mock time, verify reaper behavior)
- Poison job tests (fail job max_retries times, verify status)

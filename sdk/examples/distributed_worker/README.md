# Distributed Worker Example

A complete example demonstrating FlatAgents' distributed worker pattern with:

- **Work distribution** via `WorkBackend` (SQLite-based job pool)
- **Worker lifecycle** via `RegistrationBackend` (worker registration + heartbeat)
- **Parallelization** via trigger-based scaling (spawn workers based on queue depth)
- **Fault tolerance** via stale worker reaper (cleanup dead workers)

## Quick Start

```bash
# 1. Seed some jobs
python python/seed_jobs.py --count 10

# 2. Run the parallelization checker (spawns workers)
python python/run_checker.py --max-workers 3

# 3. Watch workers process jobs
# (workers are spawned automatically by the checker)

# 4. Run the stale worker reaper (cleanup)
python python/run_reaper.py
```

## Architecture

```
┌─────────────────┐    spawns     ┌─────────────────┐
│  Checker        │──────────────▶│  Worker 1       │
│  (cron/manual)  │               │  (claims 1 job) │
└─────────────────┘               └────────┬────────┘
        │                                   │
        │                                   ▼
        │                         ┌─────────────────┐
        │                         │  SQLite DB      │
        │                         │  - work_pool    │
        └────────────────────────▶│  - workers      │
                                  └─────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `python/hooks.py` | Custom hooks for job claiming, worker registration |
| `python/seed_jobs.py` | CLI: seed test jobs into the pool |
| `python/run_checker.py` | CLI: run parallelization checker |
| `python/run_worker.py` | CLI: run a single worker |
| `python/run_reaper.py` | CLI: run stale worker reaper |
| `config/parallelization_checker.yml` | Machine: checks pool depth, spawns workers |
| `config/job_worker.yml` | Machine: claims job → runs processor → completes |
| `config/echo_processor.yml` | Machine: trivial job processor (echoes input) |
| `config/stale_worker_reaper.yml` | Machine: finds stale workers, releases their jobs |
| `config/profiles.yml` | Model profiles |

## What This Proves

- ✅ Atomic job claiming (no race conditions)
- ✅ Worker registration and heartbeat
- ✅ Fire-and-forget subprocess spawning
- ✅ Stale worker detection and cleanup
- ✅ Job retry and poisoning after max_retries

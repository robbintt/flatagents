# Lifecycle Management Example

Demonstrates the three lifecycle management methods provided by `flatmachines.lifecycle`:

1. **`ExecutionStore`** — Backend-agnostic execution index with list/query/delete.
2. **`ExecutionManager`** — Central lifecycle manager with run/resume/list/cleanup.
3. **`supervised_run()`** — Simple convenience function for auto-retry on failure.

## Quick Start

```bash
pip install flatmachines
python main.py
```

## What It Shows

- Running a machine with automatic retry on transient failure
- Listing and querying past executions
- Resuming a specific failed execution
- Cleaning up old checkpoint data
- Using `supervised_run()` for simple one-shot resilient execution

## Use Cases

The lifecycle manager handles these scenarios generically across backends:

| Use Case | Method |
|----------|--------|
| Fire-and-forget resilient execution | `supervised_run()` |
| Run + retry + track executions | `ExecutionManager.run()` |
| Resume a crashed execution | `ExecutionManager.resume()` |
| Dashboard / monitoring | `ExecutionManager.list_executions()` |
| Garbage collection | `ExecutionManager.cleanup()` |
| Custom execution tracking | `ExecutionStore` subclass |
| Batch job management | `ExecutionManager` + loop |
| Long-running pipeline recovery | `ExecutionManager.resume()` |
| Multi-tenant execution isolation | Separate `ExecutionStore` per tenant |
| Cost tracking across executions | `ExecutionRecord.total_cost` |

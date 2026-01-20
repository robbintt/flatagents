# FlatAgents Peering Example (Python)

Demonstrates machine-to-machine communication, persistence, and checkpointing in FlatAgents for distributed workflows.

## Features Demonstrated

### 1. Machine Peering
- **Orchestrator**: Launches worker nodes without waiting
- **Worker Nodes**: Process tasks independently
- **Communication**: Results shared via result backend

### 2. Persistence and Checkpointing
- **Memory Backend**: In-memory checkpoint storage
- **Resume Capability**: Can resume from any checkpoint
- **State Management**: Full context preservation

### 3. Fire-and-Forget Pattern
- Launch machines without blocking execution
- Workers run independently in background
- Results available via polling or callbacks

## Quick Start

```bash
./run.sh
```

## Development Options

```bash
# Use local flatagents package (for development)
./run.sh --local
```

## File Structure

```
peering/
├── config/
│   ├── orchestrator.yml      # Launches worker nodes
│   ├── peering_demo.yml      # Demo flow (orchestrator + worker node)
│   ├── worker_node.yml       # Processes tasks independently
│   └── worker_task.yml       # Single-task worker wrapper
├── python/
│   ├── src/
│   │   └── peering/
│   │       └── main.py        # Demo application
│   ├── pyproject.toml
│   ├── run.sh
│   └── README.md
└── js/                        # JS example
```

## How It Works

## Peering Demo Diagram

```
peering_demo (flatmachine)
┌───────────────────────────────────────────────────────────┐
│ state: run_orchestrator                                   │
│   machine: orchestrator                                   │
│   └─ launch worker_node (fire-and-forget)                 │
│       input: context.tasks                                │
│   output → context.orchestrator_result                    │
└───────────────┬───────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│ state: run_worker_node                                     │
│   machine: worker_node                                     │
│   input: context.worker_tasks                              │
│   foreach task → worker_task → worker agent                │
│   output → context.worker_result                           │
└───────────────┬───────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│ state: done (final)                                        │
│   output: orchestrator_result + worker_node_result         │
└───────────────────────────────────────────────────────────┘
```

### Orchestrator Pattern
```yaml
states:
  initial:
    launch: [worker_node]  # Fire-and-forget
    launch_input:
      tasks: "{{ context.tasks }}"
    transitions:
      - to: wait_for_results
```

### Worker Node Processing
```yaml
states:
  process_tasks:
    foreach: "{{ context.tasks }}"
    as: task
    machine: worker_task
    output_to_context:
      results: "{{ output }}"
```

### Persistence Setup
```yaml
persistence:
  enabled: true
  backend: memory
```

## Expected Output

You'll see:
1. **Orchestrator Launch**: Tasks delegated to worker nodes
2. **Worker Processing**: Independent task execution
3. **Checkpoint Demo**: Execution ID for potential resume
4. **Distributed Results**: Processed data from multiple nodes

## Advanced Features

### Checkpoint and Resume
```python
# Save execution ID for later resume
execution_id = machine.execution_id

# Resume from checkpoint later
resumed_machine = FlatMachine(config_file=...)
await resumed_machine.execute(resume_from=execution_id)
```

### Result Backend
```python
result_backend = InMemoryResultBackend()
await result_backend.write(f"flatagents://{execution_id}/result", data)
```

## Learn More

- FlatAgents Documentation: ../../README.md
- Persistence: ../README.md#persistence--checkpointing
- Other Examples: ../

# FlatMachines (Python SDK)

State-machine orchestration for LLM agents. FlatMachines is **agent-framework agnostic** and uses adapters to execute agents from FlatAgents, smolagents, pi-mono, or other runtimes.

**For LLM/machine readers:** see [MACHINES.md](./MACHINES.md).

## Install

```bash
pip install flatmachines[flatagents]
```

Optional extras:
- `flatmachines[cel]` – CEL expression engine
- `flatmachines[validation]` – JSON schema validation
- `flatmachines[metrics]` – OpenTelemetry metrics
- `flatmachines[smolagents]` – smolagents adapter

## Quick Start

```python
from flatmachines import FlatMachine

machine = FlatMachine(config_file="workflow.yml")
result = await machine.execute(input={"query": "..."})
print(result)
```

**workflow.yml**
```yaml
spec: flatmachine
spec_version: "0.10.0"

data:
  name: reviewer
  agents:
    reviewer: ./reviewer.yml
  states:
    start:
      type: initial
      agent: reviewer
      input:
        code: "{{ input.code }}"
      output_to_context:
        review: "{{ output }}"
      transitions:
        - to: done
    done:
      type: final
      output:
        review: "{{ context.review }}"
```

## Agent Adapters

FlatMachines delegates agent execution to adapters. Built-ins are registered automatically if their dependencies are installed:
- **flatagent** – uses FlatAgents configs (`flatmachines[flatagents]`)
- **smolagents** – executes `MultiStepAgent` via `agent_ref.ref` factories
- **pi-agent** – Node bridge to pi-mono using `pi_agent_runner.mjs`

Agent refs in `data.agents` can be:
- string path to a flatagent config
- inline flatagent config (`spec: flatagent`)
- typed adapter ref: `{ type: "smolagents" | "pi-agent" | "flatagent", ref?: "...", config?: {...} }`

Custom adapters can be registered via `AgentAdapterRegistry`.

## State Execution Order

For each state, the Python runtime executes in this order:
1. `action` → `hooks.on_action`
2. `launch` → fire-and-forget machine(s)
3. `machine` / `foreach` → peer machines (blocking)
4. `agent` → adapter + execution strategy
5. `output` → render final output for `type: final`

Jinja2 templates render `input`, `context`, and `output`. A plain string like `context.foo` resolves to the actual value (not a string).

## Execution Types

```yaml
execution:
  type: retry
  backoffs: [2, 8, 16]
  jitter: 0.1
```

Supported: `default`, `retry`, `parallel`, `mdap_voting`.

## Parallelism & Launching

- `machine: child` → invoke peer machine (blocking)
- `machine: [a, b]` → parallel
- `foreach: "{{ context.items }}"` → dynamic parallelism
- `launch: child` → fire-and-forget; result is written to backend

## Persistence & Resume

```yaml
persistence:
  enabled: true
  backend: local  # local | memory
  checkpoint_on: [machine_start, state_enter, execute, state_exit, machine_end]
```

Resume with `machine.execute(resume_from=execution_id)`. Checkpoints store `MachineSnapshot` including pending launches.

## Hooks

Configure hooks via `data.hooks`:
```yaml
hooks:
  file: ./hooks.py
  class: MyHooks
  args: { ... }
```

Built-ins: `LoggingHooks`, `MetricsHooks`, `WebhookHooks`, `CompositeHooks`.

## Invokers & Result Backends

Invokers define how peer machines are launched:
- `InlineInvoker` (default)
- `QueueInvoker` (base class for external queues)
- `SubprocessInvoker` (`python -m flatmachines.run`)

Results are written/read via `ResultBackend` URIs: `flatagents://{execution_id}/result`.

## Logging & Metrics

```python
from flatmachines import setup_logging, get_logger
setup_logging(level="INFO")
logger = get_logger(__name__)
```

Env vars match FlatAgents: `FLATAGENTS_LOG_LEVEL`, `FLATAGENTS_LOG_FORMAT`, `FLATAGENTS_LOG_DIR`.

Metrics require `flatmachines[metrics]` and `FLATAGENTS_METRICS_ENABLED=true`.

## CLI Runner

```bash
python -m flatmachines.run --config machine.yml --input '{"key": "value"}'
```

## Examples (Repo)

- [helloworld](../../examples/helloworld/python)
- [writer_critic](../../examples/writer_critic/python)
- [parallelism](../../examples/parallelism/python)
- [distributed_worker](../../examples/distributed_worker/python)

## Specs

Source of truth:
- [`flatmachine.d.ts`](./flatmachines/assets/flatmachine.d.ts)
- [`flatagent.d.ts`](./flatmachines/assets/flatagent.d.ts)
- [`profiles.d.ts`](./flatmachines/assets/profiles.d.ts)

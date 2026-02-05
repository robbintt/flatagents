# FlatAgents

Define LLM agents in YAML. Run them anywhere.

## What is FlatAgents?

FlatAgents is a **lightweight framework for single LLM calls**. Each agent is a YAML config that specifies:
- Model configuration
- System and user prompts
- Structured output schema

For **multi-agent orchestration**, state machines, and workflows, see [flatmachines](https://pypi.org/project/flatmachines/).

## Why?

- **Composition over inheritance** — compose stateless agents with simple config
- **Compact structure** — easy for LLMs to read and generate
- **Inspectable** — every agent is readable config
- **Language-agnostic** — reduce code in any particular runtime
- **Common TypeScript interface** — single schema for agents

*Inspired by Kubernetes manifests and character card specifications.*

## Versioning

All specs (`flatagent.d.ts`, `profiles.d.ts`) and SDKs use **lockstep versioning**. A single version number applies across the entire repository.

## Quick Start

```bash
pip install flatagents[all]
```

```python
from flatagents import FlatAgent

agent = FlatAgent(config_file="reviewer.yml")
result = await agent.call(query="Review this code...")
print(result.output)
```

## Example Agent

**reviewer.yml**
```yaml
spec: flatagent
spec_version: "1.0.0"

data:
  name: code-reviewer

  model: "smart-expensive"  # Reference profile from profiles.yml

  system: |
    You are a senior code reviewer. Analyze code for bugs,
    style issues, and potential improvements.

  user: |
    Review this code:
    {{ input.code }}

  output:
    issues:
      type: list
      items:
        type: str
      description: "List of issues found"
    rating:
      type: str
      enum: ["good", "needs_work", "critical"]
      description: "Overall code quality"
```

**What the fields mean:**

- **spec/spec_version** — Format identifier and version
- **data.name** — Agent identifier
- **data.model** — Profile name, inline config, or profile with overrides
- **data.system** — System prompt (sets behavior)
- **data.user** — User prompt template (uses Jinja2, `{{ input.* }}` for runtime values)
- **data.output** — Structured output schema (the runtime extracts these fields)

## Model Profiles

Centralize model configurations in `profiles.yml` and reference them by name:

**profiles.yml**
```yaml
spec: flatprofiles
spec_version: "1.0.0"

data:
  model_profiles:
    fast-cheap:
      provider: cerebras
      name: zai-glm-4.6
      temperature: 0.6
      max_tokens: 2048

    smart-expensive:
      provider: anthropic
      name: claude-3-opus-20240229
      temperature: 0.3
      max_tokens: 4096

  default: fast-cheap      # Fallback when agent has no model
  # override: smart-expensive  # Uncomment to force all agents
```

**Agent usage:**
```yaml
# String shorthand — profile lookup
model: "fast-cheap"

# Profile with overrides
model:
  profile: "fast-cheap"
  temperature: 0.9

# Inline config (no profile)
model:
  provider: openai
  name: gpt-4
  temperature: 0.3
```

Resolution order (low → high): default profile → named profile → inline overrides → override profile

## Output Types

```yaml
output:
  answer:      { type: str }
  count:       { type: int }
  score:       { type: float }
  valid:       { type: bool }
  raw:         { type: json }
  items:       { type: list, items: { type: str } }
  metadata:    { type: object, properties: { key: { type: str } } }
```

Use `enum: [...]` to constrain string values.

## Multi-Agent Workflows

For orchestration, install [flatmachines](https://pypi.org/project/flatmachines/):

```bash
pip install flatmachines[flatagents]
```

```python
from flatmachines import FlatMachine

machine = FlatMachine(config_file="workflow.yml")
result = await machine.execute(input={"query": "..."})
```

FlatMachine provides: state transitions, conditional branching, loops, retry with backoff, error recovery, and distributed worker patterns—all in YAML.

## Features

- Python SDK (TypeScript SDK in progress)
- Structured output extraction
- Multiple LLM backends (LiteLLM, AISuite)
- Schema validation
- Metrics and logging
- Model profile management

## Specs

TypeScript definitions are the source of truth:
- [`flatagent.d.ts`](../../spec/flatagent.d.ts)
- [`profiles.d.ts`](../../spec/profiles.d.ts)

## Python SDK

```bash
pip install flatagents[litellm]
```

### LLM Backends

```python
from flatagents import LiteLLMBackend, AISuiteBackend

# LiteLLM (default)
agent = FlatAgent(config_file="agent.yml")

# AISuite
backend = AISuiteBackend(model="openai:gpt-4o")
agent = FlatAgent(config_file="agent.yml", backend=backend)
```

### Schema Validation

```python
from flatagents import validate_flatagent_config

warnings = validate_flatagent_config(config)
```

### Logging & Metrics

```python
from flatagents import setup_logging, get_logger

setup_logging(level="INFO")  # Respects FLATAGENTS_LOG_LEVEL env var
logger = get_logger(__name__)
```

**Env vars**: `FLATAGENTS_LOG_LEVEL` (`DEBUG`/`INFO`/`WARNING`/`ERROR`), `FLATAGENTS_LOG_FORMAT` (`standard`/`json`/`simple`)

For OpenTelemetry metrics:

```bash
pip install flatagents[metrics]
export FLATAGENTS_METRICS_ENABLED=true
```

Metrics are enabled by default and print to stdout every 5s. Redirect to file or use OTLP for production:

```bash
# Metrics print to stdout by default
python your_script.py

# Save to file
python your_script.py >> metrics.log 2>&1

# Disable if needed
FLATAGENTS_METRICS_ENABLED=false python your_script.py

# Send to OTLP collector for production
OTEL_METRICS_EXPORTER=otlp \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
python your_script.py
```

**Env vars for metrics**:

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLATAGENTS_METRICS_ENABLED` | `true` | Enable OpenTelemetry metrics |
| `OTEL_METRICS_EXPORTER` | `console` | `console` (stdout) or `otlp` (production) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTLP collector endpoint |
| `OTEL_METRIC_EXPORT_INTERVAL` | `5000` / `60000` | Export interval in ms (5s for console, 60s for otlp) |
| `OTEL_SERVICE_NAME` | `flatagents` | Service name in metrics |

## Migration from Pre-1.0

If you were importing machine classes from `flatagents`:

```python
# Old (deprecated)
from flatagents import FlatMachine, MachineHooks

# New
from flatmachines import FlatMachine, MachineHooks
```

The `flatmachines` package contains all orchestration functionality:
- FlatMachine and state machines
- Hooks (MachineHooks, LoggingHooks, etc.)
- Execution types (retry, parallel, MDAP)
- Persistence and checkpointing
- Distributed worker patterns
- GCP backends (Firestore)

Install with FlatAgent support:
```bash
pip install flatmachines[flatagents]
```

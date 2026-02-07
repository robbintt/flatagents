# FlatAgents (Python SDK)

Define single-call LLM agents in YAML. Use this package when you want **one structured call** per agent, with optional MCP tools and profile-driven model configs. For orchestration, install `flatmachines` separately.

**For LLM/machine readers:** see [MACHINES.md](./MACHINES.md).

## Install

```bash
pip install flatagents[litellm]
# or
pip install flatagents[aisuite]
```

Optional extras:
- `flatagents[validation]` – JSON schema validation
- `flatagents[metrics]` – OpenTelemetry metrics
- `flatagents[orchestration]` – installs `flatmachines` and re-exports its APIs

## Quick Start

```python
from flatagents import FlatAgent

agent = FlatAgent(config_file="reviewer.yml")
result = await agent.call(code="...")
print(result.output)
```

## Agent Config (YAML)

```yaml
spec: flatagent
spec_version: "0.10.0"

data:
  name: code-reviewer
  model: "smart"     # profile name or inline dict
  system: "You are a careful reviewer."
  user: "Review this code: {{ input.code }}"
  output:
    issues: { type: list, items: { type: str } }
    rating: { type: str, enum: [good, needs_work, critical] }
```

### Templates

`system` and `user` are Jinja2 templates with:
- `input.*` from `FlatAgent.call(**input)`
- `model.*` resolved model config (provider/name/etc)
- `tools` and `tools_prompt` if MCP tools are configured

### Output Schema

If `data.output` is provided, FlatAgents requests JSON mode and parses the response. Invalid JSON falls back to `{"_raw": "..."}`.

## Model Profiles (profiles.yml)

```yaml
spec: flatprofiles
spec_version: "0.10.0"

data:
  model_profiles:
    fast: { provider: cerebras, name: zai-glm-4.6, temperature: 0.6 }
    smart: { provider: anthropic, name: claude-3-opus-20240229 }
  default: fast
  # override: smart
```

Resolution order: default → named profile → inline overrides → override.

**Python behavior:** `FlatAgent` auto-discovers the nearest `profiles.yml` next to the config file. If a parent machine passes `profiles_dict`, it is used only as a fallback (no merging).

## Backends

Built-in backends:
- **LiteLLMBackend** (default, `litellm`)
- **AISuiteBackend** (`aisuite`)

Selection order:
1. `backend` argument to `FlatAgent(...)`
2. `data.model.backend`
3. `FLATAGENTS_BACKEND` env var ("litellm" or "aisuite")
4. Auto-detect installed backend (prefers litellm)

## MCP Tools

Configure MCP in `data.mcp` and pass a `MCPToolProvider` implementation. The SDK does not ship a provider; you supply one (e.g., from `aisuite.mcp`). Tool calls are returned in `AgentResponse.tool_calls`.

## Validation

```python
from flatagents import validate_flatagent_config
warnings = validate_flatagent_config(config)
```

## Logging & Metrics

```python
from flatagents import setup_logging, get_logger
setup_logging(level="INFO")
logger = get_logger(__name__)
```

Env vars: `FLATAGENTS_LOG_LEVEL`, `FLATAGENTS_LOG_FORMAT`, `FLATAGENTS_LOG_DIR`.

Metrics (OpenTelemetry):
```bash
pip install flatagents[metrics]
export FLATAGENTS_METRICS_ENABLED=true
```

## Optional Orchestration

If `flatmachines` is installed (`flatagents[orchestration]`), the FlatMachine APIs are re-exported from `flatagents` for convenience:

```python
from flatagents import FlatMachine
```

## Examples (Repo)

- [helloworld](../../examples/helloworld/python)
- [writer_critic](../../examples/writer_critic/python)
- [human-in-the-loop](../../examples/human-in-the-loop/python)
- [parallelism](../../examples/parallelism/python)

## Specs

Source of truth:
- [`flatagent.d.ts`](./flatagents/assets/flatagent.d.ts)
- [`profiles.d.ts`](./flatagents/assets/profiles.d.ts)

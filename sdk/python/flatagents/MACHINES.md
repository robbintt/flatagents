# FlatAgents Reference

> **Target: <500 tokens.** LLM-optimized. See `flatagent.d.ts`, `profiles.d.ts` for schemas.
>
> **Versioning:** All specs and SDKs use lockstep versioning.

## Concept

**FlatAgent**: Single LLM call. Model + prompts + output schema. No orchestration.

## Model Profiles

```yaml
# profiles.yml — agents reference by name
spec: flatprofiles
spec_version: "1.0.0"
data:
  model_profiles:
    fast: { provider: cerebras, name: zai-glm-4.6, temperature: 0.6 }
    smart: { provider: anthropic, name: claude-3-opus-20240229 }
  default: fast        # Fallback
  # override: smart    # Force all
```

Agent model field: `"fast"` | `{ profile: "fast", temperature: 0.9 }` | `{ provider: x, name: y }`

Resolution order: default → profile → overrides → override

## Agent Config

```yaml
spec: flatagent
spec_version: "1.0.0"
data:
  name: my-agent
  model: "fast"              # Profile name or inline config
  system: |                  # System prompt
    You are a helpful assistant.
  user: |                    # User prompt (Jinja2 template)
    {{ input.query }}
  output:                    # Structured output schema
    answer: { type: str }
    confidence: { type: float }
```

## Output Types

| Type | Description |
|------|-------------|
| `str` | String, optional `enum: [...]` |
| `int` | Integer |
| `float` | Floating point |
| `bool` | Boolean |
| `json` | Raw JSON |
| `list` | Array with `items: { type: ... }` |
| `object` | Object with `properties: { ... }` |

## Python Usage

```python
from flatagents import FlatAgent

agent = FlatAgent(config_file="agent.yml")
result = await agent.call(query="Hello")
print(result.output)  # Structured output dict
```

## LLM Backends

```python
from flatagents import LiteLLMBackend, AISuiteBackend

# LiteLLM (default)
agent = FlatAgent(config_file="agent.yml")

# AISuite
backend = AISuiteBackend(model="openai:gpt-4o")
agent = FlatAgent(config_file="agent.yml", backend=backend)
```

## Validation

```python
from flatagents import validate_flatagent_config

warnings = validate_flatagent_config(config)
```

## Template Variables

In user/system prompts:
- `{{ input.* }}` — Runtime input values
- `{{ context.* }}` — Context dict (when used with orchestration)

## Extractors

| Extractor | Use Case |
|-----------|----------|
| `StructuredExtractor` | JSON schema output (default) |
| `FreeExtractor` | Unstructured text |
| `FreeThinkingExtractor` | Chain-of-thought + answer |
| `ToolsExtractor` | Tool/function calling |
| `RegexExtractor` | Pattern matching |

---

## Orchestration

For multi-agent workflows, state machines, retry logic, and distributed patterns, see the **flatmachines** package:

```bash
pip install flatmachines[flatagents]
```

Refer to `flatmachines/MACHINES.md` for orchestration reference.

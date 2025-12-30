# FlatAgents Python SDK

**Status: Prototype**

Python SDK for [FlatAgents](https://github.com/memgrafter/flatagents)—a format for defining AI agents. Write your agent config once, run it anywhere. See the [spec](https://github.com/memgrafter/flatagents/blob/main/flatagent.d.ts).

### In Progress

- [ ] Unify input/output adapters for agent chaining
- [ ] Simplify output adapters
- [ ] Add workflows (flatworkflows)
- [ ] TypeScript SDK

## Why FlatAgents?

Agent configs are portable. Write your agent YAML once, run it with any SDK that implements the spec. Share agents across teams, languages, and frameworks. Want an SDK for your language? [Build one](https://github.com/memgrafter/flatagents)—the spec is simple.

## Agent Definition

Define agents in YAML or JSON. Both formats are first-class.

**agent.yml**
```yaml
spec: flatagent
spec_version: "0.6.0"

data:
  name: summarizer
  model:
    provider: openai
    name: gpt-4o-mini
  system: You summarize text concisely.
  user: "Summarize this: {{ input.text }}"
  output:
    summary:
      type: str
      description: A concise summary
```

**agent.json**
```json
{
  "spec": "flatagent",
  "spec_version": "0.6.0",
  "data": {
    "name": "summarizer",
    "model": {
      "provider": "openai",
      "name": "gpt-4o-mini"
    },
    "system": "You summarize text concisely.",
    "user": "Summarize this: {{ input.text }}",
    "output": {
      "summary": {
        "type": "str",
        "description": "A concise summary"
      }
    }
  }
}
```

```python
from flatagents import FlatAgent

agent = FlatAgent(config_file="agent.yml")  # or agent.json
result = await agent.execute(input={"text": "Long article here..."})
print(result["summary"])
```

## Quick Start

```bash
pip install flatagents[litellm]
```

**writer.yaml**
```yaml
spec: flatagent
spec_version: "0.6.0"

data:
  name: writer
  model:
    provider: openai
    name: gpt-4o-mini
  system: You write short, punchy marketing copy.
  user: |
    Product: {{ input.product }}
    {% if input.feedback %}Previous attempt: {{ input.tagline }}
    Feedback: {{ input.feedback }}
    Write an improved tagline.{% else %}Write a tagline.{% endif %}
  output:
    tagline:
      type: str
      description: The tagline
```

**critic.yaml**
```yaml
spec: flatagent
spec_version: "0.6.0"

data:
  name: critic
  model:
    provider: openai
    name: gpt-4o-mini
  system: You critique marketing copy. Be constructive but direct.
  user: |
    Product: {{ input.product }}
    Tagline: {{ input.tagline }}
  output:
    feedback:
      type: str
      description: Constructive feedback
    score:
      type: int
      description: Score from 1-10
```

**run.py**
```python
import asyncio
from flatagents import FlatAgent

async def main():
    writer = FlatAgent(config_file="writer.yaml")
    critic = FlatAgent(config_file="critic.yaml")

    product = "a CLI tool for AI agents"
    draft = await writer.execute(input={"product": product})

    for round in range(4):
        review = await critic.execute(input={"product": product, **draft})
        print(f"Round {round + 1}: \"{draft['tagline']}\" - {review['score']}/10")

        if review["score"] >= 8:
            break
        draft = await writer.execute(input={"product": product, **review, **draft})

    print(f"Final: {draft['tagline']}")

asyncio.run(main())
```

```bash
export OPENAI_API_KEY="your-key"
python run.py
```

## Usage

### From Dictionary

```python
from flatagents import FlatAgent

config = {
    "spec": "flatagent",
    "spec_version": "0.6.0",
    "data": {
        "name": "calculator",
        "model": {"provider": "openai", "name": "gpt-4"},
        "system": "You are a calculator.",
        "user": "Calculate: {{ input.expression }}",
        "output": {
            "result": {"type": "float", "description": "The calculated result"}
        }
    }
}

agent = FlatAgent(config_dict=config)
result = await agent.execute(input={"expression": "2 + 2"})
```

### Custom Agent (Subclass FlatAgent)

```python
from flatagents import FlatAgent

class MyAgent(FlatAgent):
    def create_initial_state(self):
        return {"count": 0}

    def generate_step_prompt(self, state):
        return f"Count is {state['count']}. What's next?"

    def update_state(self, state, result):
        return {**state, "count": int(result)}

    def is_solved(self, state):
        return state["count"] >= 10

agent = MyAgent(config_file="config.yaml")
trace = await agent.execute()
```

## LLM Backends

Two backends available:

```python
from flatagents import LiteLLMBackend, AISuiteBackend

# LiteLLM - model format: provider/model
backend = LiteLLMBackend(model="openai/gpt-4o", temperature=0.7)

# AISuite - model format: provider:model
backend = AISuiteBackend(model="openai:gpt-4o", temperature=0.7)
```

### Custom Backend

Implement the `LLMBackend` protocol:

```python
class MyBackend:
    total_cost: float = 0.0
    total_api_calls: int = 0

    async def call(self, messages: list, **kwargs) -> str:
        self.total_api_calls += 1
        return "response"

agent = MyAgent(backend=MyBackend())
```

## Examples

More examples are available in the [`examples/`](https://github.com/memgrafter/flatagents/tree/main/sdk/python/examples) directory:

- **[helloworld](https://github.com/memgrafter/flatagents/tree/main/sdk/python/examples/helloworld)** - Minimal getting started example
- **[writer_critic](https://github.com/memgrafter/flatagents/tree/main/sdk/python/examples/writer_critic)** - Iterative refinement with two agents
- **[mdap](https://github.com/memgrafter/flatagents/tree/main/sdk/python/examples/mdap)** - Multi-step reasoning with calibrated confidence
- **[gepa_self_optimizer](https://github.com/memgrafter/flatagents/tree/main/sdk/python/examples/gepa_self_optimizer)** - Self-optimizing prompt evolution

## Known Issues

### aisuite drops tools from API calls

When using the aisuite backend with tool calling (MCP), tools are silently dropped from the API request unless `max_turns` is set. This is a bug in aisuite's `client.chat.completions.create()` which pops the `tools` kwarg.

**Workaround:** The SDK includes a direct provider call for Cerebras that bypasses aisuite's client. See `_call_aisuite_cerebras_direct()` in `flatagent.py`. Other providers may need similar workarounds until aisuite fixes this upstream.

**Symptoms:** Model outputs tool call JSON in text content instead of using actual tool calling mechanism. Agent completes immediately with "no tool calls" when tools should have been invoked.

## License

MIT License - see [LICENSE](../../LICENSE) for details.

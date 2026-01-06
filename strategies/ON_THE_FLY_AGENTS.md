# On-The-Fly (OTF) Agent Pattern

A strategy for dynamically generating and executing specialized agents at runtime within a FlatMachine HSM.

## Concept

Instead of defining all agents statically in configuration, an **OTF agent** is generated dynamically by a "generator" agent based on the current task. This enables:

- **Task-specific specialization**: Each task gets a tailored agent with appropriate system prompt, temperature, and output schema
- **Meta-programming**: LLMs designing LLM agents for specific purposes
- **Adaptive behavior**: The same machine can handle diverse tasks by generating purpose-built agents

The pattern follows this flow:

1. **Generator Agent** analyzes the task and outputs an agent specification (system prompt, user prompt template, temperature, output schema)
2. **Supervisor Agent** (optional) validates the generated spec for safety and alignment before execution
3. **OTF Executor** instantiates a `FlatAgent` from the generated spec and runs it
4. **Guardrails** prevent runaway behavior (max iterations, timeout, schema validation)

## Implementation

OTF requires no spec changes. It uses:

- **`on_action` hook**: Instantiates and executes `FlatAgent` from context data
- **Individual context fields**: Store agent spec fields separately (not as nested JSON) to avoid template parsing issues
- **Truthy condition checks**: Use `context.human_approved` not `context.human_approved == true` for reliable transitions
- **`nest_asyncio`**: Required for running async `agent.call()` from sync hooks within the event loop

## Guardrails

| Guardrail | Implementation |
|-----------|----------------|
| Max iterations | Track `generation_attempts` in context, transition to `max_attempts_reached` state |
| Pre-execution validation | Supervisor agent analyzes spec BEFORE OTF agent runs |
| Human oversight | Human-in-the-loop review with conditional options based on supervisor decision |
| Output schema | OTF agent uses structured output; validation in hooks |

## Human-in-the-Loop Options

The flow enforces appropriate authority levels:

- **Supervisor approves**: Human can approve or deny
- **Supervisor rejects**: Human can only acknowledge (no override)

This ensures humans cannot bypass supervisor safety checks.

## Reference Implementation

See [sdk/python/examples/dynamic_agent/](../sdk/python/examples/dynamic_agent/) for a complete working example demonstrating:

- Generator creating specialized haiku poets
- Supervisor validating specs before execution
- Human review with conditional options
- OTF agent execution producing actual output

Key files:
- `config/machine.yml` - HSM orchestration with supervision flow
- `config/generator.yml` - Agent spec generator
- `config/supervisor.yml` - Pre-execution validation
- `src/dynamic_agent/hooks.py` - OTF execution and human review logic

## Use Cases

- **Creative writing**: Generate style-specific writing agents (haiku poet, noir detective narrator)
- **Code analysis**: Generate language-specific analyzer agents
- **Research**: Generate domain-specific search/synthesis agents
- **Customer service**: Generate topic-specialized response agents

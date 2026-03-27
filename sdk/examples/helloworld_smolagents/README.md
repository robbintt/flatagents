# Hello World — smolagents variant

Demonstrates the **smolagents subprocess bridge** pattern: a Python
`FlatMachine` orchestrates a character-by-character string builder whose LLM
calls are executed by a [smolagents](https://github.com/huggingface/smolagents)
`CodeAgent` running in a **separate Python subprocess**.

## Architecture

```
Python FlatMachine (orchestrator)
  └─ smolagents-bridge adapter (subprocess)
       └─ Python smolagents_runner.py
            └─ agents/builder.py  (smolagents CodeAgent)
                 └─ LLM provider via LiteLLM (Cerebras)
```

The smolagents library is **not imported** into the orchestrator process.
Instead, the bridge spawns a child Python process (just like the pi-agent
bridge spawns Node.js), keeping the pattern symmetric and generalizable
across **k** FlatMachine SDK languages and **j** agent library interfaces.

## Prerequisites

| Dependency | Purpose |
|------------|---------|
| Python ≥ 3.10 | FlatMachine SDK + smolagents runner |
| `smolagents` | HuggingFace agent framework |
| `litellm` | LLM provider abstraction |
| `CEREBRAS_API_KEY` env var | LLM calls |

## Quick start

```bash
cd python
bash run.sh --local
```

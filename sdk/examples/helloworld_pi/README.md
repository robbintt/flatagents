# Hello World — pi-agent variant

Demonstrates the **pi-agent subprocess bridge** pattern: a Python `FlatMachine`
orchestrates a character-by-character string builder whose LLM calls are executed
by a [pi-mono](https://github.com/badlogic/pi-mono) `Agent` running in a
Node.js subprocess.

## Architecture

```
Python FlatMachine (orchestrator)
  └─ pi-agent bridge adapter (subprocess)
       └─ Node.js pi_agent_runner.mjs
            └─ agents/builder.mjs  (pi-agent-core Agent)
                 └─ LLM provider (Cerebras)
```

This pattern generalises across **k** FlatMachine SDK languages and **j** agent
library interfaces — each agent framework only needs a thin subprocess runner.

## Prerequisites

| Dependency | Purpose |
|------------|---------|
| Python ≥ 3.10 | FlatMachine SDK |
| Node.js ≥ 18 | pi-agent bridge |
| `@mariozechner/pi-agent-core` | pi-mono agent runtime |
| `CEREBRAS_API_KEY` env var | LLM calls |

## Quick start

```bash
cd python
bash run.sh --local
```

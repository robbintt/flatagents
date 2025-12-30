# MCP Exa Demo

A demo that shows how to use FlatAgent with MCP (Model Context Protocol) for web search using the [Exa API](https://exa.ai).

The demo involves an agent that can search the web to answer questions. It showcases:
- Defining MCP servers in YAML configuration
- Implementing the `MCPToolProvider` protocol
- Tool discovery and filtering with allow/deny lists
- Orchestration loop for tool call execution

## Prerequisites

1.  **Python & `uv`**: Ensure you have Python 3.10+ and the `uv` package manager installed.
2.  **Exa API Key**: Get an API key at https://exa.ai
3.  **LLM API Key**: An active API key is required. The demo checks for `OPENAI_API_KEY` or `CEREBRAS_API_KEY` environment variables.

## Quick Start (with `run.sh`)

The fastest way to run the demo is with the provided shell script, which handles all setup for you.

```bash
# Set your API keys
export EXA_MCP_API_KEY="your-exa-key-here"
export CEREBRAS_API_KEY="your-llm-key-here"

# Make the script executable (if you haven't already)
chmod +x run.sh

# Run the demo
./run.sh
```

## Manual Setup

If you prefer to set up the environment manually:

1.  **Navigate into this project directory**:
    ```bash
    cd examples/mcp_exa
    ```
2.  **Install dependencies** using `uv`:
    ```bash
    uv venv
    uv pip install -e .
    ```
3.  **Set your API keys**:
    ```bash
    export EXA_MCP_API_KEY="your-exa-key-here"
    export CEREBRAS_API_KEY="your-llm-key-here"
    ```
4.  **Run the demo**:
    ```bash
    uv run python -m mcp_exa.main
    ```

## How It Works

### Agent Configuration (`config/agent.yml`)

The agent defines MCP servers, tool filters, and a tool prompt template:

```yaml
mcp:
  servers:
    exa:
      server_url: "https://mcp.exa.ai/mcp"
      headers:
        x-api-key: "${EXA_MCP_API_KEY}"

  tool_filter:
    allow:
      - "exa:web_search_exa"

  tool_prompt: |
    You have access to the following search tools:
    {% for tool in tools %}
    ## {{ tool.name }}
    {{ tool.description }}
    {% endfor %}
```

### MCPToolProvider Implementation

The `AISuiteMCPProvider` class implements the `MCPToolProvider` protocol using aisuite's MCPClient.

### Orchestration Loop

The orchestration loop handles tool calls until the agent provides a final answer:

```python
result = await agent.call(tool_provider=provider, question=question)

while result.tool_calls:
    for tc in result.tool_calls:
        tool_result = provider.call_tool(tc.server, tc.tool, tc.arguments)
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})

    result = await agent.call(tool_provider=provider, messages=messages)
```

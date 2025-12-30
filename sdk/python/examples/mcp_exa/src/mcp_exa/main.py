"""
MCP Exa Example - Web search using FlatAgent with MCP tools.

Demonstrates:
1. Defining MCP servers in agent.yml
2. Implementing MCPToolProvider using aisuite
3. Tool discovery and filtering
4. Orchestration loop for tool call execution
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from flatagents import FlatAgent, AgentResponse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AISuiteMCPProvider:
    """
    MCPToolProvider implementation using aisuite's MCPClient.

    This adapter connects to MCP servers defined in the agent config
    and provides tool discovery and execution.
    """

    def __init__(self):
        self._clients: Dict[str, Any] = {}

    def connect(self, server_name: str, config: Dict[str, Any]) -> None:
        """Connect to an MCP server."""
        if server_name in self._clients:
            return  # Already connected

        from aisuite.mcp import MCPClient

        # Expand environment variables in config
        expanded_config = self._expand_env_vars(config)

        # Build MCPClient config
        if 'command' in expanded_config:
            # Stdio transport
            client = MCPClient(
                command=expanded_config['command'],
                args=expanded_config.get('args', []),
                env=expanded_config.get('env'),
                name=server_name
            )
        elif 'server_url' in expanded_config:
            # HTTP transport
            client = MCPClient(
                server_url=expanded_config['server_url'],
                headers=expanded_config.get('headers'),
                timeout=expanded_config.get('timeout', 30.0),
                name=server_name
            )
        else:
            raise ValueError(f"Invalid MCP config for {server_name}: need 'command' or 'server_url'")

        self._clients[server_name] = client
        print(f"  Connected to MCP server: {server_name}")

    def _expand_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Expand ${VAR} patterns in config values."""
        result = {}
        for key, value in config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                result[key] = os.environ.get(env_var, '')
            elif isinstance(value, dict):
                result[key] = self._expand_env_vars(value)
            elif isinstance(value, list):
                result[key] = [
                    os.environ.get(v[2:-1], '') if isinstance(v, str) and v.startswith('${') else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    def get_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Get available tools from an MCP server."""
        if server_name not in self._clients:
            raise RuntimeError(f"Not connected to server: {server_name}")
        return self._clients[server_name].list_tools()

    def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool call."""
        if server_name not in self._clients:
            raise RuntimeError(f"Not connected to server: {server_name}")
        return self._clients[server_name].call_tool(tool_name, arguments)

    def close(self) -> None:
        """Close all MCP connections."""
        for name, client in self._clients.items():
            try:
                client.close()
                print(f"  Closed MCP server: {name}")
            except Exception as e:
                print(f"  Error closing {name}: {e}")
        self._clients.clear()


async def run_with_tools(agent: FlatAgent, provider: AISuiteMCPProvider, question: str) -> str:
    """
    Run the agent with tool call orchestration.

    Implements a loop that:
    1. Calls the agent
    2. If tool calls are requested, executes them
    3. Continues with tool results until no more tool calls
    """
    messages = []
    max_iterations = 5

    for i in range(max_iterations):
        # Call the agent
        result: AgentResponse = await agent.call(
            tool_provider=provider,
            messages=messages if messages else None,
            question=question if i == 0 else ""
        )

        # If no tool calls, we're done
        if not result.tool_calls:
            return result.content or ""

        # Process tool calls
        print(f"  Iteration {i + 1}: {len(result.tool_calls)} tool call(s)")

        # Add assistant message with tool calls to history
        import json
        assistant_msg = {
            "role": "assistant",
            "content": result.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.tool,
                        "arguments": json.dumps(tc.arguments)
                    }
                }
                for tc in result.tool_calls
            ]
        }
        messages.append(assistant_msg)

        # Execute each tool call
        for tc in result.tool_calls:
            print(f"    Calling {tc.server}:{tc.tool}")

            try:
                tool_result = provider.call_tool(tc.server, tc.tool, tc.arguments)
                display = str(tool_result)[:100] + "..." if len(str(tool_result)) > 100 else str(tool_result)
                print(f"    Result: {display}")
            except Exception as e:
                tool_result = f"Error: {e}"
                print(f"    Error: {e}")

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(tool_result)
            })

    return result.content or "Max iterations reached"


async def run():
    """Main function to run the MCP Exa demo."""
    print("--- Starting MCP Exa Demo ---")

    # Check for API keys
    if not os.environ.get("EXA_MCP_API_KEY"):
        print("ERROR: EXA_MCP_API_KEY environment variable not set")
        print("   Get an API key at https://exa.ai")
        return

    if not os.environ.get("CEREBRAS_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        print("WARNING: No LLM API key found (CEREBRAS_API_KEY, OPENAI_API_KEY).")

    # Load agent config
    config_path = Path(__file__).parent.parent.parent / 'config' / 'agent.yml'
    agent = FlatAgent(config_file=str(config_path))

    print(f"Agent: {agent.agent_name}")
    print(f"Model: {agent.model}\n")

    # Create MCP provider
    provider = AISuiteMCPProvider()

    try:
        # Example question
        question = "What are the latest developments in AI agents in December 2024?"
        print(f"Question: {question}\n")

        # Run agent with tool orchestration
        answer = await run_with_tools(agent, provider, question)

        print("\n--- Answer ---")
        print(answer)

        print("\n--- Execution Statistics ---")
        print(f"Total Cost: ${agent.total_cost:.4f}")
        print(f"Total API Calls: {agent.total_api_calls}")

    finally:
        provider.close()


def main():
    """Synchronous entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()

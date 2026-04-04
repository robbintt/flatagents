"""
MCP-Box Template: A reusable AgentDistill-style MCP-Box template using FastMCP.

This package provides:
- MCP Box JSON schema definitions
- FastMCP tool library with reusable tools
- Box Builder Pipeline (abstract, cluster, consolidate)
- Student Runtime for task execution
- Optional SQLite persistence
"""

from mcp_box.schemas.mcp_box import MCPBox, ToolSpec, ValidatorSpec, FallbackPolicy
from mcp_box.runtime.student import StudentRuntime

__version__ = "0.1.0"

__all__ = [
    "MCPBox",
    "ToolSpec", 
    "ValidatorSpec",
    "FallbackPolicy",
    "StudentRuntime",
]

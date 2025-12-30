__version__ = "0.2.0"

from .baseagent import (
    # Base agent (abstract, for multi-step agents)
    FlatAgent as BaseFlatAgent,
    # LLM Backends
    LLMBackend,
    LiteLLMBackend,
    AISuiteBackend,
    # Extractors
    Extractor,
    FreeExtractor,
    FreeThinkingExtractor,
    StructuredExtractor,
    ToolsExtractor,
    RegexExtractor,
    # MCP Types
    MCPToolProvider,
    ToolCall,
    AgentResponse,
)
from .flatagent import FlatAgent

__all__ = [
    "__version__",
    # Main agent class
    "FlatAgent",
    # Base agent for custom multi-step agents
    "BaseFlatAgent",
    # LLM Backends
    "LLMBackend",
    "LiteLLMBackend",
    "AISuiteBackend",
    # Extractors
    "Extractor",
    "FreeExtractor",
    "FreeThinkingExtractor",
    "StructuredExtractor",
    "ToolsExtractor",
    "RegexExtractor",
    # MCP Types
    "MCPToolProvider",
    "ToolCall",
    "AgentResponse",
]

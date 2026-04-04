"""
Tool Registry for managing MCP tools.

Provides centralized registration and lookup of MCP tools.
"""

from typing import Callable, Dict, Any, List, Optional
import importlib
from dataclasses import dataclass, field


@dataclass
class RegisteredTool:
    """A registered tool with its metadata."""
    name: str
    function: Callable
    description: str
    category: str = "general"
    parameters: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Central registry for MCP tools.
    
    Provides tool registration, lookup, and invocation capabilities.
    """
    
    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}
    
    def register(
        self,
        name: str,
        function: Callable,
        description: str = "",
        category: str = "general",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a tool with the registry.
        
        Args:
            name: Unique name for the tool
            function: The callable tool function
            description: Human-readable description
            category: Category for grouping
            parameters: Parameter schema
        """
        self._tools[name] = RegisteredTool(
            name=name,
            function=function,
            description=description or function.__doc__ or "",
            category=category,
            parameters=parameters or {},
        )
    
    def get(self, name: str) -> Optional[RegisteredTool]:
        """Get a registered tool by name."""
        return self._tools.get(name)
    
    def get_all(self) -> List[RegisteredTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_by_category(self, category: str) -> List[RegisteredTool]:
        """Get all tools in a category."""
        return [t for t in self._tools.values() if t.category == category]
    
    def invoke(self, name: str, **kwargs) -> Any:
        """
        Invoke a registered tool by name.
        
        Args:
            name: Tool name
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Tool result
            
        Raises:
            KeyError: If tool not found
        """
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Tool not found: {name}")
        return tool.function(**kwargs)
    
    def load_from_path(self, function_path: str) -> Callable:
        """
        Load a function from a Python path string.
        
        Args:
            function_path: Dot-separated path (e.g., "mcp_box.tools.file_ops.file_search")
            
        Returns:
            The loaded function
        """
        parts = function_path.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid function path: {function_path}")
        
        module_path, func_name = parts
        module = importlib.import_module(module_path)
        return getattr(module, func_name)
    
    def register_from_path(
        self,
        name: str,
        function_path: str,
        description: str = "",
        category: str = "general",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a tool by loading from a Python path.
        
        Args:
            name: Tool name
            function_path: Dot-separated function path
            description: Tool description
            category: Tool category
            parameters: Parameter schema
        """
        func = self.load_from_path(function_path)
        self.register(
            name=name,
            function=func,
            description=description,
            category=category,
            parameters=parameters,
        )


# Global registry instance
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
        # Register default tools
        from mcp_box.tools.file_ops import file_search, apply_patch
        from mcp_box.tools.testing import run_tests
        
        _global_registry.register(
            "file_search",
            file_search,
            "Search for files matching a pattern",
            "file_operations",
        )
        _global_registry.register(
            "apply_patch",
            apply_patch,
            "Apply a patch to a file",
            "file_operations",
        )
        _global_registry.register(
            "run_tests",
            run_tests,
            "Run tests using a testing framework",
            "testing",
        )
    return _global_registry

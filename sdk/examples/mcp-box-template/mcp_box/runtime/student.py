"""
Student Runtime: Execute tasks using MCPBox tools.

The Student Runtime loads an MCPBox configuration, exposes its tools,
and executes tasks using direct tool calls (no training, no retrieval).
"""

from typing import Any, Dict, List, Optional, Callable
import importlib
import asyncio
import time
from dataclasses import dataclass, field

from mcp_box.schemas.mcp_box import MCPBox, ToolSpec, FallbackPolicy


@dataclass
class TaskResult:
    """Result of a task execution."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """A tool call made during execution."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0


class StudentRuntime:
    """
    Runtime for executing tasks using MCPBox tools.
    
    Loads an MCPBox, resolves tool functions, and provides
    execution capabilities for student agents.
    
    Usage:
        runtime = StudentRuntime.from_file("mcp_box.json")
        result = await runtime.execute_task({
            "action": "file_search",
            "pattern": "*.py"
        })
    """
    
    def __init__(
        self,
        mcp_box: MCPBox,
        hooks: Optional[Dict[str, Callable]] = None,
    ):
        self.mcp_box = mcp_box
        self.hooks = hooks or {}
        self._tool_cache: Dict[str, Callable] = {}
        self._load_tools()
    
    @classmethod
    def from_file(
        cls,
        path: str,
        hooks: Optional[Dict[str, Callable]] = None,
    ) -> "StudentRuntime":
        """
        Create a StudentRuntime from an MCPBox JSON file.
        
        Args:
            path: Path to MCPBox JSON file
            hooks: Optional hook functions
            
        Returns:
            Configured StudentRuntime instance
        """
        mcp_box = MCPBox.load(path)
        return cls(mcp_box, hooks)
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        hooks: Optional[Dict[str, Callable]] = None,
    ) -> "StudentRuntime":
        """
        Create a StudentRuntime from a dictionary.
        
        Args:
            data: MCPBox configuration dict
            hooks: Optional hook functions
            
        Returns:
            Configured StudentRuntime instance
        """
        mcp_box = MCPBox.from_dict(data)
        return cls(mcp_box, hooks)
    
    def _load_tools(self) -> None:
        """Load and cache tool functions."""
        for tool in self.mcp_box.tools:
            try:
                func = self._resolve_function(tool.function)
                self._tool_cache[tool.name] = func
            except (ImportError, AttributeError) as e:
                # Log warning but continue - tool will fail at runtime
                print(f"Warning: Could not load tool {tool.name}: {e}")
    
    def _resolve_function(self, function_path: str) -> Callable:
        """
        Resolve a function path to an actual function.
        
        Args:
            function_path: Dot-separated function path
            
        Returns:
            The resolved function
        """
        parts = function_path.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid function path: {function_path}")
        
        module_path, func_name = parts
        module = importlib.import_module(module_path)
        return getattr(module, func_name)
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self._tool_cache.keys())
    
    def get_tool_spec(self, name: str) -> Optional[ToolSpec]:
        """Get the specification for a tool."""
        return self.mcp_box.get_tool(name)
    
    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ToolCall:
        """
        Call a single tool.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            ToolCall with result or error
        """
        arguments = arguments or {}
        tool_call = ToolCall(tool_name=name, arguments=arguments)
        
        start_time = time.time()
        
        try:
            # Get tool function
            func = self._tool_cache.get(name)
            if not func:
                raise KeyError(f"Tool not found: {name}")
            
            # Call pre-execution hook
            if "before_tool_call" in self.hooks:
                await self._call_hook("before_tool_call", name, arguments)
            
            # Execute tool (handle both sync and async)
            if asyncio.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)
            
            tool_call.result = result
            
            # Call post-execution hook
            if "after_tool_call" in self.hooks:
                await self._call_hook("after_tool_call", name, result)
                
        except Exception as e:
            tool_call.error = str(e)
            
            # Try fallback if configured
            tool_spec = self.mcp_box.get_tool(name)
            if tool_spec and tool_spec.fallback_policy:
                await self._handle_fallback(tool_call, tool_spec.fallback_policy)
        
        tool_call.execution_time = time.time() - start_time
        return tool_call
    
    async def _call_hook(self, hook_name: str, *args, **kwargs) -> Any:
        """Call a hook function if it exists."""
        hook = self.hooks.get(hook_name)
        if hook:
            if asyncio.iscoroutinefunction(hook):
                return await hook(*args, **kwargs)
            return hook(*args, **kwargs)
    
    async def _handle_fallback(
        self,
        tool_call: ToolCall,
        policy: FallbackPolicy,
    ) -> None:
        """Handle fallback after tool failure."""
        # Retry logic
        for i in range(policy.retry_count):
            await asyncio.sleep(policy.retry_delay_seconds)
            
            try:
                func = self._tool_cache.get(tool_call.tool_name)
                if func:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**tool_call.arguments)
                    else:
                        result = func(**tool_call.arguments)
                    tool_call.result = result
                    tool_call.error = None
                    return
            except Exception:
                continue
        
        # Try fallback tool
        if policy.fallback_tool and policy.on_failure == "fallback":
            fallback_call = await self.call_tool(
                policy.fallback_tool,
                tool_call.arguments,
            )
            if not fallback_call.error:
                tool_call.result = fallback_call.result
                tool_call.error = None
    
    async def execute_task(
        self,
        task: Dict[str, Any],
    ) -> TaskResult:
        """
        Execute a task using the available tools.
        
        A task should specify:
        - action: Tool name to call
        - **kwargs: Arguments for the tool
        
        Args:
            task: Task specification
            
        Returns:
            TaskResult with execution details
        """
        start_time = time.time()
        tool_calls = []
        
        try:
            # Extract action and arguments
            action = task.get("action")
            if not action:
                return TaskResult(
                    success=False,
                    error="Task must specify an 'action' field",
                )
            
            # Remove action from arguments
            arguments = {k: v for k, v in task.items() if k != "action"}
            
            # Execute the tool
            tool_call = await self.call_tool(action, arguments)
            tool_calls.append({
                "tool": tool_call.tool_name,
                "arguments": tool_call.arguments,
                "result": tool_call.result,
                "error": tool_call.error,
                "time": tool_call.execution_time,
            })
            
            if tool_call.error:
                return TaskResult(
                    success=False,
                    error=tool_call.error,
                    tool_calls=tool_calls,
                    execution_time=time.time() - start_time,
                )
            
            return TaskResult(
                success=True,
                result=tool_call.result,
                tool_calls=tool_calls,
                execution_time=time.time() - start_time,
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                tool_calls=tool_calls,
                execution_time=time.time() - start_time,
            )
    
    async def execute_sequence(
        self,
        tasks: List[Dict[str, Any]],
        stop_on_error: bool = True,
    ) -> List[TaskResult]:
        """
        Execute a sequence of tasks.
        
        Args:
            tasks: List of task specifications
            stop_on_error: Whether to stop on first error
            
        Returns:
            List of TaskResults
        """
        results = []
        
        for task in tasks:
            result = await self.execute_task(task)
            results.append(result)
            
            if not result.success and stop_on_error:
                break
        
        return results

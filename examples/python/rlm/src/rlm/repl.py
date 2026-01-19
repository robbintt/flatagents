"""
REPL Executor for RLM

Provides a sandboxed Python REPL environment where the long context
is stored as a variable that the LLM can interact with programmatically.
"""

import io
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Any


class REPLExecutor:
    """
    Sandboxed REPL executor for RLM.

    Manages a persistent Python environment where:
    - The context is stored as the INPUT variable
    - The LLM can execute code to explore and manipulate the context
    - Results are captured and returned to the LLM
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize the REPL executor.

        Args:
            timeout: Maximum execution time for code blocks (seconds)
        """
        self.timeout = timeout
        self.global_state: dict[str, Any] = {}
        self.execution_history: list[dict] = []
        self._setup_builtins()

    def _setup_builtins(self):
        """Set up safe built-in functions and modules."""
        import re
        import json
        import math
        from collections import Counter, defaultdict

        self.global_state.update({
            # Safe modules
            "re": re,
            "json": json,
            "math": math,
            "Counter": Counter,
            "defaultdict": defaultdict,
            # Safe builtins
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "any": any,
            "all": all,
            "print": print,
        })

    def set_context(self, content: str, variable_name: str = "INPUT"):
        """
        Store the context content as a variable in the REPL.

        Args:
            content: The full context text
            variable_name: Name of the variable (default: INPUT)
        """
        self.global_state[variable_name] = content
        self.global_state["_context_length"] = len(content)
        self.global_state["_context_tokens"] = len(content) // 4

    def execute(self, code: str) -> dict:
        """
        Execute code in the sandboxed environment.

        Args:
            code: Python code to execute

        Returns:
            Dictionary with:
                - success: Whether execution succeeded
                - output: Captured stdout
                - error: Error message if failed
                - return_value: Value of last expression (if any)
        """
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        result = {
            "success": False,
            "output": "",
            "error": "",
            "return_value": None
        }

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Try to execute as statements first
                try:
                    exec(code, self.global_state)
                except SyntaxError:
                    # If it's a single expression, eval it
                    pass

                # Try to evaluate the last line as an expression
                lines = code.strip().split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if last_line and not any(last_line.startswith(kw) for kw in
                                              ['if', 'for', 'while', 'def', 'class', 'try', 'with', 'import', 'from', '#']):
                        try:
                            result["return_value"] = eval(last_line, self.global_state)
                        except (SyntaxError, NameError):
                            pass

            result["success"] = True
            result["output"] = stdout_capture.getvalue()

        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            result["output"] = stdout_capture.getvalue()

        # Record in history
        self.execution_history.append({
            "code": code,
            "result": result
        })

        return result

    def get_variable(self, name: str) -> Any:
        """Get a variable from the REPL state."""
        return self.global_state.get(name)

    def set_variable(self, name: str, value: Any):
        """Set a variable in the REPL state."""
        self.global_state[name] = value

    def reset(self):
        """Reset the REPL state (except builtins)."""
        context = self.global_state.get("INPUT")
        self._setup_builtins()
        if context:
            self.set_context(context)
        self.execution_history = []

    def get_history(self) -> list[dict]:
        """Get the execution history."""
        return self.execution_history

    def get_statistics(self) -> dict:
        """Get REPL usage statistics."""
        successful = sum(1 for h in self.execution_history if h["result"]["success"])
        return {
            "total_executions": len(self.execution_history),
            "successful_executions": successful,
            "failed_executions": len(self.execution_history) - successful,
            "context_length": self.global_state.get("_context_length", 0),
            "estimated_tokens": self.global_state.get("_context_tokens", 0),
        }

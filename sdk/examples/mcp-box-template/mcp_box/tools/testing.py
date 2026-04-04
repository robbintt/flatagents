"""
Testing tools for MCP.

These tools provide test execution capabilities.
"""

import subprocess
import os
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    class FastMCP:
        def tool(self):
            def decorator(func):
                return func
            return decorator


# Create MCP server instance for testing tools
mcp = FastMCP("testing") if MCP_AVAILABLE else FastMCP()


def run_tests(
    test_path: str = ".",
    framework: str = "auto",
    pattern: Optional[str] = None,
    verbose: bool = False,
    timeout: int = 300,
    extra_args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run tests in a directory using the specified testing framework.
    
    Args:
        test_path: Path to test file or directory (default: current directory)
        framework: Testing framework to use ("pytest", "unittest", "auto")
        pattern: Optional pattern to filter tests
        verbose: Enable verbose output (default: False)
        timeout: Timeout in seconds (default: 300)
        extra_args: Additional arguments to pass to the test runner
    
    Returns:
        Result dict with test output and status
    """
    path = Path(test_path).resolve()
    
    if not path.exists():
        return {
            "success": False,
            "error": f"Test path not found: {test_path}",
            "framework": framework,
        }
    
    # Auto-detect framework
    if framework == "auto":
        framework = _detect_framework(path)
    
    # Build command
    cmd = _build_test_command(
        framework=framework,
        path=path,
        pattern=pattern,
        verbose=verbose,
        extra_args=extra_args or [],
    )
    
    if not cmd:
        return {
            "success": False,
            "error": f"Unknown testing framework: {framework}",
            "framework": framework,
        }
    
    # Run tests
    try:
        result = subprocess.run(
            cmd,
            cwd=str(path.parent if path.is_file() else path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        return {
            "success": result.returncode == 0,
            "framework": framework,
            "command": " ".join(cmd),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Tests timed out after {timeout} seconds",
            "framework": framework,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "framework": framework,
        }


def _detect_framework(path: Path) -> str:
    """Auto-detect the testing framework based on project files."""
    root = path if path.is_dir() else path.parent
    
    # Check for pytest
    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        return "pytest"
    
    # Check for unittest pattern
    if path.is_file() and path.name.startswith("test_"):
        return "pytest"  # Default to pytest for test files
    
    # Check for test directory
    if path.is_dir():
        for test_file in path.glob("test_*.py"):
            return "pytest"
        for test_file in path.glob("*_test.py"):
            return "pytest"
    
    return "pytest"  # Default to pytest


def _build_test_command(
    framework: str,
    path: Path,
    pattern: Optional[str],
    verbose: bool,
    extra_args: List[str],
) -> Optional[List[str]]:
    """Build the test command based on framework."""
    if framework == "pytest":
        cmd = [sys.executable, "-m", "pytest"]
        if verbose:
            cmd.append("-v")
        if pattern:
            cmd.extend(["-k", pattern])
        cmd.append(str(path))
        cmd.extend(extra_args)
        return cmd
    
    elif framework == "unittest":
        cmd = [sys.executable, "-m", "unittest"]
        if verbose:
            cmd.append("-v")
        if path.is_file():
            # Convert path to module notation
            module = str(path.stem)
            cmd.append(module)
        else:
            cmd.append("discover")
            cmd.extend(["-s", str(path)])
            if pattern:
                cmd.extend(["-p", pattern])
        cmd.extend(extra_args)
        return cmd
    
    return None


if MCP_AVAILABLE:
    run_tests = mcp.tool()(run_tests)

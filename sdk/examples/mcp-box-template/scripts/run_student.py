#!/usr/bin/env python3
"""
Run Student Script: Execute tasks using an MCPBox.

Usage:
    python run_student.py [--box BOX_PATH] [--task TASK_JSON]

Examples:
    # Run with default demo task
    python run_student.py
    
    # Run with custom box
    python run_student.py --box my_box.json
    
    # Run with specific task
    python run_student.py --task '{"action": "file_search", "pattern": "*.py"}'
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_box.runtime.student import StudentRuntime, TaskResult
from mcp_box.schemas.mcp_box import MCPBox


def print_result(result: TaskResult, verbose: bool = False):
    """Pretty print a task result."""
    status = "✅ SUCCESS" if result.success else "❌ FAILED"
    print(f"\n{status}")
    print(f"   Execution time: {result.execution_time:.3f}s")
    
    if result.error:
        print(f"   Error: {result.error}")
    
    if result.result:
        print(f"   Result:")
        if isinstance(result.result, (list, dict)):
            formatted = json.dumps(result.result, indent=6)
            # Truncate long output with ellipsis, preserving structure
            max_len = 500
            if len(formatted) > max_len:
                formatted = formatted[:max_len] + "\n      ... (truncated)"
            print(f"      {formatted}")
        else:
            print(f"      {result.result}")
    
    if verbose and result.tool_calls:
        print(f"\n   Tool calls:")
        for call in result.tool_calls:
            print(f"      - {call['tool']}: {call.get('time', 0):.3f}s")


async def run_demo():
    """Run the demo workflow."""
    print("🎯 MCP-Box Student Runtime Demo")
    print("=" * 50)
    
    # Create a simple in-memory MCPBox for demo
    from mcp_box.tools.file_ops import file_search
    from mcp_box.tools.testing import run_tests
    
    mcp_box = MCPBox(
        name="demo-box",
        version="0.1.0",
        description="Demo MCP Box",
        tools=[],
    )
    
    # Create runtime with tools loaded directly
    runtime = StudentRuntime(mcp_box)
    runtime._tool_cache["file_search"] = file_search
    runtime._tool_cache["run_tests"] = run_tests
    
    print("\n📦 Available tools:")
    for tool_name in runtime.get_available_tools():
        print(f"   - {tool_name}")
    
    # Demo task 1: File search
    print("\n" + "=" * 50)
    print("📋 Task 1: Search for Python files")
    
    result = await runtime.execute_task({
        "action": "file_search",
        "pattern": "*.py",
        "directory": str(Path(__file__).parent.parent),
        "max_results": 10,
    })
    print_result(result)
    
    # Demo task 2: Search with content pattern
    print("\n" + "=" * 50)
    print("📋 Task 2: Search for files containing 'MCPBox'")
    
    result = await runtime.execute_task({
        "action": "file_search",
        "pattern": "*.py",
        "directory": str(Path(__file__).parent.parent),
        "content_pattern": "MCPBox",
        "max_results": 5,
    })
    print_result(result)
    
    print("\n" + "=" * 50)
    print("✨ Demo complete!")


async def run_from_box(box_path: str, task_json: str, verbose: bool):
    """Run a task using an MCPBox file."""
    print(f"📦 Loading MCPBox from: {box_path}")
    
    runtime = StudentRuntime.from_file(box_path)
    
    print(f"   Available tools: {', '.join(runtime.get_available_tools())}")
    
    # Parse task
    task = json.loads(task_json)
    print(f"\n📋 Executing task: {task.get('action', 'unknown')}")
    
    result = await runtime.execute_task(task)
    print_result(result, verbose)
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Execute tasks using an MCPBox"
    )
    parser.add_argument(
        "--box",
        type=str,
        help="Path to MCPBox JSON file",
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Task JSON (e.g., '{\"action\": \"file_search\", \"pattern\": \"*.py\"}')",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo workflow",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    if args.demo or (not args.box and not args.task):
        # Run demo
        asyncio.run(run_demo())
    elif args.box and args.task:
        # Run specific task
        asyncio.run(run_from_box(args.box, args.task, args.verbose))
    else:
        parser.print_help()
        print("\n⚠️  Either use --demo or provide both --box and --task")
        sys.exit(1)


if __name__ == "__main__":
    main()

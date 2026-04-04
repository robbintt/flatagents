"""
Minimal Working Example: Demo task with 3 MCP tools.

This example demonstrates:
1. Building an MCPBox with tools
2. Running a student agent to execute tasks
3. Evaluating results

Usage:
    cd examples
    python demo.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_box.schemas.mcp_box import MCPBox, ToolSpec
from mcp_box.pipelines.builder import BoxBuilder
from mcp_box.runtime.student import StudentRuntime
from mcp_box.tools.file_ops import file_search, apply_patch
from mcp_box.tools.testing import run_tests


async def main():
    print("=" * 60)
    print("🎯 MCP-Box Template: Minimal Working Example")
    print("=" * 60)
    
    # =========================================================================
    # Step 1: Build an MCPBox
    # =========================================================================
    print("\n📦 Step 1: Building MCPBox...")
    
    builder = BoxBuilder(
        name="demo-mcp-box",
        version="0.1.0",
        description="Demo MCP Box with file and testing tools",
    )
    
    # Add tools using the builder
    builder.add_tool(
        name="file_search",
        description="Search for files matching a glob pattern",
        function="mcp_box.tools.file_ops.file_search",
        parameters={
            "pattern": {"type": "string", "description": "Glob pattern"},
            "directory": {"type": "string", "default": "."},
            "recursive": {"type": "boolean", "default": True},
        },
        category="file_operations",
    )
    
    builder.add_tool(
        name="apply_patch",
        description="Apply a content patch to a file",
        function="mcp_box.tools.file_ops.apply_patch",
        parameters={
            "file_path": {"type": "string"},
            "old_content": {"type": "string"},
            "new_content": {"type": "string"},
        },
        category="file_operations",
    )
    
    builder.add_tool(
        name="run_tests",
        description="Run tests in a directory",
        function="mcp_box.tools.testing.run_tests",
        parameters={
            "test_path": {"type": "string", "default": "."},
            "framework": {"type": "string", "default": "auto"},
        },
        category="testing",
    )
    
    # Build the MCPBox
    mcp_box = builder.build()
    
    print(f"   ✅ Created MCPBox: {mcp_box.name} v{mcp_box.version}")
    print(f"   ✅ Tools: {len(mcp_box.tools)}")
    for tool in mcp_box.tools:
        print(f"      - {tool.name}: {tool.description}")
    
    # Save to file
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "demo_mcp_box.json"
    mcp_box.save(str(output_path))
    print(f"   ✅ Saved to: {output_path}")
    
    # =========================================================================
    # Step 2: Create Student Runtime
    # =========================================================================
    print("\n🤖 Step 2: Creating Student Runtime...")
    
    runtime = StudentRuntime(mcp_box)
    
    # Manually register tool functions (in production, these would be loaded dynamically)
    runtime._tool_cache["file_search"] = file_search
    runtime._tool_cache["apply_patch"] = apply_patch
    runtime._tool_cache["run_tests"] = run_tests
    
    print(f"   ✅ Runtime initialized with {len(runtime.get_available_tools())} tools")
    
    # =========================================================================
    # Step 3: Execute Demo Tasks
    # =========================================================================
    print("\n🎮 Step 3: Executing Demo Tasks...")
    
    # Task 1: Search for Python files in mcp_box directory
    print("\n   📋 Task 1: Search for Python files")
    result = await runtime.execute_task({
        "action": "file_search",
        "pattern": "*.py",
        "directory": str(Path(__file__).parent.parent / "mcp_box"),
        "max_results": 5,
    })
    
    if result.success:
        print(f"      ✅ Found {len(result.result)} files:")
        for f in result.result[:3]:
            print(f"         - {f['path']}")
        if len(result.result) > 3:
            print(f"         ... and {len(result.result) - 3} more")
    else:
        print(f"      ❌ Error: {result.error}")
    
    # Task 2: Search for files containing "MCPBox"
    print("\n   📋 Task 2: Search for files containing 'MCPBox'")
    result = await runtime.execute_task({
        "action": "file_search",
        "pattern": "*.py",
        "directory": str(Path(__file__).parent.parent / "mcp_box"),
        "content_pattern": "class MCPBox",
        "max_results": 5,
    })
    
    if result.success:
        print(f"      ✅ Found {len(result.result)} files with 'class MCPBox':")
        for f in result.result:
            print(f"         - {f['path']}")
    else:
        print(f"      ❌ Error: {result.error}")
    
    # Task 3: Execute a sequence of tasks
    print("\n   📋 Task 3: Execute task sequence")
    results = await runtime.execute_sequence([
        {"action": "file_search", "pattern": "*.json", "directory": str(output_dir)},
        {"action": "file_search", "pattern": "__init__.py", "directory": str(Path(__file__).parent.parent / "mcp_box")},
    ])
    
    print(f"      ✅ Completed {len(results)} tasks:")
    for i, r in enumerate(results):
        status = "✅" if r.success else "❌"
        count = len(r.result) if r.result else 0
        print(f"         Task {i+1}: {status} ({count} results, {r.execution_time:.3f}s)")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("✨ Demo Complete!")
    print("=" * 60)
    print("""
Next steps:
1. Run scripts/build_box.py to build your own MCPBox
2. Run scripts/run_student.py to execute tasks
3. Run scripts/eval_box.py to evaluate performance

See README.md for more details.
""")


if __name__ == "__main__":
    asyncio.run(main())

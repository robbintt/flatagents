#!/usr/bin/env python3
"""
Build Box Script: Build an MCPBox from tool definitions.

Usage:
    python build_box.py [--config CONFIG] [--output OUTPUT] [--name NAME] [--version VERSION]

Examples:
    # Build from default example tools
    python build_box.py --output output/mcp_box.json
    
    # Build from a config file
    python build_box.py --config box_config.json --output my_box.json
    
    # Build from a directory of Python tools
    python build_box.py --tools-dir my_tools/ --output my_box.json
"""

import argparse
import sys
import json
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_box.pipelines.builder import BoxBuilder
from mcp_box.schemas.mcp_box import MCPBox


def build_default_box(name: str, version: str, description: str) -> MCPBox:
    """Build the default example MCPBox with built-in tools."""
    builder = BoxBuilder(
        name=name,
        version=version,
        description=description,
    )
    
    # Add built-in tools directly
    builder.add_tool(
        name="file_search",
        description="Search for files matching a pattern",
        function="mcp_box.tools.file_ops.file_search",
        parameters={
            "pattern": {"type": "string", "description": "Glob pattern to match"},
            "directory": {"type": "string", "default": ".", "description": "Directory to search"},
            "recursive": {"type": "boolean", "default": True, "description": "Search recursively"},
            "content_pattern": {"type": "string", "description": "Regex to match in file contents"},
            "max_results": {"type": "integer", "default": 100, "description": "Max results"},
        },
        category="file_operations",
    )
    
    builder.add_tool(
        name="apply_patch",
        description="Apply a patch to a file by replacing content",
        function="mcp_box.tools.file_ops.apply_patch",
        parameters={
            "file_path": {"type": "string", "description": "Path to file"},
            "old_content": {"type": "string", "description": "Content to replace"},
            "new_content": {"type": "string", "description": "Replacement content"},
            "create_backup": {"type": "boolean", "default": True, "description": "Create backup"},
        },
        category="file_operations",
    )
    
    builder.add_tool(
        name="run_tests",
        description="Run tests using a testing framework",
        function="mcp_box.tools.testing.run_tests",
        parameters={
            "test_path": {"type": "string", "default": ".", "description": "Path to tests"},
            "framework": {"type": "string", "default": "auto", "description": "Test framework"},
            "pattern": {"type": "string", "description": "Test pattern filter"},
            "verbose": {"type": "boolean", "default": False, "description": "Verbose output"},
            "timeout": {"type": "integer", "default": 300, "description": "Timeout in seconds"},
        },
        category="testing",
    )
    
    return builder.build()


def main():
    parser = argparse.ArgumentParser(
        description="Build an MCPBox from tool definitions"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to JSON config file",
    )
    parser.add_argument(
        "--tools-dir",
        type=str,
        help="Directory containing Python tool files",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="output/mcp_box.json",
        help="Output path for MCPBox JSON (default: output/mcp_box.json)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="demo-mcp-box",
        help="Name for the MCPBox (default: demo-mcp-box)",
    )
    parser.add_argument(
        "--version",
        type=str,
        default="0.1.0",
        help="Version for the MCPBox (default: 0.1.0)",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="Demo MCP Box with file operations and testing tools",
        help="Description for the MCPBox",
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if args.config:
        # Build from config file
        print(f"Building MCPBox from config: {args.config}")
        builder = BoxBuilder.from_config(args.config)
        mcp_box = builder.build()
    elif args.tools_dir:
        # Build from directory
        print(f"Building MCPBox from directory: {args.tools_dir}")
        builder = BoxBuilder(
            name=args.name,
            version=args.version,
            description=args.description,
        )
        mcp_box = builder.build_from_directory(args.tools_dir)
    else:
        # Build default example box
        print("Building default example MCPBox...")
        mcp_box = build_default_box(args.name, args.version, args.description)
    
    # Save to output
    mcp_box.save(str(output_path))
    
    print(f"\n✅ MCPBox built successfully!")
    print(f"   Name: {mcp_box.name}")
    print(f"   Version: {mcp_box.version}")
    print(f"   Tools: {len(mcp_box.tools)}")
    print(f"   Output: {output_path}")
    
    # Print tool summary
    print("\n📦 Tools included:")
    for tool in mcp_box.tools:
        print(f"   - {tool.name}: {tool.description}")


if __name__ == "__main__":
    main()

# MCP-Box Template

A reusable **AgentDistill-style MCP-Box template** using **Python MCP library (FastMCP)** with optional **SQLite** persistence.

## Overview

This template provides:
- ✅ **MCP Box Schema**: JSON schema for `MCPBox`, `ToolSpec`, `ValidatorSpec`, `FallbackPolicy`
- ✅ **FastMCP Tool Library**: Reusable MCP tools (`file_search`, `apply_patch`, `run_tests`)
- ✅ **Box Builder Pipeline**: Abstract → Cluster → Consolidate pipeline
- ✅ **Student Runtime**: Load MCPBox → expose tools → execute tasks
- ✅ **Optional SQLite Persistence**: Task logs, success rate, box metadata
- ✅ **CLI Scripts**: Build, run, and evaluate MCPBoxes

## Directory Structure

```
mcp-box-template/
├─ mcp_box/
│  ├─ __init__.py
│  ├─ tools/           # Reusable MCP tools (FastMCP)
│  │  ├─ file_ops.py   # file_search, apply_patch
│  │  ├─ testing.py    # run_tests
│  │  └─ registry.py   # Tool registry
│  ├─ pipelines/       # Build pipeline
│  │  ├─ abstract.py   # Normalize raw scripts
│  │  ├─ cluster.py    # Group by function
│  │  ├─ consolidate.py # Merge into MCPBox
│  │  └─ builder.py    # High-level builder
│  ├─ runtime/         # Student agent runner
│  │  └─ student.py    # Task execution runtime
│  ├─ schemas/         # MCP Box JSON schema
│  │  ├─ mcp_box.py    # Dataclass definitions
│  │  └─ json_schema.py # JSON Schema
│  └─ sqlite/          # Optional persistence
│     └─ persistence.py # SQLite database
├─ data/               # Optional datasets, cached tasks
├─ sqlite/             # Optional persistence files
├─ scripts/            # CLI scripts
│  ├─ build_box.py     # Build MCPBox
│  ├─ run_student.py   # Execute tasks
│  └─ eval_box.py      # Evaluate performance
├─ examples/           # Working examples
│  ├─ demo.py          # Minimal working example
│  ├─ box_config.json  # Example config
│  └─ eval_tasks.json  # Evaluation tasks
├─ pyproject.toml
└─ README.md
```

## Quick Start

### 1. Run the Demo

```bash
cd sdk/examples/mcp-box-template
python examples/demo.py
```

### 2. Build an MCPBox

```bash
# Build default example box
python scripts/build_box.py --output output/mcp_box.json

# Build from config file
python scripts/build_box.py --config examples/box_config.json --output my_box.json

# Build from directory of Python tools
python scripts/build_box.py --tools-dir my_tools/ --output my_box.json
```

### 3. Run Tasks

```bash
# Run demo workflow
python scripts/run_student.py --demo

# Run specific task with MCPBox
python scripts/run_student.py --box output/mcp_box.json \
    --task '{"action": "file_search", "pattern": "*.py"}'
```

### 4. Evaluate Performance

```bash
# Run evaluation with default tasks
python scripts/eval_box.py --box output/mcp_box.json

# Run with custom tasks and persistence
python scripts/eval_box.py \
    --box output/mcp_box.json \
    --tasks examples/eval_tasks.json \
    --db sqlite/eval.db \
    --output results.json
```

## Core Concepts

### MCPBox

An MCPBox is a containerized collection of MCP tools with metadata:

```python
from mcp_box.schemas.mcp_box import MCPBox, ToolSpec

mcp_box = MCPBox(
    name="my-box",
    version="1.0.0",
    description="My custom MCP tools",
    tools=[
        ToolSpec(
            name="my_tool",
            description="Does something useful",
            function="my_module.my_function",
            parameters={"arg": {"type": "string"}},
            category="general",
        ),
    ],
)

# Save to JSON
mcp_box.save("my_box.json")

# Load from JSON
loaded = MCPBox.load("my_box.json")
```

### Box Builder

Use the builder for programmatic MCPBox creation:

```python
from mcp_box.pipelines.builder import BoxBuilder

builder = BoxBuilder(name="my-box", version="1.0.0")

# Add tools directly
builder.add_tool(
    name="search",
    description="Search files",
    function="my_tools.search",
    category="search",
)

# Build the MCPBox
mcp_box = builder.build()
```

### Student Runtime

Execute tasks using an MCPBox:

```python
import asyncio
from mcp_box.runtime.student import StudentRuntime

async def main():
    runtime = StudentRuntime.from_file("my_box.json")
    
    result = await runtime.execute_task({
        "action": "file_search",
        "pattern": "*.py",
    })
    
    if result.success:
        print(f"Found {len(result.result)} files")
    else:
        print(f"Error: {result.error}")

asyncio.run(main())
```

### SQLite Persistence

Track execution history and metrics:

```python
from mcp_box.sqlite.persistence import MCPBoxDatabase, Run, Metric

db = MCPBoxDatabase("mcp_box.db")

# Save MCPBox
db.save_box(mcp_box)

# Log a run
db.log_run(Run(
    box_name="my-box",
    task_id="task-1",
    task_data={"action": "search"},
    success=True,
    execution_time=0.5,
))

# Get success rate
rate = db.get_success_rate("my-box")
print(f"Success rate: {rate:.1%}")

db.close()
```

## Built-in Tools

### file_search

Search for files matching a pattern:

```python
from mcp_box.tools.file_ops import file_search

results = file_search(
    pattern="*.py",
    directory=".",
    recursive=True,
    content_pattern="def main",
    max_results=100,
)
```

### apply_patch

Apply a patch to a file:

```python
from mcp_box.tools.file_ops import apply_patch

result = apply_patch(
    file_path="my_file.py",
    old_content="old_value",
    new_content="new_value",
    create_backup=True,
)
```

### run_tests

Run tests using pytest or unittest:

```python
from mcp_box.tools.testing import run_tests

result = run_tests(
    test_path="tests/",
    framework="pytest",
    pattern="test_*",
    verbose=True,
    timeout=300,
)
```

## FastMCP Integration

When the MCP library is installed, tools are automatically decorated as FastMCP tools:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
def my_custom_tool(arg: str) -> str:
    """My custom tool description."""
    return f"Result: {arg}"
```

## SQLite Schema

The persistence layer uses three tables:

- **mcp_boxes**: Box metadata storage
- **runs**: Task execution logs  
- **metrics**: Success rate and other metrics

```sql
CREATE TABLE mcp_boxes (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    version TEXT,
    config TEXT,
    tool_count INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    box_name TEXT,
    task_id TEXT,
    success BOOLEAN,
    execution_time REAL,
    created_at TIMESTAMP
);

CREATE TABLE metrics (
    id INTEGER PRIMARY KEY,
    box_name TEXT,
    metric_name TEXT,
    metric_value REAL,
    created_at TIMESTAMP
);
```

## Configuration

### Box Config File

Create a JSON config to define your MCPBox:

```json
{
    "name": "my-mcp-box",
    "version": "1.0.0",
    "description": "My custom tools",
    "tools": [
        {
            "name": "my_tool",
            "description": "Does something",
            "function": "my_module.my_function",
            "category": "general"
        }
    ]
}
```

### Evaluation Tasks

Define evaluation tasks in JSON:

```json
[
    {
        "id": "test_search",
        "description": "Test file search",
        "task": {
            "action": "file_search",
            "pattern": "*.py"
        },
        "expected_success": true
    }
]
```

## Development

### Install Dependencies

```bash
pip install -e .

# With MCP support
pip install -e ".[mcp]"
```

### Run Tests

```bash
python -m pytest tests/
```

## License

Apache 2.0

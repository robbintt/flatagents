#!/usr/bin/env python3
"""
Eval Script: Evaluate MCPBox performance with metrics.

Usage:
    python eval_box.py [--box BOX_PATH] [--tasks TASKS_FILE] [--db DB_PATH]

Examples:
    # Run evaluation with default tasks
    python eval_box.py --box output/mcp_box.json
    
    # Run with custom tasks file
    python eval_box.py --box my_box.json --tasks eval_tasks.json
    
    # Use persistent database
    python eval_box.py --box my_box.json --db sqlite/eval.db
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_box.runtime.student import StudentRuntime
from mcp_box.schemas.mcp_box import MCPBox
from mcp_box.sqlite.persistence import MCPBoxDatabase, Run, Metric


# Default evaluation tasks
DEFAULT_TASKS = [
    {
        "id": "search_python_files",
        "description": "Search for Python files",
        "task": {
            "action": "file_search",
            "pattern": "*.py",
            "max_results": 10,
        },
        "expected_success": True,
    },
    {
        "id": "search_nonexistent",
        "description": "Search in non-existent directory",
        "task": {
            "action": "file_search",
            "pattern": "*.xyz",
            "directory": "/nonexistent/path",
        },
        "expected_success": True,  # Should return empty list, not error
    },
    {
        "id": "search_with_content",
        "description": "Search with content pattern",
        "task": {
            "action": "file_search",
            "pattern": "*.py",
            "content_pattern": "def ",
            "max_results": 5,
        },
        "expected_success": True,
    },
]


async def run_evaluation(
    runtime: StudentRuntime,
    tasks: List[Dict[str, Any]],
    db: MCPBoxDatabase = None,
    box_name: str = "unknown",
) -> Dict[str, Any]:
    """Run evaluation on a set of tasks."""
    results = []
    total_time = 0
    success_count = 0
    
    for eval_task in tasks:
        task_id = eval_task.get("id", "unknown")
        description = eval_task.get("description", "")
        task = eval_task.get("task", {})
        expected = eval_task.get("expected_success", True)
        
        print(f"\n📋 Task: {task_id}")
        print(f"   Description: {description}")
        
        start = time.time()
        result = await runtime.execute_task(task)
        elapsed = time.time() - start
        total_time += elapsed
        
        # Check against expected
        matches_expected = result.success == expected
        if result.success:
            success_count += 1
        
        status = "✅" if matches_expected else "⚠️"
        print(f"   {status} Result: {'success' if result.success else 'failed'} (expected: {'success' if expected else 'failed'})")
        print(f"   Time: {elapsed:.3f}s")
        
        task_result = {
            "task_id": task_id,
            "success": result.success,
            "expected": expected,
            "matches_expected": matches_expected,
            "time": elapsed,
            "error": result.error,
        }
        results.append(task_result)
        
        # Log to database if available
        if db:
            run = Run(
                box_name=box_name,
                task_id=task_id,
                task_data=task,
                success=result.success,
                result=result.result,
                error=result.error,
                execution_time=elapsed,
                tool_calls=result.tool_calls,
            )
            db.log_run(run)
    
    # Calculate metrics
    total_tasks = len(tasks)
    success_rate = success_count / total_tasks if total_tasks > 0 else 0
    avg_time = total_time / total_tasks if total_tasks > 0 else 0
    matches_expected_count = sum(1 for r in results if r["matches_expected"])
    
    metrics = {
        "total_tasks": total_tasks,
        "success_count": success_count,
        "success_rate": success_rate,
        "matches_expected_count": matches_expected_count,
        "matches_expected_rate": matches_expected_count / total_tasks if total_tasks > 0 else 0,
        "total_time": total_time,
        "avg_time": avg_time,
    }
    
    # Log metrics to database
    if db:
        for name, value in metrics.items():
            if isinstance(value, (int, float)):
                db.log_metric(Metric(
                    box_name=box_name,
                    metric_name=name,
                    metric_value=float(value),
                ))
    
    return {
        "results": results,
        "metrics": metrics,
    }


def print_summary(eval_results: Dict[str, Any]):
    """Print evaluation summary."""
    metrics = eval_results["metrics"]
    
    print("\n" + "=" * 50)
    print("📊 EVALUATION SUMMARY")
    print("=" * 50)
    print(f"   Total tasks: {metrics['total_tasks']}")
    print(f"   Successful: {metrics['success_count']}")
    print(f"   Success rate: {metrics['success_rate']:.1%}")
    print(f"   Matches expected: {metrics['matches_expected_count']}")
    print(f"   Accuracy: {metrics['matches_expected_rate']:.1%}")
    print(f"   Total time: {metrics['total_time']:.3f}s")
    print(f"   Avg time per task: {metrics['avg_time']:.3f}s")


async def main_async(args):
    """Async main function."""
    # Load MCPBox
    if args.box:
        print(f"📦 Loading MCPBox from: {args.box}")
        runtime = StudentRuntime.from_file(args.box)
        box_name = Path(args.box).stem
    else:
        # Create demo runtime
        print("📦 Using demo MCPBox")
        from mcp_box.tools.file_ops import file_search
        
        mcp_box = MCPBox(name="demo-box", version="0.1.0")
        runtime = StudentRuntime(mcp_box)
        runtime._tool_cache["file_search"] = file_search
        box_name = "demo-box"
    
    # Load tasks
    if args.tasks:
        print(f"📋 Loading tasks from: {args.tasks}")
        with open(args.tasks) as f:
            tasks = json.load(f)
    else:
        print("📋 Using default evaluation tasks")
        tasks = DEFAULT_TASKS
    
    # Setup database
    db = None
    if args.db:
        print(f"💾 Using database: {args.db}")
        db = MCPBoxDatabase(args.db)
    
    # Run evaluation
    print(f"\n🚀 Running evaluation with {len(tasks)} tasks...")
    eval_results = await run_evaluation(runtime, tasks, db, box_name)
    
    # Print summary
    print_summary(eval_results)
    
    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(eval_results, f, indent=2)
        print(f"\n💾 Results saved to: {args.output}")
    
    # Cleanup
    if db:
        db.close()
    
    return eval_results


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate MCPBox performance"
    )
    parser.add_argument(
        "--box",
        type=str,
        help="Path to MCPBox JSON file",
    )
    parser.add_argument(
        "--tasks",
        type=str,
        help="Path to tasks JSON file",
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Path to SQLite database for persistence",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output path for evaluation results",
    )
    
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

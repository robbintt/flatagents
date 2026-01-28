"""
FlatAgents CLI Runner.

Entry point for running machines via subprocess:
    python -m flatagents.run --config machine.yml --input '{"key": "value"}'

Used by SubprocessInvoker for fire-and-forget machine execution.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Run a FlatMachine from the command line",
        prog="python -m flatagents.run"
    )
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to machine config file (YAML or JSON)"
    )
    parser.add_argument(
        "--input", "-i",
        default="{}",
        help="JSON string of input data"
    )
    parser.add_argument(
        "--execution-id", "-e",
        help="Predetermined execution ID"
    )
    parser.add_argument(
        "--parent-id", "-p",
        help="Parent execution ID for lineage tracking"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=1000,
        help="Maximum execution steps (default: 1000)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse input
    try:
        input_data = json.loads(args.input)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON input: {e}")
        sys.exit(1)
    
    # Validate config path
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    # Import here to avoid circular imports
    from .flatmachine import FlatMachine
    
    # Build machine with optional execution IDs
    machine_kwargs = {
        "config_file": str(config_path),
    }
    
    if args.execution_id:
        machine_kwargs["_execution_id"] = args.execution_id
    if args.parent_id:
        machine_kwargs["_parent_execution_id"] = args.parent_id
    
    try:
        machine = FlatMachine(**machine_kwargs)
        
        # Run the machine
        result = asyncio.run(
            machine.execute(
                input=input_data,
                max_steps=args.max_steps
            )
        )
        
        # Output result as JSON
        print(json.dumps(result, indent=2, default=str))
        
        # Log stats
        logger.info(
            f"Execution complete: {machine.total_api_calls} API calls, "
            f"${machine.total_cost:.4f} cost"
        )
        
    except Exception as e:
        logger.exception(f"Execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

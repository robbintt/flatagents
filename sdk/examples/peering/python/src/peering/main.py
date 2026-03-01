"""
Peering Demo for FlatAgents.

Demonstrates machine-to-machine communication, persistence,
and checkpointing in a distributed workflow.

Usage:
    python -m peering.main
    ./run.sh
"""

import asyncio
import json
from pathlib import Path

from flatmachines import FlatMachine, InMemoryResultBackend, MemoryBackend, setup_logging, get_logger

# Configure logging
setup_logging(level="INFO")
logger = get_logger(__name__)


async def run():
    """Run the peering demo."""
    logger.info("=== Peering Example ===")
    logger.info("Launching peering demo machine...\n")

    root_dir = Path(__file__).parent.parent.parent.parent
    config_dir = root_dir / "config"

    # Set up persistence and result backends for peering
    persistence_backend = MemoryBackend()
    result_backend = InMemoryResultBackend()

    peering_demo = FlatMachine(
        config_file=str(config_dir / "peering_demo.yml"),
        persistence=persistence_backend,
        result_backend=result_backend,
    )

    try:
        # Run the demo flow defined in the machine config
        result = await peering_demo.execute()
        logger.info(f"Demo result: {json.dumps(result, indent=2)}")

        # Demonstrate checkpoint/resume
        logger.info("\n=== Checkpoint/Resume Demo ===")
        if peering_demo.execution_id:
            logger.info(f"Execution ID: {peering_demo.execution_id}")
            logger.info("Could resume from checkpoint using this ID")

    except Exception:
        logger.exception("Error running peering demo")


def main():
    """Main entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()

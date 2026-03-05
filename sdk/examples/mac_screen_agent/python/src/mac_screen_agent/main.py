"""
macOS Screen Agent — an automation agent with screenshot, mouse, and keyboard tools.

Default: interactive REPL. Use -p for single-shot mode.

Usage:
    python -m mac_screen_agent.main                                    # REPL
    python -m mac_screen_agent.main -p "open Safari and go to google"  # single-shot
    python -m mac_screen_agent.main --standalone "take a screenshot"
"""

import argparse
import asyncio
import logging
import os
import sys
import warnings
from pathlib import Path

# Suppress validation warnings until schemas are regenerated
warnings.filterwarnings("ignore", message=".*validation.*")
warnings.filterwarnings("ignore", message=".*Flatmachine.*")
warnings.filterwarnings("ignore", message=".*Flatagent.*")

from flatmachines import FlatMachine  # noqa: E402
from flatagents import FlatAgent  # noqa: E402
from flatagents.tool_loop import ToolLoopAgent, Guardrails, StopReason  # noqa: E402

from .hooks import ScreenAgentHooks  # noqa: E402
from .tools import ScreenToolProvider  # noqa: E402

try:
    import readline  # noqa: F401 — enables arrow keys, history in input()
except ImportError:
    pass

# Quiet by default — set LOG_LEVEL=INFO or LOG_LEVEL=DEBUG to see logs
_log_level = os.environ.get("LOG_LEVEL", "WARNING").upper()
logging.getLogger().setLevel(_log_level)
for _name in ("flatagents", "flatmachines", "LiteLLM"):
    logging.getLogger(_name).setLevel(_log_level)


def _config_path(name: str) -> str:
    return str(Path(__file__).parent.parent.parent.parent / "config" / name)


async def run_machine(task: str):
    """Run a single task via FlatMachine with tool loop + human review."""
    hooks = ScreenAgentHooks()
    machine = FlatMachine(
        config_file=_config_path("machine.yml"),
        hooks=hooks,
    )

    result = await machine.execute(input={
        "task": task,
    })

    return result


async def run_standalone(task: str):
    """Run a single task via ToolLoopAgent (no machine)."""
    agent = FlatAgent(config_file=_config_path("agent.yml"))
    provider = ScreenToolProvider()

    loop = ToolLoopAgent(
        agent=agent,
        tool_provider=provider,
        guardrails=Guardrails(
            max_turns=50,
            max_tool_calls=200,
            max_cost=5.00,
            tool_timeout=30.0,
            total_timeout=900.0,
        ),
    )

    result = await loop.run(task=task)

    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Stop reason: {result.stop_reason.value}")
    print(f"Tool calls:  {result.tool_calls_count}")
    print(f"LLM turns:   {result.turns}")
    print(f"API calls:   {result.usage.api_calls}")
    print(f"Cost:        ${result.usage.total_cost:.4f}")
    print()

    if result.error:
        print(f"Error: {result.error}")

    if result.content:
        print(result.content)

    return result


async def repl():
    """Interactive REPL — enter tasks, agent executes with human review loop."""
    print("macOS Screen Agent")
    print("  Tools: screenshot, mouse_move, mouse_click, key_type, key_press")
    print("  Type a goal, then press Enter. Agent will loop until done.")
    print()

    _interrupt_count = 0

    while True:
        try:
            task = input("> ").strip()
            _interrupt_count = 0
        except KeyboardInterrupt:
            _interrupt_count += 1
            if _interrupt_count >= 2:
                print()
                break
            print()
            continue
        except EOFError:
            print()
            break

        if not task:
            continue

        _interrupt_count = 0

        try:
            await run_machine(task)
        except KeyboardInterrupt:
            print("\nInterrupted.")
        except Exception as e:
            print(f"Error: {e}")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="macOS screen automation agent with screenshot, mouse, and keyboard tools"
    )
    parser.add_argument(
        "-p", "--print",
        metavar="TASK",
        dest="task",
        help="Run a single task and exit",
    )
    parser.add_argument(
        "--standalone", "-s",
        metavar="TASK",
        nargs="?",
        const=True,
        help="Use standalone ToolLoopAgent (no machine, no human review)",
    )
    args = parser.parse_args()

    if args.standalone:
        task = args.standalone if isinstance(args.standalone, str) and args.standalone is not True else args.task
        if not task:
            parser.error("--standalone requires a task (--standalone 'task' or -p 'task' --standalone)")
        asyncio.run(run_standalone(task))
    elif args.task:
        asyncio.run(run_machine(args.task))
    else:
        asyncio.run(repl())


if __name__ == "__main__":
    main()

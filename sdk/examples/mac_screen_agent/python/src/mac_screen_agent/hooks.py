"""
Screen Agent Hooks.

Provides the tool provider, per-call display, and human review.
"""

import sys
from typing import Any, Dict, List

from flatmachines import MachineHooks
from .tools import ScreenToolProvider


def _dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


class ScreenAgentHooks(MachineHooks):
    """Hooks for screen agent workflow with per-call display and human review."""

    def __init__(self):
        self._provider = ScreenToolProvider()

    def get_tool_provider(self, state_name: str):
        return self._provider

    def on_action(self, action_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if action_name == "human_review":
            return self._human_review(context)
        return context

    def on_tool_calls(self, state_name: str, tool_calls: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Print agent thinking/content and token usage before tool execution."""
        content = context.get("_tool_loop_content")
        if content and content.strip():
            print()
            print(_dim(content.strip()))

        usage = context.get("_tool_loop_usage") or {}
        parts = []
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if input_tokens is not None or output_tokens is not None:
            parts.append(f"tokens: {input_tokens or 0}→{output_tokens or 0}")
        cost = context.get("_tool_loop_cost")
        if cost:
            parts.append(f"${cost:.4f}")
        if parts:
            print(_dim(" | ".join(parts)))

        return context

    def on_tool_result(self, state_name: str, tool_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Print tool call result."""
        name = tool_result.get("name", "")
        args = tool_result.get("arguments", {})
        is_error = tool_result.get("is_error", False)

        if name == "screenshot":
            label = "screenshot"
        elif name == "mouse_move":
            label = f"mouse_move: ({args.get('x', '?')}, {args.get('y', '?')})"
        elif name == "mouse_click":
            btn = args.get("button", "left")
            label = f"mouse_click: ({args.get('x', '?')}, {args.get('y', '?')}) [{btn}]"
        elif name == "key_type":
            text = args.get("text", "")
            display = text if len(text) <= 40 else text[:37] + "..."
            label = f"key_type: {display!r}"
        elif name == "key_press":
            label = f"key_press: {args.get('keys', '')}"
        else:
            label = f"{name}: {args}"

        status = "✗" if is_error else "✓"
        print(f"  {status} {_bold(label)}")

        return context

    def _human_review(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Show agent output, ask for follow-up or accept."""
        result = context.get("result", "")
        if result:
            print()
            print(result)

        print()
        try:
            response = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            response = ""

        if response:
            chain = context.get("_tool_loop_chain", [])
            chain.append({"role": "user", "content": response})
            context["_tool_loop_chain"] = chain
            context["human_approved"] = False
        else:
            context["human_approved"] = True

        return context

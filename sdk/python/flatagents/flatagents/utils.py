"""Utility functions for flatagents."""

import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from .monitoring import get_logger

logger = get_logger(__name__)


def check_spec_version(config_version: Optional[str], sdk_version: str) -> str:
    """
    Check spec version compatibility and warn if mismatched.

    Args:
        config_version: Version from config file (may be None)
        sdk_version: Current SDK version (__version__)

    Returns:
        The effective spec version (config_version or sdk_version as default)
    """
    effective_version = config_version or sdk_version
    sdk_major_minor = '.'.join(sdk_version.split('.')[:2])
    config_major_minor = '.'.join(effective_version.split('.')[:2])

    if config_major_minor != sdk_major_minor:
        logger.warning(
            f"Config version {effective_version} may not be fully supported. "
            f"Current SDK version is {sdk_version}."
        )

    return effective_version


def strip_markdown_json(content: str) -> str:
    """
    Extract JSON from potentially wrapped response content.

    LLMs sometimes wrap JSON responses in markdown code blocks like:
    ```json
    {"key": "value"}
    ```

    Or include explanatory text before/after the JSON:
    "Here is the result:
    ```json
    {"key": "value"}
    ```"

    This function extracts the JSON so json.loads() can parse it.

    Args:
        content: Raw string that may contain markdown-wrapped JSON

    Returns:
        Extracted JSON string
    """
    if not content:
        return content

    text = content.strip()

    # First, try to find JSON in a markdown code fence (anywhere in content)
    fence_pattern = r'```(?:json|JSON)?\s*\n?([\s\S]*?)\n?```'
    match = re.search(fence_pattern, text)
    if match:
        return match.group(1).strip()

    # If no fence, try to find a raw JSON object or array
    json_pattern = r'(\{[\s\S]*\}|\[[\s\S]*\])'
    match = re.search(json_pattern, text)
    if match:
        return match.group(1)

    return text


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _coerce_usage(usage: Any) -> Any:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return SimpleNamespace(**usage)
    return usage


async def consume_litellm_stream(stream: Any) -> Any:
    content_parts: List[str] = []
    tool_calls: Dict[int, Dict[str, Any]] = {}
    usage_data: Any = None
    finish_reason: Optional[str] = None

    async for chunk in stream:
        if chunk is None:
            continue
        usage = _get_attr(chunk, "usage")
        if usage:
            usage_data = usage

        choices = _get_attr(chunk, "choices")
        if not choices:
            continue
        choice0 = choices[0]
        finish = _get_attr(choice0, "finish_reason")
        if finish:
            finish_reason = finish

        delta = _get_attr(choice0, "delta")
        if not delta:
            continue

        content_piece = _get_attr(delta, "content")
        if content_piece:
            content_parts.append(content_piece)

        delta_tool_calls = _get_attr(delta, "tool_calls")
        if delta_tool_calls:
            for tc in delta_tool_calls:
                index = _get_attr(tc, "index", 0)
                entry = tool_calls.setdefault(index, {"id": None, "name": None, "arguments": []})
                tc_id = _get_attr(tc, "id")
                if tc_id:
                    entry["id"] = tc_id
                function = _get_attr(tc, "function")
                if function:
                    name = _get_attr(function, "name")
                    if name:
                        entry["name"] = name
                    arguments = _get_attr(function, "arguments")
                    if arguments:
                        entry["arguments"].append(arguments)

    content = "".join(content_parts)
    message_fields: Dict[str, Any] = {"content": content}
    if tool_calls:
        tool_call_objs = []
        for index in sorted(tool_calls):
            entry = tool_calls[index]
            tool_call_objs.append(SimpleNamespace(
                id=entry["id"],
                function=SimpleNamespace(
                    name=entry["name"],
                    arguments="".join(entry["arguments"]) if entry["arguments"] else ""
                )
            ))
        message_fields["tool_calls"] = tool_call_objs

    message = SimpleNamespace(**message_fields)
    choice = SimpleNamespace(message=message)
    if finish_reason is not None:
        choice.finish_reason = finish_reason

    return SimpleNamespace(
        choices=[choice],
        usage=_coerce_usage(usage_data)
    )

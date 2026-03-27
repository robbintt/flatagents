#!/usr/bin/env python3
"""smolagents subprocess runner — analogous to pi_agent_runner.mjs.

Reads a JSON request on **stdin**, loads a smolagents factory, executes the
agent, and writes a JSON response to **stdout**.

Request schema (JSON):
    {
        "ref": "path/to/factory.py#build_agent",   // module#factory
        "config": { ... },                          // kwargs for factory()
        "input": {
            "task": "...",                           // required
            "max_steps": 5,                          // optional
            "additional_args": { ... }               // optional
        }
    }

Response schema (JSON):
    {
        "output": { "content": "..." },
        "content": "...",
        "usage": { ... } | null,
        "cost": <float> | null,
        "raw": <any>
    }
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import traceback
from typing import Any, Dict, Tuple


# ---------------------------------------------------------------------------
# Factory loading (mirrors the pattern in smolagents.py)
# ---------------------------------------------------------------------------

def _parse_ref(ref: str) -> Tuple[str, str]:
    if "#" in ref:
        module_ref, factory_name = ref.split("#", 1)
    else:
        module_ref, factory_name = ref, "build_agent"
    return module_ref, factory_name


def _load_factory(ref: str, cwd: str):
    module_ref, factory_name = _parse_ref(ref)

    if module_ref.endswith(".py") or module_ref.startswith(".") or "/" in module_ref:
        module_path = module_ref
        if not os.path.isabs(module_path):
            module_path = os.path.join(cwd, module_path)
        spec = importlib.util.spec_from_file_location("smolagents_factory", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load smolagents factory from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(module_ref)

    factory = getattr(module, factory_name, None)
    if factory is None:
        raise AttributeError(f"Factory '{factory_name}' not found in {module_ref}")
    return factory


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    raw = sys.stdin.read()
    if not raw:
        raise RuntimeError("Expected JSON input on stdin for smolagents runner")

    request: Dict[str, Any] = json.loads(raw)
    ref = request.get("ref")
    config = request.get("config") or {}
    input_data = request.get("input") or {}
    cwd = request.get("cwd") or os.getcwd()

    if not ref:
        raise ValueError("Missing required field 'ref' (path to factory module) in smolagents runner request")

    # Load factory and build agent
    factory = _load_factory(ref, cwd)
    agent = factory(**config)

    # Determine task
    task = input_data.get("task") or input_data.get("prompt")
    if task is None:
        raise ValueError("Missing required field: smolagents runner requires either input.task or input.prompt")

    # Build run kwargs
    run_kwargs: Dict[str, Any] = {}
    if input_data.get("additional_args") is not None:
        run_kwargs["additional_args"] = input_data["additional_args"]
    if input_data.get("max_steps") is not None:
        run_kwargs["max_steps"] = input_data["max_steps"]

    # Always request full result when available
    run_kwargs.setdefault("return_full_result", True)

    # Execute
    result = agent.run(task, **run_kwargs)

    # Normalise output
    content = None
    output = None
    usage = None
    cost = None
    raw_result = None

    # smolagents RunResult
    if hasattr(result, "output"):
        raw_result = str(result)
        result_output = result.output
        if result_output is None:
            pass
        elif isinstance(result_output, dict):
            output = result_output
            content = result_output.get("content") if isinstance(result_output.get("content"), str) else None
        else:
            content = str(result_output)
            output = {"content": content}

        if hasattr(result, "token_usage") and result.token_usage is not None:
            try:
                usage = result.token_usage.dict()
            except Exception:
                usage = None
    elif isinstance(result, dict):
        output = result
        content = result.get("content") if isinstance(result.get("content"), str) else None
        raw_result = result
    else:
        content = None if result is None else str(result)
        output = {"content": content} if content is not None else None
        raw_result = result

    response = {
        "output": output,
        "content": content,
        "usage": usage,
        "cost": cost,
        "raw": raw_result,
    }
    sys.stdout.write(json.dumps(response))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

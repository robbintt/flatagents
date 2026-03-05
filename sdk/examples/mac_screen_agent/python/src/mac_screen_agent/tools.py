"""
macOS screen automation tools: screenshot, mouse_move, mouse_click, key_type, key_press.

Uses PyObjC (Quartz) for screenshots and cliclick for mouse/keyboard control.
All tools are designed for macOS and require Accessibility permissions.
"""

from __future__ import annotations

import base64
import io
import subprocess
import time
from typing import Any, Dict

from flatagents.tools import ToolProvider, ToolResult


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

def _take_screenshot_quartz() -> bytes:
    """Capture the main display using macOS Quartz (PyObjC). Returns PNG bytes."""
    import Quartz
    from Cocoa import NSBitmapImageRep, NSPNGFileType

    # Capture the main display
    image_ref = Quartz.CGDisplayCreateImage(Quartz.CGMainDisplayID())
    if image_ref is None:
        raise RuntimeError(
            "CGDisplayCreateImage returned None. "
            "Ensure Screen Recording permission is granted in "
            "System Settings > Privacy & Security > Screen Recording."
        )

    bitmap = NSBitmapImageRep.alloc().initWithCGImage_(image_ref)
    png_data = bitmap.representationUsingType_properties_(NSPNGFileType, None)
    return bytes(png_data)


def _take_screenshot_screencapture() -> bytes:
    """Fallback: use macOS screencapture command. Returns PNG bytes."""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["screencapture", "-x", "-C", tmp_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"screencapture failed (code {result.returncode}): {result.stderr}"
            )
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def tool_screenshot(_id: str, args: Dict[str, Any]) -> ToolResult:
    """Take a screenshot and return base64-encoded PNG."""
    try:
        try:
            png_bytes = _take_screenshot_quartz()
        except ImportError:
            png_bytes = _take_screenshot_screencapture()

        encoded = base64.b64encode(png_bytes).decode("ascii")
        return ToolResult(
            content=[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": encoded,
                    },
                },
                {
                    "type": "text",
                    "text": f"Screenshot captured ({len(png_bytes)} bytes)",
                },
            ],
        )
    except Exception as e:
        return ToolResult(content=f"Screenshot failed: {e}", is_error=True)


# ---------------------------------------------------------------------------
# Mouse control via cliclick
# ---------------------------------------------------------------------------

def _run_cliclick(args: list[str], timeout: int = 5) -> str:
    """Run a cliclick command. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["cliclick"] + args,
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"cliclick failed: {stderr or result.stdout}")
    return result.stdout.strip()


async def tool_mouse_move(_id: str, args: Dict[str, Any]) -> ToolResult:
    """Move the mouse cursor to (x, y)."""
    x = args.get("x")
    y = args.get("y")
    if x is None or y is None:
        return ToolResult(content="x and y are required", is_error=True)

    try:
        _run_cliclick(["m:{},{}".format(int(x), int(y))])
        return ToolResult(content=f"Mouse moved to ({int(x)}, {int(y)})")
    except FileNotFoundError:
        return ToolResult(
            content="cliclick not found. Install with: brew install cliclick",
            is_error=True,
        )
    except Exception as e:
        return ToolResult(content=f"mouse_move failed: {e}", is_error=True)


async def tool_mouse_click(_id: str, args: Dict[str, Any]) -> ToolResult:
    """Click the mouse at (x, y)."""
    x = args.get("x")
    y = args.get("y")
    button = args.get("button", "left")
    if x is None or y is None:
        return ToolResult(content="x and y are required", is_error=True)

    try:
        coord = "{},{}".format(int(x), int(y))
        if button == "right":
            _run_cliclick(["rc:{}".format(coord)])
        elif button == "double":
            _run_cliclick(["dc:{}".format(coord)])
        else:
            _run_cliclick(["c:{}".format(coord)])
        return ToolResult(content=f"Mouse {button}-clicked at ({int(x)}, {int(y)})")
    except FileNotFoundError:
        return ToolResult(
            content="cliclick not found. Install with: brew install cliclick",
            is_error=True,
        )
    except Exception as e:
        return ToolResult(content=f"mouse_click failed: {e}", is_error=True)


# ---------------------------------------------------------------------------
# Keyboard control via cliclick
# ---------------------------------------------------------------------------

async def tool_key_type(_id: str, args: Dict[str, Any]) -> ToolResult:
    """Type a text string using cliclick."""
    text = args.get("text", "")
    if not text:
        return ToolResult(content="text is required", is_error=True)

    try:
        _run_cliclick(["t:{}".format(text)])
        return ToolResult(content=f"Typed: {text!r}")
    except FileNotFoundError:
        return ToolResult(
            content="cliclick not found. Install with: brew install cliclick",
            is_error=True,
        )
    except Exception as e:
        return ToolResult(content=f"key_type failed: {e}", is_error=True)


# cliclick key name mapping
_KEY_MAP = {
    "return": "return",
    "enter": "return",
    "tab": "tab",
    "escape": "esc",
    "esc": "esc",
    "space": "space",
    "delete": "delete",
    "backspace": "delete",
    "forwarddelete": "fwd-delete",
    "up": "arrow-up",
    "down": "arrow-down",
    "left": "arrow-left",
    "right": "arrow-right",
    "home": "home",
    "end": "end",
    "pageup": "page-up",
    "pagedown": "page-down",
    "command": "cmd",
    "cmd": "cmd",
    "control": "ctrl",
    "ctrl": "ctrl",
    "option": "alt",
    "alt": "alt",
    "shift": "shift",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}


def _translate_key(key: str) -> str:
    """Map a user-friendly key name to cliclick key name."""
    return _KEY_MAP.get(key.lower(), key)


async def tool_key_press(_id: str, args: Dict[str, Any]) -> ToolResult:
    """Press a key or key combination using cliclick."""
    keys = args.get("keys", "")
    if not keys:
        return ToolResult(content="keys is required", is_error=True)

    try:
        parts = [p.strip() for p in keys.split("+")]
        if len(parts) == 1:
            # Single key press
            translated = _translate_key(parts[0])
            _run_cliclick(["kp:{}".format(translated)])
        else:
            # Combination: modifier(s) + key
            modifiers = [_translate_key(p) for p in parts[:-1]]
            key = _translate_key(parts[-1])

            # Build cliclick key-down, key-press, key-up sequence
            cmds = []
            for mod in modifiers:
                cmds.append("kd:{}".format(mod))
            cmds.append("kp:{}".format(key))
            for mod in reversed(modifiers):
                cmds.append("ku:{}".format(mod))
            _run_cliclick(cmds)

        return ToolResult(content=f"Pressed: {keys}")
    except FileNotFoundError:
        return ToolResult(
            content="cliclick not found. Install with: brew install cliclick",
            is_error=True,
        )
    except Exception as e:
        return ToolResult(content=f"key_press failed: {e}", is_error=True)


# ---------------------------------------------------------------------------
# ToolProvider
# ---------------------------------------------------------------------------

class ScreenToolProvider:
    """ToolProvider with screenshot, mouse, and keyboard tools for macOS."""

    def get_tool_definitions(self) -> list:
        # Definitions come from the agent YAML, not here
        return []

    async def execute_tool(self, name: str, tool_call_id: str, arguments: Dict[str, Any]) -> ToolResult:
        if name == "screenshot":
            return await tool_screenshot(tool_call_id, arguments)
        elif name == "mouse_move":
            return await tool_mouse_move(tool_call_id, arguments)
        elif name == "mouse_click":
            return await tool_mouse_click(tool_call_id, arguments)
        elif name == "key_type":
            return await tool_key_type(tool_call_id, arguments)
        elif name == "key_press":
            return await tool_key_press(tool_call_id, arguments)
        else:
            return ToolResult(content=f"Unknown tool: {name}", is_error=True)

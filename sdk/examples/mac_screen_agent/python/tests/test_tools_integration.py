"""
Integration tests for mac_screen_agent tools.

Tests tool implementations with mocked system commands (cliclick, screencapture)
to verify correct behavior without requiring macOS or actual screen access.
Uses a real PNG fixture image for screenshot tool testing.
"""

import asyncio
import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock

import pytest

# Import the tools module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mac_screen_agent.tools import (
    ScreenToolProvider,
    tool_screenshot,
    tool_mouse_move,
    tool_mouse_click,
    tool_key_type,
    tool_key_press,
    _translate_key,
    _KEY_MAP,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent
TEST_PNG_PATH = FIXTURE_DIR / "test_fixture.png"


@pytest.fixture
def png_bytes():
    """Load the test PNG fixture."""
    return TEST_PNG_PATH.read_bytes()


@pytest.fixture
def provider():
    """Create a ScreenToolProvider instance."""
    return ScreenToolProvider()


def _mock_cliclick_success(*args, **kwargs):
    """Mock subprocess.run for cliclick returning success."""
    return MagicMock(returncode=0, stdout="", stderr="")


def _mock_cliclick_failure(*args, **kwargs):
    """Mock subprocess.run for cliclick returning failure."""
    return MagicMock(returncode=1, stdout="", stderr="Permission denied")


# ---------------------------------------------------------------------------
# Screenshot tool tests
# ---------------------------------------------------------------------------

class TestScreenshotTool:
    """Tests for the screenshot tool with a real PNG fixture image."""

    @pytest.mark.asyncio
    async def test_screenshot_returns_base64_image(self, png_bytes):
        """Screenshot tool should return a base64-encoded PNG via the image content type."""
        with patch("mac_screen_agent.tools._take_screenshot_quartz", side_effect=ImportError):
            with patch("mac_screen_agent.tools._take_screenshot_screencapture", return_value=png_bytes):
                result = await tool_screenshot("call-1", {})

        assert not result.is_error
        assert isinstance(result.content, list)
        assert len(result.content) == 2

        # First element should be the image
        image_block = result.content[0]
        assert image_block["type"] == "image"
        assert image_block["source"]["type"] == "base64"
        assert image_block["source"]["media_type"] == "image/png"

        # Verify the base64 data decodes back to the original PNG
        decoded = base64.b64decode(image_block["source"]["data"])
        assert decoded == png_bytes

        # Second element should be text summary
        text_block = result.content[1]
        assert text_block["type"] == "text"
        assert "bytes" in text_block["text"]

    @pytest.mark.asyncio
    async def test_screenshot_quartz_preferred(self, png_bytes):
        """Should prefer Quartz over screencapture when available."""
        with patch("mac_screen_agent.tools._take_screenshot_quartz", return_value=png_bytes):
            result = await tool_screenshot("call-1", {})

        assert not result.is_error
        decoded = base64.b64decode(result.content[0]["source"]["data"])
        assert decoded == png_bytes

    @pytest.mark.asyncio
    async def test_screenshot_falls_back_to_screencapture(self, png_bytes):
        """Should fall back to screencapture when Quartz is unavailable."""
        with patch("mac_screen_agent.tools._take_screenshot_quartz", side_effect=ImportError):
            with patch("mac_screen_agent.tools._take_screenshot_screencapture", return_value=png_bytes):
                result = await tool_screenshot("call-1", {})

        assert not result.is_error

    @pytest.mark.asyncio
    async def test_screenshot_error_handling(self):
        """Screenshot tool should return an error if both methods fail."""
        with patch("mac_screen_agent.tools._take_screenshot_quartz", side_effect=ImportError):
            with patch("mac_screen_agent.tools._take_screenshot_screencapture", side_effect=RuntimeError("no display")):
                result = await tool_screenshot("call-1", {})

        assert result.is_error
        assert "no display" in result.content


# ---------------------------------------------------------------------------
# Mouse tool tests
# ---------------------------------------------------------------------------

class TestMouseTools:
    """Tests for mouse_move and mouse_click tools."""

    @pytest.mark.asyncio
    async def test_mouse_move(self):
        """mouse_move should call cliclick with m: command."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success) as mock_run:
            result = await tool_mouse_move("call-1", {"x": 100, "y": 200})

        assert not result.is_error
        assert "100" in result.content
        assert "200" in result.content
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "cliclick" in cmd
        assert "m:100,200" in cmd

    @pytest.mark.asyncio
    async def test_mouse_move_missing_coords(self):
        """mouse_move should error if x or y is missing."""
        result = await tool_mouse_move("call-1", {"x": 100})
        assert result.is_error

        result = await tool_mouse_move("call-1", {"y": 200})
        assert result.is_error

    @pytest.mark.asyncio
    async def test_mouse_click_left(self):
        """mouse_click should use c: for left click."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success) as mock_run:
            result = await tool_mouse_click("call-1", {"x": 50, "y": 75})

        assert not result.is_error
        cmd = mock_run.call_args[0][0]
        assert "c:50,75" in cmd

    @pytest.mark.asyncio
    async def test_mouse_click_right(self):
        """mouse_click should use rc: for right click."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success) as mock_run:
            result = await tool_mouse_click("call-1", {"x": 50, "y": 75, "button": "right"})

        assert not result.is_error
        cmd = mock_run.call_args[0][0]
        assert "rc:50,75" in cmd

    @pytest.mark.asyncio
    async def test_mouse_click_double(self):
        """mouse_click should use dc: for double click."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success) as mock_run:
            result = await tool_mouse_click("call-1", {"x": 50, "y": 75, "button": "double"})

        assert not result.is_error
        cmd = mock_run.call_args[0][0]
        assert "dc:50,75" in cmd

    @pytest.mark.asyncio
    async def test_mouse_click_missing_coords(self):
        """mouse_click should error if x or y is missing."""
        result = await tool_mouse_click("call-1", {"x": 50})
        assert result.is_error

    @pytest.mark.asyncio
    async def test_mouse_cliclick_not_found(self):
        """Should return helpful error if cliclick is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await tool_mouse_click("call-1", {"x": 50, "y": 75})

        assert result.is_error
        assert "brew install cliclick" in result.content

    @pytest.mark.asyncio
    async def test_mouse_cliclick_failure(self):
        """Should return error content on cliclick failure."""
        with patch("subprocess.run", side_effect=_mock_cliclick_failure):
            result = await tool_mouse_click("call-1", {"x": 50, "y": 75})

        assert result.is_error
        assert "Permission denied" in result.content


# ---------------------------------------------------------------------------
# Keyboard tool tests
# ---------------------------------------------------------------------------

class TestKeyboardTools:
    """Tests for key_type and key_press tools."""

    @pytest.mark.asyncio
    async def test_key_type(self):
        """key_type should call cliclick with t: command."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success) as mock_run:
            result = await tool_key_type("call-1", {"text": "hello world"})

        assert not result.is_error
        assert "hello world" in result.content
        cmd = mock_run.call_args[0][0]
        assert "t:hello world" in cmd

    @pytest.mark.asyncio
    async def test_key_type_empty(self):
        """key_type should error if text is empty."""
        result = await tool_key_type("call-1", {"text": ""})
        assert result.is_error

    @pytest.mark.asyncio
    async def test_key_press_single_key(self):
        """key_press should call cliclick kp: for a single key."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success) as mock_run:
            result = await tool_key_press("call-1", {"keys": "Return"})

        assert not result.is_error
        cmd = mock_run.call_args[0][0]
        assert "kp:return" in cmd

    @pytest.mark.asyncio
    async def test_key_press_combination(self):
        """key_press should handle modifier+key combinations."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success) as mock_run:
            result = await tool_key_press("call-1", {"keys": "command+c"})

        assert not result.is_error
        cmd = mock_run.call_args[0][0]
        # Should have kd:cmd, kp:c, ku:cmd
        assert "kd:cmd" in cmd
        assert "ku:cmd" in cmd

    @pytest.mark.asyncio
    async def test_key_press_empty(self):
        """key_press should error if keys is empty."""
        result = await tool_key_press("call-1", {"keys": ""})
        assert result.is_error

    @pytest.mark.asyncio
    async def test_key_cliclick_not_found(self):
        """Should return helpful error if cliclick is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await tool_key_type("call-1", {"text": "hello"})

        assert result.is_error
        assert "brew install cliclick" in result.content


# ---------------------------------------------------------------------------
# Key mapping tests
# ---------------------------------------------------------------------------

class TestKeyMapping:
    """Tests for the key name translation."""

    def test_common_keys(self):
        assert _translate_key("Return") == "return"
        assert _translate_key("Tab") == "tab"
        assert _translate_key("Escape") == "esc"
        assert _translate_key("space") == "space"
        assert _translate_key("delete") == "delete"

    def test_arrow_keys(self):
        assert _translate_key("up") == "arrow-up"
        assert _translate_key("down") == "arrow-down"
        assert _translate_key("left") == "arrow-left"
        assert _translate_key("right") == "arrow-right"

    def test_modifier_keys(self):
        assert _translate_key("command") == "cmd"
        assert _translate_key("control") == "ctrl"
        assert _translate_key("option") == "alt"
        assert _translate_key("shift") == "shift"

    def test_function_keys(self):
        for i in range(1, 13):
            assert _translate_key(f"f{i}") == f"f{i}"

    def test_unknown_key_passthrough(self):
        """Unknown keys should pass through unchanged."""
        assert _translate_key("a") == "a"
        assert _translate_key("z") == "z"


# ---------------------------------------------------------------------------
# ScreenToolProvider tests
# ---------------------------------------------------------------------------

class TestScreenToolProvider:
    """Tests for the ScreenToolProvider dispatch."""

    @pytest.mark.asyncio
    async def test_provider_dispatches_screenshot(self, provider, png_bytes):
        """Provider should route 'screenshot' to the screenshot tool."""
        with patch("mac_screen_agent.tools._take_screenshot_quartz", side_effect=ImportError):
            with patch("mac_screen_agent.tools._take_screenshot_screencapture", return_value=png_bytes):
                result = await provider.execute_tool("screenshot", "call-1", {})

        assert not result.is_error

    @pytest.mark.asyncio
    async def test_provider_dispatches_mouse_move(self, provider):
        """Provider should route 'mouse_move' to the mouse_move tool."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success):
            result = await provider.execute_tool("mouse_move", "call-1", {"x": 10, "y": 20})

        assert not result.is_error

    @pytest.mark.asyncio
    async def test_provider_dispatches_mouse_click(self, provider):
        """Provider should route 'mouse_click' to the mouse_click tool."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success):
            result = await provider.execute_tool("mouse_click", "call-1", {"x": 10, "y": 20})

        assert not result.is_error

    @pytest.mark.asyncio
    async def test_provider_dispatches_key_type(self, provider):
        """Provider should route 'key_type' to the key_type tool."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success):
            result = await provider.execute_tool("key_type", "call-1", {"text": "hi"})

        assert not result.is_error

    @pytest.mark.asyncio
    async def test_provider_dispatches_key_press(self, provider):
        """Provider should route 'key_press' to the key_press tool."""
        with patch("subprocess.run", side_effect=_mock_cliclick_success):
            result = await provider.execute_tool("key_press", "call-1", {"keys": "Return"})

        assert not result.is_error

    @pytest.mark.asyncio
    async def test_provider_unknown_tool(self, provider):
        """Provider should return error for unknown tools."""
        result = await provider.execute_tool("unknown_tool", "call-1", {})
        assert result.is_error
        assert "Unknown tool" in result.content

    @pytest.mark.asyncio
    async def test_provider_empty_definitions(self, provider):
        """Provider should return empty tool definitions (they come from YAML)."""
        assert provider.get_tool_definitions() == []

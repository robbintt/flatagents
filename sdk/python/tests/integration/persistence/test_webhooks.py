"""
Integration tests for WebhookHooks distributed hook dispatch.

Uses a mock HTTP server to verify events are sent correctly.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from flatagents.flatmachine import FlatMachine
from flatagents.hooks import WebhookHooks, MachineHooks


class TestWebhookHooks:
    """Test WebhookHooks dispatch functionality."""

    @pytest.mark.asyncio
    async def test_webhook_sends_machine_start(self):
        """WebhookHooks sends machine_start event."""
        with patch('flatagents.hooks.httpx') as mock_httpx:
            # Setup mock
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"context": {"injected": "value"}}
            mock_response.raise_for_status = MagicMock()
            
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_httpx.AsyncClient.return_value = mock_client
            
            hooks = WebhookHooks(endpoint="http://test.local/hooks")
            result = await hooks.on_machine_start({"original": "context"})
            
            # Verify POST was called
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert "http://test.local/hooks" in str(call_kwargs)
            
            # Verify context was modified by webhook response
            assert result.get("injected") == "value"

    @pytest.mark.asyncio
    async def test_webhook_graceful_degradation(self):
        """WebhookHooks returns original value when webhook fails."""
        with patch('flatagents.hooks.httpx') as mock_httpx:
            # Setup mock to raise exception
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Network error")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_httpx.AsyncClient.return_value = mock_client
            
            hooks = WebhookHooks(endpoint="http://test.local/hooks")
            original_context = {"key": "value"}
            result = await hooks.on_machine_start(original_context)
            
            # Should return original context on failure
            assert result == original_context

    @pytest.mark.asyncio
    async def test_webhook_all_events(self):
        """WebhookHooks implements all hook methods."""
        hooks = WebhookHooks(endpoint="http://test.local/hooks")
        
        # Verify all methods exist and are async
        assert asyncio.iscoroutinefunction(hooks.on_machine_start)
        assert asyncio.iscoroutinefunction(hooks.on_machine_end)
        assert asyncio.iscoroutinefunction(hooks.on_state_enter)
        assert asyncio.iscoroutinefunction(hooks.on_state_exit)
        assert asyncio.iscoroutinefunction(hooks.on_transition)
        assert asyncio.iscoroutinefunction(hooks.on_error)
        assert asyncio.iscoroutinefunction(hooks.on_action)

    @pytest.mark.asyncio
    async def test_webhook_transition_override(self):
        """WebhookHooks can override transition target."""
        with patch('flatagents.hooks.httpx') as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"to_state": "override_state"}
            mock_response.raise_for_status = MagicMock()
            
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_httpx.AsyncClient.return_value = mock_client
            
            hooks = WebhookHooks(endpoint="http://test.local/hooks")
            result = await hooks.on_transition("from", "original_to", {})
            
            assert result == "override_state"

    @pytest.mark.asyncio 
    async def test_webhook_error_recovery(self):
        """WebhookHooks can specify recovery state on error."""
        with patch('flatagents.hooks.httpx') as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"recovery_state": "error_handler"}
            mock_response.raise_for_status = MagicMock()
            
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_httpx.AsyncClient.return_value = mock_client
            
            hooks = WebhookHooks(endpoint="http://test.local/hooks")
            result = await hooks.on_error("failing_state", Exception("test"), {})
            
            assert result == "error_handler"

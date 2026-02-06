"""
Unit tests for flatmachines AgentResult and rate limit helpers.

Tests the integration between flatagents metrics and flatmachines orchestration.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from flatmachines import (
    AgentResult,
    build_rate_limit_windows,
    build_rate_limit_state,
    coerce_agent_result,
)


# =============================================================================
# AgentResult Tests
# =============================================================================

class TestAgentResult:
    """Tests for the enhanced AgentResult dataclass."""
    
    def test_default_values(self):
        """AgentResult should have None defaults for new fields."""
        result = AgentResult()
        assert result.output is None
        assert result.content is None
        assert result.finish_reason is None
        assert result.error is None
        assert result.rate_limit is None
        assert result.provider_data is None
    
    def test_success_property_true(self):
        """success should be True when error is None."""
        result = AgentResult(content="Hello")
        assert result.success is True
    
    def test_success_property_false(self):
        """success should be False when error is set."""
        result = AgentResult(error={"code": "rate_limit", "message": "Too many requests"})
        assert result.success is False
    
    def test_full_result(self):
        """AgentResult should accept all new fields."""
        result = AgentResult(
            output={"greeting": "Hello"},
            content="Hello",
            usage={
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 10,
            },
            cost={"input": 0.001, "output": 0.002, "total": 0.003},
            finish_reason="stop",
            error=None,
            rate_limit={
                "limited": False,
                "retry_after": None,
                "windows": [],
            },
            provider_data={
                "provider": "openai",
                "model": "gpt-4",
                "raw_headers": {"x-request-id": "abc123"},
            },
        )
        
        assert result.success is True
        assert result.finish_reason == "stop"
        assert result.usage["cache_read_tokens"] == 10
        assert result.provider_data["provider"] == "openai"
    
    def test_error_result(self):
        """AgentResult should handle error case properly."""
        result = AgentResult(
            error={
                "code": "rate_limit",
                "type": "RateLimitError",
                "message": "Too many requests",
                "status_code": 429,
                "retryable": True,
            },
            rate_limit={
                "limited": True,
                "retry_after": 60,
                "windows": [
                    {
                        "name": "requests_per_minute",
                        "resource": "requests",
                        "remaining": 0,
                        "limit": 60,
                    }
                ],
            },
            finish_reason="error",
        )
        
        assert result.success is False
        assert result.error["code"] == "rate_limit"
        assert result.error["retryable"] is True
        assert result.rate_limit["limited"] is True
        assert result.rate_limit["retry_after"] == 60
    
    def test_output_payload(self):
        """output_payload should return output or content wrapper."""
        # With output
        result = AgentResult(output={"key": "value"})
        assert result.output_payload() == {"key": "value"}
        
        # With content only
        result = AgentResult(content="Hello")
        assert result.output_payload() == {"content": "Hello"}
        
        # Empty
        result = AgentResult()
        assert result.output_payload() == {}


# =============================================================================
# coerce_agent_result Tests
# =============================================================================

class TestCoerceAgentResult:
    """Tests for coerce_agent_result function."""
    
    def test_already_agent_result(self):
        """Should return AgentResult unchanged."""
        original = AgentResult(content="Hello")
        result = coerce_agent_result(original)
        assert result is original
    
    def test_dict_with_known_fields(self):
        """Should convert dict with known fields to AgentResult."""
        d = {
            "output": {"key": "value"},
            "content": "Hello",
            "finish_reason": "stop",
            "error": None,
            "rate_limit": {"limited": False},
            "provider_data": {"provider": "test"},
        }
        result = coerce_agent_result(d)
        
        assert isinstance(result, AgentResult)
        assert result.output == {"key": "value"}
        assert result.finish_reason == "stop"
        assert result.rate_limit == {"limited": False}
    
    def test_dict_without_known_fields(self):
        """Should treat dict without known fields as output."""
        d = {"custom_key": "custom_value"}
        result = coerce_agent_result(d)
        
        assert isinstance(result, AgentResult)
        assert result.output == d
        assert result.raw == d
    
    def test_none_input(self):
        """Should return empty AgentResult for None."""
        result = coerce_agent_result(None)
        assert isinstance(result, AgentResult)
        assert result.output is None
    
    def test_string_input(self):
        """Should wrap string as content."""
        result = coerce_agent_result("Hello world")
        assert isinstance(result, AgentResult)
        assert result.content == "Hello world"


# =============================================================================
# build_rate_limit_windows Tests
# =============================================================================

class TestBuildRateLimitWindows:
    """Tests for build_rate_limit_windows function."""
    
    def test_empty_headers(self):
        """Should return empty list for empty headers."""
        windows = build_rate_limit_windows({})
        assert windows == []
    
    def test_cerebras_headers(self):
        """Should parse Cerebras time-bucketed headers."""
        headers = {
            "x-ratelimit-remaining-requests-minute": "10",
            "x-ratelimit-remaining-requests-hour": "100",
            "x-ratelimit-remaining-requests-day": "1000",
            "x-ratelimit-remaining-tokens-minute": "5000",
            "x-ratelimit-remaining-tokens-day": "500000",
            "x-ratelimit-limit-requests-minute": "60",
            "x-ratelimit-limit-tokens-day": "1000000",
        }
        windows = build_rate_limit_windows(headers)
        
        # Should have windows for each bucket with data
        names = [w["name"] for w in windows]
        assert "requests_per_minute" in names
        assert "requests_per_hour" in names
        assert "requests_per_day" in names
        assert "tokens_per_minute" in names
        assert "tokens_per_day" in names
        
        # Check values
        minute_req = next(w for w in windows if w["name"] == "requests_per_minute")
        assert minute_req["remaining"] == 10
        assert minute_req["limit"] == 60
        assert minute_req["resource"] == "requests"
        assert minute_req["resets_in"] == 60
    
    def test_openai_headers(self):
        """Should parse OpenAI-style headers."""
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-remaining-tokens": "50000",
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-reset-requests": "6m30s",
        }
        windows = build_rate_limit_windows(headers)
        
        assert len(windows) == 2
        
        req_window = next(w for w in windows if w["resource"] == "requests")
        assert req_window["remaining"] == 100
        assert req_window["limit"] == 1000
        assert req_window["resets_in"] == 390  # 6*60 + 30
    
    def test_anthropic_headers(self):
        """Should parse Anthropic-style headers."""
        headers = {
            "anthropic-ratelimit-requests-remaining": "100",
            "anthropic-ratelimit-requests-limit": "1000",
            "anthropic-ratelimit-tokens-remaining": "50000",
            "anthropic-ratelimit-tokens-limit": "100000",
        }
        windows = build_rate_limit_windows(headers)
        
        assert len(windows) == 2
        
        req_window = next(w for w in windows if w["resource"] == "requests")
        assert req_window["remaining"] == 100
        assert req_window["limit"] == 1000
    
    def test_duration_parsing(self):
        """Should parse various duration formats."""
        # Minutes and seconds (need remaining/limit for window to be created)
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-reset-requests": "6m30s",
        }
        windows = build_rate_limit_windows(headers)
        assert len(windows) > 0
        req_window = next(w for w in windows if w["resource"] == "requests")
        assert req_window["resets_in"] == 390
        
        # Hours
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-reset-requests": "1h",
        }
        windows = build_rate_limit_windows(headers)
        req_window = next(w for w in windows if w["resource"] == "requests")
        assert req_window["resets_in"] == 3600
        
        # Complex
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-reset-requests": "1h30m45s",
        }
        windows = build_rate_limit_windows(headers)
        req_window = next(w for w in windows if w["resource"] == "requests")
        assert req_window["resets_in"] == 5445


# =============================================================================
# build_rate_limit_state Tests
# =============================================================================

class TestBuildRateLimitState:
    """Tests for build_rate_limit_state function."""
    
    def test_empty_headers(self):
        """Should return non-limited state for empty headers."""
        state = build_rate_limit_state({})
        assert state["limited"] is False
        assert "retry_after" not in state or state["retry_after"] is None
    
    def test_limited_state(self):
        """Should detect limited state when remaining is 0."""
        headers = {
            "x-ratelimit-remaining-requests-minute": "0",
            "x-ratelimit-limit-requests-minute": "60",
        }
        state = build_rate_limit_state(headers)
        
        assert state["limited"] is True
        assert "windows" in state
        assert len(state["windows"]) > 0
    
    def test_retry_after_from_headers(self):
        """Should extract retry_after from headers."""
        headers = {
            "retry-after": "60",
            "x-ratelimit-remaining-requests": "0",
        }
        state = build_rate_limit_state(headers)
        
        assert state["retry_after"] == 60
    
    def test_retry_after_override(self):
        """Should use provided retry_after over headers."""
        headers = {
            "retry-after": "60",
        }
        state = build_rate_limit_state(headers, retry_after=120)
        
        assert state["retry_after"] == 120
    
    def test_not_limited_with_remaining(self):
        """Should not be limited when remaining > 0."""
        headers = {
            "x-ratelimit-remaining-requests-minute": "10",
            "x-ratelimit-remaining-tokens-minute": "5000",
        }
        state = build_rate_limit_state(headers)
        
        assert state["limited"] is False


# =============================================================================
# FlatAgentAdapter Integration Tests
# =============================================================================

class TestFlatAgentAdapterMapping:
    """Tests for FlatAgentAdapter mapping logic."""
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock FlatAgent."""
        agent = MagicMock()
        agent.total_api_calls = 0
        agent.total_cost = 0.0
        agent.provider = "cerebras"
        agent.model = "llama-4-scout-17b"
        agent.metadata = {}
        return agent
    
    @pytest.fixture
    def mock_success_response(self):
        """Create a mock successful AgentResponse."""
        from flatagents import UsageInfo, CostInfo, RateLimitInfo, FinishReason
        
        response = MagicMock()
        response.success = True
        response.output = {"greeting": "Hello"}
        response.content = "Hello"
        response.error = None
        response.finish_reason = FinishReason.STOP
        response.usage = MagicMock()
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        response.usage.total_tokens = 150
        response.usage.cache_read_tokens = 10
        response.usage.cache_write_tokens = 5
        response.usage.cost = MagicMock()
        response.usage.cost.input = 0.001
        response.usage.cost.output = 0.002
        response.usage.cost.cache_read = 0.0001
        response.usage.cost.cache_write = 0.0002
        response.usage.cost.total = 0.0033
        response.rate_limit = MagicMock()
        response.rate_limit.raw_headers = {
            "x-ratelimit-remaining-requests-minute": "10",
        }
        response.rate_limit.retry_after = None
        response.rate_limit.remaining_requests = 10
        response.rate_limit.remaining_tokens = 5000
        response.rate_limit.limit_requests = 60
        response.rate_limit.limit_tokens = 10000
        response.rate_limit.is_limited.return_value = False
        return response
    
    @pytest.fixture
    def mock_error_response(self):
        """Create a mock error AgentResponse."""
        from flatagents import FinishReason
        
        response = MagicMock()
        response.success = False
        response.output = None
        response.content = None
        response.finish_reason = FinishReason.ERROR
        response.error = MagicMock()
        response.error.error_type = "RateLimitError"
        response.error.message = "Too many requests"
        response.error.status_code = 429
        response.error.retryable = True
        response.usage = None
        response.rate_limit = MagicMock()
        response.rate_limit.raw_headers = {
            "x-ratelimit-remaining-requests-minute": "0",
            "retry-after": "60",
        }
        response.rate_limit.retry_after = 60
        response.rate_limit.remaining_requests = 0
        response.rate_limit.remaining_tokens = None
        response.rate_limit.limit_requests = 60
        response.rate_limit.limit_tokens = None
        response.rate_limit.is_limited.return_value = True
        return response
    
    @pytest.mark.asyncio
    async def test_success_mapping(self, mock_agent, mock_success_response):
        """Should map successful response to AgentResult."""
        from flatmachines.adapters.flatagent import FlatAgentExecutor
        
        mock_agent.call = AsyncMock(return_value=mock_success_response)
        mock_agent.total_api_calls = 1
        mock_agent.total_cost = 0.0033
        
        executor = FlatAgentExecutor(mock_agent)
        result = await executor.execute({"prompt": "Hello"})
        
        assert result.success is True
        assert result.output == {"greeting": "Hello"}
        assert result.finish_reason == "stop"
        assert result.usage["input_tokens"] == 100
        assert result.usage["cache_read_tokens"] == 10
        assert result.cost["total"] == 0.0033
        assert result.rate_limit["limited"] is False
        assert result.provider_data["provider"] == "cerebras"
        assert "raw_headers" in result.provider_data
    
    @pytest.mark.asyncio
    async def test_error_mapping(self, mock_agent, mock_error_response):
        """Should map error response to AgentResult."""
        from flatmachines.adapters.flatagent import FlatAgentExecutor
        
        mock_agent.call = AsyncMock(return_value=mock_error_response)
        
        executor = FlatAgentExecutor(mock_agent)
        result = await executor.execute({"prompt": "Hello"})
        
        assert result.success is False
        assert result.error is not None
        assert result.error["code"] == "rate_limit"
        assert result.error["type"] == "RateLimitError"
        assert result.error["status_code"] == 429
        assert result.error["retryable"] is True
        assert result.rate_limit["limited"] is True
        assert result.finish_reason == "error"

"""
Unit tests for metrics dataclasses.

Tests: CostInfo, UsageInfo, RateLimitInfo, ErrorInfo, FinishReason, AgentResponse
"""

import pytest
import time
from dataclasses import asdict

from flatagents import (
    CostInfo,
    UsageInfo,
    RateLimitInfo,
    ErrorInfo,
    FinishReason,
    AgentResponse,
    ToolCall,
)


# =============================================================================
# CostInfo Tests
# =============================================================================

class TestCostInfo:
    """Tests for CostInfo dataclass."""
    
    def test_default_values(self):
        """CostInfo should have zero defaults."""
        cost = CostInfo()
        assert cost.input == 0.0
        assert cost.output == 0.0
        assert cost.cache_read == 0.0
        assert cost.cache_write == 0.0
        assert cost.total == 0.0
    
    def test_custom_values(self):
        """CostInfo should accept custom values."""
        cost = CostInfo(
            input=0.001,
            output=0.002,
            cache_read=0.0001,
            cache_write=0.0002,
            total=0.0033,
        )
        assert cost.input == 0.001
        assert cost.output == 0.002
        assert cost.cache_read == 0.0001
        assert cost.cache_write == 0.0002
        assert cost.total == 0.0033
    
    def test_asdict(self):
        """CostInfo should be convertible to dict."""
        cost = CostInfo(input=0.01, output=0.02, total=0.03)
        d = asdict(cost)
        assert d["input"] == 0.01
        assert d["output"] == 0.02
        assert d["total"] == 0.03


# =============================================================================
# UsageInfo Tests
# =============================================================================

class TestUsageInfo:
    """Tests for UsageInfo dataclass."""
    
    def test_default_values(self):
        """UsageInfo should have zero defaults."""
        usage = UsageInfo()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0
        assert usage.cost is None
    
    def test_basic_token_counts(self):
        """UsageInfo should track basic token counts."""
        usage = UsageInfo(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150
    
    def test_cache_tokens(self):
        """UsageInfo should track cache tokens."""
        usage = UsageInfo(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cache_read_tokens=30,
            cache_write_tokens=20,
        )
        assert usage.cache_read_tokens == 30
        assert usage.cache_write_tokens == 20
    
    def test_with_cost_info(self):
        """UsageInfo should accept CostInfo."""
        cost = CostInfo(input=0.001, output=0.002, total=0.003)
        usage = UsageInfo(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost=cost,
        )
        assert usage.cost is not None
        assert usage.cost.total == 0.003
    
    def test_estimated_cost_property_with_cost(self):
        """estimated_cost property should return cost.total when cost is set."""
        cost = CostInfo(total=0.005)
        usage = UsageInfo(cost=cost)
        assert usage.estimated_cost == 0.005
    
    def test_estimated_cost_property_without_cost(self):
        """estimated_cost property should return 0.0 when cost is None."""
        usage = UsageInfo()
        assert usage.estimated_cost == 0.0
    
    def test_backwards_compatibility(self):
        """UsageInfo should be backwards compatible with old code."""
        # Old code might just use input/output tokens
        usage = UsageInfo(input_tokens=100, output_tokens=50, total_tokens=150)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        # New fields should have defaults
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0


# =============================================================================
# RateLimitInfo Tests
# =============================================================================

class TestRateLimitInfo:
    """Tests for RateLimitInfo dataclass."""
    
    def test_default_values(self):
        """RateLimitInfo should have None/empty defaults."""
        rl = RateLimitInfo()
        assert rl.remaining_requests is None
        assert rl.remaining_tokens is None
        assert rl.limit_requests is None
        assert rl.limit_tokens is None
        assert rl.reset_at is None
        assert rl.retry_after is None
        assert rl.raw_headers == {}
    
    def test_normalized_fields(self):
        """RateLimitInfo should accept normalized fields."""
        rl = RateLimitInfo(
            remaining_requests=100,
            remaining_tokens=50000,
            limit_requests=1000,
            limit_tokens=100000,
        )
        assert rl.remaining_requests == 100
        assert rl.remaining_tokens == 50000
        assert rl.limit_requests == 1000
        assert rl.limit_tokens == 100000
    
    def test_timing_fields(self):
        """RateLimitInfo should accept timing fields."""
        now = time.time()
        rl = RateLimitInfo(
            reset_at=now + 60,
            retry_after=30,
        )
        assert rl.reset_at == now + 60
        assert rl.retry_after == 30
    
    def test_raw_headers(self):
        """RateLimitInfo should store raw headers."""
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-custom-header": "value",
        }
        rl = RateLimitInfo(raw_headers=headers)
        assert rl.raw_headers == headers
        assert "x-custom-header" in rl.raw_headers
    
    def test_is_limited_false_when_none(self):
        """is_limited should return False when values are None."""
        rl = RateLimitInfo()
        assert rl.is_limited() is False
    
    def test_is_limited_false_when_remaining(self):
        """is_limited should return False when remaining > 0."""
        rl = RateLimitInfo(remaining_requests=5, remaining_tokens=1000)
        assert rl.is_limited() is False
    
    def test_is_limited_true_when_requests_zero(self):
        """is_limited should return True when remaining_requests == 0."""
        rl = RateLimitInfo(remaining_requests=0, remaining_tokens=1000)
        assert rl.is_limited() is True
    
    def test_is_limited_true_when_tokens_zero(self):
        """is_limited should return True when remaining_tokens == 0."""
        rl = RateLimitInfo(remaining_requests=5, remaining_tokens=0)
        assert rl.is_limited() is True
    
    def test_get_retry_delay_from_retry_after(self):
        """get_retry_delay should return retry_after when set."""
        rl = RateLimitInfo(retry_after=60)
        assert rl.get_retry_delay() == 60
    
    def test_get_retry_delay_from_reset_at(self):
        """get_retry_delay should calculate from reset_at when retry_after is None."""
        future = time.time() + 30
        rl = RateLimitInfo(reset_at=future)
        delay = rl.get_retry_delay()
        assert delay is not None
        assert 28 <= delay <= 31  # Allow small timing variance
    
    def test_get_retry_delay_none_when_no_timing(self):
        """get_retry_delay should return None when no timing info."""
        rl = RateLimitInfo()
        assert rl.get_retry_delay() is None
    
    def test_get_retry_delay_prefers_retry_after(self):
        """get_retry_delay should prefer retry_after over reset_at."""
        future = time.time() + 300
        rl = RateLimitInfo(retry_after=60, reset_at=future)
        assert rl.get_retry_delay() == 60
    
    def test_get_retry_delay_handles_past_reset(self):
        """get_retry_delay should return 0 for past reset times."""
        past = time.time() - 60
        rl = RateLimitInfo(reset_at=past)
        delay = rl.get_retry_delay()
        assert delay == 0


# =============================================================================
# ErrorInfo Tests
# =============================================================================

class TestErrorInfo:
    """Tests for ErrorInfo dataclass."""
    
    def test_required_fields(self):
        """ErrorInfo requires error_type and message."""
        error = ErrorInfo(error_type="RateLimitError", message="Too many requests")
        assert error.error_type == "RateLimitError"
        assert error.message == "Too many requests"
    
    def test_default_values(self):
        """ErrorInfo should have sensible defaults."""
        error = ErrorInfo(error_type="Error", message="test")
        assert error.status_code is None
        assert error.retryable is False
    
    def test_with_status_code(self):
        """ErrorInfo should accept status_code."""
        error = ErrorInfo(
            error_type="RateLimitError",
            message="Too many requests",
            status_code=429,
        )
        assert error.status_code == 429
    
    def test_retryable_flag(self):
        """ErrorInfo should track retryable status."""
        error = ErrorInfo(
            error_type="RateLimitError",
            message="Too many requests",
            status_code=429,
            retryable=True,
        )
        assert error.retryable is True


# =============================================================================
# FinishReason Tests
# =============================================================================

class TestFinishReason:
    """Tests for FinishReason enum."""
    
    def test_all_values_exist(self):
        """FinishReason should have all expected values."""
        assert FinishReason.STOP.value == "stop"
        assert FinishReason.LENGTH.value == "length"
        assert FinishReason.TOOL_USE.value == "tool_use"
        assert FinishReason.ERROR.value == "error"
        assert FinishReason.ABORTED.value == "aborted"
        assert FinishReason.CONTENT_FILTER.value == "content_filter"
    
    def test_is_string_enum(self):
        """FinishReason should be a string enum."""
        assert isinstance(FinishReason.STOP, str)
        assert FinishReason.STOP == "stop"
    
    def test_comparison(self):
        """FinishReason should compare with strings."""
        assert FinishReason.STOP == "stop"
        assert FinishReason.LENGTH == "length"
    
    def test_from_string(self):
        """FinishReason should be constructible from string."""
        reason = FinishReason("stop")
        assert reason == FinishReason.STOP


# =============================================================================
# AgentResponse Tests
# =============================================================================

class TestAgentResponse:
    """Tests for AgentResponse dataclass."""
    
    def test_default_values(self):
        """AgentResponse should have None defaults."""
        response = AgentResponse()
        assert response.content is None
        assert response.output is None
        assert response.tool_calls is None
        assert response.raw_response is None
        assert response.usage is None
        assert response.rate_limit is None
        assert response.finish_reason is None
        assert response.error is None
    
    def test_success_property_true(self):
        """success should be True when error is None."""
        response = AgentResponse(content="Hello")
        assert response.success is True
    
    def test_success_property_false(self):
        """success should be False when error is set."""
        error = ErrorInfo(error_type="Error", message="test")
        response = AgentResponse(error=error)
        assert response.success is False
    
    def test_content_response(self):
        """AgentResponse should store content."""
        response = AgentResponse(content="Hello, world!")
        assert response.content == "Hello, world!"
        assert response.success is True
    
    def test_output_response(self):
        """AgentResponse should store parsed output."""
        response = AgentResponse(
            content='{"greeting": "Hello"}',
            output={"greeting": "Hello"},
        )
        assert response.output == {"greeting": "Hello"}
    
    def test_tool_calls_response(self):
        """AgentResponse should store tool calls."""
        tool_call = ToolCall(
            id="call_123",
            server="filesystem",
            tool="read_file",
            arguments={"path": "/test.txt"},
        )
        response = AgentResponse(tool_calls=[tool_call])
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool == "read_file"
    
    def test_with_usage(self):
        """AgentResponse should include usage info."""
        usage = UsageInfo(input_tokens=100, output_tokens=50, total_tokens=150)
        response = AgentResponse(content="Hello", usage=usage)
        assert response.usage is not None
        assert response.usage.input_tokens == 100
    
    def test_with_rate_limit(self):
        """AgentResponse should include rate limit info."""
        rate_limit = RateLimitInfo(remaining_requests=5, raw_headers={})
        response = AgentResponse(content="Hello", rate_limit=rate_limit)
        assert response.rate_limit is not None
        assert response.rate_limit.remaining_requests == 5
    
    def test_with_finish_reason(self):
        """AgentResponse should include finish reason."""
        response = AgentResponse(
            content="Hello",
            finish_reason=FinishReason.STOP,
        )
        assert response.finish_reason == FinishReason.STOP
    
    def test_error_response(self):
        """AgentResponse should handle error case."""
        error = ErrorInfo(
            error_type="RateLimitError",
            message="Too many requests",
            status_code=429,
            retryable=True,
        )
        rate_limit = RateLimitInfo(remaining_requests=0, retry_after=60, raw_headers={})
        response = AgentResponse(
            error=error,
            rate_limit=rate_limit,
            finish_reason=FinishReason.ERROR,
        )
        assert response.success is False
        assert response.error.error_type == "RateLimitError"
        assert response.error.retryable is True
        assert response.rate_limit.retry_after == 60
        assert response.finish_reason == FinishReason.ERROR
    
    def test_full_success_response(self):
        """AgentResponse should handle full success case."""
        cost = CostInfo(input=0.001, output=0.002, total=0.003)
        usage = UsageInfo(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cache_read_tokens=10,
            cost=cost,
        )
        rate_limit = RateLimitInfo(
            remaining_requests=99,
            remaining_tokens=99000,
            raw_headers={"x-test": "value"},
        )
        response = AgentResponse(
            content="Hello, world!",
            output={"greeting": "Hello, world!"},
            usage=usage,
            rate_limit=rate_limit,
            finish_reason=FinishReason.STOP,
        )
        
        assert response.success is True
        assert response.content == "Hello, world!"
        assert response.output["greeting"] == "Hello, world!"
        assert response.usage.input_tokens == 100
        assert response.usage.cache_read_tokens == 10
        assert response.usage.estimated_cost == 0.003
        assert response.rate_limit.remaining_requests == 99
        assert response.finish_reason == FinishReason.STOP

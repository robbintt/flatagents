"""
Unit tests for FlatAgent metric helper methods.

Tests: _extract_cache_tokens, _calculate_cost, _extract_finish_reason
"""

import pytest
from unittest.mock import MagicMock, patch

from flatagents import FlatAgent, FinishReason, CostInfo


# =============================================================================
# Test Helper Class
# =============================================================================

class MockAgent:
    """
    A mock agent that has the same helper methods as FlatAgent.
    
    We test the methods directly since they don't depend on agent state.
    """
    
    def __init__(self, backend="litellm"):
        self._backend = backend
    
    # Copy the actual methods from FlatAgent
    _extract_cache_tokens = FlatAgent._extract_cache_tokens
    _calculate_cost = FlatAgent._calculate_cost
    _extract_finish_reason = FlatAgent._extract_finish_reason
    _record_rate_limit_metrics = FlatAgent._record_rate_limit_metrics


@pytest.fixture
def agent():
    """Create a mock agent for testing helper methods."""
    return MockAgent(backend="litellm")


# =============================================================================
# _extract_cache_tokens Tests
# =============================================================================

class TestExtractCacheTokens:
    """Tests for FlatAgent._extract_cache_tokens method."""
    
    def test_none_usage(self, agent):
        """Should return (0, 0) for None usage."""
        cache_read, cache_write = agent._extract_cache_tokens(None)
        assert cache_read == 0
        assert cache_write == 0
    
    def test_anthropic_style_cache_tokens(self, agent):
        """Should extract Anthropic-style cache tokens."""
        usage = MagicMock()
        usage.cache_read_input_tokens = 1000
        usage.cache_creation_input_tokens = 500
        
        cache_read, cache_write = agent._extract_cache_tokens(usage)
        assert cache_read == 1000
        assert cache_write == 500
    
    def test_openai_style_cache_tokens(self, agent):
        """Should extract OpenAI-style cached_tokens from prompt_tokens_details."""
        usage = MagicMock()
        usage.cache_read_input_tokens = None
        usage.cache_creation_input_tokens = None
        
        # OpenAI style
        details = MagicMock()
        details.cached_tokens = 750
        usage.prompt_tokens_details = details
        
        cache_read, cache_write = agent._extract_cache_tokens(usage)
        assert cache_read == 750
        assert cache_write == 0
    
    def test_no_cache_tokens(self, agent):
        """Should return (0, 0) when no cache tokens present."""
        usage = MagicMock()
        usage.cache_read_input_tokens = None
        usage.cache_creation_input_tokens = None
        usage.prompt_tokens_details = None
        
        cache_read, cache_write = agent._extract_cache_tokens(usage)
        assert cache_read == 0
        assert cache_write == 0
    
    def test_zero_cache_tokens(self, agent):
        """Should handle explicit zero values."""
        usage = MagicMock()
        usage.cache_read_input_tokens = 0
        usage.cache_creation_input_tokens = 0
        usage.prompt_tokens_details = None  # Prevent MagicMock fallback
        
        cache_read, cache_write = agent._extract_cache_tokens(usage)
        assert cache_read == 0
        assert cache_write == 0
    
    def test_anthropic_takes_precedence(self, agent):
        """Anthropic-style should take precedence over OpenAI-style."""
        usage = MagicMock()
        usage.cache_read_input_tokens = 1000  # Anthropic
        usage.cache_creation_input_tokens = 500
        
        # Also has OpenAI style
        details = MagicMock()
        details.cached_tokens = 750
        usage.prompt_tokens_details = details
        
        cache_read, cache_write = agent._extract_cache_tokens(usage)
        # Should use Anthropic values
        assert cache_read == 1000
        assert cache_write == 500


# =============================================================================
# _calculate_cost Tests
# =============================================================================

class TestCalculateCost:
    """Tests for FlatAgent._calculate_cost method."""
    
    def test_fallback_estimation(self, agent):
        """Should use fallback estimation when litellm cost fails."""
        response = MagicMock()
        
        cost = agent._calculate_cost(
            response=response,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )
        
        assert isinstance(cost, CostInfo)
        assert cost.total > 0
        # Fallback uses rough estimation
        assert cost.input > 0
        assert cost.output > 0
    
    def test_cost_breakdown_proportional(self, agent):
        """Cost breakdown should be proportional to tokens."""
        response = MagicMock()
        
        cost = agent._calculate_cost(
            response=response,
            input_tokens=100,
            output_tokens=100,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )
        
        # With equal tokens, output should cost more (2x in fallback)
        assert cost.output > cost.input
    
    def test_includes_cache_costs(self, agent):
        """Should include cache token costs in total."""
        response = MagicMock()
        
        cost = agent._calculate_cost(
            response=response,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=200,
            cache_write_tokens=100,
        )
        
        assert cost.cache_read >= 0
        assert cost.cache_write >= 0
        # Total should include all components
        expected_total = cost.input + cost.output + cost.cache_read + cost.cache_write
        assert abs(cost.total - expected_total) < 0.0001
    
    def test_litellm_cost_calculation(self, agent):
        """Should use litellm.completion_cost when available."""
        response = MagicMock()
        
        with patch('flatagents.flatagent.litellm') as mock_litellm:
            mock_litellm.completion_cost.return_value = 0.005
            agent._backend = "litellm"
            
            cost = agent._calculate_cost(
                response=response,
                input_tokens=100,
                output_tokens=50,
                cache_read_tokens=0,
                cache_write_tokens=0,
            )
            
            assert cost.total == 0.005
            mock_litellm.completion_cost.assert_called_once()
    
    def test_litellm_cost_with_breakdown(self, agent):
        """Should estimate breakdown when litellm gives total."""
        response = MagicMock()
        
        with patch('flatagents.flatagent.litellm') as mock_litellm:
            mock_litellm.completion_cost.return_value = 0.003
            agent._backend = "litellm"
            
            cost = agent._calculate_cost(
                response=response,
                input_tokens=100,  # 2/3 of total
                output_tokens=50,   # 1/3 of total
                cache_read_tokens=0,
                cache_write_tokens=0,
            )
            
            # Should estimate proportionally
            assert cost.total == 0.003
            assert 0.001 < cost.input < 0.003
            assert 0.0005 < cost.output < 0.002
    
    def test_aisuite_backend_uses_fallback(self, agent):
        """Should use fallback for aisuite backend."""
        response = MagicMock()
        agent._backend = "aisuite"
        
        cost = agent._calculate_cost(
            response=response,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )
        
        # Should use fallback estimation, not litellm
        assert isinstance(cost, CostInfo)
        assert cost.total > 0
    
    def test_handles_litellm_exception(self, agent):
        """Should fall back to estimation when litellm raises."""
        response = MagicMock()
        
        with patch('flatagents.flatagent.litellm') as mock_litellm:
            mock_litellm.completion_cost.side_effect = Exception("Cost calculation failed")
            agent._backend = "litellm"
            
            # Should not raise, should fall back
            cost = agent._calculate_cost(
                response=response,
                input_tokens=100,
                output_tokens=50,
                cache_read_tokens=0,
                cache_write_tokens=0,
            )
            
            assert isinstance(cost, CostInfo)
            assert cost.total > 0
    
    def test_handles_zero_litellm_cost(self, agent):
        """Should fall back when litellm returns zero."""
        response = MagicMock()
        
        with patch('flatagents.flatagent.litellm') as mock_litellm:
            mock_litellm.completion_cost.return_value = 0
            agent._backend = "litellm"
            
            cost = agent._calculate_cost(
                response=response,
                input_tokens=100,
                output_tokens=50,
                cache_read_tokens=0,
                cache_write_tokens=0,
            )
            
            # Should use fallback when litellm returns 0
            assert cost.total > 0


# =============================================================================
# _extract_finish_reason Tests
# =============================================================================

class TestExtractFinishReason:
    """Tests for FlatAgent._extract_finish_reason method."""
    
    def test_none_response(self, agent):
        """Should return None for None response."""
        result = agent._extract_finish_reason(None)
        assert result is None
    
    def test_no_choices(self, agent):
        """Should return None when no choices."""
        response = MagicMock()
        response.choices = []
        
        result = agent._extract_finish_reason(response)
        assert result is None
    
    def test_no_finish_reason(self, agent):
        """Should return None when finish_reason not set."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason=None)]
        
        result = agent._extract_finish_reason(response)
        assert result is None
    
    def test_stop_reason(self, agent):
        """Should map 'stop' to FinishReason.STOP."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="stop")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.STOP
    
    def test_end_turn_reason(self, agent):
        """Should map 'end_turn' (Anthropic) to FinishReason.STOP."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="end_turn")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.STOP
    
    def test_length_reason(self, agent):
        """Should map 'length' to FinishReason.LENGTH."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="length")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.LENGTH
    
    def test_max_tokens_reason(self, agent):
        """Should map 'max_tokens' to FinishReason.LENGTH."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="max_tokens")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.LENGTH
    
    def test_tool_calls_reason(self, agent):
        """Should map 'tool_calls' to FinishReason.TOOL_USE."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="tool_calls")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.TOOL_USE
    
    def test_tool_use_reason(self, agent):
        """Should map 'tool_use' (Anthropic) to FinishReason.TOOL_USE."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="tool_use")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.TOOL_USE
    
    def test_function_call_reason(self, agent):
        """Should map 'function_call' to FinishReason.TOOL_USE."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="function_call")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.TOOL_USE
    
    def test_content_filter_reason(self, agent):
        """Should map 'content_filter' to FinishReason.CONTENT_FILTER."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="content_filter")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.CONTENT_FILTER
    
    def test_case_insensitive(self, agent):
        """Should handle case-insensitive finish reasons."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="STOP")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.STOP
    
    def test_unknown_reason_defaults_to_stop(self, agent):
        """Should default unknown reasons to STOP."""
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="unknown_reason")]
        
        result = agent._extract_finish_reason(response)
        assert result == FinishReason.STOP


# =============================================================================
# _record_rate_limit_metrics Tests
# =============================================================================

class TestRecordRateLimitMetrics:
    """Tests for FlatAgent._record_rate_limit_metrics method."""
    
    def test_records_normalized_fields(self, agent):
        """Should record normalized rate limit fields."""
        from flatagents import RateLimitInfo
        from flatagents.monitoring import AgentMonitor
        
        monitor = MagicMock(spec=AgentMonitor)
        monitor.metrics = {}
        
        rate_limit = RateLimitInfo(
            remaining_requests=100,
            remaining_tokens=50000,
            limit_requests=1000,
            limit_tokens=100000,
            raw_headers={},
        )
        
        agent._record_rate_limit_metrics(monitor, rate_limit)
        
        assert monitor.metrics["ratelimit_remaining_requests"] == 100
        assert monitor.metrics["ratelimit_remaining_tokens"] == 50000
        assert monitor.metrics["ratelimit_limit_requests"] == 1000
        assert monitor.metrics["ratelimit_limit_tokens"] == 100000
    
    def test_records_timing_fields(self, agent):
        """Should record timing fields."""
        from flatagents import RateLimitInfo
        from flatagents.monitoring import AgentMonitor
        import time
        
        monitor = MagicMock(spec=AgentMonitor)
        monitor.metrics = {}
        
        reset_time = time.time() + 60
        rate_limit = RateLimitInfo(
            reset_at=reset_time,
            retry_after=30,
            raw_headers={},
        )
        
        agent._record_rate_limit_metrics(monitor, rate_limit)
        
        assert monitor.metrics["ratelimit_reset_at"] == reset_time
        assert monitor.metrics["ratelimit_retry_after"] == 30
    
    def test_skips_none_fields(self, agent):
        """Should not record None fields."""
        from flatagents import RateLimitInfo
        from flatagents.monitoring import AgentMonitor
        
        monitor = MagicMock(spec=AgentMonitor)
        monitor.metrics = {}
        
        rate_limit = RateLimitInfo(
            remaining_requests=100,
            remaining_tokens=None,  # Should not be recorded
            raw_headers={},
        )
        
        agent._record_rate_limit_metrics(monitor, rate_limit)
        
        assert "ratelimit_remaining_requests" in monitor.metrics
        assert "ratelimit_remaining_tokens" not in monitor.metrics
    
    def test_no_longer_records_time_bucketed_fields(self, agent):
        """Should not record Cerebras-specific time-bucketed fields directly."""
        from flatagents import RateLimitInfo
        from flatagents.monitoring import AgentMonitor
        
        monitor = MagicMock(spec=AgentMonitor)
        monitor.metrics = {}
        
        # Time-bucketed fields are now in raw_headers, not direct attributes
        rate_limit = RateLimitInfo(
            remaining_requests=100,
            raw_headers={
                "x-ratelimit-remaining-requests-minute": "10",
            },
        )
        
        agent._record_rate_limit_metrics(monitor, rate_limit)
        
        # Should only have normalized fields
        assert "ratelimit_remaining_requests" in monitor.metrics
        # Should NOT have time-bucketed fields as direct metrics
        assert "ratelimit_remaining_requests_minute" not in monitor.metrics

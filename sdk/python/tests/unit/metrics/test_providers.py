"""
Unit tests for provider-specific rate limit extractors.

Tests: CerebrasRateLimits, AnthropicRateLimits, OpenAIRateLimits
       and their respective extraction functions.
"""

import pytest
from datetime import datetime

from flatagents import (
    CerebrasRateLimits,
    extract_cerebras_rate_limits,
    AnthropicRateLimits,
    extract_anthropic_rate_limits,
    OpenAIRateLimits,
    extract_openai_rate_limits,
)


# =============================================================================
# Cerebras Rate Limits Tests
# =============================================================================

class TestCerebrasRateLimits:
    """Tests for CerebrasRateLimits dataclass."""
    
    def test_default_values(self):
        """Should have None defaults."""
        limits = CerebrasRateLimits()
        assert limits.remaining_requests_minute is None
        assert limits.remaining_requests_hour is None
        assert limits.remaining_requests_day is None
        assert limits.remaining_tokens_minute is None
        assert limits.remaining_tokens_hour is None
        assert limits.remaining_tokens_day is None
    
    def test_all_fields(self):
        """Should accept all time-bucketed fields."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=10,
            remaining_requests_hour=100,
            remaining_requests_day=1000,
            remaining_tokens_minute=5000,
            remaining_tokens_hour=50000,
            remaining_tokens_day=500000,
            limit_requests_minute=60,
            limit_requests_hour=600,
            limit_requests_day=6000,
            limit_tokens_minute=10000,
            limit_tokens_hour=100000,
            limit_tokens_day=1000000,
        )
        assert limits.remaining_requests_minute == 10
        assert limits.remaining_tokens_day == 500000
        assert limits.limit_requests_minute == 60
    
    def test_is_limited_false_when_remaining(self):
        """is_limited should return False when all buckets have remaining."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=10,
            remaining_requests_hour=100,
            remaining_requests_day=1000,
            remaining_tokens_minute=5000,
            remaining_tokens_hour=50000,
            remaining_tokens_day=500000,
        )
        assert limits.is_limited() is False
    
    def test_is_limited_true_when_minute_exhausted(self):
        """is_limited should return True when minute bucket exhausted."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=0,
            remaining_requests_hour=100,
            remaining_requests_day=1000,
        )
        assert limits.is_limited() is True
    
    def test_is_limited_true_when_tokens_exhausted(self):
        """is_limited should return True when tokens exhausted."""
        limits = CerebrasRateLimits(
            remaining_tokens_hour=0,
        )
        assert limits.is_limited() is True
    
    def test_get_most_restrictive_bucket_minute(self):
        """Should identify minute as most restrictive."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=0,
            remaining_requests_hour=100,
        )
        assert limits.get_most_restrictive_bucket() == "minute"
    
    def test_get_most_restrictive_bucket_hour(self):
        """Should identify hour as most restrictive."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=10,
            remaining_tokens_hour=0,
        )
        assert limits.get_most_restrictive_bucket() == "hour"
    
    def test_get_most_restrictive_bucket_day(self):
        """Should identify day as most restrictive."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=10,
            remaining_requests_hour=100,
            remaining_requests_day=0,
        )
        assert limits.get_most_restrictive_bucket() == "day"
    
    def test_get_most_restrictive_bucket_none(self):
        """Should return None when not limited."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=10,
            remaining_requests_hour=100,
        )
        assert limits.get_most_restrictive_bucket() is None
    
    def test_get_suggested_wait_seconds_minute(self):
        """Should suggest 60s for minute bucket."""
        limits = CerebrasRateLimits(remaining_requests_minute=0)
        assert limits.get_suggested_wait_seconds() == 60
    
    def test_get_suggested_wait_seconds_hour(self):
        """Should suggest 3600s for hour bucket."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=10,
            remaining_requests_hour=0,
        )
        assert limits.get_suggested_wait_seconds() == 3600
    
    def test_get_suggested_wait_seconds_day(self):
        """Should suggest 86400s for day bucket."""
        limits = CerebrasRateLimits(
            remaining_requests_minute=10,
            remaining_requests_hour=100,
            remaining_requests_day=0,
        )
        assert limits.get_suggested_wait_seconds() == 86400
    
    def test_get_suggested_wait_seconds_none(self):
        """Should return None when not limited."""
        limits = CerebrasRateLimits()
        assert limits.get_suggested_wait_seconds() is None


class TestExtractCerebrasRateLimits:
    """Tests for extract_cerebras_rate_limits function."""
    
    def test_empty_headers(self):
        """Should return CerebrasRateLimits with None values."""
        result = extract_cerebras_rate_limits({})
        assert isinstance(result, CerebrasRateLimits)
        assert result.remaining_requests_minute is None
    
    def test_all_headers(self):
        """Should extract all Cerebras headers."""
        headers = {
            "x-ratelimit-remaining-requests-minute": "10",
            "x-ratelimit-remaining-requests-hour": "100",
            "x-ratelimit-remaining-requests-day": "1000",
            "x-ratelimit-remaining-tokens-minute": "5000",
            "x-ratelimit-remaining-tokens-hour": "50000",
            "x-ratelimit-remaining-tokens-day": "500000",
            "x-ratelimit-limit-requests-minute": "60",
            "x-ratelimit-limit-requests-hour": "600",
            "x-ratelimit-limit-requests-day": "6000",
            "x-ratelimit-limit-tokens-minute": "10000",
            "x-ratelimit-limit-tokens-hour": "100000",
            "x-ratelimit-limit-tokens-day": "1000000",
        }
        result = extract_cerebras_rate_limits(headers)
        
        assert result.remaining_requests_minute == 10
        assert result.remaining_requests_hour == 100
        assert result.remaining_requests_day == 1000
        assert result.remaining_tokens_minute == 5000
        assert result.remaining_tokens_hour == 50000
        assert result.remaining_tokens_day == 500000
        assert result.limit_requests_minute == 60
        assert result.limit_requests_hour == 600
        assert result.limit_requests_day == 6000
        assert result.limit_tokens_minute == 10000
        assert result.limit_tokens_hour == 100000
        assert result.limit_tokens_day == 1000000
    
    def test_partial_headers(self):
        """Should handle partial headers."""
        headers = {
            "x-ratelimit-remaining-requests-minute": "10",
            "x-ratelimit-remaining-tokens-day": "500000",
        }
        result = extract_cerebras_rate_limits(headers)
        
        assert result.remaining_requests_minute == 10
        assert result.remaining_requests_hour is None
        assert result.remaining_tokens_day == 500000
    
    def test_invalid_values_ignored(self):
        """Should return None for non-integer values."""
        headers = {
            "x-ratelimit-remaining-requests-minute": "not-a-number",
        }
        result = extract_cerebras_rate_limits(headers)
        assert result.remaining_requests_minute is None
    
    def test_integration_with_ratelimitinfo(self):
        """Should work with raw_headers from RateLimitInfo."""
        from flatagents import extract_rate_limit_info
        
        headers = {
            "x-ratelimit-remaining-requests": "100",  # Generic
            "x-ratelimit-remaining-requests-minute": "10",  # Cerebras
            "x-ratelimit-remaining-requests-day": "1000",  # Cerebras
        }
        
        # First extract generic rate limit info
        rate_limit = extract_rate_limit_info(headers)
        assert rate_limit.remaining_requests == 100
        
        # Then extract Cerebras-specific from raw_headers
        cerebras = extract_cerebras_rate_limits(rate_limit.raw_headers)
        assert cerebras.remaining_requests_minute == 10
        assert cerebras.remaining_requests_day == 1000


# =============================================================================
# Anthropic Rate Limits Tests
# =============================================================================

class TestAnthropicRateLimits:
    """Tests for AnthropicRateLimits dataclass."""
    
    def test_default_values(self):
        """Should have None defaults."""
        limits = AnthropicRateLimits()
        assert limits.requests_remaining is None
        assert limits.requests_limit is None
        assert limits.requests_reset is None
        assert limits.tokens_remaining is None
        assert limits.tokens_limit is None
        assert limits.tokens_reset is None
    
    def test_all_fields(self):
        """Should accept all fields."""
        reset_time = datetime(2024, 6, 15, 12, 0, 0)
        limits = AnthropicRateLimits(
            requests_remaining=100,
            requests_limit=1000,
            requests_reset=reset_time,
            tokens_remaining=50000,
            tokens_limit=100000,
            tokens_reset=reset_time,
            input_tokens_remaining=25000,
            input_tokens_limit=50000,
            output_tokens_remaining=25000,
            output_tokens_limit=50000,
        )
        assert limits.requests_remaining == 100
        assert limits.tokens_limit == 100000
        assert limits.requests_reset == reset_time
    
    def test_is_limited_false(self):
        """is_limited should return False when remaining > 0."""
        limits = AnthropicRateLimits(
            requests_remaining=100,
            tokens_remaining=50000,
        )
        assert limits.is_limited() is False
    
    def test_is_limited_true_requests(self):
        """is_limited should return True when requests exhausted."""
        limits = AnthropicRateLimits(requests_remaining=0)
        assert limits.is_limited() is True
    
    def test_is_limited_true_tokens(self):
        """is_limited should return True when tokens exhausted."""
        limits = AnthropicRateLimits(tokens_remaining=0)
        assert limits.is_limited() is True
    
    def test_is_limited_true_input_tokens(self):
        """is_limited should return True when input tokens exhausted."""
        limits = AnthropicRateLimits(input_tokens_remaining=0)
        assert limits.is_limited() is True
    
    def test_is_limited_true_output_tokens(self):
        """is_limited should return True when output tokens exhausted."""
        limits = AnthropicRateLimits(output_tokens_remaining=0)
        assert limits.is_limited() is True
    
    def test_get_next_reset(self):
        """Should return earliest reset time."""
        early = datetime(2024, 6, 15, 12, 0, 0)
        late = datetime(2024, 6, 15, 13, 0, 0)
        limits = AnthropicRateLimits(
            requests_reset=late,
            tokens_reset=early,
        )
        assert limits.get_next_reset() == early
    
    def test_get_next_reset_none(self):
        """Should return None when no reset times."""
        limits = AnthropicRateLimits()
        assert limits.get_next_reset() is None


class TestExtractAnthropicRateLimits:
    """Tests for extract_anthropic_rate_limits function."""
    
    def test_empty_headers(self):
        """Should return AnthropicRateLimits with None values."""
        result = extract_anthropic_rate_limits({})
        assert isinstance(result, AnthropicRateLimits)
        assert result.requests_remaining is None
    
    def test_basic_headers(self):
        """Should extract basic Anthropic headers."""
        headers = {
            "anthropic-ratelimit-requests-remaining": "100",
            "anthropic-ratelimit-requests-limit": "1000",
            "anthropic-ratelimit-tokens-remaining": "50000",
            "anthropic-ratelimit-tokens-limit": "100000",
        }
        result = extract_anthropic_rate_limits(headers)
        
        assert result.requests_remaining == 100
        assert result.requests_limit == 1000
        assert result.tokens_remaining == 50000
        assert result.tokens_limit == 100000
    
    def test_reset_timestamps(self):
        """Should parse reset timestamps."""
        headers = {
            "anthropic-ratelimit-requests-remaining": "100",
            "anthropic-ratelimit-requests-reset": "2024-06-15T12:00:00Z",
        }
        result = extract_anthropic_rate_limits(headers)
        
        assert result.requests_remaining == 100
        assert result.requests_reset is not None
        assert result.requests_reset.year == 2024
        assert result.requests_reset.month == 6
    
    def test_input_output_tokens(self):
        """Should extract separate input/output token limits."""
        headers = {
            "anthropic-ratelimit-input-tokens-remaining": "25000",
            "anthropic-ratelimit-input-tokens-limit": "50000",
            "anthropic-ratelimit-output-tokens-remaining": "25000",
            "anthropic-ratelimit-output-tokens-limit": "50000",
        }
        result = extract_anthropic_rate_limits(headers)
        
        assert result.input_tokens_remaining == 25000
        assert result.input_tokens_limit == 50000
        assert result.output_tokens_remaining == 25000
        assert result.output_tokens_limit == 50000
    
    def test_invalid_values_ignored(self):
        """Should return None for invalid values."""
        headers = {
            "anthropic-ratelimit-requests-remaining": "not-a-number",
        }
        result = extract_anthropic_rate_limits(headers)
        assert result.requests_remaining is None


# =============================================================================
# OpenAI Rate Limits Tests
# =============================================================================

class TestOpenAIRateLimits:
    """Tests for OpenAIRateLimits dataclass."""
    
    def test_default_values(self):
        """Should have None defaults."""
        limits = OpenAIRateLimits()
        assert limits.remaining_requests is None
        assert limits.remaining_tokens is None
        assert limits.limit_requests is None
        assert limits.limit_tokens is None
        assert limits.reset_requests is None
        assert limits.reset_tokens is None
        assert limits.reset_requests_seconds is None
        assert limits.reset_tokens_seconds is None
    
    def test_all_fields(self):
        """Should accept all fields."""
        limits = OpenAIRateLimits(
            remaining_requests=100,
            remaining_tokens=50000,
            limit_requests=1000,
            limit_tokens=100000,
            reset_requests="6m30s",
            reset_requests_seconds=390,
            reset_tokens="1h",
            reset_tokens_seconds=3600,
        )
        assert limits.remaining_requests == 100
        assert limits.reset_requests == "6m30s"
        assert limits.reset_requests_seconds == 390
    
    def test_is_limited_false(self):
        """is_limited should return False when remaining > 0."""
        limits = OpenAIRateLimits(
            remaining_requests=100,
            remaining_tokens=50000,
        )
        assert limits.is_limited() is False
    
    def test_is_limited_true_requests(self):
        """is_limited should return True when requests exhausted."""
        limits = OpenAIRateLimits(remaining_requests=0)
        assert limits.is_limited() is True
    
    def test_is_limited_true_tokens(self):
        """is_limited should return True when tokens exhausted."""
        limits = OpenAIRateLimits(remaining_tokens=0)
        assert limits.is_limited() is True
    
    def test_get_seconds_until_reset(self):
        """Should return minimum reset time."""
        limits = OpenAIRateLimits(
            reset_requests_seconds=390,
            reset_tokens_seconds=3600,
        )
        assert limits.get_seconds_until_reset() == 390
    
    def test_get_seconds_until_reset_none(self):
        """Should return None when no reset times."""
        limits = OpenAIRateLimits()
        assert limits.get_seconds_until_reset() is None


class TestExtractOpenAIRateLimits:
    """Tests for extract_openai_rate_limits function."""
    
    def test_empty_headers(self):
        """Should return OpenAIRateLimits with None values."""
        result = extract_openai_rate_limits({})
        assert isinstance(result, OpenAIRateLimits)
        assert result.remaining_requests is None
    
    def test_basic_headers(self):
        """Should extract basic OpenAI headers."""
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-remaining-tokens": "50000",
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-limit-tokens": "100000",
        }
        result = extract_openai_rate_limits(headers)
        
        assert result.remaining_requests == 100
        assert result.remaining_tokens == 50000
        assert result.limit_requests == 1000
        assert result.limit_tokens == 100000
    
    def test_reset_duration_minutes_seconds(self):
        """Should parse '6m30s' format."""
        headers = {
            "x-ratelimit-reset-requests": "6m30s",
        }
        result = extract_openai_rate_limits(headers)
        
        assert result.reset_requests == "6m30s"
        assert result.reset_requests_seconds == 390
    
    def test_reset_duration_hours(self):
        """Should parse '1h' format."""
        headers = {
            "x-ratelimit-reset-tokens": "1h",
        }
        result = extract_openai_rate_limits(headers)
        
        assert result.reset_tokens == "1h"
        assert result.reset_tokens_seconds == 3600
    
    def test_reset_duration_complex(self):
        """Should parse '1h30m45s' format."""
        headers = {
            "x-ratelimit-reset-requests": "1h30m45s",
        }
        result = extract_openai_rate_limits(headers)
        
        expected = 1 * 3600 + 30 * 60 + 45
        assert result.reset_requests_seconds == expected
    
    def test_reset_duration_milliseconds(self):
        """Should parse '500ms' format."""
        headers = {
            "x-ratelimit-reset-requests": "500ms",
        }
        result = extract_openai_rate_limits(headers)
        
        # 500ms rounds up to 1 second
        assert result.reset_requests_seconds == 1
    
    def test_reset_duration_seconds_only(self):
        """Should parse '45s' format."""
        headers = {
            "x-ratelimit-reset-requests": "45s",
        }
        result = extract_openai_rate_limits(headers)
        
        assert result.reset_requests_seconds == 45
    
    def test_invalid_values_ignored(self):
        """Should return None for invalid values."""
        headers = {
            "x-ratelimit-remaining-requests": "not-a-number",
        }
        result = extract_openai_rate_limits(headers)
        assert result.remaining_requests is None


# =============================================================================
# Cross-Provider Integration Tests
# =============================================================================

class TestCrossProviderIntegration:
    """Tests for using multiple providers together."""
    
    def test_extract_from_ratelimitinfo_raw_headers(self):
        """Should extract provider-specific limits from RateLimitInfo.raw_headers."""
        from flatagents import extract_rate_limit_info
        
        # Simulate headers with mixed provider info
        headers = {
            # Generic (captured by extract_rate_limit_info)
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-remaining-tokens": "50000",
            # Cerebras-specific
            "x-ratelimit-remaining-requests-minute": "10",
            "x-ratelimit-remaining-tokens-day": "500000",
        }
        
        # Extract generic info
        rate_limit = extract_rate_limit_info(headers)
        assert rate_limit.remaining_requests == 100
        assert rate_limit.remaining_tokens == 50000
        
        # Extract Cerebras-specific from raw_headers
        cerebras = extract_cerebras_rate_limits(rate_limit.raw_headers)
        assert cerebras.remaining_requests_minute == 10
        assert cerebras.remaining_tokens_day == 500000
    
    def test_all_extractors_handle_empty(self):
        """All extractors should handle empty headers gracefully."""
        empty = {}
        
        cerebras = extract_cerebras_rate_limits(empty)
        assert not cerebras.is_limited()
        
        anthropic = extract_anthropic_rate_limits(empty)
        assert not anthropic.is_limited()
        
        openai = extract_openai_rate_limits(empty)
        assert not openai.is_limited()
    
    def test_all_extractors_handle_wrong_provider(self):
        """Extractors should return None values for wrong provider headers."""
        # Anthropic headers
        anthropic_headers = {
            "anthropic-ratelimit-requests-remaining": "100",
        }
        
        # Cerebras extractor should find nothing
        cerebras = extract_cerebras_rate_limits(anthropic_headers)
        assert cerebras.remaining_requests_minute is None
        
        # OpenAI extractor should find nothing
        openai = extract_openai_rate_limits(anthropic_headers)
        assert openai.remaining_requests is None

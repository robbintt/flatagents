"""
Unit tests for header extraction utilities.

Tests: _normalize_headers, _parse_int_header, _parse_reset_timestamp,
       extract_rate_limit_info, extract_headers_from_response,
       extract_headers_from_error, extract_status_code, is_retryable_error
"""

import pytest
import time
from datetime import datetime
from unittest.mock import MagicMock

from flatagents import (
    extract_headers_from_response,
    extract_headers_from_error,
    extract_rate_limit_info,
    extract_status_code,
    is_retryable_error,
    RateLimitInfo,
)
from flatagents.baseagent import (
    _normalize_headers,
    _parse_int_header,
    _parse_reset_timestamp,
)


# =============================================================================
# _normalize_headers Tests
# =============================================================================

class TestNormalizeHeaders:
    """Tests for _normalize_headers utility."""
    
    def test_none_input(self):
        """Should return empty dict for None input."""
        assert _normalize_headers(None) == {}
    
    def test_empty_dict(self):
        """Should return empty dict for empty input."""
        assert _normalize_headers({}) == {}
    
    def test_dict_input(self):
        """Should normalize dict keys to lowercase."""
        headers = {"Content-Type": "application/json", "X-Request-ID": "123"}
        result = _normalize_headers(headers)
        assert result["content-type"] == "application/json"
        assert result["x-request-id"] == "123"
    
    def test_mixed_case(self):
        """Should handle mixed case headers."""
        headers = {"X-RateLimit-Remaining": "100"}
        result = _normalize_headers(headers)
        assert result["x-ratelimit-remaining"] == "100"
    
    def test_list_values(self):
        """Should join list values with comma."""
        headers = {"Set-Cookie": ["a=1", "b=2"]}
        result = _normalize_headers(headers)
        assert result["set-cookie"] == "a=1,b=2"
    
    def test_tuple_input(self):
        """Should handle list of tuples."""
        headers = [("Content-Type", "text/plain"), ("X-Custom", "value")]
        result = _normalize_headers(headers)
        assert result["content-type"] == "text/plain"
        assert result["x-custom"] == "value"
    
    def test_httpx_headers(self):
        """Should handle httpx.Headers-like objects with items()."""
        mock_headers = MagicMock()
        mock_headers.items.return_value = [("Content-Type", "application/json")]
        result = _normalize_headers(mock_headers)
        assert result["content-type"] == "application/json"
    
    def test_none_key_skipped(self):
        """Should skip None keys."""
        headers = {None: "value", "valid": "data"}
        result = _normalize_headers(headers)
        assert "none" not in result
        assert result["valid"] == "data"
    
    def test_numeric_values(self):
        """Should convert numeric values to strings."""
        headers = {"x-count": 100}
        result = _normalize_headers(headers)
        assert result["x-count"] == "100"


# =============================================================================
# _parse_int_header Tests
# =============================================================================

class TestParseIntHeader:
    """Tests for _parse_int_header utility."""
    
    def test_valid_int(self):
        """Should parse valid integer."""
        headers = {"x-count": "100"}
        assert _parse_int_header(headers, "x-count") == 100
    
    def test_missing_key(self):
        """Should return None for missing key."""
        headers = {"x-other": "100"}
        assert _parse_int_header(headers, "x-count") is None
    
    def test_multiple_keys_first_match(self):
        """Should return first matching key."""
        headers = {"x-primary": "100", "x-fallback": "200"}
        assert _parse_int_header(headers, "x-primary", "x-fallback") == 100
    
    def test_multiple_keys_fallback(self):
        """Should fall back to second key."""
        headers = {"x-fallback": "200"}
        assert _parse_int_header(headers, "x-primary", "x-fallback") == 200
    
    def test_invalid_int(self):
        """Should return None for non-integer value."""
        headers = {"x-count": "not-a-number"}
        assert _parse_int_header(headers, "x-count") is None
    
    def test_case_insensitive(self):
        """Should handle case-insensitive lookup."""
        headers = {"x-count": "100"}
        # The function tries both provided key and lowercase
        assert _parse_int_header(headers, "X-COUNT") == 100
    
    def test_empty_value(self):
        """Should return None for empty value."""
        headers = {"x-count": ""}
        assert _parse_int_header(headers, "x-count") is None


# =============================================================================
# _parse_reset_timestamp Tests
# =============================================================================

class TestParseResetTimestamp:
    """Tests for _parse_reset_timestamp utility."""
    
    def test_unix_timestamp_seconds(self):
        """Should parse unix timestamp in seconds."""
        now = int(time.time())
        headers = {"x-reset": str(now + 60)}
        result = _parse_reset_timestamp(headers, "x-reset")
        assert result is not None
        assert abs(result - (now + 60)) < 1
    
    def test_unix_timestamp_milliseconds(self):
        """Should convert milliseconds to seconds."""
        now_ms = int(time.time() * 1000)
        headers = {"x-reset": str(now_ms + 60000)}
        result = _parse_reset_timestamp(headers, "x-reset")
        assert result is not None
        # Should be converted to seconds
        assert result < now_ms  # Much smaller than milliseconds
    
    def test_relative_seconds(self):
        """Should convert relative seconds to absolute timestamp."""
        headers = {"x-reset": "60"}
        before = time.time()
        result = _parse_reset_timestamp(headers, "x-reset")
        after = time.time()
        assert result is not None
        assert before + 59 <= result <= after + 61
    
    def test_relative_seconds_with_suffix(self):
        """Should handle '60s' format."""
        headers = {"x-reset": "60s"}
        before = time.time()
        result = _parse_reset_timestamp(headers, "x-reset")
        after = time.time()
        assert result is not None
        assert before + 59 <= result <= after + 61
    
    def test_iso8601_utc(self):
        """Should parse ISO 8601 UTC format."""
        headers = {"x-reset": "2024-06-15T12:00:00Z"}
        result = _parse_reset_timestamp(headers, "x-reset")
        assert result is not None
        # Verify it's a reasonable timestamp
        assert result > 1700000000  # After 2023
    
    def test_iso8601_with_microseconds(self):
        """Should parse ISO 8601 with microseconds."""
        headers = {"x-reset": "2024-06-15T12:00:00.123456Z"}
        result = _parse_reset_timestamp(headers, "x-reset")
        assert result is not None
    
    def test_multiple_keys_fallback(self):
        """Should try multiple keys."""
        headers = {"x-reset-tokens": "60"}
        result = _parse_reset_timestamp(headers, "x-reset-requests", "x-reset-tokens")
        assert result is not None
    
    def test_missing_key(self):
        """Should return None for missing key."""
        headers = {"x-other": "60"}
        result = _parse_reset_timestamp(headers, "x-reset")
        assert result is None
    
    def test_invalid_format(self):
        """Should return None for unparseable format."""
        headers = {"x-reset": "not-a-timestamp"}
        result = _parse_reset_timestamp(headers, "x-reset")
        assert result is None


# =============================================================================
# extract_rate_limit_info Tests
# =============================================================================

class TestExtractRateLimitInfo:
    """Tests for extract_rate_limit_info function."""
    
    def test_empty_headers(self):
        """Should return RateLimitInfo with None values for empty headers."""
        result = extract_rate_limit_info({})
        assert isinstance(result, RateLimitInfo)
        assert result.remaining_requests is None
        assert result.remaining_tokens is None
        assert result.raw_headers == {}
    
    def test_openai_headers(self):
        """Should parse OpenAI-style headers."""
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-ratelimit-remaining-tokens": "50000",
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-limit-tokens": "100000",
        }
        result = extract_rate_limit_info(headers)
        assert result.remaining_requests == 100
        assert result.remaining_tokens == 50000
        assert result.limit_requests == 1000
        assert result.limit_tokens == 100000
    
    def test_anthropic_headers(self):
        """Should parse Anthropic-style headers."""
        headers = {
            "anthropic-ratelimit-requests-remaining": "100",
            "anthropic-ratelimit-tokens-remaining": "50000",
            "anthropic-ratelimit-requests-limit": "1000",
            "anthropic-ratelimit-tokens-limit": "100000",
        }
        result = extract_rate_limit_info(headers)
        assert result.remaining_requests == 100
        assert result.remaining_tokens == 50000
        assert result.limit_requests == 1000
        assert result.limit_tokens == 100000
    
    def test_generic_headers(self):
        """Should parse generic ratelimit headers."""
        headers = {
            "ratelimit-remaining": "100",
            "ratelimit-limit": "1000",
        }
        result = extract_rate_limit_info(headers)
        assert result.remaining_requests == 100
        assert result.limit_requests == 1000
    
    def test_retry_after(self):
        """Should parse Retry-After header."""
        headers = {"retry-after": "60"}
        result = extract_rate_limit_info(headers)
        assert result.retry_after == 60
    
    def test_reset_timestamp(self):
        """Should parse reset timestamp."""
        headers = {"x-ratelimit-reset-requests": "2024-06-15T12:00:00Z"}
        result = extract_rate_limit_info(headers)
        assert result.reset_at is not None
    
    def test_raw_headers_preserved(self):
        """Should preserve raw headers."""
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "x-custom-header": "value",
        }
        result = extract_rate_limit_info(headers)
        assert result.raw_headers == headers
        assert "x-custom-header" in result.raw_headers
    
    def test_mixed_provider_headers(self):
        """Should handle mixed headers (OpenAI takes precedence)."""
        headers = {
            "x-ratelimit-remaining-requests": "100",
            "anthropic-ratelimit-requests-remaining": "200",
        }
        result = extract_rate_limit_info(headers)
        # OpenAI-style should match first
        assert result.remaining_requests == 100


# =============================================================================
# extract_headers_from_response Tests
# =============================================================================

class TestExtractHeadersFromResponse:
    """Tests for extract_headers_from_response function."""
    
    def test_none_response(self):
        """Should return empty dict for None."""
        # The function should handle None gracefully
        result = extract_headers_from_response(None)
        assert result == {}
    
    def test_litellm_response_headers(self):
        """Should extract from _response_headers."""
        mock_response = MagicMock()
        mock_response._response_headers = {
            "x-ratelimit-remaining-requests": "100",
        }
        mock_response._hidden_params = None
        
        result = extract_headers_from_response(mock_response)
        assert "x-ratelimit-remaining-requests" in result
    
    def test_litellm_hidden_params(self):
        """Should extract from _hidden_params.additional_headers."""
        mock_response = MagicMock()
        mock_response._response_headers = None
        mock_response._hidden_params = {
            "additional_headers": {"x-custom": "value"},
        }
        
        result = extract_headers_from_response(mock_response)
        assert "x-custom" in result
    
    def test_combines_both_sources(self):
        """Should combine headers from both sources."""
        mock_response = MagicMock()
        mock_response._response_headers = {"x-from-response": "1"}
        mock_response._hidden_params = {
            "additional_headers": {"x-from-hidden": "2"},
        }
        
        result = extract_headers_from_response(mock_response)
        assert "x-from-response" in result
        assert "x-from-hidden" in result
    
    def test_no_headers(self):
        """Should return empty dict when no headers available."""
        mock_response = MagicMock()
        mock_response._response_headers = None
        mock_response._hidden_params = None
        
        result = extract_headers_from_response(mock_response)
        assert result == {}


# =============================================================================
# extract_headers_from_error Tests
# =============================================================================

class TestExtractHeadersFromError:
    """Tests for extract_headers_from_error function."""
    
    def test_simple_exception(self):
        """Should return empty dict for simple exception."""
        error = Exception("test error")
        result = extract_headers_from_error(error)
        assert result == {}
    
    def test_error_with_response_headers(self):
        """Should extract from error.response.headers."""
        error = Exception("test")
        error.response = MagicMock()
        error.response.headers = {"x-ratelimit-remaining": "0"}
        
        result = extract_headers_from_error(error)
        assert "x-ratelimit-remaining" in result
    
    def test_error_with_dict_response(self):
        """Should extract from dict response."""
        error = Exception("test")
        error.response = {"headers": {"x-custom": "value"}}
        
        result = extract_headers_from_error(error)
        assert "x-custom" in result
    
    def test_error_with_direct_headers(self):
        """Should extract from error.headers."""
        error = Exception("test")
        error.headers = {"x-direct": "value"}
        
        result = extract_headers_from_error(error)
        assert "x-direct" in result
    
    def test_combines_sources(self):
        """Should combine headers from multiple sources."""
        error = Exception("test")
        error.response = MagicMock()
        error.response.headers = {"x-from-response": "1"}
        error.headers = {"x-from-error": "2"}
        
        result = extract_headers_from_error(error)
        assert "x-from-response" in result
        assert "x-from-error" in result


# =============================================================================
# extract_status_code Tests
# =============================================================================

class TestExtractStatusCode:
    """Tests for extract_status_code function."""
    
    def test_simple_exception(self):
        """Should return None for simple exception."""
        error = Exception("test error")
        result = extract_status_code(error)
        assert result is None
    
    def test_status_code_attribute(self):
        """Should extract from status_code attribute."""
        error = Exception("test")
        error.status_code = 429
        assert extract_status_code(error) == 429
    
    def test_status_attribute(self):
        """Should extract from status attribute."""
        error = Exception("test")
        error.status = 500
        assert extract_status_code(error) == 500
    
    def test_http_status_attribute(self):
        """Should extract from http_status attribute."""
        error = Exception("test")
        error.http_status = 503
        assert extract_status_code(error) == 503
    
    def test_response_status_code(self):
        """Should extract from response.status_code."""
        error = Exception("test")
        error.response = MagicMock()
        error.response.status_code = 429
        assert extract_status_code(error) == 429
    
    def test_dict_response(self):
        """Should extract from dict response."""
        error = Exception("test")
        error.response = {"status_code": 404}
        assert extract_status_code(error) == 404
    
    def test_parse_from_message(self):
        """Should parse status code from error message."""
        error = Exception("Error 429: Too many requests")
        assert extract_status_code(error) == 429
    
    def test_parse_500_from_message(self):
        """Should parse 5xx codes from message."""
        error = Exception("Server error 503")
        assert extract_status_code(error) == 503
    
    def test_no_false_positives(self):
        """Should not match non-status numbers."""
        error = Exception("Request took 1234ms")
        # 1234 is not a valid status code pattern (4xx/5xx)
        result = extract_status_code(error)
        assert result is None


# =============================================================================
# is_retryable_error Tests
# =============================================================================

class TestIsRetryableError:
    """Tests for is_retryable_error function."""
    
    def test_429_is_retryable(self):
        """429 Too Many Requests should be retryable."""
        error = Exception("Rate limited")
        assert is_retryable_error(error, 429) is True
    
    def test_500_is_retryable(self):
        """500 Internal Server Error should be retryable."""
        error = Exception("Server error")
        assert is_retryable_error(error, 500) is True
    
    def test_502_is_retryable(self):
        """502 Bad Gateway should be retryable."""
        error = Exception("Bad gateway")
        assert is_retryable_error(error, 502) is True
    
    def test_503_is_retryable(self):
        """503 Service Unavailable should be retryable."""
        error = Exception("Service unavailable")
        assert is_retryable_error(error, 503) is True
    
    def test_400_is_not_retryable(self):
        """400 Bad Request should not be retryable."""
        error = Exception("Bad request")
        assert is_retryable_error(error, 400) is False
    
    def test_401_is_not_retryable(self):
        """401 Unauthorized should not be retryable."""
        error = Exception("Unauthorized")
        assert is_retryable_error(error, 401) is False
    
    def test_404_is_not_retryable(self):
        """404 Not Found should not be retryable."""
        error = Exception("Not found")
        assert is_retryable_error(error, 404) is False
    
    def test_ratelimit_error_type(self):
        """RateLimitError type should be retryable."""
        class RateLimitError(Exception):
            pass
        error = RateLimitError("Rate limited")
        assert is_retryable_error(error, None) is True
    
    def test_timeout_error_type(self):
        """TimeoutError type should be retryable."""
        class TimeoutError(Exception):
            pass
        error = TimeoutError("Timed out")
        assert is_retryable_error(error, None) is True
    
    def test_rate_limit_message(self):
        """Error message with 'rate limit' should be retryable."""
        error = Exception("You have exceeded the rate limit")
        assert is_retryable_error(error, None) is True
    
    def test_too_many_requests_message(self):
        """Error message with 'too many requests' should be retryable."""
        error = Exception("Error: too many requests, please slow down")
        assert is_retryable_error(error, None) is True
    
    def test_timeout_message(self):
        """Error message with 'timeout' should be retryable."""
        error = Exception("Connection timeout after 30s")
        assert is_retryable_error(error, None) is True
    
    def test_temporarily_message(self):
        """Error message with 'temporarily' should be retryable."""
        error = Exception("Service temporarily unavailable")
        assert is_retryable_error(error, None) is True
    
    def test_generic_error_not_retryable(self):
        """Generic errors without indicators should not be retryable."""
        error = Exception("Something went wrong")
        assert is_retryable_error(error, None) is False

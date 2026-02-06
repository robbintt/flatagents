"""
Anthropic-specific rate limit extraction.

Anthropic uses the `anthropic-ratelimit-*` header prefix and provides
separate limits for requests and tokens with reset timestamps.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class AnthropicRateLimits:
    """
    Anthropic-specific rate limit information.
    
    Anthropic provides separate request and token limits with
    ISO 8601 reset timestamps.
    """
    # Requests
    requests_remaining: Optional[int] = None
    requests_limit: Optional[int] = None
    requests_reset: Optional[datetime] = None
    
    # Tokens
    tokens_remaining: Optional[int] = None
    tokens_limit: Optional[int] = None
    tokens_reset: Optional[datetime] = None
    
    # Input tokens (separate limit on some tiers)
    input_tokens_remaining: Optional[int] = None
    input_tokens_limit: Optional[int] = None
    input_tokens_reset: Optional[datetime] = None
    
    # Output tokens (separate limit on some tiers)
    output_tokens_remaining: Optional[int] = None
    output_tokens_limit: Optional[int] = None
    output_tokens_reset: Optional[datetime] = None
    
    def is_limited(self) -> bool:
        """Check if any rate limit is exhausted."""
        return (
            self.requests_remaining == 0 or
            self.tokens_remaining == 0 or
            self.input_tokens_remaining == 0 or
            self.output_tokens_remaining == 0
        )
    
    def get_next_reset(self) -> Optional[datetime]:
        """Get the earliest reset time across all limits."""
        resets = [
            r for r in [
                self.requests_reset,
                self.tokens_reset,
                self.input_tokens_reset,
                self.output_tokens_reset,
            ]
            if r is not None
        ]
        return min(resets) if resets else None
    
    def get_seconds_until_reset(self) -> Optional[int]:
        """Get seconds until the earliest limit resets."""
        next_reset = self.get_next_reset()
        if next_reset is None:
            return None
        
        now = datetime.now(next_reset.tzinfo) if next_reset.tzinfo else datetime.now()
        delta = (next_reset - now).total_seconds()
        return max(0, int(delta))


def _parse_datetime(val: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string."""
    if val is None:
        return None
    
    val = val.strip()
    
    # Try various ISO 8601 formats
    for fmt in [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S',
    ]:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    
    return None


def extract_anthropic_rate_limits(raw_headers: Dict[str, str]) -> AnthropicRateLimits:
    """
    Extract Anthropic-specific rate limits from raw headers.
    
    Args:
        raw_headers: Normalized (lowercase) headers dict from RateLimitInfo.raw_headers
    
    Returns:
        AnthropicRateLimits with all available limits and reset times
    
    Example:
        response = await agent.call(prompt="Hello")
        if response.rate_limit:
            anthropic = extract_anthropic_rate_limits(response.rate_limit.raw_headers)
            if anthropic.is_limited():
                wait = anthropic.get_seconds_until_reset()
                print(f"Rate limited, reset in {wait}s")
    """
    def _get_int(key: str) -> Optional[int]:
        val = raw_headers.get(key) or raw_headers.get(key.lower())
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        return None
    
    def _get_datetime(key: str) -> Optional[datetime]:
        val = raw_headers.get(key) or raw_headers.get(key.lower())
        return _parse_datetime(val)
    
    return AnthropicRateLimits(
        # Requests
        requests_remaining=_get_int("anthropic-ratelimit-requests-remaining"),
        requests_limit=_get_int("anthropic-ratelimit-requests-limit"),
        requests_reset=_get_datetime("anthropic-ratelimit-requests-reset"),
        # Tokens
        tokens_remaining=_get_int("anthropic-ratelimit-tokens-remaining"),
        tokens_limit=_get_int("anthropic-ratelimit-tokens-limit"),
        tokens_reset=_get_datetime("anthropic-ratelimit-tokens-reset"),
        # Input tokens
        input_tokens_remaining=_get_int("anthropic-ratelimit-input-tokens-remaining"),
        input_tokens_limit=_get_int("anthropic-ratelimit-input-tokens-limit"),
        input_tokens_reset=_get_datetime("anthropic-ratelimit-input-tokens-reset"),
        # Output tokens
        output_tokens_remaining=_get_int("anthropic-ratelimit-output-tokens-remaining"),
        output_tokens_limit=_get_int("anthropic-ratelimit-output-tokens-limit"),
        output_tokens_reset=_get_datetime("anthropic-ratelimit-output-tokens-reset"),
    )

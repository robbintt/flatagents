"""
OpenAI-specific rate limit extraction.

OpenAI uses the `x-ratelimit-*` header prefix with separate limits
for requests and tokens, plus reset timestamps.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
import time as time_module


@dataclass
class OpenAIRateLimits:
    """
    OpenAI-specific rate limit information.
    
    OpenAI provides separate request and token limits with
    reset times (as relative durations like "6m0s" or "1h30m").
    """
    # Requests
    remaining_requests: Optional[int] = None
    limit_requests: Optional[int] = None
    reset_requests: Optional[str] = None  # Raw duration string
    reset_requests_seconds: Optional[int] = None  # Parsed to seconds
    
    # Tokens
    remaining_tokens: Optional[int] = None
    limit_tokens: Optional[int] = None
    reset_tokens: Optional[str] = None  # Raw duration string
    reset_tokens_seconds: Optional[int] = None  # Parsed to seconds
    
    def is_limited(self) -> bool:
        """Check if any rate limit is exhausted."""
        return self.remaining_requests == 0 or self.remaining_tokens == 0
    
    def get_seconds_until_reset(self) -> Optional[int]:
        """Get seconds until the earliest limit resets."""
        resets = [
            r for r in [
                self.reset_requests_seconds,
                self.reset_tokens_seconds,
            ]
            if r is not None
        ]
        return min(resets) if resets else None


def _parse_duration(val: Optional[str]) -> Optional[int]:
    """
    Parse OpenAI duration strings like "6m0s", "1h30m", "500ms".
    
    Returns total seconds (rounds up for sub-second durations).
    """
    if val is None:
        return None
    
    val = val.strip()
    if not val:
        return None
    
    total_seconds = 0
    current_num = ""
    
    i = 0
    while i < len(val):
        char = val[i]
        
        if char.isdigit() or char == '.':
            current_num += char
            i += 1
        elif char in 'hms':
            if current_num:
                num = float(current_num)
                if char == 'h':
                    total_seconds += num * 3600
                elif char == 'm':
                    # Check for 'ms' (milliseconds)
                    if i + 1 < len(val) and val[i + 1] == 's':
                        total_seconds += num / 1000
                        i += 1  # Skip the 's'
                    else:
                        total_seconds += num * 60
                elif char == 's':
                    total_seconds += num
                current_num = ""
            i += 1
        else:
            i += 1
    
    # Handle any remaining number (assumed seconds)
    if current_num:
        try:
            total_seconds += float(current_num)
        except ValueError:
            pass
    
    # Round up to nearest second
    import math
    return math.ceil(total_seconds) if total_seconds > 0 else None


def extract_openai_rate_limits(raw_headers: Dict[str, str]) -> OpenAIRateLimits:
    """
    Extract OpenAI-specific rate limits from raw headers.
    
    Args:
        raw_headers: Normalized (lowercase) headers dict from RateLimitInfo.raw_headers
    
    Returns:
        OpenAIRateLimits with all available limits and reset times
    
    Example:
        response = await agent.call(prompt="Hello")
        if response.rate_limit:
            openai_limits = extract_openai_rate_limits(response.rate_limit.raw_headers)
            if openai_limits.is_limited():
                wait = openai_limits.get_seconds_until_reset()
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
    
    def _get_str(key: str) -> Optional[str]:
        return raw_headers.get(key) or raw_headers.get(key.lower())
    
    reset_requests_str = _get_str("x-ratelimit-reset-requests")
    reset_tokens_str = _get_str("x-ratelimit-reset-tokens")
    
    return OpenAIRateLimits(
        # Requests
        remaining_requests=_get_int("x-ratelimit-remaining-requests"),
        limit_requests=_get_int("x-ratelimit-limit-requests"),
        reset_requests=reset_requests_str,
        reset_requests_seconds=_parse_duration(reset_requests_str),
        # Tokens
        remaining_tokens=_get_int("x-ratelimit-remaining-tokens"),
        limit_tokens=_get_int("x-ratelimit-limit-tokens"),
        reset_tokens=reset_tokens_str,
        reset_tokens_seconds=_parse_duration(reset_tokens_str),
    )

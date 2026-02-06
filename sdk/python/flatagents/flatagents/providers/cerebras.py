"""
Cerebras-specific rate limit extraction.

Cerebras uses time-bucketed rate limits (minute, hour, day) which provide
more granular control over API usage patterns.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class CerebrasRateLimits:
    """
    Cerebras-specific time-bucketed rate limits.
    
    Cerebras provides separate limits for minute, hour, and day windows,
    allowing fine-grained rate limit management.
    """
    # Request limits by time bucket
    remaining_requests_minute: Optional[int] = None
    remaining_requests_hour: Optional[int] = None
    remaining_requests_day: Optional[int] = None
    limit_requests_minute: Optional[int] = None
    limit_requests_hour: Optional[int] = None
    limit_requests_day: Optional[int] = None
    
    # Token limits by time bucket
    remaining_tokens_minute: Optional[int] = None
    remaining_tokens_hour: Optional[int] = None
    remaining_tokens_day: Optional[int] = None
    limit_tokens_minute: Optional[int] = None
    limit_tokens_hour: Optional[int] = None
    limit_tokens_day: Optional[int] = None
    
    def is_limited(self) -> bool:
        """Check if any rate limit is exhausted."""
        for bucket in ["minute", "hour", "day"]:
            if getattr(self, f"remaining_requests_{bucket}") == 0:
                return True
            if getattr(self, f"remaining_tokens_{bucket}") == 0:
                return True
        return False
    
    def get_most_restrictive_bucket(self) -> Optional[str]:
        """
        Get the most restrictive time bucket that is exhausted.
        
        Returns:
            "minute", "hour", "day", or None if no limit is exhausted.
            Shorter buckets reset faster, so minute < hour < day in restrictiveness.
        """
        for bucket in ["minute", "hour", "day"]:
            if getattr(self, f"remaining_requests_{bucket}") == 0:
                return bucket
            if getattr(self, f"remaining_tokens_{bucket}") == 0:
                return bucket
        return None
    
    def get_suggested_wait_seconds(self) -> Optional[int]:
        """
        Get suggested wait time based on which bucket is exhausted.
        
        Returns:
            Approximate seconds to wait, or None if not limited.
        """
        bucket = self.get_most_restrictive_bucket()
        if bucket == "minute":
            return 60
        elif bucket == "hour":
            return 3600
        elif bucket == "day":
            return 86400
        return None


def extract_cerebras_rate_limits(raw_headers: Dict[str, str]) -> CerebrasRateLimits:
    """
    Extract Cerebras-specific rate limits from raw headers.
    
    Args:
        raw_headers: Normalized (lowercase) headers dict from RateLimitInfo.raw_headers
    
    Returns:
        CerebrasRateLimits with all available time-bucketed limits
    
    Example:
        response = await agent.call(prompt="Hello")
        if response.rate_limit:
            cerebras = extract_cerebras_rate_limits(response.rate_limit.raw_headers)
            if cerebras.remaining_tokens_minute == 0:
                await asyncio.sleep(60)  # Wait for minute bucket to reset
    """
    def _get_int(key: str) -> Optional[int]:
        val = raw_headers.get(key) or raw_headers.get(key.lower())
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        return None
    
    return CerebrasRateLimits(
        # Remaining requests
        remaining_requests_minute=_get_int("x-ratelimit-remaining-requests-minute"),
        remaining_requests_hour=_get_int("x-ratelimit-remaining-requests-hour"),
        remaining_requests_day=_get_int("x-ratelimit-remaining-requests-day"),
        # Limit requests
        limit_requests_minute=_get_int("x-ratelimit-limit-requests-minute"),
        limit_requests_hour=_get_int("x-ratelimit-limit-requests-hour"),
        limit_requests_day=_get_int("x-ratelimit-limit-requests-day"),
        # Remaining tokens
        remaining_tokens_minute=_get_int("x-ratelimit-remaining-tokens-minute"),
        remaining_tokens_hour=_get_int("x-ratelimit-remaining-tokens-hour"),
        remaining_tokens_day=_get_int("x-ratelimit-remaining-tokens-day"),
        # Limit tokens
        limit_tokens_minute=_get_int("x-ratelimit-limit-tokens-minute"),
        limit_tokens_hour=_get_int("x-ratelimit-limit-tokens-hour"),
        limit_tokens_day=_get_int("x-ratelimit-limit-tokens-day"),
    )

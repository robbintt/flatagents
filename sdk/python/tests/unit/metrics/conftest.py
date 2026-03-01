"""
Shared fixtures for metrics tests.
"""

import pytest


@pytest.fixture
def openai_rate_limit_headers():
    """Sample OpenAI-style rate limit headers."""
    return {
        "x-ratelimit-remaining-requests": "100",
        "x-ratelimit-remaining-tokens": "50000",
        "x-ratelimit-limit-requests": "1000",
        "x-ratelimit-limit-tokens": "100000",
        "x-ratelimit-reset-requests": "6m30s",
        "x-ratelimit-reset-tokens": "1h",
    }


@pytest.fixture
def anthropic_rate_limit_headers():
    """Sample Anthropic-style rate limit headers."""
    return {
        "anthropic-ratelimit-requests-remaining": "100",
        "anthropic-ratelimit-requests-limit": "1000",
        "anthropic-ratelimit-requests-reset": "2024-06-15T12:00:00Z",
        "anthropic-ratelimit-tokens-remaining": "50000",
        "anthropic-ratelimit-tokens-limit": "100000",
        "anthropic-ratelimit-tokens-reset": "2024-06-15T12:00:00Z",
    }


@pytest.fixture
def cerebras_rate_limit_headers():
    """Sample Cerebras-style rate limit headers."""
    return {
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


@pytest.fixture
def rate_limited_headers():
    """Headers indicating rate limit exhaustion."""
    return {
        "x-ratelimit-remaining-requests": "0",
        "x-ratelimit-remaining-tokens": "0",
        "retry-after": "60",
    }

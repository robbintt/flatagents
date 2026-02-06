# AgentResult Contract

> Universal result contract for agent execution across all backends.

## Overview

`AgentResult` is the standard interface between agent adapters and the flatmachines orchestration layer. It provides:

- **Structured error information** (no exceptions across process/network boundaries)
- **Rate limit state** for intelligent retry/backoff decisions
- **Usage metrics** including cache tokens
- **Provider-specific data** for custom handling

This contract is defined in `flatagents-runtime.d.ts` and implemented consistently across Python and TypeScript SDKs.

---

## AgentResult Structure

```python
@dataclass
class AgentResult:
    # Content
    output: Optional[Dict[str, Any]] = None    # Parsed structured output
    content: Optional[str] = None               # Raw text content
    raw: Any = None                             # In-process only, not serialized
    
    # Metrics
    usage: Optional[UsageInfo] = None           # Token counts
    cost: Optional[CostInfo | float] = None     # Cost breakdown or total
    metadata: Optional[Dict[str, Any]] = None   # Agent metadata
    
    # Completion
    finish_reason: Optional[str] = None         # Why the agent stopped
    
    # Error (None = success)
    error: Optional[AgentError] = None
    
    # Rate limits (for orchestration decisions)
    rate_limit: Optional[RateLimitState] = None
    
    # Provider-specific (includes raw_headers)
    provider_data: Optional[ProviderData] = None
    
    @property
    def success(self) -> bool:
        return self.error is None
```

---

## Field Details

### finish_reason

Why the LLM stopped generating.

**Known values:**
| Value | Description |
|-------|-------------|
| `stop` | Normal completion |
| `length` | Max tokens reached |
| `tool_use` | Tool call requested |
| `error` | Error occurred |
| `content_filter` | Safety filter triggered |
| `aborted` | User/signal aborted |

### error (AgentError)

Structured error information. Present when the agent call failed.

```python
{
    "code": "rate_limit",           # See known codes below
    "type": "RateLimitError",       # Original error type name
    "message": "Too many requests", # Human-readable message
    "status_code": 429,             # HTTP status code
    "retryable": True,              # Whether retry might succeed
}
```

**Known error codes:**
| Code | Description | Typically Retryable |
|------|-------------|---------------------|
| `rate_limit` | Hit rate limit | Yes (with backoff) |
| `timeout` | Request timed out | Yes |
| `server_error` | 5xx from provider | Yes |
| `invalid_request` | Bad request (4xx) | No |
| `auth_error` | Authentication failed | No |
| `content_filter` | Safety filter triggered | No |
| `context_length` | Input too long | No |
| `model_unavailable` | Model not available | Maybe |

### rate_limit (RateLimitState)

Rate limit state for orchestration decisions.

```python
{
    "limited": True,           # Is any limit exhausted?
    "retry_after": 60,         # Recommended wait (seconds)
    "windows": [               # Per-window breakdown
        {
            "name": "requests_per_minute",
            "resource": "requests",
            "remaining": 0,
            "limit": 60,
            "resets_in": 45,
            "reset_at": 1234567890.0,
        },
        {
            "name": "tokens_per_day",
            "resource": "tokens",
            "remaining": 500000,
            "limit": 1000000,
            "resets_in": 43200,
        },
    ],
}
```

**RateLimitWindow.resource known values:**
- `requests`
- `tokens`
- `input_tokens`
- `output_tokens`

### provider_data (ProviderData)

Provider-specific data including raw HTTP headers.

```python
{
    "provider": "cerebras",
    "model": "llama-4-scout-17b",
    "request_id": "req_abc123",
    "raw_headers": {
        "x-ratelimit-remaining-requests-minute": "10",
        "x-ratelimit-remaining-tokens-day": "500000",
    },
}
```

The `raw_headers` field contains normalized (lowercase) HTTP response headers when the backend exposes them.

### usage (UsageInfo)

Token usage metrics.

```python
{
    "input_tokens": 100,
    "output_tokens": 50,
    "total_tokens": 150,
    "cache_read_tokens": 10,
    "cache_write_tokens": 5,
    "api_calls": 1,
}
```

### cost (CostInfo)

Cost breakdown.

```python
{
    "input": 0.001,
    "output": 0.002,
    "cache_read": 0.0001,
    "cache_write": 0.0002,
    "total": 0.0033,
}
```

For backwards compatibility, `cost` can also be a float representing the total.

---

## Usage in Hooks

### Checking for Errors in on_state_exit

```python
def on_state_exit(self, state_name, context, output):
    # output may be an AgentResult dict
    if output and isinstance(output, dict):
        error = output.get("error")
        if error:
            if error.get("code") == "rate_limit":
                return self._handle_rate_limit(output, state_name, context)
            elif not error.get("retryable"):
                return self._handle_fatal_error(error, context)
    
    return output
```

### Using Rate Limit Windows

```python
def _handle_rate_limit(self, output, state_name, context):
    rate_limit = output.get("rate_limit", {})
    
    # Quick check
    if not rate_limit.get("limited"):
        return None
    
    # Find which window is exhausted
    for window in rate_limit.get("windows", []):
        if window.get("remaining") == 0:
            name = window.get("name", "")
            if "day" in name:
                # Daily limit - maybe switch providers
                return "switch_provider"
            elif "hour" in name:
                # Hourly limit - long wait
                context["wait_seconds"] = window.get("resets_in", 3600)
                return "long_wait"
            else:
                # Minute limit - short wait
                context["wait_seconds"] = rate_limit.get("retry_after", 60)
                return "short_wait"
    
    return None
```

### Accessing Raw Headers

```python
def _get_cerebras_time_buckets(self, output):
    provider_data = output.get("provider_data", {})
    raw_headers = provider_data.get("raw_headers", {})
    
    return {
        "requests_minute": raw_headers.get("x-ratelimit-remaining-requests-minute"),
        "requests_hour": raw_headers.get("x-ratelimit-remaining-requests-hour"),
        "requests_day": raw_headers.get("x-ratelimit-remaining-requests-day"),
        "tokens_minute": raw_headers.get("x-ratelimit-remaining-tokens-minute"),
        "tokens_hour": raw_headers.get("x-ratelimit-remaining-tokens-hour"),
        "tokens_day": raw_headers.get("x-ratelimit-remaining-tokens-day"),
    }
```

---

## Adapter Responsibilities

Each agent adapter maps its backend's response to `AgentResult`:

| Backend | Error Source | Rate Limit Source |
|---------|--------------|-------------------|
| flatagent | `AgentResponse.error` | `AgentResponse.rate_limit.raw_headers` |
| smolagents | Catch exceptions | `ChatMessage.raw._response_headers` |
| pi-agent | `stopReason == "error"` | Not exposed (needs enhancement) |

### FlatAgent Adapter Example

```python
async def execute(self, input_data, context):
    response = await self._agent.call(**input_data)
    
    error = None
    if response.error:
        error = {
            "code": self._map_error_code(response.error),
            "type": response.error.error_type,
            "message": response.error.message,
            "status_code": response.error.status_code,
            "retryable": response.error.retryable,
        }
    
    rate_limit = None
    if response.rate_limit:
        rate_limit = build_rate_limit_state(
            response.rate_limit.raw_headers,
            response.rate_limit.retry_after,
        )
    
    return AgentResult(
        output=response.output,
        content=response.content,
        error=error,
        rate_limit=rate_limit,
        provider_data={
            "provider": self._agent.provider,
            "model": self._agent.model,
            "raw_headers": response.rate_limit.raw_headers if response.rate_limit else {},
        },
    )
```

---

## Helper Functions

### build_rate_limit_windows

Parses raw HTTP headers into `RateLimitWindow` list.

```python
from flatmachines import build_rate_limit_windows

headers = {
    "x-ratelimit-remaining-requests-minute": "10",
    "x-ratelimit-remaining-tokens-day": "500000",
}

windows = build_rate_limit_windows(headers)
# [
#     {"name": "requests_per_minute", "resource": "requests", "remaining": 10, ...},
#     {"name": "tokens_per_day", "resource": "tokens", "remaining": 500000, ...},
# ]
```

Supports:
- Cerebras: `x-ratelimit-remaining-{requests,tokens}-{minute,hour,day}`
- OpenAI: `x-ratelimit-remaining-{requests,tokens}`, duration strings like `6m30s`
- Anthropic: `anthropic-ratelimit-{requests,tokens}-{remaining,limit,reset}`

### build_rate_limit_state

Builds complete `RateLimitState` from headers.

```python
from flatmachines import build_rate_limit_state

state = build_rate_limit_state(headers, retry_after=60)
# {
#     "limited": False,
#     "retry_after": 60,
#     "windows": [...],
# }
```

---

## Cross-Language Compatibility

`AgentResult` uses structured data (dicts) rather than classes, making it:

- **JSON-serializable** for cross-process communication
- **Language-agnostic** for Python/TypeScript/other SDKs
- **Network-safe** for distributed execution

The `raw` field is the exception - it's in-process only and not serialized.

---

## Migration from Exceptions

Previously, agent errors were raised as exceptions and handled in `on_error`. Now:

| Before | After |
|--------|-------|
| `on_error(state, exception, ctx)` | Check `output.error` in `on_state_exit` |
| `exception.status_code` | `output["error"]["status_code"]` |
| `exception.response.headers` | `output["provider_data"]["raw_headers"]` |

Keep `on_error` for unexpected runtime exceptions (code bugs), not API errors.

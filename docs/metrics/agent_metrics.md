# Agent Metrics

> Unified metrics structures for flatagents and cross-agent compatibility with smolagents and pi-agent.

## Overview

FlatAgents provides comprehensive metrics from LLM calls including:
- **Token usage** (input, output, cache read/write, totals)
- **Cost tracking** (per-field breakdown)
- **Rate limit information** (remaining quotas, reset times)
- **Finish reasons** (stop, length, tool_use, error, etc.)
- **Error information** (type, status code, retryability)

These metrics are surfaced in `AgentResponse` so that:
1. Scripts using flatagents directly can make informed decisions
2. FlatMachines orchestrator can handle retries, suspensions, and routing
3. Adapters for smolagents/pi-agent can map to the same structure

---

## Core Data Structures

### CostInfo

Per-field cost breakdown from an LLM call.

```python
@dataclass
class CostInfo:
    input: float = 0.0        # Cost for input tokens
    output: float = 0.0       # Cost for output tokens
    cache_read: float = 0.0   # Cost for cache read tokens
    cache_write: float = 0.0  # Cost for cache write tokens
    total: float = 0.0        # Total cost
```

### UsageInfo

Token usage from an LLM call.

```python
@dataclass
class UsageInfo:
    # Core tokens
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Cache tokens (Anthropic, OpenAI with prompt caching)
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    
    # Cost breakdown (None if not calculable)
    cost: Optional[CostInfo] = None
    
    @property
    def estimated_cost(self) -> float:
        """Total estimated cost (backwards compatible)."""
        return self.cost.total if self.cost else 0.0
```

### FinishReason

Why the LLM stopped generating.

```python
class FinishReason(str, Enum):
    STOP = "stop"                     # Normal completion
    LENGTH = "length"                 # Max tokens reached
    TOOL_USE = "tool_use"             # Tool call requested
    ERROR = "error"                   # Error occurred
    ABORTED = "aborted"               # User/signal aborted
    CONTENT_FILTER = "content_filter" # Safety filter triggered
```

### RateLimitInfo

Provider-agnostic rate limit information with raw headers for provider-specific parsing.

```python
@dataclass
class RateLimitInfo:
    # Normalized core (most providers expose these)
    remaining_requests: Optional[int] = None
    remaining_tokens: Optional[int] = None
    limit_requests: Optional[int] = None
    limit_tokens: Optional[int] = None
    
    # Timing for backoff calculations
    reset_at: Optional[float] = None   # Unix timestamp when limits reset
    retry_after: Optional[int] = None  # Seconds to wait (from Retry-After header)
    
    # Raw headers for provider-specific parsing
    raw_headers: Dict[str, str] = field(default_factory=dict)
    
    def is_limited(self) -> bool:
        """Check if any rate limit is exhausted (remaining == 0)."""
        return self.remaining_requests == 0 or self.remaining_tokens == 0
    
    def get_retry_delay(self) -> Optional[int]:
        """Get recommended retry delay in seconds."""
        # Returns retry_after if set, otherwise calculates from reset_at
        ...
```

### ErrorInfo

Error information from a failed LLM call.

```python
@dataclass
class ErrorInfo:
    error_type: str              # Exception class name
    message: str                 # Error message
    status_code: Optional[int] = None   # HTTP status code (429, 500, etc.)
    retryable: bool = False      # Whether retry may succeed
```

### AgentResponse

Complete response from an agent call.

```python
@dataclass
class AgentResponse:
    # Content
    content: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[ToolCall]] = None
    raw_response: Optional[Any] = None
    
    # Metrics
    usage: Optional[UsageInfo] = None
    rate_limit: Optional[RateLimitInfo] = None
    finish_reason: Optional[FinishReason] = None
    error: Optional[ErrorInfo] = None
    
    @property
    def success(self) -> bool:
        """Whether the call succeeded (no error)."""
        return self.error is None
```

---

## Provider Header Mappings

### OpenAI / Azure OpenAI

| Header | Maps To |
|--------|---------|
| `x-ratelimit-remaining-requests` | `remaining_requests` |
| `x-ratelimit-remaining-tokens` | `remaining_tokens` |
| `x-ratelimit-limit-requests` | `limit_requests` |
| `x-ratelimit-limit-tokens` | `limit_tokens` |
| `x-ratelimit-reset-requests` | `reset_at` (parsed) |
| `x-ratelimit-reset-tokens` | `reset_at` (parsed) |

### Anthropic

| Header | Maps To |
|--------|---------|
| `anthropic-ratelimit-requests-remaining` | `remaining_requests` |
| `anthropic-ratelimit-tokens-remaining` | `remaining_tokens` |
| `anthropic-ratelimit-requests-limit` | `limit_requests` |
| `anthropic-ratelimit-tokens-limit` | `limit_tokens` |
| `anthropic-ratelimit-requests-reset` | `reset_at` (parsed) |
| `anthropic-ratelimit-tokens-reset` | `reset_at` (parsed) |
| `retry-after` | `retry_after` |

### Cerebras

Cerebras uses time-bucketed rate limits (minute, hour, day). These are stored in `raw_headers` and can be extracted with provider-specific utilities.

| Header | Description |
|--------|-------------|
| `x-ratelimit-remaining-requests-minute` | Requests remaining this minute |
| `x-ratelimit-remaining-requests-hour` | Requests remaining this hour |
| `x-ratelimit-remaining-requests-day` | Requests remaining today |
| `x-ratelimit-remaining-tokens-minute` | Tokens remaining this minute |
| `x-ratelimit-remaining-tokens-hour` | Tokens remaining this hour |
| `x-ratelimit-remaining-tokens-day` | Tokens remaining today |

```python
from flatagents import extract_cerebras_rate_limits

cerebras_limits = extract_cerebras_rate_limits(response.rate_limit.raw_headers)
if cerebras_limits.remaining_tokens_day == 0:
    print("Daily token limit exhausted")
```

---

## Provider-Specific Extractors

For detailed provider-specific rate limit information, use the extraction utilities:

```python
from flatagents import (
    extract_cerebras_rate_limits,   # CerebrasRateLimits
    extract_anthropic_rate_limits,  # AnthropicRateLimits  
    extract_openai_rate_limits,     # OpenAIRateLimits
)

# All work on raw_headers from RateLimitInfo
cerebras = extract_cerebras_rate_limits(response.rate_limit.raw_headers)
anthropic = extract_anthropic_rate_limits(response.rate_limit.raw_headers)
openai = extract_openai_rate_limits(response.rate_limit.raw_headers)
```

Each returns a provider-specific dataclass with additional methods:

- **CerebrasRateLimits**: `get_most_restrictive_bucket()`, `get_suggested_wait_seconds()`
- **AnthropicRateLimits**: `get_next_reset()`, `get_seconds_until_reset()`
- **OpenAIRateLimits**: `get_seconds_until_reset()` (parses duration strings like "6m30s")

---

## Backend Limitations

### AISuite

AISuite does not expose HTTP response headers from the underlying providers. When using the AISuite backend:

- `RateLimitInfo.raw_headers` will be empty
- Provider-specific extractors will return objects with all `None` values
- Rate limits must be handled via error responses (429 status) rather than proactive header inspection
- Cache token counts will be zero (not available)
- Cost calculation uses rough estimation instead of accurate model-specific pricing

**Recommendation**: Use the LiteLLM backend for full metrics support.

---

## Cross-Agent Compatibility

### smolagents

smolagents exposes:
- `ChatMessage.token_usage: TokenUsage` with `input_tokens`, `output_tokens`, `total_tokens`
- `ChatMessage.raw: Any` containing the raw API response

**Adapter mapping:**
```python
def from_smolagents(chat_message: ChatMessage) -> AgentResponse:
    usage = None
    if chat_message.token_usage:
        usage = UsageInfo(
            input_tokens=chat_message.token_usage.input_tokens,
            output_tokens=chat_message.token_usage.output_tokens,
            total_tokens=chat_message.token_usage.total_tokens,
        )
    
    # Extract rate limits from raw response if available
    rate_limit = None
    if chat_message.raw and hasattr(chat_message.raw, '_response_headers'):
        rate_limit = extract_rate_limit_info(
            _normalize_headers(chat_message.raw._response_headers)
        )
    
    return AgentResponse(
        content=chat_message.content,
        usage=usage,
        rate_limit=rate_limit,
        finish_reason=FinishReason.STOP,
        raw_response=chat_message.raw,
    )
```

### pi-agent (pi-mono)

pi-agent exposes:
- `AssistantMessage.usage: Usage` with `input`, `output`, `cacheRead`, `cacheWrite`, `totalTokens`, `cost`
- `AssistantMessage.stopReason: StopReason` and `errorMessage?: string`

**Adapter mapping:**
```python
def from_pi_agent(assistant_message: AssistantMessage) -> AgentResponse:
    cost = CostInfo(
        input=assistant_message.usage.cost.input,
        output=assistant_message.usage.cost.output,
        cache_read=assistant_message.usage.cost.cacheRead,
        cache_write=assistant_message.usage.cost.cacheWrite,
        total=assistant_message.usage.cost.total,
    )
    usage = UsageInfo(
        input_tokens=assistant_message.usage.input,
        output_tokens=assistant_message.usage.output,
        total_tokens=assistant_message.usage.totalTokens,
        cache_read_tokens=assistant_message.usage.cacheRead,
        cache_write_tokens=assistant_message.usage.cacheWrite,
        cost=cost,
    )
    
    # Map stopReason to FinishReason
    finish_map = {
        "stop": FinishReason.STOP,
        "length": FinishReason.LENGTH,
        "toolUse": FinishReason.TOOL_USE,
        "error": FinishReason.ERROR,
        "aborted": FinishReason.ABORTED,
    }
    finish_reason = finish_map.get(assistant_message.stopReason, FinishReason.STOP)
    
    error = None
    if assistant_message.stopReason in ("error", "aborted"):
        error = ErrorInfo(
            error_type=assistant_message.stopReason,
            message=assistant_message.errorMessage or "",
            retryable=(assistant_message.stopReason != "aborted"),
        )
    
    return AgentResponse(
        content=extract_text_content(assistant_message.content),
        usage=usage,
        finish_reason=finish_reason,
        error=error,
    )
```

---

## Comparison Table

| Feature | flatagents | smolagents | pi-agent |
|---------|------------|------------|----------|
| Input tokens | ✅ `usage.input_tokens` | ✅ `token_usage.input_tokens` | ✅ `usage.input` |
| Output tokens | ✅ `usage.output_tokens` | ✅ `token_usage.output_tokens` | ✅ `usage.output` |
| Cache tokens | ✅ `usage.cache_read/write_tokens` | ❌ | ✅ `usage.cacheRead/Write` |
| Cost tracking | ✅ `usage.cost` (per-field) | ❌ | ✅ `usage.cost` (per-field) |
| Finish reason | ✅ `finish_reason` | ❌ | ✅ `stopReason` |
| Rate limit headers | ✅ normalized + raw | ❌ (raw only) | ❌ |
| Retry-after | ✅ `rate_limit.retry_after` | ❌ | ✅ `maxRetryDelayMs` option |
| Error info | ✅ `ErrorInfo` | ❌ (exceptions) | ✅ `stopReason` + `errorMessage` |
| Raw response | ✅ `raw_response` | ✅ `raw` | ❌ (embedded in message) |

---

## Usage Examples

### Basic Usage Check

```python
response = await agent.call(prompt="Hello")

if response.success:
    print(f"Output: {response.content}")
    print(f"Tokens: {response.usage.input_tokens}→{response.usage.output_tokens}")
    print(f"Finish: {response.finish_reason}")
else:
    print(f"Error: {response.error.error_type}: {response.error.message}")
    if response.error.retryable:
        delay = response.rate_limit.get_retry_delay() or 60
        print(f"Retryable, wait {delay}s")
```

### Cache Token Monitoring

```python
response = await agent.call(prompt="Hello")

if response.usage:
    usage = response.usage
    print(f"Input: {usage.input_tokens} tokens")
    print(f"Output: {usage.output_tokens} tokens")
    print(f"Cache read: {usage.cache_read_tokens} tokens")
    print(f"Cache write: {usage.cache_write_tokens} tokens")
    
    if usage.cost:
        print(f"Cost: ${usage.cost.total:.6f}")
        print(f"  Input: ${usage.cost.input:.6f}")
        print(f"  Output: ${usage.cost.output:.6f}")
```

### Rate Limit Monitoring

```python
response = await agent.call(prompt="Generate text")

if response.rate_limit:
    rl = response.rate_limit
    print(f"Remaining: {rl.remaining_requests} requests, {rl.remaining_tokens} tokens")
    
    if rl.is_limited():
        delay = rl.get_retry_delay() or 60
        print(f"Rate limited, waiting {delay}s")
        await asyncio.sleep(delay)
```

### Provider-Specific Limits (Cerebras)

```python
from flatagents import extract_cerebras_rate_limits

response = await agent.call(prompt="Fast inference")

if response.rate_limit and response.rate_limit.raw_headers:
    cerebras = extract_cerebras_rate_limits(response.rate_limit.raw_headers)
    
    # Check time-bucketed limits
    bucket = cerebras.get_most_restrictive_bucket()
    if bucket:
        wait = cerebras.get_suggested_wait_seconds()
        print(f"{bucket} limit hit, waiting {wait}s")
```

### Finish Reason Handling

```python
from flatagents import FinishReason

response = await agent.call(prompt="Generate text")

match response.finish_reason:
    case FinishReason.STOP:
        print("Completed normally")
    case FinishReason.LENGTH:
        print("Hit max tokens - response may be truncated")
    case FinishReason.TOOL_USE:
        print(f"Tool calls: {response.tool_calls}")
    case FinishReason.CONTENT_FILTER:
        print("Content was filtered")
    case FinishReason.ERROR:
        print(f"Error: {response.error.message}")
```

---

## OpenTelemetry Metrics

When OTEL is enabled, flatagents records:

| Metric | Type | Description |
|--------|------|-------------|
| `flatagents.agent.input_tokens` | Counter | Cumulative input tokens |
| `flatagents.agent.output_tokens` | Counter | Cumulative output tokens |
| `flatagents.agent.tokens` | Counter | Cumulative total tokens |
| `flatagents.agent.cache_read_tokens` | Counter | Cumulative cache read tokens |
| `flatagents.agent.cache_write_tokens` | Counter | Cumulative cache write tokens |
| `flatagents.agent.cost` | Counter | Cumulative estimated cost |
| `flatagents.agent.duration` | Histogram | Agent execution duration (ms) |
| `flatagents.agent.executions` | Counter | Execution count by status |
| `flatagents.ratelimit.remaining_requests` | Gauge | Current remaining requests |
| `flatagents.ratelimit.remaining_tokens` | Gauge | Current remaining tokens |
| `flatagents.ratelimit.limit_requests` | Gauge | Rate limit for requests |
| `flatagents.ratelimit.limit_tokens` | Gauge | Rate limit for tokens |

---

## Design Principles

1. **Provider-agnostic core**: Normalized fields work across all providers
2. **Raw preservation**: `raw_headers` allows provider-specific parsing when needed
3. **No exceptions for rate limits**: Return `ErrorInfo` with `retryable=True`, let caller decide
4. **Composable**: Works standalone or with flatmachines orchestration
5. **Adapter-friendly**: Structure maps cleanly to/from smolagents and pi-agent
6. **Backwards compatible**: `estimated_cost` property preserved for existing code

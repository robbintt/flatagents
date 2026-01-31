__version__ = "0.9.0"

from .baseagent import (
    # Base agent (abstract, for multi-step agents)
    FlatAgent as BaseFlatAgent,
    # LLM Backends
    LLMBackend,
    LiteLLMBackend,
    AISuiteBackend,
    # Extractors
    Extractor,
    FreeExtractor,
    FreeThinkingExtractor,
    StructuredExtractor,
    ToolsExtractor,
    RegexExtractor,
    # MCP Types
    MCPToolProvider,
    ToolCall,
    AgentResponse,
)
from .flatagent import FlatAgent
from .flatmachine import FlatMachine
from .hooks import (
    MachineHooks,
    LoggingHooks,
    MetricsHooks,
    CompositeHooks,
)
from .actions import (
    SubprocessInvoker,
    launch_machine,
)
from .expressions import get_expression_engine, ExpressionEngine
from .execution import (
    ExecutionType,
    DefaultExecution,
    ParallelExecution,
    RetryExecution,
    MDAPVotingExecution,
    get_execution_type,
)
from .validation import (
    validate_flatagent_config,
    validate_flatmachine_config,
    get_flatagent_schema,
    get_flatmachine_schema,
    get_asset,
    ValidationWarning,
)
from .monitoring import (
    setup_logging,
    get_logger,
    get_meter,
    AgentMonitor,
    track_operation,
)
from .backends import (
    ResultBackend,
    InMemoryResultBackend,
    LaunchIntent,
    make_uri,
    parse_uri,
    get_default_result_backend,
    reset_default_result_backend,
)
from .persistence import (
    PersistenceBackend,
    LocalFileBackend,
    MemoryBackend,
    CheckpointManager,
    MachineSnapshot,
)
from .profiles import (
    ProfileManager,
    resolve_model_config,
)
from .distributed import (
    # Types
    WorkerRegistration,
    WorkerRecord,
    WorkerFilter,
    WorkItem,
    # Protocols
    RegistrationBackend,
    WorkBackend,
    WorkPool,
    # Memory implementations
    MemoryRegistrationBackend,
    MemoryWorkBackend,
    # SQLite implementations
    SQLiteRegistrationBackend,
    SQLiteWorkBackend,
    # Factory functions
    create_registration_backend,
    create_work_backend,
)
from .distributed_hooks import DistributedWorkerHooks

__all__ = [
    "__version__",
    # Main agent class
    "FlatAgent",
    # Base agent for custom multi-step agents
    "BaseFlatAgent",
    # State machine orchestration
    "FlatMachine",
    # Machine hooks
    "MachineHooks",
    "LoggingHooks",
    "MetricsHooks",
    "CompositeHooks",
    # Expression engines
    "ExpressionEngine",
    "get_expression_engine",
    # Execution types
    "ExecutionType",
    "DefaultExecution",
    "ParallelExecution",
    "RetryExecution",
    "MDAPVotingExecution",
    "get_execution_type",
    # LLM Backends
    "LLMBackend",
    "LiteLLMBackend",
    "AISuiteBackend",
    # Extractors
    "Extractor",
    "FreeExtractor",
    "FreeThinkingExtractor",
    "StructuredExtractor",
    "ToolsExtractor",
    "RegexExtractor",
    # MCP Types
    "MCPToolProvider",
    "ToolCall",
    "AgentResponse",
    # Validation
    "validate_flatagent_config",
    "validate_flatmachine_config",
    "get_flatagent_schema",
    "get_flatmachine_schema",
    "get_asset",
    "ValidationWarning",
    # Monitoring & Observability
    "setup_logging",
    "get_logger",
    "get_meter",
    "AgentMonitor",
    "track_operation",
    # Result Backends (v0.4.0)
    "ResultBackend",
    "InMemoryResultBackend",
    "LaunchIntent",
    "make_uri",
    "parse_uri",
    "get_default_result_backend",
    "reset_default_result_backend",
    # Persistence Backends
    "PersistenceBackend",
    "LocalFileBackend",
    "MemoryBackend",
    "CheckpointManager",
    "MachineSnapshot",
    # Model Profiles
    "ProfileManager",
    "resolve_model_config",
    # Distributed Backends (v0.9.0)
    "WorkerRegistration",
    "WorkerRecord",
    "WorkerFilter",
    "WorkItem",
    "RegistrationBackend",
    "WorkBackend",
    "WorkPool",
    "MemoryRegistrationBackend",
    "MemoryWorkBackend",
    "SQLiteRegistrationBackend",
    "SQLiteWorkBackend",
    "create_registration_backend",
    "create_work_backend",
    # Subprocess execution (v0.9.0)
    "SubprocessInvoker",
    "launch_machine",
    # Distributed hooks (v0.9.0)
    "DistributedWorkerHooks",
]

__version__ = "0.10.0"

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
from .profiles import (
    ProfileManager,
    resolve_model_config,
)
from .validation import (
    validate_flatagent_config,
    get_flatagent_schema,
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

__all__ = [
    "__version__",
    # Main agent class
    "FlatAgent",
    # Base agent for custom multi-step agents
    "BaseFlatAgent",
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
    "get_flatagent_schema",
    "get_asset",
    "ValidationWarning",
    # Monitoring & Observability
    "setup_logging",
    "get_logger",
    "get_meter",
    "AgentMonitor",
    "track_operation",
    # Model Profiles
    "ProfileManager",
    "resolve_model_config",
]

# Optional compatibility exports for machine orchestration
try:  # pragma: no cover - optional dependency
    from flatmachines import (
        FlatMachine,
        MachineHooks,
        LoggingHooks,
        MetricsHooks,
        CompositeHooks,
        WebhookHooks,
        ExpressionEngine,
        get_expression_engine,
        ExecutionType,
        DefaultExecution,
        ParallelExecution,
        RetryExecution,
        MDAPVotingExecution,
        get_execution_type,
        validate_flatmachine_config,
        get_flatmachine_schema,
        ResultBackend,
        InMemoryResultBackend,
        LaunchIntent,
        make_uri,
        parse_uri,
        get_default_result_backend,
        reset_default_result_backend,
        PersistenceBackend,
        LocalFileBackend,
        MemoryBackend,
        CheckpointManager,
        MachineSnapshot,
        ExecutionLock,
        LocalFileLock,
        NoOpLock,
        SubprocessInvoker,
        launch_machine,
        DistributedWorkerHooks,
        WorkerRegistration,
        WorkerRecord,
        WorkerFilter,
        WorkItem,
        RegistrationBackend,
        WorkBackend,
        WorkPool,
        MemoryRegistrationBackend,
        MemoryWorkBackend,
        SQLiteRegistrationBackend,
        SQLiteWorkBackend,
        create_registration_backend,
        create_work_backend,
    )

    __all__.extend([
        "FlatMachine",
        "MachineHooks",
        "LoggingHooks",
        "MetricsHooks",
        "CompositeHooks",
        "WebhookHooks",
        "ExpressionEngine",
        "get_expression_engine",
        "ExecutionType",
        "DefaultExecution",
        "ParallelExecution",
        "RetryExecution",
        "MDAPVotingExecution",
        "get_execution_type",
        "validate_flatmachine_config",
        "get_flatmachine_schema",
        "ResultBackend",
        "InMemoryResultBackend",
        "LaunchIntent",
        "make_uri",
        "parse_uri",
        "get_default_result_backend",
        "reset_default_result_backend",
        "PersistenceBackend",
        "LocalFileBackend",
        "MemoryBackend",
        "CheckpointManager",
        "MachineSnapshot",
        "ExecutionLock",
        "LocalFileLock",
        "NoOpLock",
        "SubprocessInvoker",
        "launch_machine",
        "DistributedWorkerHooks",
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
    ])
except ImportError:
    pass

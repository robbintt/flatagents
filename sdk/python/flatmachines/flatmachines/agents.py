"""Agent executor interfaces and adapter registry for FlatMachines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Protocol


@dataclass
class AgentResult:
    """Normalized result from an agent execution."""

    output: Optional[Dict[str, Any]] = None
    content: Optional[str] = None
    raw: Any = None
    usage: Optional[Dict[str, Any]] = None
    cost: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def output_payload(self) -> Dict[str, Any]:
        if self.output is not None:
            return self.output
        if self.content is not None:
            return {"content": self.content}
        return {}


class AgentExecutor(Protocol):
    """Protocol for running a single agent call."""

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        ...

    @property
    def metadata(self) -> Dict[str, Any]:  # Optional metadata for execution strategies
        ...


@dataclass
class AgentRef:
    """Normalized agent reference for adapter resolution."""

    type: str
    ref: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


@dataclass
class AgentAdapterContext:
    config_dir: str
    settings: Dict[str, Any]
    machine_name: str
    profiles_file: Optional[str] = None
    profiles_dict: Optional[Dict[str, Any]] = None


class AgentAdapter(Protocol):
    """Adapter interface used to build agent executors."""

    type_name: str

    def create_executor(
        self,
        *,
        agent_name: str,
        agent_ref: AgentRef,
        context: AgentAdapterContext,
    ) -> AgentExecutor:
        ...


class AgentAdapterRegistry:
    """Registry mapping adapter type names to adapter instances."""

    def __init__(self, adapters: Optional[Iterable[AgentAdapter]] = None):
        self._adapters: Dict[str, AgentAdapter] = {}
        if adapters:
            for adapter in adapters:
                self.register(adapter)

    def register(self, adapter: AgentAdapter) -> None:
        self._adapters[adapter.type_name] = adapter

    def get(self, type_name: str) -> AgentAdapter:
        if type_name not in self._adapters:
            raise KeyError(f"No agent adapter registered for type '{type_name}'")
        return self._adapters[type_name]

    def create_executor(
        self,
        *,
        agent_name: str,
        agent_ref: AgentRef,
        context: AgentAdapterContext,
    ) -> AgentExecutor:
        adapter = self.get(agent_ref.type)
        return adapter.create_executor(
            agent_name=agent_name,
            agent_ref=agent_ref,
            context=context,
        )


DEFAULT_AGENT_TYPE = "flatagent"


def normalize_agent_ref(raw_ref: Any) -> AgentRef:
    """Normalize agent reference into AgentRef.

    Backward compatibility:
      - string -> type=flatagent, ref=string
      - dict with spec: flatagent -> type=flatagent, config=dict
    """
    if isinstance(raw_ref, str):
        return AgentRef(type=DEFAULT_AGENT_TYPE, ref=raw_ref)

    if isinstance(raw_ref, dict):
        if "type" in raw_ref:
            return AgentRef(
                type=raw_ref["type"],
                ref=raw_ref.get("ref"),
                config=raw_ref.get("config"),
            )

        if raw_ref.get("spec") == "flatagent":
            return AgentRef(type=DEFAULT_AGENT_TYPE, config=raw_ref)

    raise ValueError(
        "Invalid agent reference. Expected string path or {type, ref/config}."
    )


def coerce_agent_result(value: Any) -> AgentResult:
    if isinstance(value, AgentResult):
        return value
    if isinstance(value, dict):
        return AgentResult(output=value, raw=value)
    if value is None:
        return AgentResult()
    return AgentResult(content=str(value), raw=value)

"""FlatAgent adapter for FlatMachines."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..agents import AgentAdapter, AgentAdapterContext, AgentExecutor, AgentRef, AgentResult

try:
    from flatagents.flatagent import FlatAgent
    from flatagents.profiles import (
        discover_profiles_file,
        load_profiles_from_file,
        resolve_profiles_with_fallback,
    )
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError("flatagents is required for FlatAgentAdapter") from exc


class FlatAgentExecutor(AgentExecutor):
    def __init__(self, agent: FlatAgent):
        self._agent = agent

    @property
    def metadata(self) -> Dict[str, Any]:
        return getattr(self._agent, "metadata", {})

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        pre_calls = self._agent.total_api_calls
        pre_cost = self._agent.total_cost

        result = await self._agent.call(**input_data)

        delta_calls = self._agent.total_api_calls - pre_calls
        delta_cost = self._agent.total_cost - pre_cost

        return AgentResult(
            output=result.output,
            content=result.content,
            raw=result,
            usage={"api_calls": delta_calls},
            cost=delta_cost,
            metadata=getattr(self._agent, "metadata", None),
        )


class FlatAgentAdapter(AgentAdapter):
    type_name = "flatagent"

    def create_executor(
        self,
        *,
        agent_name: str,
        agent_ref: AgentRef,
        context: AgentAdapterContext,
    ) -> AgentExecutor:
        profiles_file = discover_profiles_file(context.config_dir, context.profiles_file)
        own_profiles = load_profiles_from_file(profiles_file) if profiles_file else None
        profiles_dict = resolve_profiles_with_fallback(own_profiles, context.profiles_dict)

        if agent_ref.ref:
            return FlatAgentExecutor(
                FlatAgent(
                    config_file=self._resolve_ref(agent_ref.ref, context),
                    profiles_dict=profiles_dict,
                )
            )
        if agent_ref.config:
            return FlatAgentExecutor(
                FlatAgent(
                    config_dict=agent_ref.config,
                    profiles_dict=profiles_dict,
                )
            )
        raise ValueError(f"FlatAgent reference missing ref/config for agent '{agent_name}'")

    def _resolve_ref(self, ref: str, context: AgentAdapterContext) -> str:
        import os

        if os.path.isabs(ref):
            return ref
        return os.path.join(context.config_dir, ref)

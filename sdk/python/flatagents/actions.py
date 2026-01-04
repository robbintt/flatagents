from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .flatmachine import FlatMachine

logger = logging.getLogger(__name__)

class Action(ABC):
    """
    Base class for state actions (when state has 'action:' key).
    """
    
    @abstractmethod
    async def execute(
        self,
        action_name: str,
        context: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the action.
        Returns modified context.
        """
        pass

class HookAction(Action):
    """
    Default action: delegates to machine hooks (on_action).
    """
    
    def __init__(self, hooks):
        self.hooks = hooks
        
    async def execute(
        self,
        action_name: str,
        context: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self.hooks.on_action(action_name, context)

# -------------------------------------------------------------------------
# Machine Invokers (Graph Execution)
# -------------------------------------------------------------------------

class MachineInvoker(ABC):
    """
    Interface for invoking other machines (graph execution).
    """
    
    @abstractmethod
    async def invoke(
        self,
        caller_machine: 'FlatMachine',
        target_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Invoke another machine.
        Returns output (if sync) or raises exception (if async/detached).
        """
        pass

class InlineInvoker(MachineInvoker):
    """
    Default v1 Invoker.
    Runs target machine in same process (synchronous await).
    """
    
    async def invoke(
        self,
        caller_machine: 'FlatMachine',
        target_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        from .flatmachine import FlatMachine  # lazy import to avoid cycle
        
        # Deterministic execution ID for target: {parent_id}:child:{target_machine_name}
        # This allows resume logic to find the same child checkpoint
        target_id = f"{caller_machine.execution_id}:child:{target_config.get('name', 'unknown')}"
        
        logger.info(f"Invoking child machine: {target_config.get('name')} (ID: {target_id})")
        
        # Determine if we should reuse parent's persistence/lock
        # (Usually yes for inline execution)
        target = FlatMachine(
            config=target_config, # Passing dict directly means dynamic config
            # Pass down parent's backend/lock to keep everything in same storage
            persistence=caller_machine.persistence,
            lock=caller_machine.lock
        )
        
        # Execute child
        # Note: resume_from=target_id ensures if we crash and retry, we pick up
        # where the child left off (or use its existing result)
        return await target.execute(
            input=context,
            resume_from=target_id
        )

class CloudInvoker(MachineInvoker):
    """STUB: Future AWS Step Functions / Lambda invoker."""
    async def invoke(self, caller, target, context):
        raise NotImplementedError("Distributed execution is a v2 feature")

class HttpInvoker(MachineInvoker):
    """STUB: Future REST/Webhook invoker."""
    async def invoke(self, caller, target, context):
        raise NotImplementedError("HTTP execution is a v2 feature")

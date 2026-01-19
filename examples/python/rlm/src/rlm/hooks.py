"""
RLM Hooks for FlatMachine Integration

Provides custom action handlers for:
- Initializing the REPL with context
- Executing exploration code
- Extracting chunks for processing
- Error handling and logging
"""

import logging
from typing import Any

from flatagents import MachineHooks
from .repl import REPLExecutor

logger = logging.getLogger(__name__)


class RLMHooks(MachineHooks):
    """
    Hooks for the main RLM machine.

    Handles REPL initialization, code execution, and error logging.
    """

    def __init__(self):
        """Initialize the RLM hooks with a REPL executor."""
        self.repl: REPLExecutor | None = None
        self._initialized = False

    def on_machine_start(self, context: dict[str, Any]) -> dict[str, Any]:
        """Initialize when machine starts."""
        logger.info(f"RLM starting with context of {context.get('context_length', 0)} characters")
        return context

    def on_machine_end(self, context: dict[str, Any], final_output: dict[str, Any]) -> dict[str, Any]:
        """Clean up when machine ends."""
        if self.repl:
            stats = self.repl.get_statistics()
            logger.info(f"RLM completed. REPL stats: {stats}")
        return context

    def on_action(self, action_name: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle custom actions."""
        if action_name == "init_repl":
            return self._init_repl(context)
        elif action_name == "execute_repl":
            return self._execute_repl(context)
        elif action_name == "log_error":
            return self._log_error(context)
        return context

    def _init_repl(self, context: dict[str, Any]) -> dict[str, Any]:
        """Initialize the REPL with the context content."""
        if self._initialized:
            logger.debug("REPL already initialized")
            return context

        self.repl = REPLExecutor()
        content = context.get("context_content", "")

        if not content:
            logger.warning("No context content provided")
            return context

        self.repl.set_context(content)
        self._initialized = True

        logger.info(f"REPL initialized with {len(content)} character context")

        # Add context metadata
        context["content_type"] = self._detect_content_type(content)
        context["structure_summary"] = self._get_structure_summary(content)

        return context

    def _execute_repl(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute exploration code in the REPL."""
        if not self.repl:
            logger.error("REPL not initialized")
            context["last_error"] = "REPL not initialized"
            return context

        # Get the code from the last explorer agent output
        code = context.get("code", "")
        if not code:
            logger.warning("No code to execute")
            return context

        logger.info(f"Executing REPL code:\n{code[:200]}...")

        result = self.repl.execute(code)

        # Build execution record
        execution_record = {
            "code": code,
            "result": result.get("output") or result.get("return_value") or result.get("error"),
            "success": result.get("success", False)
        }

        # Update exploration history
        history = context.get("exploration_history", [])
        history.append(execution_record)
        context["exploration_history"] = history

        if result.get("success"):
            logger.info(f"REPL execution successful: {str(result.get('return_value', ''))[:100]}")
        else:
            logger.warning(f"REPL execution failed: {result.get('error', '')[:200]}")
            context["last_error"] = result.get("error", "Unknown error")

        # Update context with exploration results if ready
        if context.get("ready_to_answer"):
            context["exploration_findings"] = context.get("findings", "")

        # Update suggested chunks
        suggested = context.get("suggested_chunks")
        if suggested:
            context["suggested_chunks"] = suggested

        return context

    def _log_error(self, context: dict[str, Any]) -> dict[str, Any]:
        """Log an error and prepare for retry or fallback."""
        error = context.get("last_error", "Unknown error")
        round_num = context.get("exploration_round", 0)
        logger.error(f"Exploration error in round {round_num}: {error}")
        return context

    def _detect_content_type(self, content: str) -> str:
        """Detect the type of content (code, document, data, etc.)."""
        # Simple heuristics
        if content.strip().startswith('{') or content.strip().startswith('['):
            return "json_data"
        elif '```' in content or 'def ' in content or 'class ' in content:
            return "code"
        elif content.count('\n') > 100 and any(c in content for c in ['#', '##', '###']):
            return "markdown_document"
        elif '\t' in content and content.count('\n') > 50:
            return "tabular_data"
        elif content.count('.') > content.count('\n') / 2:
            return "prose_document"
        else:
            return "mixed_content"

    def _get_structure_summary(self, content: str) -> str:
        """Get a brief summary of the content structure."""
        lines = content.split('\n')
        line_count = len(lines)
        char_count = len(content)

        # Sample beginning and end
        sample_start = content[:500] if len(content) > 500 else content
        sample_end = content[-500:] if len(content) > 500 else ""

        return f"{line_count} lines, {char_count} chars. Starts with: {sample_start[:100]}..."


class ChunkProcessorHooks(MachineHooks):
    """
    Hooks for the chunk processor machine.

    Handles chunk extraction and error logging.
    """

    def on_action(self, action_name: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle custom actions."""
        if action_name == "extract_chunk":
            return self._extract_chunk(context)
        elif action_name == "log_chunk_error":
            return self._log_chunk_error(context)
        return context

    def _extract_chunk(self, context: dict[str, Any]) -> dict[str, Any]:
        """Extract the specified chunk from the full context."""
        full_content = context.get("context_content", "")
        sub_task = context.get("sub_task", {})

        start = sub_task.get("chunk_start", 0)
        end = sub_task.get("chunk_end", len(full_content))

        # Ensure valid bounds
        start = max(0, start)
        end = min(len(full_content), end)

        chunk = full_content[start:end]
        context["chunk_content"] = chunk

        logger.info(f"Extracted chunk [{start}:{end}] ({len(chunk)} chars) for sub-task: {sub_task.get('id', 'unknown')}")

        return context

    def _log_chunk_error(self, context: dict[str, Any]) -> dict[str, Any]:
        """Log a chunk processing error."""
        error = context.get("last_error", "Unknown error")
        sub_task = context.get("sub_task", {})
        logger.error(f"Chunk processing error for sub-task {sub_task.get('id', 'unknown')}: {error}")
        return context

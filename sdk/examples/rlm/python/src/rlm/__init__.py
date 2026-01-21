"""
Recursive Language Model (RLM) Example

Implementation based on arXiv:2512.24601 - "Recursive Language Models"
by Zhang, Kraska, and Khattab.

This module provides a FlatMachine-based implementation of RLM that enables
LLMs to handle arbitrarily long contexts through:
1. REPL-based exploration of the context
2. Recursive decomposition of complex tasks
3. Parallel processing of context chunks
4. Synthesis of sub-task results
"""

from .hooks import RLMHooks
from .repl import REPLExecutor

__all__ = ["RLMHooks", "REPLExecutor"]

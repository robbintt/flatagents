"""
Abstract Pipeline: Normalize raw teacher MCP scripts.

This pipeline takes raw MCP tool definitions and normalizes them
into a consistent format for further processing.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import re
import json


@dataclass
class RawToolDefinition:
    """A raw tool definition from a teacher script."""
    name: str
    source: str  # Original source code or definition
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedTool:
    """A normalized tool definition."""
    name: str
    description: str
    parameters: Dict[str, Any]
    return_type: str
    source: str
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)


class AbstractPipeline:
    """
    Pipeline for abstracting/normalizing raw MCP scripts.
    
    Takes raw tool definitions and converts them to a normalized format
    that can be used by subsequent pipeline stages.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    def process(self, raw_tools: List[RawToolDefinition]) -> List[NormalizedTool]:
        """
        Process a list of raw tool definitions.
        
        Args:
            raw_tools: List of raw tool definitions
            
        Returns:
            List of normalized tools
        """
        normalized = []
        for raw_tool in raw_tools:
            result = self.normalize_tool(raw_tool)
            if result:
                normalized.append(result)
        return normalized
    
    def normalize_tool(self, raw_tool: RawToolDefinition) -> Optional[NormalizedTool]:
        """
        Normalize a single raw tool definition.
        
        Args:
            raw_tool: Raw tool definition
            
        Returns:
            Normalized tool or None if parsing failed
        """
        # Extract description from docstring
        description = self._extract_description(raw_tool.source)
        
        # Extract parameters from function signature or metadata
        parameters = self._extract_parameters(raw_tool)
        
        # Infer return type
        return_type = self._infer_return_type(raw_tool)
        
        # Infer category
        category = self._infer_category(raw_tool)
        
        return NormalizedTool(
            name=self._normalize_name(raw_tool.name),
            description=description,
            parameters=parameters,
            return_type=return_type,
            source=raw_tool.source,
            category=category,
            metadata=raw_tool.metadata,
        )
    
    def _normalize_name(self, name: str) -> str:
        """Convert name to snake_case."""
        # Convert camelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    
    def _extract_description(self, source: str) -> str:
        """Extract description from source docstring."""
        # Match triple-quoted docstrings
        docstring_match = re.search(r'"""(.*?)"""', source, re.DOTALL)
        if docstring_match:
            return docstring_match.group(1).strip().split("\n")[0]
        
        # Match single-quoted docstrings
        docstring_match = re.search(r"'''(.*?)'''", source, re.DOTALL)
        if docstring_match:
            return docstring_match.group(1).strip().split("\n")[0]
        
        return ""
    
    def _extract_parameters(self, raw_tool: RawToolDefinition) -> Dict[str, Any]:
        """Extract parameters from tool definition."""
        # Check if parameters are in metadata
        if "parameters" in raw_tool.metadata:
            return raw_tool.metadata["parameters"]
        
        # Try to parse from function signature
        params = {}
        
        # Match function definition with type hints
        func_match = re.search(
            r"def\s+\w+\s*\((.*?)\)",
            raw_tool.source,
            re.DOTALL
        )
        
        if func_match:
            param_str = func_match.group(1)
            # Parse individual parameters
            for param in param_str.split(","):
                param = param.strip()
                if not param or param == "self":
                    continue
                
                # Parse name: type = default
                param_match = re.match(
                    r"(\w+)\s*:\s*([^=]+)(?:\s*=\s*(.+))?",
                    param
                )
                if param_match:
                    name, type_hint, default = param_match.groups()
                    params[name] = {
                        "type": type_hint.strip(),
                        "default": default.strip() if default else None,
                    }
                else:
                    # Simple parameter without type hint
                    name = param.split("=")[0].strip()
                    if name:
                        params[name] = {"type": "Any"}
        
        return params
    
    def _infer_return_type(self, raw_tool: RawToolDefinition) -> str:
        """Infer return type from source."""
        # Check metadata
        if "return_type" in raw_tool.metadata:
            return raw_tool.metadata["return_type"]
        
        # Look for return type annotation
        match = re.search(r"->\s*([^:]+):", raw_tool.source)
        if match:
            return match.group(1).strip()
        
        return "Any"
    
    def _infer_category(self, raw_tool: RawToolDefinition) -> str:
        """Infer category from tool name or metadata."""
        if "category" in raw_tool.metadata:
            return raw_tool.metadata["category"]
        
        name = raw_tool.name.lower()
        
        # Infer from common patterns
        if any(x in name for x in ["file", "read", "write", "path"]):
            return "file_operations"
        if any(x in name for x in ["test", "check", "validate", "assert"]):
            return "testing"
        if any(x in name for x in ["search", "find", "query"]):
            return "search"
        if any(x in name for x in ["parse", "extract", "convert"]):
            return "parsing"
        
        return "general"

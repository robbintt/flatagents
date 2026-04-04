"""
MCP Box dataclass definitions.

These define the core structures for MCPBox, ToolSpec, ValidatorSpec, and FallbackPolicy.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json


@dataclass
class FallbackPolicy:
    """Defines fallback behavior when a tool fails."""
    
    retry_count: int = 3
    retry_delay_seconds: float = 1.0
    fallback_tool: Optional[str] = None
    on_failure: str = "error"  # "error", "skip", "fallback"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "retry_count": self.retry_count,
            "retry_delay_seconds": self.retry_delay_seconds,
            "fallback_tool": self.fallback_tool,
            "on_failure": self.on_failure,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FallbackPolicy":
        return cls(
            retry_count=data.get("retry_count", 3),
            retry_delay_seconds=data.get("retry_delay_seconds", 1.0),
            fallback_tool=data.get("fallback_tool"),
            on_failure=data.get("on_failure", "error"),
        )


@dataclass
class ValidatorSpec:
    """Defines validation rules for tool inputs/outputs."""
    
    name: str
    description: str = ""
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    custom_validator: Optional[str] = None  # Python function path
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "custom_validator": self.custom_validator,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidatorSpec":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            input_schema=data.get("input_schema"),
            output_schema=data.get("output_schema"),
            custom_validator=data.get("custom_validator"),
        )


@dataclass
class ToolSpec:
    """Specification for an MCP tool."""
    
    name: str
    description: str
    function: str  # Python function path (e.g., "mcp_box.tools.file_ops.file_search")
    parameters: Dict[str, Any] = field(default_factory=dict)
    return_type: str = "string"
    category: str = "general"
    validator: Optional[ValidatorSpec] = None
    fallback_policy: Optional[FallbackPolicy] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "function": self.function,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "category": self.category,
            "validator": self.validator.to_dict() if self.validator else None,
            "fallback_policy": self.fallback_policy.to_dict() if self.fallback_policy else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolSpec":
        return cls(
            name=data["name"],
            description=data["description"],
            function=data["function"],
            parameters=data.get("parameters", {}),
            return_type=data.get("return_type", "string"),
            category=data.get("category", "general"),
            validator=ValidatorSpec.from_dict(data["validator"]) if data.get("validator") else None,
            fallback_policy=FallbackPolicy.from_dict(data["fallback_policy"]) if data.get("fallback_policy") else None,
            metadata=data.get("metadata", {}),
        )


@dataclass
class MCPBox:
    """
    MCPBox: A containerized collection of MCP tools with metadata.
    
    This is the main structure that bundles tools, validators, and policies
    for use by student agents.
    """
    
    name: str
    version: str
    description: str = ""
    tools: List[ToolSpec] = field(default_factory=list)
    validators: List[ValidatorSpec] = field(default_factory=list)
    default_fallback_policy: Optional[FallbackPolicy] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tools": [t.to_dict() for t in self.tools],
            "validators": [v.to_dict() for v in self.validators],
            "default_fallback_policy": self.default_fallback_policy.to_dict() if self.default_fallback_policy else None,
            "metadata": self.metadata,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize MCPBox to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, path: str) -> None:
        """Save MCPBox to a JSON file."""
        with open(path, "w") as f:
            f.write(self.to_json())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPBox":
        return cls(
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            tools=[ToolSpec.from_dict(t) for t in data.get("tools", [])],
            validators=[ValidatorSpec.from_dict(v) for v in data.get("validators", [])],
            default_fallback_policy=FallbackPolicy.from_dict(data["default_fallback_policy"]) if data.get("default_fallback_policy") else None,
            metadata=data.get("metadata", {}),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "MCPBox":
        """Load MCPBox from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    @classmethod
    def load(cls, path: str) -> "MCPBox":
        """Load MCPBox from a JSON file."""
        with open(path, "r") as f:
            return cls.from_json(f.read())
    
    def get_tool(self, name: str) -> Optional[ToolSpec]:
        """Get a tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None
    
    def get_tools_by_category(self, category: str) -> List[ToolSpec]:
        """Get all tools in a category."""
        return [t for t in self.tools if t.category == category]
    
    def add_tool(self, tool: ToolSpec) -> None:
        """Add a tool to the box."""
        self.tools.append(tool)
    
    def add_validator(self, validator: ValidatorSpec) -> None:
        """Add a validator to the box."""
        self.validators.append(validator)

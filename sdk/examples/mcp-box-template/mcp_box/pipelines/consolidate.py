"""
Consolidate Pipeline: Merge clusters into a single MCPBox.

This pipeline takes tool clusters and consolidates them into
a complete MCPBox configuration.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from mcp_box.schemas.mcp_box import MCPBox, ToolSpec, ValidatorSpec, FallbackPolicy
from mcp_box.pipelines.cluster import ToolCluster
from mcp_box.pipelines.abstract import NormalizedTool


class ConsolidatePipeline:
    """
    Pipeline for consolidating tool clusters into an MCPBox.
    
    Merges all clusters, deduplicates tools, and generates
    the final MCPBox configuration.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.box_name = self.config.get("name", "mcp-box")
        self.box_version = self.config.get("version", "0.1.0")
        self.description = self.config.get("description", "")
    
    def process(
        self, 
        clusters: List[ToolCluster],
        name: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
    ) -> MCPBox:
        """
        Consolidate clusters into an MCPBox.
        
        Args:
            clusters: List of tool clusters
            name: Optional box name override
            version: Optional version override
            description: Optional description override
            
        Returns:
            Complete MCPBox configuration
        """
        # Collect all tools
        all_tools: List[ToolSpec] = []
        seen_names: set = set()
        
        for cluster in clusters:
            for normalized_tool in cluster.tools:
                if normalized_tool.name in seen_names:
                    continue  # Skip duplicates
                
                tool_spec = self._convert_to_tool_spec(normalized_tool)
                all_tools.append(tool_spec)
                seen_names.add(normalized_tool.name)
        
        # Generate validators for each category
        validators = self._generate_validators(clusters)
        
        # Create default fallback policy
        default_policy = FallbackPolicy(
            retry_count=self.config.get("retry_count", 3),
            retry_delay_seconds=self.config.get("retry_delay", 1.0),
            on_failure="error",
        )
        
        # Build metadata
        metadata = {
            "created_at": datetime.now().isoformat(),
            "generator": "mcp-box-template",
            "cluster_count": len(clusters),
            "tool_count": len(all_tools),
        }
        
        if self.config.get("metadata"):
            metadata.update(self.config["metadata"])
        
        return MCPBox(
            name=name or self.box_name,
            version=version or self.box_version,
            description=description or self.description or self._generate_description(clusters),
            tools=all_tools,
            validators=validators,
            default_fallback_policy=default_policy,
            metadata=metadata,
        )
    
    def _convert_to_tool_spec(self, tool: NormalizedTool) -> ToolSpec:
        """Convert a NormalizedTool to a ToolSpec."""
        # Convert parameters to JSON Schema format
        parameters = {}
        for param_name, param_info in tool.parameters.items():
            param_type = param_info.get("type", "string")
            parameters[param_name] = {
                "type": self._python_type_to_json(param_type),
                "description": param_info.get("description", ""),
            }
            if param_info.get("default") is not None:
                parameters[param_name]["default"] = param_info["default"]
        
        # Use source from metadata if available, otherwise construct from name
        # Note: The function path should match the actual tool location
        function_path = tool.metadata.get(
            "function_path",
            f"mcp_box.tools.custom.{tool.name}"  # Default path for custom tools
        )
        
        return ToolSpec(
            name=tool.name,
            description=tool.description,
            function=function_path,
            parameters=parameters,
            return_type=self._python_type_to_json(tool.return_type),
            category=tool.category,
            metadata=tool.metadata,
        )
    
    def _python_type_to_json(self, python_type: str) -> str:
        """Convert Python type hint to JSON Schema type."""
        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
            "None": "null",
            "Any": "string",  # Default to string for Any
        }
        
        # Handle Optional, List, Dict, etc.
        if "Optional" in python_type:
            inner = python_type.replace("Optional[", "").rstrip("]")
            return type_map.get(inner, "string")
        
        if "List" in python_type:
            return "array"
        
        if "Dict" in python_type:
            return "object"
        
        return type_map.get(python_type, "string")
    
    def _generate_validators(self, clusters: List[ToolCluster]) -> List[ValidatorSpec]:
        """Generate validators for each category."""
        validators = []
        seen_categories: set = set()
        
        for cluster in clusters:
            if cluster.category in seen_categories:
                continue
            seen_categories.add(cluster.category)
            
            validators.append(ValidatorSpec(
                name=f"{cluster.category}_validator",
                description=f"Validator for {cluster.category} tools",
            ))
        
        return validators
    
    def _generate_description(self, clusters: List[ToolCluster]) -> str:
        """Generate a description for the MCPBox."""
        if not clusters:
            return "Empty MCP Box"
        
        categories = set(c.category for c in clusters)
        tool_count = sum(len(c.tools) for c in clusters)
        
        return (
            f"MCP Box containing {tool_count} tools across "
            f"{len(categories)} categories: {', '.join(sorted(categories))}"
        )

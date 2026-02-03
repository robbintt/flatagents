"""
Box Builder: Orchestrates the full build pipeline.

Provides a high-level API for building MCPBox configurations
from raw tool definitions.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from mcp_box.schemas.mcp_box import MCPBox, ToolSpec, FallbackPolicy
from mcp_box.pipelines.abstract import AbstractPipeline, RawToolDefinition
from mcp_box.pipelines.cluster import ClusterPipeline
from mcp_box.pipelines.consolidate import ConsolidatePipeline


class BoxBuilder:
    """
    High-level builder for creating MCPBox configurations.
    
    Orchestrates the abstract → cluster → consolidate pipeline.
    
    Usage:
        builder = BoxBuilder(name="my-box", version="1.0.0")
        builder.add_tool_source(name="file_search", source="def file_search(...): ...")
        mcp_box = builder.build()
        mcp_box.save("output/mcp_box.json")
    """
    
    def __init__(
        self,
        name: str = "mcp-box",
        version: str = "0.1.0",
        description: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.config = config or {}
        
        self._raw_tools: List[RawToolDefinition] = []
        self._direct_tools: List[ToolSpec] = []
    
    def add_tool_source(
        self,
        name: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "BoxBuilder":
        """
        Add a raw tool from source code.
        
        Args:
            name: Tool name
            source: Python source code or definition
            metadata: Additional metadata
            
        Returns:
            Self for chaining
        """
        self._raw_tools.append(RawToolDefinition(
            name=name,
            source=source,
            metadata=metadata or {},
        ))
        return self
    
    def add_tool(
        self,
        name: str,
        description: str,
        function: str,
        parameters: Optional[Dict[str, Any]] = None,
        category: str = "general",
        **kwargs,
    ) -> "BoxBuilder":
        """
        Add a tool specification directly.
        
        Args:
            name: Tool name
            description: Tool description
            function: Python function path
            parameters: Parameter definitions
            category: Tool category
            **kwargs: Additional ToolSpec fields
            
        Returns:
            Self for chaining
        """
        self._direct_tools.append(ToolSpec(
            name=name,
            description=description,
            function=function,
            parameters=parameters or {},
            category=category,
            **kwargs,
        ))
        return self
    
    def add_tool_from_file(self, file_path: str) -> "BoxBuilder":
        """
        Add a tool from a Python file.
        
        Args:
            file_path: Path to Python file containing tool definition
            
        Returns:
            Self for chaining
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Tool file not found: {file_path}")
        
        source = path.read_text()
        name = path.stem
        
        self._raw_tools.append(RawToolDefinition(
            name=name,
            source=source,
            metadata={"source_file": str(path)},
        ))
        return self
    
    def build(self) -> MCPBox:
        """
        Build the MCPBox from added tools.
        
        Runs the full pipeline: abstract → cluster → consolidate
        
        Returns:
            Complete MCPBox configuration
        """
        # Run abstract pipeline on raw tools
        abstract_pipeline = AbstractPipeline(self.config.get("abstract", {}))
        normalized_tools = abstract_pipeline.process(self._raw_tools)
        
        # Run cluster pipeline
        cluster_pipeline = ClusterPipeline(self.config.get("cluster", {}))
        clusters = cluster_pipeline.process(normalized_tools)
        
        # Run consolidate pipeline
        consolidate_config = self.config.get("consolidate", {})
        consolidate_config.update({
            "name": self.name,
            "version": self.version,
            "description": self.description,
        })
        consolidate_pipeline = ConsolidatePipeline(consolidate_config)
        mcp_box = consolidate_pipeline.process(clusters)
        
        # Add direct tools
        for tool in self._direct_tools:
            mcp_box.add_tool(tool)
        
        return mcp_box
    
    def build_from_directory(
        self,
        directory: str,
        pattern: str = "*.py",
    ) -> MCPBox:
        """
        Build MCPBox from all Python files in a directory.
        
        Args:
            directory: Path to directory containing tool files
            pattern: Glob pattern for files to include
            
        Returns:
            Complete MCPBox configuration
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        for file_path in dir_path.glob(pattern):
            if file_path.is_file():
                self.add_tool_from_file(str(file_path))
        
        return self.build()
    
    @classmethod
    def from_config(cls, config_path: str) -> "BoxBuilder":
        """
        Create a BoxBuilder from a JSON config file.
        
        Args:
            config_path: Path to JSON config file
            
        Returns:
            Configured BoxBuilder instance
        """
        with open(config_path) as f:
            config = json.load(f)
        
        builder = cls(
            name=config.get("name", "mcp-box"),
            version=config.get("version", "0.1.0"),
            description=config.get("description", ""),
            config=config.get("pipeline_config", {}),
        )
        
        # Add tools from config
        for tool in config.get("tools", []):
            if "source" in tool:
                builder.add_tool_source(
                    name=tool["name"],
                    source=tool["source"],
                    metadata=tool.get("metadata"),
                )
            else:
                builder.add_tool(**tool)
        
        return builder

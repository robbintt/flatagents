"""
Cluster Pipeline: Group normalized tools by function/category.

This pipeline takes normalized tools and groups them into logical
clusters based on their functionality.
"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict

from mcp_box.pipelines.abstract import NormalizedTool


@dataclass
class ToolCluster:
    """A cluster of related tools."""
    name: str
    description: str
    tools: List[NormalizedTool]
    category: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ClusterPipeline:
    """
    Pipeline for clustering normalized tools by functionality.
    
    Groups tools based on:
    - Category
    - Name patterns
    - Parameter similarity
    - Custom clustering rules
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_cluster_size = self.config.get("min_cluster_size", 1)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.5)
    
    def process(self, tools: List[NormalizedTool]) -> List[ToolCluster]:
        """
        Cluster a list of normalized tools.
        
        Args:
            tools: List of normalized tools
            
        Returns:
            List of tool clusters
        """
        # Group by category first
        category_groups = self._group_by_category(tools)
        
        clusters = []
        for category, category_tools in category_groups.items():
            # Further cluster within each category
            sub_clusters = self._cluster_by_similarity(category_tools, category)
            clusters.extend(sub_clusters)
        
        return clusters
    
    def _group_by_category(self, tools: List[NormalizedTool]) -> Dict[str, List[NormalizedTool]]:
        """Group tools by their category."""
        groups: Dict[str, List[NormalizedTool]] = defaultdict(list)
        for tool in tools:
            groups[tool.category].append(tool)
        return dict(groups)
    
    def _cluster_by_similarity(
        self, 
        tools: List[NormalizedTool], 
        category: str
    ) -> List[ToolCluster]:
        """
        Cluster tools by name/parameter similarity within a category.
        """
        if not tools:
            return []
        
        # For small groups, keep as single cluster
        if len(tools) <= 3:
            return [ToolCluster(
                name=category,
                description=f"Tools for {category.replace('_', ' ')}",
                tools=tools,
                category=category,
            )]
        
        # Group by name prefix
        prefix_groups = self._group_by_prefix(tools)
        
        clusters = []
        for prefix, prefix_tools in prefix_groups.items():
            cluster_name = f"{category}_{prefix}" if prefix else category
            clusters.append(ToolCluster(
                name=cluster_name,
                description=self._generate_cluster_description(prefix_tools),
                tools=prefix_tools,
                category=category,
                metadata={"prefix": prefix},
            ))
        
        return clusters
    
    def _group_by_prefix(self, tools: List[NormalizedTool]) -> Dict[str, List[NormalizedTool]]:
        """Group tools by common name prefix."""
        groups: Dict[str, List[NormalizedTool]] = defaultdict(list)
        
        for tool in tools:
            # Extract prefix (first word before underscore)
            parts = tool.name.split("_")
            prefix = parts[0] if len(parts) > 1 else ""
            groups[prefix].append(tool)
        
        return dict(groups)
    
    def _generate_cluster_description(self, tools: List[NormalizedTool]) -> str:
        """Generate a description for a cluster based on its tools."""
        if not tools:
            return ""
        
        if len(tools) == 1:
            return tools[0].description
        
        # Combine descriptions
        descriptions = [t.description for t in tools if t.description]
        if descriptions:
            return f"Tools including: {descriptions[0]}"
        
        names = [t.name for t in tools]
        return f"Tool cluster containing: {', '.join(names[:3])}"
    
    def calculate_similarity(self, tool1: NormalizedTool, tool2: NormalizedTool) -> float:
        """
        Calculate similarity score between two tools.
        
        Based on:
        - Name similarity
        - Parameter overlap
        - Category match
        """
        score = 0.0
        
        # Category match
        if tool1.category == tool2.category:
            score += 0.3
        
        # Name similarity (common prefix)
        name1_parts = set(tool1.name.lower().split("_"))
        name2_parts = set(tool2.name.lower().split("_"))
        if name1_parts & name2_parts:
            overlap = len(name1_parts & name2_parts) / len(name1_parts | name2_parts)
            score += 0.4 * overlap
        
        # Parameter overlap
        params1 = set(tool1.parameters.keys())
        params2 = set(tool2.parameters.keys())
        if params1 and params2:
            param_overlap = len(params1 & params2) / len(params1 | params2)
            score += 0.3 * param_overlap
        
        return score
    
    def merge_clusters(self, clusters: List[ToolCluster]) -> List[ToolCluster]:
        """
        Merge clusters that are too similar or too small.
        """
        if len(clusters) <= 1:
            return clusters
        
        merged = []
        used: Set[int] = set()
        
        for i, cluster in enumerate(clusters):
            if i in used:
                continue
            
            # Find clusters to merge with
            to_merge = [cluster]
            for j, other in enumerate(clusters[i + 1:], start=i + 1):
                if j in used:
                    continue
                
                # Check if should merge (same category, small size)
                if (cluster.category == other.category and 
                    len(cluster.tools) + len(other.tools) <= 10):
                    to_merge.append(other)
                    used.add(j)
            
            if len(to_merge) == 1:
                merged.append(cluster)
            else:
                # Merge clusters
                all_tools = []
                for c in to_merge:
                    all_tools.extend(c.tools)
                
                merged.append(ToolCluster(
                    name=cluster.name,
                    description=self._generate_cluster_description(all_tools),
                    tools=all_tools,
                    category=cluster.category,
                ))
        
        return merged

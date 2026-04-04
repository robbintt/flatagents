"""
File operations tools for MCP.

These tools provide file search and patching capabilities.
"""

import os
import re
import fnmatch
from typing import List, Optional, Dict, Any
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Fallback: create a no-op decorator
    class FastMCP:
        def tool(self):
            def decorator(func):
                return func
            return decorator


# Create MCP server instance for file operations
mcp = FastMCP("file-ops") if MCP_AVAILABLE else FastMCP()


def file_search(
    pattern: str,
    directory: str = ".",
    recursive: bool = True,
    content_pattern: Optional[str] = None,
    max_results: int = 100,
) -> List[Dict[str, Any]]:
    """
    Search for files matching a pattern.
    
    Args:
        pattern: Glob pattern to match file names (e.g., "*.py", "test_*.py")
        directory: Directory to search in (default: current directory)
        recursive: Whether to search recursively (default: True)
        content_pattern: Optional regex pattern to match file contents
        max_results: Maximum number of results to return (default: 100)
    
    Returns:
        List of matching files with metadata
    """
    results = []
    root_path = Path(directory).resolve()
    
    if not root_path.exists():
        return []
    
    # Determine search pattern
    if recursive:
        search_pattern = f"**/{pattern}"
    else:
        search_pattern = pattern
    
    for file_path in root_path.glob(search_pattern):
        if not file_path.is_file():
            continue
            
        if len(results) >= max_results:
            break
        
        # Check content pattern if specified
        if content_pattern:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if not re.search(content_pattern, content):
                        continue
            except (IOError, OSError):
                continue
        
        # Get file metadata
        stat = file_path.stat()
        results.append({
            "path": str(file_path.relative_to(root_path)),
            "absolute_path": str(file_path),
            "size": stat.st_size,
            "modified": stat.st_mtime,
        })
    
    return results


if MCP_AVAILABLE:
    file_search = mcp.tool()(file_search)


def apply_patch(
    file_path: str,
    old_content: str,
    new_content: str,
    create_backup: bool = True,
) -> Dict[str, Any]:
    """
    Apply a patch to a file by replacing old content with new content.
    
    Args:
        file_path: Path to the file to patch
        old_content: Content to find and replace
        new_content: Content to replace with
        create_backup: Whether to create a backup file (default: True)
    
    Returns:
        Result dict with status and details
    """
    path = Path(file_path)
    
    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}",
        }
    
    try:
        # Read current content
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check if old content exists
        if old_content not in content:
            return {
                "success": False,
                "error": "Old content not found in file",
            }
        
        # Create backup if requested
        if create_backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        # Apply patch
        new_file_content = content.replace(old_content, new_content, 1)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_file_content)
        
        return {
            "success": True,
            "file_path": str(path),
            "backup_created": create_backup,
            "bytes_written": len(new_file_content),
        }
        
    except (IOError, OSError) as e:
        return {
            "success": False,
            "error": str(e),
        }


if MCP_AVAILABLE:
    apply_patch = mcp.tool()(apply_patch)

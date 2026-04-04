"""
JSON Schema definitions for MCPBox validation.

These schemas can be used to validate MCPBox JSON files against the expected structure.
"""

MCP_BOX_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://flatagents.dev/schemas/mcp-box.json",
    "title": "MCPBox",
    "description": "A containerized collection of MCP tools with metadata",
    "type": "object",
    "required": ["name", "version"],
    "properties": {
        "name": {
            "type": "string",
            "description": "Unique name for the MCP box"
        },
        "version": {
            "type": "string",
            "description": "Semantic version of the MCP box",
            "pattern": "^\\d+\\.\\d+\\.\\d+(-[a-zA-Z0-9]+)?$"
        },
        "description": {
            "type": "string",
            "description": "Human-readable description of the MCP box"
        },
        "tools": {
            "type": "array",
            "items": {"$ref": "#/definitions/ToolSpec"},
            "description": "List of tools in this MCP box"
        },
        "validators": {
            "type": "array",
            "items": {"$ref": "#/definitions/ValidatorSpec"},
            "description": "List of validators for tools"
        },
        "default_fallback_policy": {
            "$ref": "#/definitions/FallbackPolicy",
            "description": "Default fallback policy for all tools"
        },
        "metadata": {
            "type": "object",
            "description": "Additional metadata for the MCP box"
        }
    },
    "definitions": {
        "FallbackPolicy": {
            "type": "object",
            "properties": {
                "retry_count": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 3,
                    "description": "Number of retry attempts"
                },
                "retry_delay_seconds": {
                    "type": "number",
                    "minimum": 0,
                    "default": 1.0,
                    "description": "Delay between retries in seconds"
                },
                "fallback_tool": {
                    "type": ["string", "null"],
                    "description": "Name of tool to use as fallback"
                },
                "on_failure": {
                    "type": "string",
                    "enum": ["error", "skip", "fallback"],
                    "default": "error",
                    "description": "Behavior when all retries fail"
                }
            }
        },
        "ValidatorSpec": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique name for the validator"
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description"
                },
                "input_schema": {
                    "type": "object",
                    "description": "JSON Schema for input validation"
                },
                "output_schema": {
                    "type": "object",
                    "description": "JSON Schema for output validation"
                },
                "custom_validator": {
                    "type": ["string", "null"],
                    "description": "Python function path for custom validation"
                }
            }
        },
        "ToolSpec": {
            "type": "object",
            "required": ["name", "description", "function"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique name for the tool"
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description"
                },
                "function": {
                    "type": "string",
                    "description": "Python function path (e.g., 'mcp_box.tools.file_ops.file_search')"
                },
                "parameters": {
                    "type": "object",
                    "description": "Parameter definitions with types and defaults"
                },
                "return_type": {
                    "type": "string",
                    "default": "string",
                    "description": "Return type of the tool"
                },
                "category": {
                    "type": "string",
                    "default": "general",
                    "description": "Category for grouping tools"
                },
                "validator": {
                    "$ref": "#/definitions/ValidatorSpec",
                    "description": "Validator for this tool"
                },
                "fallback_policy": {
                    "$ref": "#/definitions/FallbackPolicy",
                    "description": "Fallback policy for this tool"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            }
        }
    }
}

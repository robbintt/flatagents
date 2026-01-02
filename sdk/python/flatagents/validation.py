"""
Schema validation for flatagent and flatmachine configurations.

Uses JSON Schema validation against the bundled schemas.
Validation errors are warnings by default to avoid breaking user configs.
"""

import json
import warnings
from importlib.resources import files
from typing import Any, Dict, List, Optional, Union

# Package containing bundled assets
_ASSETS = files("flatagents.assets")


class ValidationWarning(UserWarning):
    """Warning for schema validation issues."""
    pass


def _load_schema(filename: str) -> Optional[Dict[str, Any]]:
    """Load a JSON schema from bundled assets."""
    try:
        content = (_ASSETS / filename).read_text()
        return json.loads(content)
    except FileNotFoundError:
        return None


def _validate_with_jsonschema(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate config against JSON Schema using jsonschema library."""
    try:
        import jsonschema
    except ImportError:
        return []  # Skip validation if jsonschema not installed

    errors = []
    validator = jsonschema.Draft7Validator(schema)
    for error in validator.iter_errors(config):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"{path}: {error.message}")
    return errors


def validate_flatagent_config(
    config: Dict[str, Any],
    warn: bool = True,
    strict: bool = False
) -> List[str]:
    """
    Validate a flatagent configuration against the schema.

    Args:
        config: The configuration dictionary to validate
        warn: If True, emit warnings for validation errors (default: True)
        strict: If True, raise ValueError on validation errors (default: False)

    Returns:
        List of validation error messages (empty if valid)
    """
    schema = _load_schema("flatagent.schema.json")
    if schema is None:
        return []  # Schema not bundled, skip validation

    errors = _validate_with_jsonschema(config, schema)

    if errors:
        if strict:
            raise ValueError(
                f"Flatagent config validation failed:\n" +
                "\n".join(f"  - {e}" for e in errors)
            )
        elif warn:
            warnings.warn(
                f"Flatagent config has validation issues:\n" +
                "\n".join(f"  - {e}" for e in errors),
                ValidationWarning,
                stacklevel=3
            )

    return errors


def validate_flatmachine_config(
    config: Dict[str, Any],
    warn: bool = True,
    strict: bool = False
) -> List[str]:
    """
    Validate a flatmachine configuration against the schema.

    Args:
        config: The configuration dictionary to validate
        warn: If True, emit warnings for validation errors (default: True)
        strict: If True, raise ValueError on validation errors (default: False)

    Returns:
        List of validation error messages (empty if valid)
    """
    schema = _load_schema("flatmachine.schema.json")
    if schema is None:
        return []  # Schema not bundled, skip validation

    errors = _validate_with_jsonschema(config, schema)

    if errors:
        if strict:
            raise ValueError(
                f"Flatmachine config validation failed:\n" +
                "\n".join(f"  - {e}" for e in errors)
            )
        elif warn:
            warnings.warn(
                f"Flatmachine config has validation issues:\n" +
                "\n".join(f"  - {e}" for e in errors),
                ValidationWarning,
                stacklevel=3
            )

    return errors


def get_flatagent_schema() -> Optional[Dict[str, Any]]:
    """Get the bundled flatagent JSON schema."""
    return _load_schema("flatagent.schema.json")


def get_flatmachine_schema() -> Optional[Dict[str, Any]]:
    """Get the bundled flatmachine JSON schema."""
    return _load_schema("flatmachine.schema.json")


def get_asset(filename: str) -> str:
    """Get the contents of a bundled asset file."""
    return (_ASSETS / filename).read_text()


def _get_asset_path(filename: str):
    """Internal: Get a Traversable for a bundled asset file."""
    return _ASSETS / filename

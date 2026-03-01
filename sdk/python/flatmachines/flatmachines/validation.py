"""
Schema validation for flatmachine configurations.

Uses JSON Schema validation against the bundled schema.
Validation errors are warnings by default to avoid breaking user configs.
"""

import json
import warnings
from importlib.resources import files
from typing import Any, Dict, List, Optional

_ASSETS = files("flatmachines.assets")


class ValidationWarning(UserWarning):
    """Warning for schema validation issues."""



def _load_schema(filename: str) -> Optional[Dict[str, Any]]:
    try:
        content = (_ASSETS / filename).read_text()
        return json.loads(content)
    except FileNotFoundError:
        return None


def _validate_with_jsonschema(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    try:
        import jsonschema
    except ImportError:
        return []

    errors: List[str] = []
    validator = jsonschema.Draft7Validator(schema)
    for error in validator.iter_errors(config):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"{path}: {error.message}")
    return errors


def validate_flatmachine_config(
    config: Dict[str, Any],
    warn: bool = True,
    strict: bool = False,
) -> List[str]:
    """Validate a flatmachine configuration against the schema."""
    schema = _load_schema("flatmachine.schema.json")
    if schema is None:
        return []

    errors = _validate_with_jsonschema(config, schema)

    if errors:
        if strict:
            raise ValueError(
                "Flatmachine config validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        if warn:
            warnings.warn(
                "Flatmachine config has validation issues:\n"
                + "\n".join(f"  - {e}" for e in errors),
                ValidationWarning,
                stacklevel=3,
            )

    return errors


def get_flatmachine_schema() -> Optional[Dict[str, Any]]:
    """Get the bundled flatmachine JSON schema."""
    return _load_schema("flatmachine.schema.json")


def get_asset(filename: str) -> str:
    """Get the contents of a bundled asset file."""
    return (_ASSETS / filename).read_text()

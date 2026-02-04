"""Compatibility wrapper for FlatMachines FlatMachine."""

try:
    from flatmachines.flatmachine import FlatMachine
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "FlatMachine requires the flatmachines package. Install flatmachines to use orchestration."
    ) from exc

__all__ = ["FlatMachine"]

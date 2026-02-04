"""Compatibility wrapper for FlatMachines CLI runner."""

try:
    from flatmachines.run import main
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "FlatMachines CLI runner requires the flatmachines package."
    ) from exc


if __name__ == "__main__":
    main()

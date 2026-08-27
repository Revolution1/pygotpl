"""Errors specific to optional Helm capabilities."""


class MissingOptionalDependencyError(RuntimeError):
    """An optional Helm serializer is unavailable."""

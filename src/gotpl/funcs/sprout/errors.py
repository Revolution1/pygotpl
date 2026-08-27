"""Project-specific errors for optional Sprout capabilities."""


class MissingOptionalDependencyError(ImportError):
    """A requested registry capability needs an uninstalled package extra."""

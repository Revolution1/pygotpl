"""Human-friendly Go ``time.Duration`` compatibility for Python."""

from .go import (
    HOUR,
    MAX_DURATION,
    MAX_NANOSECONDS,
    MICROSECOND,
    MILLISECOND,
    MIN_DURATION,
    MIN_NANOSECONDS,
    MINUTE,
    NANOSECOND,
    SECOND,
    Duration,
    DurationParseError,
)

__all__ = [
    "HOUR",
    "MAX_DURATION",
    "MAX_NANOSECONDS",
    "MICROSECOND",
    "MILLISECOND",
    "MINUTE",
    "MIN_DURATION",
    "MIN_NANOSECONDS",
    "NANOSECOND",
    "SECOND",
    "Duration",
    "DurationParseError",
    "__version__",
]

__version__ = "0.0.0"

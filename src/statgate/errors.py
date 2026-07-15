class StatgateError(Exception):
    """Base class for all statgate errors."""


class AdapterError(StatgateError):
    """Raised when an input file cannot be parsed into eval records."""


class ConfigError(StatgateError):
    """Raised when configuration is missing, malformed, or invalid."""


class AnalysisError(StatgateError):
    """Raised when the data is insufficient or unsuitable for analysis."""

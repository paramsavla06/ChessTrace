class EngineError(Exception):
    """Base exception for engine-related errors."""


class EvaluationError(EngineError):
    """Raised when a position cannot be evaluated."""

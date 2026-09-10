"""Custom exceptions for the MD Simulation Interface."""


class MDSimulationError(Exception):
    """Base exception for MD Simulation Interface."""
    pass


class AgentExecutionError(MDSimulationError):
    """Raised when an agent fails to execute properly."""
    pass


class ValidationError(MDSimulationError):
    """Raised when validation of results fails."""
    pass


class ConfigurationError(MDSimulationError):
    """Raised when there's a configuration issue."""
    pass


class MaxAttemptsExceededError(MDSimulationError):
    """Raised when maximum number of attempts is exceeded."""
    pass

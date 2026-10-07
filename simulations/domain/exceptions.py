class SimulationError(Exception):
    """Base exception for expected simulation domain errors."""


class InvalidScenario(SimulationError):
    """Raised when a scenario definition does not respect the contract."""


class InvalidAction(SimulationError):
    """Raised when an event cannot be applied to the current state."""


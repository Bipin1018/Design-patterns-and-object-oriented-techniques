"""Automation errors."""


class UnknownStrategyError(ValueError):
    """A strategy key was asked for that is not registered.

    A ValueError, so it lands on the same 400 path as Phase 4's
    ConfigurationError and Phase 5's AdapterError.
    """
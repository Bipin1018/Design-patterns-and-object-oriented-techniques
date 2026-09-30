"""Errors raised by the sensor domain.

ValueError subclasses on purpose, exactly like ConfigurationError in the
location domain. The routers already turn a ValueError into a 400, so these
need no new handling in the API layer.
"""


class AdapterError(ValueError):
    """No adapter can read this device, or the payload could not be translated."""
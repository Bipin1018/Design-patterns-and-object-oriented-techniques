"""The sampling rules.

A module-level function, not a method, for the same reason validate_zone_fields
is one in the location domain. PATCH /api/devices/{id}/sampling updates an
existing row rather than rebuilding anything, but it must still obey the rule,
so both sides call this.

Five seconds is the floor. Below that the sampler would spend more time asking
the database for the last reading than the reading is worth.
"""

MIN_SAMPLING_INTERVAL_SECONDS = 5


def validate_sampling_interval(seconds: int) -> None:
    """Raise ValueError if the interval is below the floor."""
    if seconds < MIN_SAMPLING_INTERVAL_SECONDS:
        raise ValueError(
            f"sampling_interval_seconds must be at least "
            f"{MIN_SAMPLING_INTERVAL_SECONDS}, got {seconds}."
        )
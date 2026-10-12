"""What a strategy gives back."""

from dataclasses import dataclass

#: Water this zone now.
IRRIGATE = "irrigate"

#: Leave it alone.
WAIT = "wait"


@dataclass(frozen=True)
class Recommendation:
    """One decision about one zone."""

    action: str
    reason: str
    score: float | None = None
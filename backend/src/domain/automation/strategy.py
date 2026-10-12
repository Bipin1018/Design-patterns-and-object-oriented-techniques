"""The automation strategies: one interface, two algorithms, a lookup in between."""

from abc import ABC, abstractmethod

from src.domain.automation.context import LocationAutomationContext
from src.domain.automation.errors import UnknownStrategyError
from src.domain.automation.recommendation import IRRIGATE, WAIT, Recommendation

CONSERVATIVE = "conservative"
AGGRESSIVE = "aggressive"

#: Used when a location has never had a strategy saved.
DEFAULT_STRATEGY_KEY = CONSERVATIVE

#: Above this a day counts as bright. Lux, matching the light sensors' unit.
BRIGHT_LIGHT_LUX = 800.0

#: How far further up the band the aggressive acting point moves when bright.
BRIGHT_BOOST = 0.2


def _urgency(moisture: float, trigger: float) -> float:
    """0.0 at the trigger point, 1.0 at bone dry. Always within range."""
    if trigger <= 0.0:
        return 0.0
    return min(1.0, max(0.0, (trigger - moisture) / trigger))


def _nothing_to_judge(context: LocationAutomationContext) -> Recommendation:
    """Both strategies answer the same way when the zone has no sensor.

    A zone with no moisture sensor does not borrow a reading from another zone,
    and an unassigned device sits in no zone at all.
    """
    return Recommendation(
        action=WAIT,
        reason=f"No moisture sensor in zone '{context.zone_name}', so there is nothing to judge.",
    )


class AutomationStrategy(ABC):
    """The promise every algorithm keeps: give me a zone, I give you a decision."""

    key: str = ""
    label: str = ""
    description: str = ""

    @abstractmethod
    def decide(self, context: LocationAutomationContext) -> Recommendation:
        """Look at one zone and say what should happen to it."""


class ConservativeMoistureStrategy(AutomationStrategy):
    """Waters late: only once the zone reaches its low threshold."""

    key = CONSERVATIVE
    label = "Conservative"
    description = "Irrigates only when moisture reaches the zone's low threshold."

    def decide(self, context: LocationAutomationContext) -> Recommendation:
        if context.moisture is None:
            return _nothing_to_judge(context)

        moisture = context.moisture
        low = context.moisture_low
        high = context.moisture_high

        if moisture <= low:
            return Recommendation(
                action=IRRIGATE,
                reason=f"Moisture {moisture:.2f} is at or below the low threshold {low:.2f}.",
                score=_urgency(moisture, low),
            )

        if moisture >= high:
            return Recommendation(
                action=WAIT,
                reason=f"Moisture {moisture:.2f} is at or above the high threshold {high:.2f}.",
                score=0.0,
            )

        return Recommendation(
            action=WAIT,
            reason=f"Moisture {moisture:.2f} is within {low:.2f}-{high:.2f}.",
            score=0.0,
        )


class AggressiveMoistureStrategy(AutomationStrategy):
    """Waters early: from the middle of the band, and sooner when the light is strong."""

    key = AGGRESSIVE
    label = "Aggressive"
    description = "Irrigates from the middle of the band, and sooner on a bright day."

    def __init__(self, trigger_fraction: float = 0.5) -> None:
        # A constructor argument, so a tuned instance can be built from
        # automation_rules.parameters later without this class changing.
        self._trigger_fraction = trigger_fraction

    def decide(self, context: LocationAutomationContext) -> Recommendation:
        if context.moisture is None:
            return _nothing_to_judge(context)

        moisture = context.moisture
        band = context.moisture_high - context.moisture_low
        bright = context.light is not None and context.light >= BRIGHT_LIGHT_LUX
        fraction = min(self._trigger_fraction + (BRIGHT_BOOST if bright else 0.0), 1.0)
        trigger = context.moisture_low + fraction * band

        if moisture <= trigger:
            daylight = " and the light is strong" if bright else ""
            return Recommendation(
                action=IRRIGATE,
                reason=(
                    f"Moisture {moisture:.2f} is at or below the acting point "
                    f"{trigger:.2f}{daylight}."
                ),
                score=_urgency(moisture, trigger),
            )

        return Recommendation(
            action=WAIT,
            reason=f"Moisture {moisture:.2f} is above the acting point {trigger:.2f}.",
            score=0.0,
        )


#: The only place in the codebase that maps a key to a concrete class.
_STRATEGIES: dict[str, type[AutomationStrategy]] = {
    CONSERVATIVE: ConservativeMoistureStrategy,
    AGGRESSIVE: AggressiveMoistureStrategy,
}


def available_strategy_keys() -> list[str]:
    """Known keys, sorted."""
    return sorted(_STRATEGIES)


def available_strategies() -> list[AutomationStrategy]:
    """One default instance of each, for listing key, label and description."""
    return [strategy_class() for _, strategy_class in sorted(_STRATEGIES.items())]


def get_strategy(key: str) -> AutomationStrategy:
    """Look up an algorithm by key.

    Raises before anything is decided. An unknown key is a 400 at the edge, not
    a quiet fall back to whatever seems reasonable.
    """
    try:
        strategy_class = _STRATEGIES[key]
    except KeyError:
        known = ", ".join(available_strategy_keys())
        raise UnknownStrategyError(f"Unknown strategy key '{key}'. Known keys: {known}.") from None
    return strategy_class()
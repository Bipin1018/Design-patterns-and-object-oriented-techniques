"""Unit tests for the strategies. No database, no HTTP."""

from uuid import uuid4

import pytest

from src.domain.automation.context import LocationAutomationContext
from src.domain.automation.errors import UnknownStrategyError
from src.domain.automation.recommendation import IRRIGATE, WAIT
from src.domain.automation.strategy import (
    AggressiveMoistureStrategy,
    ConservativeMoistureStrategy,
    available_strategy_keys,
    get_strategy,
)

LOW = 0.25
HIGH = 0.45


def context(moisture: float | None, light: float | None = None) -> LocationAutomationContext:
    return LocationAutomationContext(
        location_id=uuid4(),
        zone_id=uuid4(),
        zone_name="Bench 1",
        moisture_low=LOW,
        moisture_high=HIGH,
        moisture=moisture,
        light=light,
    )


def test_conservative_waits_when_within_band() -> None:
    result = ConservativeMoistureStrategy().decide(context(0.30))

    assert result.action == WAIT
    assert "within" in result.reason


def test_conservative_irrigates_at_the_low_threshold() -> None:
    assert ConservativeMoistureStrategy().decide(context(LOW)).action == IRRIGATE
    assert ConservativeMoistureStrategy().decide(context(0.10)).action == IRRIGATE


def test_conservative_waits_above_the_high_threshold() -> None:
    assert ConservativeMoistureStrategy().decide(context(0.50)).action == WAIT


def test_aggressive_differs_on_same_context() -> None:
    """The claim the phase is marked on: one context, two keys, two answers."""
    same = context(0.30)

    conservative = get_strategy("conservative").decide(same)
    aggressive = get_strategy("aggressive").decide(same)

    assert conservative.action == WAIT
    assert aggressive.action == IRRIGATE
    assert conservative.reason != aggressive.reason


def test_aggressive_waits_in_the_upper_band() -> None:
    assert AggressiveMoistureStrategy().decide(context(0.40)).action == WAIT


def test_bright_light_moves_the_acting_point_up() -> None:
    """0.37 is above the midpoint, below the bright-day point of 0.39."""
    dim = AggressiveMoistureStrategy().decide(context(0.37, light=100.0))
    bright = AggressiveMoistureStrategy().decide(context(0.37, light=1500.0))

    assert dim.action == WAIT
    assert bright.action == IRRIGATE
    assert "light is strong" in bright.reason


def test_light_is_ignored_by_conservative() -> None:
    dim = ConservativeMoistureStrategy().decide(context(0.30, light=100.0))
    bright = ConservativeMoistureStrategy().decide(context(0.30, light=1500.0))

    assert dim == bright


@pytest.mark.parametrize("key", available_strategy_keys())
def test_no_sensor_waits_without_inventing_a_value(key: str) -> None:
    """A zone with no moisture sensor does not borrow one."""
    result = get_strategy(key).decide(context(None))

    assert result.action == WAIT
    assert "No moisture sensor" in result.reason
    assert result.score is None


@pytest.mark.parametrize("key", available_strategy_keys())
def test_score_stays_within_range(key: str) -> None:
    for moisture in (0.0, 0.1, 0.25, 0.35, 0.45, 0.9):
        score = get_strategy(key).decide(context(moisture)).score
        assert score is not None
        assert 0.0 <= score <= 1.0


def test_unknown_key_is_rejected_before_deciding() -> None:
    with pytest.raises(UnknownStrategyError) as caught:
        get_strategy("reckless")

    assert "reckless" in str(caught.value)
    assert "conservative" in str(caught.value)


def test_registry_lists_both_keys() -> None:
    assert available_strategy_keys() == ["aggressive", "conservative"]
"""Automation orchestration: load the facts, pick the algorithm, map the result."""

from typing import Any
from uuid import UUID

from src.application.automation.dto import (
    EvaluationDto,
    StrategyOptionDto,
    StrategyRuleDto,
    ZoneRecommendationDto,
)
from src.application.locations.config_service import LocationNotFoundError
from src.domain.automation.context import LocationAutomationContext
from src.domain.automation.recommendation import IRRIGATE, WAIT
from src.domain.automation.strategy import (
    DEFAULT_STRATEGY_KEY,
    available_strategies,
    get_strategy,
)
from src.infrastructure.persistence.automation_repository import (
    LIGHT_SENSOR_TYPE,
    MOISTURE_SENSOR_TYPE,
    AutomationContextRepository,
    AutomationRuleRepository,
)


class AutomationService:
    def __init__(
        self,
        rules: AutomationRuleRepository,
        contexts: AutomationContextRepository,
    ) -> None:
        self._rules = rules
        self._contexts = contexts

    # -- strategy choice ----------------------------------------------------

    def list_strategies(self) -> list[StrategyOptionDto]:
        """Every registered algorithm, described by itself."""
        return [
            StrategyOptionDto(key=s.key, label=s.label, description=s.description)
            for s in available_strategies()
        ]

    def get_rule(self, location_id: UUID) -> StrategyRuleDto:
        """The saved choice, or the default presented as not yet persisted."""
        self._require_location(location_id)
        rule = self._rules.get(location_id)
        if rule is None:
            return StrategyRuleDto(
                location_id=location_id,
                strategy_key=DEFAULT_STRATEGY_KEY,
                parameters={},
                updated_at=None,
                persisted=False,
            )
        return StrategyRuleDto(
            location_id=rule.location_id,
            strategy_key=rule.strategy_key,
            parameters=rule.parameters,
            updated_at=rule.updated_at,
            persisted=True,
        )

    def set_strategy(
        self,
        location_id: UUID,
        strategy_key: str,
        parameters: dict[str, Any] | None = None,
    ) -> StrategyRuleDto:
        """Save which algorithm this location decides with.

        get_strategy is called for its refusal, not its result. An unknown key
        raises before anything is written, so a typo cannot be stored and found
        later at evaluate time.
        """
        self._require_location(location_id)
        key = strategy_key.strip().lower()
        get_strategy(key)

        rule = self._rules.upsert(location_id, key, parameters)
        return StrategyRuleDto(
            location_id=rule.location_id,
            strategy_key=rule.strategy_key,
            parameters=rule.parameters,
            updated_at=rule.updated_at,
            persisted=True,
        )

    # -- evaluation ---------------------------------------------------------

    def evaluate(self, location_id: UUID) -> EvaluationDto:
        """Decide for every zone in the location, with the persisted strategy."""
        location_name = self._require_location(location_id)

        rule = self._rules.get(location_id)
        strategy_key = rule.strategy_key if rule else DEFAULT_STRATEGY_KEY
        # Raises on a key that was valid when saved but is no longer registered.
        # Better a 400 naming the key than a silent fall back to something the
        # operator did not choose.
        strategy = get_strategy(strategy_key)

        zones = self._contexts.zone_thresholds(location_id)
        zone_ids = [zone.zone_id for zone in zones]
        moisture = self._contexts.latest_by_zone(zone_ids, MOISTURE_SENSOR_TYPE)
        light = self._contexts.latest_by_zone(zone_ids, LIGHT_SENSOR_TYPE)

        results: list[ZoneRecommendationDto] = []
        for zone in zones:
            latest_moisture = moisture.get(zone.zone_id)
            latest_light = light.get(zone.zone_id)

            context = LocationAutomationContext(
                location_id=location_id,
                zone_id=zone.zone_id,
                zone_name=zone.name,
                moisture_low=zone.moisture_low,
                moisture_high=zone.moisture_high,
                moisture=latest_moisture.value if latest_moisture else None,
                light=latest_light.value if latest_light else None,
                recorded_at=latest_moisture.recorded_at if latest_moisture else None,
                source_device_id=latest_moisture.device_id if latest_moisture else None,
            )

            recommendation = strategy.decide(context)

            results.append(
                ZoneRecommendationDto(
                    zone_id=context.zone_id,
                    zone_name=context.zone_name,
                    action=recommendation.action,
                    reason=recommendation.reason,
                    score=recommendation.score,
                    moisture=context.moisture,
                    light=context.light,
                    moisture_low=context.moisture_low,
                    moisture_high=context.moisture_high,
                    recorded_at=context.recorded_at,
                    source_device_id=context.source_device_id,
                )
            )

        action, reason = self._roll_up(location_name, results)
        return EvaluationDto(
            location_id=location_id,
            strategy_key=strategy_key,
            action=action,
            reason=reason,
            zones=results,
        )

    # -- helpers ------------------------------------------------------------

    def _require_location(self, location_id: UUID) -> str:
        """The location's name, or a not-found error the router turns into 404."""
        name = self._contexts.location_name(location_id)
        if name is None:
            raise LocationNotFoundError(f"No location with id {location_id}.")
        return name

    @staticmethod
    def _roll_up(
        location_name: str,
        results: list[ZoneRecommendationDto],
    ) -> tuple[str, str]:
        """One headline for the whole location.

        Summarising, not deciding. Every verdict came from the strategy; this
        only counts them. A location needs water if any zone does, because the
        alternative is a dry bench nobody mentions.
        """
        if not results:
            return WAIT, f"{location_name} has no zones, so there is nothing to decide."

        if len(results) == 1:
            return results[0].action, results[0].reason

        thirsty = [zone.zone_name for zone in results if zone.action == IRRIGATE]
        if thirsty:
            return IRRIGATE, (
                f"{len(thirsty)} of {len(results)} zones need water: {', '.join(thirsty)}."
            )
        return WAIT, f"No zone in {location_name} needs water."
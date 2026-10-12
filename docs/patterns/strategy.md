# Strategy

## Problem

A greenhouse has to decide when to water. The decision depends on the latest
moisture reading and on the zone's own thresholds, and reasonable people
disagree about where the line sits. Water late and you save water but risk a
dry bench between readings. Water early and the plants never dry out but the
tank empties faster.

Both are valid. Which one a site wants is a decision for whoever runs it, and
it can change on a Tuesday.

Write the rule as an `if` in the API handler and there is one rule for
everybody. Write two and the handler grows a branch on a string, which means
every new rule edits the file that every other rule lives in.

## Solution

Put the decision behind an interface. The interface is a promise: give me one
zone's numbers, I give you an action and a reason.

Each algorithm is a class that keeps the promise its own way. Conservative
waters once moisture reaches the zone's low threshold. Aggressive waters from
the middle of the band, and sooner on a bright day because light dries a zone
faster. Same input, different answers, and neither knows the other exists.

A dictionary maps a key to a class, and the key is what the database stores.
Choosing an algorithm is then a word in a row rather than a branch in code.

The service loads the facts and asks. It does not judge. There is no threshold
comparison anywhere in `application/automation/service.py`, and that is the
test of whether the pattern survived.

## Where it is

Domain, no SQLAlchemy and no FastAPI:

    domain/automation/context.py          LocationAutomationContext, one per zone
    domain/automation/recommendation.py   Recommendation: action, reason, score
    domain/automation/strategy.py         the interface, two algorithms, the lookup
    domain/automation/errors.py           UnknownStrategyError, a ValueError so 400 catches it
    domain/automation/rule.py             the saved choice, as a plain value

Infrastructure:

    persistence/models.py                 AutomationRuleRow, one row per location
    persistence/automation_repository.py  the rule, and the facts a decision needs

Application:

    automation/service.py                 loads, builds contexts, asks, maps
    automation/dto.py                     what the API sends back

API: `GET /api/automation/strategies`, `GET` and `PUT
/api/locations/{id}/automation`, `POST
/api/locations/{id}/automation/evaluate`.

Frontend: `features/automation/StrategyPanel.tsx`, mounted in `#automation`.

## Rules the phase enforces

The thresholds come from `zones`, never from a constant. Every zone sets its
own band, which is what Phase 4 was for.

A zone's moisture is the newest reading from a device whose `zone_id` matches
that zone. A zone with no moisture sensor does not borrow one from elsewhere,
and an unassigned device belongs to no zone at all. Both strategies answer the
same way in that case: wait, and say why.

No ORM row reaches a strategy. The repository returns floats and UUIDs, the
service builds a plain context, and `decide` never sees a session. That is why
`test_automation_strategies.py` runs with no database.

Evaluate uses the key in the database, not one in the request. Saving and
evaluating are separate calls, so a dropdown that has not been saved does not
change the answer — the panel says so rather than letting it surprise you.

## Extension

Say a site wants a schedule-first rule: water at 08:00 if moisture is anywhere
below the high threshold, and otherwise leave it alone.

1. Add `ScheduleMoistureStrategy(AutomationStrategy)` in `strategy.py` with
   `key = "schedule"` and its own `decide`.
2. Add one line to `_STRATEGIES`.
3. Write a test with a fake context.

Nothing else changes. The service, the repository, the router, the database and
the dropdown all keep working, because none of them names a strategy class. The
dropdown fills itself from `available_strategies()`, so the new option appears
on the dashboard without a line of TypeScript.

`automation_rules.parameters` is where a tuned variant gets its numbers.
`AggressiveMoistureStrategy` already takes `trigger_fraction` in its
constructor, so a future `get_strategy(key, parameters)` feeds that column in
without the class changing.
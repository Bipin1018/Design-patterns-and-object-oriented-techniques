"""API tests for automation. These need the stack up."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

ZONES = [
    {"name": "Bench 1", "moisture_threshold_low": 0.25, "moisture_threshold_high": 0.45},
    {"name": "Bench 2", "moisture_threshold_low": 0.20, "moisture_threshold_high": 0.50},
]

MISSING = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def location() -> Iterator[dict]:
    created = client.post(
        "/api/locations/config",
        json={"location_name": "Automation Site", "zones": ZONES},
    )
    assert created.status_code == 201
    body = created.json()
    yield body
    client.delete(f"/api/locations/{body['location']['id']}")


def saved_key(location_id: str) -> str:
    return client.get(f"/api/locations/{location_id}/automation").json()["strategy_key"]


def test_strategies_are_listed_with_labels() -> None:
    body = client.get("/api/automation/strategies").json()
    keys = [option["key"] for option in body]

    assert keys == ["aggressive", "conservative"]
    assert all(option["label"] and option["description"] for option in body)


def test_rule_defaults_to_conservative_before_anything_is_saved(location: dict) -> None:
    location_id = location["location"]["id"]
    body = client.get(f"/api/locations/{location_id}/automation").json()

    assert body["strategy_key"] == "conservative"
    assert body["persisted"] is False


def test_saving_a_strategy_persists_it(location: dict) -> None:
    location_id = location["location"]["id"]

    saved = client.put(
        f"/api/locations/{location_id}/automation",
        json={"strategy_key": "aggressive"},
    )
    assert saved.status_code == 200
    assert saved.json()["persisted"] is True
    assert saved_key(location_id) == "aggressive"


def test_saving_twice_replaces_rather_than_duplicates(location: dict) -> None:
    """The UNIQUE on location_id is what makes this an upsert, not an insert."""
    location_id = location["location"]["id"]

    for key in ("aggressive", "conservative", "aggressive"):
        response = client.put(
            f"/api/locations/{location_id}/automation",
            json={"strategy_key": key},
        )
        assert response.status_code == 200

    assert saved_key(location_id) == "aggressive"


def test_evaluate_uses_the_persisted_key(location: dict) -> None:
    """Nothing in the evaluate request names a strategy."""
    location_id = location["location"]["id"]
    client.put(f"/api/locations/{location_id}/automation", json={"strategy_key": "aggressive"})

    body = client.post(f"/api/locations/{location_id}/automation/evaluate").json()

    assert body["strategy_key"] == "aggressive"
    assert body["location_id"] == location_id


def test_evaluate_returns_one_result_per_zone_with_its_own_band(location: dict) -> None:
    location_id = location["location"]["id"]
    body = client.post(f"/api/locations/{location_id}/automation/evaluate").json()

    bands = {
        zone["zone_name"]: (zone["moisture_low"], zone["moisture_high"])
        for zone in body["zones"]
    }

    assert bands == {"Bench 1": (0.25, 0.45), "Bench 2": (0.20, 0.50)}


def test_zone_without_a_sensor_waits(location: dict) -> None:
    """No device is assigned to these zones, so none may borrow a reading."""
    location_id = location["location"]["id"]
    body = client.post(f"/api/locations/{location_id}/automation/evaluate").json()

    for zone in body["zones"]:
        assert zone["action"] == "wait"
        assert zone["moisture"] is None
        assert "No moisture sensor" in zone["reason"]


def test_unknown_key_is_400_and_writes_nothing(location: dict) -> None:
    location_id = location["location"]["id"]
    client.put(f"/api/locations/{location_id}/automation", json={"strategy_key": "conservative"})

    rejected = client.put(
        f"/api/locations/{location_id}/automation",
        json={"strategy_key": "reckless"},
    )

    assert rejected.status_code == 400
    assert saved_key(location_id) == "conservative"


def test_missing_location_is_404() -> None:
    saved = client.put(
        f"/api/locations/{MISSING}/automation",
        json={"strategy_key": "conservative"},
    )

    assert client.get(f"/api/locations/{MISSING}/automation").status_code == 404
    assert saved.status_code == 404
    assert client.post(f"/api/locations/{MISSING}/automation/evaluate").status_code == 404


def test_deleting_a_location_takes_its_rule_with_it() -> None:
    created = client.post(
        "/api/locations/config",
        json={"location_name": "Cascade Site", "zones": ZONES},
    ).json()
    location_id = created["location"]["id"]

    client.put(f"/api/locations/{location_id}/automation", json={"strategy_key": "aggressive"})
    assert client.delete(f"/api/locations/{location_id}").status_code == 204

    assert client.get(f"/api/locations/{location_id}/automation").status_code == 404
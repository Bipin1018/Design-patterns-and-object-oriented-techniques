"""API tests for the location overview. These need the stack up."""

from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

ZONES = [
    {"name": "Bench 1", "moisture_threshold_low": 0.20, "moisture_threshold_high": 0.45},
    {"name": "Bench 2", "moisture_threshold_low": 0.30, "moisture_threshold_high": 0.60},
]

MISSING = "00000000-0000-0000-0000-000000000000"


def create_sensor(name: str) -> str:
    response = client.post("/api/sensors", json={"type": "moisture", "display_name": name})
    assert response.status_code == 201
    return response.json()["id"]


def overview(location_id: str) -> dict:
    response = client.get(f"/api/locations/{location_id}/overview")
    assert response.status_code == 200
    return response.json()


def zone_named(body: dict, name: str) -> dict:
    return next(zone for zone in body["zones"] if zone["name"] == name)


@pytest.fixture
def site() -> Iterator[dict]:
    created = client.post(
        "/api/locations/config",
        json={"location_name": "Overview Site", "zones": ZONES},
    )
    assert created.status_code == 201
    body = created.json()
    zones = {zone["name"]: zone["id"] for zone in body["zones"]}

    assigned = create_sensor("Bench moisture")
    unassigned = create_sensor("Spare moisture")

    placed = client.patch(f"/api/devices/{assigned}/zone", json={"zone_id": zones["Bench 1"]})
    assert placed.status_code == 200

    reading = client.post(f"/api/sensors/{assigned}/read")
    assert reading.status_code == 201

    yield {
        "id": body["location"]["id"],
        "assigned": assigned,
        "unassigned": unassigned,
        "reading": reading.json(),
    }
    client.delete(f"/api/locations/{body['location']['id']}")


def test_overview_returns_strategy_and_readings(site: dict) -> None:
    assert client.get(f"/api/locations/{MISSING}/overview").status_code == 404

    body = overview(site["id"])

    assert body["location"]["name"] == "Overview Site"
    assert body["strategy_key"] is None
    assert body["last_recommendation"] is None
    assert body["device_counts"] == {"sensor": 1, "actuator": 0}
    assert [zone["name"] for zone in body["zones"]] == ["Bench 1", "Bench 2"]

    listed = {device["id"] for zone in body["zones"] for device in zone["devices"]}
    read = {r["device_id"] for zone in body["zones"] for r in zone["latest_readings"]}
    assert site["unassigned"] not in listed
    assert site["unassigned"] not in read
    assert listed == {site["assigned"]}

    bench_1 = zone_named(body, "Bench 1")
    assert (bench_1["moisture_threshold_low"], bench_1["moisture_threshold_high"]) == (0.20, 0.45)
    [latest] = bench_1["latest_readings"]
    device = next(d for d in client.get("/api/devices").json() if d["id"] == site["assigned"])
    assert latest["device_id"] == site["assigned"]
    assert latest["value"] == pytest.approx(site["reading"]["value"])
    assert latest["unit"] == site["reading"]["unit"]
    assert latest["tracking_enabled"] == device["tracking_enabled"]
    assert latest["sampling_interval_seconds"] == device["sampling_interval_seconds"]

    bench_2 = zone_named(body, "Bench 2")
    assert bench_2["devices"] == []
    assert bench_2["latest_readings"] == []

    saved = client.put(
        f"/api/locations/{site['id']}/automation",
        json={"strategy_key": "conservative"},
    )
    assert saved.status_code == 200

    after = overview(site["id"])
    evaluated = client.post(f"/api/locations/{site['id']}/automation/evaluate").json()

    assert after["strategy_key"] == "conservative"
    assert after["last_recommendation"] == {
        "action": evaluated["action"],
        "reason": evaluated["reason"],
    }


def test_next_get_reflects_a_new_reading(site: dict) -> None:
    newer = client.post(f"/api/sensors/{site['assigned']}/read").json()

    [latest] = zone_named(overview(site["id"]), "Bench 1")["latest_readings"]

    assert datetime.fromisoformat(latest["recorded_at"]) == datetime.fromisoformat(
        newer["recorded_at"]
    )
    assert latest["value"] == pytest.approx(newer["value"])
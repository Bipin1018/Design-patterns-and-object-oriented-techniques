"""API tests for locations, zones and device placement.

These need the database, so run them with the stack up:
    docker compose exec backend pytest tests -q

Each test makes its own location and removes it afterwards, so they can run in
any order and leave no rows behind.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

VALID_ZONES = [
    {
        "name": "Bench 1",
        "moisture_threshold_low": 0.2,
        "moisture_threshold_high": 0.45,
        "schedule": {"watering": "08:00"},
    },
    {"name": "Bench 2", "moisture_threshold_low": 0.25, "moisture_threshold_high": 0.5},
]


def create_location(name: str = "Test Site", zones: list[dict] | None = None) -> dict:
    response = client.post(
        "/api/locations/config",
        json={"location_name": name, "zones": zones or VALID_ZONES},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def location() -> Iterator[dict]:
    created = create_location()
    yield created
    client.delete(f"/api/locations/{created['location']['id']}")


@pytest.fixture
def devices() -> list[dict]:
    response = client.post("/api/devices/provision?family=simulation")
    assert response.status_code == 201
    return response.json()


# -- create and read --------------------------------------------------------


def test_create_config_persists_location_and_zones(location: dict) -> None:
    assert location["location"]["name"] == "Test Site"
    assert len(location["zones"]) == 2


def test_get_config_returns_location_id_on_every_zone(location: dict) -> None:
    location_id = location["location"]["id"]
    body = client.get(f"/api/locations/{location_id}/config").json()

    assert body["location"]["id"] == location_id
    assert [zone["location_id"] for zone in body["zones"]] == [location_id] * 2
    assert body["zones"][0]["moisture_threshold_low"] == 0.2


def test_invalid_payload_returns_400() -> None:
    response = client.post(
        "/api/locations/config",
        json={
            "location_name": "Bad",
            "zones": [{"name": "Z", "moisture_threshold_low": 0.9, "moisture_threshold_high": 0.2}],
        },
    )

    assert response.status_code == 400
    assert "must be below" in response.json()["detail"]


def test_missing_location_returns_404() -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/locations/{missing}/config").status_code == 404


# -- list and delete --------------------------------------------------------


def test_list_locations(location: dict) -> None:
    names = [row["name"] for row in client.get("/api/locations").json()]
    assert "Test Site" in names


def test_delete_location_clears_assignments(devices: list[dict]) -> None:
    created = create_location("Doomed Site")
    location_id = created["location"]["id"]
    zone_id = created["zones"][0]["id"]
    device_id = devices[0]["id"]

    client.patch(f"/api/devices/{device_id}/zone", json={"zone_id": zone_id})

    assert client.delete(f"/api/locations/{location_id}").status_code == 204
    assert client.get(f"/api/locations/{location_id}/config").status_code == 404

    # The device row survives, unplaced.
    after = next(d for d in client.get("/api/devices").json() if d["id"] == device_id)
    assert after["zone_id"] is None
    assert after["location_id"] is None


def test_delete_missing_location_returns_404() -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.delete(f"/api/locations/{missing}").status_code == 404


# -- zones on a saved location ----------------------------------------------


def test_add_zone_to_location(location: dict) -> None:
    location_id = location["location"]["id"]
    response = client.post(
        f"/api/locations/{location_id}/zones",
        json={"name": "Bench 3", "moisture_threshold_low": 0.3, "moisture_threshold_high": 0.6},
    )

    assert response.status_code == 201
    assert response.json()["location_id"] == location_id

    names = [z["name"] for z in client.get(f"/api/locations/{location_id}/config").json()["zones"]]
    assert "Bench 3" in names


def test_update_zone_rejects_invalid_thresholds(location: dict) -> None:
    location_id = location["location"]["id"]
    zone_id = location["zones"][0]["id"]

    response = client.patch(
        f"/api/locations/{location_id}/zones/{zone_id}",
        json={"name": "Bench 1", "moisture_threshold_low": 0.9, "moisture_threshold_high": 0.1},
    )
    assert response.status_code == 400

    # The stored zone is untouched.
    zones = client.get(f"/api/locations/{location_id}/config").json()["zones"]
    unchanged = next(z for z in zones if z["id"] == zone_id)
    assert unchanged["moisture_threshold_low"] == 0.2


def test_delete_zone_clears_assignments(devices: list[dict]) -> None:
    created = create_location("Zone Delete Site")
    location_id = created["location"]["id"]
    zone_id = created["zones"][0]["id"]
    device_id = devices[1]["id"]

    client.patch(f"/api/devices/{device_id}/zone", json={"zone_id": zone_id})
    assert client.delete(f"/api/locations/{location_id}/zones/{zone_id}").status_code == 204

    # ON DELETE SET NULL only clears zone_id; the service must clear both.
    after = next(d for d in client.get("/api/devices").json() if d["id"] == device_id)
    assert after["zone_id"] is None
    assert after["location_id"] is None

    client.delete(f"/api/locations/{location_id}")


def test_delete_last_zone_is_rejected() -> None:
    created = create_location(
        "Single Zone Site",
        [{"name": "Only", "moisture_threshold_low": 0.1, "moisture_threshold_high": 0.3}],
    )
    location_id = created["location"]["id"]
    zone_id = created["zones"][0]["id"]

    response = client.delete(f"/api/locations/{location_id}/zones/{zone_id}")
    assert response.status_code == 400
    assert len(client.get(f"/api/locations/{location_id}/config").json()["zones"]) == 1

    client.delete(f"/api/locations/{location_id}")


# -- device placement -------------------------------------------------------


def test_assign_devices_to_zone(location: dict, devices: list[dict]) -> None:
    location_id = location["location"]["id"]
    zone_one, zone_two = location["zones"][0]["id"], location["zones"][1]["id"]

    client.patch(f"/api/devices/{devices[0]['id']}/zone", json={"zone_id": zone_one})
    client.patch(f"/api/devices/{devices[1]['id']}/zone", json={"zone_id": zone_one})
    client.patch(f"/api/devices/{devices[2]['id']}/zone", json={"zone_id": zone_two})

    listed = client.get(f"/api/locations/{location_id}/zones/{zone_one}/devices").json()
    ids = {device["id"] for device in listed}

    assert ids == {devices[0]["id"], devices[1]["id"]}
    assert devices[2]["id"] not in ids  # the device in the other zone is absent


def test_assign_copies_location_from_the_zone(location: dict, devices: list[dict]) -> None:
    location_id = location["location"]["id"]
    zone_id = location["zones"][0]["id"]

    body = client.patch(f"/api/devices/{devices[0]['id']}/zone", json={"zone_id": zone_id}).json()

    assert body["zone_id"] == zone_id
    assert body["location_id"] == location_id


def test_unassign_clears_zone_and_location(location: dict, devices: list[dict]) -> None:
    zone_id = location["zones"][0]["id"]
    device_id = devices[0]["id"]

    client.patch(f"/api/devices/{device_id}/zone", json={"zone_id": zone_id})
    body = client.patch(f"/api/devices/{device_id}/zone", json={"zone_id": None}).json()

    assert body["zone_id"] is None
    assert body["location_id"] is None


def test_zone_device_list_404s_for_a_zone_in_another_location(location: dict) -> None:
    other = create_location("Other Site")
    foreign_zone = location["zones"][0]["id"]

    response = client.get(
        f"/api/locations/{other['location']['id']}/zones/{foreign_zone}/devices"
    )
    assert response.status_code == 404

    client.delete(f"/api/locations/{other['location']['id']}")


def test_assign_missing_device_returns_404(location: dict) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    zone_id = location["zones"][0]["id"]

    assert client.patch(f"/api/devices/{missing}/zone", json={"zone_id": zone_id}).status_code == 404
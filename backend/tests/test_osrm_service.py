import pytest

from app.services.osrm_service import OSRMError, OSRMService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payload)


def test_osrm_table_normalizes_units_and_coordinate_order():
    session = FakeSession({
        "code": "Ok",
        "durations": [[0, 120], [180, 0]],
        "distances": [[0, 2500], [2600, 0]],
    })
    service = OSRMService(base_url="http://osrm.test", session=session)

    table = service.table([(36.7, 10.1), (35.8, 10.6)])

    assert table.durations_min == [[0, 2], [3, 0]]
    assert table.distances_km == [[0, 2.5], [2.6, 0]]
    assert "/10.100000,36.700000;10.600000,35.800000" in session.calls[0][0]


def test_osrm_route_normalizes_legs():
    session = FakeSession({
        "code": "Ok",
        "routes": [{
            "distance": 3000,
            "duration": 240,
            "geometry": {"type": "LineString", "coordinates": []},
            "legs": [
                {"distance": 1000, "duration": 60, "steps": []},
                {"distance": 2000, "duration": 180, "steps": []},
            ],
        }],
    })
    service = OSRMService(base_url="http://osrm.test", session=session)

    route = service.route([(36.7, 10.1), (35.8, 10.6), (36.7, 10.1)])

    assert route["total_distance_km"] == 3.0
    assert route["total_travel_min"] == 4
    assert [leg["travel_min"] for leg in route["legs"]] == [1, 3]


def test_osrm_table_fails_on_unrouteable_edge():
    session = FakeSession({
        "code": "Ok",
        "durations": [[0, None], [120, 0]],
        "distances": [[0, 1000], [1000, 0]],
    })
    service = OSRMService(base_url="http://osrm.test", session=session)

    with pytest.raises(OSRMError, match="could not route"):
        service.table([(36.7, 10.1), (35.8, 10.6)])

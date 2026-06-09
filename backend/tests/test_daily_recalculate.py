from app.routes import optimization


class FakeOSRM:
    def route(self, coordinates):
        return {
            "total_distance_km": 42.0,
            "total_travel_min": 50,
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in coordinates]},
            "legs": [
                {"distance_km": 10.0, "travel_min": 12, "steps": []},
                {"distance_km": 14.0, "travel_min": 16, "steps": []},
                {"distance_km": 18.0, "travel_min": 22, "steps": []},
            ],
        }


def test_recalculate_daily_plan_refreshes_trip_routes(monkeypatch):
    monkeypatch.setattr(optimization, "OSRMService", lambda: FakeOSRM())
    plan = {
        "depot": {"lat": 36.7703, "lon": 10.2316},
        "work_window": {"start": "06:00", "end": "20:00"},
        "trucks": [{
            "truck_id": 1,
            "truck_label": "Truck 1",
            "trips": [{
                "trip_id": "1-1",
                "depart_at": "06:00",
                "return_at": "07:00",
                "route_status": "manual_pending",
                "stops": [
                    {"id": 1, "client": "A", "lat": 36.7, "lon": 10.1, "etd": "06:30", "quantity_positions": 2},
                    {"id": 2, "client": "B", "lat": 36.8, "lon": 10.2, "etd": "07:00", "quantity_positions": 3},
                ],
            }],
        }],
    }

    recalculated = optimization._recalculate_daily_plan_routes(plan)
    trip = recalculated["trucks"][0]["trips"][0]

    assert trip["route_status"] == "osrm"
    assert trip["total_distance_km"] == 42.0
    assert trip["total_travel_min"] == 50
    assert trip["total_service_min"] == 25
    assert trip["geometry"]["type"] == "LineString"
    assert len(trip["legs"]) == 3
    assert trip["stops"][0]["distance_km"] == 10.0
    assert trip["stops"][0]["travel_min"] == 12
    assert trip["stops"][0]["service_min"] == 10
    assert trip["stops"][1]["service_min"] == 15


def test_recalculate_daily_plan_marks_missing_coordinates_pending(monkeypatch):
    monkeypatch.setattr(optimization, "OSRMService", lambda: FakeOSRM())
    plan = {
        "depot": {"lat": 36.7703, "lon": 10.2316},
        "trucks": [{
            "truck_id": 1,
            "trips": [{
                "trip_id": "1-1",
                "total_distance_km": 10,
                "stops": [{"id": 1, "client": "Manual stop", "etd": "06:30"}],
            }],
        }],
    }

    recalculated = optimization._recalculate_daily_plan_routes(plan)
    trip = recalculated["trucks"][0]["trips"][0]

    assert trip["route_status"] == "manual_pending"
    assert "Missing coordinates" in trip["route_error"]
    assert "total_distance_km" not in trip

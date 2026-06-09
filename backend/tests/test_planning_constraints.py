from app.services.planning_service import PlanningService


def test_etd_eta_are_requested_slot_not_hard_time_window():
    constraints = PlanningService.parse_constraints({
        "etd": "08:00",
        "eta": "10:00",
        "notes": "",
    })

    assert constraints["requested_slot"] == ["08:00", "10:00"]
    assert "time_window" not in constraints


def test_comment_client_hour_remains_hard_time_window():
    constraints = PlanningService.parse_constraints({
        "etd": "08:00",
        "eta": "10:00",
        "notes": "Chez le client 14h",
    })

    assert constraints["requested_slot"] == ["08:00", "10:00"]
    assert constraints["time_window"] == ["14:00", "15:00"]

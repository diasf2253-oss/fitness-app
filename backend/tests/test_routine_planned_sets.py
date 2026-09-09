"""
Per-set planning on a routine (RoutineExercise.planned_sets).

The routine editor plans weight/reps/RIR for each set; the workout shows those
as grey placeholders. target_sets must follow the plan's length, because the
generator, the coach and the workout's "4 x 4-6" badge all read it.
"""


def _exercise(auth_client, name):
    return auth_client.post("/api/exercises", json={"name": name}).json()["id"]


def test_planned_sets_round_trip_and_drive_target_sets(auth_client):
    ex_id = _exercise(auth_client, "Planned Deadlift")
    plan = [
        {"weight_kg": 100.0, "reps": 5, "rir": 3},
        {"weight_kg": 110.0, "reps": 5, "rir": 2},
        {"weight_kg": 120.0, "reps": 3, "rir": 1},
    ]
    r = auth_client.post("/api/routines", json={
        "name": "Planned day",
        "exercises": [{"exercise_id": ex_id, "position": 0,
                       "target_sets": 99,          # deliberately wrong…
                       "planned_sets": plan}],
    })
    assert r.status_code in (200, 201), r.text
    [re_out] = r.json()["exercises"]
    assert re_out["planned_sets"] == plan
    assert re_out["target_sets"] == 3, "…the plan's length wins over target_sets"

    # Survives a read-back through the list the routine editor loads
    routine = [x for x in auth_client.get("/api/routines").json() if x["name"] == "Planned day"][0]
    assert routine["exercises"][0]["planned_sets"] == plan


def test_planned_sets_accept_blank_cells(auth_client):
    """A plan is guidance: any cell may be left empty."""
    ex_id = _exercise(auth_client, "Loose Plan Press")
    plan = [{"weight_kg": None, "reps": 8, "rir": None},
            {"weight_kg": 60.0, "reps": None, "rir": 2}]
    r = auth_client.post("/api/routines", json={
        "name": "Loose day",
        "exercises": [{"exercise_id": ex_id, "position": 0, "planned_sets": plan}],
    })
    assert r.status_code in (200, 201), r.text
    assert r.json()["exercises"][0]["planned_sets"] == plan
    assert r.json()["exercises"][0]["target_sets"] == 2


def test_routine_without_a_plan_still_works(auth_client):
    """Routines created before per-set planning (and the generator) keep using
    target_sets with no planned_sets at all."""
    ex_id = _exercise(auth_client, "Legacy Row")
    r = auth_client.post("/api/routines", json={
        "name": "Legacy day",
        "exercises": [{"exercise_id": ex_id, "position": 0, "target_sets": 4}],
    })
    out = r.json()["exercises"][0]
    assert out["planned_sets"] is None
    assert out["target_sets"] == 4

    # Starting a workout from it still creates target_sets empty sets
    routine_id = r.json()["id"]
    session = auth_client.post("/api/sessions", json={"name": "Legacy", "routine_id": routine_id}).json()
    assert len(session["exercises"][0]["sets"]) == 4

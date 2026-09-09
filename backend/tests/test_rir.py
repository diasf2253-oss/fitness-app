"""
RIR (Reps In Reserve) on a logged set.

The set row's RPE input was replaced by RIR, so `rir` must survive create,
PATCH and read-back — and an explicit null must clear it (the PATCH uses
exclude_unset, so a sent-but-null field still applies).
"""


def _set_up_set(auth_client):
    ex_id = auth_client.post("/api/exercises", json={"name": "RIR Test Press"}).json()["id"]
    session_id = auth_client.post("/api/sessions", json={"name": "RIR day"}).json()["id"]
    se_id = auth_client.post(
        f"/api/sessions/{session_id}/exercises",
        json={"exercise_id": ex_id, "position": 0},
    ).json()["id"]
    return session_id, se_id


def test_rir_round_trips_through_create_and_patch(auth_client):
    session_id, se_id = _set_up_set(auth_client)
    base = f"/api/sessions/{session_id}/exercises/{se_id}/sets"

    created = auth_client.post(base, json={"set_number": 1, "weight_kg": 80, "reps": 8, "rir": 2})
    assert created.status_code in (200, 201), created.text
    set_id = created.json()["id"]
    assert created.json()["rir"] == 2

    # PATCH to a new value
    r = auth_client.patch(f"{base}/{set_id}", json={"weight_kg": 82.5, "reps": 8, "rir": 1})
    assert r.status_code == 200, r.text
    assert r.json()["rir"] == 1

    # Read back through the session payload the workout page uses
    session = auth_client.get(f"/api/sessions/{session_id}").json()
    [logged] = session["exercises"][0]["sets"]
    assert logged["rir"] == 1
    assert logged["weight_kg"] == 82.5


def test_rir_can_be_cleared_and_defaults_to_null(auth_client):
    session_id, se_id = _set_up_set(auth_client)
    base = f"/api/sessions/{session_id}/exercises/{se_id}/sets"

    # Omitted on create -> null, not an error
    set_id = auth_client.post(base, json={"set_number": 1}).json()["id"]
    assert auth_client.get(f"/api/sessions/{session_id}").json()["exercises"][0]["sets"][0]["rir"] is None

    auth_client.patch(f"{base}/{set_id}", json={"rir": 3})
    r = auth_client.patch(f"{base}/{set_id}", json={"rir": None})
    assert r.status_code == 200, r.text
    assert r.json()["rir"] is None

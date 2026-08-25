"""Next-session notes: surface once at the next session of the routine, then
auto-archive (still in history). Plus persistent per-exercise notes carry into
the session via the exercise."""


def make_routine(client, note_cue=None, label="A"):
    ex = client.post(
        "/api/exercises",
        json={"name": f"Squat {label}", "primary_muscle_group": "Quads", "notes": note_cue},
    ).json()
    routine = client.post(
        "/api/routines",
        json={"name": f"Lower {label}", "exercises": [
            {"exercise_id": ex["id"], "position": 0, "target_sets": 2,
             "target_rep_low": 5, "target_rep_high": 8, "rest_seconds": 120},
        ]},
    ).json()
    return ex, routine


def test_next_session_note_surfaces_once_then_archives(auth_client):
    _, routine = make_routine(auth_client)
    rid = routine["id"]

    note = auth_client.post(f"/api/routines/{rid}/notes", json={"text": "add a set to squats"}).json()
    assert note["archived_at"] is None        # pending

    # First session of this routine surfaces the note
    s1 = auth_client.post("/api/sessions", json={"name": "Lower A", "routine_id": rid}).json()
    assert [n["text"] for n in s1["next_session_notes"]] == ["add a set to squats"]
    # ...and it's now consumed/archived
    fetched = auth_client.get(f"/api/routines/{rid}/notes?include_archived=false").json()
    assert fetched == []
    archived = auth_client.get(f"/api/routines/{rid}/notes").json()
    assert archived[0]["surfaced_in_session_id"] == s1["id"] and archived[0]["archived_at"]

    # A later session of the same routine does NOT resurface it
    s2 = auth_client.post("/api/sessions", json={"name": "Lower A", "routine_id": rid}).json()
    assert s2["next_session_notes"] == []

    # It's still visible on the session that consumed it (history)
    assert [n["text"] for n in auth_client.get(f"/api/sessions/{s1['id']}").json()["next_session_notes"]] == ["add a set to squats"]


def test_note_only_surfaces_for_its_own_routine(auth_client):
    _, r1 = make_routine(auth_client, label="A")
    _, r2 = make_routine(auth_client, label="B")
    auth_client.post(f"/api/routines/{r1['id']}/notes", json={"text": "for r1"})
    s = auth_client.post("/api/sessions", json={"name": "other", "routine_id": r2["id"]}).json()
    assert s["next_session_notes"] == []      # belongs to r1, not r2


def test_persistent_exercise_note_shows_in_session(auth_client):
    ex, routine = make_routine(auth_client, note_cue="Brace hard, knees out")
    s = auth_client.post("/api/sessions", json={"name": "Lower A", "routine_id": routine["id"]}).json()
    assert s["exercises"][0]["exercise"]["notes"] == "Brace hard, knees out"
    # editable via the exercise endpoint
    auth_client.put(f"/api/exercises/{ex['id']}", json={"notes": "New cue"})
    assert auth_client.get(f"/api/exercises/{ex['id']}").json()["notes"] == "New cue"


def test_edit_and_delete_note(auth_client):
    _, routine = make_routine(auth_client)
    rid = routine["id"]
    note = auth_client.post(f"/api/routines/{rid}/notes", json={"text": "draft"}).json()
    edited = auth_client.patch(f"/api/routine-notes/{note['id']}", json={"text": "final"}).json()
    assert edited["text"] == "final"
    assert auth_client.delete(f"/api/routine-notes/{note['id']}").status_code == 204
    assert auth_client.get(f"/api/routines/{rid}/notes").json() == []

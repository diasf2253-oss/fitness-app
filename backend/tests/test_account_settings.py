"""Settings > Account/Profile: height and display name. (Password changes
happen in the browser against Supabase Auth — no app endpoint to test.)"""


def test_height_round_trips_and_validates(auth_client):
    assert auth_client.get("/api/settings").json()["height_cm"] is None
    r = auth_client.put("/api/settings", json={"height_cm": 181.5})
    assert r.status_code == 200 and r.json()["height_cm"] == 181.5
    assert auth_client.get("/api/settings").json()["height_cm"] == 181.5
    # Out-of-range heights are rejected, not stored
    assert auth_client.put("/api/settings", json={"height_cm": 20}).status_code == 422


def test_rename_trims_and_rejects_blank(auth_client):
    r = auth_client.patch("/api/auth/me", json={"name": "  Felipe  "})
    assert r.status_code == 200 and r.json()["name"] == "Felipe"
    assert auth_client.get("/api/auth/me").json()["name"] == "Felipe"
    assert auth_client.patch("/api/auth/me", json={"name": "   "}).status_code == 400


def test_old_password_endpoints_are_gone(auth_client):
    """Login, logout and password changes moved to Supabase Auth."""
    for path in ("/api/auth/login", "/api/auth/logout", "/api/auth/change-password"):
        assert auth_client.post(path, json={}).status_code in (404, 405), path

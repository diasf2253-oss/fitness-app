"""
Admin invite codes: create, list, switch off/on. Admin-only throughout.
Also the admin's own-account guards (can't reject yourself) and the
status/role value check on the user-update endpoint.
That sign-up refuses a switched-off or used-up code is covered in
test_supabase_auth.py (test_used_up_or_inactive_codes_are_refused).
"""
from app.models import InviteCode
from tests.conftest import TestingSession


def _create(client, **body):
    r = client.post("/api/admin/invite-codes", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_and_list_newest_first(admin_client):
    first = _create(admin_client, label="gym friends", max_uses=3)
    second = _create(admin_client)

    assert first["label"] == "gym friends" and first["max_uses"] == 3
    assert first["active"] is True and first["uses"] == 0
    assert len(first["code"]) >= 10
    assert second["max_uses"] is None                       # unlimited by default

    listed = admin_client.get("/api/admin/invite-codes").json()
    assert [c["id"] for c in listed] == [second["id"], first["id"]]


def test_rejects_nonsense_limits(admin_client):
    assert admin_client.post("/api/admin/invite-codes", json={"max_uses": 0}).status_code == 422
    assert admin_client.post("/api/admin/invite-codes", json={"label": "x" * 61}).status_code == 422


def test_switch_off_and_back_on(admin_client):
    code = _create(admin_client)
    r = admin_client.patch(f"/api/admin/invite-codes/{code['id']}", json={"active": False})
    assert r.status_code == 200 and r.json()["active"] is False

    db = TestingSession()
    try:
        assert db.get(InviteCode, code["id"]).active is False
    finally:
        db.close()

    r = admin_client.patch(f"/api/admin/invite-codes/{code['id']}", json={"active": True})
    assert r.json()["active"] is True


def test_switching_off_an_unknown_code_is_404(admin_client):
    assert admin_client.patch("/api/admin/invite-codes/9999", json={"active": False}).status_code == 404


def test_regular_users_cannot_touch_invite_codes(auth_client):
    assert auth_client.get("/api/admin/invite-codes").status_code == 403
    assert auth_client.post("/api/admin/invite-codes", json={}).status_code == 403
    assert auth_client.patch("/api/admin/invite-codes/1", json={"active": False}).status_code == 403


def test_admin_cannot_reject_themselves(admin_client):
    me = admin_client.get("/api/auth/me").json()
    r = admin_client.post(f"/api/admin/users/{me['id']}/reject")
    assert r.status_code == 400
    assert admin_client.get("/api/auth/me").json()["status"] == "active"


def test_status_and_role_must_be_known_values(admin_client):
    me = admin_client.get("/api/auth/me").json()
    assert admin_client.patch(f"/api/admin/users/{me['id']}", json={"status": "Active"}).status_code == 422
    assert admin_client.patch(f"/api/admin/users/{me['id']}", json={"role": "superuser"}).status_code == 422

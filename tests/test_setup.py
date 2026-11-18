from app.models.user import User

DATA = {"full_name": "Ngozi Eze", "email": "ngozi@example.ng", "password": "longpass123",
        "confirm": "longpass123", "token": "test-setup-token"}


def test_first_run_claims_the_site_once(app, client):
    client.post("/setup", data={**DATA, "token": "wrong"})
    assert User.query.count() == 0                      # wrong key creates nothing

    assert client.post("/setup", data=DATA).status_code == 302
    coord = User.query.one()
    assert coord.role == "coordinator" and coord.status == "active"

    assert client.get("/setup").status_code == 404      # the page is gone
    assert client.post("/setup", data={**DATA, "email": "x@example.ng"}).status_code == 404
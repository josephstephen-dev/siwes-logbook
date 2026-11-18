import re

from app.extensions import db
from app.models.user import User
from app.services.passwords import hash_password


def test_forgot_password_email_link_works_once(app, client, capsys):
    db.session.add(User(role="student", status="active", full_name="Amara Okoye",
                        matric_number="ENG/1", email="a@example.ng",
                        password_hash=hash_password("oldlongpass123")))
    db.session.commit()

    r = client.post("/forgot-password", data={"identifier": "a@example.ng"})
    assert b"reset link has been sent" in r.data
    link = re.search(r"/reset-password/(\S+)", capsys.readouterr().out).group(1)

    r = client.post(f"/reset-password/{link}",
                    data={"password": "newlongpass123", "confirm": "newlongpass123"})
    assert r.status_code == 302
    assert client.post("/sign-in/student", data={"identifier": "ENG/1",
                                                 "password": "newlongpass123"}).status_code == 302
    assert client.get(f"/reset-password/{link}").status_code == 410      # single use


def test_unknown_account_gets_the_same_answer(app, client):
    r = client.post("/forgot-password", data={"identifier": "nobody@example.ng"})
    assert b"reset link has been sent" in r.data
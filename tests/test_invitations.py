from app.extensions import db
from app.models.user import User
from app.services.invitations import create_link, now
from app.services.passwords import hash_password
from app.services.staff_code import new_code
from app.services.tokens import make_verify_token
STUDENT_FORM = {
    "full_name": "Amara Okoye", "matric_number": "eng/2022/1047",
    "department": "Electrical Engineering", "level": "300",
    "email": "amara@example.ng", "phone": "08031234567",
    "password": "longpass123", "confirm": "longpass123", "consent": "y"}


def _coordinator():
    c = User(role="coordinator", full_name="Ngozi Eze", email="ngozi@example.ng",
             status="active", password_hash=hash_password("coordpass123"))
    db.session.add(c)
    db.session.commit()
    return c


def _student():
    s = User(role="student", status="active", full_name="Amara Okoye",
             matric_number="ENG/2022/1047", email="amara@example.ng",
             password_hash=hash_password("longpass123"))
    db.session.add(s)
    db.session.commit()
    return s

def _verify(client, email):
    user = User.query.filter_by(email=email).one()
    assert client.get(f"/join/verify/{make_verify_token(user)}").status_code == 200

def test_student_signs_up_then_confirms_email(app, client):
    link = create_link("student", _coordinator(), label="2025", days=7)
    db.session.commit()
    url = f"/join/student/{link.token}"
    r = client.post(url, data=STUDENT_FORM, follow_redirects=True)
    assert b"Check your email" in r.data

    r = client.post("/sign-in/student",
                    data={"identifier": "ENG/2022/1047", "password": "longpass123"})
    assert b"Confirm your email first" in r.data

    _verify(client, "amara@example.ng")
    other = app.test_client()
    assert other.post("/sign-in/student",
                      data={"identifier": "amara@example.ng", "password": "longpass123"}).status_code == 302

    r = app.test_client().post(url, data={**STUDENT_FORM, "email": "o@example.ng",
                                          "phone": "08039999999"})
    assert b"already has an account" in r.data      # a confirmed matric number is protected


def test_unconfirmed_signup_can_be_replaced(app, client):
    link = create_link("student", _coordinator(), label="x", days=7)
    db.session.commit()
    url = f"/join/student/{link.token}"
    client.post(url, data={**STUDENT_FORM, "email": "typo@example.ng"})
    client.post(url, data=STUDENT_FORM)
    emails = [u.email for u in User.query.filter_by(role="student")]
    assert emails == ["amara@example.ng"]


def test_supervisor_joins_but_must_confirm_email_and_identity(app, client):
    student = _student()
    link = create_link("supervisor", student, label="s", days=14, max_uses=1, student=student)
    db.session.commit()
    url = f"/join/supervisor/{link.token}"
    r = client.post(url, follow_redirects=True, data={
        "full_name": "Chinedu Okafor", "company": "Northbridge Engineering Ltd.",
        "designation": "Maintenance Engineer", "email": "c.okafor@example.com",
        "phone": "08030000142", "password": "longpass123", "confirm": "longpass123",
        "consent": "y"})
    assert b"Check your email" in r.data
    sup = User.query.filter_by(role="supervisor").one()
    db.session.refresh(student)
    assert student.industry_supervisor_id == sup.id and not sup.is_verified
    assert client.get(url).status_code == 410            # single use

    r = client.post("/sign-in/supervisor",
                    data={"identifier": "c.okafor@example.com", "password": "longpass123"})
    assert b"Confirm your email first" in r.data
    _verify(client, "c.okafor@example.com")
    r = client.post("/sign-in/supervisor",
                    data={"identifier": "c.okafor@example.com", "password": "longpass123"})
    assert r.status_code == 302


def test_staff_needs_code_email_and_approval(app, client):
    _coordinator()
    code = new_code()
    data = {"full_name": "Ada Obi", "email": "ada@example.ng",
            "password": "longpass123", "confirm": "longpass123"}
    client.post("/join/staff", data={**data, "code": "WRONG-CODE-0000"})
    assert User.query.filter_by(email="ada@example.ng").first() is None

    client.post("/join/staff", data={**data, "code": code.lower()})
    ada = User.query.filter_by(email="ada@example.ng").one()
    assert ada.status == "unverified"
    _verify(client, "ada@example.ng")
    db.session.refresh(ada)
    assert ada.status == "pending"
    r = client.post("/sign-in/coordinator",
                    data={"identifier": "ada@example.ng", "password": "longpass123"})
    assert b"waiting for approval" in r.data

    ada.status = "active"
    db.session.commit()
    r = client.post("/sign-in/coordinator",
                    data={"identifier": "ada@example.ng", "password": "longpass123"})
    assert r.status_code == 302

def test_closed_and_unknown_links_do_not_work(app, client):
    link = create_link("student", _coordinator(), label="x", days=7)
    link.closed_at = now()
    db.session.commit()
    assert client.get(f"/join/student/{link.token}").status_code == 410
    assert client.get("/join/student/not-a-real-token").status_code == 410

def test_wrong_role_gets_generic_error(app, client):
    _coordinator()
    r = client.post("/sign-in/student",
                    data={"identifier": "ngozi@example.ng", "password": "coordpass123"})
    assert b"match a student account" in r.data
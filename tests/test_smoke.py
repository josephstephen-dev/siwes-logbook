from datetime import date
from types import SimpleNamespace

import pytest

from app.extensions import db
from app.models.placement import Placement
from app.models.user import User, utcnow
from app.services import approvals, entries, weeks
from app.services.passwords import hash_password

PW = "longpass123"
TEXT = "Assisted with routine workshop maintenance and documented the equipment readings."


@pytest.fixture
def world(app, monkeypatch):
    monkeypatch.setattr(weeks, "today", lambda: date(2025, 5, 17))

    def mk(**kw):
        u = User(status="active", password_hash=hash_password(PW), email_verified_at=utcnow(), **kw)
        db.session.add(u)
        db.session.flush()
        return u

    coord = mk(role="coordinator", full_name="Ngozi Eze", email="coord@example.ng", verified_at=utcnow())
    sup = mk(role="supervisor", full_name="Chinedu Okafor", email="sup@example.ng", phone="+2348030000142",
             company="Northbridge", designation="Engineer", verified_at=utcnow(), verified_by_id=coord.id)
    st = mk(role="student", full_name="Amara Okoye", matric_number="ENG/1", email="stu@example.ng",
            department="Engineering", level="300", industry_supervisor_id=sup.id)
    db.session.add(Placement(student_id=st.id, company_name="Northbridge", school_supervisor="Dr Kemi",
                             start_date=date(2025, 5, 12), end_date=date(2025, 10, 3)))
    db.session.commit()
    with app.test_request_context():
        for i in range(6):
            entries.record_entry(st, date(2025, 5, 12 + i), TEXT + f" Day {i}.")
        wk = weeks.get_week(st, 1)
        approvals.submit_week(st, wk, "Amara Okoye", True)
        return SimpleNamespace(week_id=wk.id, student_id=st.id, placement_id=Placement.query.one().id)


def _client(app, role, ident):
    c = app.test_client()
    r = c.post(f"/sign-in/{role}", data={"identifier": ident, "password": PW})
    assert r.status_code == 302, r.data[:300]
    return c


def _all_ok(client, urls):
    for url in urls:
        r = client.get(url)
        assert r.status_code == 200, f"{url} -> {r.status_code}"


def test_public_pages(app, world):
    c = app.test_client()
    _all_ok(c, ["/", "/sign-in/student", "/sign-in/supervisor", "/sign-in/coordinator",
                "/forgot-password", "/session-expired", "/signed-out", "/v/check",
                "/v/SW-00-XX-AAAA", "/healthz", "/robots.txt", "/sitemap.xml", "/privacy", "/manifest.webmanifest", "/sw.js", "/offline", "/join/staff"])
    assert c.get("/setup").status_code == 404                  # the site is already claimed
    assert b"NOT VALID" in c.get("/v/SW-00-XX-AAAA").data
    assert "noindex" in c.get("/sign-in/student").headers["X-Robots-Tag"]


def test_student_pages(app, world):
    c = _client(app, "student", "stu@example.ng")
    _all_ok(c, ["/student/home", "/student/logbook", "/student/details", "/student/week/1",
                "/student/week/1/sketches", "/student/entry/2025-05-12",
                "/student/entry/2025-05-12/amend", "/help", "/student/supervisor"])


def test_supervisor_pages(app, world):
    c = _client(app, "supervisor", "sup@example.ng")
    _all_ok(c, ["/supervisor/weeks", "/help", f"/supervisor/weeks/{world.week_id}"])


def test_coordinator_pages(app, world):
    c = _client(app, "coordinator", "coord@example.ng")
    _all_ok(c, ["/coordinator/dashboard", "/coordinator/dashboard?risk=Watch&pending=1&sort=name",
                "/coordinator/student-link", "/coordinator/supervisors", "/coordinator/staff",
                "/coordinator/accounts", "/coordinator/placements", "/coordinator/placements/new",
                f"/coordinator/placements/{world.placement_id}/edit",
                f"/coordinator/students/{world.student_id}", "/coordinator/flags", "/coordinator/integrity",
                "/coordinator/finalize", f"/coordinator/finalize/{world.student_id}"])


def test_role_walls(app, world):
    s = _client(app, "student", "stu@example.ng")
    for url in ("/coordinator/dashboard", "/coordinator/staff", "/supervisor/weeks"):
        assert s.get(url).status_code == 403
    sup = _client(app, "supervisor", "sup@example.ng")
    for url in ("/student/home", "/coordinator/accounts"):
        assert sup.get(url).status_code == 403
    r = app.test_client().get("/student/home")
    assert r.status_code == 302


def test_other_supervisor_cannot_open_the_week(app, world):
    db.session.add(User(role="supervisor", status="active", full_name="Other Sup", email="other@example.ng",
                        phone="+2348000000000", company="X", designation="Y",
                        password_hash=hash_password(PW), verified_at=utcnow()))
    db.session.commit()
    c = _client(app, "supervisor", "other@example.ng")
    assert c.get(f"/supervisor/weeks/{world.week_id}").status_code == 404


def test_csv_export_neutralises_formulas(app, world):
    db.session.get(User, world.student_id).full_name = '=HYPERLINK("http://x")'
    db.session.commit()
    r = _client(app, "coordinator", "coord@example.ng").get("/coordinator/dashboard.csv")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    assert b"'=HYPERLINK" in r.data


def test_start_date_locked_once_entries_exist(app, world):
    c = _client(app, "coordinator", "coord@example.ng")
    r = c.post(f"/coordinator/placements/{world.placement_id}/edit", data={
        "company_name": "Northbridge", "company_address": "", "school_supervisor": "",
        "start_date": "2025-05-19", "end_date": "2025-10-03", "working_days": ["0", "1", "2", "3", "4", "5"]})
    assert b"cannot be changed" in r.data

def test_dashboard_filter_and_help(app, world):
    c = _client(app, "coordinator", "coord@example.ng")
    assert b"Amara Okoye" in c.get("/coordinator/dashboard?q=amara").data
    r = c.get("/coordinator/dashboard?q=nobodyhere")
    assert b"No students match" in r.data and b"Clear filters" in r.data
    assert b"Site administrator" in c.get("/help").data
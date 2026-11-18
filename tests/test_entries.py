from datetime import date

import pytest

from app.extensions import db
from app.models.entry import Entry
from app.models.placement import Placement
from app.models.user import User, utcnow
from app.services import approvals, entries, weeks
from app.services.entries import RuleError
from app.services.passwords import hash_password

TEXT = "Assisted with routine workshop maintenance and documented the equipment readings."


def _setup(monkeypatch, verified=True, today=date(2025, 5, 17)):
    sup = User(role="supervisor", status="active", full_name="Chinedu Okafor", email="c@example.com",
               company="Northbridge", designation="Engineer", verified_at=utcnow() if verified else None)
    db.session.add(sup)
    db.session.flush()
    st = User(role="student", status="active", full_name="Amara Okoye", matric_number="ENG/1",
              email="a@example.ng", industry_supervisor_id=sup.id)
    db.session.add(st)
    db.session.flush()
    db.session.add(Placement(student_id=st.id, company_name="Northbridge",
                             start_date=date(2025, 5, 12), end_date=date(2025, 10, 3)))
    db.session.commit()
    monkeypatch.setattr(weeks, "today", lambda: today)
    return st, sup


def _fill_week(st):
    return [entries.record_entry(st, date(2025, 5, 12 + i), TEXT)[0] for i in range(6)]


def test_full_week_lifecycle(app, monkeypatch):
    st, sup = _setup(monkeypatch)
    with app.test_request_context():
        first = _fill_week(st)[0]
        again, created = entries.record_entry(st, date(2025, 5, 12), "a different text that is long enough")
        assert not created and again.body == TEXT                    # a retry never duplicates

        wk = weeks.get_week(st, 1)
        approvals.submit_week(st, wk, "Amara Okoye", True)
        assert wk.status == "submitted"
        with pytest.raises(RuleError):
            entries.amend_entry(first, TEXT + " More.")              # locked while with the supervisor

        approvals.return_entry(sup, wk, date(2025, 5, 13), "Add the meter readings")
        assert wk.status == "returned"
        tue = Entry.query.filter_by(work_date=date(2025, 5, 13)).one()
        entries.amend_entry(tue, TEXT + " Meter reading 230V.")
        assert len(tue.versions) == 2 and tue.status == "recorded"

        approvals.submit_week(st, wk, "Amara Okoye", True)
        approvals.approve_week(sup, wk, "Good work", "Chinedu Okafor", "Engineer")
        assert wk.status == "approved"
        assert all(e.sealed for e in Entry.query.all())
        with pytest.raises(RuleError):
            entries.amend_entry(tue, "Trying to change a sealed entry afterwards.")


def test_late_and_future_days(app, monkeypatch):
    st, _ = _setup(monkeypatch, today=date(2025, 5, 14))
    with app.test_request_context():
        assert entries.record_entry(st, date(2025, 5, 12), TEXT)[0].is_late
        assert not entries.record_entry(st, date(2025, 5, 14), TEXT)[0].is_late
        with pytest.raises(RuleError):
            entries.record_entry(st, date(2025, 5, 15), TEXT)         # future
        with pytest.raises(RuleError):
            entries.record_entry(st, date(2025, 5, 18), TEXT)         # Sunday


def test_submit_needs_every_day(app, monkeypatch):
    st, _ = _setup(monkeypatch)
    with app.test_request_context():
        entries.record_entry(st, date(2025, 5, 12), TEXT)
        with pytest.raises(RuleError):
            approvals.submit_week(st, weeks.get_week(st, 1), "Amara Okoye", True)


def test_unverified_supervisor_cannot_approve(app, monkeypatch):
    st, sup = _setup(monkeypatch, verified=False)
    with app.test_request_context():
        _fill_week(st)
        wk = weeks.get_week(st, 1)
        approvals.submit_week(st, wk, "Amara Okoye", True)
        with pytest.raises(RuleError):
            approvals.approve_week(sup, wk, "", "Chinedu Okafor", "Engineer")


def test_roles_cannot_cross(app, client):
    db.session.add(User(role="student", status="active", full_name="S One", matric_number="M/1",
                        email="s@x.ng", password_hash=hash_password("longpass123")))
    db.session.commit()
    client.post("/sign-in/student", data={"identifier": "M/1", "password": "longpass123"})
    assert client.get("/student/home").status_code == 200
    assert client.get("/supervisor/weeks").status_code == 403
    assert client.get("/coordinator/dashboard").status_code == 403
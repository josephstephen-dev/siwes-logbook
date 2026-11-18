from datetime import date

from test_entries import TEXT, _fill_week, _setup

from app.extensions import db
from app.models.audit_log import AuditEvent
from app.models.entry import Entry
from app.services import audit_chain


def test_chain_verifies_then_detects_tampering(app, monkeypatch):
    st, _ = _setup(monkeypatch)
    with app.test_request_context():
        _fill_week(st)
        assert audit_chain.verify(st.id)[0]

        e = Entry.query.filter_by(work_date=date(2025, 5, 13)).one()
        e.body = "Quietly rewritten text that nobody ever approved or recorded."
        db.session.commit()
        ok, seq, _ = audit_chain.verify(st.id)
        assert not ok and seq == 2                     # Tuesday was the second event
        e.body = TEXT
        db.session.commit()
        assert audit_chain.verify(st.id)[0]

        db.session.delete(AuditEvent.query.filter_by(student_id=st.id, seq=3).one())
        db.session.commit()
        ok, seq, _ = audit_chain.verify(st.id)
        assert not ok and seq == 3                     # the missing record is located


def test_removed_tail_is_caught_by_checkpoint(app, monkeypatch):
    st, _ = _setup(monkeypatch)
    with app.test_request_context():
        _fill_week(st)
        audit_chain.make_checkpoint()
        db.session.delete(AuditEvent.query.filter_by(student_id=st.id, seq=6).one())
        db.session.delete(Entry.query.filter_by(work_date=date(2025, 5, 17)).one())
        db.session.commit()
        assert not audit_chain.run_check(st.id).ok
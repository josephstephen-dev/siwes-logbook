from datetime import date

from app.extensions import db
from app.models.entry import Entry
from app.models.user import User
from app.services import detection

BASE = ("Today I assisted the senior engineer to inspect the main distribution panel and "
        "record the readings in the service register for the week")


def _student(n):
    s = User(role="student", status="active", full_name=f"S{n}", matric_number=f"M/{n}", email=f"s{n}@x.ng")
    db.session.add(s)
    db.session.flush()
    return s


def test_similar_entries_are_flagged_and_different_ones_are_not(app):
    a, b, c = _student(1), _student(2), _student(3)
    db.session.add_all([
        Entry(student_id=a.id, work_date=date(2026, 11, 9), body=BASE),
        Entry(student_id=b.id, work_date=date(2026, 11, 9), body=BASE + " and filed the report"),
        Entry(student_id=c.id, work_date=date(2026, 11, 9),
              body="I spent the day learning how to weld steel brackets and prepare the cutting tools safely")])
    db.session.commit()
    assert detection.scan(since_days=3650) == 1
    assert detection.scan(since_days=3650) == 0          # no duplicates on a second run
    assert "<mark>" in detection.highlight(BASE, BASE + " extra")
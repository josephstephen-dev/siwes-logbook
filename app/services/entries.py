from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.entry import Entry, EntryVersion
from . import weeks
from . import audit_chain
from .canonical import sha256_text

MIN_CHARS, MAX_CHARS = 40, 3000


class RuleError(Exception):
    """A rule was broken. The message is safe to show to the person."""


def check_writable(student, d):
    p = student.placement
    if not p:
        raise RuleError("Your coordinator hasn't set up your placement yet.")
    if d < p.start_date or d > p.end_date:
        raise RuleError("That date is outside your placement.")
    if d.weekday() not in weeks.working_set(p):
        raise RuleError("That isn't one of your working days.")
    if d > weeks.today():
        raise RuleError("You can't write an entry for a day that hasn't happened yet.")
    return p


def _unlocked_week(student, p, d):
    wk = weeks.get_week(student, weeks.week_no_for(p, d))
    if wk.status in ("submitted", "approved"):
        raise RuleError("This week has been sent to your supervisor, so its entries are locked.")
    return wk


def record_entry(student, d, body):
    """Returns (entry, created). Repeating the same request never makes a second entry."""
    p = check_writable(student, d)
    existing = Entry.query.filter_by(student_id=student.id, work_date=d).first()
    if existing:
        return existing, False
    _unlocked_week(student, p, d)
    e = Entry(student_id=student.id, work_date=d, body=body, is_late=d < weeks.today())
    e.versions.append(EntryVersion(version_no=1, body=body))
    db.session.add(e)
    try:
        db.session.flush()
        audit_chain.append(student.id, "entry_recorded",
                           {"date": d.isoformat(), "sha": sha256_text(body), "late": e.is_late})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return Entry.query.filter_by(student_id=student.id, work_date=d).one(), False
    return e, True


def amend_entry(entry, body):
    p = entry.student.placement
    if entry.sealed:
        raise RuleError("This entry is sealed because its week was approved.")
    _unlocked_week(entry.student, p, entry.work_date)
    if body == entry.body:
        raise RuleError("Nothing changed. Edit the text before saving.")
    entry.body = body
    entry.status = "recorded"
    entry.versions.append(EntryVersion(version_no=len(entry.versions) + 1, body=body))
    audit_chain.append(entry.student_id, "entry_amended",
                       {"date": entry.work_date.isoformat(), "sha": sha256_text(body),
                        "version": len(entry.versions)})
    db.session.commit()
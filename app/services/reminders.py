from ..models.entry import Entry
from ..models.placement import Placement
from ..models.user import User
from ..models.week import WeekRecord
from . import weeks
from .invitations import public_url
from .notifications import send_email


def entry_reminders():
    """Run late in the afternoon: students who haven't written today's entry."""
    t, sent = weeks.today(), 0
    for p in Placement.query.all():
        s = p.student
        if s.status != "active" or not s.email or not (p.start_date <= t <= p.end_date):
            continue
        if t.weekday() not in weeks.working_set(p):
            continue
        if Entry.query.filter_by(student_id=s.id, work_date=t).first():
            continue
        send_email(s.email, "Don't forget today's logbook entry",
                   f"Hello {s.full_name.split()[0]},\n\nYou haven't written today's entry yet.\n"
                   f"Open your logbook: {public_url('student.entry_write', day=t.isoformat())}\n")
        sent += 1
    return sent


def supervisor_reminders():
    """Weekly: supervisors with weeks waiting. The link opens sign-in, then that week."""
    sent = 0
    for sup in User.query.filter_by(role="supervisor", status="active"):
        if not sup.is_verified or not sup.email:
            continue
        ids = [s.id for s in sup.supervised_students]
        waiting = (WeekRecord.query.filter(WeekRecord.student_id.in_(ids), WeekRecord.status == "submitted")
                   .order_by(WeekRecord.submitted_at).all()) if ids else []
        if not waiting:
            continue
        send_email(sup.email, f"{len(waiting)} week(s) waiting for your approval",
                   f"Hello {sup.full_name.split()[0]},\n\n{len(waiting)} logbook week(s) are waiting.\n"
                   f"Start with the oldest (you will be asked to sign in):\n"
                   f"{public_url('supervisor.week_review', week_id=waiting[0].id)}\n")
        sent += 1
    return sent